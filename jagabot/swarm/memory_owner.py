"""Swarm orchestrator — Memory Owner that plans, spawns, collects, and stitches."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from jagabot.swarm.costs import CostTracker
from jagabot.swarm.planner import TaskPlanner
from jagabot.swarm.status import WorkerTracker
from jagabot.swarm.stitcher import ResultStitcher
from jagabot.swarm.watchdog import Watchdog
from jagabot.swarm.worker_pool import TaskResult, WorkerPool


class SwarmOrchestrator:
    """Central coordinator for swarm-based parallel analysis.

    Owns persistent memory (SQLite), plans tasks via TaskPlanner,
    executes them in parallel via WorkerPool, and stitches results
    via ResultStitcher.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        max_workers: int | None = None,
        locale: str = "en",
        enable_watchdog: bool = False,
    ):
        if db_path is None:
            db_path = Path.home() / ".jagabot" / "swarm.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(db_path)

        self.tracker = WorkerTracker()
        self.costs = CostTracker()
        self.pool = WorkerPool(max_workers=max_workers, tracker=self.tracker)
        self.planner = TaskPlanner()
        self.stitcher = ResultStitcher(locale=locale)
        self.locale = locale

        self.watchdog = Watchdog()
        self.watchdog.set_tracker(self.tracker)
        self.watchdog.set_cost_tracker(self.costs)
        if enable_watchdog:
            self.watchdog.start()

        self._db: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        self._db = sqlite3.connect(str(self.db_path))
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                query TEXT,
                plan_json TEXT,
                results_json TEXT,
                report TEXT,
                elapsed_s REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS worker_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id TEXT,
                tool_name TEXT,
                method TEXT,
                task_id TEXT,
                status TEXT,
                elapsed_s REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._db.commit()

    def process_query(
        self,
        query: str,
        context: dict[str, Any] | None = None,
        global_timeout: float = 120.0,
    ) -> str:
        """Run a full swarm analysis: plan → spawn → collect → stitch → store.

        Returns the markdown report.
        """
        analysis_id = uuid.uuid4().hex[:8]
        start = time.monotonic()

        # Plan
        groups = self.planner.plan(query, context)
        plan_summary = self.planner.plan_summary(groups)

        # Execute groups
        all_results: list[TaskResult] = []
        try:
            remaining = global_timeout
            for group in groups:
                if remaining <= 0:
                    break
                group_start = time.monotonic()
                group_results = self.pool.run_task_groups([group])
                all_results.extend(group_results)
                remaining -= (time.monotonic() - group_start)

                # Log each worker + record costs
                for r in group_results:
                    self._log_worker(analysis_id, r)
                    self.costs.record(
                        tool_name=r.tool_name,
                        method=r.method,
                        analysis_id=analysis_id,
                        elapsed_s=r.elapsed_s,
                    )
        except Exception as exc:
            all_results.append(TaskResult(
                task_id="orchestrator_error", tool_name="orchestrator",
                method="run_task_groups", data={"error": str(exc)},
                success=False,
            ))

        # Stitch
        report = self.stitcher.stitch(all_results, query)
        elapsed = round(time.monotonic() - start, 3)

        # Store
        self._store_analysis(analysis_id, query, plan_summary, all_results, report, elapsed)

        return report

    def get_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return recent analysis history."""
        if not self._db:
            return []
        cursor = self._db.execute(
            "SELECT id, query, elapsed_s, timestamp FROM analyses ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [
            {"id": row[0], "query": row[1], "elapsed_s": row[2], "timestamp": row[3]}
            for row in cursor.fetchall()
        ]

    def get_analysis(self, analysis_id: str) -> dict[str, Any] | None:
        """Retrieve a stored analysis by ID."""
        if not self._db:
            return None
        cursor = self._db.execute(
            "SELECT id, query, plan_json, results_json, report, elapsed_s, timestamp "
            "FROM analyses WHERE id = ?",
            (analysis_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0], "query": row[1],
            "plan": json.loads(row[2]) if row[2] else None,
            "results": json.loads(row[3]) if row[3] else None,
            "report": row[4], "elapsed_s": row[5], "timestamp": row[6],
        }

    def status(self) -> dict[str, Any]:
        """Return orchestrator status."""
        from jagabot.swarm.tool_registry import get_all_tool_names, get_tool_count

        analysis_count = 0
        if self._db:
            cursor = self._db.execute("SELECT COUNT(*) FROM analyses")
            analysis_count = cursor.fetchone()[0]

        return {
            "max_workers": self.pool.max_workers,
            "available_tools": get_tool_count(),
            "tool_names": get_all_tool_names(),
            "total_analyses": analysis_count,
            "db_path": str(self.db_path),
            "locale": self.locale,
            "tracker": self.tracker.stats(),
            "watchdog": self.watchdog.health(),
            "costs": self.costs.summary(),
        }

    def shutdown(self) -> None:
        """Clean up resources."""
        self.watchdog.stop()
        self.pool.shutdown()
        self.costs.shutdown()
        if self._db:
            self._db.close()
            self._db = None

    def _store_analysis(
        self, analysis_id: str, query: str,
        plan: dict, results: list[TaskResult],
        report: str, elapsed: float,
    ) -> None:
        if not self._db:
            return
        results_data = [
            {"task_id": r.task_id, "tool": r.tool_name, "method": r.method,
             "success": r.success, "elapsed_s": r.elapsed_s,
             "data": r.data if isinstance(r.data, (dict, str)) else str(r.data)}
            for r in results
        ]
        self._db.execute(
            "INSERT INTO analyses (id, query, plan_json, results_json, report, elapsed_s) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (analysis_id, query, json.dumps(plan), json.dumps(results_data), report, elapsed),
        )
        self._db.commit()

    def _log_worker(self, analysis_id: str, result: TaskResult) -> None:
        if not self._db:
            return
        self._db.execute(
            "INSERT INTO worker_logs (analysis_id, tool_name, method, task_id, status, elapsed_s) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (analysis_id, result.tool_name, result.method, result.task_id,
             "ok" if result.success else "error", result.elapsed_s),
        )
        self._db.commit()
