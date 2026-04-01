"""Supervisor subagent — compiles final report using Bayesian, Sensitivity, and Pareto engines."""

from typing import Any

from jagabot.agent.tools.bayesian import update_belief, sequential_update
from jagabot.agent.tools.sensitivity import analyze_sensitivity
from jagabot.agent.tools.pareto import rank_strategies


async def supervisor_agent(
    web_results: dict[str, Any],
    support_results: dict[str, Any],
    billing_results: dict[str, Any],
) -> dict[str, Any]:
    """Compile final analysis report from all upstream results.

    Uses BayesianReasoner, SensitivityAnalyzer, and ParetoOptimizer to
    synthesize a final recommendation.

    Does NOT access memory — only the orchestrator stores results.

    Args:
        web_results: Output from websearch_agent.
        support_results: Output from support_agent.
        billing_results: Output from billing_agent.

    Returns:
        Dict with final report, bayesian_analysis, strategies, and narrative.
    """
    # --- Bayesian belief update ---
    # Prior: base rate for adverse event
    mc = billing_results.get("probability", {})
    prob_below = mc.get("prob_below", 50.0) / 100.0 if "prob_below" in mc else 0.5

    warnings = support_results.get("warnings", {})
    risk_score = warnings.get("risk_score", 0.0)
    warning_likelihood = min(1.0, risk_score / 10.0)

    bayesian_result = update_belief(prior=0.5, likelihood=max(0.01, min(0.99, prob_below)))

    # Sequential update with warning signals
    observations = []
    if warning_likelihood > 0:
        observations.append({"likelihood": min(0.99, warning_likelihood)})
    for signal in warnings.get("signals", [])[:3]:
        sev_map = {"low": 0.3, "medium": 0.5, "high": 0.7, "critical": 0.9}
        observations.append({"likelihood": sev_map.get(signal.get("severity", "low"), 0.3)})

    seq_result = sequential_update(prior=bayesian_result["posterior"], observations=observations) if observations else None

    final_posterior = seq_result["final_posterior"] if seq_result else bayesian_result["posterior"]

    # --- Strategy ranking ---
    margin = billing_results.get("margin_call", {})
    equity = billing_results.get("equity", {})
    current_equity = equity.get("current", 0.0)

    strategies = [
        {
            "name": "hold",
            "expected_return": mc.get("mean", 100) - mc.get("initial_price", 100),
            "risk": billing_results.get("derived_volatility", 0.3),
            "cost": 0,
        },
        {
            "name": "hedge",
            "expected_return": mc.get("mean", 100) - mc.get("initial_price", 100) * 0.95,
            "risk": billing_results.get("derived_volatility", 0.3) * 0.5,
            "cost": current_equity * 0.02,
        },
        {
            "name": "reduce_exposure",
            "expected_return": (mc.get("mean", 100) - mc.get("initial_price", 100)) * 0.5,
            "risk": billing_results.get("derived_volatility", 0.3) * 0.3,
            "cost": current_equity * 0.005,
        },
        {
            "name": "exit",
            "expected_return": 0,
            "risk": 0.01,
            "cost": current_equity * 0.01,
        },
    ]

    criteria = {
        "expected_return": {"weight": 0.4, "maximize": True},
        "risk": {"weight": 0.35, "maximize": False},
        "cost": {"weight": 0.25, "maximize": False},
    }

    ranked = rank_strategies(strategies=strategies, criteria=criteria)
    best_strategy = ranked.get("best", {})

    # --- Generate narrative ---
    level = warnings.get("level", "normal")
    margin_active = margin.get("active", False)

    narrative = _build_narrative(
        level=level,
        final_posterior=final_posterior,
        mc=mc,
        margin_active=margin_active,
        margin=margin,
        best_strategy=best_strategy,
        web_results=web_results,
    )

    return {
        "report": narrative,
        "bayesian_analysis": {
            "initial_update": bayesian_result,
            "sequential_update": seq_result,
            "final_posterior": round(final_posterior, 4),
        },
        "strategies": ranked,
        "risk_level": level,
        "margin_call_active": margin_active,
    }


def _build_narrative(
    level: str,
    final_posterior: float,
    mc: dict,
    margin_active: bool,
    margin: dict,
    best_strategy: dict,
    web_results: dict,
) -> str:
    """Build a human-readable report narrative."""
    lines = []
    lines.append("=" * 60)
    lines.append("  JAGABOT GUARDIAN REPORT")
    lines.append("=" * 60)
    lines.append("")

    # Market status
    level_emoji = {"normal": "🟢", "elevated": "🟡", "warning": "🟠", "critical": "🔴"}.get(level, "⚪")
    lines.append(f"MARKET STATUS: {level_emoji} {level.upper()}")

    # Probability
    if "prob_below" in mc:
        lines.append(f"THRESHOLD BREACH PROBABILITY: {mc['prob_below']:.1f}%")
    lines.append(f"BAYESIAN POSTERIOR (adverse event): {final_posterior:.1%}")

    # Monte Carlo summary
    lines.append(f"PRICE FORECAST: mean={mc.get('mean', 'N/A')}, "
                 f"range=[{mc.get('min', 'N/A')}, {mc.get('max', 'N/A')}]")

    # Margin
    margin_status = "🔴 ACTIVE" if margin_active else "🟢 CLEAR"
    lines.append(f"MARGIN CALL: {margin_status}")
    if margin_active:
        lines.append(f"  Shortfall: ${margin.get('shortfall', 0):,.2f}")

    # Strategy
    strat_name = best_strategy.get("name", "N/A")
    strat_score = best_strategy.get("_score", 0)
    lines.append(f"RECOMMENDED STRATEGY: {strat_name.upper()} (score: {strat_score:.2f})")

    # Web context
    headlines = [item.get("title", "") for item in web_results.get("news", [])][:3]
    if headlines:
        lines.append("")
        lines.append("LATEST NEWS:")
        for h in headlines:
            lines.append(f"  • {h}")

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)
