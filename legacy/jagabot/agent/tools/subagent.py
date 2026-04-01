"""SubagentTool — Tool ABC wrapper for the 4-stage subagent pipeline.

Actions:
  run_workflow    — execute full WebSearch → Tools → Models → Reasoning pipeline
  run_stage       — execute a single named stage with provided data
  list_stages     — show available stages, their tools, and execution order
  get_stage_prompt — retrieve the instruction prompt for a stage
"""

from __future__ import annotations

import json
from typing import Any

from jagabot.agent.tools.base import Tool
from jagabot.subagents.manager import SubagentManager


class SubagentTool(Tool):
    name = "subagent"
    description = (
        "4-stage stateless analysis pipeline. "
        "Stages: websearch → tools → models → reasoning. "
        "Each stage runs existing jagabot tools and passes structured output downstream."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["run_workflow", "run_stage", "list_stages", "get_stage_prompt"],
                "description": "Action to perform.",
            },
            "query": {
                "type": "string",
                "description": "Analysis query (for run_workflow).",
            },
            "stage": {
                "type": "string",
                "enum": ["websearch", "tools", "models", "reasoning"],
                "description": "Stage name (for run_stage / get_stage_prompt).",
            },
            "data": {
                "type": "object",
                "description": "Input data dict for run_workflow or run_stage.",
            },
        },
        "required": ["action"],
    }

    def __init__(self, **kwargs: Any) -> None:
        self._manager = SubagentManager()

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")

        if action == "run_workflow":
            return await self._run_workflow(kwargs)
        if action == "run_stage":
            return await self._run_stage(kwargs)
        if action == "list_stages":
            return self._list_stages()
        if action == "get_stage_prompt":
            return self._get_stage_prompt(kwargs)

        return json.dumps({"error": f"Unknown action: {action}"})

    # ------------------------------------------------------------------

    async def _run_workflow(self, kwargs: dict) -> str:
        query = kwargs.get("query", "")
        data = kwargs.get("data") or {}
        result = await self._manager.execute_workflow(query=query, data=data)
        return json.dumps(result, default=str)

    async def _run_stage(self, kwargs: dict) -> str:
        stage_name = kwargs.get("stage")
        if not stage_name:
            return json.dumps({"error": "stage is required for run_stage"})
        data = kwargs.get("data") or {}
        result = await self._manager.execute_stage(stage_name, data)
        return json.dumps(result, default=str)

    def _list_stages(self) -> str:
        return json.dumps(self._manager.get_stages())

    def _get_stage_prompt(self, kwargs: dict) -> str:
        stage_name = kwargs.get("stage")
        if not stage_name:
            return json.dumps({"error": "stage is required for get_stage_prompt"})
        prompt = self._manager.get_prompt(stage_name)
        if prompt is None:
            return json.dumps({"error": f"Unknown stage: {stage_name}"})
        return json.dumps({"stage": stage_name, "prompt": prompt})
