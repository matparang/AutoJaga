"""
BeliefEngine — Downstream of BrierScorer

Maintains a calibrated belief state across all domains and perspectives.
Uses BrierScorer trust scores to weight beliefs and detect when the
agent should be more or less confident.

Architecture:
  BrierScorer → trust scores per domain
  BeliefEngine → weighted belief state per domain
  CognitiveStack → reasoning depth adjustment
  Agent → calibrated responses

Key insight:
  Raw confidence (what the agent thinks) ≠ Calibrated confidence
  BeliefEngine bridges the gap using historical accuracy data.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


# ── Belief state ──────────────────────────────────────────────────

@dataclass
class DomainBelief:
    """Calibrated belief state for one domain."""
    domain:              str
    perspective:         str
    raw_confidence:      float    # what agent thinks (0-1)
    trust_score:         float    # BrierScorer historical accuracy (0-1)
    calibrated_confidence: float  # adjusted = raw × trust
    belief_state:        str      # "strong" | "moderate" | "weak" | "uncertain"
    recommendation:      str      # action recommendation
    updated_at:          str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class BeliefUpdate:
    """A single belief update event."""
    domain:       str
    perspective:  str
    prior:        float   # confidence before update
    posterior:    float   # confidence after update
    evidence:     str     # what triggered the update
    direction:    str     # "increased" | "decreased" | "stable"
    timestamp:    str = field(default_factory=lambda: datetime.now().isoformat())


# ── Main engine ───────────────────────────────────────────────────

class BeliefEngine:
    """
    Maintains calibrated belief states across domains.

    Reads from BrierScorer to weight raw agent confidence.
    Provides recommendations to CognitiveStack on reasoning depth.

    Usage:
        engine = BeliefEngine(workspace, brier_scorer)
        belief = engine.update("financial", "bear", raw_confidence=0.8)
        # belief.calibrated_confidence = 0.8 × trust_score
        # belief.recommendation = "proceed with caution" if trust < 0.5
    """

    # Belief state thresholds
    STRONG_THRESHOLD   = 0.75
    MODERATE_THRESHOLD = 0.55
    WEAK_THRESHOLD     = 0.35

    def __init__(self, workspace: Path, brier_scorer=None):
        self.workspace   = Path(workspace)
        self.brier       = brier_scorer
        self.db_path     = self.workspace / "memory" / "beliefs.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._belief_cache: dict[str, DomainBelief] = {}
        self._update_history: list[BeliefUpdate] = []

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS beliefs (
                domain               TEXT,
                perspective          TEXT,
                raw_confidence       REAL,
                trust_score          REAL,
                calibrated_confidence REAL,
                belief_state         TEXT,
                recommendation       TEXT,
                updated_at           TEXT,
                PRIMARY KEY (domain, perspective)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS belief_updates (
                domain       TEXT,
                perspective  TEXT,
                prior        REAL,
                posterior    REAL,
                evidence     TEXT,
                direction    TEXT,
                timestamp    TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _get_trust(self, perspective: str, domain: str) -> float:
        """Get trust score from BrierScorer."""
        if not self.brier:
            return 0.7  # Default moderate trust if no BrierScorer

        try:
            trust = self.brier.trust_score(perspective, domain)
            if trust is None:
                return 0.7  # Insufficient data — use moderate default
            return max(0.1, min(1.0, trust))
        except Exception:
            return 0.7

    def _classify_belief(self, calibrated: float) -> tuple[str, str]:
        """Classify belief strength and generate recommendation."""
        if calibrated >= self.STRONG_THRESHOLD:
            return "strong", "High confidence — proceed with standard reasoning depth"
        elif calibrated >= self.MODERATE_THRESHOLD:
            return "moderate", "Moderate confidence — verify key assumptions before concluding"
        elif calibrated >= self.WEAK_THRESHOLD:
            return "weak", "Low confidence — use deeper reasoning, seek additional evidence"
        else:
            return "uncertain", "Very low confidence — escalate to CRITICAL reasoning mode"

    def update(
        self,
        domain:         str,
        perspective:    str = "general",
        raw_confidence: float = 0.7,
        evidence:       str = "",
    ) -> DomainBelief:
        """
        Update belief state for a domain/perspective pair.
        Returns calibrated DomainBelief.
        """
        trust = self._get_trust(perspective, domain)
        calibrated = raw_confidence * trust
        state, recommendation = self._classify_belief(calibrated)

        belief = DomainBelief(
            domain                = domain,
            perspective           = perspective,
            raw_confidence        = raw_confidence,
            trust_score           = trust,
            calibrated_confidence = round(calibrated, 3),
            belief_state          = state,
            recommendation        = recommendation,
        )

        # Track update history
        cache_key = f"{perspective}:{domain}"
        prior = self._belief_cache.get(cache_key)
        if prior:
            direction = (
                "increased" if calibrated > prior.calibrated_confidence
                else "decreased" if calibrated < prior.calibrated_confidence
                else "stable"
            )
            update = BeliefUpdate(
                domain      = domain,
                perspective = perspective,
                prior       = prior.calibrated_confidence,
                posterior   = calibrated,
                evidence    = evidence[:200],
                direction   = direction,
            )
            self._update_history.append(update)
            if len(self._update_history) > 100:
                self._update_history = self._update_history[-100:]

            if direction != "stable":
                logger.info(
                    f"BeliefEngine: {perspective}/{domain} "
                    f"{direction} {prior.calibrated_confidence:.2f} → {calibrated:.2f} "
                    f"(trust={trust:.2f})"
                )

        self._belief_cache[cache_key] = belief
        self._save_belief(belief)

        logger.debug(
            f"BeliefEngine: {domain}/{perspective} "
            f"raw={raw_confidence:.2f} trust={trust:.2f} "
            f"→ calibrated={calibrated:.2f} [{state}]"
        )
        return belief

    def get_belief(self, domain: str, perspective: str = "general") -> DomainBelief | None:
        """Get current belief state for a domain."""
        cache_key = f"{perspective}:{domain}"
        if cache_key in self._belief_cache:
            return self._belief_cache[cache_key]

        # Load from DB
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("""
            SELECT domain, perspective, raw_confidence, trust_score,
                   calibrated_confidence, belief_state, recommendation, updated_at
            FROM beliefs WHERE domain=? AND perspective=?
        """, (domain, perspective)).fetchone()
        conn.close()

        if row:
            belief = DomainBelief(*row)
            self._belief_cache[cache_key] = belief
            return belief
        return None

    def get_cognitive_recommendation(self, domain: str) -> str:
        """
        Get reasoning depth recommendation for CognitiveStack.
        Called before each major task to set appropriate depth.
        """
        belief = self.get_belief(domain)
        if not belief:
            return "NORMAL"  # No data — use normal depth

        if belief.belief_state == "uncertain":
            return "CRITICAL"  # Use Model 2 (reasoner)
        elif belief.belief_state == "weak":
            return "COMPLEX"   # Use M1+M2 collaboration
        else:
            return "NORMAL"    # Use Model 1 (fast)

    def get_all_beliefs(self) -> dict[str, DomainBelief]:
        """Return all current belief states."""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT domain, perspective, raw_confidence, trust_score,
                   calibrated_confidence, belief_state, recommendation, updated_at
            FROM beliefs ORDER BY calibrated_confidence DESC
        """).fetchall()
        conn.close()

        return {
            f"{r[1]}:{r[0]}": DomainBelief(*r)
            for r in rows
        }

    def format_report(self) -> str:
        """Format belief state report."""
        beliefs = self.get_all_beliefs()
        if not beliefs:
            return (
                "## 🧠 Belief Engine\n\n"
                "No belief states recorded yet.\n"
                "Beliefs form as the agent answers questions and receives feedback.\n"
            )

        lines = ["## 🧠 Calibrated Belief States\n"]
        state_emoji = {
            "strong": "🟢", "moderate": "🟡",
            "weak": "🟠", "uncertain": "🔴"
        }

        for key, b in beliefs.items():
            emoji = state_emoji.get(b.belief_state, "⚪")
            lines.append(
                f"{emoji} **{b.perspective}/{b.domain}**: "
                f"raw={b.raw_confidence:.0%} → calibrated={b.calibrated_confidence:.0%} "
                f"(trust={b.trust_score:.0%}) [{b.belief_state}]"
            )
            lines.append(f"   → {b.recommendation}")
            lines.append("")

        if self._update_history:
            recent = self._update_history[-3:]
            lines.append("### Recent Updates")
            for u in reversed(recent):
                lines.append(
                    f"- {u.domain}/{u.perspective}: "
                    f"{u.prior:.2f} → {u.posterior:.2f} ({u.direction})"
                )

        return "\n".join(lines)

    def _save_belief(self, belief: DomainBelief) -> None:
        """Save belief to database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO beliefs
            (domain, perspective, raw_confidence, trust_score,
             calibrated_confidence, belief_state, recommendation, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            belief.domain, belief.perspective,
            belief.raw_confidence, belief.trust_score,
            belief.calibrated_confidence, belief.belief_state,
            belief.recommendation, belief.updated_at,
        ))
        conn.commit()
        conn.close()

    def get_stats(self) -> dict:
        """Return belief statistics."""
        beliefs = self.get_all_beliefs()
        if not beliefs:
            return {"total": 0}

        states = {}
        for b in beliefs.values():
            states[b.belief_state] = states.get(b.belief_state, 0) + 1

        avg_trust = sum(b.trust_score for b in beliefs.values()) / len(beliefs)
        avg_cal   = sum(b.calibrated_confidence for b in beliefs.values()) / len(beliefs)

        return {
            "total":       len(beliefs),
            "states":      states,
            "avg_trust":   round(avg_trust, 2),
            "avg_calibrated": round(avg_cal, 2),
            "updates":     len(self._update_history),
        }
