"""FlowTool — run YAML/JSON workflows via QuantaLogic Flow engine.

Allows the agent to execute pre-defined QuantaLogic workflow definitions
(YAML or JSON) with variable context injection.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from jagabot.agent.tools.base import Tool

# Try to import at module level for easy patching in tests
try:
    from quantalogic_flow.flow.flow_manager import WorkflowManager
    from quantalogic_flow.flow.flow_manager_schema import WorkflowDefinition
    _FLOW_AVAILABLE = True
except ImportError:
    WorkflowManager = None  # type: ignore[assignment,misc]
    WorkflowDefinition = None  # type: ignore[assignment,misc]
    _FLOW_AVAILABLE = False


def _check_flow() -> bool:
    return _FLOW_AVAILABLE


class FlowTool(Tool):
    """Execute QuantaLogic Flow YAML/JSON workflows.

    Actions
    -------
    run     — run a workflow from a JSON definition or file path
    status  — check if quantalogic_flow is available
    """

    @property
    def name(self) -> str:
        return "flow"

    @property
    def description(self) -> str:
        return (
            "Execute QuantaLogic Flow YAML/JSON workflows. "
            "Actions: run (execute a workflow file or JSON), status (check availability)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["run", "status"],
                    "description": "Action to perform",
                },
                "workflow_path": {
                    "type": "string",
                    "description": "Path to a workflow JSON file (for action=run)",
                },
                "workflow_json": {
                    "type": "string",
                    "description": "Inline JSON string of a WorkflowDefinition (for action=run, alternative to workflow_path)",
                },
                "context": {
                    "type": "object",
                    "description": "Initial context variables passed to the workflow (optional)",
                },
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "status")

        if action == "status":
            available = _check_flow()
            return json.dumps({
                "available": available,
                "message": "QuantaLogic Flow ready" if available else "quantalogic_flow not installed",
            })

        if action == "run":
            return await self._run(kwargs)

        return f"Unknown action: {action!r}. Use: run, status"

    async def _run(self, kwargs: dict) -> str:
        if not _check_flow():
            return "Error: quantalogic_flow not available. Install it from the local repo."

        workflow_path = kwargs.get("workflow_path", "")
        workflow_json = kwargs.get("workflow_json", "")
        context: dict = kwargs.get("context") or {}

        if not workflow_path and not workflow_json:
            return "Error: provide 'workflow_path' (file path) or 'workflow_json' (inline JSON)"

        try:
            # Load workflow definition
            if workflow_path:
                path = Path(workflow_path)
                if not path.exists():
                    return f"Error: workflow file not found: {workflow_path}"
                manager = WorkflowManager()
                workflow_def = manager.import_workflow_json(path)
            else:
                # Parse inline JSON
                data = json.loads(workflow_json)
                workflow_def = WorkflowDefinition.model_validate(data)

            # Execute synchronously (WorkflowManager.execute_workflow is sync)
            import asyncio
            manager = WorkflowManager()
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: manager.execute_workflow(workflow_def, context)
            )

            if result is None:
                return "(Flow returned no result)"
            if isinstance(result, str):
                return result
            return json.dumps(result, ensure_ascii=False, default=str)

        except json.JSONDecodeError as exc:
            return f"Error: invalid workflow JSON — {exc}"
        except Exception as exc:
            return f"Flow error: {exc}"
