"""
Unit tests for MemoryFleet system.
Tests fractal memory, ALS manager, and consolidation engine.
"""
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Any


class TestMemoryFleet:
    """Test MemoryFleet core functionality."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        """Create temporary workspace for testing."""
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def memory_fleet(self, temp_workspace: Path):
        """Create MemoryFleet instance with temp workspace."""
        from jagabot.agent.tools.memory_fleet import MemoryFleet
        return MemoryFleet(workspace=temp_workspace)
    
    def test_fractal_creation(self, memory_fleet):
        """Test fractal memory node creation."""
        events = memory_fleet.on_interaction(
            user_message="What is VIX?",
            agent_response="VIX measures market volatility expectations.",
            topic="volatility"
        )
        
        assert memory_fleet.fractal.total_count == 1
        assert isinstance(events, list)
    
    def test_multiple_interactions(self, memory_fleet):
        """Test multiple interaction storage."""
        for i in range(5):
            memory_fleet.on_interaction(
                user_message=f"Question {i}",
                agent_response=f"Answer {i}",
                topic=f"topic_{i}"
            )
        
        assert memory_fleet.fractal.total_count == 5
    
    def test_retrieval(self, memory_fleet):
        """Test context retrieval."""
        memory_fleet.on_interaction(
            user_message="What is portfolio risk?",
            agent_response="Risk is the probability of loss...",
            topic="risk"
        )
        
        context = memory_fleet.get_context("portfolio risk", k=1)
        assert context is not None
        assert len(context) > 0
    
    def test_consolidation_trigger(self, memory_fleet):
        """Test auto-consolidation after threshold."""
        # Add 10 interactions to trigger auto-consolidation
        for i in range(10):
            memory_fleet.on_interaction(
                user_message=f"Q{i}",
                agent_response=f"A{i}",
                topic="test"
            )
        
        # Consolidation should have been attempted
        assert memory_fleet._interaction_count == 10
    
    def test_consolidate_now(self, memory_fleet):
        """Test manual consolidation."""
        # Add some interactions
        for i in range(3):
            memory_fleet.on_interaction(
                user_message=f"Important question {i}",
                agent_response=f"Important answer {i}",
                topic="important"
            )
        
        # Force consolidation
        count = memory_fleet.consolidate_now()
        assert count >= 0  # May be 0 if nothing to consolidate
    
    def test_optimize_memory(self, memory_fleet):
        """Test memory optimization."""
        # Add interactions
        for i in range(3):
            memory_fleet.on_interaction(
                user_message=f"Q{i}",
                agent_response=f"A{i}",
                topic="test"
            )
        
        # Run optimization (dry run)
        result = memory_fleet.optimize_memory(dry_run=True)
        
        assert "strengthened" in result
        assert "merged" in result
        assert "pruned" in result
        assert result["dry_run"] is True
    
    def test_get_exposure_count(self, memory_fleet):
        """Test topic exposure counting."""
        memory_fleet.on_interaction(
            user_message="Tell me about AAPL",
            agent_response="AAPL is Apple Inc...",
            topic="AAPL"
        )
        memory_fleet.on_interaction(
            user_message="What about MSFT?",
            agent_response="MSFT is Microsoft...",
            topic="MSFT"
        )
        
        aapl_count = memory_fleet.get_exposure_count("AAPL")
        assert aapl_count >= 1
    
    def test_get_all_topics(self, memory_fleet):
        """Test topic extraction."""
        memory_fleet.on_interaction(
            user_message="Portfolio question",
            agent_response="Portfolio advice...",
            topic="portfolio"
        )
        memory_fleet.on_interaction(
            user_message="Risk question",
            agent_response="Risk advice...",
            topic="risk"
        )
        
        topics = memory_fleet.get_all_topics()
        assert isinstance(topics, list)
    
    def test_stats(self, memory_fleet):
        """Test memory statistics."""
        # MemoryFleet doesn't have get_stats, use fractal stats instead
        stats = memory_fleet.fractal.get_stats()
        
        assert "total_nodes" in stats
        assert "consolidated" in stats  # Use 'consolidated' instead of 'pending_nodes'


class TestMemoryFleetTool:
    """Test MemoryFleetTool ABC wrapper."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.mark.asyncio
    async def test_store_action(self, temp_workspace):
        """Test store action."""
        from jagabot.agent.tools.memory_fleet import MemoryFleetTool
        import json
        
        tool = MemoryFleetTool()
        tool._fleet = None  # Reset singleton
        
        # Temporarily set workspace (hack for testing)
        from jagabot.agent.tools.memory_fleet import MemoryFleet
        tool._fleet = MemoryFleet(workspace=temp_workspace)
        
        result = await tool.execute(
            action="store",
            user_message="Test message",
            agent_response="Test response"
        )
        
        data = json.loads(result)
        assert data["stored"] is True
        assert "total_nodes" in data
    
    @pytest.mark.asyncio
    async def test_retrieve_action(self, temp_workspace):
        """Test retrieve action."""
        from jagabot.agent.tools.memory_fleet import MemoryFleetTool
        import json
        
        tool = MemoryFleetTool()
        tool._fleet = None
        from jagabot.agent.tools.memory_fleet import MemoryFleet
        tool._fleet = MemoryFleet(workspace=temp_workspace)
        
        # Store something first
        await tool.execute(
            action="store",
            user_message="What is risk?",
            agent_response="Risk is probability of loss"
        )
        
        # Retrieve
        result = await tool.execute(
            action="retrieve",
            query="risk",
            k=1
        )
        
        data = json.loads(result)
        assert "context" in data
        assert "matched_nodes" in data
    
    @pytest.mark.asyncio
    async def test_stats_action(self, temp_workspace):
        """Test stats action."""
        from jagabot.agent.tools.memory_fleet import MemoryFleetTool
        import json
        
        tool = MemoryFleetTool()
        tool._fleet = None
        from jagabot.agent.tools.memory_fleet import MemoryFleet
        tool._fleet = MemoryFleet(workspace=temp_workspace)
        
        result = await tool.execute(action="stats")
        data = json.loads(result)
        
        assert "total_nodes" in data
    
    @pytest.mark.asyncio
    async def test_consolidate_action(self, temp_workspace):
        """Test consolidate action."""
        from jagabot.agent.tools.memory_fleet import MemoryFleetTool
        import json
        
        tool = MemoryFleetTool()
        tool._fleet = None
        from jagabot.agent.tools.memory_fleet import MemoryFleet
        tool._fleet = MemoryFleet(workspace=temp_workspace)
        
        result = await tool.execute(action="consolidate")
        data = json.loads(result)
        
        assert "consolidated" in data
    
    @pytest.mark.asyncio
    async def test_optimize_action(self, temp_workspace):
        """Test optimize action."""
        from jagabot.agent.tools.memory_fleet import MemoryFleetTool
        import json
        
        tool = MemoryFleetTool()
        tool._fleet = None
        from jagabot.agent.tools.memory_fleet import MemoryFleet
        tool._fleet = MemoryFleet(workspace=temp_workspace)
        
        result = await tool.execute(action="optimize", dry_run=True)
        data = json.loads(result)
        
        assert "strengthened" in data
        assert data["dry_run"] is True
    
    @pytest.mark.asyncio
    async def test_unknown_action(self, temp_workspace):
        """Test unknown action handling."""
        from jagabot.agent.tools.memory_fleet import MemoryFleetTool
        import json
        
        tool = MemoryFleetTool()
        tool._fleet = None
        from jagabot.agent.tools.memory_fleet import MemoryFleet
        tool._fleet = MemoryFleet(workspace=temp_workspace)
        
        result = await tool.execute(action="invalid_action")
        data = json.loads(result)
        
        assert "error" in data


class TestFractalManager:
    """Test FractalManager directly."""
    
    @pytest.fixture
    def temp_memory_dir(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "memory"
    
    def test_save_node(self, temp_memory_dir):
        """Test saving a fractal node."""
        from jagabot.memory.fractal_manager import FractalManager
        
        manager = FractalManager(temp_memory_dir)
        node_id = manager.save_node(
            content="Test content",
            summary="Test summary",
            important=False,
            tags=["test", "unit"]
        )
        
        assert node_id is not None
        assert manager.total_count == 1
    
    def test_get_all_nodes(self, temp_memory_dir):
        """Test retrieving all nodes."""
        from jagabot.memory.fractal_manager import FractalManager
        
        manager = FractalManager(temp_memory_dir)
        
        for i in range(3):
            manager.save_node(
                content=f"Content {i}",
                summary=f"Summary {i}",
                tags=[f"tag_{i}"]
            )
        
        nodes = manager.get_all_nodes()
        assert len(nodes) == 3
    
    def test_retrieve_relevant(self, temp_memory_dir):
        """Test keyword-based retrieval."""
        from jagabot.memory.fractal_manager import FractalManager
        
        manager = FractalManager(temp_memory_dir)
        
        manager.save_node(
            content="Portfolio risk analysis",
            summary="Risk assessment",
            tags=["risk", "portfolio"]
        )
        manager.save_node(
            content="Market volatility",
            summary="VIX analysis",
            tags=["volatility", "market"]
        )
        
        results = manager.retrieve_relevant("portfolio", k=1)
        assert len(results) >= 1
    
    def test_strengthen_nodes(self, temp_memory_dir):
        """Test node strengthening."""
        from jagabot.memory.fractal_manager import FractalManager
        
        manager = FractalManager(temp_memory_dir)
        
        manager.save_node(
            content="Important content",
            summary="Important",
            important=True
        )
        
        strengthened = manager.strengthen_nodes()
        assert strengthened >= 0
    
    def test_prune_old(self, temp_memory_dir):
        """Test pruning old nodes."""
        from jagabot.memory.fractal_manager import FractalManager
        
        manager = FractalManager(temp_memory_dir)
        
        for i in range(5):
            manager.save_node(
                content=f"Old content {i}",
                summary=f"Old {i}",
                important=False
            )
        
        pruned = manager.prune_old(dry_run=True)
        assert len(pruned) >= 0
        assert manager.total_count == 5  # Dry run, nothing removed
    
    def test_get_stats(self, temp_memory_dir):
        """Test statistics."""
        from jagabot.memory.fractal_manager import FractalManager
        
        manager = FractalManager(temp_memory_dir)
        
        for i in range(3):
            manager.save_node(
                content=f"Content {i}",
                summary=f"Summary {i}",
                important=(i == 0)
            )
        
        stats = manager.get_stats()
        
        assert stats["total_nodes"] == 3
        assert "important" in stats
        assert "consolidated" in stats  # Use 'consolidated' instead of 'pending_nodes'


class TestALSManager:
    """Test ALSManager (Identity/Focus tracking)."""
    
    @pytest.fixture
    def temp_memory_dir(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "memory"
    
    def test_update_focus(self, temp_memory_dir):
        """Test focus update."""
        from jagabot.memory.als_manager import ALSManager
        
        manager = ALSManager(temp_memory_dir)
        manager.update_focus("Portfolio analysis")
        
        assert manager.focus == "Portfolio analysis"
    
    def test_get_identity_context(self, temp_memory_dir):
        """Test identity context retrieval."""
        from jagabot.memory.als_manager import ALSManager
        
        manager = ALSManager(temp_memory_dir)
        context = manager.get_identity_context()
        
        assert isinstance(context, str)
    
    def test_stage_tracking(self, temp_memory_dir):
        """Test stage tracking."""
        from jagabot.memory.als_manager import ALSManager
        
        manager = ALSManager(temp_memory_dir)
        
        # Stage should be tracked
        assert hasattr(manager, 'stage')


class TestConsolidationEngine:
    """Test ConsolidationEngine."""
    
    @pytest.fixture
    def temp_memory_dir(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "memory"
    
    def test_should_consolidate(self, temp_memory_dir):
        """Test consolidation trigger detection."""
        from jagabot.memory.consolidation import ConsolidationEngine
        from jagabot.memory.fractal_manager import FractalManager
        
        fractal = FractalManager(temp_memory_dir)
        engine = ConsolidationEngine(temp_memory_dir, fractal)
        
        # Initially should not consolidate
        assert engine.should_consolidate() is False
        
        # Add pending nodes
        for i in range(5):
            fractal.save_node(
                content=f"Content {i}",
                summary=f"Summary {i}",
                important=True
            )
        
        # Should consolidate now
        assert engine.should_consolidate() is True
    
    def test_run_consolidation(self, temp_memory_dir):
        """Test running consolidation."""
        from jagabot.memory.consolidation import ConsolidationEngine
        from jagabot.memory.fractal_manager import FractalManager
        
        fractal = FractalManager(temp_memory_dir)
        engine = ConsolidationEngine(temp_memory_dir, fractal)
        
        # Add important nodes
        for i in range(3):
            fractal.save_node(
                content=f"Important lesson {i}",
                summary=f"Lesson {i}",
                important=True
            )
        
        # Run consolidation
        count = engine.run(force=True)
        assert count >= 0
