"""Tests for v2.3 Fix Sandbox — tracker, config, CLI, verifier, executor integration."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# SandboxTracker tests
# ---------------------------------------------------------------------------


class TestSandboxTracker:
    """Tests for jagabot.sandbox.tracker.SandboxTracker."""

    def _make_tracker(self, tmp_path: Path):
        from jagabot.sandbox.tracker import SandboxTracker
        return SandboxTracker(db_path=tmp_path / "test_sandbox.db")

    def test_import(self):
        from jagabot.sandbox.tracker import SandboxTracker, ExecutionRecord
        assert SandboxTracker is not None
        assert ExecutionRecord is not None

    def test_log_and_count(self, tmp_path):
        tracker = self._make_tracker(tmp_path)
        assert tracker.count() == 0
        row_id = tracker.log_execution(
            code="print(1)", success=True, exec_time_ms=5.0, engine="subprocess"
        )
        assert row_id > 0
        assert tracker.count() == 1
        tracker.close()

    def test_log_with_subagent(self, tmp_path):
        tracker = self._make_tracker(tmp_path)
        tracker.log_execution(
            code="x=1", success=True, exec_time_ms=3.0,
            engine="docker", subagent="billing", calc_type="equity",
        )
        records = tracker.get_recent(1)
        assert len(records) == 1
        assert records[0].subagent == "billing"
        assert records[0].calc_type == "equity"
        assert records[0].engine == "docker"
        tracker.close()

    def test_get_recent_ordering(self, tmp_path):
        tracker = self._make_tracker(tmp_path)
        for i in range(5):
            tracker.log_execution(code=f"print({i})", success=True, exec_time_ms=float(i))
        records = tracker.get_recent(3)
        assert len(records) == 3
        # Most recent first
        assert records[0].id > records[1].id > records[2].id
        tracker.close()

    def test_get_usage_report(self, tmp_path):
        tracker = self._make_tracker(tmp_path)
        tracker.log_execution(code="a", success=True, exec_time_ms=10.0, subagent="billing")
        tracker.log_execution(code="b", success=False, exec_time_ms=5.0, subagent="billing")
        tracker.log_execution(code="c", success=True, exec_time_ms=8.0, subagent="support")
        report = tracker.get_usage_report()
        assert len(report) == 2
        billing_row = next(r for r in report if r["subagent"] == "billing")
        assert billing_row["total"] == 2
        assert billing_row["successes"] == 1
        tracker.close()

    def test_clear(self, tmp_path):
        tracker = self._make_tracker(tmp_path)
        tracker.log_execution(code="x", success=True, exec_time_ms=1.0)
        tracker.log_execution(code="y", success=True, exec_time_ms=2.0)
        deleted = tracker.clear()
        assert deleted == 2
        assert tracker.count() == 0
        tracker.close()

    def test_get_executions_for_session(self, tmp_path):
        tracker = self._make_tracker(tmp_path)
        tracker.log_execution(code="a", success=True, exec_time_ms=1.0, subagent="s1")
        # All records use CURRENT_TIMESTAMP so they should all be after a past date
        records = tracker.get_executions_for_session("2000-01-01")
        assert len(records) >= 1
        tracker.close()

    def test_code_hash_computed(self, tmp_path):
        tracker = self._make_tracker(tmp_path)
        tracker.log_execution(code="print('hello')", success=True, exec_time_ms=1.0)
        records = tracker.get_recent(1)
        assert len(records[0].code_hash) == 32  # MD5 hex
        tracker.close()


# ---------------------------------------------------------------------------
# Config schema tests
# ---------------------------------------------------------------------------


class TestSandboxConfig:
    """Tests for SandboxToolConfig in Pydantic schema."""

    def test_default_sandbox_config(self):
        from jagabot.config.schema import Config
        cfg = Config()
        scfg = cfg.tools.sandbox
        assert scfg.timeout == 10
        assert scfg.memory_limit == "128m"
        assert scfg.cpu_limit == 0.5
        assert scfg.network is False
        assert scfg.allow_fallback is True
        assert scfg.log_executions is True
        assert scfg.force_fallback is False

    def test_sandbox_config_in_json_roundtrip(self):
        from jagabot.config.schema import Config
        cfg = Config()
        cfg.tools.sandbox.timeout = 30
        cfg.tools.sandbox.memory_limit = "256m"
        data = cfg.model_dump()
        assert data["tools"]["sandbox"]["timeout"] == 30
        assert data["tools"]["sandbox"]["memory_limit"] == "256m"

    def test_from_pydantic(self):
        from jagabot.config.schema import Config
        from jagabot.sandbox.executor import SandboxConfig
        cfg = Config()
        cfg.tools.sandbox.timeout = 20
        cfg.tools.sandbox.force_fallback = True
        scfg = SandboxConfig.from_pydantic(cfg.tools.sandbox)
        assert scfg.timeout_s == 20
        assert scfg.force_fallback is True
        assert scfg.allow_subprocess_fallback is True


# ---------------------------------------------------------------------------
# Executor + Tracker integration tests
# ---------------------------------------------------------------------------


class TestExecutorTrackerIntegration:
    """Test SafePythonExecutor with SandboxTracker wired in."""

    @pytest.mark.asyncio
    async def test_execute_logs_to_tracker(self, tmp_path):
        from jagabot.sandbox.executor import SafePythonExecutor, SandboxConfig
        from jagabot.sandbox.tracker import SandboxTracker

        tracker = SandboxTracker(db_path=tmp_path / "int_test.db")
        cfg = SandboxConfig(allow_subprocess_fallback=True)
        exe = SafePythonExecutor(cfg, tracker=tracker)
        exe._docker = None  # force subprocess

        result = await exe.execute("print(42)", subagent="test_agent", calc_type="test_calc")
        assert result.success is True
        assert tracker.count() == 1

        records = tracker.get_recent(1)
        assert records[0].subagent == "test_agent"
        assert records[0].calc_type == "test_calc"
        assert records[0].success is True
        tracker.close()

    @pytest.mark.asyncio
    async def test_execute_logs_failure(self, tmp_path):
        from jagabot.sandbox.executor import SafePythonExecutor, SandboxConfig
        from jagabot.sandbox.tracker import SandboxTracker

        tracker = SandboxTracker(db_path=tmp_path / "fail_test.db")
        cfg = SandboxConfig(allow_subprocess_fallback=True)
        exe = SafePythonExecutor(cfg, tracker=tracker)
        exe._docker = None

        result = await exe.execute("raise ValueError('boom')", subagent="billing")
        assert result.success is False
        assert tracker.count() == 1
        records = tracker.get_recent(1)
        assert records[0].success is False
        tracker.close()

    @pytest.mark.asyncio
    async def test_force_fallback_skips_docker(self, tmp_path):
        from jagabot.sandbox.executor import SafePythonExecutor, SandboxConfig
        cfg = SandboxConfig(force_fallback=True)
        exe = SafePythonExecutor(cfg)
        # Even if docker binary exists, force_fallback makes docker_available False
        assert exe.docker_available is False

        result = await exe.execute("print('fallback')")
        assert result.success is True
        assert result.engine == "subprocess"

    @pytest.mark.asyncio
    async def test_no_tracker_still_works(self):
        from jagabot.sandbox.executor import SafePythonExecutor, SandboxConfig
        cfg = SandboxConfig()
        exe = SafePythonExecutor(cfg, tracker=None)
        exe._docker = None
        result = await exe.execute("print('ok')")
        assert result.success is True


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestSandboxCLI:
    """Test sandbox CLI commands via Typer test runner."""

    def test_cli_import(self):
        from jagabot.cli.sandbox import sandbox_app
        assert sandbox_app is not None

    def test_status_command(self):
        from typer.testing import CliRunner
        from jagabot.cli.sandbox import sandbox_app
        runner = CliRunner()
        result = runner.invoke(sandbox_app, ["status"])
        assert result.exit_code == 0
        assert "Docker" in result.output

    def test_test_command(self):
        from typer.testing import CliRunner
        from jagabot.cli.sandbox import sandbox_app
        runner = CliRunner()
        result = runner.invoke(sandbox_app, ["test", "--timeout", "5"])
        assert result.exit_code == 0
        # Should show engine used
        assert "Engine" in result.output

    def test_config_command(self):
        from typer.testing import CliRunner
        from jagabot.cli.sandbox import sandbox_app
        runner = CliRunner()
        result = runner.invoke(sandbox_app, ["config"])
        assert result.exit_code == 0
        assert "timeout" in result.output
        assert "memory_limit" in result.output

    def test_logs_command_empty(self):
        from typer.testing import CliRunner
        from jagabot.cli.sandbox import sandbox_app
        runner = CliRunner()
        result = runner.invoke(sandbox_app, ["logs"])
        # May be empty or have records — just shouldn't crash
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# SandboxVerifier tests
# ---------------------------------------------------------------------------


class TestSandboxVerifier:
    """Tests for jagabot.sandbox.verifier."""

    def test_import(self):
        from jagabot.sandbox.verifier import SandboxVerifier, VerificationReport
        assert SandboxVerifier is not None
        assert VerificationReport is not None

    def test_expected_calculations(self):
        from jagabot.sandbox.verifier import SandboxVerifier
        v = SandboxVerifier.__new__(SandboxVerifier)
        v.tracker = None
        expected = v.get_expected_calculations()
        assert "monte_carlo" in expected
        assert "equity" in expected
        assert "bayesian" in expected
        assert len(expected) > 5

    def test_expected_for_single_phase(self):
        from jagabot.sandbox.verifier import SandboxVerifier
        v = SandboxVerifier.__new__(SandboxVerifier)
        v.tracker = None
        expected = v.get_expected_calculations(["billing"])
        assert "monte_carlo" in expected
        assert "bayesian" not in expected

    def test_verify_all_present(self, tmp_path):
        from jagabot.sandbox.tracker import SandboxTracker
        from jagabot.sandbox.verifier import SandboxVerifier

        tracker = SandboxTracker(db_path=tmp_path / "verify.db")
        # Log all expected calc types
        for ct in ["cv_analysis", "early_warning", "monte_carlo", "equity",
                    "margin_call", "confidence_interval", "bayesian",
                    "sensitivity", "pareto"]:
            tracker.log_execution(code=ct, success=True, exec_time_ms=1.0, calc_type=ct)

        v = SandboxVerifier(tracker)
        rpt = v.verify_analysis("2000-01-01")
        assert rpt.verified is True
        assert rpt.coverage_pct == 100.0
        assert rpt.missing == []
        tracker.close()

    def test_verify_missing_calcs(self, tmp_path):
        from jagabot.sandbox.tracker import SandboxTracker
        from jagabot.sandbox.verifier import SandboxVerifier

        tracker = SandboxTracker(db_path=tmp_path / "verify_missing.db")
        # Only log some
        tracker.log_execution(code="cv", success=True, exec_time_ms=1.0, calc_type="cv_analysis")

        v = SandboxVerifier(tracker)
        rpt = v.verify_analysis("2000-01-01")
        assert rpt.verified is False
        assert len(rpt.missing) > 0
        assert "monte_carlo" in rpt.missing
        assert rpt.coverage_pct < 100.0
        tracker.close()

    def test_quick_check(self, tmp_path):
        from jagabot.sandbox.tracker import SandboxTracker
        from jagabot.sandbox.verifier import SandboxVerifier

        tracker = SandboxTracker(db_path=tmp_path / "quick.db")
        v = SandboxVerifier(tracker)
        msg = v.quick_check("2000-01-01")
        # Nothing logged — should be missing
        assert "❌" in msg
        tracker.close()

    def test_verify_empty_phases(self, tmp_path):
        from jagabot.sandbox.tracker import SandboxTracker
        from jagabot.sandbox.verifier import SandboxVerifier

        tracker = SandboxTracker(db_path=tmp_path / "empty.db")
        v = SandboxVerifier(tracker)
        rpt = v.verify_analysis("2000-01-01", phases=["web"])
        # web has no expected calcs
        assert rpt.verified is True
        assert rpt.total_expected == 0
        assert rpt.coverage_pct == 100.0
        tracker.close()

    def test_verification_report_dataclass(self):
        from jagabot.sandbox.verifier import VerificationReport
        rpt = VerificationReport(
            verified=True, total_expected=5, total_actual=5,
            coverage_pct=100.0, missing=[]
        )
        assert rpt.verified is True


# ---------------------------------------------------------------------------
# Regression: existing fixswarm tests still import
# ---------------------------------------------------------------------------


class TestBackwardCompat:
    """Verify v2.2 fixswarm imports still work after v2.3 changes."""

    def test_sandbox_init_exports(self):
        from jagabot.sandbox import (
            SafePythonExecutor,
            SandboxConfig,
            ExecutionResult,
            SelfCorrectingRunner,
            SandboxTracker,
            SandboxVerifier,
        )
        assert all([
            SafePythonExecutor, SandboxConfig, ExecutionResult,
            SelfCorrectingRunner, SandboxTracker, SandboxVerifier,
        ])

    def test_executor_backward_compat_no_tracker(self):
        """Executor works without tracker arg (v2.2 API)."""
        from jagabot.sandbox.executor import SafePythonExecutor, SandboxConfig
        exe = SafePythonExecutor(SandboxConfig())
        assert exe.tracker is None

    @pytest.mark.asyncio
    async def test_executor_execute_without_subagent_kwarg(self):
        """execute() works without subagent/calc_type kwargs (v2.2 API)."""
        from jagabot.sandbox.executor import SafePythonExecutor, SandboxConfig
        exe = SafePythonExecutor(SandboxConfig(allow_subprocess_fallback=True))
        exe._docker = None
        result = await exe.execute("print('compat')")
        assert result.success is True
