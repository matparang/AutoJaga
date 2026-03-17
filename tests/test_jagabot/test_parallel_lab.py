"""Tests for JAGABOT v3.4 Phase 2 — ParallelLab batch execution, workflows,
partial failure, concurrency, CLI, and SubagentManager integration.
"""

import asyncio
import json

import pytest

from jagabot.lab.parallel import ParallelLab
from jagabot.lab.service import LabService


# ---------------------------------------------------------------------------
# Batch Submission & Execution
# ---------------------------------------------------------------------------

class TestParallelLabBatch:
    """Batch submit + execute."""

    @pytest.fixture(autouse=True)
    def _plab(self, tmp_path):
        self.plab = ParallelLab(lab=LabService(log_dir=tmp_path))

    @pytest.mark.asyncio
    async def test_submit_returns_batch_id(self):
        bid = self.plab.submit_batch([
            {"tool": "monte_carlo", "params": {"current_price": 100, "target_price": 90, "vix": 30}},
        ])
        assert bid.startswith("batch_")

    @pytest.mark.asyncio
    async def test_execute_batch_3_tasks(self):
        tasks = [
            {"tool": "monte_carlo", "params": {"current_price": 76.5, "target_price": 70, "vix": 52}},
            {"tool": "monte_carlo", "params": {"current_price": 100, "target_price": 80, "vix": 30}},
            {"tool": "monte_carlo", "params": {"current_price": 50, "target_price": 40, "vix": 25}},
        ]
        bid = self.plab.submit_batch(tasks)
        r = await self.plab.execute_batch(bid)
        assert r["status"] == "complete"
        assert r["completed"] == 3
        assert r["failed"] == 0
        assert r["total"] == 3

    @pytest.mark.asyncio
    async def test_submit_and_execute_convenience(self):
        r = await self.plab.submit_and_execute([
            {"tool": "monte_carlo", "params": {"current_price": 100, "target_price": 90, "vix": 30}},
        ])
        assert r["status"] == "complete"
        assert r["completed"] == 1

    @pytest.mark.asyncio
    async def test_execute_unknown_batch(self):
        r = await self.plab.execute_batch("nonexistent")
        assert "error" in r


# ---------------------------------------------------------------------------
# Priority Sorting
# ---------------------------------------------------------------------------

class TestParallelLabPriority:
    """Priority-based task ordering."""

    @pytest.fixture(autouse=True)
    def _plab(self, tmp_path):
        self.plab = ParallelLab(lab=LabService(log_dir=tmp_path))

    def test_priority_sort(self):
        tasks = [
            {"tool": "a", "params": {}, "priority": 1},
            {"tool": "b", "params": {}, "priority": 10},
            {"tool": "c", "params": {}, "priority": 5},
        ]
        bid = self.plab.submit_batch(tasks, priority_sort=True)
        batch = self.plab._batches[bid]
        assert batch["tasks"][0]["tool"] == "b"  # highest priority first
        assert batch["tasks"][1]["tool"] == "c"
        assert batch["tasks"][2]["tool"] == "a"

    def test_no_priority_sort(self):
        tasks = [
            {"tool": "a", "params": {}, "priority": 1},
            {"tool": "b", "params": {}, "priority": 10},
        ]
        bid = self.plab.submit_batch(tasks, priority_sort=False)
        batch = self.plab._batches[bid]
        assert batch["tasks"][0]["tool"] == "a"  # original order


# ---------------------------------------------------------------------------
# Partial Failure
# ---------------------------------------------------------------------------

class TestParallelLabFailure:
    """Partial failure handling."""

    @pytest.fixture(autouse=True)
    def _plab(self, tmp_path):
        self.plab = ParallelLab(lab=LabService(log_dir=tmp_path))

    @pytest.mark.asyncio
    async def test_partial_failure(self):
        tasks = [
            {"tool": "monte_carlo", "params": {"current_price": 100, "target_price": 90, "vix": 30}},
            {"tool": "nonexistent_tool", "params": {}},
            {"tool": "monte_carlo", "params": {"current_price": 50, "target_price": 40, "vix": 25}},
        ]
        r = await self.plab.submit_and_execute(tasks)
        assert r["status"] == "partial"
        assert r["completed"] == 2
        assert r["failed"] == 1
        assert r["total"] == 3

    @pytest.mark.asyncio
    async def test_all_failures(self):
        tasks = [
            {"tool": "bad1", "params": {}},
            {"tool": "bad2", "params": {}},
        ]
        r = await self.plab.submit_and_execute(tasks)
        assert r["status"] == "partial"
        assert r["completed"] == 0
        assert r["failed"] == 2


# ---------------------------------------------------------------------------
# Batch Tracking
# ---------------------------------------------------------------------------

class TestParallelLabTracking:
    """Batch status and listing."""

    @pytest.fixture(autouse=True)
    def _plab(self, tmp_path):
        self.plab = ParallelLab(lab=LabService(log_dir=tmp_path))

    def test_batch_status_pending(self):
        bid = self.plab.submit_batch([
            {"tool": "monte_carlo", "params": {"current_price": 100, "target_price": 90, "vix": 30}},
        ])
        s = self.plab.get_batch_status(bid)
        assert s["status"] == "pending"

    @pytest.mark.asyncio
    async def test_batch_status_after_execute(self):
        bid = self.plab.submit_batch([
            {"tool": "monte_carlo", "params": {"current_price": 100, "target_price": 90, "vix": 30}},
        ])
        await self.plab.execute_batch(bid)
        s = self.plab.get_batch_status(bid)
        assert s["status"] == "complete"
        assert s["completed"] == 1

    def test_batch_status_unknown(self):
        s = self.plab.get_batch_status("nope")
        assert "error" in s

    @pytest.mark.asyncio
    async def test_list_batches(self):
        self.plab.submit_batch([{"tool": "a", "params": {}}])
        self.plab.submit_batch([{"tool": "b", "params": {}}])
        batches = self.plab.list_batches()
        assert len(batches) == 2
        assert all("batch_id" in b for b in batches)


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------

class TestParallelLabWorkflows:
    """Predefined workflow execution."""

    @pytest.fixture(autouse=True)
    def _plab(self, tmp_path):
        self.plab = ParallelLab(lab=LabService(log_dir=tmp_path))

    @pytest.mark.asyncio
    async def test_risk_analysis_workflow(self):
        r = await self.plab.execute_workflow("risk_analysis", {
            "mc_params": {"current_price": 76.5, "target_price": 70, "vix": 52},
            "var_params": {"portfolio_value": 1109092, "annual_vol": 0.82},
            "stress_params": {"current_equity": 1109092, "current_price": 76.5, "stress_price": 65, "units": 21307},
        })
        assert r["total"] == 3
        assert r["completed"] >= 2  # at least MC and stress succeed

    @pytest.mark.asyncio
    async def test_unknown_workflow(self):
        r = await self.plab.execute_workflow("nonexistent", {})
        assert "error" in r

    def test_available_workflows(self):
        wf = ParallelLab.available_workflows()
        assert "risk_analysis" in wf
        assert "portfolio_review" in wf
        assert "full_analysis" in wf
        assert len(wf) == 3


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------

class TestParallelLabPerformance:
    """Performance: wall_time and speedup tracking."""

    @pytest.fixture(autouse=True)
    def _plab(self, tmp_path):
        self.plab = ParallelLab(lab=LabService(log_dir=tmp_path), max_concurrent=4)

    @pytest.mark.asyncio
    async def test_wall_time_recorded(self):
        r = await self.plab.submit_and_execute([
            {"tool": "monte_carlo", "params": {"current_price": 100, "target_price": 90, "vix": 30}},
            {"tool": "monte_carlo", "params": {"current_price": 50, "target_price": 40, "vix": 25}},
        ])
        assert r["wall_time"] >= 0
        assert r["wall_time"] < 10  # should be fast

    @pytest.mark.asyncio
    async def test_speedup_estimate_present(self):
        r = await self.plab.submit_and_execute([
            {"tool": "monte_carlo", "params": {"current_price": 100, "target_price": 90, "vix": 30}},
        ])
        assert "speedup_estimate" in r
        assert isinstance(r["speedup_estimate"], float)


# ---------------------------------------------------------------------------
# SubagentManager Integration
# ---------------------------------------------------------------------------

class TestSubagentManagerParallel:
    """SubagentManager.run_parallel_analysis()."""

    @pytest.mark.asyncio
    async def test_run_parallel_analysis(self):
        from jagabot.subagents.manager import SubagentManager
        mgr = SubagentManager()
        r = await mgr.run_parallel_analysis("risk_analysis", {
            "mc_params": {"current_price": 76.5, "target_price": 70, "vix": 52},
            "var_params": {"portfolio_value": 1109092, "annual_vol": 0.82},
            "stress_params": {"current_equity": 1109092, "current_price": 76.5, "stress_price": 65, "units": 21307},
        })
        assert r["total"] == 3
        assert r["completed"] >= 2
