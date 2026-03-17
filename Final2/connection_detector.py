# jagabot/agent/connection_detector.py
"""
ConnectionDetector — Proactive cross-session insight engine.

The gap between "smart chatbot" and "genuine research partner"
is this: a research partner notices connections you didn't ask for.

"You researched quantum computing last week.
 Today you're asking about drug discovery timelines.
 There's a direct link — want me to explore it?"

Uses:
    SessionIndex    → knows past topics and conclusions
    MemoryFleet     → knows concept relationships
    KnowledgeGraph  → knows entity connections
    OutcomeTracker  → knows what was verified true

Runs at session start. Injects proactive connections
into context if found. Silent if nothing relevant.

Wire into loop.py __init__:
    from jagabot.agent.connection_detector import ConnectionDetector
    self.connector = ConnectionDetector(workspace, tool_registry)

Wire into loop.py _process_message (first message):
    connections = self.connector.detect(
        current_query=msg.content,
        session_key=session.key,
    )
    if connections.has_insights:
        self._inject_system_note(connections.format_for_context())
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger


# ── Connection strength thresholds ─────────────────────────────────
MIN_KEYWORD_OVERLAP  = 2     # min shared keywords to flag connection
MIN_SESSION_QUALITY  = 0.6   # only connect to decent-quality sessions
MAX_CONNECTIONS      = 3     # max connections to surface per session
DAYS_LOOKBACK        = 30    # how far back to look


# ── Domain connection map ───────────────────────────────────────────
# Pairs of topics that often have hidden connections
# Agent surfaces these when both appear in recent sessions
DOMAIN_BRIDGES = {
    ("quantum", "healthcare"):
        "Quantum simulation can accelerate protein folding for drug discovery",
    ("quantum", "financial"):
        "Quantum algorithms may break current encryption in financial systems",
    ("causal", "healthcare"):
        "Causal inference is critical for clinical trial analysis",
    ("causal", "financial"):
        "Causal methods distinguish market correlation from causation",
    ("ideas", "research"):
        "Ideation sessions can generate hypotheses for formal research",
    ("engineering", "research"):
        "Agent architecture improvements directly affect research quality",
    ("healthcare", "financial"):
        "Healthcare cost analysis requires both clinical and financial tools",
    ("research", "financial"):
        "Research findings can inform investment thesis generation",
    ("learning", "research"):
        "Self-improvement loop quality determines research partner reliability",
    ("causal", "ideas"):
        "Causal thinking can structure creative ideation into testable hypotheses",
}

# Keyword clusters for topic detection
TOPIC_CLUSTERS = {
    "quantum":      ["quantum", "qubit", "superposition", "entanglement",
                     "quantum computing", "qc"],
    "healthcare":   ["hospital", "patient", "clinical", "therapy", "drug",
                     "medical", "hipaa", "counselor", "mental health"],
    "financial":    ["stock", "portfolio", "risk", "margin", "equity",
                     "investment", "var", "volatility", "monte carlo"],
    "causal":       ["causal", "ipw", "confounder", "regression",
                     "propensity", "treatment effect", "ate"],
    "research":     ["hypothesis", "experiment", "study", "paper",
                     "literature", "findings", "conclusion"],
    "ideas":        ["brainstorm", "idea", "creative", "novel", "strategy",
                     "innovative", "out of the box"],
    "engineering":  ["agent", "tool", "harness", "kernel", "engine",
                     "loop", "context", "session", "tui"],
    "learning":     ["calibration", "accuracy", "self-improvement",
                     "meta learning", "outcome", "verified"],
}


@dataclass
class Connection:
    """A detected connection between current query and past research."""
    past_topic:       str
    past_session_key: str
    past_date:        str
    past_summary:     str
    connection_type:  str       # "keyword" | "domain_bridge" | "verified_finding"
    bridge_insight:   str       # the specific connection explanation
    strength:         float     # 0.0 - 1.0
    verified:         bool = False  # was past finding verified correct?


@dataclass
class ConnectionReport:
    """Result of connection detection for one query."""
    current_query:   str
    current_topic:   str
    connections:     list = field(default_factory=list)
    has_insights:    bool = False
    open_questions:  list = field(default_factory=list)

    def format_for_context(self) -> str:
        """
        Format connections as context injection.
        Designed to be concise — max 200 tokens.
        """
        if not self.has_insights:
            return ""

        lines = ["## 💡 Research Connections Found", ""]

        for conn in self.connections[:MAX_CONNECTIONS]:
            verified_note = " [verified ✅]" if conn.verified else ""
            lines.append(
                f"**{conn.past_date}** — you researched "
                f"*{conn.past_topic}*{verified_note}"
            )
            if conn.past_summary:
                lines.append(f"  Finding: {conn.past_summary[:80]}")
            if conn.bridge_insight:
                lines.append(f"  Link: {conn.bridge_insight}")
            lines.append("")

        if self.open_questions:
            lines.append("**Open questions from past research:**")
            for q in self.open_questions[:2]:
                lines.append(f"- {q[:80]}")
            lines.append("")

        lines.append(
            "*Mention any of these topics to build on past findings.*"
        )
        return "\n".join(lines)

    def format_for_user(self) -> str:
        """
        Format connections as a user-facing message.
        More conversational than context injection.
        """
        if not self.has_insights:
            return ""

        lines = ["💡 **I found connections to your past research:**", ""]

        for i, conn in enumerate(self.connections[:MAX_CONNECTIONS], 1):
            verified_note = " *(verified correct)*" if conn.verified else ""
            lines.append(
                f"{i}. **{conn.past_topic}** ({conn.past_date})"
                f"{verified_note}"
            )
            if conn.bridge_insight:
                lines.append(f"   → {conn.bridge_insight}")
            lines.append("")

        if self.open_questions:
            lines.append("**Unresolved questions from past sessions:**")
            for q in self.open_questions[:2]:
                lines.append(f"- {q}")

        lines.append(
            "\nWant me to build on any of these findings?"
        )
        return "\n".join(lines)


class ConnectionDetector:
    """
    Detects proactive connections between current query
    and past research sessions.

    Priority order:
    1. Verified correct findings (highest trust)
    2. Domain bridge connections (conceptual links)
    3. Keyword overlap connections (surface similarity)
    """

    def __init__(
        self,
        workspace:     Path,
        tool_registry: object = None,
    ) -> None:
        self.workspace     = Path(workspace)
        self.memory_dir    = self.workspace / "memory"
        self.tool_registry = tool_registry
        self._index_cache  = None
        self._index_mtime  = 0

    # ── Public API ──────────────────────────────────────────────────

    def detect(
        self,
        current_query: str,
        session_key:   str = "",
    ) -> ConnectionReport:
        """
        Detect connections between current query and past research.
        Returns ConnectionReport — silent if nothing relevant found.
        """
        current_topic = self._detect_topic(current_query)

        report = ConnectionReport(
            current_query = current_query[:80],
            current_topic = current_topic,
        )

        # Load session index
        index = self._load_session_index()
        if not index:
            return report

        # Get past sessions (excluding current)
        past = [
            v for k, v in index.items()
            if k != session_key
            and v.get("quality_avg", 0) >= MIN_SESSION_QUALITY
            and self._is_within_lookback(v.get("last_active", ""))
        ]

        if not past:
            return report

        connections = []

        # 1. Check verified findings first
        verified = self._find_verified_connections(
            current_query, current_topic, past
        )
        connections.extend(verified)

        # 2. Check domain bridges
        bridges = self._find_domain_bridges(current_topic, past)
        connections.extend(bridges)

        # 3. Check keyword overlap
        if len(connections) < MAX_CONNECTIONS:
            keywords = self._find_keyword_connections(
                current_query, current_topic, past,
                exclude_sessions={
                    c.past_session_key for c in connections
                }
            )
            connections.extend(keywords)

        # Sort by strength, cap at max
        connections.sort(key=lambda c: c.strength, reverse=True)
        connections = connections[:MAX_CONNECTIONS]

        # Load open questions from OutcomeTracker
        open_q = self._load_open_questions(current_topic)

        report.connections   = connections
        report.has_insights  = len(connections) > 0 or len(open_q) > 0
        report.open_questions= open_q

        if connections:
            logger.info(
                f"ConnectionDetector: found {len(connections)} "
                f"connections for topic '{current_topic}'"
            )

        return report

    def get_research_map(self) -> dict:
        """
        Return a map of all research topics and their connections.
        Used for KnowledgeGraph and research agenda view.
        """
        index = self._load_session_index()
        if not index:
            return {"topics": {}, "connections": []}

        # Build topic frequency map
        topics = {}
        for session in index.values():
            tag = session.get("topic_tag", "general")
            topics[tag] = topics.get(tag, 0) + 1

        # Build connection map from domain bridges
        found_connections = []
        topic_list = list(topics.keys())
        for i, t1 in enumerate(topic_list):
            for t2 in topic_list[i+1:]:
                key1 = (t1, t2)
                key2 = (t2, t1)
                bridge = (
                    DOMAIN_BRIDGES.get(key1) or
                    DOMAIN_BRIDGES.get(key2)
                )
                if bridge:
                    found_connections.append({
                        "from":    t1,
                        "to":      t2,
                        "insight": bridge,
                    })

        return {
            "topics":      topics,
            "connections": found_connections,
            "session_count": len(index),
        }

    # ── Detection strategies ────────────────────────────────────────

    def _find_verified_connections(
        self,
        current_query: str,
        current_topic: str,
        past_sessions: list,
    ) -> list[Connection]:
        """Find connections to verified-correct past findings."""
        connections = []
        bridge_log  = self._load_bridge_log()

        # Get verified-correct conclusions
        verified = [
            e for e in bridge_log
            if e.get("result") == "correct"
        ]

        for entry in verified:
            conclusion = entry.get("conclusion", "")
            # Does this verified finding relate to current query?
            overlap = self._keyword_overlap(
                current_query, conclusion
            )
            if overlap >= MIN_KEYWORD_OVERLAP:
                # Find the session it came from
                session = self._find_session_by_content(
                    conclusion, past_sessions
                )
                if session:
                    connections.append(Connection(
                        past_topic       = session.get("topic_tag", "research"),
                        past_session_key = session.get("session_key", ""),
                        past_date        = self._format_date(
                            session.get("last_active", "")
                        ),
                        past_summary     = conclusion[:80],
                        connection_type  = "verified_finding",
                        bridge_insight   = (
                            f"You verified this correct: '{conclusion[:60]}'"
                        ),
                        strength         = min(overlap / 5, 1.0) + 0.3,
                        verified         = True,
                    ))

        return connections[:2]

    def _find_domain_bridges(
        self,
        current_topic: str,
        past_sessions: list,
    ) -> list[Connection]:
        """Find connections via known domain bridge map."""
        connections  = []
        past_topics  = {
            s.get("topic_tag", ""): s
            for s in past_sessions
        }

        for (t1, t2), insight in DOMAIN_BRIDGES.items():
            # Current topic matches one side of a bridge
            if current_topic not in (t1, t2):
                continue

            other_topic = t2 if current_topic == t1 else t1

            # Do we have past research on the other topic?
            past = past_topics.get(other_topic)
            if not past:
                continue

            connections.append(Connection(
                past_topic       = other_topic,
                past_session_key = past.get("session_key", ""),
                past_date        = self._format_date(
                    past.get("last_active", "")
                ),
                past_summary     = past.get("summary", "")[:80],
                connection_type  = "domain_bridge",
                bridge_insight   = insight,
                strength         = 0.7,
                verified         = False,
            ))

        return connections[:2]

    def _find_keyword_connections(
        self,
        current_query:    str,
        current_topic:    str,
        past_sessions:    list,
        exclude_sessions: set = None,
    ) -> list[Connection]:
        """Find connections via keyword overlap with past sessions."""
        connections      = []
        exclude_sessions = exclude_sessions or set()

        for session in past_sessions:
            key = session.get("session_key", "")
            if key in exclude_sessions:
                continue
            if session.get("topic_tag") == current_topic:
                # Same topic — not a cross-session connection,
                # but still useful to surface
                summary = session.get("summary", "")
                if summary:
                    overlap = self._keyword_overlap(
                        current_query,
                        session.get("first_query", "") + " " + summary
                    )
                    if overlap >= MIN_KEYWORD_OVERLAP + 1:
                        connections.append(Connection(
                            past_topic       = current_topic,
                            past_session_key = key,
                            past_date        = self._format_date(
                                session.get("last_active", "")
                            ),
                            past_summary     = summary[:80],
                            connection_type  = "keyword",
                            bridge_insight   = (
                                "You researched this before — "
                                "building on past findings"
                            ),
                            strength         = min(overlap / 8, 0.6),
                            verified         = False,
                        ))

        connections.sort(key=lambda c: c.strength, reverse=True)
        return connections[:1]

    # ── Helpers ─────────────────────────────────────────────────────

    def _detect_topic(self, text: str) -> str:
        """Detect primary topic from text."""
        text_lower = text.lower()
        scores     = {}
        for topic, keywords in TOPIC_CLUSTERS.items():
            scores[topic] = sum(
                1 for kw in keywords if kw in text_lower
            )
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "general"

    def _keyword_overlap(self, text1: str, text2: str) -> int:
        """Count shared meaningful words between two texts."""
        stop = {
            "the", "a", "an", "is", "are", "was", "were",
            "it", "this", "that", "and", "or", "but", "in",
            "on", "at", "to", "for", "of", "with", "by",
            "i", "you", "we", "they", "my", "your", "our",
        }
        words1 = {
            w for w in re.findall(r'\b\w+\b', text1.lower())
            if w not in stop and len(w) > 3
        }
        words2 = {
            w for w in re.findall(r'\b\w+\b', text2.lower())
            if w not in stop and len(w) > 3
        }
        return len(words1 & words2)

    def _is_within_lookback(self, iso_date: str) -> bool:
        """Check if date is within DAYS_LOOKBACK."""
        try:
            dt   = datetime.fromisoformat(iso_date)
            diff = (datetime.now() - dt).days
            return diff <= DAYS_LOOKBACK
        except Exception:
            return True

    def _format_date(self, iso: str) -> str:
        """Format ISO date as human-readable."""
        try:
            dt   = datetime.fromisoformat(iso)
            diff = (datetime.now() - dt).days
            if diff == 0:
                return "earlier today"
            elif diff == 1:
                return "yesterday"
            elif diff <= 7:
                return f"{diff} days ago"
            else:
                return dt.strftime("%b %d")
        except Exception:
            return "recently"

    def _find_session_by_content(
        self, content: str, sessions: list
    ) -> Optional[dict]:
        """Find session whose summary best matches content."""
        best      = None
        best_score= 0
        for s in sessions:
            score = self._keyword_overlap(
                content,
                s.get("summary", "") + " " + s.get("first_query", "")
            )
            if score > best_score:
                best_score = score
                best       = s
        return best if best_score > 0 else None

    def _load_open_questions(self, topic: str) -> list[str]:
        """Load unverified pending outcomes for context topic."""
        pending_file = self.memory_dir / "pending_outcomes.json"
        if not pending_file.exists():
            return []
        try:
            data    = json.loads(pending_file.read_text())
            pending = data if isinstance(data, list) else []
            return [
                p.get("conclusion", "")[:80]
                for p in pending
                if p.get("status") == "pending"
                and (
                    topic == "general" or
                    topic in p.get("topic_tag", "")
                )
            ][:3]
        except Exception:
            return []

    def _load_session_index(self) -> dict:
        """Load session index with simple caching."""
        index_file = self.memory_dir / "session_index.json"
        if not index_file.exists():
            return {}
        try:
            mtime = index_file.stat().st_mtime
            if mtime != self._index_mtime or self._index_cache is None:
                self._index_cache = json.loads(
                    index_file.read_text(encoding="utf-8")
                )
                self._index_mtime = mtime
            return self._index_cache
        except Exception:
            return {}

    def _load_bridge_log(self) -> list:
        """Load memory-outcome bridge log."""
        bridge_file = self.memory_dir / "bridge_log.json"
        if not bridge_file.exists():
            return []
        try:
            return json.loads(bridge_file.read_text(encoding="utf-8"))
        except Exception:
            return []
