"""Persistent task manager with dependency graph.

Adapted from learn-claude-code s07.  Tasks are stored as individual JSON
files in a directory so they survive context compression and process restarts.

Each task carries ``blocked_by`` / ``blocks`` lists that form a DAG.
Completing a task automatically clears it from all dependents' ``blocked_by``.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Optional


VALID_STATUSES = ("pending", "in_progress", "completed", "failed")


class TaskManagerError(ValueError):
    """Raised for invalid task operations."""


class TaskManager:
    """File-backed task board with dependency resolution.

    Each task is stored as ``{tasks_dir}/task_{id}.json``.

    Usage::

        tm = TaskManager(Path("/tmp/tasks"))
        tm.create("Build API", description="REST endpoints")
        tm.create("Write tests", blocked_by=[1])
        tm.update(1, status="completed")  # auto-clears from task 2
        print(tm.list_ready())            # → [task 2]
    """

    def __init__(self, tasks_dir: Path) -> None:
        self.dir = tasks_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._next_id: int = self._max_id() + 1

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _max_id(self) -> int:
        ids = []
        for f in self.dir.glob("task_*.json"):
            try:
                ids.append(int(f.stem.split("_")[1]))
            except (IndexError, ValueError):
                pass
        return max(ids) if ids else 0

    def _path(self, task_id: int) -> Path:
        return self.dir / f"task_{task_id}.json"

    def _load(self, task_id: int) -> dict[str, Any]:
        path = self._path(task_id)
        if not path.exists():
            raise TaskManagerError(f"Task {task_id} not found")
        return json.loads(path.read_text(encoding="utf-8"))

    def _save(self, task: dict[str, Any]) -> None:
        path = self._path(task["id"])
        path.write_text(json.dumps(task, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create(
        self,
        subject: str,
        description: str = "",
        blocked_by: Optional[list[int]] = None,
        blocks: Optional[list[int]] = None,
        owner: str = "",
    ) -> dict[str, Any]:
        """Create a new task. Returns the task dict."""
        with self._lock:
            task: dict[str, Any] = {
                "id": self._next_id,
                "subject": subject,
                "description": description,
                "status": "pending",
                "owner": owner,
                "blocked_by": list(blocked_by or []),
                "blocks": list(blocks or []),
                "created_at": time.time(),
            }
            self._save(task)
            # Bidirectional: update blocked tasks' blocked_by
            for blocked_id in task["blocks"]:
                try:
                    blocked = self._load(blocked_id)
                    if task["id"] not in blocked["blocked_by"]:
                        blocked["blocked_by"].append(task["id"])
                        self._save(blocked)
                except TaskManagerError:
                    pass
            self._next_id += 1
        return task

    def get(self, task_id: int) -> dict[str, Any]:
        """Get a task by ID."""
        return self._load(task_id)

    def exists(self, task_id: int) -> bool:
        """Check if a task exists."""
        return self._path(task_id).exists()

    def update(
        self,
        task_id: int,
        status: Optional[str] = None,
        owner: Optional[str] = None,
        add_blocked_by: Optional[list[int]] = None,
        add_blocks: Optional[list[int]] = None,
    ) -> dict[str, Any]:
        """Update task fields. Returns the updated task."""
        with self._lock:
            task = self._load(task_id)

            if status is not None:
                if status not in VALID_STATUSES:
                    raise TaskManagerError(
                        f"Invalid status: {status!r}. Must be one of {VALID_STATUSES}"
                    )
                task["status"] = status
                if status == "completed":
                    self._clear_dependency(task_id)

            if owner is not None:
                task["owner"] = owner

            if add_blocked_by:
                task["blocked_by"] = list(set(task["blocked_by"] + add_blocked_by))

            if add_blocks:
                task["blocks"] = list(set(task["blocks"] + add_blocks))
                for blocked_id in add_blocks:
                    try:
                        blocked = self._load(blocked_id)
                        if task_id not in blocked["blocked_by"]:
                            blocked["blocked_by"].append(task_id)
                            self._save(blocked)
                    except TaskManagerError:
                        pass

            self._save(task)
        return task

    def delete(self, task_id: int) -> bool:
        """Delete a task file. Returns True if it existed."""
        path = self._path(task_id)
        if path.exists():
            path.unlink()
            return True
        return False

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_all(self) -> list[dict[str, Any]]:
        """Return all tasks sorted by ID."""
        tasks = []
        for f in sorted(self.dir.glob("task_*.json")):
            try:
                tasks.append(json.loads(f.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                pass
        return tasks

    def list_ready(self) -> list[dict[str, Any]]:
        """Return tasks that are pending and have no unresolved dependencies."""
        return [
            t for t in self.list_all()
            if t["status"] == "pending" and not t.get("blocked_by")
        ]

    def list_by_status(self, status: str) -> list[dict[str, Any]]:
        """Return tasks with the given status."""
        return [t for t in self.list_all() if t["status"] == status]

    def list_by_owner(self, owner: str) -> list[dict[str, Any]]:
        """Return tasks assigned to a specific owner."""
        return [t for t in self.list_all() if t.get("owner") == owner]

    def render(self) -> str:
        """Human-readable task board string."""
        tasks = self.list_all()
        if not tasks:
            return "No tasks."
        markers = {
            "pending": "[ ]",
            "in_progress": "[>]",
            "completed": "[x]",
            "failed": "[!]",
        }
        lines = []
        for t in tasks:
            marker = markers.get(t["status"], "[?]")
            blocked = f" (blocked by: {t['blocked_by']})" if t.get("blocked_by") else ""
            owner = f" @{t['owner']}" if t.get("owner") else ""
            lines.append(f"{marker} #{t['id']}: {t['subject']}{owner}{blocked}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Dependency resolution
    # ------------------------------------------------------------------

    def _clear_dependency(self, completed_id: int) -> None:
        """Remove completed_id from all other tasks' blocked_by lists.

        Must be called under self._lock.
        """
        for f in self.dir.glob("task_*.json"):
            try:
                task = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if completed_id in task.get("blocked_by", []):
                task["blocked_by"].remove(completed_id)
                self._save(task)
