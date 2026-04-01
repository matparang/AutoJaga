"""Tests for jagabot.swarm.autonomous — worker claiming & WORK/IDLE cycle."""
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from jagabot.core.task_manager import TaskManager
from jagabot.swarm.autonomous import (
    AutonomousWorker,
    claim_task,
    make_identity_block,
    scan_unclaimed_tasks,
)


@pytest.fixture
def tm(tmp_path):
    return TaskManager(tmp_path / "tasks")


# ── scan_unclaimed_tasks ─────────────────────────────────────────────

class TestScanUnclaimed:
    def test_empty_board(self, tm):
        assert scan_unclaimed_tasks(tm) == []

    def test_finds_unclaimed(self, tm):
        tm.create("A")
        result = scan_unclaimed_tasks(tm)
        assert len(result) == 1

    def test_skips_owned(self, tm):
        tm.create("A", owner="alice")
        result = scan_unclaimed_tasks(tm)
        assert len(result) == 0

    def test_skips_blocked(self, tm):
        t1 = tm.create("A")
        tm.create("B", blocked_by=[t1["id"]])
        result = scan_unclaimed_tasks(tm)
        assert len(result) == 1
        assert result[0]["subject"] == "A"

    def test_skips_completed(self, tm):
        t = tm.create("A")
        tm.update(t["id"], status="completed")
        assert scan_unclaimed_tasks(tm) == []

    def test_multiple_unclaimed(self, tm):
        tm.create("A")
        tm.create("B")
        tm.create("C")
        assert len(scan_unclaimed_tasks(tm)) == 3


# ── claim_task ───────────────────────────────────────────────────────

class TestClaimTask:
    def test_claim_success(self, tm):
        t = tm.create("A")
        result = claim_task(tm, t["id"], "alice")
        assert "claimed by alice" in result

    def test_claim_updates_status(self, tm):
        t = tm.create("A")
        claim_task(tm, t["id"], "alice")
        task = tm.get(t["id"])
        assert task["status"] == "in_progress"
        assert task["owner"] == "alice"

    def test_claim_already_in_progress(self, tm):
        t = tm.create("A")
        tm.update(t["id"], status="in_progress", owner="bob")
        result = claim_task(tm, t["id"], "alice")
        assert "already" in result

    def test_claim_already_owned(self, tm):
        t = tm.create("A")
        tm.update(t["id"], owner="bob")
        result = claim_task(tm, t["id"], "alice")
        assert "already claimed" in result

    def test_concurrent_claims(self, tm):
        t = tm.create("A")
        lock = threading.Lock()
        results = []

        def try_claim(name):
            r = claim_task(tm, t["id"], name, lock=lock)
            results.append(r)

        threads = [threading.Thread(target=try_claim, args=(f"w{i}",)) for i in range(5)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        claimed = [r for r in results if "claimed by" in r]
        assert len(claimed) >= 1  # at least one succeeded


# ── make_identity_block ──────────────────────────────────────────────

class TestIdentityBlock:
    def test_basic(self):
        block = make_identity_block("alice", "analyst", ["bob", "charlie"])
        assert block["name"] == "alice"
        assert block["role"] == "analyst"
        assert "alice" in block["reminder"]

    def test_team_members(self):
        block = make_identity_block("alice", "analyst", ["bob"])
        assert "bob" in block["reminder"]

    def test_empty_team(self):
        block = make_identity_block("solo", "analyst", [])
        assert isinstance(block["reminder"], str)


# ── AutonomousWorker ─────────────────────────────────────────────────

class TestAutonomousWorker:
    def test_start_stop(self, tm):
        w = AutonomousWorker("w1", "tester", tm, idle_timeout=2.0, idle_poll_interval=0.1)
        w.start()
        time.sleep(0.2)
        assert w.is_alive()
        w.stop()
        time.sleep(2.0)
        assert not w.is_alive()

    def test_claims_and_completes(self, tm):
        handler = MagicMock()
        tm.create("Test task")
        w = AutonomousWorker(
            "w1", "tester", tm,
            handler=handler,
            idle_timeout=2.0,
            idle_poll_interval=0.1,
        )
        w.start()
        time.sleep(1.0)
        handler.assert_called_once()
        task = tm.get(1)
        assert task["status"] == "completed"
        w.stop()

    def test_idle_timeout(self, tm):
        w = AutonomousWorker("w1", "tester", tm, idle_timeout=0.5, idle_poll_interval=0.1)
        w.start()
        time.sleep(1.5)
        assert not w.is_alive()
        assert w.state == "stopped"

    def test_handler_exception(self, tm):
        def bad_handler(task):
            raise RuntimeError("oops")

        tm.create("Failing task")
        w = AutonomousWorker(
            "w1", "tester", tm,
            handler=bad_handler,
            idle_timeout=1.0,
            idle_poll_interval=0.1,
        )
        w.start()
        time.sleep(1.0)
        task = tm.get(1)
        assert task["status"] == "failed"
        w.stop()

    def test_tasks_completed_counter(self, tm):
        tm.create("A")
        tm.create("B")
        w = AutonomousWorker(
            "w1", "tester", tm,
            idle_timeout=2.0,
            idle_poll_interval=0.1,
        )
        w.start()
        time.sleep(1.5)
        assert w.tasks_completed == 2
        w.stop()

    def test_initial_state(self, tm):
        w = AutonomousWorker("w1", "tester", tm)
        assert w.state == "idle"
        assert w.tasks_completed == 0

    def test_skips_blocked_tasks(self, tm):
        t1 = tm.create("A")
        t2 = tm.create("B", blocked_by=[t1["id"]])
        w = AutonomousWorker(
            "w1", "tester", tm,
            idle_timeout=0.5,
            idle_poll_interval=0.1,
        )
        w.start()
        time.sleep(1.0)
        # Should complete A, B should now be unblocked
        assert tm.get(t1["id"])["status"] == "completed"
        time.sleep(1.0)
        assert tm.get(t2["id"])["status"] == "completed"
        w.stop()
