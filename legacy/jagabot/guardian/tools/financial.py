"""Financial engine tool — stateless pure functions for CV, equity, Monte Carlo, margin analysis."""

import json
import math
import random
from typing import Any

from jagabot.agent.tools.base import Tool


def calculate_cv(changes: list[float]) -> float:
    """Coefficient of variation with sample standard deviation."""
    if not changes or len(changes) < 2:
        return 0.0
    n = len(changes)
    mean = sum(changes) / n
    if mean == 0:
        return 0.0
    variance = sum((x - mean) ** 2 for x in changes) / (n - 1)
    return math.sqrt(variance) / abs(mean)


def calculate_cv_ratios(changes: list[float]) -> dict:
    """Calculate CV ratios with pattern classification across time windows."""
    if not changes or len(changes) < 2:
        return {"overall_cv": 0.0, "windows": {}, "pattern": "insufficient_data"}

    overall_cv = calculate_cv(changes)
    windows = {}
    for label, size in [("short", 3), ("medium", 7), ("long", 14)]:
        if len(changes) >= size:
            windows[label] = calculate_cv(changes[-size:])

    if not windows:
        return {"overall_cv": overall_cv, "windows": {}, "pattern": "insufficient_data"}

    cv_values = list(windows.values())
    trend = cv_values[-1] - cv_values[0] if len(cv_values) > 1 else 0.0

    if abs(trend) < 0.05:
        pattern = "stable"
    elif trend > 0:
        pattern = "increasing_volatility"
    else:
        pattern = "decreasing_volatility"

    return {
        "overall_cv": round(overall_cv, 6),
        "windows": {k: round(v, 6) for k, v in windows.items()},
        "trend": round(trend, 6),
        "pattern": pattern,
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


def monte_carlo_gbm(
    price: float,
    vol: float,
    days: int,
    n_sims: int = 10000,
    threshold: float | None = None,
    seed: int | None = None,
) -> dict:
    """Geometric Brownian Motion Monte Carlo simulation — stdlib only."""
    if seed is not None:
        random.seed(seed)

    dt = 1 / 252  # trading days
    drift = -0.5 * vol * vol * dt
    diffusion = vol * math.sqrt(dt)

    final_prices = []
    for _ in range(n_sims):
        p = price
        for _ in range(days):
            z = random.gauss(0, 1)
            p *= math.exp(drift + diffusion * z)
        final_prices.append(p)

    final_prices.sort()
    n = len(final_prices)
    mean_price = sum(final_prices) / n
    median_price = final_prices[n // 2]
    variance = sum((x - mean_price) ** 2 for x in final_prices) / (n - 1) if n > 1 else 0.0
    std_price = math.sqrt(variance)

    percentiles = {}
    for pct in [5, 10, 25, 50, 75, 90, 95]:
        idx = int(n * pct / 100)
        percentiles[f"p{pct}"] = round(final_prices[min(idx, n - 1)], 2)

    result = {
        "initial_price": price,
        "days": days,
        "simulations": n_sims,
        "volatility": vol,
        "mean": round(mean_price, 2),
        "median": round(median_price, 2),
        "std": round(std_price, 2),
        "min": round(final_prices[0], 2),
        "max": round(final_prices[-1], 2),
        "percentiles": percentiles,
    }

    if threshold is not None:
        count_below = sum(1 for p in final_prices if p < threshold)
        result["threshold"] = threshold
        result["prob_below"] = round(count_below / n * 100, 2)
        result["prob_above"] = round((1 - count_below / n) * 100, 2)
        ev_below = sum(p for p in final_prices if p < threshold)
        result["expected_value_if_below"] = round(ev_below / count_below, 2) if count_below else None

    return result


class FinancialTool(Tool):
    """Dispatches financial engine methods: cv, equity, margin, Monte Carlo."""

    name = "financial_engine"
    description = (
        "Financial analysis engine. Methods: calculate_cv, calculate_cv_ratios, "
        "calculate_equity, calculate_leveraged_equity, check_margin_call, monte_carlo_gbm"
    )
    parameters = {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "description": "The method to call",
                "enum": [
                    "calculate_cv",
                    "calculate_cv_ratios",
                    "calculate_equity",
                    "calculate_leveraged_equity",
                    "check_margin_call",
                    "monte_carlo_gbm",
                ],
            },
            "params": {
                "type": "object",
                "description": "Parameters for the chosen method (passed as kwargs)",
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
        "monte_carlo_gbm": monte_carlo_gbm,
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
