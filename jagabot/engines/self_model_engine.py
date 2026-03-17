# jagabot/engines/self_model_engine.py
"""
SelfModelEngine — Explicit structured self-model for AutoJaga.

Fixes the fabrication problem at the ROOT level.

Instead of rules ("don't claim what you don't know"),
the agent maintains an explicit, live, evidence-based model
of its own capabilities, limitations, and knowledge gaps.

Three core questions it answers:
  1. WHAT DO I KNOW?      → verified facts with confidence scores
  2. WHAT CAN I DO?       → capability map with reliability scores
  3. WHAT DON'T I KNOW?   → knowledge gaps flagged for curiosity engine

The difference from existing systems:
  BrierScorer:     tracks prediction accuracy (retrospective)
  KernelHealth:    tracks data availability (static)
  SelfModelEngine: tracks self-knowledge state (live, dynamic)

When agent says "I'm 90% confident" — SelfModelEngine checks:
  "My self-model says I'm only 40% reliable in this domain.
   Flagging overconfidence before response leaves."

Wire into loop.py __init__:
    from jagabot.engines.self_model_engine import SelfModelEngine
    self.self_model = SelfModelEngine(workspace, brier_scorer)

Wire into loop.py _process_message START:
    # Get self-model context for this query
    self_context = self.self_model.get_context(
        query=msg.content,
        topic=detected_topic,
    )
    # Inject into system prompt Layer 1

Wire into loop.py _process_message END:
    # Update self-model from this interaction
    self.self_model.update_from_turn(
        query=msg.content,
        response=final_content,
        tools_used=tools_used,
        quality=quality_score,
        topic=detected_topic,
    )

Wire into session_writer.py after save():
    self.self_model.record_session_outcome(
        session_key=session_key,
        quality=quality,
        topic=topic,
    )
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger


# ── Config ───────────────────────────────────────────────────────────
MIN_SESSIONS_FOR_RELIABLE  = 5    # need 5+ sessions to mark as reliable
HIGH_RELIABILITY_THRESHOLD = 0.75 # above this = reliable
LOW_RELIABILITY_THRESHOLD  = 0.40 # below this = unreliable
UNKNOWN_RELIABILITY        = None # no data yet


# ── Domain taxonomy ──────────────────────────────────────────────────
KNOWN_DOMAINS = {
    "financial":   "Financial analysis, risk, portfolio",
    "research":    "Research synthesis, literature review",
    "causal":      "Causal inference, IPW, regression",
    "algorithm":   "Algorithm design, benchmarking",
    "healthcare":  "Clinical, medical, health systems",
    "engineering": "Software, agent architecture, tools",
    "ideas":       "Creative ideation, brainstorming",
    "general":     "Cross-domain, general knowledge",
}

# Capability taxonomy
KNOWN_CAPABILITIES = {
    "web_research":     "Finding and synthesising information",
    "computation":      "Numerical calculation and verification",
    "causal_analysis":  "Causal inference and confounding",
    "code_generation":  "Writing and debugging code",
    "idea_generation":  "Novel idea creation (tri/quad agent)",
    "verification":     "Fact-checking and cross-validation",
    "memory_retrieval": "Recalling past research accurately",
    "prediction":       "Forecasting outcomes with confidence",
    "financial_risk":   "Portfolio and risk analysis",
    "report_writing":   "Structured research output",
}


# ── Data classes ─────────────────────────────────────────────────────

@dataclass
class DomainKnowledge:
    """What the agent knows about a specific domain."""
    domain:           str
    session_count:    int   = 0
    quality_avg:      float = 0.0
    reliability:      float = 0.0      # 0-1
    verified_facts:   int   = 0
    wrong_claims:     int   = 0
    pending_outcomes: int   = 0
    last_active:      str   = ""
    confidence_level: str   = "unknown"  # reliable/moderate/unreliable/unknown

    @property
    def is_reliable(self) -> bool:
        return self.reliability >= HIGH_RELIABILITY_THRESHOLD

    @property
    def is_unreliable(self) -> bool:
        return (
            self.session_count >= MIN_SESSIONS_FOR_RELIABLE and
            self.reliability < LOW_RELIABILITY_THRESHOLD
        )

    @property
    def has_data(self) -> bool:
        return self.session_count >= MIN_SESSIONS_FOR_RELIABLE


@dataclass
class CapabilityModel:
    """What the agent can and cannot do reliably."""
    capability:      str
    use_count:       int   = 0
    success_rate:    float = 0.0
    last_used:       str   = ""
    reliability:     str   = "unknown"  # high/medium/low/unknown
    notes:           str   = ""


@dataclass
class KnowledgeGap:
    """Something the agent doesn't know or is uncertain about."""
    topic:       str
    gap_type:    str   # "no_data" | "conflicting" | "outdated" | "low_confidence"
    description: str
    priority:    float = 0.5  # 0-1, higher = more important to fill
    discovered:  str   = ""


@dataclass
class SelfModelContext:
    """Context injected into system prompt from self-model."""
    domain_reliability:   str   = ""
    capability_warnings:  str   = ""
    knowledge_gaps:       str   = ""
    confidence_guide:     str   = ""
    has_content:          bool  = False

    def format_for_prompt(self) -> str:
        """Format as system prompt injection."""
        parts = []

        if self.domain_reliability:
            parts.append(self.domain_reliability)
        if self.capability_warnings:
            parts.append(self.capability_warnings)
        if self.knowledge_gaps:
            parts.append(self.knowledge_gaps)
        if self.confidence_guide:
            parts.append(self.confidence_guide)

        if not parts:
            return ""

        return (
            "## Self-Model (verified capability state)\n\n" +
            "\n\n".join(parts)
        )


# ── Main engine ───────────────────────────────────────────────────────

class SelfModelEngine:
    """
    Maintains an explicit, live model of AutoJaga's own
    capabilities, knowledge, and limitations.

    Updated automatically from:
    - Session quality scores
    - BrierScorer calibration data
    - OutcomeTracker verdicts
    - KernelHealthMonitor status

    Used by:
    - ContextBuilder (inject into Layer 1)
    - StrategicInterceptor (check before overconfident response)
    - CuriosityEngine (identify gaps to fill)
    - /status command (honest capability report)
    """

    def __init__(
        self,
        workspace:    Path,
        brier_scorer: object = None,
        session_index: object = None,
        outcome_tracker: object = None,
    ) -> None:
        self.workspace       = Path(workspace)
        self.memory_dir      = self.workspace / "memory"
        self.brier           = brier_scorer
        self.session_index   = session_index
        self.outcome_tracker = outcome_tracker
        self.db_path         = self.memory_dir / "self_model.db"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._domain_cache:     dict[str, DomainKnowledge]  = {}
        self._capability_cache: dict[str, CapabilityModel]  = {}
        self._gap_cache:        list[KnowledgeGap]          = []
        self._cache_valid       = False

    # ── Public API ───────────────────────────────────────────────────

    def get_context(
        self,
        query:  str,
        topic:  str = "general",
    ) -> SelfModelContext:
        """
        Get self-model context for system prompt injection.
        Called at start of every _process_message.
        """
        self._refresh_if_needed()

        ctx = SelfModelContext()

        # 1. Domain reliability
        domain_info = self._get_domain_reliability_text(topic)
        if domain_info:
            ctx.domain_reliability = domain_info
            ctx.has_content = True

        # 2. Capability warnings for this query
        cap_warnings = self._get_capability_warnings(query, topic)
        if cap_warnings:
            ctx.capability_warnings = cap_warnings
            ctx.has_content = True

        # 3. Relevant knowledge gaps
        gaps = self._get_relevant_gaps(topic, query)
        if gaps:
            ctx.knowledge_gaps = gaps
            ctx.has_content = True

        # 4. Confidence guide based on domain history
        conf_guide = self._get_confidence_guide(topic)
        if conf_guide:
            ctx.confidence_guide = conf_guide
            ctx.has_content = True

        return ctx

    def update_from_turn(
        self,
        query:      str,
        response:   str,
        tools_used: list      = None,
        quality:    float     = 0.0,
        topic:      str       = "general",
        session_key:str       = "",
    ) -> None:
        """
        Update self-model from a completed conversation turn.
        Called at end of every _process_message.
        """
        tools_used = tools_used or []
        now        = datetime.now().isoformat()

        # Update domain knowledge
        self._update_domain(topic, quality, tools_used, now)

        # Update capability models
        for tool in tools_used:
            cap = self._tool_to_capability(tool)
            if cap:
                self._update_capability(cap, quality > 0.6, now)

        # Detect new knowledge gaps from response
        gaps = self._detect_gaps_from_response(response, topic)
        for gap in gaps:
            self._record_gap(gap)

        # Invalidate cache
        self._cache_valid = False

        logger.debug(
            f"SelfModelEngine: updated — topic={topic} "
            f"quality={quality:.2f} tools={len(tools_used)}"
        )

    def record_verified_outcome(
        self,
        topic:    str,
        result:   str,   # "correct" | "wrong" | "inconclusive"
        claim:    str    = "",
    ) -> None:
        """
        Called by OutcomeTracker when a verdict is given.
        Updates domain reliability based on verified outcomes.
        """
        conn = sqlite3.connect(self.db_path)

        if result == "correct":
            conn.execute("""
                UPDATE domain_knowledge
                SET verified_facts = verified_facts + 1,
                    updated_at = ?
                WHERE domain = ?
            """, (datetime.now().isoformat(), topic))
        elif result == "wrong":
            conn.execute("""
                UPDATE domain_knowledge
                SET wrong_claims = wrong_claims + 1,
                    updated_at = ?
                WHERE domain = ?
            """, (datetime.now().isoformat(), topic))

        conn.commit()
        conn.close()
        self._cache_valid = False

    def get_domain_model(self, domain: str) -> object:
        """
        Get domain model by name.
        Returns DomainKnowledge object or None if not found.
        """
        self._refresh_if_needed()
        
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("""
            SELECT domain, session_count, quality_avg, reliability,
                   verified_facts, wrong_claims, pending_outcomes,
                   last_active, confidence_level
            FROM domain_knowledge
            WHERE domain = ?
        """, (domain,)).fetchone()
        conn.close()
        
        if not row:
            return None
        
        from dataclasses import dataclass
        
        @dataclass
        class DomainKnowledge:
            domain: str
            session_count: int
            quality_avg: float
            reliability: float
            verified_facts: int
            wrong_claims: int
            pending_outcomes: int
            last_active: str
            confidence_level: str
        
        return DomainKnowledge(
            domain=row[0],
            session_count=row[1],
            quality_avg=row[2] or 0.0,
            reliability=row[3] or 0.0,
            verified_facts=row[4] or 0,
            wrong_claims=row[5] or 0,
            pending_outcomes=row[6] or 0,
            last_active=row[7] or "",
            confidence_level=row[8] or "unknown",
        )

    def get_capability_model(self, capability: str) -> object:
        """
        Get capability model by name.
        Returns CapabilityModel object or None if not found.
        """
        self._refresh_if_needed()
        
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("""
            SELECT capability, use_count, success_rate, last_used,
                   reliability, notes
            FROM capability_models
            WHERE capability = ?
        """, (capability,)).fetchone()
        conn.close()
        
        if not row:
            return None
        
        from dataclasses import dataclass
        
        @dataclass
        class CapabilityModel:
            capability: str
            use_count: int
            success_rate: float
            last_used: str
            reliability: str
            notes: str
        
        return CapabilityModel(
            capability=row[0],
            use_count=row[1] or 0,
            success_rate=row[2] or 0.0,
            last_used=row[3] or "",
            reliability=row[4] or "unknown",
            notes=row[5] or "",
        )

    def get_full_status(self) -> str:
        """
        Return complete self-model status report.
        Used by /status command.
        Honest — only reports what's actually known.
        """
        self._refresh_if_needed()

        lines = ["## 🧠 Self-Model Status", ""]

        # Domain knowledge
        lines.append("### Domain Reliability")
        lines.append("")

        domains = self._load_all_domains()
        if not domains:
            lines.append(
                "*No domain data yet. "
                "Reliability builds with usage.*"
            )
        else:
            for d in sorted(
                domains, key=lambda x: x.session_count, reverse=True
            ):
                icon  = self._reliability_icon(d)
                level = d.confidence_level
                data  = (
                    f"{d.session_count} sessions, "
                    f"quality avg={d.quality_avg:.2f}"
                )
                if d.verified_facts > 0 or d.wrong_claims > 0:
                    data += (
                        f", {d.verified_facts}✅ "
                        f"{d.wrong_claims}❌"
                    )
                lines.append(
                    f"{icon} **{d.domain}** ({level}): {data}"
                )

        lines.append("")

        # Capability models
        lines.append("### Capability Reliability")
        lines.append("")

        caps = self._load_all_capabilities()
        if not caps:
            lines.append(
                "*No capability data yet.*"
            )
        else:
            for c in sorted(
                caps, key=lambda x: x.use_count, reverse=True
            )[:8]:
                icon = (
                    "✅" if c.reliability == "high"
                    else "⚠️" if c.reliability == "medium"
                    else "❌" if c.reliability == "low"
                    else "❓"
                )
                lines.append(
                    f"{icon} **{c.capability}**: "
                    f"{c.reliability} "
                    f"(used {c.use_count}x, "
                    f"success={c.success_rate:.0%})"
                )

        lines.append("")

        # Knowledge gaps
        gaps = self._load_all_gaps()
        if gaps:
            lines.append("### Knowledge Gaps")
            lines.append("")
            for g in sorted(
                gaps, key=lambda x: x.priority, reverse=True
            )[:5]:
                lines.append(
                    f"🔲 **{g.topic}** ({g.gap_type}): "
                    f"{g.description[:80]}"
                )
            lines.append("")

        # Honest summary
        reliable_domains = [
            d for d in domains if d.is_reliable
        ]
        unreliable_domains = [
            d for d in domains if d.is_unreliable
        ]

        lines.append("### Summary")
        lines.append("")
        if reliable_domains:
            lines.append(
                f"✅ Reliable in: "
                f"{', '.join(d.domain for d in reliable_domains)}"
            )
        if unreliable_domains:
            lines.append(
                f"⚠️ Unreliable in: "
                f"{', '.join(d.domain for d in unreliable_domains)} "
                f"— use with caution"
            )
        unknown = [
            d for d in KNOWN_DOMAINS
            if d not in {dom.domain for dom in domains}
        ]
        if unknown:
            lines.append(
                f"❓ No data on: {', '.join(unknown[:4])}"
            )

        return "\n".join(lines)

    def get_domain_reliability(self, domain: str) -> Optional[float]:
        """
        Return reliability score for a domain (0-1 or None).
        Used by StrategicInterceptor and BrierScorer.
        None = insufficient data.
        """
        domain_data = self._get_domain(domain)
        if not domain_data or not domain_data.has_data:
            return None
        return domain_data.reliability

    def suggest_confidence_level(
        self,
        domain:    str,
        raw_conf:  float,
    ) -> tuple[float, str]:
        """
        Suggest calibrated confidence based on self-model.
        Returns (adjusted_confidence, explanation).

        Used by StrategicInterceptor before adjusting response.
        """
        domain_data = self._get_domain(domain)

        if not domain_data or not domain_data.has_data:
            return raw_conf, "no self-model data for this domain"

        reliability = domain_data.reliability

        if reliability >= HIGH_RELIABILITY_THRESHOLD:
            # Well-established domain — minor adjustment only
            adjusted = raw_conf * min(1.0, reliability + 0.1)
            return adjusted, f"domain reliability={reliability:.2f} (high)"

        if reliability < LOW_RELIABILITY_THRESHOLD:
            # Poor track record — significant downward adjustment
            adjusted  = raw_conf * reliability
            return adjusted, (
                f"self-model flags {domain} as unreliable "
                f"(reliability={reliability:.2f}) — "
                f"confidence adjusted down"
            )

        # Moderate — proportional adjustment
        adjusted = raw_conf * reliability
        return adjusted, f"domain reliability={reliability:.2f} (moderate)"

    # ── Context generation ────────────────────────────────────────────

    def _get_domain_reliability_text(self, topic: str) -> str:
        """Generate domain reliability section for prompt."""
        domain_data = self._get_domain(topic)

        if not domain_data or not domain_data.has_data:
            return (
                f"**Self-model:** No reliability data for "
                f"'{topic}' domain yet. "
                f"Express uncertainty explicitly — "
                f"don't infer reliability from training data."
            )

        if domain_data.is_reliable:
            return (
                f"**Self-model:** '{topic}' domain — "
                f"reliable (score={domain_data.reliability:.2f}, "
                f"n={domain_data.session_count} sessions). "
                f"You have a good track record here."
            )

        if domain_data.is_unreliable:
            return (
                f"**Self-model WARNING:** '{topic}' domain — "
                f"unreliable (score={domain_data.reliability:.2f}, "
                f"n={domain_data.session_count} sessions, "
                f"{domain_data.wrong_claims} wrong claims recorded). "
                f"Express HIGH uncertainty. "
                f"Prefer Buffet perspective. "
                f"Flag all claims as needing verification."
            )

        return (
            f"**Self-model:** '{topic}' domain — "
            f"moderate reliability (score={domain_data.reliability:.2f}, "
            f"n={domain_data.session_count} sessions). "
            f"Express appropriate uncertainty."
        )

    def _get_capability_warnings(
        self, query: str, topic: str
    ) -> str:
        """Generate capability warnings for this query type."""
        query_lower = query.lower()
        warnings    = []

        # Check capabilities implied by query
        if any(w in query_lower for w in
               ["predict", "forecast", "will", "expect"]):
            cap = self._load_capability("prediction")
            if cap and cap.reliability == "low":
                warnings.append(
                    "⚠️ Prediction capability: "
                    f"historically low reliability "
                    f"(success={cap.success_rate:.0%}). "
                    "Express ranges not point estimates."
                )

        if any(w in query_lower for w in
               ["remember", "recall", "last time", "previously"]):
            cap = self._load_capability("memory_retrieval")
            if cap and cap.reliability in ("low", "medium"):
                warnings.append(
                    "⚠️ Memory retrieval: "
                    "verify with read_file before claiming. "
                    "Do not rely on training data for session facts."
                )

        if any(w in query_lower for w in
               ["calculate", "compute", "exact", "precise"]):
            cap = self._load_capability("computation")
            if cap and cap.reliability != "high":
                warnings.append(
                    "⚠️ Computation: "
                    "always use exec to verify — "
                    "never calculate in response text."
                )

        return "\n".join(warnings) if warnings else ""

    def _get_relevant_gaps(
        self, topic: str, query: str
    ) -> str:
        """Surface relevant knowledge gaps."""
        gaps      = self._load_all_gaps()
        relevant  = [
            g for g in gaps
            if g.topic == topic
            or topic in g.description.lower()
            or any(
                w in g.description.lower()
                for w in query.lower().split()[:5]
                if len(w) > 4
            )
        ][:2]

        if not relevant:
            return ""

        lines = ["**Known gaps in this area:**"]
        for g in relevant:
            lines.append(f"- {g.description[:100]}")
        return "\n".join(lines)

    def _get_confidence_guide(self, topic: str) -> str:
        """Guide confidence expression based on domain history."""
        domain_data = self._get_domain(topic)

        if not domain_data or not domain_data.has_data:
            return ""

        if domain_data.wrong_claims > 2:
            return (
                f"**Confidence guide:** In {topic}, you have "
                f"{domain_data.wrong_claims} recorded wrong claims. "
                "Use hedged language: "
                "'my analysis suggests', 'preliminary finding', "
                "'needs verification' — not 'confirmed' or 'certain'."
            )

        if domain_data.verified_facts > 5 and domain_data.is_reliable:
            return (
                f"**Confidence guide:** In {topic}, you have "
                f"{domain_data.verified_facts} verified facts. "
                "You can express moderate confidence in well-established "
                "findings, but still verify novel claims."
            )

        return ""

    # ── Gap detection ─────────────────────────────────────────────────

    def _detect_gaps_from_response(
        self,
        response: str,
        topic:    str,
    ) -> list[KnowledgeGap]:
        """Detect knowledge gaps from agent response patterns."""
        gaps = []
        resp_lower = response.lower()

        # Pattern: agent expresses uncertainty
        uncertainty_patterns = [
            (r"i(?:'m| am) not (?:sure|certain) (?:about|if|whether)",
             "uncertainty expressed"),
            (r"i (?:don't|do not) (?:have|know)",
             "explicit knowledge gap"),
            (r"(?:no data|insufficient data|not enough data)",
             "data gap"),
            (r"(?:conflicting|contradictory|inconsistent) (?:data|evidence|findings)",
             "conflicting evidence"),
            (r"(?:outdated|stale|old) (?:data|information|knowledge)",
             "outdated knowledge"),
        ]

        for pattern, gap_type in uncertainty_patterns:
            matches = re.findall(
                pattern, resp_lower, re.IGNORECASE
            )
            if matches:
                # Extract context around the match
                match = re.search(pattern, resp_lower, re.IGNORECASE)
                if match:
                    start = max(0, match.start() - 30)
                    end   = min(len(resp_lower), match.end() + 60)
                    context = resp_lower[start:end].strip()

                    gaps.append(KnowledgeGap(
                        topic       = topic,
                        gap_type    = gap_type,
                        description = context[:120],
                        priority    = 0.6,
                        discovered  = datetime.now().isoformat(),
                    ))

        return gaps[:3]  # cap per turn

    # ── Database ──────────────────────────────────────────────────────

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS domain_knowledge (
                domain          TEXT PRIMARY KEY,
                session_count   INTEGER DEFAULT 0,
                quality_sum     REAL    DEFAULT 0.0,
                quality_avg     REAL    DEFAULT 0.0,
                reliability     REAL    DEFAULT 0.0,
                verified_facts  INTEGER DEFAULT 0,
                wrong_claims    INTEGER DEFAULT 0,
                pending_outcomes INTEGER DEFAULT 0,
                confidence_level TEXT   DEFAULT 'unknown',
                last_active     TEXT    DEFAULT '',
                updated_at      TEXT    DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS capability_models (
                capability      TEXT PRIMARY KEY,
                use_count       INTEGER DEFAULT 0,
                success_count   INTEGER DEFAULT 0,
                success_rate    REAL    DEFAULT 0.0,
                reliability     TEXT    DEFAULT 'unknown',
                last_used       TEXT    DEFAULT '',
                notes           TEXT    DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS knowledge_gaps (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                topic       TEXT    NOT NULL,
                gap_type    TEXT    NOT NULL,
                description TEXT    NOT NULL,
                priority    REAL    DEFAULT 0.5,
                resolved    INTEGER DEFAULT 0,
                discovered  TEXT    NOT NULL
            );
        """)
        conn.commit()
        conn.close()

    def _update_domain(
        self,
        domain:     str,
        quality:    float,
        tools_used: list,
        timestamp:  str,
    ) -> None:
        conn = sqlite3.connect(self.db_path)

        # Get current state
        row = conn.execute(
            "SELECT session_count, quality_sum, verified_facts, "
            "wrong_claims FROM domain_knowledge WHERE domain=?",
            (domain,)
        ).fetchone()

        if row:
            count     = row[0] + 1
            q_sum     = row[1] + quality
            verified  = row[2]
            wrong     = row[3]
        else:
            count     = 1
            q_sum     = quality
            verified  = 0
            wrong     = 0

        q_avg       = q_sum / count
        reliability = self._calculate_reliability(
            count, q_avg, verified, wrong
        )
        conf_level  = self._reliability_to_level(reliability, count)

        conn.execute("""
            INSERT INTO domain_knowledge
            (domain, session_count, quality_sum, quality_avg,
             reliability, confidence_level, last_active, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(domain) DO UPDATE SET
                session_count   = excluded.session_count,
                quality_sum     = excluded.quality_sum,
                quality_avg     = excluded.quality_avg,
                reliability     = excluded.reliability,
                confidence_level= excluded.confidence_level,
                last_active     = excluded.last_active,
                updated_at      = excluded.updated_at
        """, (
            domain, count, q_sum, q_avg,
            reliability, conf_level, timestamp, timestamp
        ))
        conn.commit()
        conn.close()

    def _update_capability(
        self,
        capability: str,
        success:    bool,
        timestamp:  str,
    ) -> None:
        conn = sqlite3.connect(self.db_path)

        row = conn.execute(
            "SELECT use_count, success_count FROM capability_models "
            "WHERE capability=?",
            (capability,)
        ).fetchone()

        if row:
            count   = row[0] + 1
            successes = row[1] + (1 if success else 0)
        else:
            count     = 1
            successes = 1 if success else 0

        rate        = successes / count
        reliability = (
            "high"    if rate >= 0.75 and count >= 3
            else "medium" if rate >= 0.50 and count >= 3
            else "low"    if count >= 5
            else "unknown"
        )

        conn.execute("""
            INSERT INTO capability_models
            (capability, use_count, success_count, success_rate,
             reliability, last_used)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(capability) DO UPDATE SET
                use_count     = excluded.use_count,
                success_count = excluded.success_count,
                success_rate  = excluded.success_rate,
                reliability   = excluded.reliability,
                last_used     = excluded.last_used
        """, (capability, count, successes, rate, reliability, timestamp))
        conn.commit()
        conn.close()

    def _record_gap(self, gap: KnowledgeGap) -> None:
        """Record a knowledge gap if not already known."""
        conn = sqlite3.connect(self.db_path)
        # Check for near-duplicate
        existing = conn.execute("""
            SELECT id FROM knowledge_gaps
            WHERE topic = ? AND resolved = 0
            AND description LIKE ?
        """, (gap.topic, gap.description[:40] + "%")).fetchone()

        if not existing:
            conn.execute("""
                INSERT INTO knowledge_gaps
                (topic, gap_type, description, priority, discovered)
                VALUES (?, ?, ?, ?, ?)
            """, (
                gap.topic, gap.gap_type,
                gap.description, gap.priority, gap.discovered
            ))
            conn.commit()
        conn.close()

    def _get_domain(self, domain: str) -> Optional[DomainKnowledge]:
        conn = sqlite3.connect(self.db_path)
        row  = conn.execute(
            "SELECT * FROM domain_knowledge WHERE domain=?",
            (domain,)
        ).fetchone()
        conn.close()

        if not row:
            return None

        return DomainKnowledge(
            domain           = row[0],
            session_count    = row[1],
            quality_avg      = row[3],
            reliability      = row[4],
            verified_facts   = row[5],
            wrong_claims     = row[6],
            pending_outcomes = row[7],
            confidence_level = row[8],
            last_active      = row[9],
        )

    def _load_all_domains(self) -> list[DomainKnowledge]:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT * FROM domain_knowledge ORDER BY session_count DESC"
        ).fetchall()
        conn.close()
        return [
            DomainKnowledge(
                domain=r[0], session_count=r[1], quality_avg=r[3],
                reliability=r[4], verified_facts=r[5], wrong_claims=r[6],
                pending_outcomes=r[7], confidence_level=r[8],
                last_active=r[9],
            )
            for r in rows
        ]

    def _load_capability(self, capability: str) -> Optional[CapabilityModel]:
        conn = sqlite3.connect(self.db_path)
        row  = conn.execute(
            "SELECT * FROM capability_models WHERE capability=?",
            (capability,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        return CapabilityModel(
            capability   = row[0],
            use_count    = row[1],
            success_rate = row[3],
            reliability  = row[4],
            last_used    = row[5],
        )

    def _load_all_capabilities(self) -> list[CapabilityModel]:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT * FROM capability_models ORDER BY use_count DESC"
        ).fetchall()
        conn.close()
        return [
            CapabilityModel(
                capability=r[0], use_count=r[1],
                success_rate=r[3], reliability=r[4], last_used=r[5],
            )
            for r in rows
        ]

    def _load_all_gaps(self) -> list[KnowledgeGap]:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT topic, gap_type, description, priority, discovered
            FROM knowledge_gaps
            WHERE resolved = 0
            ORDER BY priority DESC
            LIMIT 20
        """).fetchall()
        conn.close()
        return [
            KnowledgeGap(
                topic=r[0], gap_type=r[1],
                description=r[2], priority=r[3], discovered=r[4],
            )
            for r in rows
        ]

    # ── Helpers ───────────────────────────────────────────────────────

    def _calculate_reliability(
        self,
        session_count: int,
        quality_avg:   float,
        verified_facts:int,
        wrong_claims:  int,
    ) -> float:
        """
        Calculate domain reliability score (0-1).
        Combines quality, verification history, and error rate.
        """
        if session_count < MIN_SESSIONS_FOR_RELIABLE:
            # Not enough data — return partial score
            return quality_avg * 0.5

        # Base: quality average
        base = quality_avg

        # Bonus: verified facts boost reliability
        fact_bonus = min(0.15, verified_facts * 0.03)

        # Penalty: wrong claims reduce reliability
        error_rate  = wrong_claims / max(1, session_count)
        error_penalty = error_rate * 0.5

        reliability = max(0.0, min(1.0,
            base + fact_bonus - error_penalty
        ))
        return round(reliability, 3)

    def _reliability_to_level(
        self, reliability: float, count: int
    ) -> str:
        if count < MIN_SESSIONS_FOR_RELIABLE:
            return "unknown"
        if reliability >= HIGH_RELIABILITY_THRESHOLD:
            return "reliable"
        if reliability >= LOW_RELIABILITY_THRESHOLD:
            return "moderate"
        return "unreliable"

    def _reliability_icon(self, d: DomainKnowledge) -> str:
        if not d.has_data:
            return "❓"
        if d.is_reliable:
            return "✅"
        if d.is_unreliable:
            return "⚠️"
        return "🔵"

    def _tool_to_capability(self, tool_name: str) -> Optional[str]:
        """Map tool name to capability category."""
        mapping = {
            "web_search":      "web_research",
            "web_fetch":       "web_research",
            "researcher":      "web_research",
            "exec":            "computation",
            "statistical_engine": "computation",
            "monte_carlo":     "computation",
            "tri_agent":       "idea_generation",
            "quad_agent":      "idea_generation",
            "memory_fleet":    "memory_retrieval",
            "read_file":       "memory_retrieval",
            "k1_bayesian":     "prediction",
            "k3_perspective":  "prediction",
            "write_file":      "report_writing",
            "financial_cv":    "financial_risk",
            "portfolio_analyzer": "financial_risk",
        }
        return mapping.get(tool_name)

    def _refresh_if_needed(self) -> None:
        """Sync with BrierScorer if available."""
        if not self._cache_valid and self.brier:
            try:
                reports = self.brier.get_all_reports()
                for r in reports:
                    if r.sample_count >= MIN_SESSIONS_FOR_RELIABLE:
                        self._sync_brier_to_domain(r)
            except Exception as e:
                logger.debug(f"SelfModelEngine: brier sync failed: {e}")
        self._cache_valid = True

    def _sync_brier_to_domain(self, report) -> None:
        """Sync BrierScorer data into domain knowledge."""
        conn = sqlite3.connect(self.db_path)
        # Update reliability from Brier trust score
        conn.execute("""
            UPDATE domain_knowledge
            SET reliability = ?,
                confidence_level = ?,
                updated_at = ?
            WHERE domain = ?
        """, (
            report.trust_score,
            self._reliability_to_level(
                report.trust_score, report.sample_count
            ),
            datetime.now().isoformat(),
            report.domain,
        ))
        conn.commit()
        conn.close()
