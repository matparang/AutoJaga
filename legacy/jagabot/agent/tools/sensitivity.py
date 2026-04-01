"""Sensitivity analyzer tool — parameter sensitivity and tornado analysis."""

import json
from typing import Any

from jagabot.agent.tools.base import Tool
from jagabot.agent.tools.dynamics import simulate as dynamics_simulate


def analyze_sensitivity(
    base_params: dict,
    vary_params: dict,
    steps: int = 12,
    growth_model: str = "logistic",
) -> dict:
    """Analyze sensitivity of outcomes to parameter variations.

    Args:
        base_params: Base scenario dict with 'energy', 'stability', 'defense', 'params'.
        vary_params: Dict mapping parameter names to [low, high] ranges.
            Supported top-level keys: energy, stability, defense.
            Nested 'params.*' keys also supported (e.g., 'params.growth_rate').
        steps: Number of simulation steps.
        growth_model: Growth model.
    """
    base_energy = base_params.get("energy", 0.5)
    base_stability = base_params.get("stability", 0.5)
    base_defense = base_params.get("defense", 0.0)
    sim_params = base_params.get("params", {})

    # Run base case
    base_states = dynamics_simulate(
        energy=base_energy, stability=base_stability,
        steps=steps, growth_model=growth_model,
        defense=base_defense, params=sim_params,
    )
    base_final_energy = base_states[-1]["energy"] if base_states else 0.0

    sensitivities = {}
    for param_name, (low, high) in vary_params.items():
        results = {}
        for label, value in [("low", low), ("high", high)]:
            kwargs = {
                "energy": base_energy, "stability": base_stability,
                "steps": steps, "growth_model": growth_model,
                "defense": base_defense, "params": dict(sim_params),
            }
            if param_name.startswith("params."):
                inner_key = param_name.split(".", 1)[1]
                kwargs["params"][inner_key] = value
            elif param_name in ("energy", "stability", "defense"):
                kwargs[param_name] = value

            states = dynamics_simulate(**kwargs)
            final_e = states[-1]["energy"] if states else 0.0
            results[label] = round(final_e, 6)

        swing = results["high"] - results["low"]
        sensitivities[param_name] = {
            "low_value": low,
            "high_value": high,
            "low_outcome": results["low"],
            "high_outcome": results["high"],
            "swing": round(swing, 6),
            "base_outcome": round(base_final_energy, 6),
        }

    # Rank by swing magnitude
    ranked = sorted(sensitivities.items(), key=lambda x: abs(x[1]["swing"]), reverse=True)
    return {
        "base_final_energy": round(base_final_energy, 6),
        "sensitivities": dict(ranked),
        "most_sensitive": ranked[0][0] if ranked else None,
        "least_sensitive": ranked[-1][0] if ranked else None,
    }


def tornado_analysis(
    base_params: dict,
    parameters: dict,
    steps: int = 12,
    growth_model: str = "logistic",
) -> dict:
    """Generate tornado chart data showing relative parameter impact.

    Args:
        base_params: Base scenario (energy, stability, defense, params).
        parameters: Dict of param_name -> [low, high] to test.
        steps: Number of simulation steps.
        growth_model: Growth model.
    """
    result = analyze_sensitivity(base_params, parameters, steps, growth_model)
    base = result["base_final_energy"]

    bars = []
    for param_name, sens in result["sensitivities"].items():
        bars.append({
            "parameter": param_name,
            "low_delta": round(sens["low_outcome"] - base, 6),
            "high_delta": round(sens["high_outcome"] - base, 6),
            "total_swing": sens["swing"],
        })

    bars.sort(key=lambda b: abs(b["total_swing"]), reverse=True)

    return {
        "base_outcome": base,
        "bars": bars,
        "parameter_count": len(bars),
    }


class SensitivityTool(Tool):
    """Sensitivity analysis engine."""

    name = "sensitivity_analyzer"
    description = (
        "Sensitivity analysis — identifies which parameters most impact outcomes. "
        "CALL THIS TOOL to find what drives risk: 'which factor matters most?', "
        "'how sensitive is the result to decay rate?'\n\n"
        "Methods:\n"
        "- analyze_sensitivity: Vary one parameter across a range, measure output impact → "
        "returns parameter-impact mapping\n"
        "- tornado_analysis: Multi-parameter sensitivity in one pass → "
        "returns ranked tornado chart data (most impactful parameter first)\n\n"
        "Chain: Run after dynamics_oracle simulation, feed tornado results into visualization"
    )
    parameters = {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["analyze_sensitivity", "tornado_analysis"],
                "description": (
                    "analyze_sensitivity: needs {base_params, param_name, param_range, steps}. "
                    "tornado_analysis: needs {base_params, param_ranges: {name: [low, high], ...}, steps}."
                ),
            },
            "params": {
                "type": "object",
                "description": (
                    "Keyword arguments. Examples:\n"
                    "analyze_sensitivity: {\"base_params\": {\"initial_energy\": 100, \"decay_rate\": 0.05, "
                    "\"feedback_strength\": 0.02}, \"param_name\": \"decay_rate\", "
                    "\"param_range\": [0.01, 0.1], \"steps\": 50}\n"
                    "tornado_analysis: {\"base_params\": {\"initial_energy\": 100, \"decay_rate\": 0.05, "
                    "\"feedback_strength\": 0.02}, \"param_ranges\": {\"decay_rate\": [0.01, 0.1], "
                    "\"feedback_strength\": [0.005, 0.05]}, \"steps\": 50}"
                ),
            },
        },
        "required": ["method", "params"],
    }

    _DISPATCH = {
        "analyze_sensitivity": analyze_sensitivity,
        "tornado_analysis": tornado_analysis,
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
