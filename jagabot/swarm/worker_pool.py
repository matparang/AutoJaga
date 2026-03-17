"""Worker pool — manages parallel tool execution via ProcessPoolExecutor."""

from __future__ import annotations

import json
import os
import uuid
from concurrent.futures import Future, ProcessPoolExecutor, TimeoutError as FuturesTimeout
from dataclasses import dataclass, field
from typing import Any

from jagabot.swarm.base_worker import _run_tool_sync


@dataclass
class TaskSpec:
    """A single task to be executed by a worker."""
    tool_name: str
    method: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    timeout: float = 30.0
    group: int = 0  # tasks in the same group run in parallel


@dataclass
class TaskResult:
    """Result of a completed task."""
    task_id: str
    tool_name: str
    method: str
    data: dict[str, Any] | str
    success: bool
    elapsed_s: float = 0.0


class WorkerPool:
    """Process pool for parallel tool execution.

    Uses ProcessPoolExecutor to run tools in separate processes,
    bypassing the GIL for CPU-bound work (Monte Carlo, statistics).
    """

    def __init__(self, max_workers: int | None = None, tracker: Any | None = None):
        if max_workers is None:
            max_workers = min(os.cpu_count() or 4, 8)
        self.max_workers = max_workers
        self._executor: ProcessPoolExecutor | None = None
        self._tracker = tracker  # Optional WorkerTracker

    def _get_executor(self) -> ProcessPoolExecutor:
        if self._executor is None or self._executor._broken:
            self._executor = ProcessPoolExecutor(max_workers=self.max_workers)
        return self._executor

    def submit(self, task: TaskSpec) -> Future:
        """Submit a single task, returning a Future."""
        executor = self._get_executor()
        if self._tracker:
            self._tracker.register(task.task_id, task.tool_name, task.method)
        return executor.submit(_run_tool_sync, task.tool_name, task.method, task.params)

    def submit_batch(self, tasks: list[TaskSpec]) -> dict[str, Future]:
        """Submit multiple tasks in parallel. Returns {task_id: Future}."""
        futures = {}
        for task in tasks:
            futures[task.task_id] = self.submit(task)
        return futures

    def collect(
        self,
        futures: dict[str, Future],
        tasks: list[TaskSpec],
        default_timeout: float = 30.0,
    ) -> list[TaskResult]:
        """Collect results from submitted futures."""
        import time

        task_map = {t.task_id: t for t in tasks}
        results = []

        for task_id, future in futures.items():
            task = task_map.get(task_id)
            timeout = task.timeout if task else default_timeout
            tool_name = task.tool_name if task else "unknown"
            method = task.method if task else ""

            start = time.monotonic()
            try:
                raw = future.result(timeout=timeout)
                elapsed = time.monotonic() - start
                try:
                    data = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    data = raw
                success = not (isinstance(data, dict) and "error" in data)
                results.append(TaskResult(
                    task_id=task_id, tool_name=tool_name, method=method,
                    data=data, success=success, elapsed_s=round(elapsed, 3),
                ))
                if self._tracker:
                    self._tracker.mark_done(task_id, success=success)
            except FuturesTimeout:
                elapsed = time.monotonic() - start
                results.append(TaskResult(
                    task_id=task_id, tool_name=tool_name, method=method,
                    data={"error": "timeout", "timeout_s": timeout},
                    success=False, elapsed_s=round(elapsed, 3),
                ))
                if self._tracker:
                    self._tracker.mark_done(task_id, success=False, error="timeout")
            except Exception as exc:
                elapsed = time.monotonic() - start
                results.append(TaskResult(
                    task_id=task_id, tool_name=tool_name, method=method,
                    data={"error": str(exc)},
                    success=False, elapsed_s=round(elapsed, 3),
                ))
                if self._tracker:
                    self._tracker.mark_done(task_id, success=False, error=str(exc))
        return results

    def run_task_groups(
        self, groups: list[list[TaskSpec]], prior_results: dict[str, Any] | None = None,
    ) -> list[TaskResult]:
        """Execute task groups sequentially; tasks within a group run in parallel.

        ``groups[0]`` runs first (all in parallel), then ``groups[1]`` (which may
        reference results from group 0), etc.
        """
        all_results: list[TaskResult] = []
        results_by_name: dict[str, Any] = dict(prior_results or {})

        for group in groups:
            if not group:
                continue
            futures = self.submit_batch(group)
            group_results = self.collect(futures, group)
            all_results.extend(group_results)
            for r in group_results:
                if r.success:
                    results_by_name[r.tool_name] = r.data
        return all_results

    def shutdown(self, wait: bool = True) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=wait)
            self._executor = None
