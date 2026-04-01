"""K1 Bayesian reasoning tool — probabilistic inference with calibration persistence."""

import json
from typing import Any

from jagabot.agent.tools.base import Tool
from jagabot.kernels.k1_bayesian import K1Bayesian


class K1BayesianTool(Tool):
    """Bayesian kernel with calibration tracking."""

    name = "k1_bayesian"
    description = (
        "Bayesian reasoning kernel with calibration persistence. "
        "Tracks prediction accuracy over time and refines confidence based on history.\n\n"
        "Actions:\n"
        "- update_belief: Bayesian update — prior × likelihood → posterior with audit trail\n"
        "- assess: Full uncertainty assessment with Wilson confidence intervals\n"
        "- refine_confidence: Adjust raw confidence using historical calibration data\n"
        "- record_outcome: Record actual outcome for calibration tracking\n"
        "- get_calibration: Return Brier score and calibration quality per perspective\n\n"
        "Chain: Use after bayesian_reasoner for raw computation, "
        "then k1_bayesian to calibrate and persist results."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["update_belief", "assess", "refine_confidence",
                         "record_outcome", "get_calibration"],
                "description": (
                    "update_belief: {topic, evidence: {key: value}}. "
                    "assess: {problem: str}. "
                    "refine_confidence: {raw_confidence: float, perspective: str}. "
                    "record_outcome: {perspective, predicted_prob, actual: bool}. "
                    "get_calibration: {perspective?: str}."
                ),
            },
            "topic": {"type": "string", "description": "Topic for update_belief"},
            "evidence": {"type": "object", "description": "Evidence dict for update_belief"},
            "problem": {"type": "string", "description": "Problem string for assess"},
            "raw_confidence": {"type": "number", "description": "Raw confidence value (0-100)"},
            "perspective": {"type": "string", "description": "Perspective name (bull/bear/buffet)"},
            "predicted_prob": {"type": "number", "description": "Predicted probability (0-1)"},
            "actual": {"type": "boolean", "description": "Actual outcome for record_outcome"},
            "prediction_id": {"type": "string", "description": "Optional prediction ID"},
        },
        "required": ["action"],
    }

    def __init__(self, workspace: str | None = None) -> None:
        self._k1 = K1Bayesian(workspace)

    @property
    def kernel(self) -> K1Bayesian:
        return self._k1

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")

        if action == "update_belief":
            topic = kwargs.get("topic", "")
            evidence = kwargs.get("evidence", {})
            if not topic:
                return json.dumps({"error": "topic is required for update_belief"})
            result = self._k1.update(topic, evidence)
            return json.dumps(result)

        if action == "assess":
            problem = kwargs.get("problem", "")
            if not problem:
                return json.dumps({"error": "problem is required for assess"})
            result = self._k1.assess(problem)
            return json.dumps(result)

        if action == "refine_confidence":
            raw = kwargs.get("raw_confidence")
            perspective = kwargs.get("perspective", "")
            if raw is None or not perspective:
                return json.dumps({"error": "raw_confidence and perspective required"})
            refined = self._k1.refine_confidence(float(raw), perspective)
            return json.dumps({"raw": float(raw), "refined": refined, "perspective": perspective})

        if action == "record_outcome":
            perspective = kwargs.get("perspective", "")
            predicted = kwargs.get("predicted_prob")
            actual = kwargs.get("actual")
            if not perspective or predicted is None or actual is None:
                return json.dumps({"error": "perspective, predicted_prob, actual required"})
            result = self._k1.record_outcome(
                perspective, float(predicted), bool(actual),
                kwargs.get("prediction_id"),
            )
            return json.dumps(result)

        if action == "get_calibration":
            perspective = kwargs.get("perspective")
            result = self._k1.get_calibration(perspective)
            return json.dumps(result)

        return json.dumps({"error": f"Unknown action: {action}"})
