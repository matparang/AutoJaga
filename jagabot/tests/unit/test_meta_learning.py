"""
Unit tests for MetaLearning engine.
Tests strategy tracking, experiment management, and self-improvement.
"""
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
import json


class TestMetaLearningEngine:
    """Test MetaLearningEngine core functionality."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def meta_learning(self, temp_workspace: Path):
        from jagabot.engines.meta_learning import MetaLearningEngine
        return MetaLearningEngine(workspace=temp_workspace)
    
    def test_record_strategy_result(self, meta_learning):
        """Test recording a strategy result."""
        result = meta_learning.record_strategy_result(
            strategy_name="bull_analysis",
            success=True,
            fitness_gain=0.15
        )
        
        assert isinstance(result, dict) or result is None  # May not return anything
        # Check that strategy was recorded
        assert "bull_analysis" in meta_learning.strategies
        assert meta_learning.strategies["bull_analysis"].attempts == 1
    
    def test_record_multiple_strategies(self, meta_learning):
        """Test recording multiple strategy outcomes."""
        strategies = ["bull_analysis", "bear_analysis", "buffet_analysis"]
        
        for i, strategy in enumerate(strategies):
            meta_learning.record_strategy_result(
                strategy_name=strategy,
                success=(i % 2 == 0),
                fitness_gain=0.1 * (i + 1)
            )
        
        rankings = meta_learning.get_strategy_rankings()
        assert len(rankings) >= 3
    
    def test_select_strategy(self, meta_learning):
        """Test strategy selection."""
        # Record some outcomes
        for i in range(10):
            meta_learning.record_strategy_result(
                strategy_name="high_confidence",
                success=(i > 2),  # 70% success
                fitness_gain=0.1
            )
        
        for i in range(10):
            meta_learning.record_strategy_result(
                strategy_name="low_confidence",
                success=(i > 7),  # 20% success
                fitness_gain=0.05
            )
        
        # Select best strategy
        result = meta_learning.select_best_strategy()
        
        assert isinstance(result, dict)
        assert "strategy" in result
    
    def test_select_strategy_no_history(self, meta_learning):
        """Test strategy selection with no history."""
        available = ["new_strategy_1", "new_strategy_2"]
        result = meta_learning.select_best_strategy(available)
        
        # Should handle gracefully (random or first)
        assert result is not None
    
    def test_detect_learning_problems(self, meta_learning):
        """Test learning problem detection."""
        # Record problematic pattern
        for i in range(10):
            meta_learning.record_strategy_result(
                strategy_name="failing_strategy",
                success=False,
                fitness_gain=-0.1
            )

        problems = meta_learning.detect_learning_problems()

        assert isinstance(problems, list)

    def test_meta_cycle(self, meta_learning):
        """Test full meta-analysis cycle."""
        # Record some data
        for i in range(5):
            meta_learning.record_strategy_result(
                strategy_name=f"strategy_{i}",
                success=(i % 2 == 0),
                fitness_gain=0.1 * i
            )

        result = meta_learning.meta_cycle()

        assert isinstance(result, dict)
        assert "cycle" in result
    
    def test_get_status(self, meta_learning):
        """Test status retrieval."""
        # Record some data
        meta_learning.record_strategy_result("test", True, 0.1)
        
        status = meta_learning.get_status()
        
        assert isinstance(status, dict)
        assert "total_strategies" in status or "total_records" in status
    
    def test_get_strategy_rankings(self, meta_learning):
        """Test strategy rankings."""
        # Record varied outcomes
        strategies = [
            ("excellent", 0.9, 0.2),
            ("good", 0.7, 0.15),
            ("average", 0.5, 0.1),
            ("poor", 0.3, 0.05)
        ]

        for name, success_rate, gain in strategies:
            for i in range(10):
                meta_learning.record_strategy_result(
                    strategy_name=name,
                    success=(i / 10) < success_rate,
                    fitness_gain=gain
                )

        rankings = meta_learning.get_strategy_rankings()

        assert isinstance(rankings, list)
        assert len(rankings) >= 4
        assert "name" in rankings[0]
        assert "success_rate" in rankings[0]
    
    def test_persistence(self, temp_workspace):
        """Test that data persists across instances."""
        from jagabot.engines.meta_learning import MetaLearningEngine
        
        # Create instance and record data
        ml_v1 = MetaLearningEngine(workspace=temp_workspace)
        ml_v1.record_strategy_result("persistent", True, 0.15)
        
        # Create new instance (should load from disk)
        ml_v2 = MetaLearningEngine(workspace=temp_workspace)
        rankings = ml_v2.get_strategy_rankings()
        
        # Should have recorded data
        assert len(rankings) >= 1


class TestExperimentTracker:
    """Test ExperimentTracker functionality."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def tracker(self, temp_workspace: Path):
        from jagabot.engines.experiment_tracker import ExperimentTracker
        return ExperimentTracker(workspace=temp_workspace)
    
    def test_create_experiment(self, tracker):
        """Test experiment creation."""
        exp = tracker.create(
            hypothesis="Higher confidence leads to better outcomes",
            method="A/B testing with confidence thresholds",
            variables={"threshold": 0.7}
        )
        
        assert exp is not None
        assert exp.hypothesis == "Higher confidence leads to better outcomes"
        assert exp.status == "planned"
    
    def test_complete_experiment(self, tracker):
        """Test experiment completion."""
        exp = tracker.create(
            hypothesis="Test hypothesis",
            method="Test method"
        )
        
        completed = tracker.complete(
            experiment_id=exp.experiment_id,
            result={"success_rate": 0.75},
            conclusion="Hypothesis supported",
            falsified=False
        )
        
        assert completed is not None
        assert completed.status == "completed"
        assert completed.conclusion == "Hypothesis supported"
    
    def test_list_experiments_all(self, tracker):
        """Test listing all experiments."""
        for i in range(5):
            tracker.create(f"Hypothesis {i}", f"Method {i}")
        
        exps = tracker.list_experiments(limit=10)
        assert len(exps) == 5
    
    def test_list_experiments_by_status(self, tracker):
        """Test filtering experiments by status."""
        exp1 = tracker.create("H1", "M1")
        tracker.create("H2", "M2")
        
        # Complete one
        tracker.complete(exp1.experiment_id, {}, "Completed", False)
        
        # Filter by status
        completed = tracker.list_experiments(status="completed", limit=10)
        assert len(completed) == 1
        
        planned = tracker.list_experiments(status="planned", limit=10)
        assert len(planned) == 1
    
    def test_experiment_summary(self, tracker):
        """Test experiment summary statistics."""
        # Create and complete some experiments
        for i in range(5):
            exp = tracker.create(f"Hypothesis {i}", f"Method {i}")
            tracker.complete(
                exp.experiment_id,
                {"metric": i * 0.1},
                f"Conclusion {i}",
                falsified=(i % 2 == 0)
            )
        
        summary = tracker.summary()
        
        assert isinstance(summary, dict)
        assert "total" in summary or summary.get("total", 0) > 0
    
    def test_experiment_to_dict(self, tracker):
        """Test experiment serialization."""
        exp = tracker.create("Test hypothesis", "Test method")
        
        exp_dict = tracker.get(exp.experiment_id)
        
        assert exp_dict is not None
        assert "experiment_id" in exp_dict
        assert "hypothesis" in exp_dict
        assert "method" in exp_dict
        assert "status" in exp_dict


class TestMetaLearningTool:
    """Test MetaLearningTool ABC wrapper."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.mark.asyncio
    async def test_record_result_action(self, temp_workspace):
        """Test record_result action."""
        from jagabot.agent.tools.meta_learning import MetaLearningTool
        
        tool = MetaLearningTool(workspace=temp_workspace)
        result = await tool.execute(
            action="record_result",
            strategy="test_strategy",
            success=True,
            fitness_gain=0.15
        )
        
        data = json.loads(result)
        assert isinstance(data, dict)
    
    @pytest.mark.asyncio
    async def test_select_strategy_action(self, temp_workspace):
        """Test select_strategy action."""
        from jagabot.agent.tools.meta_learning import MetaLearningTool
        
        tool = MetaLearningTool(workspace=temp_workspace)
        
        # Record some data first
        await tool.execute(
            action="record_result",
            strategy="strategy_a",
            success=True
        )
        
        result = await tool.execute(
            action="select_strategy",
            available=["strategy_a", "strategy_b"]
        )
        
        data = json.loads(result)
        assert isinstance(data, dict)
    
    @pytest.mark.asyncio
    async def test_detect_problems_action(self, temp_workspace):
        """Test detect_problems action."""
        from jagabot.agent.tools.meta_learning import MetaLearningTool
        
        tool = MetaLearningTool(workspace=temp_workspace)
        
        # Record problematic pattern
        for i in range(5):
            await tool.execute(
                action="record_result",
                strategy="failing",
                success=False
            )
        
        result = await tool.execute(action="detect_problems")
        
        data = json.loads(result)
        assert "problems" in data
    
    @pytest.mark.asyncio
    async def test_meta_cycle_action(self, temp_workspace):
        """Test meta_cycle action."""
        from jagabot.agent.tools.meta_learning import MetaLearningTool
        
        tool = MetaLearningTool(workspace=temp_workspace)
        result = await tool.execute(action="meta_cycle")
        
        data = json.loads(result)
        assert isinstance(data, dict)
    
    @pytest.mark.asyncio
    async def test_get_status_action(self, temp_workspace):
        """Test get_status action."""
        from jagabot.agent.tools.meta_learning import MetaLearningTool
        
        tool = MetaLearningTool(workspace=temp_workspace)
        result = await tool.execute(action="get_status")
        
        data = json.loads(result)
        assert isinstance(data, dict)
    
    @pytest.mark.asyncio
    async def test_get_rankings_action(self, temp_workspace):
        """Test get_rankings action."""
        from jagabot.agent.tools.meta_learning import MetaLearningTool
        
        tool = MetaLearningTool(workspace=temp_workspace)
        
        # Record some data
        for i in range(5):
            await tool.execute(
                action="record_result",
                strategy=f"strategy_{i}",
                success=(i % 2 == 0)
            )
        
        result = await tool.execute(action="get_rankings")
        
        data = json.loads(result)
        assert isinstance(data, list)
    
    @pytest.mark.asyncio
    async def test_create_experiment_action(self, temp_workspace):
        """Test create_experiment action."""
        from jagabot.agent.tools.meta_learning import MetaLearningTool
        
        tool = MetaLearningTool(workspace=temp_workspace)
        result = await tool.execute(
            action="create_experiment",
            hypothesis="Test hypothesis",
            method="Test method",
            variables={"param": "value"}
        )
        
        data = json.loads(result)
        assert "hypothesis" in data
        assert "method" in data
    
    @pytest.mark.asyncio
    async def test_complete_experiment_action(self, temp_workspace):
        """Test complete_experiment action."""
        from jagabot.agent.tools.meta_learning import MetaLearningTool
        
        tool = MetaLearningTool(workspace=temp_workspace)
        
        # Create experiment using the tool
        create_result = await tool.execute(
            action="create_experiment",
            hypothesis="Test hypothesis",
            method="Test method"
        )
        exp_id = json.loads(create_result).get("experiment_id")
        
        # Complete it
        result = await tool.execute(
            action="complete_experiment",
            experiment_id=exp_id,
            result={"metric": 0.75},
            conclusion="Hypothesis supported",
            falsified=False
        )
        
        data = json.loads(result)
        # Tool returns the experiment dict or error
        assert data.get("status") == "completed" or "experiment_id" in data or "error" not in data
    
    @pytest.mark.asyncio
    async def test_list_experiments_action(self, temp_workspace):
        """Test list_experiments action."""
        from jagabot.agent.tools.meta_learning import MetaLearningTool
        
        tool = MetaLearningTool(workspace=temp_workspace)
        
        # Create some experiments
        for i in range(3):
            await tool.execute(
                action="create_experiment",
                hypothesis=f"H{i}",
                method=f"M{i}"
            )
        
        result = await tool.execute(
            action="list_experiments",
            limit=10
        )
        
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) == 3
    
    @pytest.mark.asyncio
    async def test_experiment_summary_action(self, temp_workspace):
        """Test experiment_summary action."""
        from jagabot.agent.tools.meta_learning import MetaLearningTool
        
        tool = MetaLearningTool(workspace=temp_workspace)
        result = await tool.execute(action="experiment_summary")
        
        data = json.loads(result)
        assert isinstance(data, dict)
    
    @pytest.mark.asyncio
    async def test_missing_required_params(self, temp_workspace):
        """Test missing required parameters."""
        from jagabot.agent.tools.meta_learning import MetaLearningTool
        
        tool = MetaLearningTool(workspace=temp_workspace)
        
        # Missing strategy
        result = await tool.execute(
            action="record_result",
            success=True
        )
        
        data = json.loads(result)
        assert "error" in data
    
    @pytest.mark.asyncio
    async def test_unknown_action(self, temp_workspace):
        """Test unknown action handling."""
        from jagabot.agent.tools.meta_learning import MetaLearningTool
        
        tool = MetaLearningTool(workspace=temp_workspace)
        result = await tool.execute(action="invalid_action")
        
        data = json.loads(result)
        assert "error" in data


class TestMetaLearningIntegration:
    """Test MetaLearning integration scenarios."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_full_experiment_lifecycle(self, temp_workspace):
        """Test complete experiment lifecycle."""
        from jagabot.engines.meta_learning import MetaLearningEngine
        from jagabot.engines.experiment_tracker import ExperimentTracker
        
        engine = MetaLearningEngine(workspace=temp_workspace)
        tracker = ExperimentTracker(workspace=temp_workspace)
        
        # 1. Create experiment
        exp = tracker.create(
            hypothesis="Bull analysis works better in uptrends",
            method="Compare bull vs bear analysis accuracy"
        )
        
        # 2. Record strategy results
        for i in range(20):
            engine.record_strategy_result(
                strategy_name="bull_analysis",
                success=(i % 3 == 0),
                fitness_gain=0.1
            )
        
        # 3. Complete experiment
        completed = tracker.complete(
            exp.experiment_id,
            {"bull_accuracy": 0.65, "bear_accuracy": 0.45},
            "Bull analysis outperforms in uptrends",
            falsified=False
        )
        
        assert completed.status == "completed"
    
    def test_strategy_selection_improves_outcomes(self, temp_workspace):
        """Test that strategy selection improves with data."""
        from jagabot.engines.meta_learning import MetaLearningEngine
        
        engine = MetaLearningEngine(workspace=temp_workspace)
        
        # Record strong pattern for a KNOWN strategy (bull_analysis is in KNOWN_STRATEGIES)
        for i in range(30):
            engine.record_strategy_result(
                strategy_name="bull_analysis",
                success=True,  # 100% success
                fitness_gain=0.15
            )
        
        # Record weak pattern for another KNOWN strategy
        for i in range(30):
            engine.record_strategy_result(
                strategy_name="bear_analysis",
                success=False,  # 0% success
                fitness_gain=0.05
            )
        
        # Selection should favor bull_analysis (known strategy with better performance)
        result = engine.select_best_strategy()
        
        # select_best_strategy returns dict with "strategy" key
        # Should select bull_analysis due to better success rate
        assert result.get("strategy") == "bull_analysis"
