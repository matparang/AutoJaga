"""
TwoStageReview — Superpowers-style two-stage output review.

Stage 1 (Spec Compliance): checks that required output fields are present
    and non-empty for the given task type.
Stage 2 (Quality): uses EvaluationKernel to score the output against
    expected values. Threshold defaults to 0.7.

Both stages must pass for the review to succeed.
"""

from __future__ import annotations

from typing import Any


# Required fields per task type.  Each maps to a list of output keys
# that MUST be present and non-None.
DEFAULT_SPECS: dict[str, list[str]] = {
    "monte_carlo": ["probability", "confidence_interval", "simulations"],
    "risk_assessment": ["probability", "confidence_interval", "action", "rationale"],
    "var_analysis": ["var_value", "confidence_level", "horizon"],
    "stress_test": ["scenarios", "worst_case", "action"],
    "portfolio_review": ["total_value", "allocations", "risk_metrics"],
    "investment_thesis": ["opportunity", "risks", "entry_criteria", "position_sizing"],
    "default": ["action", "rationale"],
}


class TwoStageReview:
    """Two-stage review gate for financial analysis outputs."""

    def __init__(
        self,
        evaluation_kernel: Any | None = None,
        quality_threshold: float = 0.7,
        specs: dict[str, list[str]] | None = None,
    ):
        self._kernel = evaluation_kernel
        self._threshold = quality_threshold
        self._specs = dict(specs or DEFAULT_SPECS)

    # ------------------------------------------------------------------
    # Stage 1 — spec compliance
    # ------------------------------------------------------------------

    def stage1_spec(self, task: dict, output: dict) -> dict:
        """Check that required fields are present in *output*.

        Returns::

            {"passed": True/False, "missing": [...], "task_type": "..."}
        """
        task_type = task.get("type", "default")
        required = self._specs.get(task_type, self._specs.get("default", []))

        missing = [f for f in required if output.get(f) is None]

        return {
            "passed": len(missing) == 0,
            "missing": missing,
            "task_type": task_type,
            "checked": required,
        }

    # ------------------------------------------------------------------
    # Stage 2 — quality evaluation
    # ------------------------------------------------------------------

    def stage2_quality(self, task: dict, output: dict) -> dict:
        """Score the output quality.

        If an EvaluationKernel is available, delegates to
        ``evaluate_result(expected, actual)``.  Otherwise falls back to
        a simple heuristic: field-count ratio.

        Returns::

            {"passed": True/False, "score": 0.0–1.0, "method": "kernel"|"heuristic"}
        """
        expected = task.get("expected", {})

        # Try EvaluationKernel first
        if self._kernel is not None and expected:
            try:
                result = self._kernel.evaluate_result(expected, output)
                score = result.get("score", 0.0)
                return {
                    "passed": score >= self._threshold,
                    "score": round(score, 4),
                    "method": "kernel",
                    "details": result.get("details", {}),
                }
            except Exception:
                pass  # fall through to heuristic

        # Heuristic fallback: what fraction of output fields are non-None/non-empty?
        if not output:
            return {"passed": False, "score": 0.0, "method": "heuristic"}

        populated = sum(
            1 for v in output.values()
            if v is not None and v != "" and v != []
        )
        score = populated / max(len(output), 1)
        return {
            "passed": score >= self._threshold,
            "score": round(score, 4),
            "method": "heuristic",
        }

    # ------------------------------------------------------------------
    # Combined review
    # ------------------------------------------------------------------

    def review(self, task: dict, output: dict) -> dict:
        """Run both stages. Returns::

            {
                "passed": True/False,
                "stage1": {...},
                "stage2": {...},
                "failed_stage": None | 1 | 2,
            }
        """
        s1 = self.stage1_spec(task, output)
        if not s1["passed"]:
            return {
                "passed": False,
                "stage1": s1,
                "stage2": None,
                "failed_stage": 1,
            }

        s2 = self.stage2_quality(task, output)
        return {
            "passed": s2["passed"],
            "stage1": s1,
            "stage2": s2,
            "failed_stage": None if s2["passed"] else 2,
        }

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def register_spec(self, task_type: str, required_fields: list[str]) -> None:
        """Add or update required fields for a task type."""
        self._specs[task_type] = list(required_fields)

    def get_specs(self) -> dict[str, list[str]]:
        """Return all registered spec definitions."""
        return dict(self._specs)
