"""Stress testing tool — scenario-based and historical crisis stress tests."""

import json
from typing import Any

from jagabot.agent.tools.base import Tool
from jagabot.agent.tools.dynamics import simulate as dynamics_simulate


# Historical crisis presets: (name, decay_rate, feedback_strength, description)
HISTORICAL_CRISES = {
    "asian_1997": {
        "name": "1997 Asian Financial Crisis",
        "decay_rate": 0.08,
        "feedback_strength": 0.04,
        "peak_drawdown_pct": 60,
        "duration_months": 18,
        "description": "Ringgit collapsed from 2.50 to 4.88 per USD. KLCI fell 79%.",
    },
    "gfc_2008": {
        "name": "2008 Global Financial Crisis",
        "decay_rate": 0.06,
        "feedback_strength": 0.035,
        "peak_drawdown_pct": 45,
        "duration_months": 12,
        "description": "KLCI fell 45%. Global credit freeze and banking collapse.",
    },
    "covid_2020": {
        "name": "2020 COVID-19 Crash",
        "decay_rate": 0.10,
        "feedback_strength": 0.02,
        "peak_drawdown_pct": 30,
        "duration_months": 3,
        "description": "Sharp 30% drop followed by V-shaped recovery. MCO lockdowns.",
    },
    "dot_com_2000": {
        "name": "2000 Dot-Com Bubble",
        "decay_rate": 0.04,
        "feedback_strength": 0.025,
        "peak_drawdown_pct": 35,
        "duration_months": 24,
        "description": "Slow grinding decline in tech-heavy portfolios over 2 years.",
    },
}


def position_stress(
    current_equity: float,
    current_price: float,
    stress_price: float,
    units: float,
) -> dict:
    """Position-level stress test — equity under a stressed asset price.

    Args:
        current_equity: Current account equity value.
        current_price: Current asset price.
        stress_price: Hypothetical stressed price.
        units: Number of units/shares held.

    Returns:
        dict with stress_equity, stress_loss, change_percent.
    """
    stress_loss = (stress_price - current_price) * units
    stress_equity = current_equity + stress_loss
    change_pct = (stress_equity / current_equity - 1) * 100 if current_equity else 0
    return {
        "current_equity": round(current_equity, 2),
        "current_price": round(current_price, 2),
        "stress_price": round(stress_price, 2),
        "units": round(units, 2),
        "stress_loss": round(abs(stress_loss), 2),
        "stress_equity": round(stress_equity, 2),
        "change_percent": round(change_pct, 2),
        "type": "position_stress",
    }


def run_stress_test(
    portfolio_value: float,
    scenarios: list[dict],
    steps: int = 60,
) -> dict:
    """Run custom stress test scenarios on a portfolio.

    Args:
        portfolio_value: Current portfolio value.
        scenarios: List of dicts with {name, shock_pct} or {name, decay_rate, feedback_strength}.
        steps: Simulation steps (days).

    Returns:
        dict with results per scenario: final_value, max_drawdown, loss.
    """
    results = []
    for s in scenarios:
        name = s.get("name", "unnamed")
        if "shock_pct" in s:
            shock = s["shock_pct"] / 100.0
            final = portfolio_value * (1 - shock)
            results.append({
                "scenario": name,
                "initial_value": portfolio_value,
                "final_value": round(final, 2),
                "loss": round(portfolio_value - final, 2),
                "loss_pct": round(shock * 100, 2),
                "type": "instant_shock",
            })
        else:
            dr = s.get("decay_rate", 0.05)
            fs = s.get("feedback_strength", 0.02)
            # Map crisis params to dynamics engine interface
            # energy scale: portfolio_value normalised to 0-1, stability inversely proportional to decay
            init_energy = 1.0
            init_stability = max(0.0, 1.0 - dr * 5)  # high decay → low stability
            sim = dynamics_simulate(
                energy=init_energy,
                stability=init_stability,
                steps=steps,
                growth_model="decay",
                defense=0.0,
                params={"decay_rate": dr, "growth_rate": fs},
            )
            # Extract energy trajectory and scale back to portfolio value
            trajectory = [step["energy"] * portfolio_value for step in sim]
            min_val = min(trajectory)
            final = trajectory[-1]
            peak = max(trajectory)
            drawdown = (peak - min_val) / peak if peak > 0 else 0
            results.append({
                "scenario": name,
                "initial_value": portfolio_value,
                "final_value": round(final, 2),
                "min_value": round(min_val, 2),
                "loss": round(portfolio_value - final, 2),
                "loss_pct": round((1 - final / portfolio_value) * 100, 2),
                "max_drawdown_pct": round(drawdown * 100, 2),
                "steps": steps,
                "type": "dynamics_simulation",
            })
    worst = max(results, key=lambda r: r["loss"]) if results else None
    return {
        "results": results,
        "worst_case": worst["scenario"] if worst else None,
        "portfolio_value": portfolio_value,
    }


def historical_stress(
    portfolio_value: float,
    crises: list[str] | None = None,
    steps: int = 60,
) -> dict:
    """Apply historical crisis scenarios to a portfolio.

    Args:
        portfolio_value: Current portfolio value.
        crises: List of crisis keys (asian_1997, gfc_2008, covid_2020, dot_com_2000).
                Defaults to all crises.
        steps: Simulation steps.

    Returns:
        dict with results per historical crisis.
    """
    if crises is None:
        crises = list(HISTORICAL_CRISES.keys())

    scenarios = []
    for key in crises:
        if key not in HISTORICAL_CRISES:
            continue
        c = HISTORICAL_CRISES[key]
        scenarios.append({
            "name": c["name"],
            "decay_rate": c["decay_rate"],
            "feedback_strength": c["feedback_strength"],
        })

    result = run_stress_test(portfolio_value, scenarios, steps)

    # Enrich with historical context
    for r in result["results"]:
        for key in crises:
            c = HISTORICAL_CRISES.get(key, {})
            if c.get("name") == r["scenario"]:
                r["historical_drawdown_pct"] = c["peak_drawdown_pct"]
                r["historical_duration_months"] = c["duration_months"]
                r["context"] = c["description"]
                break

    result["available_crises"] = list(HISTORICAL_CRISES.keys())
    return result


class StressTestTool(Tool):
    """Scenario-based stress testing tool."""

    name = "stress_test"
    description = (
        "Stress testing — simulate how a portfolio performs under crisis scenarios. "
        "CALL THIS TOOL when asked about worst-case scenarios, crisis preparedness, "
        "or 'what happens if the market crashes?'\n\n"
        "Methods:\n"
        "- run_stress_test: Custom scenarios with shock_pct or dynamics parameters\n"
        "- historical_stress: Preset crises — 1997 Asian Crisis, 2008 GFC, COVID-2020, Dot-Com 2000\n"
        "- position_stress: Equity impact from a specific stressed asset price (needs current_equity, current_price, stress_price, units)\n\n"
        "Chain: Use after monte_carlo for probability, then stress_test for scenario analysis. "
        "Feed results into counterfactual_sim for deeper what-if analysis."
    )
    parameters = {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["run_stress_test", "historical_stress", "position_stress"],
                "description": (
                    "run_stress_test: needs {portfolio_value, scenarios: [{name, shock_pct}], steps?}. "
                    "historical_stress: needs {portfolio_value, crises?: ['asian_1997','gfc_2008','covid_2020','dot_com_2000'], steps?}. "
                    "position_stress: needs {current_equity, current_price, stress_price, units}."
                ),
            },
            "params": {
                "type": "object",
                "description": (
                    "Keyword arguments. Examples:\n"
                    "run_stress_test: {\"portfolio_value\": 100000, \"scenarios\": "
                    "[{\"name\": \"mild\", \"shock_pct\": 10}, {\"name\": \"severe\", \"shock_pct\": 40}]}\n"
                    "historical_stress: {\"portfolio_value\": 100000, \"crises\": [\"asian_1997\", \"gfc_2008\"]}"
                ),
            },
        },
        "required": ["method", "params"],
    }

    _DISPATCH = {
        "run_stress_test": run_stress_test,
        "historical_stress": historical_stress,
        "position_stress": position_stress,
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
