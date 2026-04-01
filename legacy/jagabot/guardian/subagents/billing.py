"""Billing subagent — calculates probabilities, expected value, and margin status."""

from typing import Any

from jagabot.agent.tools.financial_cv import (
    calculate_equity,
    check_margin_call,
)
from jagabot.agent.tools.monte_carlo import standard_monte_carlo, monte_carlo_gbm
from jagabot.agent.tools.statistical import confidence_interval


async def billing_agent(
    portfolio: dict[str, Any],
    market_data: dict[str, Any],
    support_results: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calculate probabilities, expected value, and margin status.

    Prefers VIX-based ``standard_monte_carlo`` when a VIX value is available
    in *market_data*.  Falls back to CV-derived volatility via the legacy
    ``monte_carlo_gbm`` wrapper when VIX is absent.

    Args:
        portfolio: Dict with 'capital', 'positions' (list), 'cash', and optional
                   'borrowed', 'maintenance_rate'.
        market_data: Dict with 'current' (asset prices + optional 'VIX'),
                     'historical_changes', and optional 'monte_carlo' overrides.
        support_results: Optional output from support_agent (for CV-derived volatility).

    Returns:
        Dict with probability, equity, margin_call, and confidence_interval.
    """
    # Derive volatility source
    cv_analysis = (support_results or {}).get("cv_analysis", {})
    primary_asset = next(iter(cv_analysis), None)

    current_prices = market_data.get("current", {})
    price = (
        current_prices.get(primary_asset, current_prices.get("price", 100.0))
        if current_prices
        else 100.0
    )

    # MC overrides from market_data
    mc_config = market_data.get("monte_carlo", {})
    n_sims = mc_config.get("n_sims", mc_config.get("n_simulations", 10000))
    days = mc_config.get("days", 30)
    seed = mc_config.get("seed", 42)

    # Prefer VIX when available
    vix = current_prices.get("VIX") or current_prices.get("vix")
    threshold = mc_config.get("threshold", mc_config.get("target_price"))

    if vix is not None and threshold is not None:
        mc_result = standard_monte_carlo(
            current_price=price,
            target_price=threshold,
            vix=float(vix),
            days=days,
            n_simulations=n_sims,
            seed=seed,
        )
        # Normalise keys for downstream consumers
        mc_out: dict[str, Any] = {k: v for k, v in mc_result.items() if k != "all_prices"}
    else:
        # Fallback: CV-derived vol (decimal, e.g. 0.30)
        vol = cv_analysis.get(primary_asset, {}).get("cv", 0.3) if primary_asset else 0.3
        # Defensive guard: CV should be decimal (0.30). If > 1.0, scale down.
        if vol > 1.0:
            vol = vol / 100.0
        mc_out = monte_carlo_gbm(
            price=price,
            vol=max(0.01, vol),
            days=days,
            n_sims=n_sims,
            threshold=threshold,
            seed=seed,
        )

    # Equity calculation
    equity_result = calculate_equity(
        capital=portfolio.get("capital", 0.0),
        positions=portfolio.get("positions", []),
        cash=portfolio.get("cash", 0.0),
    )

    # Leveraged equity fix: equity = capital + total_pnl (not capital + position_value + cash)
    leverage = portfolio.get("leverage", 1.0)
    if leverage > 1:
        capital_val = portfolio.get("capital", 0.0)
        total_pnl = sum(
            p.get("quantity", 0) * (p.get("current_price", 0) - p.get("entry_price", p.get("current_price", 0)))
            for p in portfolio.get("positions", [])
        )
        equity_result["current"] = round(capital_val + total_pnl, 2)
        equity_result["loan"] = round(capital_val * (leverage - 1), 2)

    # Margin check
    maintenance_rate = portfolio.get("maintenance_rate", 0.25)
    if leverage > 1:
        margin_result = check_margin_call(
            equity=equity_result["current"],
            pos_value=portfolio.get("capital", 0.0) * leverage,
            rate=1.0 / leverage,
        )
    else:
        margin_result = check_margin_call(
            equity=equity_result["current"],
            pos_value=equity_result["total_position"],
            rate=maintenance_rate,
        )

    # Confidence interval on MC percentile values
    percentile_values = list(mc_out.get("percentiles", {}).values())
    ci_result = (
        confidence_interval(percentile_values)
        if percentile_values
        else {"error": "no percentile data"}
    )

    return {
        "probability": mc_out,
        "equity": equity_result,
        "margin_call": margin_result,
        "confidence_interval": ci_result,
        "derived_volatility": round(mc_out.get("annual_vol", mc_out.get("volatility", 0.0)), 6),
        "primary_asset": primary_asset,
        "volatility_source": "vix" if vix is not None else "cv",
    }
