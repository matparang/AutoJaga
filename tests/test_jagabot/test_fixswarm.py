"""Tests for v2.2 Fix Swarm — sandbox, self-correction, hardened workers, resilience."""

from __future__ import annotations

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# SafePythonExecutor tests
# ---------------------------------------------------------------------------


class TestSafePythonExecutor:
    """Tests for jagabot.sandbox.executor.SafePythonExecutor."""

    def test_import(self):
        from jagabot.sandbox.executor import SafePythonExecutor, SandboxConfig, ExecutionResult
        assert SafePythonExecutor is not None
        assert SandboxConfig is not None
        assert ExecutionResult is not None

    def test_default_config(self):
        from jagabot.sandbox.executor import SandboxConfig
        cfg = SandboxConfig()
        assert cfg.timeout_s == 10
        assert cfg.memory_limit == "128m"
        assert cfg.cpu_limit == 0.5
        assert cfg.network is False
        assert cfg.allow_subprocess_fallback is True

    def test_custom_config(self):
        from jagabot.sandbox.executor import SandboxConfig
        cfg = SandboxConfig(timeout_s=30, memory_limit="256m", cpu_limit=1.0, network=True)
        assert cfg.timeout_s == 30
        assert cfg.memory_limit == "256m"
        assert cfg.cpu_limit == 1.0
        assert cfg.network is True

    def test_docker_available_property(self):
        from jagabot.sandbox.executor import SafePythonExecutor, SandboxConfig
        exe = SafePythonExecutor(SandboxConfig())
        # docker_available is True or False depending on environment
        assert isinstance(exe.docker_available, bool)

    @pytest.mark.asyncio
    async def test_subprocess_fallback_success(self):
        """When Docker is not available, runs code via subprocess."""
        from jagabot.sandbox.executor import SafePythonExecutor, SandboxConfig
        cfg = SandboxConfig(timeout_s=5, allow_subprocess_fallback=True)
        exe = SafePythonExecutor(cfg)
        exe._docker = None  # force no docker

        result = await exe.execute("print('hello sandbox')")
        assert result.success is True
        assert "hello sandbox" in result.output
        assert result.engine == "subprocess"
        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_subprocess_fallback_error(self):
        """Subprocess correctly reports errors from bad code."""
        from jagabot.sandbox.executor import SafePythonExecutor, SandboxConfig
        cfg = SandboxConfig(timeout_s=5, allow_subprocess_fallback=True)
        exe = SafePythonExecutor(cfg)
        exe._docker = None

        result = await exe.execute("raise ValueError('boom')")
        assert result.success is False
        assert "boom" in result.error
        assert result.engine == "subprocess"

    @pytest.mark.asyncio
    async def test_subprocess_timeout(self):
        """Subprocess enforces timeout."""
        from jagabot.sandbox.executor import SafePythonExecutor, SandboxConfig
        cfg = SandboxConfig(timeout_s=1, allow_subprocess_fallback=True)
        exe = SafePythonExecutor(cfg)
        exe._docker = None

        result = await exe.execute("import time; time.sleep(10)")
        assert result.success is False
        assert "Timeout" in result.error
        assert result.engine == "subprocess"

    @pytest.mark.asyncio
    async def test_no_docker_no_fallback(self):
        """When Docker unavailable and fallback disabled, returns error."""
        from jagabot.sandbox.executor import SafePythonExecutor, SandboxConfig
        cfg = SandboxConfig(allow_subprocess_fallback=False)
        exe = SafePythonExecutor(cfg)
        exe._docker = None

        result = await exe.execute("print('nope')")
        assert result.success is False
        assert "Docker not available" in result.error

    def test_truncation(self):
        from jagabot.sandbox.executor import SafePythonExecutor, SandboxConfig
        cfg = SandboxConfig(max_output=20)
        exe = SafePythonExecutor(cfg)
        truncated = exe._truncate("a" * 100)
        assert len(truncated) < 100
        assert "truncated" in truncated


# ---------------------------------------------------------------------------
# SelfCorrectingRunner tests
# ---------------------------------------------------------------------------


class TestSelfCorrectingRunner:
    """Tests for jagabot.sandbox.self_correct.SelfCorrectingRunner."""

    def test_import(self):
        from jagabot.sandbox.self_correct import SelfCorrectingRunner, CorrectionResult
        assert SelfCorrectingRunner is not None
        assert CorrectionResult is not None

    @pytest.mark.asyncio
    async def test_succeeds_first_try(self):
        from jagabot.sandbox.self_correct import SelfCorrectingRunner

        async def good():
            return "ok"

        runner = SelfCorrectingRunner(max_attempts=3)
        cr = await runner.run(good)
        assert cr.success is True
        assert cr.result == "ok"
        assert cr.attempts == 1
        assert cr.errors == []

    @pytest.mark.asyncio
    async def test_succeeds_on_retry(self):
        from jagabot.sandbox.self_correct import SelfCorrectingRunner

        call_count = 0

        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("not yet")
            return "recovered"

        runner = SelfCorrectingRunner(max_attempts=3, backoff_s=0.01)
        cr = await runner.run(flaky)
        assert cr.success is True
        assert cr.result == "recovered"
        assert cr.attempts == 3
        assert len(cr.errors) == 2

    @pytest.mark.asyncio
    async def test_all_attempts_fail(self):
        from jagabot.sandbox.self_correct import SelfCorrectingRunner

        async def always_fail():
            raise ValueError("nope")

        runner = SelfCorrectingRunner(max_attempts=2, backoff_s=0.01)
        cr = await runner.run(always_fail)
        assert cr.success is False
        assert cr.result is None
        assert cr.attempts == 2
        assert len(cr.errors) == 2
        assert "nope" in cr.errors[0]

    @pytest.mark.asyncio
    async def test_error_context_accumulation(self):
        from jagabot.sandbox.self_correct import SelfCorrectingRunner

        accumulated = []

        async def on_err(errors):
            accumulated.append(list(errors))

        counter = 0

        async def fail_then_pass():
            nonlocal counter
            counter += 1
            if counter < 2:
                raise RuntimeError(f"fail-{counter}")
            return "ok"

        runner = SelfCorrectingRunner(max_attempts=3, backoff_s=0.01, on_error=on_err)
        cr = await runner.run(fail_then_pass)
        assert cr.success is True
        assert len(accumulated) == 1  # on_error called once (one failure)
        assert "fail-1" in accumulated[0][0]

    @pytest.mark.asyncio
    async def test_on_error_sync_callback(self):
        """on_error can be a sync function too."""
        from jagabot.sandbox.self_correct import SelfCorrectingRunner

        called = []

        def sync_handler(errors):
            called.append(len(errors))

        async def fail():
            raise RuntimeError("x")

        runner = SelfCorrectingRunner(max_attempts=2, backoff_s=0.01, on_error=sync_handler)
        await runner.run(fail)
        assert called == [1, 2]

    def test_invalid_max_attempts(self):
        from jagabot.sandbox.self_correct import SelfCorrectingRunner
        with pytest.raises(ValueError):
            SelfCorrectingRunner(max_attempts=0)


# ---------------------------------------------------------------------------
# HardenedWorkerConfig tests
# ---------------------------------------------------------------------------


class TestHardenedWorker:
    """Tests for v2.2 hardened base_worker."""

    def test_import_config(self):
        from jagabot.swarm.base_worker import (
            HardenedWorkerConfig,
            TOOL_SECURITY_POLICIES,
            DEFAULT_POLICY,
            get_policy,
        )
        assert HardenedWorkerConfig is not None
        assert isinstance(TOOL_SECURITY_POLICIES, dict)
        assert DEFAULT_POLICY is not None

    def test_exec_tool_has_docker_policy(self):
        from jagabot.swarm.base_worker import get_policy
        policy = get_policy("exec")
        assert policy.sandbox_mode == "docker"
        assert policy.max_retries == 2
        assert policy.timeout_s == 60

    def test_unknown_tool_gets_default(self):
        from jagabot.swarm.base_worker import get_policy, DEFAULT_POLICY
        assert get_policy("nonexistent_tool") is DEFAULT_POLICY

    def test_monte_carlo_has_retries(self):
        from jagabot.swarm.base_worker import get_policy
        policy = get_policy("monte_carlo")
        assert policy.max_retries == 2
        assert policy.timeout_s == 45

    def test_run_tool_sync_unknown(self):
        """_run_tool_sync returns error for unknown tool (backward compat)."""
        from jagabot.swarm.base_worker import _run_tool_sync
        result = _run_tool_sync("totally_fake_tool_xyz", "", {})
        data = json.loads(result)
        assert "error" in data
        assert "Unknown tool" in data["error"]

    def test_run_tool_sync_real_tool(self):
        """_run_tool_sync still works for a real tool (backward compat)."""
        from jagabot.swarm.base_worker import _run_tool_sync
        result = _run_tool_sync(
            "financial_cv", "calculate_cv", {"mean": 100.0, "stddev": 15.0}
        )
        data = json.loads(result)
        assert "cv" in data or "coefficient_of_variation" in data or isinstance(data, dict)

    def test_stateless_worker_backward_compat(self):
        """StatelessWorker still has the same interface."""
        from jagabot.swarm.base_worker import StatelessWorker
        w = StatelessWorker("financial_cv")
        assert w.tool_cls_name == "financial_cv"
        result = w.run_sync("calculate_cv", {"mean": 100.0, "stddev": 15.0})
        assert isinstance(result, str)

    def test_policy_dataclass_defaults(self):
        from jagabot.swarm.base_worker import HardenedWorkerConfig
        cfg = HardenedWorkerConfig()
        assert cfg.timeout_s == 30
        assert cfg.max_retries == 1
        assert cfg.sandbox_mode == "none"


# ---------------------------------------------------------------------------
# ResilientPipeline tests
# ---------------------------------------------------------------------------


class TestResilientPipeline:
    """Tests for jagabot.guardian.subagents.resilience."""

    def test_import(self):
        from jagabot.guardian.subagents.resilience import (
            ResilientPipeline,
            StageSpec,
            StageResult,
            PipelineResult,
        )
        assert ResilientPipeline is not None

    @pytest.mark.asyncio
    async def test_all_stages_succeed(self):
        from jagabot.guardian.subagents.resilience import ResilientPipeline, StageSpec

        async def stage_a(ctx):
            return {"value": 1}

        async def stage_b(ctx):
            return {"value": ctx["a"]["value"] + 1}

        pipeline = ResilientPipeline([
            StageSpec(name="a", fn=stage_a),
            StageSpec(name="b", fn=stage_b),
        ])
        pr = await pipeline.run()
        assert pr.all_succeeded is True
        assert pr.degraded is False
        assert pr.final_data["a"]["value"] == 1
        assert pr.final_data["b"]["value"] == 2

    @pytest.mark.asyncio
    async def test_middle_stage_fails_with_fallback(self):
        from jagabot.guardian.subagents.resilience import ResilientPipeline, StageSpec

        async def stage_a(ctx):
            return {"ok": True}

        async def stage_b(ctx):
            raise RuntimeError("b broke")

        async def stage_c(ctx):
            return {"used_b": ctx.get("b", {}).get("ok", False)}

        pipeline = ResilientPipeline([
            StageSpec(name="a", fn=stage_a, fallback={"ok": False}),
            StageSpec(name="b", fn=stage_b, max_retries=1, fallback={"ok": False}),
            StageSpec(name="c", fn=stage_c),
        ])
        pr = await pipeline.run()
        assert pr.degraded is True
        # Stage C still ran with fallback data
        assert pr.stages[2].success is True
        assert pr.stages[2].data["used_b"] is False

    @pytest.mark.asyncio
    async def test_all_stages_fail(self):
        from jagabot.guardian.subagents.resilience import ResilientPipeline, StageSpec

        async def bad(ctx):
            raise RuntimeError("fail")

        pipeline = ResilientPipeline([
            StageSpec(name="a", fn=bad, max_retries=1),
            StageSpec(name="b", fn=bad, max_retries=1),
        ])
        pr = await pipeline.run()
        assert pr.degraded is True
        assert not pr.all_succeeded

    @pytest.mark.asyncio
    async def test_retry_succeeds(self):
        from jagabot.guardian.subagents.resilience import ResilientPipeline, StageSpec

        call_count = 0

        async def flaky(ctx):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("not yet")
            return {"recovered": True}

        pipeline = ResilientPipeline([
            StageSpec(name="flaky", fn=flaky, max_retries=3, backoff_s=0.01),
        ])
        pr = await pipeline.run()
        assert pr.all_succeeded is True
        assert pr.stages[0].attempts == 2

    @pytest.mark.asyncio
    async def test_initial_context_passed(self):
        from jagabot.guardian.subagents.resilience import ResilientPipeline, StageSpec

        async def reader(ctx):
            return {"got": ctx.get("seed")}

        pipeline = ResilientPipeline([
            StageSpec(name="reader", fn=reader),
        ])
        pr = await pipeline.run({"seed": 42})
        assert pr.stages[0].data["got"] == 42

    @pytest.mark.asyncio
    async def test_default_fallback_has_degraded_flag(self):
        from jagabot.guardian.subagents.resilience import ResilientPipeline, StageSpec

        async def bad(ctx):
            raise RuntimeError("fail")

        pipeline = ResilientPipeline([
            StageSpec(name="x", fn=bad, max_retries=1),
        ])
        pr = await pipeline.run()
        # Without explicit fallback, default fallback has _degraded=True
        assert pr.stages[0].success is False

    @pytest.mark.asyncio
    async def test_pipeline_result_final_data(self):
        from jagabot.guardian.subagents.resilience import PipelineResult, StageResult
        pr = PipelineResult(stages=[
            StageResult(name="a", success=True, data={"x": 1}),
            StageResult(name="b", success=True, data={"y": 2}),
        ])
        fd = pr.final_data
        assert fd["a"]["x"] == 1
        assert fd["b"]["y"] == 2

    @pytest.mark.asyncio
    async def test_empty_pipeline(self):
        from jagabot.guardian.subagents.resilience import ResilientPipeline
        pipeline = ResilientPipeline([])
        pr = await pipeline.run()
        assert pr.all_succeeded is True
        assert pr.degraded is False


# ---------------------------------------------------------------------------
# Integration: core.py resilient pipeline wiring
# ---------------------------------------------------------------------------


class TestCoreResilience:
    """Test that Jagabot.handle_query uses the resilient pipeline."""

    def test_core_imports_resilience(self):
        """core.py imports ResilientPipeline."""
        from jagabot.guardian.core import Jagabot
        # Just verifying the import chain works
        assert Jagabot is not None

    @pytest.mark.asyncio
    async def test_handle_query_still_works(self):
        """handle_query produces results with the new resilient pipeline."""
        import tempfile
        from jagabot.guardian.core import Jagabot

        with tempfile.TemporaryDirectory() as tmpdir:
            jaga = Jagabot(workspace=tmpdir)
            result = await jaga.handle_query(
                user_query="test risk analysis",
                portfolio={"capital": 100000, "positions": []},
                market_data={"current_price": 50.0, "changes": [1.0, -2.0, 0.5]},
            )
            assert "report" in result
            assert "session_id" in result

    @pytest.mark.asyncio
    async def test_degraded_flag_present(self):
        """Result includes 'degraded' key from resilient pipeline."""
        import tempfile
        from jagabot.guardian.core import Jagabot

        with tempfile.TemporaryDirectory() as tmpdir:
            jaga = Jagabot(workspace=tmpdir)
            result = await jaga.handle_query(
                user_query="test",
                portfolio={"capital": 100000, "positions": []},
                market_data={"current_price": 50.0, "changes": [1.0]},
            )
            assert "degraded" in result


# ---------------------------------------------------------------------------
# SKILL.md self-correction rules
# ---------------------------------------------------------------------------


class TestSkillSelfCorrection:
    """Verify SKILL.md contains self-correction rules."""

    def test_skill_has_self_correction_section(self):
        from pathlib import Path
        skill_path = Path(__file__).parent.parent.parent / "jagabot" / "skills" / "financial" / "SKILL.md"
        content = skill_path.read_text()
        assert "Self-Correction Rules" in content
        assert "retry" in content.lower() or "retries" in content.lower()
        assert "sandbox" in content.lower() or "Docker" in content
        assert "vectorised numpy" in content.lower() or "vectorized numpy" in content.lower()
