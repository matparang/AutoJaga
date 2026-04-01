"""CodeActTool — run a CodeAct agent for complex multi-step tasks.

Wraps quantalogic_codeact's CodeActAgent so jagabot's main agent can
delegate complex tasks that benefit from iterative code execution.
"""

from __future__ import annotations

import json
import os
from typing import Any

from jagabot.agent.tools.base import Tool

# Try to import CodeActAgent at module level for easy patching in tests
try:
    from quantalogic_codeact.codeact.codeact_agent import CodeActAgent
    _CODEACT_AVAILABLE = True
except ImportError:
    CodeActAgent = None  # type: ignore[assignment,misc]
    _CODEACT_AVAILABLE = False


def _check_codeact() -> bool:
    return _CODEACT_AVAILABLE
    return _CODEACT_AVAILABLE


class CodeActTool(Tool):
    """Delegate a complex task to a CodeAct sub-agent that can write and execute Python code.

    The CodeAct agent uses an LLM to iteratively write Python snippets,
    execute them in a sandbox, observe results, and refine until the task
    is solved. Useful for data analysis, calculation pipelines, or any
    task requiring multiple code-execution steps.

    Actions
    -------
    run    — run a task with the CodeAct agent
    status — check if CodeAct is available
    """

    @property
    def name(self) -> str:
        return "codeact"

    @property
    def description(self) -> str:
        return (
            "Run a complex multi-step task via a CodeAct sub-agent that writes and executes "
            "Python code iteratively. Actions: run (execute a task), status (check availability)."
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
                "task": {
                    "type": "string",
                    "description": "Natural-language task description for the CodeAct agent (required for action=run)",
                },
                "model": {
                    "type": "string",
                    "description": "LLM model identifier (default: from CODEACT_MODEL env or claude-3-5-haiku-20241022)",
                },
                "max_iterations": {
                    "type": "integer",
                    "description": "Maximum reasoning iterations (default: 5)",
                },
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "status")

        if action == "status":
            available = _check_codeact()
            return json.dumps({
                "available": available,
                "message": "CodeAct ready" if available else "quantalogic_codeact not installed",
            })

        if action == "run":
            return await self._run(kwargs)

        return f"Unknown action: {action!r}. Use: run, status"

    async def _run(self, kwargs: dict) -> str:
        task = kwargs.get("task", "").strip()
        if not task:
            return "Error: 'task' is required for action=run"

        if not _check_codeact():
            return "Error: quantalogic_codeact not available. Install it from the local repo."

        model = kwargs.get("model") or os.environ.get("CODEACT_MODEL", "claude-3-5-haiku-20241022")
        max_iterations = int(kwargs.get("max_iterations") or 5)

        try:
            agent = CodeActAgent(
                model=model,
                tools=[],  # No extra tools — pure code execution via sandbox
                max_iterations=max_iterations,
            )

            messages = await agent.solve(task)
            # solve() returns List[Dict] of conversation messages — extract final assistant content
            if not messages:
                return "(CodeAct returned no messages)"
            # Find the last assistant message
            for msg in reversed(messages):
                if isinstance(msg, dict) and msg.get("role") == "assistant":
                    content = msg.get("content", "")
                    if isinstance(content, str):
                        return content
                    return json.dumps(content, ensure_ascii=False, default=str)
            return json.dumps(messages[-1], ensure_ascii=False, default=str)

        except Exception as exc:
            return f"CodeAct error: {exc}"
