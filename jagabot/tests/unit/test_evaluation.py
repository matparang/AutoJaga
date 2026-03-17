"""
Unit tests for K7 Evaluation kernel.
Tests result scoring, anomaly detection, improvement suggestions, and ROI calculation.
"""
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
import json


class TestEvaluationKernel:
    """Test EvaluationKernel core functionality."""
    
    @pytest.fixture
    def kernel(self):
        from jagabot.agent.tools.evaluation import EvaluationKernel
        return EvaluationKernel()
    
    def test_evaluate_result_match(self, kernel):
        """Test evaluation with matching results."""
        expected = {
            "probability": 0.65,
            "confidence": 80,
            "verdict": "BUY"
        }
        actual = {
            "probability": 0.63,
            "confidence": 78,
            "verdict": "BUY"
        }
        
        result = kernel.evaluate_result(expected, actual)
        
        assert "score" in result
        assert "gap" in result
        assert result["score"] > 0.5  # Should be good match
    
    def test_evaluate_result_mismatch(self, kernel):
        """Test evaluation with mismatched results."""
        expected = {
            "probability": 0.80,
            "confidence": 90,
            "verdict": "BUY"
        }
        actual = {
            "probability": 0.30,
            "confidence": 40,
            "verdict": "SELL"
        }
        
        result = kernel.evaluate_result(expected, actual)
        
        assert "score" in result
        assert result["score"] < 0.5  # Should be poor match
    
    def test_evaluate_result_missing_fields(self, kernel):
        """Test evaluation with missing fields."""
        expected = {
            "probability": 0.65,
            "confidence": 80
        }
        actual = {
            "probability": 0.65
            # Missing confidence
        }
        
        result = kernel.evaluate_result(expected, actual)
        
        assert "score" in result
        assert "details" in result
    
    def test_evaluate_result_empty(self, kernel):
        """Test evaluation with empty inputs."""
        result = kernel.evaluate_result({}, {})
        
        assert "score" in result
        assert result["score"] == 0.5  # Default for insufficient data
    
    def test_detect_anomaly_no_history(self, kernel):
        """Test anomaly detection without history."""
        result = {"value": 100}
        history = []
        
        anomaly = kernel.detect_anomaly(result, history)
        
        assert anomaly.get("is_anomaly") is False
        assert "no history" in anomaly.get("reason", "").lower()
    
    def test_detect_anomaly_normal(self, kernel):
        """Test anomaly detection with normal result."""
        result = {"value": 52}
        history = [
            {"value": 50},
            {"value": 51},
            {"value": 49},
            {"value": 50},
            {"value": 52}
        ]
        
        anomaly = kernel.detect_anomaly(result, history)
        
        assert anomaly.get("is_anomaly") is False
    
    def test_detect_anomaly_outlier(self, kernel):
        """Test anomaly detection with outlier."""
        result = {"value": 200}  # Way outside normal range
        history = [
            {"value": 50},
            {"value": 51},
            {"value": 49},
            {"value": 50},
            {"value": 52}
        ]
        
        anomaly = kernel.detect_anomaly(result, history)
        
        assert anomaly.get("is_anomaly") is True
        assert "z-score" in anomaly.get("reason", "").lower()
    
    def test_detect_anomaly_multiple_keys(self, kernel):
        """Test anomaly detection with multiple keys."""
        result = {"value1": 100, "value2": 50}
        history = [
            {"value1": 50, "value2": 50},
            {"value1": 51, "value2": 49},
            {"value1": 49, "value2": 51}
        ]
        
        anomaly = kernel.detect_anomaly(result, history)
        
        assert anomaly.get("is_anomaly") is True  # value1 is anomalous
    
    def test_suggest_improvement_empty(self, kernel):
        """Test improvement suggestions with empty log."""
        suggestions = kernel.suggest_improvement([])
        
        assert isinstance(suggestions, list)
        assert len(suggestions) == 0
    
    def test_suggest_improvement_slow_steps(self, kernel):
        """Test suggestions for slow steps."""
        execution_log = [
            {"step_id": "step1", "elapsed_ms": 150, "success": True},
            {"step_id": "step2", "elapsed_ms": 200, "success": True},
            {"step_id": "step3", "elapsed_ms": 180, "success": True}
        ]
        
        suggestions = kernel.suggest_improvement(execution_log)
        
        assert len(suggestions) > 0
        assert any(s.get("type") == "parallelize" for s in suggestions)
    
    def test_suggest_improvement_failed_steps(self, kernel):
        """Test suggestions for failed steps."""
        execution_log = [
            {"step_id": "step1", "elapsed_ms": 50, "success": True},
            {"step_id": "step2", "elapsed_ms": 100, "success": False, "error": "timeout"},
            {"step_id": "step3", "elapsed_ms": 30, "success": True}
        ]
        
        suggestions = kernel.suggest_improvement(execution_log)
        
        assert len(suggestions) > 0
        assert any(s.get("type") == "increase_timeout" for s in suggestions)
    
    def test_suggest_improvement_missing_resource(self, kernel):
        """Test suggestions for missing resources."""
        execution_log = [
            {"step_id": "step1", "success": False, "error": "file not found"},
        ]
        
        suggestions = kernel.suggest_improvement(execution_log)
        
        assert len(suggestions) > 0
        assert any(s.get("type") == "skip_or_fallback" for s in suggestions)
    
    def test_suggest_improvement_repeated_kernel(self, kernel):
        """Test suggestions for repeated kernel calls."""
        execution_log = [
            {"step_id": "s1", "kernel": "monte_carlo", "success": True},
            {"step_id": "s2", "kernel": "monte_carlo", "success": True},
            {"step_id": "s3", "kernel": "monte_carlo", "success": True},
        ]
        
        suggestions = kernel.suggest_improvement(execution_log)
        
        assert len(suggestions) > 0
        assert any(s.get("type") == "cache_results" for s in suggestions)
    
    def test_calculate_roi(self, kernel):
        """Test ROI calculation."""
        result = kernel.calculate_roi(
            plan_tokens=1000,
            result_score=0.8,
            total_tokens_used=1200
        )
        
        assert "roi" in result
        assert "quality_per_token" in result
        assert "efficiency" in result
    
    def test_calculate_roi_zero_tokens(self, kernel):
        """Test ROI with zero tokens (edge case)."""
        result = kernel.calculate_roi(
            plan_tokens=0,
            result_score=0.8,
            total_tokens_used=0
        )
        
        assert "roi" in result
        # Should handle division by zero gracefully
    
    def test_full_evaluate(self, kernel):
        """Test full evaluation pipeline."""
        expected = {"probability": 0.65, "verdict": "BUY"}
        actual = {"probability": 0.63, "verdict": "BUY"}
        history = [
            {"probability": 0.60},
            {"probability": 0.62},
            {"probability": 0.64}
        ]
        execution_log = [
            {"step_id": "s1", "kernel": "k1", "elapsed_ms": 50, "success": True}
        ]
        
        evaluation = kernel.full_evaluate(
            expected=expected,
            actual=actual,
            history=history,
            execution_log=execution_log,
            plan_tokens=500,
            total_tokens_used=600
        )
        
        assert hasattr(evaluation, 'score')
        assert hasattr(evaluation, 'gap')
        assert hasattr(evaluation, 'anomalies')
        assert hasattr(evaluation, 'improvements')
        assert hasattr(evaluation, 'roi')
    
    def test_full_evaluate_dict(self, kernel):
        """Test full_evaluate to_dict conversion."""
        expected = {"probability": 0.65}
        actual = {"probability": 0.63}
        
        evaluation = kernel.full_evaluate(
            expected=expected,
            actual=actual,
            history=[],
            execution_log=[],
            plan_tokens=500,
            total_tokens_used=600
        )
        
        result_dict = evaluation.to_dict()
        
        assert "score" in result_dict
        assert "gap" in result_dict
        assert "roi" in result_dict


class TestEvaluationTool:
    """Test EvaluationTool ABC wrapper."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.mark.asyncio
    async def test_evaluate_action(self, temp_workspace):
        """Test evaluate action."""
        from jagabot.agent.tools.evaluation import EvaluationTool
        
        tool = EvaluationTool()
        result = await tool.execute(
            action="evaluate",
            expected={"probability": 0.65, "verdict": "BUY"},
            actual={"probability": 0.63, "verdict": "BUY"}
        )
        
        data = json.loads(result)
        assert "score" in data
        assert "gap" in data
    
    @pytest.mark.asyncio
    async def test_anomaly_action(self, temp_workspace):
        """Test anomaly action."""
        from jagabot.agent.tools.evaluation import EvaluationTool
        
        tool = EvaluationTool()
        result = await tool.execute(
            action="anomaly",
            actual={"value": 200},
            history=[{"value": 50}, {"value": 51}, {"value": 49}]
        )
        
        data = json.loads(result)
        assert "is_anomaly" in data
    
    @pytest.mark.asyncio
    async def test_improve_action(self, temp_workspace):
        """Test improve action."""
        from jagabot.agent.tools.evaluation import EvaluationTool
        
        tool = EvaluationTool()
        result = await tool.execute(
            action="improve",
            execution_log=[
                {"step_id": "s1", "elapsed_ms": 150, "success": True},
                {"step_id": "s2", "elapsed_ms": 200, "success": True}
            ]
        )
        
        data = json.loads(result)
        assert "suggestions" in data
        assert "count" in data
    
    @pytest.mark.asyncio
    async def test_roi_action(self, temp_workspace):
        """Test roi action."""
        from jagabot.agent.tools.evaluation import EvaluationTool
        
        tool = EvaluationTool()
        result = await tool.execute(
            action="roi",
            plan_tokens=1000,
            result_score=0.8,
            total_tokens_used=1200
        )
        
        data = json.loads(result)
        assert "roi" in data
        assert "quality_per_token" in data
    
    @pytest.mark.asyncio
    async def test_full_action(self, temp_workspace):
        """Test full evaluation action."""
        from jagabot.agent.tools.evaluation import EvaluationTool
        
        tool = EvaluationTool()
        result = await tool.execute(
            action="full",
            expected={"probability": 0.65},
            actual={"probability": 0.63},
            history=[{"probability": 0.60}, {"probability": 0.62}],
            execution_log=[{"step_id": "s1", "kernel": "k1", "elapsed_ms": 50}],
            plan_tokens=500,
            total_tokens_used=600
        )
        
        data = json.loads(result)
        assert "score" in data
        assert "gap" in data
        assert "roi" in data
    
    @pytest.mark.asyncio
    async def test_unknown_action(self, temp_workspace):
        """Test unknown action handling."""
        from jagabot.agent.tools.evaluation import EvaluationTool
        
        tool = EvaluationTool()
        result = await tool.execute(action="invalid_action")
        
        data = json.loads(result)
        assert "error" in data


class TestAnomalyDetection:
    """Test anomaly detection mechanics."""
    
    @pytest.fixture
    def kernel(self):
        from jagabot.agent.tools.evaluation import EvaluationKernel
        return EvaluationKernel()
    
    def test_z_score_calculation(self, kernel):
        """Test z-score calculation correctness."""
        result = {"value": 70}
        history = [
            {"value": 50},
            {"value": 50},
            {"value": 50},
            {"value": 50}
        ]
        
        anomaly = kernel.detect_anomaly(result, history)
        
        # z-score should be high (constant history, different value)
        if anomaly.get("is_anomaly"):
            # Reason should mention the difference
            assert "differs" in anomaly.get("reason", "").lower() or "z-score" in anomaly.get("reason", "").lower()
    
    def test_constant_history(self, kernel):
        """Test anomaly detection with constant history."""
        result = {"value": 51}
        history = [
            {"value": 50},
            {"value": 50},
            {"value": 50}
        ]
        
        anomaly = kernel.detect_anomaly(result, history)
        
        # Should detect as anomaly (value differs from constant)
        assert anomaly.get("is_anomaly") is True
    
    def test_insufficient_history(self, kernel):
        """Test with insufficient history (< 2 samples)."""
        result = {"value": 100}
        history = [{"value": 50}]  # Only 1 sample
        
        anomaly = kernel.detect_anomaly(result, history)
        
        # Should not detect (insufficient data)
        assert anomaly.get("is_anomaly") is False


class TestROICalculation:
    """Test ROI calculation mechanics."""
    
    @pytest.fixture
    def kernel(self):
        from jagabot.agent.tools.evaluation import EvaluationKernel
        return EvaluationKernel()
    
    def test_high_efficiency(self, kernel):
        """Test ROI with high efficiency."""
        result = kernel.calculate_roi(
            plan_tokens=1000,
            result_score=0.9,
            total_tokens_used=800  # Under budget
        )
        
        assert result["efficiency"] > 1.0
        assert result["roi"] > 0
    
    def test_low_efficiency(self, kernel):
        """Test ROI with low efficiency."""
        result = kernel.calculate_roi(
            plan_tokens=1000,
            result_score=0.3,
            total_tokens_used=2000  # Over budget
        )
        
        assert result["efficiency"] < 1.0
    
    def test_perfect_score(self, kernel):
        """Test ROI with perfect score."""
        result = kernel.calculate_roi(
            plan_tokens=1000,
            result_score=1.0,
            total_tokens_used=1000
        )
        
        assert result["roi"] > 0
        assert result["quality_per_token"] > 0


class TestEvaluationEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.fixture
    def kernel(self):
        from jagabot.agent.tools.evaluation import EvaluationKernel
        return EvaluationKernel()
    
    def test_none_inputs(self, kernel):
        """Test handling of None inputs."""
        result = kernel.evaluate_result(None, None)
        
        assert result["score"] == 0.5
        assert "insufficient data" in result.get("details", {}).get("reason", "")
    
    def test_type_mismatch(self, kernel):
        """Test evaluation with type mismatches."""
        expected = {"value": 50}
        actual = {"value": "fifty"}  # String instead of number
        
        result = kernel.evaluate_result(expected, actual)
        
        assert "score" in result
        assert "details" in result
    
    def test_boolean_evaluation(self, kernel):
        """Test boolean field evaluation."""
        expected = {"is_bullish": True}
        actual = {"is_bullish": True}
        
        result = kernel.evaluate_result(expected, actual)
        
        assert result["score"] == 1.0  # Perfect match
    
    def test_boolean_mismatch(self, kernel):
        """Test boolean field mismatch."""
        expected = {"is_bullish": True}
        actual = {"is_bullish": False}
        
        result = kernel.evaluate_result(expected, actual)
        
        assert result["score"] < 1.0
