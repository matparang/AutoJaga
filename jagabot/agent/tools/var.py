"""Value at Risk (VaR) tool — parametric, historical, and Monte Carlo methods."""

import json
import math
from typing import Any

import numpy as np
from scipy import stats as sp_stats

from jagabot.agent.tools.base import Tool


def parametric_var(
    mean_return: float,
    std_return: float,
    confidence: float = 0.95,
    portfolio_value: float = 100_000,
    holding_period: int = 10,
) -> dict:
    """Parametric (variance-covariance) VaR assuming normal returns.

    Args:
        mean_return: Expected daily return (e.g. -0.001).
        std_return: Daily return standard deviation.
        confidence: Confidence level (0.95 or 0.99).
        portfolio_value: Portfolio value in currency units.
        holding_period: Holding period in days (default 10, Basel III standard).

    Returns:
        dict with var_pct, var_amount, confidence, holding_period.
    """
    # Defensive guard: daily std_return should be decimal (e.g. 0.025).
    # If caller passes percentage (e.g. 2.5), auto-scale down.
    if std_return > 1.0:
        std_return = std_return / 100.0

    z = sp_stats.norm.ppf(1 - confidence)
    adj_mean = mean_return * holding_period
    adj_std = std_return * math.sqrt(holding_period)
    var_pct = -(adj_mean + z * adj_std)
    var_amount = var_pct * portfolio_value
    return {
        "var_pct": round(float(var_pct) * 100, 4),
        "var_amount": round(float(var_amount), 2),
        "confidence": confidence,
        "holding_period_days": holding_period,
        "method": "parametric",
    }


def historical_var(
    returns: list[float],
    confidence: float = 0.95,
    portfolio_value: float = 100_000,
) -> dict:
    """Historical simulation VaR from observed return series.

    Args:
        returns: List of historical daily returns (e.g. [-0.02, 0.01, ...]).
        confidence: Confidence level.
        portfolio_value: Portfolio value.

    Returns:
        dict with var_pct, var_amount, confidence, n_observations.
    """
    if not returns:
        return {"error": "returns list is empty"}
    arr = np.array(returns)
    cutoff = np.percentile(arr, (1 - confidence) * 100)
    var_pct = -float(cutoff)
    var_amount = var_pct * portfolio_value
    return {
        "var_pct": round(var_pct * 100, 4),
        "var_amount": round(var_amount, 2),
        "confidence": confidence,
        "n_observations": len(returns),
        "method": "historical",
    }


def monte_carlo_var(
    prices: list[float],
    current_price: float,
    confidence: float = 0.95,
    portfolio_value: float = 100_000,
) -> dict:
    """Monte Carlo VaR from simulated final price distribution.

    Args:
        prices: Array of simulated final prices (from monte_carlo tool).
        current_price: Current asset price.
        confidence: Confidence level.
        portfolio_value: Portfolio value.

    Returns:
        dict with var_pct, var_amount, confidence, n_simulations.
    """
    if not prices or current_price <= 0:
        return {"error": "invalid prices or current_price"}
    arr = np.array(prices)
    sim_returns = (arr - current_price) / current_price
    cutoff = np.percentile(sim_returns, (1 - confidence) * 100)
    var_pct = -float(cutoff)
    var_amount = var_pct * portfolio_value
    return {
        "var_pct": round(var_pct * 100, 4),
        "var_amount": round(var_amount, 2),
        "confidence": confidence,
        "n_simulations": len(prices),
        "method": "monte_carlo",
    }


def portfolio_var(
    position_value: float,
    cash: float,
    annual_vol: float,
    holding_period: int = 10,
    confidence: float = 0.95,
) -> dict:
    """Convenience VaR from portfolio composition and annual volatility.

    Calculates portfolio_value = position_value + cash, derives daily std
    from annual_vol, then delegates to parametric_var.

    Args:
        position_value: Total position value (units × price).
        cash: Cash held in the portfolio.
        annual_vol: Annualised volatility (decimal, e.g. 0.52 for 52%).
        holding_period: Holding period in days (default 10, Basel III).
        confidence: Confidence level (default 0.95).

    Returns:
        dict with var_pct, var_amount, portfolio_value, position_value, cash.
    """
    portfolio_value = position_value + cash
    daily_std = annual_vol / math.sqrt(252)
    result = parametric_var(
        mean_return=0.0,
        std_return=daily_std,
        portfolio_value=portfolio_value,
        holding_period=holding_period,
        confidence=confidence,
    )
    result["position_value"] = round(position_value, 2)
    result["cash"] = round(cash, 2)
    result["annual_vol"] = round(annual_vol, 4)
    return result


class VaRTool(Tool):
    """Value at Risk tool with 3 calculation methods."""

    name = "var"
    description = (
        "Value at Risk (VaR) — quantifies maximum expected loss at a given confidence level. "
        "CALL THIS TOOL when asked about portfolio risk, maximum loss, or downside exposure.\n\n"
        "Methods:\n"
        "- parametric_var: Fast analytical VaR assuming normal returns (needs mean_return, std_return)\n"
        "- historical_var: VaR from actual return history (needs returns array)\n"
        "- monte_carlo_var: VaR from MC simulation prices (needs prices array from monte_carlo tool)\n\n"
        "Chain: Run monte_carlo first → pass 'prices' array to monte_carlo_var method. "
        "Compare with CVaR tool for tail risk. Feed result into decision engine."
    )
    parameters = {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["parametric_var", "historical_var", "monte_carlo_var", "portfolio_var"],
                "description": (
                    "parametric_var: needs {mean_return, std_return, confidence?, portfolio_value?, holding_period? (default 10-day Basel)}. "
                    "historical_var: needs {returns: [...], confidence?, portfolio_value?}. "
                    "monte_carlo_var: needs {prices: [...], current_price, confidence?, portfolio_value?}. "
                    "portfolio_var: needs {position_value, cash, annual_vol, holding_period?, confidence?}."
                ),
            },
            "params": {
                "type": "object",
                "description": (
                    "Keyword arguments. Examples:\n"
                    "parametric_var: {\"mean_return\": -0.001, \"std_return\": 0.025, \"confidence\": 0.99, \"portfolio_value\": 100000}\n"
                    "historical_var: {\"returns\": [-0.02, 0.01, -0.03, 0.005], \"confidence\": 0.95}\n"
                    "monte_carlo_var: {\"prices\": [148, 142, 155, ...], \"current_price\": 150, \"confidence\": 0.99}"
                ),
            },
        },
        "required": ["method", "params"],
    }

    _DISPATCH = {
        "parametric_var": parametric_var,
        "historical_var": historical_var,
        "monte_carlo_var": monte_carlo_var,
        "portfolio_var": portfolio_var,
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
