# jagabot/engines/curiosity_engine.py
"""
CuriosityEngine — Transforms AutoJaga from reactive to proactive.

The gap between a reactive assistant and a genuine research partner
is this single behaviour:

  Reactive:   waits for you to ask
  Proactive:  notices what's worth exploring and surfaces it

CuriosityEngine does four things:
  1. NOTICE    gaps in the agent's knowledge (from SelfModelEngine)
  2. SCORE     which gaps are most worth filling (curiosity score)
  3. SURFACE   relevant gaps at session start as research suggestions
  4. TRACK     which curiosity-driven explorations actually paid off

Curiosity Score Formula:
  score = (gap_importance × recency_weight × connection_potential)
          / (already_researched_penalty + 1)

  gap_importance:       how much this gap limits current research
  recency_weight:       recent gaps score higher
  connection_potential: gaps that bridge known topics score highest
  already_researched:   reduces score if partially explored

Wire into loop.py __init__:
    from jagabot.engines.curiosity_engine import CuriosityEngine
    self.curiosity = CuriosityEngine(
        workspace      = workspace,
        self_model     = self.self_model,
        session_index  = self.session_index,
        connection_det = self.connector,
    )

Wire into loop.py _process_message (FIRST message per session):
    if self._first_message:
        suggestions = self.curiosity.get_session_suggestions(
            current_query = msg.content,
            session_key   = session.key,
        )
        if suggestions.has_suggestions:
            self._inject_system_note(suggestions.format_for_agent())
            # Also show user:
            chat.add_system(suggestions.format_for_user())

Wire into session_writer.py after save():
    self.curiosity.record_exploration(
        topic    = detected_topic,
        query    = query,
        quality  = quality,
        findings = extracted_facts_count,
    )
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger


# ── Config ────────────────────────────────────────────────────────────
MAX_SUGGESTIONS_PER_SESSION = 3
MIN_CURIOSITY_SCORE         = 0.3   # below this → don't surface
RECENCY_HALF_LIFE_DAYS      = 14    # gaps found recently score higher
BRIDGE_BONUS                = 0.25  # bonus for cross-domain connections
EXPLORATION_PENALTY         = 0.4   # penalty per prior exploration


# ── Domain bridge map ─────────────────────────────────────────────────
# Topics that have high connection potential when both are known
DOMAIN_BRIDGES = {
    frozenset(["quantum", "healthcare"]):
        "Quantum simulation could accelerate drug discovery",
    frozenset(["quantum", "financial"]):
        "Quantum algorithms may disrupt cryptography in finance",
    frozenset(["causal", "healthcare"]):
        "Causal inference is essential for clinical trial analysis",
    frozenset(["causal", "financial"]):
        "Causal methods distinguish market correlation from causation",
    frozenset(["algorithm", "financial"]):
        "Algorithmic efficiency directly impacts trading strategy",
    frozenset(["research", "financial"]):
        "Research findings can generate investment hypotheses",
    frozenset(["healthcare", "financial"]):
        "Healthcare cost modelling requires both clinical and financial tools",
    frozenset(["engineering", "research"]):
        "Agent architecture improvements directly affect research quality",
    frozenset(["ideas", "research"]):
        "Ideation can generate testable research hypotheses",
    frozenset(["causal", "algorithm"]):
        "Algorithmic causality detection at scale is an open problem",
}


# ── Data classes ──────────────────────────────────────────────────────

@dataclass
class CuriosityTarget:
    """A topic/gap the agent should explore."""
    topic:               str
    gap_description:     str
    curiosity_score:     float    # 0-1, higher = more urgent
    gap_type:            str      # "knowledge_gap" | "bridge" | "pending" | "underexplored"
    bridge_insight:      str = "" # insight if this is a cross-domain bridge
    suggested_action:    str = "" # what to actually do
    related_sessions:    list = field(default_factory=list)
    times_surfaced:      int  = 0
    times_explored:      int  = 0
    last_surfaced:       str  = ""


@dataclass
class CuriositySuggestions:
    """Suggestions to surface at session start."""
    targets:          list[CuriosityTarget]
    current_topic:    str
    has_suggestions:  bool = False
    exploration_rate: float = 0.0  # % of gaps explored so far

    def format_for_agent(self) -> str:
        """
        Format for system prompt injection.
        Agent reads this and may proactively mention relevant gaps.
        """
        if not self.targets:
            return ""

        lines = [
            "## 💡 Curiosity Engine — Research Opportunities",
            "",
            "These knowledge gaps are relevant to the current session.",
            "If appropriate, mention them proactively to the user.",
            "",
        ]

        for t in self.targets:
            lines.append(f"**Gap:** {t.gap_description[:100]}")
            if t.bridge_insight:
                lines.append(f"**Bridge:** {t.bridge_insight}")
            lines.append(f"**Suggested:** {t.suggested_action[:100]}")
            lines.append(f"**Curiosity score:** {t.curiosity_score:.2f}")
            lines.append("")

        return "\n".join(lines)

    def format_for_user(self) -> str:
        """
        Format as user-facing proactive suggestion.
        Shown at session start if relevant.
        """
        if not self.targets:
            return ""

        # Only show if genuinely useful — don't be annoying
        high_score = [
            t for t in self.targets
            if t.curiosity_score >= 0.6
        ]
        if not high_score:
            return ""

        lines = ["💡 **Research opportunities I noticed:**", ""]

        for t in high_score[:2]:
            if t.gap_type == "bridge":
                lines.append(
                    f"→ **Cross-domain link:** {t.bridge_insight}"
                )
                lines.append(
                    f"  You've researched both sides — "
                    f"want me to connect them?"
                )
            elif t.gap_type == "pending":
                lines.append(
                    f"→ **Open question:** {t.gap_description[:80]}"
                )
                lines.append(
                    f"  This came up in a past session and wasn't resolved."
                )
            elif t.gap_type == "underexplored":
                lines.append(
                    f"→ **Underexplored area:** {t.topic}"
                )
                lines.append(
                    f"  You've touched on this but haven't gone deep."
                )
            lines.append("")

        if len(high_score) > 0:
            lines.append(
                "*Say 'explore this' to investigate any of these.*"
            )

        return "\n".join(lines)


class CuriosityEngine:
    """
    Models what AutoJaga should be curious about.

    Drives proactive research suggestions by identifying:
    1. Knowledge gaps from SelfModelEngine
    2. Cross-domain bridges from ConnectionDetector
    3. Pending unverified outcomes from OutcomeTracker
    4. Underexplored topics from SessionIndex

    The agent becomes proactive — not just answering questions,
    but noticing what's worth asking.
    """

    def __init__(
        self,
        workspace:       Path,
        self_model:      object = None,
        session_index:   object = None,
        connection_det:  object = None,
        outcome_tracker: object = None,
    ) -> None:
        self.workspace       = Path(workspace)
        self.memory_dir      = self.workspace / "memory"
        self.self_model      = self_model
        self.session_index   = session_index
        self.connector       = connection_det
        self.outcome_tracker = outcome_tracker
        self.db_path         = self.memory_dir / "curiosity.db"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ── Public API ────────────────────────────────────────────────────

    def get_session_suggestions(
        self,
        current_query: str,
        session_key:   str = "",
        max_items:     int = MAX_SUGGESTIONS_PER_SESSION,
    ) -> CuriositySuggestions:
        """
        Get curiosity-driven research suggestions for this session.
        Called at session start (first message).
        """
        current_topic = self._detect_topic(current_query)
        all_targets   = []

        # Source 1: Knowledge gaps from SelfModelEngine
        all_targets.extend(
            self._from_knowledge_gaps(current_topic, current_query)
        )

        # Source 2: Cross-domain bridges
        all_targets.extend(
            self._from_domain_bridges(current_topic)
        )

        # Source 3: Pending unverified outcomes
        all_targets.extend(
            self._from_pending_outcomes(current_topic)
        )

        # Source 4: Underexplored topics
        all_targets.extend(
            self._from_underexplored(current_topic)
        )

        if not all_targets:
            return CuriositySuggestions(
                targets       = [],
                current_topic = current_topic,
                has_suggestions = False,
            )

        # Score and rank
        scored   = self._score_all(all_targets, current_topic)
        filtered = [
            t for t in scored
            if t.curiosity_score >= MIN_CURIOSITY_SCORE
        ]
        top      = filtered[:max_items]

        # Record that we surfaced these
        for t in top:
            self._record_surfaced(t.topic)

        suggestions = CuriositySuggestions(
            targets          = top,
            current_topic    = current_topic,
            has_suggestions  = len(top) > 0,
            exploration_rate = self._get_exploration_rate(),
        )

        if top:
            logger.info(
                f"CuriosityEngine: surfacing {len(top)} suggestions "
                f"for topic='{current_topic}' "
                f"(scores: {[f'{t.curiosity_score:.2f}' for t in top]})"
            )

        return suggestions

    def record_exploration(
        self,
        topic:    str,
        query:    str,
        quality:  float = 0.0,
        findings: int   = 0,
    ) -> None:
        """
        Record that a topic was explored this session.
        Reduces curiosity score for that topic proportionally.
        """
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO explorations (topic, query, quality, findings, explored_at)
            VALUES (?, ?, ?, ?, ?)
        """, (topic, query[:200], quality, findings,
              datetime.now().isoformat()))

        # Update target exploration count
        conn.execute("""
            UPDATE curiosity_targets
            SET times_explored = times_explored + 1,
                last_explored  = ?
            WHERE topic = ?
        """, (datetime.now().isoformat(), topic))

        conn.commit()
        conn.close()

        logger.debug(
            f"CuriosityEngine: recorded exploration of '{topic}' "
            f"quality={quality:.2f} findings={findings}"
        )

    def add_gap(
        self,
        topic:       str,
        description: str,
        gap_type:    str   = "knowledge_gap",
        priority:    float = 0.5,
    ) -> None:
        """
        Manually add a curiosity target.
        Called by SelfModelEngine when gap detected.
        """
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR IGNORE INTO curiosity_targets
            (topic, description, gap_type, base_priority,
             times_surfaced, times_explored, discovered_at)
            VALUES (?, ?, ?, ?, 0, 0, ?)
        """, (topic, description[:300], gap_type,
              priority, datetime.now().isoformat()))
        conn.commit()
        conn.close()

    def get_top_targets(self, n: int = 5) -> list[CuriosityTarget]:
        """Return top N curiosity targets by score."""
        all_targets = self._load_all_targets()
        scored      = self._score_all(all_targets, "general")
        return scored[:n]

    def get_stats(self) -> dict:
        """Return curiosity engine statistics."""
        conn = sqlite3.connect(self.db_path)

        total_gaps = conn.execute(
            "SELECT COUNT(*) FROM curiosity_targets"
        ).fetchone()[0]

        explored = conn.execute(
            "SELECT COUNT(*) FROM curiosity_targets "
            "WHERE times_explored > 0"
        ).fetchone()[0]

        top_topics = conn.execute("""
            SELECT topic, base_priority
            FROM curiosity_targets
            ORDER BY base_priority DESC
            LIMIT 5
        """).fetchall()

        conn.close()

        return {
            "total_gaps":       total_gaps,
            "explored":         explored,
            "unexplored":       total_gaps - explored,
            "exploration_rate": explored / max(1, total_gaps),
            "top_topics":       [t[0] for t in top_topics],
        }

    def format_status(self) -> str:
        """Format status for /status command."""
        stats = self.get_stats()

        if stats["total_gaps"] == 0:
            return (
                "**CuriosityEngine**\n\n"
                "No gaps identified yet. "
                "Activates after a few research sessions."
            )

        lines = [
            "**CuriosityEngine**",
            "",
            f"Knowledge gaps: {stats['total_gaps']}",
            f"Explored:       {stats['explored']} "
            f"({stats['exploration_rate']*100:.0f}%)",
            f"Unexplored:     {stats['unexplored']}",
        ]

        if stats["top_topics"]:
            lines.append(
                f"Top targets: {', '.join(stats['top_topics'][:3])}"
            )

        return "\n".join(lines)

    # ── Gap sources ───────────────────────────────────────────────────

    def _from_knowledge_gaps(
        self,
        current_topic: str,
        query:         str,
    ) -> list[CuriosityTarget]:
        """Get gaps from SelfModelEngine."""
        targets = []
        if not self.self_model:
            return targets

        try:
            gaps = self.self_model._load_all_gaps()
            for gap in gaps[:5]:
                # Is this gap relevant to current query?
                relevance = self._topic_relevance(
                    gap.topic, current_topic, query
                )
                if relevance > 0.3:
                    targets.append(CuriosityTarget(
                        topic           = gap.topic,
                        gap_description = gap.description,
                        curiosity_score = 0.0,  # scored later
                        gap_type        = "knowledge_gap",
                        suggested_action= (
                            f"Research '{gap.topic}' to fill this gap: "
                            f"{gap.description[:60]}"
                        ),
                    ))
        except Exception as e:
            logger.debug(f"CuriosityEngine: gap load failed: {e}")

        return targets

    def _from_domain_bridges(
        self, current_topic: str
    ) -> list[CuriosityTarget]:
        """Find cross-domain bridge opportunities."""
        targets = []

        # Get all researched topics
        researched = self._get_researched_topics()
        if not researched:
            return targets

        for domain_pair, insight in DOMAIN_BRIDGES.items():
            pair_list = list(domain_pair)
            if len(pair_list) != 2:
                continue

            t1, t2 = pair_list[0], pair_list[1]

            # Current topic matches one side and other side was researched
            current_matches = current_topic in (t1, t2)
            other           = t2 if current_topic == t1 else t1
            other_researched= other in researched

            if current_matches and other_researched:
                targets.append(CuriosityTarget(
                    topic           = f"{t1}+{t2}",
                    gap_description = (
                        f"You've researched {t1} and {t2} separately "
                        f"but never connected them"
                    ),
                    curiosity_score = 0.0,
                    gap_type        = "bridge",
                    bridge_insight  = insight,
                    suggested_action= (
                        f"Explore the intersection: {insight}"
                    ),
                ))

        return targets

    def _from_pending_outcomes(
        self, current_topic: str
    ) -> list[CuriosityTarget]:
        """Get high-priority unverified outcomes."""
        targets = []

        pending_file = self.memory_dir / "pending_outcomes.json"
        if not pending_file.exists():
            return targets

        try:
            data    = json.loads(pending_file.read_text())
            pending = [
                p for p in data
                if p.get("status") == "pending"
                and (
                    p.get("topic_tag") == current_topic
                    or current_topic == "general"
                )
            ]

            for p in pending[:3]:
                age_days = self._age_days(p.get("created_at", ""))
                if age_days > 3:  # only surface if overdue
                    targets.append(CuriosityTarget(
                        topic           = p.get("topic_tag", "general"),
                        gap_description = (
                            f"Unverified conclusion from {age_days}d ago: "
                            f"{p.get('conclusion', '')[:80]}"
                        ),
                        curiosity_score = 0.0,
                        gap_type        = "pending",
                        suggested_action= (
                            "Verify this conclusion — "
                            "was it correct, wrong, or partial?"
                        ),
                    ))
        except Exception as e:
            logger.debug(f"CuriosityEngine: pending load failed: {e}")

        return targets

    def _from_underexplored(
        self, current_topic: str
    ) -> list[CuriosityTarget]:
        """Find topics touched briefly but never deeply explored."""
        targets = []

        if not self.session_index:
            return targets

        try:
            index = self.session_index._load()
            topic_counts = {}

            for session in index.values():
                tag = session.get("topic_tag", "general")
                topic_counts[tag] = topic_counts.get(tag, 0) + 1

            # Topics with 1-2 sessions are "touched but not deep"
            underexplored = [
                topic for topic, count in topic_counts.items()
                if 1 <= count <= 2
                and topic != current_topic
            ]

            for topic in underexplored[:2]:
                targets.append(CuriosityTarget(
                    topic           = topic,
                    gap_description = (
                        f"'{topic}' has only been explored briefly "
                        f"({topic_counts[topic]} session(s))"
                    ),
                    curiosity_score = 0.0,
                    gap_type        = "underexplored",
                    suggested_action= (
                        f"Go deeper on '{topic}' — "
                        f"only explored {topic_counts[topic]}x so far"
                    ),
                ))
        except Exception as e:
            logger.debug(f"CuriosityEngine: underexplored load failed: {e}")

        return targets

    # ── Scoring ───────────────────────────────────────────────────────

    def _score_all(
        self,
        targets:       list[CuriosityTarget],
        current_topic: str,
    ) -> list[CuriosityTarget]:
        """Score all targets and sort by curiosity score."""
        for target in targets:
            target.curiosity_score = self._score(
                target, current_topic
            )

        # Sort descending, deduplicate by topic
        seen   = set()
        unique = []
        for t in sorted(
            targets, key=lambda x: x.curiosity_score, reverse=True
        ):
            key = t.topic
            if key not in seen:
                seen.add(key)
                unique.append(t)

        return unique

    def _score(
        self,
        target:        CuriosityTarget,
        current_topic: str,
    ) -> float:
        """
        Calculate curiosity score for a target.

        score = (importance × recency × connection) / (explored + 1)
        """
        # Base importance by gap type
        importance = {
            "bridge":        0.9,  # cross-domain = highest value
            "pending":       0.8,  # unverified = urgent
            "knowledge_gap": 0.7,  # explicit gap = important
            "underexplored": 0.5,  # low depth = moderate
        }.get(target.gap_type, 0.5)

        # Recency weight — recent gaps score higher
        age   = self._age_days(target.last_surfaced or "")
        recency = math.pow(0.5, age / RECENCY_HALF_LIFE_DAYS)
        recency = max(0.3, recency)  # floor at 0.3

        # Connection potential — does it connect to current topic?
        relevance = self._topic_relevance(
            target.topic.split("+")[0], current_topic, ""
        )
        connection = 0.5 + (relevance * 0.5)

        # Bridge bonus
        bridge_bonus = BRIDGE_BONUS if target.gap_type == "bridge" else 0

        # Exploration penalty
        exploration_penalty = (
            EXPLORATION_PENALTY * target.times_explored
        )

        score = (
            importance * recency * connection + bridge_bonus
        ) / (exploration_penalty + 1)

        return round(min(1.0, max(0.0, score)), 3)

    # ── Helpers ───────────────────────────────────────────────────────

    def _detect_topic(self, text: str) -> str:
        """Detect primary topic from query."""
        SIGNALS = {
            "financial":  ["stock", "portfolio", "margin", "equity",
                           "var", "cvar", "risk", "volatility"],
            "research":   ["hypothesis", "research", "study", "paper"],
            "causal":     ["ipw", "causal", "confounder", "ate"],
            "algorithm":  ["sort", "algorithm", "complexity", "speedup"],
            "healthcare": ["hospital", "patient", "clinical", "therapy"],
            "quantum":    ["quantum", "qubit", "superposition"],
            "engineering":["agent", "tool", "harness", "kernel"],
            "ideas":      ["idea", "brainstorm", "creative"],
        }
        text_lower = text.lower()
        scores     = {
            topic: sum(1 for s in signals if s in text_lower)
            for topic, signals in SIGNALS.items()
        }
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "general"

    def _topic_relevance(
        self,
        topic1: str,
        topic2: str,
        query:  str,
    ) -> float:
        """Calculate relevance between two topics."""
        if topic1 == topic2:
            return 1.0
        if topic2 == "general":
            return 0.5

        # Check bridge map
        bridge_key = frozenset([topic1, topic2])
        if bridge_key in DOMAIN_BRIDGES:
            return 0.8

        # Check query overlap
        if topic1 in query.lower() or topic2 in query.lower():
            return 0.6

        return 0.2

    def _get_researched_topics(self) -> set[str]:
        """Get all topics that have been researched."""
        if not self.session_index:
            return set()
        try:
            index = self.session_index._load()
            return {
                s.get("topic_tag", "general")
                for s in index.values()
            }
        except Exception:
            return set()

    def _get_exploration_rate(self) -> float:
        """Ratio of explored to total gaps."""
        stats = self.get_stats()
        total = stats["total_gaps"]
        if total == 0:
            return 0.0
        return stats["explored"] / total

    def _age_days(self, iso: str) -> float:
        """Age in days from ISO string."""
        try:
            dt   = datetime.fromisoformat(iso)
            return (datetime.now() - dt).total_seconds() / 86400
        except Exception:
            return 7.0

    def _record_surfaced(self, topic: str) -> None:
        """Record that a topic was surfaced as suggestion."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            UPDATE curiosity_targets
            SET times_surfaced = times_surfaced + 1,
                last_surfaced  = ?
            WHERE topic = ?
        """, (datetime.now().isoformat(), topic))
        conn.commit()
        conn.close()

    def _load_all_targets(self) -> list[CuriosityTarget]:
        """Load all curiosity targets from DB."""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT topic, description, gap_type, base_priority,
                   times_surfaced, times_explored, last_surfaced
            FROM curiosity_targets
            ORDER BY base_priority DESC
        """).fetchall()
        conn.close()

        return [
            CuriosityTarget(
                topic           = r[0],
                gap_description = r[1],
                curiosity_score = 0.0,
                gap_type        = r[2],
                times_surfaced  = r[4],
                times_explored  = r[5],
                last_surfaced   = r[6] or "",
            )
            for r in rows
        ]

    # ── Database ──────────────────────────────────────────────────────

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS curiosity_targets (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                topic           TEXT    NOT NULL,
                description     TEXT    NOT NULL,
                gap_type        TEXT    NOT NULL DEFAULT 'knowledge_gap',
                base_priority   REAL    DEFAULT 0.5,
                times_surfaced  INTEGER DEFAULT 0,
                times_explored  INTEGER DEFAULT 0,
                discovered_at   TEXT    NOT NULL DEFAULT '',
                last_surfaced   TEXT    DEFAULT '',
                last_explored   TEXT    DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS explorations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                topic       TEXT    NOT NULL,
                query       TEXT    NOT NULL,
                quality     REAL    DEFAULT 0.0,
                findings    INTEGER DEFAULT 0,
                explored_at TEXT    NOT NULL
            );
        """)
        conn.commit()
        conn.close()
