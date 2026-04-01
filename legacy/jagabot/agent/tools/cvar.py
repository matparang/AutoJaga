"""Conditional Value at Risk (CVaR / Expected Shortfall) tool."""

import json
from typing import Any

import numpy as np

from jagabot.agent.tools.base import Tool


def calculate_cvar(
    prices: list[float],
    current_price: float,
    confidence: float = 0.95,
    portfolio_value: float = 100_000,
) -> dict:
    """CVaR (Expected Shortfall) — average loss beyond the VaR threshold.

    Args:
        prices: Simulated final prices from monte_carlo tool.
        current_price: Current asset price.
        confidence: Confidence level (0.95 or 0.99).
        portfolio_value: Portfolio value.

    Returns:
        dict with cvar_pct, cvar_amount, var_pct, var_amount, n_tail.
    """
    # Parameter validation
    if not prices:
        return {"error": "prices list cannot be empty"}
    if current_price <= 0:
        return {"error": "current_price must be positive"}
    if confidence <= 0 or confidence >= 1:
        return {"error": f"confidence must be between 0 and 1 exclusive, got {confidence}"}
    if portfolio_value <= 0:
        return {"error": "portfolio_value must be positive"}
    
    arr = np.array(prices)
    sim_returns = (arr - current_price) / current_price
    cutoff = np.percentile(sim_returns, (1 - confidence) * 100)
    tail = sim_returns[sim_returns <= cutoff]
    if len(tail) == 0:
        tail = np.array([cutoff])
    cvar_return = float(np.mean(tail))
    var_return = float(cutoff)
    return {
        "cvar_pct": round(-cvar_return * 100, 4),
        "cvar_amount": round(-cvar_return * portfolio_value, 2),
        "var_pct": round(-var_return * 100, 4),
        "var_amount": round(-var_return * portfolio_value, 2),
        "confidence": confidence,
        "n_tail": int(len(tail)),
        "n_simulations": len(prices),
        "method": "monte_carlo_cvar",
    }


def compare_var_cvar(
    prices: list[float],
    current_price: float,
    confidence_levels: list[float] | None = None,
    portfolio_value: float = 100_000,
) -> dict:
    """Compare VaR and CVaR across multiple confidence levels.

    Args:
        prices: Simulated final prices.
        current_price: Current price.
        confidence_levels: List of confidence levels (default [0.90, 0.95, 0.99]).
        portfolio_value: Portfolio value.

    Returns:
        dict with comparison table across confidence levels.
    """
    if confidence_levels is None:
        confidence_levels = [0.90, 0.95, 0.99]
    results = []
    for cl in confidence_levels:
        r = calculate_cvar(prices, current_price, cl, portfolio_value)
        if "error" in r:
            return r
        results.append({
            "confidence": cl,
            "var_pct": r["var_pct"],
            "var_amount": r["var_amount"],
            "cvar_pct": r["cvar_pct"],
            "cvar_amount": r["cvar_amount"],
            "excess_loss": round(r["cvar_amount"] - r["var_amount"], 2),
        })
    return {"comparison": results, "portfolio_value": portfolio_value}


class CVaRTool(Tool):
    """Conditional Value at Risk / Expected Shortfall tool."""

    name = "cvar"
    description = (
        "Conditional Value at Risk (CVaR / Expected Shortfall) — measures the average loss "
        "in the worst-case tail beyond the VaR threshold. More conservative than VaR.\n\n"
        "CALL THIS TOOL after monte_carlo to understand tail risk — 'how bad could it get?'\n\n"
        "Methods:\n"
        "- calculate_cvar: CVaR at a single confidence level → returns both VaR and CVaR\n"
        "- compare_var_cvar: Compare VaR vs CVaR at 90%, 95%, 99% → shows how tail risk escalates\n\n"
        "Chain: monte_carlo → cvar → decision engine (bear perspective uses CVaR). "
        "Pass the 'prices' array from monte_carlo result directly."
    )
    parameters = {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["calculate_cvar", "compare_var_cvar"],
                "description": (
                    "calculate_cvar: needs {prices: [...], current_price, confidence?, portfolio_value?}. "
                    "compare_var_cvar: needs {prices: [...], current_price, confidence_levels?, portfolio_value?}."
                ),
            },
            "params": {
                "type": "object",
                "description": (
                    "Keyword arguments. Examples:\n"
                    "calculate_cvar: {\"prices\": [148, 142, 155], \"current_price\": 150, \"confidence\": 0.99}\n"
                    "compare_var_cvar: {\"prices\": [148, 142, 155], \"current_price\": 150, "
                    "\"confidence_levels\": [0.90, 0.95, 0.99]}"
                ),
            },
        },
        "required": ["method", "params"],
    }

    _DISPATCH = {
        "calculate_cvar": calculate_cvar,
        "compare_var_cvar": compare_var_cvar,
    }

    async def execute(self, **kwargs: Any) -> str:
        method = kwargs.get("method", "")
        params = kwargs.get("params", {})
        fn = self._DISPATCH.get(method)
        if fn is None:
            return json.dumps({"error": f"Unknown method: {method}"})
        try:
            result = fn(**params)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})
