"""Pareto optimizer tool — multi-objective optimization and strategy ranking."""

import json
from typing import Any

from jagabot.agent.tools.base import Tool


def _dominates(a: dict, b: dict, objectives: list[str], maximize: list[bool]) -> bool:
    """Return True if solution 'a' Pareto-dominates 'b'."""
    dominated_in_any = False
    for obj, do_max in zip(objectives, maximize):
        va, vb = a.get(obj, 0), b.get(obj, 0)
        if do_max:
            if va < vb:
                return False
            if va > vb:
                dominated_in_any = True
        else:
            if va > vb:
                return False
            if va < vb:
                dominated_in_any = True
    return dominated_in_any


def find_pareto_optimal(
    solutions: list[dict],
    objectives: list[str],
    maximize: list[bool] | None = None,
) -> dict:
    """Find the Pareto-optimal front from a set of solutions.

    Args:
        solutions: List of dicts, each containing objective values.
        objectives: List of objective key names to optimize.
        maximize: List of bools indicating whether each objective should be maximized (True) or minimized (False). Defaults to all maximize.
    """
    if not solutions or not objectives:
        return {"pareto_front": [], "dominated": [], "error": None}

    if maximize is None:
        maximize = [True] * len(objectives)

    pareto_front = []
    dominated = []

    for i, candidate in enumerate(solutions):
        is_dominated = False
        for j, other in enumerate(solutions):
            if i != j and _dominates(other, candidate, objectives, maximize):
                is_dominated = True
                break
        if is_dominated:
            dominated.append(candidate)
        else:
            pareto_front.append(candidate)

    return {
        "pareto_front": pareto_front,
        "pareto_count": len(pareto_front),
        "dominated_count": len(dominated),
        "total_solutions": len(solutions),
        "objectives": objectives,
    }


def rank_strategies(
    strategies: list[dict],
    criteria: dict,
) -> dict:
    """Rank strategies using weighted scoring.

    Args:
        strategies: List of strategy dicts with named attributes.
        criteria: Dict mapping attribute names to {'weight': float, 'maximize': bool}.
    """
    if not strategies or not criteria:
        return {"ranked": [], "error": "empty input"}

    scored = []
    for strategy in strategies:
        total_score = 0.0
        detail = {}
        for attr, config in criteria.items():
            value = strategy.get(attr, 0)
            weight = config.get("weight", 1.0)
            do_max = config.get("maximize", True)

            # Normalize to [0, 1] across all strategies for this attribute
            all_vals = [s.get(attr, 0) for s in strategies]
            min_v, max_v = min(all_vals), max(all_vals)
            if max_v == min_v:
                normalized = 0.5
            else:
                normalized = (value - min_v) / (max_v - min_v)
                if not do_max:
                    normalized = 1.0 - normalized

            weighted = normalized * weight
            total_score += weighted
            detail[attr] = {
                "raw": value,
                "normalized": round(normalized, 4),
                "weighted": round(weighted, 4),
            }

        scored.append({
            **strategy,
            "_score": round(total_score, 4),
            "_detail": detail,
        })

    scored.sort(key=lambda s: s["_score"], reverse=True)
    for i, s in enumerate(scored):
        s["_rank"] = i + 1

    return {
        "ranked": scored,
        "best": scored[0] if scored else None,
        "worst": scored[-1] if scored else None,
        "criteria_used": list(criteria.keys()),
    }


def optimize_portfolio_allocation(
    assets: list[dict],
    total_capital: float,
    risk_tolerance: float = 0.5,
) -> dict:
    """Simple portfolio allocation optimizer using risk-return scoring.

    Args:
        assets: List of dicts with 'name', 'expected_return', 'risk' (volatility).
        total_capital: Total capital to allocate.
        risk_tolerance: 0 = risk-averse, 1 = risk-seeking.
    """
    if not assets:
        return {"allocations": [], "error": "no assets"}

    scored = []
    for asset in assets:
        ret = asset.get("expected_return", 0.0)
        risk = asset.get("risk", 0.5)
        score = risk_tolerance * ret - (1 - risk_tolerance) * risk
        scored.append({**asset, "_score": score})

    # Normalize scores to weights
    total_score = sum(max(0.01, s["_score"]) for s in scored)
    allocations = []
    for s in scored:
        weight = max(0.01, s["_score"]) / total_score
        allocations.append({
            "name": s.get("name", "unknown"),
            "weight": round(weight, 4),
            "amount": round(weight * total_capital, 2),
            "expected_return": s.get("expected_return", 0),
            "risk": s.get("risk", 0),
        })

    allocations.sort(key=lambda a: a["weight"], reverse=True)
    portfolio_return = sum(a["weight"] * a["expected_return"] for a in allocations)
    portfolio_risk = sum(a["weight"] * a["risk"] for a in allocations)

    return {
        "allocations": allocations,
        "total_capital": total_capital,
        "portfolio_expected_return": round(portfolio_return, 6),
        "portfolio_risk": round(portfolio_risk, 6),
        "risk_tolerance": risk_tolerance,
    }


class ParetoTool(Tool):
    """Pareto optimization and strategy ranking engine."""

    name = "pareto_optimizer"
    description = (
        "Multi-objective optimization. Methods: find_pareto_optimal, "
        "rank_strategies, optimize_portfolio_allocation"
    )
    parameters = {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["find_pareto_optimal", "rank_strategies", "optimize_portfolio_allocation"],
                "description": "The method to call",
            },
            "params": {
                "type": "object",
                "description": "Parameters for the chosen method",
            },
        },
        "required": ["method", "params"],
    }

    _DISPATCH = {
        "find_pareto_optimal": find_pareto_optimal,
        "rank_strategies": rank_strategies,
        "optimize_portfolio_allocation": optimize_portfolio_allocation,
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
