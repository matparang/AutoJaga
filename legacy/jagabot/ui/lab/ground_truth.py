"""Ground truth values from Colab for tool output comparison.

Each entry is keyed by (tool_name, method) and contains:
  - params: canonical parameter dict to match against
  - expected: dict of expected output fields with (min, max) tolerance ranges
  - label: human-readable description
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


# (tool_name, method_or_None) → list of ground truth entries
_GROUND_TRUTH: dict[tuple[str, str | None], list[dict[str, Any]]] = {
    ("monte_carlo", None): [
        {
            "label": "BABA P(<$70|30d) risk-neutral GBM",
            "params": {
                "current_price": 76.50,
                "threshold": 70,
                "vix": 52,
                "days": 30,
            },
            "expected": {
                "probability": (30.0, 38.0),  # ~34.24% ± tolerance
            },
        },
    ],
    ("stress_test", "position_stress"): [
        {
            "label": "BABA position stress $76.50→$65",
            "params": {
                "current_equity": 1_109_092,
                "current_price": 76.50,
                "stress_price": 65,
                "units": 21_307,
            },
            "expected": {
                "stress_equity": (860_000, 870_000),  # ~864,061
                "stress_loss": (-250_000, -240_000),
            },
        },
    ],
    ("var", "parametric_var"): [
        {
            "label": "BABA VaR 10-day 95% (annualized vol 82%)",
            "params": {
                "portfolio_value": 1_109_092,
                "annual_vol": 0.82,
                "holding_period": 10,
                "confidence": 0.95,
            },
            "expected": {
                "var_amount": (350_000, 500_000),  # ~$419K range
            },
        },
    ],
    ("var", "portfolio_var"): [
        {
            "label": "BABA portfolio VaR convenience",
            "params": {
                "position_value": 1_109_092,
                "cash": 0,
                "annual_vol": 0.82,
            },
            "expected": {
                "var_amount": (350_000, 500_000),
            },
        },
    ],
    ("decision_engine", "bear_perspective"): [
        {
            "label": "BABA bear with margin_call",
            "params": {
                "downside_risk": 33.85,
                "var_pct": 14.4,
                "margin_call": True,
            },
            "expected": {
                "confidence": (15.0, 35.0),  # ~24%
            },
        },
    ],
}


def _params_match(gt_params: dict, user_params: dict) -> bool:
    """Check if user params match ground truth params (loose numeric comparison)."""
    for key, expected_val in gt_params.items():
        actual_val = user_params.get(key)
        if actual_val is None:
            return False
        if isinstance(expected_val, (int, float)) and isinstance(actual_val, (int, float)):
            if abs(expected_val) > 0:
                if abs(expected_val - actual_val) / abs(expected_val) > 0.01:
                    return False
            elif abs(actual_val) > 0.01:
                return False
        elif str(expected_val) != str(actual_val):
            return False
    return True


def _extract_numeric(result: str | dict, field: str) -> float | None:
    """Try to pull a numeric field out of a result string or dict."""
    if isinstance(result, dict):
        val = result.get(field)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

    if isinstance(result, str):
        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict):
                val = parsed.get(field)
                if val is not None:
                    return float(val)
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
    return None


class GroundTruth:
    """Compare tool outputs against known Colab ground truth values."""

    def compare(
        self,
        tool_name: str,
        params: dict[str, Any],
        result: str | dict,
        method: str | None = None,
    ) -> dict[str, Any] | None:
        """Compare result against ground truth.

        Returns None if no ground truth exists for this tool/params combo.
        Otherwise returns {matches: bool, expected: dict, actual: dict, diffs: dict, label: str}.
        """
        entries = _GROUND_TRUTH.get((tool_name, method), [])
        if not entries:
            # Try without method
            entries = _GROUND_TRUTH.get((tool_name, None), [])
        if not entries:
            return None

        for entry in entries:
            if not _params_match(entry["params"], params):
                continue

            expected = entry["expected"]
            actual: dict[str, float | None] = {}
            diffs: dict[str, str] = {}
            all_match = True

            for field, (lo, hi) in expected.items():
                val = _extract_numeric(result, field)
                actual[field] = val
                if val is not None and lo <= val <= hi:
                    diffs[field] = "✅ in range"
                else:
                    all_match = False
                    diffs[field] = f"❌ got {val}, expected [{lo}, {hi}]"

            return {
                "matches": all_match,
                "expected": {k: f"[{lo}, {hi}]" for k, (lo, hi) in expected.items()},
                "actual": actual,
                "diffs": diffs,
                "label": entry.get("label", ""),
            }

        return None

    @staticmethod
    def list_ground_truths() -> list[dict[str, Any]]:
        """List all available ground truth entries."""
        result = []
        for (tool, method), entries in _GROUND_TRUTH.items():
            for entry in entries:
                result.append({
                    "tool": tool,
                    "method": method,
                    "label": entry.get("label", ""),
                    "params": entry["params"],
                    "expected": entry["expected"],
                })
        return result
