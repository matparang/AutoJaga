"""Tests for v2.1 Vadim Upgrade: tracker, dashboard, scheduler, costs, watchdog, new tools."""

import json
import os
import tempfile
import time
import pytest

from jagabot.agent.tools.registry import ToolRegistry


# ========================= WorkerTracker =========================

from jagabot.swarm.status import WorkerTracker, WorkerState, WorkerInfo


class TestWorkerTracker:
    def test_register_and_active(self):
        t = WorkerTracker()
        t.register("t1", "var", "parametric_var")
        active = t.active_workers()
        assert len(active) == 1
        assert active[0].tool_name == "var"
        assert active[0].state == WorkerState.RUNNING

    def test_mark_done(self):
        t = WorkerTracker()
        t.register("t1", "var")
        t.mark_done("t1", success=True)
        assert len(t.active_workers()) == 0
        history = t.recent_history()
        assert len(history) == 1
        assert history[0].state == WorkerState.DONE

    def test_mark_done_error(self):
        t = WorkerTracker()
        t.register("t1", "cvar")
        t.mark_done("t1", success=False, error="timeout")
        history = t.recent_history()
        assert history[0].state == WorkerState.ERROR
        assert history[0].error == "timeout"

    def test_heartbeat(self):
        t = WorkerTracker()
        t.register("t1", "mc")
        first_time = t._workers["t1"].started_at
        time.sleep(0.01)
        t.heartbeat("t1")
        assert t._workers["t1"].started_at > first_time

    def test_detect_stalled(self):
        t = WorkerTracker(stall_timeout=0.01)
        t.register("t1", "slow_tool")
        time.sleep(0.02)
        stalled = t.detect_stalled()
        assert len(stalled) == 1
        assert stalled[0].state == WorkerState.STALLED

    def test_stats(self):
        t = WorkerTracker()
        t.register("t1", "var")
        t.register("t2", "cvar")
        t.mark_done("t1", success=True)
        stats = t.stats()
        assert stats["running"] == 1
        assert stats["completed"] == 1
        assert stats["errors"] == 0

    def test_clear(self):
        t = WorkerTracker()
        t.register("t1", "var")
        t.mark_done("t1")
        t.clear()
        assert t.stats()["completed"] == 0
        assert len(t.active_workers()) == 0


# ========================= Dashboard =========================

from jagabot.swarm.dashboard import generate_dashboard


class TestDashboard:
    def test_generate_basic(self):
        t = WorkerTracker()
        output = generate_dashboard(t)
        assert "MISSION CONTROL" in output
        assert "Workers" in output

    def test_with_active_workers(self):
        t = WorkerTracker()
        t.register("t1", "var", "parametric_var")
        output = generate_dashboard(t)
        assert "Running:" in output
        assert "var" in output

    def test_with_orchestrator_status(self):
        t = WorkerTracker()
        output = generate_dashboard(t, orchestrator_status={
            "max_workers": 4, "available_tools": 21, "total_analyses": 5,
        })
        assert "Max Workers: 4" in output

    def test_with_cost_summary(self):
        t = WorkerTracker()
        output = generate_dashboard(t, cost_summary={
            "daily": 0.05, "monthly": 1.20, "budgets": {"daily": 1.0},
        })
        assert "$0.05" in output

    def test_with_watchdog_health(self):
        t = WorkerTracker()
        output = generate_dashboard(t, watchdog_health={
            "running": True, "total_alerts": 3, "recent_critical": 0,
            "system": {"note": "psutil not installed"},
        })
        assert "Alerts: 3" in output


# ========================= Scheduler =========================

from jagabot.swarm.scheduler import SwarmScheduler


class TestSwarmScheduler:
    def test_add_workflow(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            s = SwarmScheduler(store_path=__import__("pathlib").Path(path))
            job = s.add_workflow("Test", "Analyze risk", "0 8 * * *")
            assert job.name == "Test"
            assert job.payload.message == "Analyze risk"
        finally:
            os.unlink(path)

    def test_list_workflows(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            s = SwarmScheduler(store_path=__import__("pathlib").Path(path))
            s.add_workflow("W1", "query1", "0 8 * * *")
            s.add_workflow("W2", "query2", "0 9 * * *")
            workflows = s.list_workflows()
            assert len(workflows) == 2
        finally:
            os.unlink(path)

    def test_remove_workflow(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            s = SwarmScheduler(store_path=__import__("pathlib").Path(path))
            job = s.add_workflow("Removable", "query", "0 8 * * *")
            assert s.remove_workflow(job.id)
            assert len(s.list_workflows()) == 0
        finally:
            os.unlink(path)

    def test_status(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            s = SwarmScheduler(store_path=__import__("pathlib").Path(path))
            status = s.status()
            assert "enabled" in status
            assert "workflows" in status
        finally:
            os.unlink(path)


# ========================= Workflows =========================

from jagabot.swarm.workflows import PRESETS, get_preset, list_presets


class TestWorkflows:
    def test_has_4_presets(self):
        assert len(PRESETS) == 4

    def test_market_monitor(self):
        p = get_preset("market_monitor")
        assert p is not None
        assert "market" in p.query.lower()

    def test_daily_risk(self):
        p = get_preset("daily_risk")
        assert p is not None
        assert "risk" in p.query.lower()

    def test_list_presets(self):
        presets = list_presets()
        assert len(presets) == 4
        names = {p.name for p in presets}
        assert "Daily Risk Report" in names


# ========================= CostTracker =========================

from jagabot.swarm.costs import CostTracker


class TestCostTracker:
    def _tmp_tracker(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            return CostTracker(db_path=f.name), f.name

    def test_record_and_daily(self):
        ct, path = self._tmp_tracker()
        try:
            ct.record("var", method="parametric_var")
            ct.record("monte_carlo")
            daily = ct.daily_total()
            assert daily > 0
        finally:
            ct.shutdown()
            os.unlink(path)

    def test_by_tool(self):
        ct, path = self._tmp_tracker()
        try:
            ct.record("var")
            ct.record("var")
            ct.record("cvar")
            breakdown = ct.by_tool()
            assert len(breakdown) == 2
            var_entry = [b for b in breakdown if b["tool"] == "var"][0]
            assert var_entry["invocations"] == 2
        finally:
            ct.shutdown()
            os.unlink(path)

    def test_set_budget_and_alerts(self):
        ct, path = self._tmp_tracker()
        try:
            ct.set_budget("daily", 0.0001)
            ct.record("var")
            ct.record("cvar")
            alerts = ct.recent_alerts()
            assert len(alerts) >= 1
        finally:
            ct.shutdown()
            os.unlink(path)

    def test_summary(self):
        ct, path = self._tmp_tracker()
        try:
            ct.record("var")
            s = ct.summary()
            assert "daily" in s
            assert "monthly" in s
            assert "by_tool" in s
        finally:
            ct.shutdown()
            os.unlink(path)

    def test_monthly_total(self):
        ct, path = self._tmp_tracker()
        try:
            ct.record("var")
            assert ct.monthly_total() > 0
        finally:
            ct.shutdown()
            os.unlink(path)


# ========================= Watchdog =========================

from jagabot.swarm.watchdog import Watchdog, Alert


class TestWatchdog:
    def test_start_stop(self):
        wd = Watchdog(check_interval=0.1)
        wd.start()
        assert wd.is_running()
        wd.stop()
        assert not wd.is_running()

    def test_health(self):
        wd = Watchdog()
        health = wd.health()
        assert "running" in health
        assert "system" in health

    def test_stalled_detection(self):
        tracker = WorkerTracker(stall_timeout=0.01)
        tracker.register("stalled_task", "slow_tool")
        time.sleep(0.02)
        wd = Watchdog(check_interval=0.05)
        wd.set_tracker(tracker)
        wd._check_workers()
        alerts = wd.get_alerts()
        assert len(alerts) >= 1
        assert "stalled" in alerts[0].message.lower()

    def test_cost_alert_detection(self):
        ct_fd, ct_path = tempfile.mkstemp(suffix=".db")
        os.close(ct_fd)
        try:
            ct = CostTracker(db_path=ct_path)
            ct.set_budget("daily", 0.0001)
            ct.record("var")
            ct.record("cvar")
            wd = Watchdog()
            wd.set_cost_tracker(ct)
            wd._check_costs()
            alerts = wd.get_alerts()
            assert len(alerts) >= 1
            ct.shutdown()
        finally:
            os.unlink(ct_path)

    def test_alert_class(self):
        a = Alert(level="warning", source="test", message="test alert")
        assert a.level == "warning"
        assert a.timestamp > 0


# ========================= Researcher =========================

from jagabot.agent.tools.researcher import ResearcherTool, scan_trends, detect_anomalies


class TestResearcher:
    def test_scan_trends_uptrend(self):
        result = scan_trends([100, 102, 104, 106, 108, 110, 112, 114])
        assert result["direction"] == "uptrend"
        assert result["momentum"] > 0

    def test_scan_trends_downtrend(self):
        result = scan_trends([120, 118, 116, 114, 112, 110, 108, 106])
        assert result["direction"] == "downtrend"

    def test_scan_trends_insufficient(self):
        result = scan_trends([100, 101])
        assert result["trend"] == "insufficient_data"

    def test_detect_anomalies_basic(self):
        values = [1.0, 1.1, 0.9, 1.0, 1.05, 5.0, 1.0, 0.95]
        result = detect_anomalies(values)
        assert result["total"] >= 1
        assert any(a["direction"] == "above" for a in result["anomalies"])

    def test_detect_anomalies_none(self):
        values = [1.0, 1.0, 1.0, 1.0, 1.0]
        result = detect_anomalies(values)
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_tool_execute_trends(self):
        tool = ResearcherTool()
        result = await tool.execute(method="scan_trends", params={
            "data_points": [100, 105, 110, 108, 115, 120]
        })
        data = json.loads(result)
        assert "direction" in data

    @pytest.mark.asyncio
    async def test_tool_execute_anomalies(self):
        tool = ResearcherTool()
        result = await tool.execute(method="detect_anomalies", params={
            "values": [1, 1, 1, 1, 10, 1, 1]
        })
        data = json.loads(result)
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_tool_unknown_method(self):
        tool = ResearcherTool()
        result = await tool.execute(method="unknown")
        data = json.loads(result)
        assert "error" in data

    def test_tool_schema(self):
        tool = ResearcherTool()
        assert tool.name == "researcher"
        schema = tool.to_schema()
        assert schema["function"]["name"] == "researcher"


# ========================= Copywriter =========================

from jagabot.agent.tools.copywriter import CopywriterTool, draft_alert, draft_report_summary


class TestCopywriter:
    def test_draft_alert_high(self):
        result = draft_alert(risk_level="high", tool_name="var", key_metric="VaR", value=5000)
        assert result["risk_level"] == "high"
        assert "🟠" in result["alert"]

    def test_draft_alert_malay(self):
        result = draft_alert(risk_level="critical", locale="ms")
        assert "KRITIKAL" in result["alert"]

    def test_draft_report_summary(self):
        result = draft_report_summary(
            analysis_results={"var": {"var_amount": 5000}},
            query="test analysis",
        )
        assert "summary" in result
        assert result["tool_count"] == 1

    def test_draft_report_summary_empty(self):
        result = draft_report_summary(query="test")
        assert result["tool_count"] == 0

    @pytest.mark.asyncio
    async def test_tool_execute_alert(self):
        tool = CopywriterTool()
        result = await tool.execute(method="draft_alert", params={
            "risk_level": "low", "tool_name": "cvar", "key_metric": "CVaR", "value": 3000,
        })
        data = json.loads(result)
        assert "🟢" in data["alert"]

    @pytest.mark.asyncio
    async def test_tool_execute_summary(self):
        tool = CopywriterTool()
        result = await tool.execute(method="draft_report_summary", params={
            "query": "oil analysis",
        })
        data = json.loads(result)
        assert "summary" in data

    def test_tool_schema(self):
        tool = CopywriterTool()
        assert tool.name == "copywriter"


# ========================= SelfImprover =========================

from jagabot.agent.tools.self_improver import SelfImproverTool, analyze_mistakes, suggest_improvements


class TestSelfImprover:
    def test_analyze_mistakes_optimistic(self):
        preds = [
            {"predicted": 110, "actual": 100, "tool": "mc"},
            {"predicted": 115, "actual": 100, "tool": "mc"},
        ]
        result = analyze_mistakes(preds)
        assert result["bias"] == "optimistic"
        assert result["error_count"] == 2

    def test_analyze_mistakes_empty(self):
        result = analyze_mistakes([])
        assert result["error_count"] == 0

    def test_suggest_improvements_high_mae(self):
        result = suggest_improvements({"bias": "optimistic", "mae": 0.2, "by_tool": {}})
        assert result["total"] >= 2  # calibration + accuracy

    def test_suggest_improvements_good(self):
        result = suggest_improvements({"bias": "neutral", "mae": 0.01, "by_tool": {}})
        assert result["total"] >= 1

    @pytest.mark.asyncio
    async def test_tool_execute_mistakes(self):
        tool = SelfImproverTool()
        result = await tool.execute(method="analyze_mistakes", params={
            "predictions": [{"predicted": 100, "actual": 95}],
        })
        data = json.loads(result)
        assert data["error_count"] == 1

    @pytest.mark.asyncio
    async def test_tool_execute_improvements(self):
        tool = SelfImproverTool()
        result = await tool.execute(method="suggest_improvements", params={
            "analysis_results": {"bias": "pessimistic", "mae": 0.05, "by_tool": {}},
        })
        data = json.loads(result)
        assert data["total"] >= 1

    def test_tool_schema(self):
        tool = SelfImproverTool()
        assert tool.name == "self_improver"


# ========================= Planner v2.1 Categories =========================

from jagabot.swarm.planner import _classify_query


class TestPlannerV21:
    def test_research_category(self):
        cats = _classify_query("scan for trends and anomalies")
        assert "research" in cats

    def test_content_category(self):
        cats = _classify_query("draft alert and report summary")
        assert "content" in cats

    def test_research_malay(self):
        cats = _classify_query("imbas tren pasaran")
        assert "research" in cats

    def test_content_malay(self):
        cats = _classify_query("buat ringkasan laporan")
        assert "content" in cats


# ========================= Stitcher v2.1 Sections =========================

from jagabot.swarm.stitcher import ResultStitcher
from jagabot.swarm.worker_pool import TaskResult


class TestStitcherV21:
    def test_research_section(self):
        results = [
            TaskResult(task_id="r1", tool_name="researcher", method="scan_trends",
                       data={"direction": "uptrend", "strength": 75.0}, success=True, elapsed_s=0.1),
        ]
        s = ResultStitcher()
        report = s.stitch(results, "test")
        assert "Research" in report
        assert "uptrend" in report

    def test_content_section(self):
        results = [
            TaskResult(task_id="c1", tool_name="copywriter", method="draft_alert",
                       data={"alert": "🟡 Moderate alert"}, success=True, elapsed_s=0.1),
            TaskResult(task_id="c2", tool_name="self_improver", method="suggest_improvements",
                       data={"suggestions": [{"priority": "high", "suggestion": "Calibrate models"}], "total": 1},
                       success=True, elapsed_s=0.1),
        ]
        s = ResultStitcher()
        report = s.stitch(results, "test")
        assert "Content" in report
        assert "Moderate alert" in report
        assert "Improvement suggestions" in report


# ========================= Full 21-tool Registration =========================

class TestV21Registration:
    def test_21_tools_in_guardian(self):
        from jagabot.guardian.tools import ALL_TOOLS
        assert len(ALL_TOOLS) == 32

    def test_21_tools_swarm_registry(self):
        from jagabot.swarm.tool_registry import get_tool_count
        assert get_tool_count() == 32

    def test_new_tools_in_swarm_registry(self):
        from jagabot.swarm.tool_registry import get_tool_class
        assert get_tool_class("researcher") is not None
        assert get_tool_class("copywriter") is not None
        assert get_tool_class("self_improver") is not None
