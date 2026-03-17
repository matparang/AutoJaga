"""Monte Carlo tool — VIX-based GBM simulation with confidence intervals."""

import json
import math
import random
from typing import Any

import numpy as np
from scipy import stats as sp_stats

from jagabot.agent.tools.base import Tool


def standard_monte_carlo(
    current_price: float,
    target_price: float,
    vix: float,
    days: int = 30,
    n_simulations: int = 10000,
    mu: float = 0.0,
    seed: int = 42,
) -> dict:
    """Standard Monte Carlo GBM using VIX-based volatility.

    This is the **canonical** implementation used across all Jagabot components.
    Both CLI and Colab should call this function to guarantee identical results.

    Args:
        current_price: Current asset price (e.g. 52.80).
        target_price: Threshold for probability calculation (e.g. 45).
        vix: VIX value — annualised vol expressed as index points (e.g. 58 → 58%).
        days: Forecast horizon in trading days (default 30).
        n_simulations: Number of simulated paths (default 10 000).
        mu: Daily drift (default 0.0 for risk-neutral GBM matching Colab).
        seed: Random seed for reproducibility (default 42).

    Returns:
        dict with probability, confidence intervals, price distribution, and
        the raw ``all_prices`` array (list) for downstream visualisation.
    """
    np.random.seed(seed)

    # Defensive guard: if caller passes decimal vol (e.g. 0.2225) instead of
    # VIX index (22.25), auto-scale to percentage form.
    if vix < 1.0:
        vix = vix * 100.0

    annual_vol = vix / 100.0
    daily_vol = annual_vol / np.sqrt(252)

    # Vectorised GBM: S_T = S_0 · exp(Σ (mu − ½σ²) + σ·Z_t)
    z = np.random.standard_normal((n_simulations, days))
    log_returns = (mu - 0.5 * daily_vol**2) + daily_vol * z
    cumulative = np.cumsum(log_returns, axis=1)
    final_log = cumulative[:, -1]
    prices = current_price * np.exp(final_log)

    # Core statistics
    prob_below = float(np.mean(prices < target_price) * 100)
    n_below = int(np.sum(prices < target_price))

    # 95 % confidence interval via Beta distribution
    ci_lower, ci_upper = sp_stats.beta.interval(
        0.95, n_below + 1, n_simulations - n_below + 1
    )

    # Percentiles
    pct_keys = [5, 10, 25, 50, 75, 90, 95]
    percentile_values = np.percentile(prices, pct_keys)
    percentiles = {f"p{k}": round(float(v), 2) for k, v in zip(pct_keys, percentile_values)}

    result: dict[str, Any] = {
        "initial_price": current_price,
        "target_price": target_price,
        "vix": vix,
        "annual_vol": round(annual_vol, 4),
        "daily_vol": round(float(daily_vol), 6),
        "days": days,
        "simulations": n_simulations,
        "probability": round(prob_below, 2),
        "ci_95": [round(float(ci_lower) * 100, 2), round(float(ci_upper) * 100, 2)],
        "mean_price": round(float(np.mean(prices)), 2),
        "median_price": round(float(np.median(prices)), 2),
        "std_price": round(float(np.std(prices, ddof=1)), 2),
        "min_price": round(float(np.min(prices)), 2),
        "max_price": round(float(np.max(prices)), 2),
        "percentiles": percentiles,
        "all_prices": prices.tolist(),
    }

    # Expected value if breach occurs
    below_mask = prices < target_price
    if n_below > 0:
        result["expected_value_if_below"] = round(float(np.mean(prices[below_mask])), 2)
    else:
        result["expected_value_if_below"] = None

    return result


# ---------------------------------------------------------------------------
# Legacy wrapper — keeps backward-compatible call signature for any callers
# that still pass raw ``vol`` instead of ``vix``.
# ---------------------------------------------------------------------------

def monte_carlo_gbm(
    price: float,
    vol: float,
    days: int,
    n_sims: int = 10000,
    threshold: float | None = None,
    seed: int | None = None,
) -> dict:
    """Legacy GBM wrapper — converts ``vol`` (0-1 scale) to VIX and delegates."""
    # Defensive guard: if caller passes percentage (e.g. 22.25) instead of
    # decimal (0.2225), auto-scale down.
    if vol > 1.0:
        vol = vol / 100.0
    vix = vol * 100.0  # 0.58 → 58
    target = threshold if threshold is not None else price * 0.5
    result = standard_monte_carlo(
        current_price=price,
        target_price=target,
        vix=vix,
        days=days,
        n_simulations=n_sims,
        seed=seed if seed is not None else 42,
    )
    # Re-map keys for backward compat
    compat: dict[str, Any] = {
        "initial_price": result["initial_price"],
        "days": result["days"],
        "simulations": result["simulations"],
        "volatility": vol,
        "mean": result["mean_price"],
        "median": result["median_price"],
        "std": result["std_price"],
        "min": result["min_price"],
        "max": result["max_price"],
        "percentiles": result["percentiles"],
    }
    if threshold is not None:
        compat["threshold"] = threshold
        compat["prob_below"] = result["probability"]
        compat["prob_above"] = round(100.0 - result["probability"], 2)
        compat["expected_value_if_below"] = result["expected_value_if_below"]
        compat["ci_95"] = result["ci_95"]
    return compat


class MonteCarloTool(Tool):
    """Monte Carlo GBM simulation — VIX-based, with confidence intervals."""

    name = "monte_carlo"
    description = (
        "Monte Carlo simulation using Geometric Brownian Motion with VIX-based volatility. "
        "CALL THIS TOOL for any price forecasting, probability estimation, or risk simulation.\n\n"
        "Usage: Pass current_price, target_price, and vix to get:\n"
        "- probability of price falling below target\n"
        "- 95% confidence interval (scipy.stats.beta)\n"
        "- full price distribution array (feed into visualization tool)\n\n"
        "Example: current_price=150, target_price=120, vix=58 → \"72% chance of falling below RM120\"\n"
        "Chain: CV analysis → Monte Carlo → Visualization dashboard\n"
        "The 'prices' array in the result can be passed directly to the visualization tool."
    )
    parameters = {
        "type": "object",
        "properties": {
            "current_price": {
                "type": "number",
                "description": "Current asset price in local currency (e.g. 150.0 for RM150)",
            },
            "target_price": {
                "type": "number",
                "description": "Price threshold — simulation calculates P(price < target). E.g. 120.0",
            },
            "vix": {
                "type": "number",
                "description": "VIX index value representing annualised volatility. E.g. 58 means 58% annual vol",
            },
            "days": {
                "type": "integer",
                "description": "Forecast horizon in trading days. Default 30 (~6 weeks)",
            },
            "n_simulations": {
                "type": "integer",
                "description": "Number of Monte Carlo paths. Default 10000. More = higher accuracy",
            },
            "mu": {
                "type": "number",
                "description": "Daily drift rate. Default 0.0 (risk-neutral GBM)",
            },
            "seed": {
                "type": "integer",
                "description": "Random seed for reproducibility. Default 42",
            },
            "price": {"type": "number", "description": "(Legacy) alias for current_price"},
            "vol": {"type": "number", "description": "(Legacy) annualised vol 0-1 scale"},
            "threshold": {"type": "number", "description": "(Legacy) alias for target_price"},
        },
        "required": ["current_price", "target_price", "vix"],
    }

    async def execute(self, **kwargs: Any) -> str:
        try:
            # Detect legacy vs standard call
            if "vix" in kwargs and "current_price" in kwargs:
                kw = {k: v for k, v in kwargs.items() if k in {
                    "current_price", "target_price", "vix", "days",
                    "n_simulations", "mu", "seed",
                }}
                result = standard_monte_carlo(**kw)
            else:
                # Legacy path
                kw = {k: v for k, v in kwargs.items() if k in {
                    "price", "vol", "days", "n_sims", "threshold", "seed",
                }}
                result = monte_carlo_gbm(**kw)

            # Strip all_prices from tool output (too large for LLM context)
            out = {k: v for k, v in result.items() if k != "all_prices"}
            return json.dumps(out, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})