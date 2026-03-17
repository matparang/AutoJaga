"""Tests for JAGABOT v3.5 — Auto-Scaling Worker Pools.

Covers ScalingConfig, ScalingMetrics, ScalableWorkerPool, and
ParallelLab auto_scale integration.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jagabot.lab.scaling import ScalingConfig, ScalingMetrics, ScalableWorkerPool, _STOP


# ====================================================================
# ScalingConfig
# ====================================================================

class TestScalingConfig:
    def test_defaults(self):
        cfg = ScalingConfig()
        assert cfg.min_workers == 2
        assert cfg.max_workers == 32
        assert cfg.scale_up_threshold == 5
        assert cfg.scale_down_threshold == 2
        assert cfg.cooldown_period == 60.0
        assert cfg.scale_up_factor == 1.5
        assert cfg.scale_down_factor == 0.5
        assert cfg.monitor_interval == 5.0

    def test_custom_values(self):
        cfg = ScalingConfig(min_workers=4, max_workers=16, cooldown_period=10)
        assert cfg.min_workers == 4
        assert cfg.max_workers == 16
        assert cfg.cooldown_period == 10

    def test_min_less_than_max(self):
        cfg = ScalingConfig(min_workers=1, max_workers=64)
        assert cfg.min_workers < cfg.max_workers


# ====================================================================
# ScalingMetrics
# ====================================================================

class TestScalingMetrics:
    def test_defaults(self):
        m = ScalingMetrics()
        assert m.scale_up_events == 0
        assert m.scale_down_events == 0
        assert m.peak_workers == 0
        assert m.total_tasks_processed == 0
        assert m.total_tasks_failed == 0

    def test_to_dict(self):
        m = ScalingMetrics(scale_up_events=3, peak_workers=8)
        d = m.to_dict()
        assert d["scale_up_events"] == 3
        assert d["peak_workers"] == 8
        assert "total_tasks_processed" in d

    def test_record_event(self):
        m = ScalingMetrics()
        m.record_event("scale_up", {"from": 2, "to": 4})
        assert len(m._history) == 1
        assert m._history[0]["type"] == "scale_up"
        assert m._history[0]["from"] == 2


# ====================================================================
# ScalableWorkerPool — creation & basic API
# ====================================================================

def _mock_lab():
    """Create a mock LabService whose execute returns success."""
    lab = AsyncMock()
    lab.execute = AsyncMock(return_value={
        "success": True,
        "tool": "mock",
        "output": {"value": 42},
        "execution_id": "mock_001",
        "execution_time": 0.01,
        "sandbox_used": False,
    })
    return lab


class TestScalableWorkerPoolCreation:
    @pytest.mark.asyncio
    async def test_create_with_defaults(self):
        lab = _mock_lab()
        pool = await ScalableWorkerPool.create(lab)
        try:
            assert pool.current_workers == 2  # min_workers default
            assert pool.config.min_workers == 2
            assert pool.metrics.peak_workers == 2
        finally:
            await pool.shutdown()

    @pytest.mark.asyncio
    async def test_create_with_custom_config(self):
        lab = _mock_lab()
        cfg = ScalingConfig(min_workers=4, max_workers=8)
        pool = await ScalableWorkerPool.create(lab, cfg)
        try:
            assert pool.current_workers == 4
            assert pool.config.max_workers == 8
        finally:
            await pool.shutdown()

    @pytest.mark.asyncio
    async def test_create_default_lab(self):
        """create() without explicit lab imports LabService."""
        with patch("jagabot.lab.service.LabService", return_value=_mock_lab()):
            pool = await ScalableWorkerPool.create()
            await pool.shutdown()


# ====================================================================
# ScalableWorkerPool — task submission & results
# ====================================================================

class TestScalableWorkerPoolTasks:
    @pytest.mark.asyncio
    async def test_submit_returns_task_id(self):
        lab = _mock_lab()
        pool = await ScalableWorkerPool.create(lab)
        try:
            tid = await pool.submit_task("monte_carlo", {"n": 100})
            assert tid.startswith("task_")
        finally:
            await pool.shutdown()

    @pytest.mark.asyncio
    async def test_get_result(self):
        lab = _mock_lab()
        pool = await ScalableWorkerPool.create(lab)
        try:
            tid = await pool.submit_task("monte_carlo", {"n": 100})
            result = await pool.get_result(tid, timeout=5.0)
            assert result["success"] is True
            assert result["output"]["value"] == 42
        finally:
            await pool.shutdown()

    @pytest.mark.asyncio
    async def test_unknown_task_id(self):
        lab = _mock_lab()
        pool = await ScalableWorkerPool.create(lab)
        try:
            result = await pool.get_result("nonexistent")
            assert result["success"] is False
            assert "Unknown task" in result["error"]
        finally:
            await pool.shutdown()

    @pytest.mark.asyncio
    async def test_multiple_tasks(self):
        lab = _mock_lab()
        pool = await ScalableWorkerPool.create(lab)
        try:
            ids = []
            for i in range(5):
                tid = await pool.submit_task("monte_carlo", {"n": i})
                ids.append(tid)
            for tid in ids:
                r = await pool.get_result(tid, timeout=5.0)
                assert r["success"] is True
            assert pool.metrics.total_tasks_processed == 5
        finally:
            await pool.shutdown()

    @pytest.mark.asyncio
    async def test_submit_and_wait(self):
        lab = _mock_lab()
        pool = await ScalableWorkerPool.create(lab)
        try:
            tasks = [
                {"tool": "monte_carlo", "params": {"n": 100}},
                {"tool": "var", "params": {"method": "parametric_var", "params": {}}},
            ]
            result = await pool.submit_and_wait(tasks, timeout=5.0)
            assert result["total"] == 2
            assert result["completed"] == 2
            assert result["failed"] == 0
            assert result["status"] == "complete"
            assert "wall_time" in result
            assert "workers_used" in result
        finally:
            await pool.shutdown()

    @pytest.mark.asyncio
    async def test_task_failure_counted(self):
        lab = _mock_lab()
        lab.execute = AsyncMock(return_value={
            "success": False,
            "error": "boom",
            "execution_time": 0.001,
        })
        pool = await ScalableWorkerPool.create(lab)
        try:
            tid = await pool.submit_task("bad_tool", {})
            r = await pool.get_result(tid, timeout=5.0)
            assert r["success"] is False
            assert pool.metrics.total_tasks_failed == 1
        finally:
            await pool.shutdown()

    @pytest.mark.asyncio
    async def test_task_exception_handled(self):
        lab = _mock_lab()
        lab.execute = AsyncMock(side_effect=RuntimeError("kaboom"))
        pool = await ScalableWorkerPool.create(lab)
        try:
            tid = await pool.submit_task("exploding", {})
            r = await pool.get_result(tid, timeout=5.0)
            assert r["success"] is False
            assert "kaboom" in r["error"]
        finally:
            await pool.shutdown()


# ====================================================================
# ScalableWorkerPool — scaling logic
# ====================================================================

class TestScalableWorkerPoolScaling:
    @pytest.mark.asyncio
    async def test_scale_up_on_queue_pressure(self):
        """Directly test _evaluate_scaling triggers scale up."""
        lab = _mock_lab()
        cfg = ScalingConfig(min_workers=2, max_workers=8, scale_up_threshold=3, cooldown_period=0)
        pool = await ScalableWorkerPool.create(lab, cfg)
        try:
            pool._last_scale_time = 0  # bypass cooldown
            await pool._evaluate_scaling(queue_size=10)
            assert pool.metrics.scale_up_events == 1
            assert pool._current_workers > 2
        finally:
            await pool.shutdown()

    @pytest.mark.asyncio
    async def test_scale_down_on_idle(self):
        """Directly test _evaluate_scaling triggers scale down."""
        lab = _mock_lab()
        cfg = ScalingConfig(min_workers=2, max_workers=8, cooldown_period=0)
        pool = await ScalableWorkerPool.create(lab, cfg)
        try:
            # First scale up
            pool._last_scale_time = 0
            await pool._evaluate_scaling(queue_size=10)
            workers_after_up = pool._current_workers
            assert workers_after_up > 2

            # Now scale down (queue empty)
            pool._last_scale_time = 0
            await pool._evaluate_scaling(queue_size=0)
            assert pool.metrics.scale_down_events == 1
        finally:
            await pool.shutdown()

    @pytest.mark.asyncio
    async def test_cooldown_prevents_thrashing(self):
        """Scaling should NOT happen during cooldown period."""
        lab = _mock_lab()
        cfg = ScalingConfig(min_workers=2, max_workers=8, cooldown_period=9999)
        pool = await ScalableWorkerPool.create(lab, cfg)
        try:
            # _last_scale_time is recent (set in create) → cooldown active
            await pool._evaluate_scaling(queue_size=100)
            assert pool.metrics.scale_up_events == 0  # blocked by cooldown
        finally:
            await pool.shutdown()

    @pytest.mark.asyncio
    async def test_scale_respects_max(self):
        """Workers should not exceed max_workers."""
        lab = _mock_lab()
        cfg = ScalingConfig(min_workers=2, max_workers=4, cooldown_period=0, scale_up_factor=10.0)
        pool = await ScalableWorkerPool.create(lab, cfg)
        try:
            pool._last_scale_time = 0
            await pool._evaluate_scaling(queue_size=100)
            assert pool._current_workers <= 4
        finally:
            await pool.shutdown()

    @pytest.mark.asyncio
    async def test_scale_respects_min(self):
        """Workers should not go below min_workers."""
        lab = _mock_lab()
        cfg = ScalingConfig(min_workers=2, max_workers=8, cooldown_period=0, scale_down_factor=0.1)
        pool = await ScalableWorkerPool.create(lab, cfg)
        try:
            pool._last_scale_time = 0
            await pool._evaluate_scaling(queue_size=20)
            pool._last_scale_time = 0
            await pool._evaluate_scaling(queue_size=0)
            assert pool._current_workers >= 2
        finally:
            await pool.shutdown()

    @pytest.mark.asyncio
    async def test_peak_workers_tracked(self):
        lab = _mock_lab()
        cfg = ScalingConfig(min_workers=2, max_workers=8, cooldown_period=0)
        pool = await ScalableWorkerPool.create(lab, cfg)
        try:
            pool._last_scale_time = 0
            await pool._evaluate_scaling(queue_size=20)
            assert pool.metrics.peak_workers >= pool._current_workers
        finally:
            await pool.shutdown()


# ====================================================================
# ScalableWorkerPool — shutdown
# ====================================================================

class TestScalableWorkerPoolShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_stops_workers(self):
        lab = _mock_lab()
        pool = await ScalableWorkerPool.create(lab)
        assert pool.current_workers == 2
        await pool.shutdown()
        assert pool.current_workers == 0

    @pytest.mark.asyncio
    async def test_shutdown_cancels_monitor(self):
        lab = _mock_lab()
        pool = await ScalableWorkerPool.create(lab)
        assert pool._monitor_task is not None
        await pool.shutdown()
        assert pool._monitor_task.done()


# ====================================================================
# ParallelLab auto_scale integration
# ====================================================================

class TestParallelLabAutoScale:
    def test_default_auto_scale_off(self):
        from jagabot.lab.parallel import ParallelLab
        plab = ParallelLab()
        assert plab._auto_scale is False
        assert plab._pool is None

    def test_auto_scale_on(self):
        from jagabot.lab.parallel import ParallelLab
        plab = ParallelLab(auto_scale=True)
        assert plab._auto_scale is True

    @pytest.mark.asyncio
    async def test_submit_to_pool_without_auto_scale(self):
        """When auto_scale=False, submit_to_pool falls back to submit_and_execute."""
        from jagabot.lab.parallel import ParallelLab
        lab = _mock_lab()
        plab = ParallelLab(lab=lab, auto_scale=False)
        tasks = [{"tool": "monte_carlo", "params": {"n": 100}, "priority": 5}]
        result = await plab.submit_to_pool(tasks, timeout=5.0)
        assert result["total"] == 1

    @pytest.mark.asyncio
    async def test_submit_to_pool_with_auto_scale(self):
        """When auto_scale=True, submit_to_pool routes through ScalableWorkerPool."""
        from jagabot.lab.parallel import ParallelLab
        lab = _mock_lab()
        cfg = ScalingConfig(min_workers=2, max_workers=4)
        plab = ParallelLab(lab=lab, auto_scale=True, scaling_config=cfg)
        tasks = [{"tool": "monte_carlo", "params": {"n": 100}}]
        result = await plab.submit_to_pool(tasks, timeout=5.0)
        assert result["completed"] == 1
        assert plab._pool is not None
        await plab.shutdown_pool()

    @pytest.mark.asyncio
    async def test_get_scaling_metrics_empty(self):
        from jagabot.lab.parallel import ParallelLab
        plab = ParallelLab()
        m = await plab.get_scaling_metrics()
        assert m == {}

    @pytest.mark.asyncio
    async def test_get_scaling_metrics_with_pool(self):
        from jagabot.lab.parallel import ParallelLab
        lab = _mock_lab()
        cfg = ScalingConfig(min_workers=2, max_workers=4)
        plab = ParallelLab(lab=lab, auto_scale=True, scaling_config=cfg)
        await plab.submit_to_pool([{"tool": "mc", "params": {}}], timeout=5.0)
        m = await plab.get_scaling_metrics()
        assert "peak_workers" in m
        assert "total_tasks_processed" in m
        await plab.shutdown_pool()

    @pytest.mark.asyncio
    async def test_shutdown_pool(self):
        from jagabot.lab.parallel import ParallelLab
        lab = _mock_lab()
        plab = ParallelLab(lab=lab, auto_scale=True)
        await plab.submit_to_pool([{"tool": "mc", "params": {}}], timeout=5.0)
        assert plab._pool is not None
        await plab.shutdown_pool()
        assert plab._pool is None
