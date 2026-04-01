"""Counterfactual simulator tool — scenario simulation and comparison."""

import json
import math
from typing import Any

from jagabot.agent.tools.base import Tool
from jagabot.agent.tools.dynamics import simulate as dynamics_simulate


def simulate_counterfactual(
    baseline: dict,
    changes: dict,
    steps: int = 12,
    growth_model: str = "logistic",
) -> dict:
    """Simulate a counterfactual scenario by modifying baseline parameters.

    Args:
        baseline: Dict with 'energy', 'stability', and optional 'defense', 'params'.
        changes: Dict with parameter overrides to apply (e.g., {'defense': 0.5}).
        steps: Number of simulation steps.
        growth_model: Growth model to use.
    """
    # Run baseline scenario
    base_energy = baseline.get("energy", 0.5)
    base_stability = baseline.get("stability", 0.5)
    base_defense = baseline.get("defense", 0.0)
    base_params = baseline.get("params", {})

    baseline_states = dynamics_simulate(
        energy=base_energy,
        stability=base_stability,
        steps=steps,
        growth_model=growth_model,
        defense=base_defense,
        params=base_params,
    )

    # Apply changes for counterfactual
    cf_energy = changes.get("energy", base_energy)
    cf_stability = changes.get("stability", base_stability)
    cf_defense = changes.get("defense", base_defense)
    cf_params = {**base_params, **changes.get("params", {})}

    counterfactual_states = dynamics_simulate(
        energy=cf_energy,
        stability=cf_stability,
        steps=steps,
        growth_model=growth_model,
        defense=cf_defense,
        params=cf_params,
    )

    # Compare
    diffs = []
    for b, c in zip(baseline_states, counterfactual_states):
        diffs.append({
            "step": b["step"],
            "energy_diff": round(c["energy"] - b["energy"], 6),
            "stability_diff": round(c["stability"] - b["stability"], 6),
            "baseline_risk": b["risk_level"],
            "counterfactual_risk": c["risk_level"],
        })

    base_final = baseline_states[-1] if baseline_states else {}
    cf_final = counterfactual_states[-1] if counterfactual_states else {}

    return {
        "baseline_final": base_final,
        "counterfactual_final": cf_final,
        "changes_applied": changes,
        "energy_impact": round(cf_final.get("energy", 0) - base_final.get("energy", 0), 6),
        "stability_impact": round(cf_final.get("stability", 0) - base_final.get("stability", 0), 6),
        "step_diffs": diffs,
    }


def compare_scenarios(scenarios: list[dict], steps: int = 12, growth_model: str = "logistic") -> dict:
    """Compare multiple scenarios side by side.

    Args:
        scenarios: List of dicts, each with 'name', 'energy', 'stability', 'defense', 'params'.
        steps: Simulation steps.
        growth_model: Growth model.
    """
    results = []
    for sc in scenarios:
        states = dynamics_simulate(
            energy=sc.get("energy", 0.5),
            stability=sc.get("stability", 0.5),
            steps=steps,
            growth_model=growth_model,
            defense=sc.get("defense", 0.0),
            params=sc.get("params", {}),
        )
        final = states[-1] if states else {}
        avg_stability = sum(s["stability"] for s in states) / len(states) if states else 0.0
        results.append({
            "name": sc.get("name", "unnamed"),
            "final_energy": final.get("energy", 0),
            "final_stability": final.get("stability", 0),
            "final_risk": final.get("risk_level", "unknown"),
            "avg_stability": round(avg_stability, 6),
        })

    # Rank by final energy descending
    ranked = sorted(results, key=lambda r: r["final_energy"], reverse=True)
    for i, r in enumerate(ranked):
        r["rank"] = i + 1

    return {
        "scenarios_compared": len(scenarios),
        "results": ranked,
        "best": ranked[0]["name"] if ranked else None,
        "worst": ranked[-1]["name"] if ranked else None,
    }


class CounterfactualTool(Tool):
    """Counterfactual simulation engine."""

    name = "counterfactual_sim"
    description = (
        "Counterfactual scenario simulation — 'what-if' analysis for financial decisions. "
        "CALL THIS TOOL when users ask 'what if I had sold earlier?', 'what if rates change?', "
        "or when comparing alternative strategies.\n\n"
        "Methods:\n"
        "- simulate_counterfactual: Run system dynamics with altered parameters → "
        "compare actual vs hypothetical trajectory\n"
        "- compare_scenarios: Run multiple what-if scenarios side by side → "
        "returns ranked comparison with delta analysis\n\n"
        "Chain: Use after bayesian_reasoner to test high-probability scenarios, "
        "feed results into pareto_optimizer for strategy selection"
    )
    parameters = {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["simulate_counterfactual", "compare_scenarios"],
                "description": (
                    "simulate_counterfactual: needs {baseline_params, altered_params, steps}. "
                    "compare_scenarios: needs {base_params, scenarios: [{name, params}, ...], steps}."
                ),
            },
            "params": {
                "type": "object",
                "description": (
                    "Keyword arguments. Examples:\n"
                    "simulate_counterfactual: {\"baseline_params\": {\"initial_energy\": 100, "
                    "\"decay_rate\": 0.05, \"feedback_strength\": 0.02}, "
                    "\"altered_params\": {\"initial_energy\": 100, \"decay_rate\": 0.03, "
                    "\"feedback_strength\": 0.01}, \"steps\": 50}\n"
                    "compare_scenarios: {\"base_params\": {\"initial_energy\": 100, \"decay_rate\": 0.05, "
                    "\"feedback_strength\": 0.02}, \"scenarios\": [{\"name\": \"optimistic\", \"params\": "
                    "{\"decay_rate\": 0.02}}, {\"name\": \"pessimistic\", \"params\": {\"decay_rate\": 0.08}}], "
                    "\"steps\": 30}"
                ),
            },
        },
        "required": ["method", "params"],
    }

    _DISPATCH = {
        "simulate_counterfactual": simulate_counterfactual,
        "compare_scenarios": compare_scenarios,
    }

    async def execute(self, method: str, params: dict, **kw: Any) -> str:
        fn = self._DISPATCH.get(method)
        if fn is None:
            return json.dumps({"error": f"Unknown method: {method}"})
        try:
            result = fn(**params)
            return json.dumps(result, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})
