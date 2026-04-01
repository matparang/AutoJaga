"""Autonomous worker claiming — WORK/IDLE cycle with task scanning.

Adapted from learn-claude-code s11.  Workers autonomously scan the task
board for unclaimed ready tasks, atomically claim one, execute up to
``max_iterations`` actions, then idle until more work appears or timeout.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, Optional

from loguru import logger

from jagabot.core.task_manager import TaskManager


def scan_unclaimed_tasks(task_manager: TaskManager) -> list[dict[str, Any]]:
    """Return ready tasks that have no owner assigned."""
    return [
        t for t in task_manager.list_ready()
        if not t.get("owner")
    ]


def claim_task(
    task_manager: TaskManager,
    task_id: int,
    owner: str,
    lock: Optional[threading.Lock] = None,
) -> str:
    """Atomically claim a task for *owner*.  Returns status string.

    Uses the provided lock (or creates one) to prevent two workers
    from claiming the same task simultaneously.
    """
    _lock = lock or threading.Lock()
    with _lock:
        task = task_manager.get(task_id)
        if task["status"] != "pending":
            return f"Task #{task_id} is already {task['status']}"
        if task.get("owner") and task["owner"] != owner:
            return f"Task #{task_id} already claimed by {task['owner']}"
        task_manager.update(task_id, status="in_progress", owner=owner)
        return f"Task #{task_id} claimed by {owner}"


def make_identity_block(name: str, role: str, team: list[str]) -> dict[str, str]:
    """Generate an identity dict for re-injection after context compression.

    This ensures that even after aggressive micro-compact, the agent still
    knows who it is and what its role is.
    """
    return {
        "name": name,
        "role": role,
        "team": team,
        "reminder": f"You are {name}, a {role}. Your teammates are: {', '.join(team)}.",
    }


class AutonomousWorker:
    """WORK/IDLE cycle worker that self-claims tasks from a TaskManager.

    Args:
        name: Worker name / identity.
        role: Worker role description.
        task_manager: Shared TaskManager.
        handler: Called with ``(task_dict)`` when a task is claimed.
        max_iterations: Max actions per WORK phase before going IDLE.
        idle_poll_interval: Seconds between task board scans while IDLE.
        idle_timeout: Seconds of idle before auto-shutdown (0 = never).
    """

    def __init__(
        self,
        name: str,
        role: str,
        task_manager: TaskManager,
        handler: Optional[Callable[[dict[str, Any]], None]] = None,
        max_iterations: int = 50,
        idle_poll_interval: float = 5.0,
        idle_timeout: float = 60.0,
    ) -> None:
        self.name = name
        self.role = role
        self.task_manager = task_manager
        self.handler = handler
        self.max_iterations = max_iterations
        self.idle_poll_interval = idle_poll_interval
        self.idle_timeout = idle_timeout
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._claim_lock = threading.Lock()
        self.state: str = "idle"  # idle | working | stopped
        self.tasks_completed: int = 0

    def start(self) -> None:
        """Start the worker in a daemon thread."""
        self._running = True
        self.state = "idle"
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name=f"autonomous-{self.name}",
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the worker to stop."""
        self._running = False

    def is_alive(self) -> bool:
        """Check if the worker thread is running."""
        return self._thread is not None and self._thread.is_alive()

    def _run_loop(self) -> None:
        logger.info(f"AutonomousWorker [{self.name}] started ({self.role})")

        while self._running:
            # IDLE phase: scan for unclaimed tasks
            self.state = "idle"
            task = self._wait_for_task()
            if task is None:
                logger.info(f"[{self.name}] idle timeout — shutting down")
                break

            # WORK phase
            self.state = "working"
            logger.info(f"[{self.name}] working on #{task['id']}: {task['subject']}")
            iterations = 0

            try:
                if self.handler:
                    self.handler(task)
                self.task_manager.update(task["id"], status="completed")
                self.tasks_completed += 1
                logger.info(f"[{self.name}] completed #{task['id']}")
            except Exception as exc:
                logger.error(f"[{self.name}] failed #{task['id']}: {exc}")
                try:
                    self.task_manager.update(task["id"], status="failed")
                except Exception:
                    pass

        self.state = "stopped"
        self._running = False
        logger.info(f"AutonomousWorker [{self.name}] stopped (completed {self.tasks_completed} tasks)")

    def _wait_for_task(self) -> Optional[dict[str, Any]]:
        """Poll the task board until a task is found or timeout."""
        start = time.time()
        while self._running:
            unclaimed = scan_unclaimed_tasks(self.task_manager)
            for candidate in unclaimed:
                result = claim_task(
                    self.task_manager,
                    candidate["id"],
                    self.name,
                    self._claim_lock,
                )
                if "claimed by" in result:
                    return self.task_manager.get(candidate["id"])

            if self.idle_timeout > 0 and (time.time() - start) > self.idle_timeout:
                return None

            time.sleep(self.idle_poll_interval)

        return None
