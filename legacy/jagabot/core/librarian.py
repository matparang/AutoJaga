# jagabot/core/librarian.py
"""
Phase 3 — Librarian: Memory-Negative Constrained RAG

Scans MEMORY.md and bridge_log.json for verified failures.
Injects them as negative constraints into system prompt.
Prevents agent from repeating known wrong conclusions.

This is "Anti-Hallucination Scaffolding" —
building guardrails from the agent's own error history.

Example injection:
    ## VERIFIED FAILURES — Do NOT repeat:
    - DO NOT claim CVaR(99%) predicts margin breach timing
      → Verified: warning coincident with breach (0/100 simulations)
    - DO NOT present SSB hypothesis as confirmed
      → Status: synthetic data only, real-world test pending

Wire into context_builder.py:
    from jagabot.core.librarian import Librarian
    self.librarian = Librarian(workspace)

    # In build() after Layer 1 (core identity):
    negative_constraints = self.librarian.get_constraints(topic)
    if negative_constraints:
        parts.insert(1, negative_constraints)

Wire into loop.py __init__:
    from jagabot.core.librarian import Librarian
    self.librarian = Librarian(workspace)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger


# ── Config ───────────────────────────────────────────────────────────
MAX_CONSTRAINTS_IN_CONTEXT = 5    # cap to avoid bloating context
CONSTRAINT_MAX_AGE_DAYS    = 180  # only use recent failures
WRONG_TAG_PATTERNS = [
    r'\[❌\s*VERIFIED\s*WRONG[^\]]*\]',
    r'\[⚠️\s*INCONCLUSIVE[^\]]*\]',
    r'\[❌[^\]]*\]',
    r'VERIFIED\s*WRONG',
    r'DO\s*NOT\s*REPEAT',
]


@dataclass
class NegativeConstraint:
    """A verified failure that should not be repeated."""
    claim:       str
    reason:      str
    result:      str        # "wrong" | "inconclusive"
    domain:      str
    date:        str
    source:      str        # "bridge_log" | "memory_scan"
    severity:    str = "warning"  # "critical" | "warning"


class Librarian:
    """
    Scans memory for verified failures and generates
    negative constraints for system prompt injection.
    
    Three sources:
    1. bridge_log.json       — OutcomeTracker verdicts
    2. MEMORY.md tags        — [❌ VERIFIED WRONG] markers
    3. BrierScorer database  — low-trust perspective + domain pairs
    """

    def __init__(
        self,
        workspace:    Path,
        brier_scorer: object = None,
    ) -> None:
        self.workspace    = Path(workspace)
        self.memory_dir   = self.workspace / "memory"
        self.bridge_log   = self.memory_dir / "bridge_log.json"
        self.memory_file  = self.memory_dir / "MEMORY.md"
        self.brier_scorer = brier_scorer
        self._cache:      list[NegativeConstraint] = []
        self._cache_time: float = 0.0
        self._cache_ttl:  float = 300.0  # 5 min cache

    # ── Public API ───────────────────────────────────────────────────

    def get_constraints(
        self,
        topic:     str = "general",
        max_items: int = MAX_CONSTRAINTS_IN_CONTEXT,
    ) -> str:
        """
        Return formatted negative constraints for context injection.
        Returns empty string if no constraints found.
        """
        constraints = self._load_all_constraints()

        if not constraints:
            return ""

        # Filter to topic-relevant + cap
        relevant = self._filter_by_topic(constraints, topic)
        top      = relevant[:max_items]

        if not top:
            return ""

        return self._format_constraints(top)

    def get_wrong_claims(self) -> list[str]:
        """Return list of verified wrong claim texts."""
        constraints = self._load_all_constraints()
        return [
            c.claim for c in constraints
            if c.result == "wrong"
        ]

    def get_constraint_count(self) -> dict:
        """Return counts by severity."""
        constraints = self._load_all_constraints()
        return {
            "wrong":        sum(1 for c in constraints if c.result == "wrong"),
            "inconclusive": sum(1 for c in constraints if c.result == "inconclusive"),
            "total":        len(constraints),
        }

    def add_constraint(
        self,
        claim:   str,
        reason:  str,
        result:  str,
        domain:  str = "general",
    ) -> None:
        """
        Manually add a constraint.
        Called by MemoryOutcomeBridge when outcome recorded.
        """
        self._cache = []  # invalidate cache
        logger.info(
            f"Librarian: added constraint [{result}] "
            f"'{claim[:50]}'"
        )

    # ── Load constraints ─────────────────────────────────────────────

    def _load_all_constraints(self) -> list[NegativeConstraint]:
        """Load all constraints from all sources with caching."""
        import time
        now = time.time()

        if self._cache and (now - self._cache_time) < self._cache_ttl:
            return self._cache

        constraints = []

        # Source 1: bridge_log.json
        constraints.extend(self._load_from_bridge_log())

        # Source 2: MEMORY.md tags
        constraints.extend(self._load_from_memory_md())

        # Source 3: Brier scorer (low trust perspectives)
        if self.brier_scorer:
            constraints.extend(self._load_from_brier_scorer())

        # Deduplicate by claim similarity
        constraints = self._deduplicate(constraints)

        # Sort: wrong > inconclusive, recent first
        constraints.sort(
            key=lambda c: (
                0 if c.result == "wrong" else 1,
                c.date,
            )
        )

        self._cache      = constraints
        self._cache_time = now
        return constraints

    def _load_from_bridge_log(self) -> list[NegativeConstraint]:
        """Load verified failures from bridge_log.json."""
        if not self.bridge_log.exists():
            return []

        constraints = []
        cutoff      = (
            datetime.now() - timedelta(days=CONSTRAINT_MAX_AGE_DAYS)
        ).isoformat()

        try:
            entries = json.loads(self.bridge_log.read_text())
            for e in entries:
                if e.get("result") not in ("wrong", "inconclusive"):
                    continue
                if e.get("timestamp", "") < cutoff:
                    continue

                claim = e.get("conclusion", "")
                if len(claim) < 10:
                    continue

                severity = (
                    "critical" if e.get("result") == "wrong"
                    else "warning"
                )
                constraints.append(NegativeConstraint(
                    claim    = claim[:200],
                    reason   = self._build_reason(e),
                    result   = e.get("result", "inconclusive"),
                    domain   = e.get("topic_tag", "general"),
                    date     = e.get("timestamp", "")[:10],
                    source   = "bridge_log",
                    severity = severity,
                ))
        except Exception as ex:
            logger.debug(f"Librarian: bridge_log load failed: {ex}")

        return constraints

    def _load_from_memory_md(self) -> list[NegativeConstraint]:
        """Scan MEMORY.md for verified failure tags."""
        if not self.memory_file.exists():
            return []

        constraints = []
        try:
            content = self.memory_file.read_text(encoding="utf-8")
            lines   = content.split("\n")

            for i, line in enumerate(lines):
                # Check if line has a wrong/inconclusive tag
                is_wrong = bool(re.search(
                    r'\[❌.*VERIFIED.*WRONG[^\]]*\]',
                    line, re.IGNORECASE
                ))
                is_inconclusive = bool(re.search(
                    r'\[⚠️.*INCONCLUSIVE[^\]]*\]',
                    line, re.IGNORECASE
                ))

                if not (is_wrong or is_inconclusive):
                    continue

                # Extract the claim text (remove the tag)
                claim = re.sub(r'\[[^\]]+\]', '', line).strip()
                claim = claim.lstrip('-•* ').strip()

                if len(claim) < 10:
                    continue

                result = "wrong" if is_wrong else "inconclusive"
                constraints.append(NegativeConstraint(
                    claim    = claim[:200],
                    reason   = f"Tagged in MEMORY.md (line {i+1})",
                    result   = result,
                    domain   = "general",
                    date     = datetime.now().strftime("%Y-%m-%d"),
                    source   = "memory_scan",
                    severity = "critical" if is_wrong else "warning",
                ))

        except Exception as ex:
            logger.debug(f"Librarian: MEMORY.md scan failed: {ex}")

        return constraints

    def _load_from_brier_scorer(self) -> list[NegativeConstraint]:
        """Load low-trust perspective+domain pairs from Brier scorer."""
        constraints = []
        try:
            reports = self.brier_scorer.get_all_reports()
            for r in reports:
                if r.is_reliable or r.sample_count < 3:
                    continue
                constraints.append(NegativeConstraint(
                    claim    = (
                        f"{r.perspective} perspective in "
                        f"{r.domain} domain"
                    ),
                    reason   = (
                        f"Low calibration: trust={r.trust_score:.2f}, "
                        f"brier={r.avg_brier:.3f} "
                        f"(n={r.sample_count})"
                    ),
                    result   = "inconclusive",
                    domain   = r.domain,
                    date     = datetime.now().strftime("%Y-%m-%d"),
                    source   = "brier_scorer",
                    severity = "warning",
                ))
        except Exception as ex:
            logger.debug(f"Librarian: Brier scorer load failed: {ex}")
        return constraints

    # ── Formatting ───────────────────────────────────────────────────

    def _format_constraints(
        self,
        constraints: list[NegativeConstraint],
    ) -> str:
        """Format constraints for system prompt injection."""
        lines = [
            "## ⚠️ VERIFIED FAILURES — Do NOT repeat these:",
            "",
        ]

        for c in constraints:
            icon = "❌" if c.result == "wrong" else "⚠️"
            lines.append(
                f"{icon} DO NOT claim: \"{c.claim[:100]}\""
            )
            lines.append(f"   → {c.reason}")
            lines.append("")

        lines.append(
            "These constraints come from verified "
            "outcomes in your memory. "
            "Treat them as hard boundaries."
        )

        return "\n".join(lines)

    # ── Helpers ──────────────────────────────────────────────────────

    def _filter_by_topic(
        self,
        constraints: list[NegativeConstraint],
        topic:       str,
    ) -> list[NegativeConstraint]:
        """Filter to topic-relevant constraints."""
        if topic == "general":
            return constraints

        relevant = [
            c for c in constraints
            if c.domain == topic
            or c.domain == "general"
            or topic in c.claim.lower()
        ]
        return relevant if relevant else constraints

    def _deduplicate(
        self,
        constraints: list[NegativeConstraint],
    ) -> list[NegativeConstraint]:
        """Remove near-duplicate constraints."""
        seen   = []
        unique = []
        for c in constraints:
            words = set(c.claim.lower().split())
            is_dup = any(
                len(words & set(s.lower().split())) / max(len(words), 1) > 0.7
                for s in seen
            )
            if not is_dup:
                seen.append(c.claim)
                unique.append(c)
        return unique

    def _build_reason(self, entry: dict) -> str:
        """Build human-readable reason from bridge_log entry."""
        result = entry.get("result", "")
        claim  = entry.get("conclusion", "")[:60]

        if result == "wrong":
            return (
                f"Verified WRONG on {entry.get('timestamp', '')[:10]}. "
                "Do not repeat."
            )
        elif result == "inconclusive":
            return (
                f"Inconclusive — real-world test pending. "
                "Do not present as verified."
            )
        return f"Marked as {result}."
