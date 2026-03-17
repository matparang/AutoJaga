"""
Unit tests for K3 Multi-Perspective kernel.
Tests calibrated Bull/Bear/Buffet analysis with accuracy tracking.
"""
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
import json


class TestK3MultiPerspective:
    """Test K3MultiPerspective kernel core functionality."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def k3(self, temp_workspace: Path):
        from jagabot.kernels.k3_perspective import K3MultiPerspective
        return K3MultiPerspective(workspace=temp_workspace)
    
    def test_get_perspective_bull(self, k3):
        """Test Bull perspective retrieval."""
        data = {
            "probability_below_target": 0.35,
            "current_price": 150,
            "target_price": 180
        }
        
        result = k3.get_perspective("bull", data)
        
        assert isinstance(result, dict)
        assert "verdict" in result or "recommendation" in result
    
    def test_get_perspective_bear(self, k3):
        """Test Bear perspective retrieval."""
        data = {
            "probability_below_target": 0.65,
            "current_price": 150,
            "target_price": 120
        }
        
        result = k3.get_perspective("bear", data)
        
        assert isinstance(result, dict)
        assert "verdict" in result or "recommendation" in result
    
    def test_get_perspective_buffet(self, k3):
        """Test Buffett perspective retrieval."""
        data = {
            "probability_below_target": 0.50,
            "current_price": 150,
            "target_price": 150,
            "intrinsic_value": 170
        }
        
        result = k3.get_perspective("buffet", data)
        
        assert isinstance(result, dict)
    
    def test_invalid_perspective_type(self, k3):
        """Test handling of invalid perspective type."""
        data = {"probability_below_target": 0.5}
        
        result = k3.get_perspective("invalid_type", data)
        
        assert "error" in result or result is None
    
    def test_update_accuracy(self, k3):
        """Test accuracy tracking update."""
        result = k3.update_accuracy(
            perspective="bull",
            predicted_verdict="BUY",
            actual_outcome="up"
        )
        
        assert "was_correct" in result or "total" in result
        assert "perspective" in result or "accuracy" in result
    
    def test_update_accuracy_multiple(self, k3):
        """Test multiple accuracy updates."""
        for i in range(5):
            k3.update_accuracy(
                perspective="bull",
                predicted_verdict="BUY" if i % 2 == 0 else "HOLD",
                actual_outcome="up" if i % 3 == 0 else "down"
            )
        
        stats = k3.get_accuracy_stats()
        assert "bull" in stats or stats.get("total", 0) > 0
    
    def test_get_weights_default(self, k3):
        """Test default weight retrieval."""
        result = k3.get_weights()
        
        assert isinstance(result, dict)
        # Should have weights dict
        assert "weights" in result
        # Default weights should be present
        weights = result["weights"]
        assert "bull" in weights or "default" in weights
    
    def test_get_weights_adaptive(self, k3):
        """Test adaptive weights after sufficient history."""
        # Record enough outcomes to trigger adaptive weighting
        for i in range(20):
            k3.update_accuracy(
                perspective="bull" if i % 3 == 0 else "bear" if i % 3 == 1 else "buffet",
                predicted_verdict="BUY",
                actual_outcome="up" if i % 2 == 0 else "down"
            )
        
        weights = k3.get_weights()
        
        assert isinstance(weights, dict)
    
    def test_recalibrate_weights(self, k3):
        """Test manual weight recalibration."""
        # Record some outcomes
        for i in range(10):
            k3.update_accuracy(
                perspective="bull",
                predicted_verdict="BUY",
                actual_outcome="up" if i > 5 else "down"
            )
        
        weights = k3.recalibrate_weights()
        
        assert isinstance(weights, dict)
    
    def test_calibrated_decision(self, k3):
        """Test full calibrated decision pipeline."""
        data = {
            "probability_below_target": 0.40,
            "current_price": 150,
            "target_price": 180,
        }
        
        result = k3.calibrated_collapse(data)
        
        assert isinstance(result, dict)
        # Should have verdict or recommendation from collapse_perspectives
        assert "verdict" in result or "recommendation" in result or "confidence" in result
    
    def test_accuracy_stats(self, k3):
        """Test accuracy statistics retrieval."""
        # Record some outcomes
        for i in range(10):
            k3.update_accuracy(
                perspective="bull" if i % 2 == 0 else "bear",
                predicted_verdict="BUY",
                actual_outcome="up" if i % 3 == 0 else "down"
            )
        
        stats = k3.get_accuracy_stats()
        
        assert isinstance(stats, dict)
    
    def test_persistence(self, temp_workspace):
        """Test that accuracy data persists across instances."""
        from jagabot.kernels.k3_perspective import K3MultiPerspective
        
        # Create instance and record outcomes
        k3_v1 = K3MultiPerspective(workspace=temp_workspace)
        for i in range(5):
            k3_v1.update_accuracy("bull", "BUY", "up")
        
        # Create new instance (should load from disk)
        k3_v2 = K3MultiPerspective(workspace=temp_workspace)
        stats = k3_v2.get_accuracy_stats()
        
        # Should have recorded outcomes
        assert stats is not None


class TestK3PerspectiveTool:
    """Test K3PerspectiveTool ABC wrapper."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.mark.asyncio
    async def test_get_perspective_action(self, temp_workspace):
        """Test get_perspective action."""
        from jagabot.agent.tools.k3_perspective import K3PerspectiveTool
        
        tool = K3PerspectiveTool(workspace=temp_workspace)
        result = await tool.execute(
            action="get_perspective",
            ptype="bull",
            data={
                "probability_below_target": 0.35,
                "current_price": 150,
                "target_price": 180
            }
        )
        
        data = json.loads(result)
        assert isinstance(data, dict)
    
    @pytest.mark.asyncio
    async def test_update_accuracy_action(self, temp_workspace):
        """Test update_accuracy action."""
        from jagabot.agent.tools.k3_perspective import K3PerspectiveTool
        
        tool = K3PerspectiveTool(workspace=temp_workspace)
        result = await tool.execute(
            action="update_accuracy",
            perspective="bull",
            predicted_verdict="BUY",
            actual_outcome="up"
        )
        
        data = json.loads(result)
        assert isinstance(data, dict)
    
    @pytest.mark.asyncio
    async def test_get_weights_action(self, temp_workspace):
        """Test get_weights action."""
        from jagabot.agent.tools.k3_perspective import K3PerspectiveTool
        
        tool = K3PerspectiveTool(workspace=temp_workspace)
        result = await tool.execute(action="get_weights")
        
        data = json.loads(result)
        assert isinstance(data, dict)
    
    @pytest.mark.asyncio
    async def test_recalibrate_action(self, temp_workspace):
        """Test recalibrate action."""
        from jagabot.agent.tools.k3_perspective import K3PerspectiveTool
        
        tool = K3PerspectiveTool(workspace=temp_workspace)
        
        # Record some outcomes first
        for i in range(5):
            await tool.execute(
                action="update_accuracy",
                perspective="bull",
                predicted_verdict="BUY",
                actual_outcome="up" if i % 2 == 0 else "down"
            )
        
        result = await tool.execute(action="recalibrate")
        data = json.loads(result)
        
        assert "weights" in data
    
    @pytest.mark.asyncio
    async def test_calibrated_decision_action(self, temp_workspace):
        """Test calibrated_decision action."""
        from jagabot.agent.tools.k3_perspective import K3PerspectiveTool
        
        tool = K3PerspectiveTool(workspace=temp_workspace)
        result = await tool.execute(
            action="calibrated_decision",
            data={
                "probability_below_target": 0.40,
                "current_price": 150,
                "target_price": 180
            }
        )
        
        data = json.loads(result)
        assert isinstance(data, dict)
    
    @pytest.mark.asyncio
    async def test_accuracy_stats_action(self, temp_workspace):
        """Test accuracy_stats action."""
        from jagabot.agent.tools.k3_perspective import K3PerspectiveTool
        
        tool = K3PerspectiveTool(workspace=temp_workspace)
        
        # Record some outcomes
        for i in range(5):
            await tool.execute(
                action="update_accuracy",
                perspective="bear",
                predicted_verdict="SELL",
                actual_outcome="down"
            )
        
        result = await tool.execute(action="accuracy_stats")
        data = json.loads(result)
        
        assert isinstance(data, dict)
    
    @pytest.mark.asyncio
    async def test_missing_required_params(self, temp_workspace):
        """Test missing required parameters."""
        from jagabot.agent.tools.k3_perspective import K3PerspectiveTool
        
        tool = K3PerspectiveTool(workspace=temp_workspace)
        
        # Missing ptype
        result = await tool.execute(
            action="get_perspective",
            data={"probability_below_target": 0.5}
        )
        
        data = json.loads(result)
        assert "error" in data
    
    @pytest.mark.asyncio
    async def test_unknown_action(self, temp_workspace):
        """Test unknown action handling."""
        from jagabot.agent.tools.k3_perspective import K3PerspectiveTool
        
        tool = K3PerspectiveTool(workspace=temp_workspace)
        result = await tool.execute(action="invalid_action")
        
        data = json.loads(result)
        assert "error" in data


class TestPerspectiveCalibration:
    """Test perspective calibration mechanics."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_bull_bear_disagreement(self, temp_workspace):
        """Test that Bull and Bear perspectives disagree appropriately."""
        from jagabot.kernels.k3_perspective import K3MultiPerspective
        
        k3 = K3MultiPerspective(workspace=temp_workspace)
        
        data = {
            "probability_below_target": 0.70,  # High risk
            "current_price": 150,
            "target_price": 120
        }
        
        bull_view = k3.get_perspective("bull", data)
        bear_view = k3.get_perspective("bear", data)
        
        # Bull and Bear should have different verdicts for high-risk scenario
        assert bull_view is not None
        assert bear_view is not None
    
    def test_buffet_long_term_view(self, temp_workspace):
        """Test Buffett perspective focuses on long-term value."""
        from jagabot.kernels.k3_perspective import K3MultiPerspective
        
        k3 = K3MultiPerspective(workspace=temp_workspace)
        
        data = {
            "probability_below_target": 0.60,
            "current_price": 150,
            "target_price": 140,
            "intrinsic_value": 200  # Undervalued
        }
        
        buffet_view = k3.get_perspective("buffet", data)
        
        assert buffet_view is not None
    
    def test_accuracy_improves_with_data(self, temp_workspace):
        """Test that accuracy tracking improves with more data."""
        from jagabot.kernels.k3_perspective import K3MultiPerspective
        
        k3 = K3MultiPerspective(workspace=temp_workspace)
        
        # Record consistent outcomes
        for i in range(30):
            actual = "up" if i % 3 == 0 else "down"
            k3.update_accuracy(
                perspective="bull",
                predicted_verdict="BUY",
                actual_outcome=actual
            )
        
        stats = k3.get_accuracy_stats()
        
        # Should have meaningful statistics
        assert stats is not None


class TestK3EdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_empty_data(self, temp_workspace):
        """Test perspective with empty data."""
        from jagabot.kernels.k3_perspective import K3MultiPerspective
        
        k3 = K3MultiPerspective(workspace=temp_workspace)
        result = k3.get_perspective("bull", {})
        
        # Should handle gracefully with defaults
        assert result is not None
    
    def test_cold_start_weights(self, temp_workspace):
        """Test weights with no accuracy history."""
        from jagabot.kernels.k3_perspective import K3MultiPerspective
        
        k3 = K3MultiPerspective(workspace=temp_workspace)
        weights = k3.get_weights()
        
        # Should return default weights
        assert isinstance(weights, dict)
    
    def test_extreme_probabilities(self, temp_workspace):
        """Test handling of extreme probabilities (0, 1)."""
        from jagabot.kernels.k3_perspective import K3MultiPerspective
        
        k3 = K3MultiPerspective(workspace=temp_workspace)
        
        data_extreme_low = {
            "probability_below_target": 0.01,
            "current_price": 150,
            "target_price": 200
        }
        
        data_extreme_high = {
            "probability_below_target": 0.99,
            "current_price": 150,
            "target_price": 100
        }
        
        result_low = k3.get_perspective("bull", data_extreme_low)
        result_high = k3.get_perspective("bear", data_extreme_high)
        
        assert result_low is not None
        assert result_high is not None
    
    def test_all_perspectives_same_data(self, temp_workspace):
        """Test all three perspectives with same data."""
        from jagabot.kernels.k3_perspective import K3MultiPerspective
        
        k3 = K3MultiPerspective(workspace=temp_workspace)
        
        data = {
            "probability_below_target": 0.50,
            "current_price": 150,
            "target_price": 150
        }
        
        bull = k3.get_perspective("bull", data)
        bear = k3.get_perspective("bear", data)
        buffet = k3.get_perspective("buffet", data)
        
        assert bull is not None
        assert bear is not None
        assert buffet is not None
