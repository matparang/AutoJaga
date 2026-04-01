"""
YOLO Mode Tool — Agent-callable autonomous research.

Unlike the CLI command, this tool allows the agent
to invoke YOLO mode from within a conversation.

Usage from agent:
    yolo_mode({"goal": "research quantum computing"})

The agent can call this when it determines
autonomous execution is appropriate.
"""

from jagabot.agent.tools.base import Tool
from jagabot.agent.yolo import YOLORunner, ALLOWED_WORKSPACE
from pathlib import Path
from typing import Any


class YoloModeTool(Tool):
    """Invoke YOLO mode for autonomous research execution."""

    @property
    def name(self) -> str:
        return "yolo_mode"

    @property
    def description(self) -> str:
        return (
            "Execute research autonomously without step-by-step confirmation. "
            "Use when the user wants fast results and trusts the agent to "
            "decompose and execute the full research pipeline. "
            "Sandboxed to ~/.jagabot/workspace/ only. "
            "Every action audited. Returns final report path and summary."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": (
                        "Research goal e.g. 'research quantum computing in "
                        "drug discovery' or 'generate 5 unconventional ideas "
                        "for hospital readmission reduction'"
                    ),
                },
            },
            "required": ["goal"],
        }

    async def execute(
        self,
        goal: str,
        **kwargs: Any,
    ) -> str:
        """Execute YOLO mode research autonomously."""
        try:
            runner = YOLORunner(
                workspace=ALLOWED_WORKSPACE,
                tool_registry=None,  # Will use internal agent
                agent=None,  # Will initialize internally
            )
            
            session = runner.run(goal)
            
            # Format result for agent
            steps_completed = len([
                s for s in session.steps if s.status == "done"
            ])
            total_steps = len(session.steps)
            
            result_lines = [
                f"✅ YOLO research complete: {goal[:60]}",
                "",
                f"**Steps:** {steps_completed}/{total_steps} succeeded",
                f"**Time:** {session.total_elapsed:.0f}s",
                f"**Report:** {session.report_path or 'N/A'}",
                f"**Memory:** {session.memory_added} facts added",
                f"**Pending:** {session.pending_added} conclusions logged",
                "",
                "**Step Summary:**",
            ]
            
            for step in session.steps:
                icon = "✅" if step.status == "done" else "✗"
                result_lines.append(
                    f"  {icon} Step {step.step_num}: {step.summary}"
                )
            
            return "\n".join(result_lines)
            
        except Exception as e:
            return f"❌ YOLO mode failed: {e}"
