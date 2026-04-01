"""Bayesian reasoner tool — belief updates and simple network inference."""

import json
import math
from typing import Any

from jagabot.agent.tools.base import Tool


def update_belief(prior: float, likelihood: float, evidence_prob: float | None = None) -> dict:
    """Bayesian belief update using Bayes' theorem.

    P(H|E) = P(E|H) * P(H) / P(E)

    If evidence_prob is not given, it is computed assuming binary hypothesis:
        P(E) = P(E|H)*P(H) + P(E|~H)*P(~H)
    where P(E|~H) is approximated as (1 - likelihood).

    Args:
        prior: Prior probability P(H) in [0, 1].
        likelihood: Likelihood P(E|H) in [0, 1].
        evidence_prob: Optional marginal P(E).
    """
    prior = max(0.0, min(1.0, prior))
    likelihood = max(0.0, min(1.0, likelihood))

    if evidence_prob is None:
        complement_likelihood = 1.0 - likelihood
        evidence_prob = likelihood * prior + complement_likelihood * (1.0 - prior)

    if evidence_prob == 0:
        return {"posterior": 0.0, "prior": prior, "likelihood": likelihood, "evidence_prob": 0.0}

    posterior = (likelihood * prior) / evidence_prob

    bf = likelihood / (1 - likelihood) if likelihood < 1 else float("inf")
    prior_odds = prior / (1 - prior) if prior < 1 else float("inf")
    posterior_odds = posterior / (1 - posterior) if posterior < 1 else float("inf")

    return {
        "posterior": round(posterior, 6),
        "prior": round(prior, 6),
        "likelihood": round(likelihood, 6),
        "evidence_prob": round(evidence_prob, 6),
        "bayes_factor": round(bf, 6) if bf != float("inf") else "inf",
        "prior_odds": round(prior_odds, 6) if prior_odds != float("inf") else "inf",
        "posterior_odds": round(posterior_odds, 6) if posterior_odds != float("inf") else "inf",
        "belief_change": round(posterior - prior, 6),
        "direction": "strengthened" if posterior > prior else "weakened" if posterior < prior else "unchanged",
    }


def sequential_update(prior: float, observations: list[dict]) -> dict:
    """Apply sequential Bayesian updates for multiple observations.

    Args:
        prior: Initial prior P(H).
        observations: List of dicts with 'likelihood' and optional 'evidence_prob'.
    """
    current = prior
    history = [{"step": 0, "posterior": round(prior, 6), "observation": None}]

    for i, obs in enumerate(observations, 1):
        result = update_belief(
            prior=current,
            likelihood=obs.get("likelihood", 0.5),
            evidence_prob=obs.get("evidence_prob"),
        )
        current = result["posterior"]
        history.append({
            "step": i,
            "posterior": current,
            "likelihood": obs.get("likelihood", 0.5),
            "belief_change": result["belief_change"],
        })

    return {
        "initial_prior": round(prior, 6),
        "final_posterior": round(current, 6),
        "total_change": round(current - prior, 6),
        "n_updates": len(observations),
        "history": history,
    }


def bayesian_network_inference(nodes: dict, evidence: dict) -> dict:
    """Simple Bayesian network inference for linked hypotheses.

    Args:
        nodes: Dict mapping node names to {'prior': float, 'parents': {parent_name: influence}}.
        evidence: Dict mapping node names to observed likelihood values.
    """
    posteriors = {}
    processing_order = _topological_sort(nodes)

    for name in processing_order:
        node = nodes[name]
        prior = node.get("prior", 0.5)

        # Adjust prior based on parent posteriors
        for parent, influence in node.get("parents", {}).items():
            if parent in posteriors:
                parent_post = posteriors[parent]["posterior"]
                prior = prior + influence * (parent_post - 0.5)
                prior = max(0.0, min(1.0, prior))

        # Apply evidence if available
        if name in evidence:
            result = update_belief(prior=prior, likelihood=evidence[name])
            posteriors[name] = result
        else:
            posteriors[name] = {"posterior": round(prior, 6), "prior": round(prior, 6), "updated_by": "propagation"}

    return {"posteriors": posteriors, "evidence_applied": list(evidence.keys()), "nodes_processed": processing_order}


def _topological_sort(nodes: dict) -> list[str]:
    """Sort nodes so parents come before children."""
    visited = set()
    order = []

    def _visit(name):
        if name in visited:
            return
        visited.add(name)
        for parent in nodes.get(name, {}).get("parents", {}):
            if parent in nodes:
                _visit(parent)
        order.append(name)

    for name in nodes:
        _visit(name)
    return order


class BayesianTool(Tool):
    """Bayesian reasoning engine."""

    name = "bayesian_reasoner"
    description = (
        "Bayesian reasoning. Methods: update_belief, sequential_update, "
        "bayesian_network_inference"
    )
    parameters = {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["update_belief", "sequential_update", "bayesian_network_inference"],
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
        "update_belief": update_belief,
        "sequential_update": sequential_update,
        "bayesian_network_inference": bayesian_network_inference,
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
