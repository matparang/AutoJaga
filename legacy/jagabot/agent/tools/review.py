"""ReviewTool — Tool ABC wrapper for the two-stage review system.

Actions:
  review        — run full two-stage review (spec + quality)
  spec_check    — run stage 1 only (spec compliance)
  quality_check — run stage 2 only (quality scoring)
"""

from __future__ import annotations

import json
from typing import Any

from jagabot.agent.tools.base import Tool
from jagabot.skills.review import TwoStageReview


class ReviewTool(Tool):
    name = "review"
    description = (
        "Two-stage review gate for financial analysis outputs. "
        "Stage 1: spec compliance (required fields). "
        "Stage 2: quality scoring (threshold 0.7). "
        "Both must pass for approval."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["review", "spec_check", "quality_check"],
                "description": "Action to perform.",
            },
            "task": {
                "type": "object",
                "description": "Task definition with 'type' and optional 'expected' fields.",
            },
            "output": {
                "type": "object",
                "description": "The output to review.",
            },
        },
        "required": ["action", "task", "output"],
    }

    def __init__(self, evaluation_kernel: Any | None = None) -> None:
        self._review = TwoStageReview(evaluation_kernel=evaluation_kernel)

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")
        task = kwargs.get("task", {})
        output = kwargs.get("output", {})

        if not task or not output:
            return json.dumps({"error": "task and output are required"})

        if action == "review":
            result = self._review.review(task, output)
            return json.dumps(result)

        if action == "spec_check":
            result = self._review.stage1_spec(task, output)
            return json.dumps(result)

        if action == "quality_check":
            result = self._review.stage2_quality(task, output)
            return json.dumps(result)

        return json.dumps({"error": f"Unknown action: {action}"})
