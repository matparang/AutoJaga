"""Worker status tracker — real-time visibility into swarm workers."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class WorkerState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    STALLED = "stalled"


@dataclass
class WorkerInfo:
    """Snapshot of a single worker's status."""
    task_id: str
    tool_name: str
    method: str = ""
    state: WorkerState = WorkerState.IDLE
    started_at: float = 0.0
    finished_at: float = 0.0
    elapsed_s: float = 0.0
    error: str | None = None


class WorkerTracker:
    """Thread-safe tracker for swarm worker status.

    Tracks active workers, detects stalled tasks, and provides
    aggregate statistics for the Mission Control dashboard.
    """

    def __init__(self, stall_timeout: float = 60.0):
        self._workers: dict[str, WorkerInfo] = {}
        self._lock = threading.Lock()
        self._stall_timeout = stall_timeout
        self._history: list[WorkerInfo] = []
        self._max_history = 200

    def register(self, task_id: str, tool_name: str, method: str = "") -> None:
        """Register a new task as running."""
        info = WorkerInfo(
            task_id=task_id,
            tool_name=tool_name,
            method=method,
            state=WorkerState.RUNNING,
            started_at=time.monotonic(),
        )
        with self._lock:
            self._workers[task_id] = info

    def heartbeat(self, task_id: str) -> None:
        """Update the timestamp of an active worker (keeps it from appearing stalled)."""
        with self._lock:
            if task_id in self._workers:
                self._workers[task_id].started_at = time.monotonic()

    def mark_done(self, task_id: str, success: bool = True, error: str | None = None) -> None:
        """Mark a task as completed."""
        with self._lock:
            if task_id not in self._workers:
                return
            w = self._workers[task_id]
            w.state = WorkerState.DONE if success else WorkerState.ERROR
            w.finished_at = time.monotonic()
            w.elapsed_s = round(w.finished_at - w.started_at, 3)
            w.error = error
            self._history.append(w)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
            del self._workers[task_id]

    def detect_stalled(self) -> list[WorkerInfo]:
        """Return workers that have exceeded the stall timeout."""
        now = time.monotonic()
        stalled = []
        with self._lock:
            for w in self._workers.values():
                if w.state == WorkerState.RUNNING and (now - w.started_at) > self._stall_timeout:
                    w.state = WorkerState.STALLED
                    stalled.append(w)
        return stalled

    def active_workers(self) -> list[WorkerInfo]:
        """Return list of currently running workers."""
        with self._lock:
            return [w for w in self._workers.values() if w.state in (WorkerState.RUNNING, WorkerState.STALLED)]

    def recent_history(self, limit: int = 20) -> list[WorkerInfo]:
        """Return recent completed worker history."""
        with self._lock:
            return list(reversed(self._history[-limit:]))

    def stats(self) -> dict[str, Any]:
        """Aggregate statistics for the dashboard."""
        with self._lock:
            active = [w for w in self._workers.values()]
            running = sum(1 for w in active if w.state == WorkerState.RUNNING)
            stalled = sum(1 for w in active if w.state == WorkerState.STALLED)
            done_count = len(self._history)
            errors = sum(1 for w in self._history if w.state == WorkerState.ERROR)
            avg_time = (
                round(sum(w.elapsed_s for w in self._history) / done_count, 3)
                if done_count else 0.0
            )
            tools_used = set(w.tool_name for w in self._history)

        return {
            "running": running,
            "stalled": stalled,
            "completed": done_count,
            "errors": errors,
            "avg_elapsed_s": avg_time,
            "tools_used": sorted(tools_used),
        }

    def clear(self) -> None:
        """Reset all tracking state."""
        with self._lock:
            self._workers.clear()
            self._history.clear()
