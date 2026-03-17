"""K3 Multi-Perspective tool — calibrated Bull/Bear/Buffet with accuracy tracking."""

import json
from typing import Any

from jagabot.agent.tools.base import Tool
from jagabot.kernels.k3_perspective import K3MultiPerspective


class K3PerspectiveTool(Tool):
    """Calibrated multi-perspective decision tool."""

    name = "k3_perspective"
    description = (
        "Calibrated multi-perspective kernel — Bull/Bear/Buffet with historical accuracy tracking "
        "and adaptive weight recalibration.\n\n"
        "Actions:\n"
        "- get_perspective: Get a single perspective with calibrated confidence\n"
        "- update_accuracy: Record outcome to track perspective accuracy\n"
        "- get_weights: Return current weights (adaptive if enough history)\n"
        "- recalibrate: Force weight recalibration from accuracy data\n"
        "- calibrated_decision: Full 3-perspective analysis with calibrated weights\n"
        "- accuracy_stats: Return accuracy metrics for all perspectives\n\n"
        "Chain: Use instead of decision_engine for calibrated decisions. "
        "Feed outcomes back via update_accuracy to improve over time."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get_perspective", "update_accuracy", "get_weights",
                         "recalibrate", "calibrated_decision", "accuracy_stats"],
                "description": (
                    "get_perspective: {ptype: bull/bear/buffet, data: {probability_below_target, ...}}. "
                    "update_accuracy: {perspective, predicted_verdict, actual_outcome: up/down}. "
                    "get_weights: no params. "
                    "recalibrate: no params. "
                    "calibrated_decision: {data: {probability_below_target, current_price, target_price, ...}}. "
                    "accuracy_stats: no params."
                ),
            },
            "ptype": {"type": "string", "description": "Perspective type: bull, bear, or buffet"},
            "data": {"type": "object", "description": "Parameters for perspective/decision"},
            "perspective": {"type": "string", "description": "Perspective name for update_accuracy"},
            "predicted_verdict": {"type": "string", "description": "The verdict given"},
            "actual_outcome": {"type": "string", "description": "Actual result: up or down"},
        },
        "required": ["action"],
    }

    def __init__(self, workspace: str | None = None) -> None:
        self._k3 = K3MultiPerspective(workspace=workspace)

    @property
    def kernel(self) -> K3MultiPerspective:
        return self._k3

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")

        if action == "get_perspective":
            ptype = kwargs.get("ptype", "")
            data = kwargs.get("data", {})
            if not ptype:
                return json.dumps({"error": "ptype is required (bull/bear/buffet)"})
            result = self._k3.get_perspective(ptype, data)
            return json.dumps(result)

        if action == "update_accuracy":
            perspective = kwargs.get("perspective", "")
            predicted = kwargs.get("predicted_verdict", "")
            actual = kwargs.get("actual_outcome", "")
            if not perspective or not predicted or not actual:
                return json.dumps({"error": "perspective, predicted_verdict, actual_outcome required"})
            result = self._k3.update_accuracy(perspective, predicted, actual)
            return json.dumps(result, default=str)

        if action == "get_weights":
            result = self._k3.get_weights()
            return json.dumps(result)

        if action == "recalibrate":
            weights = self._k3.recalibrate_weights()
            return json.dumps({"weights": weights})

        if action == "calibrated_decision":
            data = kwargs.get("data", {})
            if not data:
                return json.dumps({"error": "data dict required with at least probability_below_target, current_price, target_price"})
            result = self._k3.calibrated_collapse(data)
            return json.dumps(result, default=str)

        if action == "accuracy_stats":
            result = self._k3.get_accuracy_stats()
            return json.dumps(result, default=str)

        return json.dumps({"error": f"Unknown action: {action}"})
