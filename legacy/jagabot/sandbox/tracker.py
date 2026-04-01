"""Sandbox execution tracker — SQLite-backed log of every sandbox run."""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path.home() / ".jagabot" / "sandbox.db"


@dataclass
class ExecutionRecord:
    """Single sandbox execution log entry."""

    id: int = 0
    subagent: str = ""
    calc_type: str = ""
    code_hash: str = ""
    success: bool = False
    exec_time_ms: float = 0.0
    engine: str = "none"
    error: str = ""
    timestamp: str = ""


class SandboxTracker:
    """Track every sandbox execution in SQLite for auditing.

    Usage::

        tracker = SandboxTracker()
        tracker.log_execution("billing", "equity", code, True, 42.1, "docker")
        report = tracker.get_usage_report()
    """

    def __init__(self, db_path: Path | str | None = None):
        self._db_path = Path(db_path) if db_path else _DEFAULT_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sandbox_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subagent TEXT NOT NULL DEFAULT '',
                calc_type TEXT NOT NULL DEFAULT '',
                code_hash TEXT NOT NULL,
                success INTEGER NOT NULL,
                exec_time_ms REAL NOT NULL,
                engine TEXT NOT NULL DEFAULT 'none',
                error TEXT NOT NULL DEFAULT '',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def log_execution(
        self,
        code: str,
        success: bool,
        exec_time_ms: float,
        engine: str = "none",
        subagent: str = "",
        calc_type: str = "",
        error: str = "",
    ) -> int:
        """Record a sandbox execution. Returns the row id."""
        code_hash = hashlib.md5(code.encode()).hexdigest()
        cur = self._conn.execute(
            """INSERT INTO sandbox_executions
               (subagent, calc_type, code_hash, success, exec_time_ms, engine, error)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (subagent, calc_type, code_hash, int(success), exec_time_ms, engine, error),
        )
        self._conn.commit()
        return cur.lastrowid or 0

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_recent(self, n: int = 50) -> list[ExecutionRecord]:
        """Return the *n* most recent executions."""
        rows = self._conn.execute(
            "SELECT * FROM sandbox_executions ORDER BY id DESC LIMIT ?", (n,)
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_usage_report(self) -> list[dict[str, Any]]:
        """Aggregate sandbox usage per subagent."""
        rows = self._conn.execute("""
            SELECT subagent,
                   COUNT(*)         AS total,
                   SUM(success)     AS successes,
                   AVG(exec_time_ms) AS avg_time_ms,
                   MIN(timestamp)   AS first_seen,
                   MAX(timestamp)   AS last_seen
            FROM sandbox_executions
            GROUP BY subagent
            ORDER BY total DESC
        """).fetchall()
        return [dict(r) for r in rows]

    def get_executions_for_session(self, since_ts: str) -> list[ExecutionRecord]:
        """Return executions since a given ISO timestamp."""
        rows = self._conn.execute(
            "SELECT * FROM sandbox_executions WHERE timestamp >= ? ORDER BY id",
            (since_ts,),
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def count(self) -> int:
        """Total execution count."""
        row = self._conn.execute("SELECT COUNT(*) FROM sandbox_executions").fetchone()
        return row[0] if row else 0

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def clear(self) -> int:
        """Delete all records. Returns count of deleted rows."""
        cur = self._conn.execute("DELETE FROM sandbox_executions")
        self._conn.commit()
        return cur.rowcount

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ExecutionRecord:
        return ExecutionRecord(
            id=row["id"],
            subagent=row["subagent"],
            calc_type=row["calc_type"],
            code_hash=row["code_hash"],
            success=bool(row["success"]),
            exec_time_ms=row["exec_time_ms"],
            engine=row["engine"],
            error=row["error"],
            timestamp=row["timestamp"],
        )
