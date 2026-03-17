"""DynamicsOracle tool — stateless system dynamics simulation (no file I/O, no cache)."""

import json
import math
from typing import Any

from jagabot.agent.tools.base import Tool


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def simulate(
    energy: float,
    stability: float,
    steps: int = 12,
    growth_model: str = "exponential",
    defense: float = 0.0,
    params: dict | None = None,
) -> list[dict]:
    """Run a stateless system dynamics simulation.

    Creates a fresh state each call — no persistence, no cache.

    Args:
        energy: Initial energy level (0-1 scale).
        stability: Initial stability level (0-1 scale).
        steps: Number of simulation steps.
        growth_model: One of exponential, logistic, linear, decay.
        defense: External defense factor (0-1).
        params: Optional overrides (growth_rate, decay_rate, capacity, shock_prob, shock_magnitude).
    """
    p = {
        "growth_rate": 0.05,
        "decay_rate": 0.03,
        "capacity": 1.0,
        "shock_prob": 0.1,
        "shock_magnitude": 0.15,
    }
    if params:
        p.update(params)

    states = []
    e, s = float(energy), float(stability)

    for step in range(steps):
        # growth model
        if growth_model == "exponential":
            delta_e = p["growth_rate"] * e
        elif growth_model == "logistic":
            delta_e = p["growth_rate"] * e * (1 - e / p["capacity"])
        elif growth_model == "linear":
            delta_e = p["growth_rate"]
        elif growth_model == "decay":
            delta_e = -p["decay_rate"] * e
        else:
            delta_e = 0.0

        # defense dampens shocks
        effective_shock = p["shock_magnitude"] * (1 - defense)

        # deterministic shock at known intervals for reproducibility
        shock = effective_shock if (step % max(1, int(1 / p["shock_prob"]))) == 0 else 0.0

        e = _clamp(e + delta_e - shock * 0.5, 0.0, p["capacity"])
        s = _clamp(s - shock + defense * 0.02 + 0.01 * (1 - abs(delta_e)), 0.0, 1.0)

        # risk level
        if s > 0.7:
            risk = "low"
        elif s > 0.4:
            risk = "moderate"
        elif s > 0.2:
            risk = "high"
        else:
            risk = "critical"

        states.append({
            "step": step + 1,
            "energy": round(e, 6),
            "stability": round(s, 6),
            "delta_energy": round(delta_e, 6),
            "shock": round(shock, 6),
            "risk_level": risk,
            "defense_active": defense > 0,
        })

    return states


def forecast_convergence(
    energy: float,
    stability: float,
    target_energy: float,
    growth_model: str = "logistic",
    max_steps: int = 100,
    tolerance: float = 0.01,
) -> dict:
    """Forecast how many steps until energy converges near a target."""
    states = simulate(energy, stability, steps=max_steps, growth_model=growth_model)
    for st in states:
        if abs(st["energy"] - target_energy) <= tolerance:
            return {
                "converged": True,
                "steps_needed": st["step"],
                "final_energy": st["energy"],
                "final_stability": st["stability"],
            }
    last = states[-1] if states else {"energy": energy, "stability": stability}
    return {
        "converged": False,
        "steps_needed": max_steps,
        "final_energy": last["energy"],
        "final_stability": last["stability"],
        "gap": round(abs(last["energy"] - target_energy), 6),
    }


class DynamicsTool(Tool):
    """System dynamics simulation engine — stateless, no file I/O."""

    name = "dynamics_oracle"
    description = (
        "System dynamics simulation for modelling feedback loops and energy decay in financial systems. "
        "CALL THIS TOOL when analyzing systemic risk propagation, crisis momentum, or recovery timelines.\n\n"
        "Methods:\n"
        "- simulate: Run n-step simulation with initial_energy, decay_rate, feedback_strength → "
        "returns energy trajectory over time\n"
        "- forecast_convergence: Find how many steps until energy drops below a target threshold\n\n"
        "Chain: Use after early_warning to model crisis propagation, then feed results into sensitivity_analyzer"
    )
    parameters = {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["simulate", "forecast_convergence"],
                "description": (
                    "simulate: needs {initial_energy, decay_rate, feedback_strength, steps}. "
                    "forecast_convergence: needs {initial_energy, decay_rate, feedback_strength, target_energy}."
                ),
            },
            "params": {
                "type": "object",
                "description": (
                    "Keyword arguments. Examples:\n"
                    "simulate: {\"initial_energy\": 100, \"decay_rate\": 0.05, \"feedback_strength\": 0.02, \"steps\": 50}\n"
                    "forecast_convergence: {\"initial_energy\": 100, \"decay_rate\": 0.05, "
                    "\"feedback_strength\": 0.02, \"target_energy\": 10}"
                ),
            },
        },
        "required": ["method", "params"],
    }

    _DISPATCH = {
        "simulate": simulate,
        "forecast_convergence": forecast_convergence,
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
