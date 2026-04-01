"""EvolutionTool — Tool ABC wrapper for safe parameter self-evolution.

Actions:
  cycle    — run one evolution cycle (heartbeat)
  status   — engine status (fitness, mutations, sandbox)
  mutations — list recent mutations and outcomes
  force    — force a specific mutation (within safety bounds)
  cancel   — cancel active sandbox and rollback
  targets  — list mutation targets and current values
  fitness  — calculate current fitness score
"""

from __future__ import annotations

import json
from typing import Any

from jagabot.agent.tools.base import Tool
from jagabot.evolution.engine import EvolutionEngine


class EvolutionTool(Tool):
    name = "evolution"
    description = (
        "Safe self-evolution engine. Mutates financial parameters within "
        "±10% bounds, tests for 50 cycles, auto-rolls back on fitness loss. "
        "Actions: cycle, status, mutations, force, cancel, targets, fitness."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["cycle", "status", "mutations", "force", "cancel", "targets", "fitness"],
                "description": "Action to perform.",
            },
            "target": {
                "type": "string",
                "description": "Mutation target name (for force action).",
            },
            "factor": {
                "type": "number",
                "description": "Mutation factor 0.90–1.10 (for force action).",
            },
            "limit": {
                "type": "integer",
                "description": "Max mutations to list (default 20).",
            },
        },
        "required": ["action"],
    }

    def __init__(self, workspace: str | None = None, **kwargs: Any) -> None:
        if workspace:
            from pathlib import Path
            self._engine = EvolutionEngine(Path(workspace) / "evolution_state.json")
        else:
            self._engine = EvolutionEngine()

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")

        if action == "cycle":
            return json.dumps(self._engine.cycle())
        if action == "status":
            return json.dumps(self._engine.get_status())
        if action == "mutations":
            limit = kwargs.get("limit", 20)
            return json.dumps(self._engine.get_mutations(limit))
        if action == "force":
            return self._force(kwargs)
        if action == "cancel":
            return self._cancel()
        if action == "targets":
            return json.dumps(self._engine.get_targets())
        if action == "fitness":
            return json.dumps({"fitness": self._engine._calculate_fitness()})

        return json.dumps({"error": f"Unknown action: {action}"})

    def _force(self, kwargs: dict) -> str:
        target = kwargs.get("target")
        factor = kwargs.get("factor")
        if not target or factor is None:
            return json.dumps({"error": "target and factor required for force action"})
        result = self._engine.force_mutation(target, factor)
        if result is None:
            return json.dumps({"error": "Invalid target, factor out of bounds (0.90–1.10), or zero value"})
        return json.dumps(result)

    def _cancel(self) -> str:
        success = self._engine.cancel_sandbox()
        return json.dumps({"cancelled": success})
