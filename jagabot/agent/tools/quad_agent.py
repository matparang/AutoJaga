"""
Quad-Agent Verification Tool — LLM-callable tool for strategy-driven verified execution.

Exposes the QuadAgentLoop as a tool the main agent can invoke for complex
tasks that benefit from strategic planning, independent verification, and
adversarial robustness testing.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from jagabot.agent.tools.base import Tool

if TYPE_CHECKING:
    from jagabot.providers.base import LLMProvider


class QuadAgentTool(Tool):
    """Run a task through the Planner -> Worker -> Verifier -> Adversary loop."""

    def __init__(
        self,
        provider: "LLMProvider",
        workspace: Path,
        model: str | None = None,
        restrict_to_workspace: bool = True,
    ) -> None:
        self._provider = provider
        self._workspace = workspace
        self._model = model
        self._restrict = restrict_to_workspace

    @property
    def name(self) -> str:
        return "quad_agent"

    @property
    def description(self) -> str:
        return (
            "Execute a complex task using four cooperating agents: "
            "Planner (creates/adapts strategy), Worker (executes), "
            "Verifier (checks independently), Adversary (tests robustness). "
            "The Planner analyzes failures and adapts strategy each cycle. "
            "Each agent operates in an isolated sandbox. "
            "Use for high-stakes tasks requiring strategic planning, "
            "verification, and adversarial testing."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": (
                        "The task to execute with quad-agent verification. "
                        "Be specific about expected outputs and files."
                    ),
                },
                "max_cycles": {
                    "type": "integer",
                    "description": "Maximum planning/verification cycles (default: 3)",
                    "minimum": 1,
                    "maximum": 5,
                },
            },
            "required": ["task"],
        }

    async def execute(
        self,
        task: str,
        max_cycles: int = 3,
        **kwargs: Any,
    ) -> str:
        try:
            from jagabot.core.quad_loop import QuadAgentLoop

            loop = QuadAgentLoop(
                provider=self._provider,
                workspace=self._workspace,
                model=self._model,
                max_cycles=max_cycles,
                restrict_to_workspace=self._restrict,
            )
            result = await loop.run(task)
            return self._format_result(result)
        except Exception as e:
            return f"Error in quad-agent loop: {e}"

    @staticmethod
    def _format_result(result) -> str:
        lines = [
            f"QUAD-AGENT RESULT: {result.status}",
            f"Cycles: {result.cycles} | Time: {result.elapsed:.1f}s",
        ]

        if result.strategies:
            lines.append("")
            lines.append("--- Strategy Evolution ---")
            for i, strat in enumerate(result.strategies, 1):
                preview = strat[:200].replace("\n", " ")
                lines.append(f"Cycle {i}: {preview}")

        lines.extend(["", "--- Worker Output ---", result.result])

        if result.log:
            lines.append("")
            lines.append("--- Cycle Log ---")
            for clog in result.log:
                lines.append(f"Cycle {clog.cycle}:")
                lines.append(f"  Verification: {'PASS' if clog.verification_passed else 'FAIL'}")
                if clog.adversary_result:
                    lines.append(f"  Adversary: attacked")
                    lines.append(f"  Repair verified: {'PASS' if clog.repair_verified else 'FAIL'}")

        return "\n".join(lines)
