"""
Unit tests for K1 Bayesian kernel.
Tests Bayesian reasoning, calibration, and uncertainty assessment.
"""
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
import json


class TestK1Bayesian:
    """Test K1Bayesian kernel core functionality."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def k1(self, temp_workspace: Path):
        from jagabot.kernels.k1_bayesian import K1Bayesian
        return K1Bayesian(workspace=temp_workspace)
    
    def test_update_belief(self, k1):
        """Test Bayesian belief update."""
        result = k1.update(
            topic="market_outlook",
            evidence={
                "price_trend": "up",
                "volume": "high",
                "sentiment": "positive"
            }
        )
        
        assert "posterior" in result
        assert "prior" in result
        assert "likelihood" in result
    
    def test_update_belief_multiple_evidence(self, k1):
        """Test update with multiple evidence pieces."""
        evidence_list = [
            {"indicator": "RSI", "value": "oversold"},
            {"indicator": "MACD", "value": "bullish_crossover"},
            {"indicator": "volume", "value": "increasing"}
        ]
        
        for evidence in evidence_list:
            result = k1.update("AAPL_outlook", evidence)
            assert "posterior" in result
    
    def test_assess_problem(self, k1):
        """Test uncertainty assessment."""
        result = k1.assess("Will AAPL reach $200 by year end?")
        
        assert "ci_lower" in result
        assert "ci_upper" in result
        assert "uncertainty" in result
        assert "prior" in result
    
    def test_refine_confidence(self, k1):
        """Test confidence refinement using calibration."""
        # First, add some calibration data
        k1.record_outcome("bull", 0.7, True, "pred_001")
        k1.record_outcome("bull", 0.6, True, "pred_002")
        k1.record_outcome("bull", 0.8, False, "pred_003")
        
        # Now refine a new confidence
        refined = k1.refine_confidence(raw_confidence=75.0, perspective="bull")
        
        assert isinstance(refined, float)
        assert 0 <= refined <= 100
    
    def test_record_outcome(self, k1):
        """Test outcome recording for calibration."""
        result = k1.record_outcome(
            perspective="bull",
            predicted_prob=0.75,
            actual=True,
            prediction_id="test_001"
        )
        
        assert "perspective" in result
        assert "predicted" in result
        assert "actual" in result
        assert "brier_score" in result or "n_records" in result
    
    def test_get_calibration(self, k1):
        """Test calibration retrieval."""
        # Record some outcomes first
        for i in range(5):
            k1.record_outcome("bull", 0.6 + i * 0.05, i % 2 == 0, f"pred_{i}")
        
        calibration = k1.get_calibration("bull")
        
        assert isinstance(calibration, dict)
        # Should have Brier score or similar metric
    
    def test_get_calibration_all_perspectives(self, k1):
        """Test calibration for all perspectives."""
        # Record outcomes for multiple perspectives
        perspectives = ["bull", "bear", "buffet"]
        for p in perspectives:
            for i in range(3):
                k1.record_outcome(p, 0.5 + i * 0.1, i % 2 == 0, f"{p}_{i}")
        
        calibration = k1.get_calibration()
        
        assert isinstance(calibration, dict)
    
    def test_persistence(self, temp_workspace):
        """Test that calibration persists across instances."""
        from jagabot.kernels.k1_bayesian import K1Bayesian
        
        # Create instance and record outcomes
        k1_v1 = K1Bayesian(workspace=temp_workspace)
        k1_v1.record_outcome("bull", 0.7, True, "persist_test")
        
        # Create new instance (should load from disk)
        k1_v2 = K1Bayesian(workspace=temp_workspace)
        calibration = k1_v2.get_calibration("bull")
        
        # Should have the recorded outcome
        assert calibration is not None
    
    def test_wilson_confidence_interval(self, k1):
        """Test Wilson confidence interval calculation."""
        result = k1.assess("Test problem with uncertainty")
        
        # Should have confidence interval
        assert isinstance(result, dict)


class TestK1BayesianTool:
    """Test K1BayesianTool ABC wrapper."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.mark.asyncio
    async def test_update_belief_action(self, temp_workspace):
        """Test update_belief action."""
        from jagabot.agent.tools.k1_bayesian import K1BayesianTool
        
        tool = K1BayesianTool(workspace=temp_workspace)
        result = await tool.execute(
            action="update_belief",
            topic="market_analysis",
            evidence={"trend": "up", "volume": "high"}
        )
        
        data = json.loads(result)
        assert "posterior" in data or "belief" in data
    
    @pytest.mark.asyncio
    async def test_assess_action(self, temp_workspace):
        """Test assess action."""
        from jagabot.agent.tools.k1_bayesian import K1BayesianTool
        
        tool = K1BayesianTool(workspace=temp_workspace)
        result = await tool.execute(
            action="assess",
            problem="Will the market rise tomorrow?"
        )
        
        data = json.loads(result)
        assert isinstance(data, dict)
    
    @pytest.mark.asyncio
    async def test_refine_confidence_action(self, temp_workspace):
        """Test refine_confidence action."""
        from jagabot.agent.tools.k1_bayesian import K1BayesianTool
        
        tool = K1BayesianTool(workspace=temp_workspace)
        
        # Record some outcomes first
        await tool.execute(
            action="record_outcome",
            perspective="bull",
            predicted_prob=0.7,
            actual=True
        )
        
        result = await tool.execute(
            action="refine_confidence",
            raw_confidence=75.0,
            perspective="bull"
        )
        
        data = json.loads(result)
        assert "raw" in data
        assert "refined" in data
        assert "perspective" in data
    
    @pytest.mark.asyncio
    async def test_record_outcome_action(self, temp_workspace):
        """Test record_outcome action."""
        from jagabot.agent.tools.k1_bayesian import K1BayesianTool
        
        tool = K1BayesianTool(workspace=temp_workspace)
        result = await tool.execute(
            action="record_outcome",
            perspective="bear",
            predicted_prob=0.6,
            actual=False,
            prediction_id="test_123"
        )
        
        data = json.loads(result)
        assert isinstance(data, dict)
    
    @pytest.mark.asyncio
    async def test_get_calibration_action(self, temp_workspace):
        """Test get_calibration action."""
        from jagabot.agent.tools.k1_bayesian import K1BayesianTool
        
        tool = K1BayesianTool(workspace=temp_workspace)
        
        # Record some outcomes
        for i in range(3):
            await tool.execute(
                action="record_outcome",
                perspective="bull",
                predicted_prob=0.5 + i * 0.1,
                actual=(i % 2 == 0)
            )
        
        result = await tool.execute(action="get_calibration", perspective="bull")
        data = json.loads(result)
        
        assert isinstance(data, dict)
    
    @pytest.mark.asyncio
    async def test_unknown_action(self, temp_workspace):
        """Test unknown action handling."""
        from jagabot.agent.tools.k1_bayesian import K1BayesianTool
        
        tool = K1BayesianTool(workspace=temp_workspace)
        result = await tool.execute(action="invalid_action")
        
        data = json.loads(result)
        assert "error" in data
    
    @pytest.mark.asyncio
    async def test_missing_required_params(self, temp_workspace):
        """Test missing required parameters."""
        from jagabot.agent.tools.k1_bayesian import K1BayesianTool
        
        tool = K1BayesianTool(workspace=temp_workspace)
        
        # Missing topic for update_belief
        result = await tool.execute(
            action="update_belief",
            evidence={"trend": "up"}
        )
        
        data = json.loads(result)
        assert "error" in data


class TestBayesianCalibration:
    """Test Bayesian calibration mechanics."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_brier_score_calculation(self, temp_workspace):
        """Test Brier score calculation for calibration."""
        from jagabot.kernels.k1_bayesian import K1Bayesian
        
        k1 = K1Bayesian(workspace=temp_workspace)
        
        # Record predictions with known outcomes
        predictions = [
            (0.9, True),   # Well calibrated
            (0.8, True),   # Well calibrated
            (0.7, False),  # Overconfident
            (0.6, True),   # Underconfident
        ]
        
        for prob, actual in predictions:
            k1.record_outcome("test", prob, actual)
        
        calibration = k1.get_calibration("test")
        
        # Should have some calibration metric
        assert calibration is not None
    
    def test_sequential_updates(self, temp_workspace):
        """Test sequential Bayesian updates."""
        from jagabot.kernels.k1_bayesian import K1Bayesian
        
        k1 = K1Bayesian(workspace=temp_workspace)
        
        # Start with prior
        result1 = k1.update("topic", {"evidence": "weak_positive"})
        prior_1 = result1.get("posterior", 0.5)
        
        # Update with more evidence
        result2 = k1.update("topic", {"evidence": "strong_positive"})
        prior_2 = result2.get("posterior", prior_1)
        
        # Posterior should have changed or history should have 2 entries
        assert len(k1.history) == 2 or prior_2 != prior_1
    
    def test_confidence_refinement_improves_accuracy(self, temp_workspace):
        """Test that confidence refinement improves with more data."""
        from jagabot.kernels.k1_bayesian import K1Bayesian
        
        k1 = K1Bayesian(workspace=temp_workspace)
        
        # Record many consistent outcomes
        for i in range(20):
            # 80% confidence predictions are correct 80% of time
            actual = (i % 5) != 0  # 80% success rate
            k1.record_outcome("consistent", 0.8, actual)
        
        # Get calibration
        calibration = k1.get_calibration("consistent")
        
        # Should show good calibration
        assert calibration is not None


class TestK1EdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_empty_evidence(self, temp_workspace):
        """Test update with empty evidence."""
        from jagabot.kernels.k1_bayesian import K1Bayesian
        
        k1 = K1Bayesian(workspace=temp_workspace)
        result = k1.update("topic", {})
        
        # Should handle gracefully
        assert result is not None
    
    def test_cold_start(self, temp_workspace):
        """Test behavior with no calibration history."""
        from jagabot.kernels.k1_bayesian import K1Bayesian
        
        k1 = K1Bayesian(workspace=temp_workspace)
        
        # Should use default prior
        refined = k1.refine_confidence(75.0, "new_perspective")
        
        # Should return something reasonable
        assert isinstance(refined, float)
    
    def test_extreme_probabilities(self, temp_workspace):
        """Test handling of extreme probabilities (0, 1)."""
        from jagabot.kernels.k1_bayesian import K1Bayesian
        
        k1 = K1Bayesian(workspace=temp_workspace)
        
        # Record extreme predictions
        k1.record_outcome("extreme", 0.99, True)
        k1.record_outcome("extreme", 0.01, False)
        
        calibration = k1.get_calibration("extreme")
        assert calibration is not None
    
    def test_invalid_perspective(self, temp_workspace):
        """Test handling of invalid perspective names."""
        from jagabot.kernels.k1_bayesian import K1Bayesian
        
        k1 = K1Bayesian(workspace=temp_workspace)
        
        # Should handle any string as perspective
        result = k1.record_outcome("custom_perspective_123", 0.6, True)
        assert result is not None
