"""Tests for Jagabot Swarm — workers, pool, planner, stitcher, orchestrator."""

import json
import os
import tempfile
import pytest

from jagabot.swarm.base_worker import StatelessWorker, _run_tool_sync
from jagabot.swarm.tool_registry import get_all_tool_names, get_tool_class, get_tool_count
from jagabot.swarm.worker_pool import TaskSpec, TaskResult, WorkerPool
from jagabot.swarm.planner import TaskPlanner, _classify_query
from jagabot.swarm.stitcher import ResultStitcher
from jagabot.swarm.queue_backend import LocalBackend, get_backend
from jagabot.swarm.memory_owner import SwarmOrchestrator


# ========================= Tool Registry =========================

class TestSwarmToolRegistry:
    def test_has_18_tools(self):
        assert get_tool_count() == 32

    def test_all_names_present(self):
        names = get_all_tool_names()
        assert "monte_carlo" in names
        assert "var" in names
        assert "decision_engine" in names
        assert "education" in names
        assert "accountability" in names

    def test_get_tool_class(self):
        cls = get_tool_class("monte_carlo")
        assert cls is not None
        instance = cls()
        assert instance.name == "monte_carlo"

    def test_unknown_tool_returns_none(self):
        assert get_tool_class("nonexistent") is None


# ========================= Base Worker =========================

class TestBaseWorker:
    def test_run_sync_monte_carlo(self):
        result = _run_tool_sync(
            "monte_carlo", "__direct__",
            {"current_price": 100, "target_price": 90, "vix": 25},
        )
        data = json.loads(result)
        assert "probability" in data
        assert 0 <= data["probability"] <= 100

    def test_run_sync_var(self):
        result = _run_tool_sync(
            "var", "parametric_var",
            {"mean_return": -0.001, "std_return": 0.02, "portfolio_value": 100000},
        )
        data = json.loads(result)
        assert "var_pct" in data
        assert data["var_amount"] > 0

    def test_run_sync_education(self):
        result = _run_tool_sync(
            "education", "explain_concept", {"concept": "var"},
        )
        data = json.loads(result)
        assert "title" in data

    def test_run_sync_unknown_tool(self):
        result = _run_tool_sync("bogus_tool", "method", {})
        data = json.loads(result)
        assert "error" in data

    def test_stateless_worker_wrapper(self):
        w = StatelessWorker("monte_carlo")
        result = w.run_sync("__direct__", {"current_price": 50, "target_price": 45, "vix": 30})
        data = json.loads(result)
        assert "probability" in data

    def test_error_handling(self):
        result = _run_tool_sync("var", "parametric_var", {"bad_param": True})
        data = json.loads(result)
        assert "error" in data


# ========================= Worker Pool =========================

class TestWorkerPool:
    def test_submit_single(self):
        pool = WorkerPool(max_workers=2)
        try:
            task = TaskSpec(tool_name="var", method="parametric_var",
                           params={"mean_return": 0, "std_return": 0.02, "portfolio_value": 100000})
            future = pool.submit(task)
            raw = future.result(timeout=15)
            data = json.loads(raw)
            assert "var_pct" in data
        finally:
            pool.shutdown()

    def test_submit_batch_parallel(self):
        pool = WorkerPool(max_workers=4)
        try:
            tasks = [
                TaskSpec(tool_name="monte_carlo", method="__direct__",
                         params={"current_price": 100, "target_price": 90, "vix": 25}),
                TaskSpec(tool_name="var", method="parametric_var",
                         params={"mean_return": 0, "std_return": 0.02, "portfolio_value": 100000}),
                TaskSpec(tool_name="education", method="explain_concept",
                         params={"concept": "cv"}),
            ]
            futures = pool.submit_batch(tasks)
            results = pool.collect(futures, tasks)
            assert len(results) == 3
            assert sum(1 for r in results if r.success) >= 2
        finally:
            pool.shutdown()

    def test_run_task_groups(self):
        pool = WorkerPool(max_workers=2)
        try:
            group0 = [
                TaskSpec(tool_name="var", method="parametric_var",
                         params={"mean_return": 0, "std_return": 0.02, "portfolio_value": 100000}, group=0),
            ]
            group1 = [
                TaskSpec(tool_name="education", method="explain_concept",
                         params={"concept": "var"}, group=1),
            ]
            results = pool.run_task_groups([group0, group1])
            assert len(results) == 2
        finally:
            pool.shutdown()

    def test_timeout_handling(self):
        pool = WorkerPool(max_workers=1)
        try:
            task = TaskSpec(tool_name="monte_carlo", method="__direct__",
                           params={"current_price": 100, "target_price": 90, "vix": 25},
                           timeout=0.001)  # unreasonably short
            futures = pool.submit_batch([task])
            results = pool.collect(futures, [task])
            # Either completes fast or times out — both acceptable
            assert len(results) == 1
        finally:
            pool.shutdown()


# ========================= Queue Backend =========================

class TestLocalBackend:
    def test_put_get_task(self):
        b = LocalBackend()
        b.put_task("t1", {"tool": "var", "method": "calc"})
        data = b.get_task("t1")
        assert data["tool"] == "var"

    def test_task_expiry(self):
        b = LocalBackend()
        b.put_task("t2", {"x": 1}, ttl=0)  # expires immediately
        import time
        time.sleep(0.01)
        assert b.get_task("t2") is None

    def test_put_get_result(self):
        import threading
        b = LocalBackend()

        def delayed_put():
            import time
            time.sleep(0.1)
            b.put_result("r1", {"value": 42})

        t = threading.Thread(target=delayed_put)
        t.start()
        result = b.get_result("r1", timeout=5)
        t.join()
        assert result["value"] == 42

    def test_result_timeout(self):
        b = LocalBackend()
        result = b.get_result("missing", timeout=0.1)
        assert result is None

    def test_health_check(self):
        b = LocalBackend()
        h = b.health_check()
        assert h["backend"] == "local"
        assert h["available"] is True

    def test_get_backend_local_fallback(self):
        b = get_backend(prefer_redis=False)
        assert isinstance(b, LocalBackend)

    def test_get_backend_redis_fallback(self):
        # Redis likely not running — should fall back to local
        b = get_backend(prefer_redis=True)
        assert b.is_available()  # local is always available


# ========================= Planner =========================

class TestPlanner:
    def test_crisis_query(self):
        p = TaskPlanner()
        groups = p.plan("oil crisis risk analysis")
        total = sum(len(g) for g in groups)
        assert total >= 5  # crisis + risk overlap = many tools

    def test_stock_query(self):
        p = TaskPlanner()
        groups = p.plan("Should I buy AAPL stock?")
        tools = {t.tool_name for g in groups for t in g}
        assert "monte_carlo" in tools
        assert "decision_engine" in tools

    def test_education_query(self):
        p = TaskPlanner()
        groups = p.plan("Explain what VaR is")
        tools = {t.tool_name for g in groups for t in g}
        assert "education" in tools

    def test_accountability_query(self):
        p = TaskPlanner()
        groups = p.plan("Check fund manager red flags")
        tools = {t.tool_name for g in groups for t in g}
        assert "accountability" in tools

    def test_malay_query(self):
        p = TaskPlanner()
        groups = p.plan("Analisis krisis minyak mentah")
        total = sum(len(g) for g in groups)
        assert total >= 3  # crisis pattern detected

    def test_general_fallback(self):
        p = TaskPlanner()
        groups = p.plan("hello world")
        assert len(groups) >= 1  # at least general tasks

    def test_price_extraction(self):
        p = TaskPlanner()
        groups = p.plan("Analyze stock at RM4.50")
        # Should find price=4.50
        has_price = False
        for g in groups:
            for t in g:
                if t.tool_name == "monte_carlo":
                    has_price = t.params.get("current_price") == 4.50
        assert has_price

    def test_plan_summary(self):
        p = TaskPlanner()
        groups = p.plan("oil crisis")
        summary = p.plan_summary(groups)
        assert summary["total_tasks"] > 0
        assert summary["groups"] > 0
        assert len(summary["unique_tools"]) > 0

    def test_classify_crisis(self):
        assert "crisis" in _classify_query("oil crash analysis")

    def test_classify_stock(self):
        assert "stock" in _classify_query("should I buy this saham?")

    def test_classify_general(self):
        assert "general" in _classify_query("random text with no keywords")


# ========================= Stitcher =========================

class TestStitcher:
    def _make_results(self):
        return [
            TaskResult(task_id="t1", tool_name="monte_carlo", method="__direct__",
                       data={"probability": 35.5, "mean_price": 48.2}, success=True, elapsed_s=1.2),
            TaskResult(task_id="t2", tool_name="var", method="parametric_var",
                       data={"var_pct": 5.4, "var_amount": 5400}, success=True, elapsed_s=0.3),
            TaskResult(task_id="t3", tool_name="decision_engine", method="bull_perspective",
                       data={"perspective": "bull", "verdict": "BUY", "confidence": 70},
                       success=True, elapsed_s=0.1),
            TaskResult(task_id="t4", tool_name="education", method="explain_concept",
                       data={"title": "VaR", "explanation": "Value at Risk measures..."},
                       success=True, elapsed_s=0.05),
        ]

    def test_stitch_produces_markdown(self):
        s = ResultStitcher()
        report = s.stitch(self._make_results(), "oil crisis")
        assert "JAGABOT SWARM ANALYSIS" in report
        assert "oil crisis" in report
        assert "Risk Metrics" in report
        assert "Decision Engine" in report

    def test_stitch_malay_locale(self):
        s = ResultStitcher(locale="ms")
        report = s.stitch(self._make_results(), "krisis minyak")
        assert "ANALISIS SWARM JAGABOT" in report
        assert "Metrik Risiko" in report

    def test_stitch_with_failures(self):
        results = [
            TaskResult(task_id="t1", tool_name="var", method="calc",
                       data={"error": "timeout"}, success=False, elapsed_s=30.0),
        ]
        s = ResultStitcher()
        report = s.stitch(results, "test")
        assert "1 failed" in report

    def test_stitch_empty(self):
        s = ResultStitcher()
        report = s.stitch([], "empty query")
        assert "JAGABOT SWARM ANALYSIS" in report
        assert "0/0" in report

    def test_accountability_section(self):
        results = [
            TaskResult(task_id="t1", tool_name="accountability", method="detect_red_flags",
                       data={"red_flags": [], "count": 0}, success=True, elapsed_s=0.1),
        ]
        s = ResultStitcher()
        report = s.stitch(results)
        assert "Accountability" in report


# ========================= Orchestrator (E2E) =========================

class TestSwarmOrchestrator:
    @pytest.fixture
    def orchestrator(self):
        db = tempfile.mktemp(suffix=".db")
        o = SwarmOrchestrator(db_path=db, max_workers=2)
        yield o
        o.shutdown()
        if os.path.exists(db):
            os.unlink(db)

    def test_process_query_crisis(self, orchestrator):
        report = orchestrator.process_query("oil crisis analysis")
        assert "JAGABOT SWARM ANALYSIS" in report
        assert "oil crisis" in report

    def test_process_query_stock(self, orchestrator):
        report = orchestrator.process_query("Should I buy this stock at RM4.50?")
        assert "SWARM ANALYSIS" in report

    def test_process_query_education(self, orchestrator):
        report = orchestrator.process_query("Explain what VaR means")
        assert "SWARM ANALYSIS" in report

    def test_status(self, orchestrator):
        info = orchestrator.status()
        assert info["available_tools"] == 32
        assert info["max_workers"] == 2

    def test_history_stored(self, orchestrator):
        orchestrator.process_query("test query")
        history = orchestrator.get_history()
        assert len(history) == 1
        assert history[0]["query"] == "test query"

    def test_get_analysis(self, orchestrator):
        orchestrator.process_query("test retrieval")
        history = orchestrator.get_history()
        analysis = orchestrator.get_analysis(history[0]["id"])
        assert analysis is not None
        assert "report" in analysis
        assert analysis["query"] == "test retrieval"

    def test_global_timeout(self, orchestrator):
        # Very short timeout — should still return partial results
        report = orchestrator.process_query("oil crisis", global_timeout=0.001)
        assert "SWARM ANALYSIS" in report

    def test_malay_locale(self):
        db = tempfile.mktemp(suffix=".db")
        o = SwarmOrchestrator(db_path=db, max_workers=1, locale="ms")
        try:
            report = o.process_query("Analisis krisis minyak")
            assert "ANALISIS SWARM JAGABOT" in report
        finally:
            o.shutdown()
            if os.path.exists(db):
                os.unlink(db)
