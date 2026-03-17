"""Sandbox verification — audit whether analyses used sandbox for calculations."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from jagabot.sandbox.tracker import SandboxTracker

logger = logging.getLogger(__name__)

# Expected calculation types per analysis phase
_EXPECTED_CALCS: dict[str, list[str]] = {
    "web": [],  # websearch doesn't compute
    "support": ["cv_analysis", "early_warning"],
    "billing": ["monte_carlo", "equity", "margin_call", "confidence_interval"],
    "supervisor": ["bayesian", "sensitivity", "pareto"],
}


@dataclass
class VerificationReport:
    """Result of a sandbox usage audit."""

    verified: bool
    total_expected: int = 0
    total_actual: int = 0
    missing: list[str] = field(default_factory=list)
    coverage_pct: float = 0.0
    details: list[dict[str, Any]] = field(default_factory=list)


class SandboxVerifier:
    """Verify sandbox usage for an analysis session.

    Checks the tracker database for expected calculation types and
    reports coverage.  Useful for auditing that no calculations were
    done outside the sandbox.
    """

    def __init__(self, tracker: SandboxTracker | None = None):
        self.tracker = tracker or SandboxTracker()

    def get_expected_calculations(
        self, phases: list[str] | None = None,
    ) -> list[str]:
        """Return the list of expected calc_types for the given phases."""
        phases = phases or list(_EXPECTED_CALCS.keys())
        expected: list[str] = []
        for phase in phases:
            expected.extend(_EXPECTED_CALCS.get(phase, []))
        return expected

    def verify_analysis(
        self,
        since_ts: str,
        phases: list[str] | None = None,
    ) -> VerificationReport:
        """Audit sandbox usage since *since_ts* (ISO timestamp).

        Compares expected calculation types against actual tracker records.
        """
        expected = self.get_expected_calculations(phases)
        records = self.tracker.get_executions_for_session(since_ts)

        actual_types = {r.calc_type for r in records if r.calc_type}
        missing = [c for c in expected if c not in actual_types]

        total_expected = len(expected)
        total_actual = len(actual_types & set(expected))
        coverage = (total_actual / total_expected * 100) if total_expected > 0 else 100.0

        details = [
            {
                "calc_type": c,
                "found": c in actual_types,
                "record_count": sum(1 for r in records if r.calc_type == c),
            }
            for c in expected
        ]

        return VerificationReport(
            verified=len(missing) == 0,
            total_expected=total_expected,
            total_actual=total_actual,
            missing=missing,
            coverage_pct=round(coverage, 1),
            details=details,
        )

    def quick_check(self, since_ts: str) -> str:
        """One-line verification summary."""
        rpt = self.verify_analysis(since_ts)
        if rpt.verified:
            return f"✅ ALL {rpt.total_expected} calculations used sandbox ({rpt.coverage_pct}% coverage)"
        return (
            f"❌ {len(rpt.missing)} of {rpt.total_expected} calculations "
            f"missing from sandbox: {rpt.missing}"
        )
