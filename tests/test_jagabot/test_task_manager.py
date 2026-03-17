"""Tests for jagabot.core.task_manager — persistent task board with dependencies."""
import json
import tempfile
from pathlib import Path

import pytest

from jagabot.core.task_manager import TaskManager, TaskManagerError, VALID_STATUSES


@pytest.fixture
def tm(tmp_path):
    return TaskManager(tmp_path / "tasks")


# ── Creation ─────────────────────────────────────────────────────────

class TestCreate:
    def test_create_basic(self, tm):
        t = tm.create("Build API")
        assert t["id"] == 1
        assert t["subject"] == "Build API"
        assert t["status"] == "pending"

    def test_create_with_description(self, tm):
        t = tm.create("Build API", description="REST endpoints")
        assert t["description"] == "REST endpoints"

    def test_auto_increment(self, tm):
        t1 = tm.create("A")
        t2 = tm.create("B")
        assert t2["id"] == t1["id"] + 1

    def test_create_with_blocked_by(self, tm):
        t1 = tm.create("A")
        t2 = tm.create("B", blocked_by=[t1["id"]])
        assert t1["id"] in t2["blocked_by"]

    def test_create_with_blocks(self, tm):
        t1 = tm.create("A")
        t2 = tm.create("B", blocks=[t1["id"]])
        # t2 blocks t1 → t1.blocked_by should contain t2.id
        t1r = tm.get(t1["id"])
        assert t2["id"] in t1r["blocked_by"]

    def test_create_with_owner(self, tm):
        t = tm.create("A", owner="alice")
        assert t["owner"] == "alice"

    def test_create_persists_to_disk(self, tm):
        t = tm.create("A")
        path = tm._path(t["id"])
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["subject"] == "A"

    def test_create_has_created_at(self, tm):
        t = tm.create("A")
        assert "created_at" in t
        assert isinstance(t["created_at"], float)

    def test_create_empty_deps(self, tm):
        t = tm.create("A")
        assert t["blocked_by"] == []
        assert t["blocks"] == []


# ── Get / Exists ─────────────────────────────────────────────────────

class TestGetExists:
    def test_get_existing(self, tm):
        t = tm.create("A")
        result = tm.get(t["id"])
        assert result["subject"] == "A"

    def test_get_nonexistent(self, tm):
        with pytest.raises(TaskManagerError):
            tm.get(999)

    def test_exists_true(self, tm):
        t = tm.create("A")
        assert tm.exists(t["id"]) is True

    def test_exists_false(self, tm):
        assert tm.exists(999) is False


# ── Update ───────────────────────────────────────────────────────────

class TestUpdate:
    def test_update_status(self, tm):
        t = tm.create("A")
        result = tm.update(t["id"], status="in_progress")
        assert result["status"] == "in_progress"

    def test_update_invalid_status(self, tm):
        t = tm.create("A")
        with pytest.raises(TaskManagerError, match="Invalid status"):
            tm.update(t["id"], status="bogus")

    def test_update_owner(self, tm):
        t = tm.create("A")
        result = tm.update(t["id"], owner="bob")
        assert result["owner"] == "bob"

    def test_update_add_blocked_by(self, tm):
        t1 = tm.create("A")
        t2 = tm.create("B")
        tm.update(t2["id"], add_blocked_by=[t1["id"]])
        result = tm.get(t2["id"])
        assert t1["id"] in result["blocked_by"]

    def test_update_add_blocks(self, tm):
        t1 = tm.create("A")
        t2 = tm.create("B")
        tm.update(t1["id"], add_blocks=[t2["id"]])
        t2r = tm.get(t2["id"])
        assert t1["id"] in t2r["blocked_by"]

    def test_update_nonexistent(self, tm):
        with pytest.raises(TaskManagerError):
            tm.update(999, status="pending")

    def test_update_persists(self, tm):
        t = tm.create("A")
        tm.update(t["id"], status="completed")
        data = json.loads(tm._path(t["id"]).read_text())
        assert data["status"] == "completed"


# ── Delete ───────────────────────────────────────────────────────────

class TestDelete:
    def test_delete_existing(self, tm):
        t = tm.create("A")
        assert tm.delete(t["id"]) is True
        assert not tm.exists(t["id"])

    def test_delete_nonexistent(self, tm):
        assert tm.delete(999) is False


# ── Dependency resolution ────────────────────────────────────────────

class TestDependencies:
    def test_complete_clears_dependency(self, tm):
        t1 = tm.create("A")
        t2 = tm.create("B", blocked_by=[t1["id"]])
        tm.update(t1["id"], status="completed")
        t2r = tm.get(t2["id"])
        assert t1["id"] not in t2r["blocked_by"]

    def test_complete_cascade(self, tm):
        t1 = tm.create("A")
        t2 = tm.create("B", blocked_by=[t1["id"]])
        t3 = tm.create("C", blocked_by=[t1["id"]])
        tm.update(t1["id"], status="completed")
        assert tm.get(t2["id"])["blocked_by"] == []
        assert tm.get(t3["id"])["blocked_by"] == []

    def test_partial_unblock(self, tm):
        t1 = tm.create("A")
        t2 = tm.create("B")
        t3 = tm.create("C", blocked_by=[t1["id"], t2["id"]])
        tm.update(t1["id"], status="completed")
        t3r = tm.get(t3["id"])
        assert t2["id"] in t3r["blocked_by"]
        assert t1["id"] not in t3r["blocked_by"]


# ── Queries ──────────────────────────────────────────────────────────

class TestQueries:
    def test_list_all_empty(self, tm):
        assert tm.list_all() == []

    def test_list_all(self, tm):
        tm.create("A")
        tm.create("B")
        assert len(tm.list_all()) == 2

    def test_list_all_sorted(self, tm):
        tm.create("B")
        tm.create("A")
        tasks = tm.list_all()
        assert tasks[0]["id"] < tasks[1]["id"]

    def test_list_ready(self, tm):
        t1 = tm.create("A")
        t2 = tm.create("B", blocked_by=[t1["id"]])
        ready = tm.list_ready()
        assert len(ready) == 1
        assert ready[0]["id"] == t1["id"]

    def test_list_ready_after_completion(self, tm):
        t1 = tm.create("A")
        t2 = tm.create("B", blocked_by=[t1["id"]])
        tm.update(t1["id"], status="completed")
        ready = tm.list_ready()
        assert len(ready) == 1
        assert ready[0]["id"] == t2["id"]

    def test_list_by_status(self, tm):
        tm.create("A")
        t2 = tm.create("B")
        tm.update(t2["id"], status="in_progress")
        assert len(tm.list_by_status("pending")) == 1
        assert len(tm.list_by_status("in_progress")) == 1

    def test_list_by_owner(self, tm):
        tm.create("A", owner="alice")
        tm.create("B", owner="bob")
        assert len(tm.list_by_owner("alice")) == 1

    def test_render_empty(self, tm):
        assert tm.render() == "No tasks."

    def test_render_output(self, tm):
        tm.create("A")
        tm.create("B", blocked_by=[1])
        output = tm.render()
        assert "#1" in output
        assert "blocked by" in output


# ── Valid statuses ───────────────────────────────────────────────────

class TestStatuses:
    @pytest.mark.parametrize("status", VALID_STATUSES)
    def test_valid_status(self, tm, status):
        t = tm.create("A")
        result = tm.update(t["id"], status=status)
        assert result["status"] == status


# ── Persistence across reload ────────────────────────────────────────

class TestPersistence:
    def test_reload_preserves_tasks(self, tmp_path):
        tm1 = TaskManager(tmp_path / "tasks")
        tm1.create("A")
        tm1.create("B")
        tm2 = TaskManager(tmp_path / "tasks")
        assert len(tm2.list_all()) == 2

    def test_next_id_after_reload(self, tmp_path):
        tm1 = TaskManager(tmp_path / "tasks")
        tm1.create("A")
        tm2 = TaskManager(tmp_path / "tasks")
        t = tm2.create("B")
        assert t["id"] == 2
