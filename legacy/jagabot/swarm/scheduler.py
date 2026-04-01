"""Swarm scheduler — wraps CronService for automated swarm query execution."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from jagabot.cron.service import CronService
from jagabot.cron.types import CronJob, CronSchedule


class SwarmScheduler:
    """Scheduler that triggers SwarmOrchestrator queries on cron schedules.

    Wraps the existing CronService and adds swarm-specific workflow presets.
    """

    def __init__(
        self,
        store_path: Path | None = None,
        on_query: Callable[[str], str] | None = None,
    ):
        if store_path is None:
            store_path = Path.home() / ".jagabot" / "swarm_cron.json"
        self._store_path = store_path
        self._on_query = on_query  # sync callback: query → report

        async def _cron_callback(job: CronJob) -> str | None:
            query = job.payload.message
            if self._on_query:
                return self._on_query(query)
            return None

        self._cron = CronService(store_path=self._store_path, on_job=_cron_callback)

    async def start(self) -> None:
        """Start the scheduler service."""
        await self._cron.start()
        logger.info("SwarmScheduler started")

    def stop(self) -> None:
        """Stop the scheduler service."""
        self._cron.stop()
        logger.info("SwarmScheduler stopped")

    def add_workflow(
        self,
        name: str,
        query: str,
        cron_expr: str,
    ) -> CronJob:
        """Add a scheduled swarm workflow.

        Args:
            name: Human-readable name.
            query: The analysis query to run.
            cron_expr: Standard cron expression (e.g. '0 8 * * *' = daily 8am).
        """
        schedule = CronSchedule(kind="cron", expr=cron_expr)
        return self._cron.add_job(
            name=name,
            schedule=schedule,
            message=query,
        )

    def remove_workflow(self, job_id: str) -> bool:
        """Remove a scheduled workflow by ID."""
        return self._cron.remove_job(job_id)

    def list_workflows(self, include_disabled: bool = False) -> list[CronJob]:
        """List all scheduled workflows."""
        return self._cron.list_jobs(include_disabled=include_disabled)

    async def run_now(self, job_id: str) -> bool:
        """Manually trigger a workflow immediately."""
        return await self._cron.run_job(job_id, force=True)

    def status(self) -> dict[str, Any]:
        """Return scheduler status."""
        cron_status = self._cron.status()
        return {
            "enabled": cron_status["enabled"],
            "workflows": cron_status["jobs"],
            "next_run_ms": cron_status["next_wake_at_ms"],
            "store_path": str(self._store_path),
        }
