"""Spawn tool for creating background subagents."""

import asyncio
from datetime import datetime
from pathlib import Path
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
        from loguru import logger

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
            logger.warning(
                f"Spawn: daily budget low ({daily_left:,} tokens left) — "
                f"spawning '{label or task[:30]}' but use sparingly"
            )

        # Retry logic with exponential backoff (FIX 4)
        MAX_RETRIES    = 3
        RETRY_DELAYS   = [1, 2, 4]  # exponential backoff seconds
        last_error     = None

        for attempt, delay in enumerate(RETRY_DELAYS, 1):
            try:
                result = await self._manager.spawn(
                    task=task,
                    label=label,
                    origin_channel=self._origin_channel,
                    origin_chat_id=self._origin_chat_id,
                )
                if attempt > 1:
                    logger.info(
                        f"SpawnTool: succeeded on attempt {attempt}"
                    )
                return result

            except Exception as e:
                last_error = e
                logger.warning(
                    f"SpawnTool: attempt {attempt}/{MAX_RETRIES} failed: {e}"
                )
                # Log to HISTORY.md
                self._log_spawn_error(task, attempt, str(e))

                if attempt < MAX_RETRIES:
                    logger.info(
                        f"SpawnTool: retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)

        # All retries exhausted
        logger.error(
            f"SpawnTool: all {MAX_RETRIES} attempts failed for task: {task[:60]}"
        )
        return (
            f"Subagent spawn failed after {MAX_RETRIES} attempts. "
            f"Last error: {last_error}. "
            f"Task logged to HISTORY.md for manual retry."
        )

    def _log_spawn_error(
        self, task: str, attempt: int, error: str
    ) -> None:
        """Log spawn error to HISTORY.md for tracking."""
        try:
            history = Path(
                "/root/.jagabot/workspace/memory/HISTORY.md"
            )
            entry = (
                f"\n{datetime.now().strftime('%Y-%m-%d %H:%M')} | "
                f"SPAWN_ERROR | attempt={attempt} | "
                f"task={task[:60]} | error={error[:100]}\n"
            )
            with open(history, "a") as f:
                f.write(entry)
        except Exception:
            pass  # Silently ignore logging failures
