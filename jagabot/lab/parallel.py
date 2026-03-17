"""ParallelLab — batch submission, priority-sorted concurrent tool execution.

Wraps LabService with:
  - Batch management (submit → execute → track by batch_id)
  - Priority sorting (higher priority tasks run first)
  - Concurrency limiting via asyncio.Semaphore
  - Partial failure handling (per-task error collection)
  - Predefined workflow presets (risk_analysis, portfolio_review, full_analysis)
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class ParallelLab:
    """Batch-oriented parallel tool execution on top of LabService.

    With ``auto_scale=True`` the pool dynamically adjusts worker count
    based on queue depth (v3.5).  Default (``False``) uses the original
    fixed-semaphore ``asyncio.gather`` approach for backward compatibility.
    """

    def __init__(
        self,
        lab: Any | None = None,
        max_concurrent: int = 4,
        *,
        auto_scale: bool = False,
        scaling_config: Any | None = None,
    ) -> None:
        if lab is None:
            from jagabot.lab.service import LabService
            lab = LabService()
        self.lab = lab
        self.max_concurrent = max_concurrent
        self._batches: dict[str, dict[str, Any]] = {}
        self._auto_scale = auto_scale
        self._scaling_config = scaling_config
        self._pool: Any | None = None  # ScalableWorkerPool, created lazily

    # ------------------------------------------------------------------
    # Batch submission
    # ------------------------------------------------------------------

    def submit_batch(
        self,
        tasks: list[dict[str, Any]],
        *,
        priority_sort: bool = True,
    ) -> str:
        """Register a batch of tasks and return a batch_id.

        Each task dict must have ``tool`` (str) and ``params`` (dict).
        Optional ``priority`` (int, 1-10, higher = sooner) and
        ``sandbox`` (bool).
        """
        batch_id = f"batch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"

        sorted_tasks = list(tasks)
        if priority_sort:
            sorted_tasks.sort(key=lambda t: t.get("priority", 5), reverse=True)

        self._batches[batch_id] = {
            "batch_id": batch_id,
            "tasks": sorted_tasks,
            "status": "pending",
            "submitted": datetime.now(timezone.utc).isoformat(),
            "completed": 0,
            "failed": 0,
            "results": [],
            "wall_time": None,
        }
        return batch_id

    # ------------------------------------------------------------------
    # Batch execution
    # ------------------------------------------------------------------

    async def execute_batch(
        self,
        batch_id: str,
        *,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Execute all tasks in a batch concurrently.

        Returns standardised result dict with per-task results and metadata.
        """
        batch = self._batches.get(batch_id)
        if batch is None:
            return {"error": f"Batch {batch_id} not found"}

        batch["status"] = "running"
        sem = asyncio.Semaphore(self.max_concurrent)
        wall_start = time.monotonic()

        async def _run(task: dict) -> dict[str, Any]:
            async with sem:
                try:
                    result = await self.lab.execute(
                        task["tool"],
                        task["params"],
                        sandbox=task.get("sandbox", False),
                        timeout=timeout,
                    )
                    return {"task": task, **result}
                except Exception as exc:
                    return {
                        "task": task,
                        "success": False,
                        "error": str(exc),
                        "execution_time": 0,
                    }

        raw_results = await asyncio.gather(
            *[_run(t) for t in batch["tasks"]],
            return_exceptions=False,
        )

        wall_time = round(time.monotonic() - wall_start, 3)

        # Tally
        results: list[dict] = []
        completed = failed = 0
        sum_individual = 0.0
        for r in raw_results:
            ok = r.get("success", False)
            if ok:
                completed += 1
            else:
                failed += 1
            sum_individual += r.get("execution_time", 0)
            results.append(r)

        speedup = round(sum_individual / wall_time, 2) if wall_time > 0 else 1.0

        batch.update({
            "status": "complete" if failed == 0 else "partial",
            "completed": completed,
            "failed": failed,
            "results": results,
            "wall_time": wall_time,
        })

        return {
            "batch_id": batch_id,
            "status": batch["status"],
            "total": len(results),
            "completed": completed,
            "failed": failed,
            "results": results,
            "wall_time": wall_time,
            "sum_individual_time": round(sum_individual, 3),
            "speedup_estimate": speedup,
        }

    async def submit_and_execute(
        self,
        tasks: list[dict[str, Any]],
        *,
        timeout: int = 30,
        priority_sort: bool = True,
    ) -> dict[str, Any]:
        """Convenience: submit + execute in one call."""
        batch_id = self.submit_batch(tasks, priority_sort=priority_sort)
        return await self.execute_batch(batch_id, timeout=timeout)

    # ------------------------------------------------------------------
    # Workflow presets
    # ------------------------------------------------------------------

    _WORKFLOWS: dict[str, list[dict[str, Any]]] = {
        "risk_analysis": [
            {"tool": "monte_carlo", "key": "mc_params", "priority": 10},
            {"tool": "var", "key": "var_params", "method": "parametric_var", "priority": 8},
            {"tool": "stress_test", "key": "stress_params", "method": "position_stress", "priority": 7},
        ],
        "portfolio_review": [
            {"tool": "portfolio_analyzer", "key": "portfolio_params", "priority": 10},
            {"tool": "correlation", "key": "correlation_params", "method": "calculate", "priority": 8},
            {"tool": "recovery_time", "key": "recovery_params", "priority": 7},
        ],
        "full_analysis": [
            {"tool": "monte_carlo", "key": "mc_params", "priority": 10},
            {"tool": "var", "key": "var_params", "method": "parametric_var", "priority": 9},
            {"tool": "cvar", "key": "cvar_params", "method": "calculate_cvar", "priority": 8},
            {"tool": "stress_test", "key": "stress_params", "method": "position_stress", "priority": 8},
            {"tool": "correlation", "key": "correlation_params", "method": "calculate", "priority": 6},
            {"tool": "recovery_time", "key": "recovery_params", "priority": 5},
            {"tool": "financial_cv", "key": "cv_params", "method": "calculate_cv", "priority": 5},
            {"tool": "decision_engine", "key": "decision_params", "method": "collapse_perspectives", "priority": 4},
        ],
    }

    async def execute_workflow(
        self,
        workflow_name: str,
        data: dict[str, Any],
        *,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Execute a predefined workflow.

        Available workflows: risk_analysis, portfolio_review, full_analysis.
        ``data`` keys should match the workflow's ``key`` fields (e.g. ``mc_params``).
        """
        spec = self._WORKFLOWS.get(workflow_name)
        if spec is None:
            return {"error": f"Unknown workflow: {workflow_name}. Available: {list(self._WORKFLOWS)}"}

        tasks: list[dict[str, Any]] = []
        for entry in spec:
            raw_params = data.get(entry["key"], {})
            method = entry.get("method")
            if method:
                params = {"method": method, "params": raw_params}
            else:
                params = raw_params
            tasks.append({
                "tool": entry["tool"],
                "params": params,
                "priority": entry.get("priority", 5),
            })

        return await self.submit_and_execute(tasks, timeout=timeout)

    @classmethod
    def available_workflows(cls) -> list[str]:
        """Return names of all predefined workflows."""
        return list(cls._WORKFLOWS.keys())

    # ------------------------------------------------------------------
    # Batch tracking
    # ------------------------------------------------------------------

    def get_batch_status(self, batch_id: str) -> dict[str, Any]:
        """Return current status of a batch."""
        batch = self._batches.get(batch_id)
        if batch is None:
            return {"error": f"Batch {batch_id} not found"}
        return {
            "batch_id": batch_id,
            "status": batch["status"],
            "total": len(batch["tasks"]),
            "completed": batch["completed"],
            "failed": batch["failed"],
            "wall_time": batch["wall_time"],
        }

    def list_batches(self) -> list[dict[str, Any]]:
        """Return metadata for all tracked batches."""
        return [
            {
                "batch_id": b["batch_id"],
                "status": b["status"],
                "total": len(b["tasks"]),
                "completed": b["completed"],
                "failed": b["failed"],
                "submitted": b["submitted"],
            }
            for b in self._batches.values()
        ]

    # ------------------------------------------------------------------
    # Auto-scaling pool (v3.5)
    # ------------------------------------------------------------------

    async def _ensure_pool(self) -> Any:
        """Lazily create the ScalableWorkerPool on first use."""
        if self._pool is None:
            from jagabot.lab.scaling import ScalableWorkerPool, ScalingConfig

            config = self._scaling_config or ScalingConfig()
            self._pool = await ScalableWorkerPool.create(self.lab, config)
        return self._pool

    async def submit_to_pool(
        self,
        tasks: list[dict[str, Any]],
        *,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Submit tasks through the auto-scaling worker pool.

        Falls back to ``submit_and_execute`` when ``auto_scale`` is False.
        """
        if not self._auto_scale:
            return await self.submit_and_execute(tasks, timeout=int(timeout))

        pool = await self._ensure_pool()
        return await pool.submit_and_wait(tasks, timeout=timeout)

    async def get_scaling_metrics(self) -> dict[str, Any]:
        """Return scaling metrics (empty dict if auto_scale is off)."""
        if self._pool is None:
            return {}
        return self._pool.metrics.to_dict()

    async def shutdown_pool(self) -> None:
        """Shut down the auto-scaling pool if active."""
        if self._pool is not None:
            await self._pool.shutdown()
            self._pool = None
