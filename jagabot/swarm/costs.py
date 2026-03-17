"""Cost tracker — records and aggregates swarm resource usage."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any


# Default cost per tool invocation (placeholder — real API costs later)
_DEFAULT_COSTS: dict[str, float] = {
    "monte_carlo": 0.002,
    "var": 0.001,
    "cvar": 0.001,
    "stress_test": 0.0015,
    "correlation": 0.001,
    "financial_cv": 0.0005,
    "early_warning": 0.0005,
    "recovery_time": 0.0005,
    "sensitivity_analyzer": 0.001,
    "bayesian_reasoner": 0.001,
    "counterfactual_sim": 0.001,
    "pareto_optimizer": 0.001,
    "dynamics_oracle": 0.001,
    "statistical_engine": 0.001,
    "visualization": 0.0005,
    "decision_engine": 0.001,
    "education": 0.0003,
    "accountability": 0.0003,
    "researcher": 0.002,
    "copywriter": 0.0015,
    "self_improver": 0.001,
}


class CostTracker:
    """SQLite-backed tracker for swarm cost accounting.

    Records per-invocation costs and provides daily/monthly/worker aggregation.
    Supports optional budget alerts.
    """

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = Path.home() / ".jagabot" / "swarm_costs.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(db_path)
        self._db: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        self._db = sqlite3.connect(str(self.db_path))
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS costs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id TEXT,
                tool_name TEXT NOT NULL,
                method TEXT,
                cost REAL NOT NULL DEFAULT 0.0,
                elapsed_s REAL DEFAULT 0.0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS budget_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                period TEXT NOT NULL,
                budget REAL NOT NULL,
                actual REAL NOT NULL,
                triggered_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                period TEXT PRIMARY KEY,
                amount REAL NOT NULL
            )
        """)
        self._db.commit()

    def record(
        self,
        tool_name: str,
        method: str = "",
        analysis_id: str = "",
        elapsed_s: float = 0.0,
        cost: float | None = None,
    ) -> float:
        """Record a tool invocation cost. Returns the cost recorded."""
        if cost is None:
            cost = _DEFAULT_COSTS.get(tool_name, 0.001)
        if not self._db:
            return cost
        self._db.execute(
            "INSERT INTO costs (analysis_id, tool_name, method, cost, elapsed_s) "
            "VALUES (?, ?, ?, ?, ?)",
            (analysis_id, tool_name, method, cost, elapsed_s),
        )
        self._db.commit()
        self._check_budget_alerts()
        return cost

    def daily_total(self, date: str | None = None) -> float:
        """Get total cost for a specific day (YYYY-MM-DD) or today."""
        if not self._db:
            return 0.0
        if date is None:
            date = time.strftime("%Y-%m-%d")
        cursor = self._db.execute(
            "SELECT COALESCE(SUM(cost), 0) FROM costs WHERE DATE(timestamp) = ?",
            (date,),
        )
        return cursor.fetchone()[0]

    def monthly_total(self, month: str | None = None) -> float:
        """Get total cost for a month (YYYY-MM) or current month."""
        if not self._db:
            return 0.0
        if month is None:
            month = time.strftime("%Y-%m")
        cursor = self._db.execute(
            "SELECT COALESCE(SUM(cost), 0) FROM costs WHERE strftime('%Y-%m', timestamp) = ?",
            (month,),
        )
        return cursor.fetchone()[0]

    def by_tool(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get cost breakdown by tool name."""
        if not self._db:
            return []
        cursor = self._db.execute(
            "SELECT tool_name, COUNT(*) as invocations, SUM(cost) as total_cost, "
            "AVG(elapsed_s) as avg_time "
            "FROM costs GROUP BY tool_name ORDER BY total_cost DESC LIMIT ?",
            (limit,),
        )
        return [
            {"tool": r[0], "invocations": r[1], "total_cost": round(r[2], 6),
             "avg_time": round(r[3], 3)}
            for r in cursor.fetchall()
        ]

    def set_budget(self, period: str, amount: float) -> None:
        """Set a budget for a period (e.g. 'daily', 'monthly')."""
        if not self._db:
            return
        self._db.execute(
            "INSERT OR REPLACE INTO budgets (period, amount) VALUES (?, ?)",
            (period, amount),
        )
        self._db.commit()

    def get_budgets(self) -> dict[str, float]:
        """Get all configured budgets."""
        if not self._db:
            return {}
        cursor = self._db.execute("SELECT period, amount FROM budgets")
        return {r[0]: r[1] for r in cursor.fetchall()}

    def _check_budget_alerts(self) -> None:
        """Check if any budget limits have been exceeded."""
        if not self._db:
            return
        budgets = self.get_budgets()
        for period, limit_amount in budgets.items():
            if period == "daily":
                actual = self.daily_total()
            elif period == "monthly":
                actual = self.monthly_total()
            else:
                continue
            if actual > limit_amount:
                self._db.execute(
                    "INSERT INTO budget_alerts (period, budget, actual) VALUES (?, ?, ?)",
                    (period, limit_amount, actual),
                )
                self._db.commit()

    def recent_alerts(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent budget alerts."""
        if not self._db:
            return []
        cursor = self._db.execute(
            "SELECT period, budget, actual, triggered_at FROM budget_alerts "
            "ORDER BY triggered_at DESC LIMIT ?",
            (limit,),
        )
        return [
            {"period": r[0], "budget": r[1], "actual": r[2], "triggered_at": r[3]}
            for r in cursor.fetchall()
        ]

    def summary(self) -> dict[str, Any]:
        """Full cost summary."""
        return {
            "daily": round(self.daily_total(), 6),
            "monthly": round(self.monthly_total(), 6),
            "by_tool": self.by_tool(10),
            "budgets": self.get_budgets(),
            "recent_alerts": self.recent_alerts(5),
        }

    def shutdown(self) -> None:
        """Close the database connection."""
        if self._db:
            self._db.close()
            self._db = None
