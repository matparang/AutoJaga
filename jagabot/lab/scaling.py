"""Auto-scaling worker pool for dynamic workloads.

v3.5: ScalableWorkerPool adjusts worker count based on queue depth.
Uses asyncio.Queue + persistent worker coroutines instead of
the fixed-semaphore approach in ParallelLab.

Key design choices:
  - ``async create()`` factory (cannot start tasks in sync ``__init__``)
  - Sentinel-based graceful shutdown (workers exit on ``None``)
  - Queue-depth scaling only (no psutil dependency)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ScalingConfig:
    """Configuration for auto-scaling behavior."""

    min_workers: int = 2
    max_workers: int = 32
    scale_up_threshold: int = 5
    scale_down_threshold: int = 2
    cooldown_period: float = 60.0  # seconds between scaling events
    scale_up_factor: float = 1.5
    scale_down_factor: float = 0.5
    monitor_interval: float = 5.0  # seconds between queue checks


@dataclass
class ScalingMetrics:
    """Runtime metrics for observability."""

    scale_up_events: int = 0
    scale_down_events: int = 0
    peak_workers: int = 0
    total_tasks_processed: int = 0
    total_tasks_failed: int = 0
    _history: list[dict[str, Any]] = field(default_factory=list, repr=False)

    def record_event(self, event_type: str, detail: dict[str, Any] | None = None) -> None:
        self._history.append({
            "type": event_type,
            "time": datetime.now(timezone.utc).isoformat(),
            **(detail or {}),
        })

    def to_dict(self) -> dict[str, Any]:
        return {
            "scale_up_events": self.scale_up_events,
            "scale_down_events": self.scale_down_events,
            "peak_workers": self.peak_workers,
            "total_tasks_processed": self.total_tasks_processed,
            "total_tasks_failed": self.total_tasks_failed,
        }


# Sentinel value — workers exit when they receive this.
_STOP = object()


class ScalableWorkerPool:
    """Worker pool that automatically scales based on queue depth.

    Use the async factory ``await ScalableWorkerPool.create(lab, config)``
    instead of ``__init__`` directly.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        # Intentionally bare — real init happens in create().
        self._lab: Any = None
        self.config = ScalingConfig()
        self.metrics = ScalingMetrics()
        self._queue: asyncio.Queue[Any] = asyncio.Queue()
        self._workers: list[asyncio.Task[None]] = []
        self._monitor_task: asyncio.Task[None] | None = None
        self._results: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._current_workers = 0
        self._last_scale_time = 0.0
        self._shutting_down = False
        self._task_counter = 0
        self._lock = asyncio.Lock()

    @classmethod
    async def create(
        cls,
        lab: Any | None = None,
        config: ScalingConfig | None = None,
    ) -> ScalableWorkerPool:
        """Async factory — creates pool and starts initial workers + monitor."""
        pool = cls()
        pool.config = config or ScalingConfig()

        if lab is None:
            from jagabot.lab.service import LabService
            lab = LabService()
        pool._lab = lab

        pool._current_workers = 0
        pool._last_scale_time = time.monotonic()
        pool.metrics.peak_workers = pool.config.min_workers

        # Start minimum workers
        pool._start_workers(pool.config.min_workers)

        # Start monitor loop
        pool._monitor_task = asyncio.create_task(pool._monitor_loop())

        return pool

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def submit_task(
        self,
        tool: str,
        params: dict[str, Any],
        *,
        priority: int = 5,
        sandbox: bool = False,
    ) -> str:
        """Submit a task and return its task_id."""
        self._task_counter += 1
        task_id = f"task_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{self._task_counter}"

        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._results[task_id] = future

        # Lower sort_key = higher priority (PriorityQueue semantics if we switch later).
        # For regular Queue we just put; priority is metadata.
        await self._queue.put({
            "id": task_id,
            "tool": tool,
            "params": params,
            "priority": priority,
            "sandbox": sandbox,
            "submitted": time.monotonic(),
        })

        return task_id

    async def get_result(
        self,
        task_id: str,
        *,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Wait for a task result."""
        future = self._results.get(task_id)
        if future is None:
            return {"success": False, "error": f"Unknown task: {task_id}"}
        return await asyncio.wait_for(asyncio.shield(future), timeout=timeout)

    async def submit_and_wait(
        self,
        tasks: list[dict[str, Any]],
        *,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Submit multiple tasks and wait for all results.

        Each task dict: ``{tool, params, priority?, sandbox?}``.
        Returns dict with batch metadata + per-task results.
        """
        wall_start = time.monotonic()

        task_ids: list[str] = []
        for t in tasks:
            tid = await self.submit_task(
                t["tool"],
                t["params"],
                priority=t.get("priority", 5),
                sandbox=t.get("sandbox", False),
            )
            task_ids.append(tid)

        results: list[dict[str, Any]] = []
        completed = failed = 0
        sum_individual = 0.0

        for tid in task_ids:
            try:
                r = await self.get_result(tid, timeout=timeout)
            except asyncio.TimeoutError:
                r = {"success": False, "error": "Timeout", "execution_time": 0}
            results.append(r)
            if r.get("success"):
                completed += 1
            else:
                failed += 1
            sum_individual += r.get("execution_time", 0)

        wall_time = round(time.monotonic() - wall_start, 3)
        speedup = round(sum_individual / wall_time, 2) if wall_time > 0 else 1.0

        return {
            "status": "complete" if failed == 0 else "partial",
            "total": len(results),
            "completed": completed,
            "failed": failed,
            "results": results,
            "wall_time": wall_time,
            "sum_individual_time": round(sum_individual, 3),
            "speedup_estimate": speedup,
            "workers_used": self._current_workers,
        }

    @property
    def current_workers(self) -> int:
        return self._current_workers

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    async def shutdown(self) -> None:
        """Gracefully stop all workers and the monitor."""
        self._shutting_down = True

        # Cancel monitor
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        # Send stop sentinels for all active workers
        for _ in range(self._current_workers):
            await self._queue.put(_STOP)

        # Wait for workers to finish
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        self._current_workers = 0

    # ------------------------------------------------------------------
    # Worker management
    # ------------------------------------------------------------------

    def _start_workers(self, count: int) -> None:
        """Spawn *count* new worker coroutines."""
        for _ in range(count):
            wid = len(self._workers)
            task = asyncio.create_task(self._worker_loop(wid))
            self._workers.append(task)
            self._current_workers += 1

        self.metrics.peak_workers = max(self.metrics.peak_workers, self._current_workers)

    async def _stop_workers(self, count: int) -> None:
        """Gracefully stop *count* workers via sentinel."""
        for _ in range(count):
            await self._queue.put(_STOP)
        # Workers will decrement _current_workers on exit.

    async def _worker_loop(self, worker_id: int) -> None:
        """Consume tasks from the queue until a stop sentinel arrives."""
        logger.debug("Worker %d started", worker_id)
        while not self._shutting_down:
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=10.0)
            except asyncio.TimeoutError:
                continue  # go back and check _shutting_down

            if item is _STOP:
                self._current_workers = max(0, self._current_workers - 1)
                logger.debug("Worker %d stopped (sentinel)", worker_id)
                return

            task_id = item["id"]
            future = self._results.get(task_id)

            try:
                result = await self._lab.execute(
                    item["tool"],
                    item["params"],
                    sandbox=item.get("sandbox", False),
                )
                self.metrics.total_tasks_processed += 1
                if not result.get("success"):
                    self.metrics.total_tasks_failed += 1
            except Exception as exc:
                result = {"success": False, "error": str(exc), "execution_time": 0}
                self.metrics.total_tasks_processed += 1
                self.metrics.total_tasks_failed += 1

            if future and not future.done():
                future.set_result(result)

            self._queue.task_done()

    # ------------------------------------------------------------------
    # Auto-scaling monitor
    # ------------------------------------------------------------------

    async def _monitor_loop(self) -> None:
        """Periodically evaluate whether to scale up/down."""
        while not self._shutting_down:
            try:
                await asyncio.sleep(self.config.monitor_interval)
                qsize = self._queue.qsize()
                async with self._lock:
                    await self._evaluate_scaling(qsize)
            except asyncio.CancelledError:
                return
            except Exception:
                logger.debug("Monitor error", exc_info=True)

    async def _evaluate_scaling(self, queue_size: int) -> None:
        """Decide whether to scale up or down based on queue depth."""
        now = time.monotonic()
        if (now - self._last_scale_time) < self.config.cooldown_period:
            return  # cooldown active

        cfg = self.config

        if queue_size > cfg.scale_up_threshold and self._current_workers < cfg.max_workers:
            new_count = min(
                int(self._current_workers * cfg.scale_up_factor),
                cfg.max_workers,
            )
            # Ensure we actually add at least 1 worker
            new_count = max(new_count, self._current_workers + 1)
            await self._scale_to(new_count)
            self.metrics.scale_up_events += 1
            self.metrics.record_event("scale_up", {
                "from": self._current_workers, "to": new_count, "queue": queue_size,
            })

        elif queue_size < cfg.scale_down_threshold and self._current_workers > cfg.min_workers:
            new_count = max(
                int(self._current_workers * cfg.scale_down_factor),
                cfg.min_workers,
            )
            await self._scale_to(new_count)
            self.metrics.scale_down_events += 1
            self.metrics.record_event("scale_down", {
                "from": self._current_workers, "to": new_count, "queue": queue_size,
            })

    async def _scale_to(self, target: int) -> None:
        """Adjust worker count to *target*."""
        if target == self._current_workers:
            return

        logger.info("Scaling workers: %d → %d", self._current_workers, target)

        if target > self._current_workers:
            self._start_workers(target - self._current_workers)
        else:
            await self._stop_workers(self._current_workers - target)

        self._last_scale_time = time.monotonic()
