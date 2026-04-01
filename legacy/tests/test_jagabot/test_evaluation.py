"""Tests for jagabot v3.0 Phase 1 — K7 Evaluation tool."""

import asyncio
import json

import pytest

from jagabot.agent.tools.evaluation import EvaluationKernel, Evaluation, EvaluationTool


@pytest.fixture
def kernel():
    return EvaluationKernel()


@pytest.fixture
def tool():
    return EvaluationTool()


def _run(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


# ===================================================================
# EvaluationKernel.evaluate_result tests
# ===================================================================

class TestEvaluateResult:
    def test_perfect_match(self, kernel):
        expected = {"price": 100, "volume": 5000}
        actual = {"price": 100, "volume": 5000}
        result = kernel.evaluate_result(expected, actual)
        assert result["score"] == 1.0
        assert result["gap"] == 0.0

    def test_numeric_within_tolerance(self, kernel):
        expected = {"price": 100}
        actual = {"price": 115}  # 15% off, within 20%
        result = kernel.evaluate_result(expected, actual)
        assert result["score"] == 1.0

    def test_numeric_outside_tolerance(self, kernel):
        expected = {"price": 100}
        actual = {"price": 150}  # 50% off
        result = kernel.evaluate_result(expected, actual)
        assert result["score"] == 0.0
        assert "gap=" in result["details"]["price"]

    def test_missing_key(self, kernel):
        expected = {"price": 100, "volume": 5000}
        actual = {"price": 100}
        result = kernel.evaluate_result(expected, actual)
        assert result["score"] == 0.5
        assert result["details"]["volume"] == "missing"

    def test_string_match(self, kernel):
        expected = {"status": "active"}
        actual = {"status": "active"}
        result = kernel.evaluate_result(expected, actual)
        assert result["score"] == 1.0

    def test_string_mismatch(self, kernel):
        expected = {"status": "active"}
        actual = {"status": "closed"}
        result = kernel.evaluate_result(expected, actual)
        assert result["score"] == 0.0

    def test_bool_match(self, kernel):
        expected = {"margin_call": True}
        actual = {"margin_call": True}
        result = kernel.evaluate_result(expected, actual)
        assert result["score"] == 1.0

    def test_bool_mismatch(self, kernel):
        expected = {"margin_call": True}
        actual = {"margin_call": False}
        result = kernel.evaluate_result(expected, actual)
        assert result["score"] == 0.0

    def test_empty_inputs(self, kernel):
        result = kernel.evaluate_result({}, {"price": 100})
        assert result["score"] == 0.5
        assert result["details"]["reason"] == "insufficient data"

    def test_zero_expected(self, kernel):
        expected = {"pnl": 0}
        actual = {"pnl": 0}
        result = kernel.evaluate_result(expected, actual)
        assert result["score"] == 1.0

    def test_mixed_types(self, kernel):
        expected = {"price": 100, "active": True, "name": "WTI"}
        actual = {"price": 105, "active": True, "name": "WTI"}
        result = kernel.evaluate_result(expected, actual)
        assert result["score"] == 1.0


# ===================================================================
# EvaluationKernel.detect_anomaly tests
# ===================================================================

class TestDetectAnomaly:
    def test_no_history(self, kernel):
        result = kernel.detect_anomaly({"price": 100}, [])
        assert result["is_anomaly"] is False
        assert result["reason"] == "no history"

    def test_normal_result(self, kernel):
        history = [{"price": 100}, {"price": 102}, {"price": 98}, {"price": 101}]
        result = kernel.detect_anomaly({"price": 99}, history)
        assert result["is_anomaly"] is False

    def test_anomalous_result(self, kernel):
        history = [{"price": 100}, {"price": 101}, {"price": 99}, {"price": 100}]
        result = kernel.detect_anomaly({"price": 200}, history)
        assert result["is_anomaly"] is True
        assert result["confidence"] > 0.5

    def test_constant_history_different(self, kernel):
        history = [{"price": 100}, {"price": 100}, {"price": 100}]
        result = kernel.detect_anomaly({"price": 150}, history)
        assert result["is_anomaly"] is True

    def test_constant_history_same(self, kernel):
        history = [{"price": 100}, {"price": 100}, {"price": 100}]
        result = kernel.detect_anomaly({"price": 100}, history)
        assert result["is_anomaly"] is False

    def test_non_numeric_ignored(self, kernel):
        history = [{"status": "ok", "price": 100}]
        result = kernel.detect_anomaly({"status": "fail", "price": 100}, history)
        # Only 1 history point for price, so can't compute z-score
        assert result["is_anomaly"] is False


# ===================================================================
# EvaluationKernel.suggest_improvement tests
# ===================================================================

class TestSuggestImprovement:
    def test_empty_log(self, kernel):
        assert kernel.suggest_improvement([]) == []

    def test_detect_slow_steps(self, kernel):
        log = [
            {"step_id": "s1", "elapsed_ms": 200, "success": True},
            {"step_id": "s2", "elapsed_ms": 300, "success": True},
        ]
        suggestions = kernel.suggest_improvement(log)
        types = [s["type"] for s in suggestions]
        assert "parallelize" in types

    def test_detect_timeout(self, kernel):
        log = [
            {"step_id": "s1", "elapsed_ms": 50, "success": False, "error": "Request timeout"},
        ]
        suggestions = kernel.suggest_improvement(log)
        types = [s["type"] for s in suggestions]
        assert "increase_timeout" in types

    def test_detect_not_found(self, kernel):
        log = [
            {"step_id": "s1", "success": False, "error": "Resource not found"},
        ]
        suggestions = kernel.suggest_improvement(log)
        types = [s["type"] for s in suggestions]
        assert "skip_or_fallback" in types

    def test_detect_duplicate_kernels(self, kernel):
        log = [
            {"step_id": "s1", "kernel": "K1", "elapsed_ms": 10, "success": True},
            {"step_id": "s2", "kernel": "K1", "elapsed_ms": 10, "success": True},
            {"step_id": "s3", "kernel": "K1", "elapsed_ms": 10, "success": True},
        ]
        suggestions = kernel.suggest_improvement(log)
        types = [s["type"] for s in suggestions]
        assert "cache_results" in types


# ===================================================================
# EvaluationKernel.calculate_roi tests
# ===================================================================

class TestCalculateROI:
    def test_basic_roi(self, kernel):
        result = kernel.calculate_roi(plan_tokens=500, result_score=0.8, total_tokens_used=1000)
        assert result["roi"] > 0
        assert result["quality_per_token"] > 0
        assert result["efficiency"] == 0.5

    def test_zero_tokens(self, kernel):
        result = kernel.calculate_roi(plan_tokens=0, result_score=0.5, total_tokens_used=0)
        assert result["roi"] >= 0  # no division by zero
        assert result["quality_per_token"] >= 0

    def test_high_efficiency(self, kernel):
        result = kernel.calculate_roi(plan_tokens=1000, result_score=1.0, total_tokens_used=1000)
        assert result["efficiency"] == 1.0


# ===================================================================
# EvaluationKernel.full_evaluate tests
# ===================================================================

class TestFullEvaluate:
    def test_full_evaluate_happy_path(self, kernel):
        ev = kernel.full_evaluate(
            expected={"price": 100, "volume": 5000},
            actual={"price": 105, "volume": 4800},
            history=[{"price": 100}, {"price": 102}, {"price": 98}],
            execution_log=[
                {"step_id": "s1", "elapsed_ms": 50, "success": True},
            ],
            plan_tokens=200,
            total_tokens_used=300,
        )
        assert isinstance(ev, Evaluation)
        assert 0 <= ev.score <= 1
        assert ev.roi >= 0
        d = ev.to_dict()
        assert "score" in d
        assert "anomalies" in d

    def test_full_evaluate_with_anomaly(self, kernel):
        ev = kernel.full_evaluate(
            expected={"price": 100},
            actual={"price": 500},
            history=[{"price": 100}, {"price": 101}, {"price": 99}],
            execution_log=[],
        )
        assert len(ev.anomalies) > 0

    def test_full_evaluate_empty(self, kernel):
        ev = kernel.full_evaluate(
            expected={},
            actual={},
            history=[],
            execution_log=[],
        )
        assert ev.score == 0.5

    def test_estimate_tokens(self):
        assert EvaluationKernel.estimate_tokens() == 500


# ===================================================================
# EvaluationTool tests (async execute via Tool ABC)
# ===================================================================

class TestEvaluationTool:
    def test_tool_name(self, tool):
        assert tool.name == "evaluate_result"

    def test_tool_schema(self, tool):
        schema = tool.to_schema()
        assert schema["type"] == "function"
        assert "action" in schema["function"]["parameters"]["properties"]

    def test_evaluate_action(self, tool):
        result = json.loads(_run(tool.execute(
            action="evaluate",
            expected={"price": 100},
            actual={"price": 105},
        )))
        assert result["score"] == 1.0

    def test_anomaly_action(self, tool):
        result = json.loads(_run(tool.execute(
            action="anomaly",
            actual={"price": 500},
            history=[{"price": 100}, {"price": 101}, {"price": 99}],
        )))
        assert result["is_anomaly"] is True

    def test_improve_action(self, tool):
        result = json.loads(_run(tool.execute(
            action="improve",
            execution_log=[
                {"step_id": "s1", "elapsed_ms": 200, "success": True},
                {"step_id": "s2", "elapsed_ms": 300, "success": True},
            ],
        )))
        assert result["count"] >= 1

    def test_roi_action(self, tool):
        result = json.loads(_run(tool.execute(
            action="roi",
            plan_tokens=500,
            result_score=0.8,
            total_tokens_used=1000,
        )))
        assert result["roi"] > 0

    def test_full_action(self, tool):
        result = json.loads(_run(tool.execute(
            action="full",
            expected={"price": 100},
            actual={"price": 105},
            history=[{"price": 100}],
            execution_log=[],
            plan_tokens=100,
            total_tokens_used=150,
        )))
        assert "score" in result
        assert "roi" in result
        assert "anomalies" in result

    def test_unknown_action(self, tool):
        result = json.loads(_run(tool.execute(action="invalid")))
        assert "error" in result
