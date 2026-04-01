"""
Push Notifier — async heartbeat updates for long-running background tasks.

The TUI dispatches agent calls as background asyncio tasks.  Between start
and completion the user sees nothing.  PushNotifier sends periodic heartbeat
messages so the terminal never appears frozen.

Usage::

    notifier = PushNotifier(output_callback=print, heartbeat_interval=10)
    notifier.start_task("t1", "Analysing portfolio")
    # ... agent works ...
    notifier.update_progress("t1", "Fetched 3 tickers")
    # ... agent finishes ...
    notifier.complete_task("t1", "Report saved to portfolio.md")
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable


@dataclass
class _TaskState:
    task_id: str
    description: str
    start_time: float = field(default_factory=time.time)
    last_update: float = field(default_factory=time.time)
    heartbeat_handle: asyncio.Task | None = None


class PushNotifier:
    """Async heartbeat notifier for TUI background tasks."""

    def __init__(
        self,
        output_callback: Callable[[str], None],
        heartbeat_interval: int = 10,
    ) -> None:
        self._output = output_callback
        self._interval = heartbeat_interval
        self._tasks: dict[str, _TaskState] = {}

    # ── Public API ───────────────────────────────────────────────

    def start_task(self, task_id: str, description: str) -> None:
        """Register a new task and begin heartbeat."""
        state = _TaskState(task_id=task_id, description=description)
        self._tasks[task_id] = state

        # Spawn heartbeat coroutine
        try:
            loop = asyncio.get_running_loop()
            state.heartbeat_handle = loop.create_task(
                self._heartbeat_loop(task_id)
            )
        except RuntimeError:
            # No running loop — skip heartbeat (e.g. during tests)
            pass

        self._push(f"  >> Started: {description}")

    def update_progress(self, task_id: str, message: str) -> None:
        """Manual progress update — resets heartbeat timer."""
        state = self._tasks.get(task_id)
        if state is None:
            return
        state.last_update = time.time()
        self._push(f"  .. [{self._elapsed(state)}] {message}")

    def complete_task(self, task_id: str, result: str | None = None) -> None:
        """Mark task complete and stop heartbeat."""
        state = self._tasks.pop(task_id, None)
        if state is None:
            return
        self._cancel_heartbeat(state)
        elapsed = self._elapsed(state)
        if result:
            self._push(f"  [OK] Complete ({elapsed}): {result[:200]}")
        else:
            self._push(f"  [OK] Complete ({elapsed})")

    def fail_task(self, task_id: str, error: str) -> None:
        """Mark task failed and stop heartbeat."""
        state = self._tasks.pop(task_id, None)
        if state is None:
            return
        self._cancel_heartbeat(state)
        self._push(f"  [FAIL] {state.description} ({self._elapsed(state)}): {error[:200]}")

    def stop_all(self) -> None:
        """Cancel all running heartbeats (e.g. on shutdown)."""
        for state in list(self._tasks.values()):
            self._cancel_heartbeat(state)
        self._tasks.clear()

    # ── Heartbeat coroutine ──────────────────────────────────────

    async def _heartbeat_loop(self, task_id: str) -> None:
        """Periodic heartbeat until the task completes or is cancelled."""
        try:
            while task_id in self._tasks:
                await asyncio.sleep(self._interval)
                state = self._tasks.get(task_id)
                if state is None:
                    break
                # Only fire if no manual update in the interval
                since_update = time.time() - state.last_update
                if since_update >= self._interval * 0.8:
                    self._push(
                        f"  .. [{self._elapsed(state)}] "
                        f"Still working on: {state.description}..."
                    )
                    state.last_update = time.time()
        except asyncio.CancelledError:
            pass

    # ── Internal ─────────────────────────────────────────────────

    @staticmethod
    def _cancel_heartbeat(state: _TaskState) -> None:
        if state.heartbeat_handle and not state.heartbeat_handle.done():
            state.heartbeat_handle.cancel()

    @staticmethod
    def _elapsed(state: _TaskState) -> str:
        e = time.time() - state.start_time
        if e < 60:
            return f"{e:.0f}s"
        return f"{int(e // 60)}m{int(e % 60):02d}s"

    def _push(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._output(f"[{ts}] {message}")
