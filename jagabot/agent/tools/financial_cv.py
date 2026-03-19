"""Financial CV tool — CV calculation, ratios, equity, leveraged equity, margin analysis."""

import json
import math
from typing import Any

from jagabot.agent.tools.base import Tool


# ---------------------------------------------------------------------------
# Locale-aware pattern / classification labels
# ---------------------------------------------------------------------------

_PATTERN_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "stable": "stable",
        "increasing_volatility": "increasing_volatility",
        "decreasing_volatility": "decreasing_volatility",
        "insufficient_data": "insufficient_data",
    },
    "ms": {
        "stable": "STABIL",
        "increasing_volatility": "TIDAK STABIL",
        "decreasing_volatility": "STABIL MENURUN",
        "insufficient_data": "DATA TIDAK CUKUP",
    },
    "id": {
        "stable": "STABIL",
        "increasing_volatility": "TIDAK STABIL",
        "decreasing_volatility": "STABIL MENURUN",
        "insufficient_data": "DATA TIDAK CUKUP",
    },
}


def _localise_pattern(pattern: str, locale: str = "en") -> str:
    labels = _PATTERN_LABELS.get(locale, _PATTERN_LABELS["en"])
    return labels.get(pattern, pattern)


def calculate_cv(changes: list[float] = None, mean: float = None, stddev: float = None) -> float:
    """Coefficient of variation with sample standard deviation.
    
    Accepts either:
    - changes: list of price changes/returns
    - mean and stddev: precomputed statistics
    
    Returns CV = stddev / abs(mean)
    """
    # Handle mean/stddev input
    if mean is not None and stddev is not None:
        if mean == 0:
            return 0.0
        return stddev / abs(mean)
    
    # Handle changes list input (backward compatibility)
    if changes is None:
        changes = []
    if not changes or len(changes) < 2:
        return 0.0
    n = len(changes)
    mean_val = sum(changes) / n
    if mean_val == 0:
        return 0.0
    variance = sum((x - mean_val) ** 2 for x in changes) / (n - 1)
    return math.sqrt(variance) / abs(mean_val)


def calculate_cv_ratios(changes: list[float], locale: str = "en") -> dict:
    """Calculate CV ratios with pattern classification across time windows."""
    if not changes or len(changes) < 2:
        return {
            "overall_cv": 0.0, "windows": {},
            "pattern": _localise_pattern("insufficient_data", locale),
        }

    overall_cv = calculate_cv(changes)
    windows = {}
    for label, size in [("short", 3), ("medium", 7), ("long", 14)]:
        if len(changes) >= size:
            windows[label] = calculate_cv(changes[-size:])

    if not windows:
        return {
            "overall_cv": overall_cv, "windows": {},
            "pattern": _localise_pattern("insufficient_data", locale),
        }

    cv_values = list(windows.values())
    trend = cv_values[-1] - cv_values[0] if len(cv_values) > 1 else 0.0

    if abs(trend) < 0.05:
        pattern_key = "stable"
    elif trend > 0:
        pattern_key = "increasing_volatility"
    else:
        pattern_key = "decreasing_volatility"

    return {
        "overall_cv": round(overall_cv, 6),
        "windows": {k: round(v, 6) for k, v in windows.items()},
        "trend": round(trend, 6),
        "pattern": _localise_pattern(pattern_key, locale),
    }


def calculate_equity(capital: float, positions: list, cash: float = 0.0) -> dict:
    """Calculate portfolio equity from capital, positions, and cash."""
    total_position = 0.0
    position_details = []
    for pos in positions:
        qty = pos.get("quantity", 0)
        price = pos.get("current_price", 0.0)
        entry = pos.get("entry_price", price)
        value = qty * price
        pnl = qty * (price - entry)
        total_position += value
        position_details.append({
            "symbol": pos.get("symbol", "unknown"),
            "quantity": qty,
            "current_price": price,
            "entry_price": entry,
            "value": round(value, 2),
            "pnl": round(pnl, 2),
        })

    current_equity = capital + total_position + cash
    total_pnl = sum(p["pnl"] for p in position_details)

    return {
        "capital": round(capital, 2),
        "cash": round(cash, 2),
        "total_position": round(total_position, 2),
        "current": round(current_equity, 2),
        "total_pnl": round(total_pnl, 2),
        "positions": position_details,
    }


def calculate_leveraged_equity(portfolio: dict) -> dict:
    """Calculate leveraged equity metrics including margin ratios."""
    equity = portfolio.get("equity", 0.0)
    borrowed = portfolio.get("borrowed", 0.0)
    total_assets = equity + borrowed
    leverage_ratio = total_assets / equity if equity > 0 else float("inf")
    debt_equity = borrowed / equity if equity > 0 else float("inf")
    margin_ratio = equity / total_assets if total_assets > 0 else 0.0

    return {
        "equity": round(equity, 2),
        "borrowed": round(borrowed, 2),
        "total_assets": round(total_assets, 2),
        "leverage_ratio": round(leverage_ratio, 4),
        "debt_to_equity": round(debt_equity, 4),
        "margin_ratio": round(margin_ratio, 4),
    }


def check_margin_call(equity: float, pos_value: float, rate: float = 0.25) -> dict:
    """Check if a margin call is triggered based on equity and position value."""
    if pos_value <= 0:
        return {"active": False, "margin_ratio": 1.0, "required": 0.0, "shortfall": 0.0}

    margin_ratio = equity / pos_value
    required = pos_value * rate
    shortfall = max(0.0, required - equity)

    return {
        "active": margin_ratio < rate,
        "margin_ratio": round(margin_ratio, 4),
        "maintenance_rate": rate,
        "required_equity": round(required, 2),
        "current_equity": round(equity, 2),
        "shortfall": round(shortfall, 2),
        "excess": round(max(0.0, equity - required), 2),
    }


class FinancialCVTool(Tool):
    """Financial CV analysis — coefficient of variation, equity, margin."""

    name = "financial_cv"
    description = (
        "Financial Coefficient of Variation (CV) analysis for crisis assessment. "
        "CALL THIS TOOL whenever a user asks about stock risk, volatility patterns, "
        "equity positions, margin calls, or leveraged exposure.\n\n"
        "Methods:\n"
        "- calculate_cv: Compute CV from mean/stddev → identifies volatility regime\n"
        "- calculate_cv_ratios: Compare multiple assets' CVs → ranks relative risk (supports locale: 'en','ms','id')\n"
        "- calculate_equity: Basic equity = assets - liabilities\n"
        "- calculate_leveraged_equity: Equity with leverage multiplier\n"
        "- check_margin_call: Check if equity breaches margin requirement\n\n"
        "Chain: Use CV results → feed into early_warning → then monte_carlo → visualization"
    )
    parameters = {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "description": (
                    "Which calculation to run. "
                    "calculate_cv: needs {mean, stddev}. "
                    "calculate_cv_ratios: needs {cv_values: {name: cv, ...}}. "
                    "calculate_equity: needs {assets, liabilities}. "
                    "calculate_leveraged_equity: needs {assets, liabilities, leverage}. "
                    "check_margin_call: needs {equity, margin_requirement}."
                ),
                "enum": [
                    "calculate_cv",
                    "calculate_cv_ratios",
                    "calculate_equity",
                    "calculate_leveraged_equity",
                    "check_margin_call",
                ],
            },
            "params": {
                "type": "object",
                "description": (
                    "Keyword arguments for the chosen method. Examples:\n"
                    "calculate_cv: {\"mean\": 150.0, \"stddev\": 45.0}\n"
                    "calculate_cv_ratios: {\"cv_values\": {\"AAPL\": 0.3, \"TSLA\": 0.65}, \"locale\": \"ms\"}\n"
                    "calculate_equity: {\"assets\": 100000, \"liabilities\": 60000}\n"
                    "check_margin_call: {\"equity\": 25000, \"margin_requirement\": 30000}"
                ),
            },
        },
        "required": ["method", "params"],
    }

    _DISPATCH = {
        "calculate_cv": calculate_cv,
        "calculate_cv_ratios": calculate_cv_ratios,
        "calculate_equity": calculate_equity,
        "calculate_leveraged_equity": calculate_leveraged_equity,
        "check_margin_call": check_margin_call,
    }

    async def execute(self, method: str, params: dict, **kw: Any) -> str:
        fn = self._DISPATCH.get(method)
        if fn is None:
            return json.dumps({"error": f"Unknown method: {method}"})
        try:
            if isinstance(params, dict):
                result = fn(**params)
            else:
                result = fn(params)
            return json.dumps(result, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})
