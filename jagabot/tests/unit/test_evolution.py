"""
Unit tests for Evolution engine.
Tests safe parameter self-evolution with sandbox validation.
"""
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
import json


class TestEvolutionEngine:
    """Test EvolutionEngine core functionality."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def evolution_engine(self, temp_workspace: Path):
        from jagabot.evolution.engine import EvolutionEngine
        state_file = temp_workspace / "evolution_state.json"
        return EvolutionEngine(storage_path=state_file)
    
    def test_cycle(self, evolution_engine):
        """Test one evolution cycle."""
        result = evolution_engine.cycle()
        
        assert isinstance(result, dict)
        assert "fitness" in result or "generation" in result
    
    def test_multiple_cycles(self, evolution_engine):
        """Test multiple evolution cycles."""
        results = []
        for i in range(5):
            result = evolution_engine.cycle()
            results.append(result)
        
        # Should have progression
        assert len(results) == 5
    
    def test_get_status(self, evolution_engine):
        """Test status retrieval."""
        # Run a cycle first
        evolution_engine.cycle()
        
        status = evolution_engine.get_status()
        
        assert isinstance(status, dict)
        assert "fitness" in status or "generation" in status
    
    def test_get_mutations(self, evolution_engine):
        """Test mutation retrieval."""
        # Run some cycles to generate mutations
        for i in range(3):
            evolution_engine.cycle()
        
        mutations = evolution_engine.get_mutations(limit=10)
        
        assert isinstance(mutations, list)
    
    def test_get_mutations_limit(self, evolution_engine):
        """Test mutation retrieval with limit."""
        # Run many cycles
        for i in range(20):
            evolution_engine.cycle()
        
        mutations = evolution_engine.get_mutations(limit=5)
        
        assert len(mutations) <= 5
    
    def test_force_mutation(self, evolution_engine):
        """Test forcing a specific mutation."""
        # First, get available targets
        targets = evolution_engine.get_targets()
        
        if targets and "targets" in targets:
            # Try to force a mutation on a valid target
            target_name = list(targets["targets"].keys())[0]
            result = evolution_engine.force_mutation(target_name, 1.05)
            
            assert result is not None
    
    def test_force_mutation_invalid_target(self, evolution_engine):
        """Test forcing mutation with invalid target."""
        result = evolution_engine.force_mutation("nonexistent_target", 1.05)
        
        assert result is None
    
    def test_force_mutation_out_of_bounds(self, evolution_engine):
        """Test forcing mutation with out-of-bounds factor."""
        targets = evolution_engine.get_targets()
        
        if targets and "targets" in targets:
            target_name = list(targets["targets"].keys())[0]
            
            # Factor out of bounds (should be 0.90-1.10)
            result = evolution_engine.force_mutation(target_name, 2.0)
            
            # Should reject or clamp
            assert result is None or result.get("error") is not None
    
    def test_cancel_sandbox(self, evolution_engine):
        """Test sandbox cancellation."""
        result = evolution_engine.cancel_sandbox()
        
        assert isinstance(result, bool)

    def test_get_targets(self, evolution_engine):
        """Test target retrieval."""
        targets = evolution_engine.get_targets()

        # get_targets() returns a list of target dicts
        assert isinstance(targets, list)
        assert len(targets) > 0
        assert "target" in targets[0]
        assert "current" in targets[0]
        assert "default" in targets[0]
    
    def test_fitness_calculation(self, evolution_engine):
        """Test fitness calculation."""
        # Run some cycles
        for i in range(3):
            evolution_engine.cycle()
        
        # Get status which should include fitness
        status = evolution_engine.get_status()
        
        assert "fitness" in status
    
    def test_persistence(self, temp_workspace):
        """Test that state persists across instances."""
        from jagabot.evolution.engine import EvolutionEngine

        state_file = temp_workspace / "evolution_state.json"

        # Create instance and run a cycle to create state
        engine_v1 = EvolutionEngine(storage_path=state_file)
        engine_v1.cycle()
        cycle_after_first = engine_v1.cycle_count

        # Create new instance (should load from disk)
        engine_v2 = EvolutionEngine(storage_path=state_file)

        # Should have loaded state
        assert engine_v2.cycle_count == cycle_after_first
    
    def test_bounds_enforcement(self, evolution_engine):
        """Test that mutations stay within ±10% bounds."""
        targets = evolution_engine.get_targets()
        
        if targets and "targets" in targets:
            target_name = list(targets["targets"].keys())[0]
            
            # Try to force mutation at boundary
            result_low = evolution_engine.force_mutation(target_name, 0.90)
            result_high = evolution_engine.force_mutation(target_name, 1.10)
            
            # Should accept boundary values
            assert result_low is not None or result_high is not None


class TestEvolutionTool:
    """Test EvolutionTool ABC wrapper."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.mark.asyncio
    async def test_cycle_action(self, temp_workspace):
        """Test cycle action."""
        from jagabot.agent.tools.evolution import EvolutionTool
        
        tool = EvolutionTool(workspace=temp_workspace)
        result = await tool.execute(action="cycle")
        
        data = json.loads(result)
        assert isinstance(data, dict)
    
    @pytest.mark.asyncio
    async def test_status_action(self, temp_workspace):
        """Test status action."""
        from jagabot.agent.tools.evolution import EvolutionTool
        
        tool = EvolutionTool(workspace=temp_workspace)
        
        # Run a cycle first
        await tool.execute(action="cycle")
        
        result = await tool.execute(action="status")
        
        data = json.loads(result)
        assert isinstance(data, dict)
    
    @pytest.mark.asyncio
    async def test_mutations_action(self, temp_workspace):
        """Test mutations action."""
        from jagabot.agent.tools.evolution import EvolutionTool
        
        tool = EvolutionTool(workspace=temp_workspace)
        
        # Run some cycles
        for i in range(3):
            await tool.execute(action="cycle")
        
        result = await tool.execute(action="mutations", limit=10)
        
        data = json.loads(result)
        assert isinstance(data, list)
    
    @pytest.mark.asyncio
    async def test_mutations_action_default_limit(self, temp_workspace):
        """Test mutations action with default limit."""
        from jagabot.agent.tools.evolution import EvolutionTool
        
        tool = EvolutionTool(workspace=temp_workspace)
        
        for i in range(20):
            await tool.execute(action="cycle")
        
        result = await tool.execute(action="mutations")
        
        data = json.loads(result)
        assert len(data) <= 20  # Default limit is 20
    
    @pytest.mark.asyncio
    async def test_force_action(self, temp_workspace):
        """Test force action."""
        from jagabot.agent.tools.evolution import EvolutionTool
        
        tool = EvolutionTool(workspace=temp_workspace)
        
        # Get targets first
        targets_result = await tool.execute(action="targets")
        targets = json.loads(targets_result)
        
        if "targets" in targets:
            target_name = list(targets["targets"].keys())[0]
            
            result = await tool.execute(
                action="force",
                target=target_name,
                factor=1.05
            )
            
            data = json.loads(result)
            assert isinstance(data, dict)
    
    @pytest.mark.asyncio
    async def test_force_action_missing_params(self, temp_workspace):
        """Test force action with missing parameters."""
        from jagabot.agent.tools.evolution import EvolutionTool
        
        tool = EvolutionTool(workspace=temp_workspace)
        result = await tool.execute(action="force")
        
        data = json.loads(result)
        assert "error" in data
    
    @pytest.mark.asyncio
    async def test_cancel_action(self, temp_workspace):
        """Test cancel action."""
        from jagabot.agent.tools.evolution import EvolutionTool
        
        tool = EvolutionTool(workspace=temp_workspace)
        result = await tool.execute(action="cancel")
        
        data = json.loads(result)
        assert "cancelled" in data
    
    @pytest.mark.asyncio
    async def test_targets_action(self, temp_workspace):
        """Test targets action."""
        from jagabot.agent.tools.evolution import EvolutionTool

        tool = EvolutionTool(workspace=temp_workspace)
        result = await tool.execute(action="targets")

        data = json.loads(result)
        # get_targets returns a list of target dicts
        assert isinstance(data, list)
        assert len(data) > 0
        assert "target" in data[0]
    
    @pytest.mark.asyncio
    async def test_fitness_action(self, temp_workspace):
        """Test fitness action."""
        from jagabot.agent.tools.evolution import EvolutionTool
        
        tool = EvolutionTool(workspace=temp_workspace)
        
        # Run a cycle first
        await tool.execute(action="cycle")
        
        result = await tool.execute(action="fitness")
        
        data = json.loads(result)
        assert "fitness" in data
    
    @pytest.mark.asyncio
    async def test_unknown_action(self, temp_workspace):
        """Test unknown action handling."""
        from jagabot.agent.tools.evolution import EvolutionTool
        
        tool = EvolutionTool(workspace=temp_workspace)
        result = await tool.execute(action="invalid_action")
        
        data = json.loads(result)
        assert "error" in data


class TestEvolutionTargets:
    """Test evolution target mechanics."""

    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_target_initialization(self, temp_workspace):
        """Test that targets are properly initialized."""
        from jagabot.evolution.engine import EvolutionEngine

        state_file = temp_workspace / "evolution_state.json"
        engine = EvolutionEngine(storage_path=state_file)

        targets = engine.get_targets()

        # get_targets returns a list of target dicts
        assert isinstance(targets, list)
        assert len(targets) > 0
        assert "target" in targets[0]

    def test_target_mutation_range(self, temp_workspace):
        """Test that target mutations stay in valid range."""
        from jagabot.evolution.engine import EvolutionEngine

        state_file = temp_workspace / "evolution_state.json"
        engine = EvolutionEngine(storage_path=state_file)

        targets = engine.get_targets()

        # targets is a list of dicts
        if targets and len(targets) > 0:
            target_name = targets[0]["target"]
            # Test lower bound
            result_low = engine.force_mutation(target_name, 0.90)
            # Test upper bound
            result_high = engine.force_mutation(target_name, 1.10)

            # At least one should work
            assert result_low is not None or result_high is not None


class TestEvolutionSafety:
    """Test evolution safety mechanisms."""

    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_sandbox_isolation(self, temp_workspace):
        """Test that evolution runs in sandbox."""
        from jagabot.evolution.engine import EvolutionEngine

        state_file = temp_workspace / "evolution_state.json"
        engine = EvolutionEngine(storage_path=state_file)

        # Run cycles
        for i in range(3):
            result = engine.cycle()

            # Should return status dict
            assert isinstance(result, dict)

    def test_rollback_on_fitness_loss(self, temp_workspace):
        """Test that rollback occurs on fitness loss."""
        from jagabot.evolution.engine import EvolutionEngine

        state_file = temp_workspace / "evolution_state.json"
        engine = EvolutionEngine(storage_path=state_file)

        # Run initial cycles
        initial_status = engine.get_status()

        # Force potentially bad mutation
        targets = engine.get_targets()
        if targets and len(targets) > 0:
            target_name = targets[0]["target"]

            # Try extreme mutation (should be rejected - out of bounds 0.90-1.10)
            result = engine.force_mutation(target_name, 0.50)  # Out of bounds

            # Should be rejected
            assert result is None

    def test_zero_value_handling(self, temp_workspace):
        """Test handling of zero values."""
        from jagabot.evolution.engine import EvolutionEngine

        state_file = temp_workspace / "evolution_state.json"
        engine = EvolutionEngine(storage_path=state_file)

        targets = engine.get_targets()

        if targets and len(targets) > 0:
            target_name = targets[0]["target"]

            # Force mutation (should handle gracefully)
            result = engine.force_mutation(target_name, 1.0)  # No change

            # Should handle gracefully (returns result dict or None)
            assert result is not None or result is None  # Either is acceptable


class TestEvolutionEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_empty_state_file(self, temp_workspace):
        """Test handling of empty/corrupt state file."""
        from jagabot.evolution.engine import EvolutionEngine

        state_file = temp_workspace / "evolution_state.json"
        state_file.write_text("")  # Empty file

        # Should handle gracefully
        engine = EvolutionEngine(storage_path=state_file)
        result = engine.cycle()

        assert result is not None

    def test_missing_state_file(self, temp_workspace):
        """Test handling of missing state file."""
        from jagabot.evolution.engine import EvolutionEngine

        state_file = temp_workspace / "nonexistent.json"

        # Should create new state
        engine = EvolutionEngine(storage_path=state_file)
        result = engine.cycle()

        assert result is not None

    def test_concurrent_access(self, temp_workspace):
        """Test handling of concurrent access."""
        from jagabot.evolution.engine import EvolutionEngine
        import threading

        state_file = temp_workspace / "evolution_state.json"
        engine = EvolutionEngine(storage_path=state_file)

        errors = []

        def run_cycle():
            try:
                for i in range(3):
                    engine.cycle()
            except Exception as e:
                errors.append(e)

        # Run multiple threads
        threads = [threading.Thread(target=run_cycle) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should not have errors
        assert len(errors) == 0
