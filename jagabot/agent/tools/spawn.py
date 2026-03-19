"""Spawn tool for creating background subagents."""

from typing import Any, TYPE_CHECKING

from jagabot.agent.tools.base import Tool

if TYPE_CHECKING:
    from jagabot.agent.subagent import SubagentManager


class SpawnTool(Tool):
    """
    Tool to spawn a subagent for background task execution.
    
    The subagent runs asynchronously and announces its result back
    to the main agent when complete.
    """
    
    def __init__(self, manager: "SubagentManager"):
        self._manager = manager
        self._origin_channel = "cli"
        self._origin_chat_id = "direct"
    
    def set_context(self, channel: str, chat_id: str) -> None:
        """Set the origin context for subagent announcements."""
        self._origin_channel = channel
        self._origin_chat_id = chat_id
    
    @property
    def name(self) -> str:
        return "spawn"
    
    @property
    def description(self) -> str:
        return (
            "Spawn a subagent to handle a task in the background. "
            "Use this for complex or time-consuming tasks that can run independently. "
            "The subagent will complete the task and report back when done."
        )
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The task for the subagent to complete",
                },
                "label": {
                    "type": "string",
                    "description": "Optional short label for the task (for display)",
                },
            },
            "required": ["task"],
        }
    
    async def execute(self, task: str, label: str | None = None, **kwargs: Any) -> str:
        """Spawn a subagent to execute the given task."""
        from jagabot.core.token_budget import budget

        # Estimate subagent cost — average ~3000 tokens per subagent run
        SUBAGENT_ESTIMATED_TOKENS = 3000

        # Check session budget
        remaining = budget.remaining()
        if remaining < SUBAGENT_ESTIMATED_TOKENS:
            return (
                f"⚠️ Cannot spawn subagent '{label or task[:30]}' — "
                f"session budget too low ({remaining:,} tokens remaining, "
                f"need ~{SUBAGENT_ESTIMATED_TOKENS:,}). "
                f"Start a new session to reset."
            )

        # Check daily budget
        daily_used  = budget._daily.get("total", 0)
        daily_left  = budget.daily_limit - daily_used
        if daily_left < SUBAGENT_ESTIMATED_TOKENS:
            return (
                f"⚠️ Cannot spawn subagent '{label or task[:30]}' — "
                f"daily budget exhausted ({daily_left:,} tokens remaining). "
                f"Budget resets tomorrow."
            )

        # Warn if running low but allow spawn
        if daily_left < SUBAGENT_ESTIMATED_TOKENS * 10:
            from loguru import logger
            logger.warning(
                f"Spawn: daily budget low ({daily_left:,} tokens left) — "
                f"spawning '{label or task[:30]}' but use sparingly"
            )

        return await self._manager.spawn(
            task=task,
            label=label,
            origin_channel=self._origin_channel,
            origin_chat_id=self._origin_chat_id,
        )
