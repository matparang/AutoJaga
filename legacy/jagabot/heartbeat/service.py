"""Heartbeat service - periodic agent wake-up to check for tasks."""

import asyncio
import time
from pathlib import Path
from typing import Any, Callable, Coroutine

from loguru import logger

# Default interval: 30 minutes
DEFAULT_HEARTBEAT_INTERVAL_S = 30 * 60

# Minimum seconds between heartbeat ticks (cooldown)
HEARTBEAT_COOLDOWN_S = 120

# Max iterations the agent is allowed during a heartbeat check
HEARTBEAT_MAX_ITERATIONS = 3

# The prompt sent to agent during heartbeat — deliberately constrained
HEARTBEAT_PROMPT = (
    "Read HEARTBEAT.md in your workspace. "
    "If there are unchecked tasks (- [ ]), do ONE task and check it off. "
    "If nothing needs attention, reply: HEARTBEAT_OK. "
    "Do NOT create new tasks or modify other files."
)

# Token that indicates "nothing to do"
HEARTBEAT_OK_TOKEN = "HEARTBEAT_OK"


def _is_heartbeat_empty(content: str | None) -> bool:
    """Check if HEARTBEAT.md has no actionable content."""
    if not content:
        return True
    
    # Only unchecked checkboxes count as actionable
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("- [ ]") or stripped.startswith("* [ ]"):
            return False
    
    return True


class HeartbeatService:
    """
    Periodic heartbeat service that wakes the agent to check for tasks.
    
    The agent reads HEARTBEAT.md from the workspace and executes any
    unchecked tasks listed there (one per tick). If nothing needs
    attention, it replies HEARTBEAT_OK.
    """
    
    def __init__(
        self,
        workspace: Path,
        on_heartbeat: Callable[[str], Coroutine[Any, Any, str]] | None = None,
        interval_s: int = DEFAULT_HEARTBEAT_INTERVAL_S,
        enabled: bool = True,
    ):
        self.workspace = workspace
        self.on_heartbeat = on_heartbeat
        self.interval_s = interval_s
        self.enabled = enabled
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_tick_ts: float = 0.0
    
    @property
    def heartbeat_file(self) -> Path:
        return self.workspace / "HEARTBEAT.md"
    
    def _read_heartbeat_file(self) -> str | None:
        """Read HEARTBEAT.md content."""
        if self.heartbeat_file.exists():
            try:
                return self.heartbeat_file.read_text()
            except Exception:
                return None
        return None
    
    async def start(self) -> None:
        """Start the heartbeat service."""
        if not self.enabled:
            logger.info("Heartbeat disabled")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Heartbeat started (every {self.interval_s}s)")
    
    def stop(self) -> None:
        """Stop the heartbeat service."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
    
    async def _run_loop(self) -> None:
        """Main heartbeat loop."""
        while self._running:
            try:
                await asyncio.sleep(self.interval_s)
                if self._running:
                    await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
    
    async def _tick(self) -> None:
        """Execute a single heartbeat tick."""
        # Cooldown guard — prevent rapid re-triggers
        now = time.time()
        if now - self._last_tick_ts < HEARTBEAT_COOLDOWN_S:
            logger.debug("Heartbeat: skipped (cooldown)")
            return
        self._last_tick_ts = now

        content = self._read_heartbeat_file()
        
        # Skip if HEARTBEAT.md has no unchecked tasks
        if _is_heartbeat_empty(content):
            logger.debug("Heartbeat: no tasks (HEARTBEAT.md empty)")
            return
        
        logger.info("Heartbeat: checking for tasks...")
        
        if self.on_heartbeat:
            try:
                response = await self.on_heartbeat(HEARTBEAT_PROMPT)
                
                # Check if agent said "nothing to do"
                if HEARTBEAT_OK_TOKEN.replace("_", "") in response.upper().replace("_", ""):
                    logger.info("Heartbeat: OK (no action needed)")
                else:
                    logger.info("Heartbeat: completed task")
                    
            except Exception as e:
                logger.error(f"Heartbeat execution failed: {e}")
    
    async def trigger_now(self) -> str | None:
        """Manually trigger a heartbeat."""
        if self.on_heartbeat:
            return await self.on_heartbeat(HEARTBEAT_PROMPT)
        return None
