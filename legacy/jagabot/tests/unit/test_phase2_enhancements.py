"""
Unit tests for Phase 2 Core Enhancements.
Tests VectorMemory, EnhancedKnowledgeGraph, and AdaptivePlanner.
"""
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
import json


class TestVectorMemory:
    """Test VectorMemory functionality."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def vector_memory(self, temp_workspace: Path):
        from jagabot.memory.vector_memory import VectorMemory
        return VectorMemory(workspace=temp_workspace)
    
    def test_creation(self, vector_memory):
        """Test VectorMemory creation."""
        assert vector_memory is not None
        assert vector_memory.workspace.exists()
    
    def test_add_memory(self, vector_memory):
        """Test adding memory."""
        node_id = vector_memory.add_memory(
            text="Portfolio risk is high due to market volatility",
            metadata={"topic": "risk", "important": True}
        )
        
        assert node_id is not None
        assert vector_memory.fractal.total_count >= 1
    
    def test_add_multiple_memories(self, vector_memory):
        """Test adding multiple memories."""
        for i in range(5):
            vector_memory.add_memory(f"Memory text {i}", {"index": i})
        
        assert vector_memory.fractal.total_count >= 5
    
    def test_semantic_search(self, vector_memory):
        """Test semantic search (falls back to keyword if no model)."""
        # Add some memories
        vector_memory.add_memory("Portfolio risk analysis shows high volatility")
        vector_memory.add_memory("Market outlook is positive for tech stocks")
        vector_memory.add_memory("Bond yields are rising steadily")
        
        # Search
        results = vector_memory.semantic_search("What are the risks?", top_k=2)
        
        assert isinstance(results, list)
        assert len(results) <= 2
    
    def test_semantic_search_empty(self, vector_memory):
        """Test search with no memories."""
        results = vector_memory.semantic_search("test query")
        
        assert isinstance(results, list)
    
    def test_get_stats(self, vector_memory):
        """Test statistics retrieval."""
        stats = vector_memory.get_stats()
        
        assert isinstance(stats, dict)
        assert "vector_support" in stats
        assert "total_vectors" in stats
        assert "total_nodes" in stats
    
    def test_find_similar_to_text(self, vector_memory):
        """Test finding similar memories."""
        vector_memory.add_memory("AAPL stock analysis")
        vector_memory.add_memory("MSFT earnings report")
        vector_memory.add_memory("Portfolio diversification strategy")
        
        # Find similar (may return empty if no vector model)
        results = vector_memory.find_similar_to_text("Apple stock", threshold=0.5)
        
        assert isinstance(results, list)
    
    def test_clear(self, vector_memory):
        """Test clearing memories."""
        vector_memory.add_memory("Test memory")
        vector_memory.clear()
        
        stats = vector_memory.get_stats()
        assert stats["total_vectors"] == 0 or stats["total_metadata"] == 0
    
    def test_persistence(self, temp_workspace):
        """Test that vectors persist across instances."""
        from jagabot.memory.vector_memory import VectorMemory
        
        # Create instance and add memory
        vm_v1 = VectorMemory(workspace=temp_workspace)
        vm_v1.add_memory("Persistent memory")
        
        # Create new instance
        vm_v2 = VectorMemory(workspace=temp_workspace)
        stats = vm_v2.get_stats()
        
        # Should have loaded existing data
        assert stats["total_metadata"] >= 1 or stats["total_nodes"] >= 1


class TestVectorMemoryTool:
    """Test VectorMemoryTool wrapper."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.mark.asyncio
    async def test_search_action(self, temp_workspace):
        """Test search action."""
        from jagabot.memory.vector_memory import VectorMemoryTool
        
        tool = VectorMemoryTool(workspace=temp_workspace)
        result = await tool.execute(action="search", query="test", top_k=5)
        
        data = json.loads(result)
        assert "results" in data
    
    @pytest.mark.asyncio
    async def test_add_action(self, temp_workspace):
        """Test add action."""
        from jagabot.memory.vector_memory import VectorMemoryTool
        
        tool = VectorMemoryTool(workspace=temp_workspace)
        result = await tool.execute(
            action="add",
            text="Test memory",
            metadata={"topic": "test"}
        )
        
        data = json.loads(result)
        assert "node_id" in data or "stored" in data
    
    @pytest.mark.asyncio
    async def test_stats_action(self, temp_workspace):
        """Test stats action."""
        from jagabot.memory.vector_memory import VectorMemoryTool
        
        tool = VectorMemoryTool(workspace=temp_workspace)
        result = await tool.execute(action="stats")
        
        data = json.loads(result)
        assert "vector_support" in data
    
    @pytest.mark.asyncio
    async def test_clear_action(self, temp_workspace):
        """Test clear action."""
        from jagabot.memory.vector_memory import VectorMemoryTool
        
        tool = VectorMemoryTool(workspace=temp_workspace)
        result = await tool.execute(action="clear")
        
        data = json.loads(result)
        assert "cleared" in data
    
    @pytest.mark.asyncio
    async def test_unknown_action(self, temp_workspace):
        """Test unknown action handling."""
        from jagabot.memory.vector_memory import VectorMemoryTool
        
        tool = VectorMemoryTool(workspace=temp_workspace)
        result = await tool.execute(action="invalid_action")
        
        data = json.loads(result)
        assert "error" in data


class TestEnhancedKnowledgeGraph:
    """Test EnhancedKnowledgeGraph functionality."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def graph(self, temp_workspace: Path):
        from jagabot.memory.knowledge_graph_enhanced import EnhancedKnowledgeGraph
        return EnhancedKnowledgeGraph(workspace=temp_workspace)
    
    def test_creation(self, graph):
        """Test graph creation."""
        assert graph is not None
        assert graph.workspace.exists()
    
    def test_extract_entities(self, graph):
        """Test entity extraction."""
        text = "Apple stock rose 5% to $150 in January 2026"
        entities = graph.extract_entities(text)
        
        assert isinstance(entities, dict)
        # Should extract some entities (type depends on spacy availability)
    
    def test_extract_relations(self, graph):
        """Test relation extraction."""
        text = "Investors bought shares after the earnings report"
        relations = graph.extract_relations(text)
        
        assert isinstance(relations, list)
    
    def test_analyze_text(self, graph):
        """Test full text analysis."""
        text = "Microsoft reported strong earnings. Stock price increased 10%."
        result = graph.analyze_text(text)
        
        assert isinstance(result, dict)
        assert "entities" in result
        assert "relations" in result
        assert "entity_count" in result
    
    def test_get_stats(self, graph):
        """Test statistics retrieval."""
        stats = graph.get_stats()
        
        assert isinstance(stats, dict)
        assert "total_entity_types" in stats
        assert "spacy_support" in stats
    
    def test_query_entities(self, graph):
        """Test entity querying."""
        graph.extract_entities("Tesla stock rose in California")
        
        entities = graph.query_entities()
        assert isinstance(entities, dict)
    
    def test_get_entity_connections(self, graph):
        """Test entity connection retrieval."""
        graph.extract_relations("Apple released new products")
        
        connections = graph.get_entity_connections("Apple")
        assert isinstance(connections, list)
    
    def test_export_graph(self, graph, temp_workspace):
        """Test graph export."""
        graph.extract_entities("Test entity")
        
        path = graph.export_graph()
        
        assert path.exists()
        assert path.name == "entity_graph.json"
    
    def test_clear(self, graph):
        """Test clearing graph."""
        graph.extract_entities("Test")
        graph.clear()
        
        stats = graph.get_stats()
        assert stats["total_entities"] == 0


class TestEnhancedKnowledgeGraphTool:
    """Test EnhancedKnowledgeGraphTool wrapper."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.mark.asyncio
    async def test_analyze_action(self, temp_workspace):
        """Test analyze action."""
        from jagabot.memory.knowledge_graph_enhanced import EnhancedKnowledgeGraphTool
        
        tool = EnhancedKnowledgeGraphTool(workspace=temp_workspace)
        result = await tool.execute(
            action="analyze",
            text="Apple stock rose 5% on strong earnings"
        )
        
        data = json.loads(result)
        assert "entities" in data
    
    @pytest.mark.asyncio
    async def test_entities_action(self, temp_workspace):
        """Test entities action."""
        from jagabot.memory.knowledge_graph_enhanced import EnhancedKnowledgeGraphTool
        
        tool = EnhancedKnowledgeGraphTool(workspace=temp_workspace)
        result = await tool.execute(action="entities")
        
        data = json.loads(result)
        assert isinstance(data, dict)
    
    @pytest.mark.asyncio
    async def test_relations_action(self, temp_workspace):
        """Test relations action."""
        from jagabot.memory.knowledge_graph_enhanced import EnhancedKnowledgeGraphTool
        
        tool = EnhancedKnowledgeGraphTool(workspace=temp_workspace)
        result = await tool.execute(action="relations")
        
        data = json.loads(result)
        assert "relations" in data
    
    @pytest.mark.asyncio
    async def test_stats_action(self, temp_workspace):
        """Test stats action."""
        from jagabot.memory.knowledge_graph_enhanced import EnhancedKnowledgeGraphTool
        
        tool = EnhancedKnowledgeGraphTool(workspace=temp_workspace)
        result = await tool.execute(action="stats")
        
        data = json.loads(result)
        assert "total_entity_types" in data
    
    @pytest.mark.asyncio
    async def test_query_action(self, temp_workspace):
        """Test query action."""
        from jagabot.memory.knowledge_graph_enhanced import EnhancedKnowledgeGraphTool
        
        tool = EnhancedKnowledgeGraphTool(workspace=temp_workspace)
        result = await tool.execute(action="query", entity="Test")
        
        data = json.loads(result)
        assert "entity" in data
    
    @pytest.mark.asyncio
    async def test_export_action(self, temp_workspace):
        """Test export action."""
        from jagabot.memory.knowledge_graph_enhanced import EnhancedKnowledgeGraphTool
        
        tool = EnhancedKnowledgeGraphTool(workspace=temp_workspace)
        result = await tool.execute(action="export")
        
        data = json.loads(result)
        assert "exported" in data


class TestAdaptivePlanner:
    """Test AdaptivePlanner functionality."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def planner(self, temp_workspace: Path):
        from jagabot.swarm.adaptive_planner import AdaptivePlanner
        return AdaptivePlanner(workspace=temp_workspace)
    
    def test_creation(self, planner):
        """Test planner creation."""
        assert planner is not None
        assert planner.workspace.exists()
    
    def test_plan(self, planner):
        """Test plan generation."""
        plan = planner.plan("Analyze AAPL stock risk")
        
        assert plan is not None
        assert plan.task_id == "Analyze AAPL stock risk"
        assert isinstance(plan.steps, list)
        assert plan.strategy in planner.STRATEGIES
    
    def test_plan_with_context(self, planner):
        """Test planning with context."""
        context = {"portfolio_value": 100000, "risk_tolerance": "high"}
        plan = planner.plan("Optimize portfolio", context)
        
        assert plan is not None
        assert plan.task_id == "Optimize portfolio"
    
    def test_replan(self, planner):
        """Test replanning after failures."""
        from jagabot.swarm.adaptive_planner import FailureRecord, FailureType
        
        # Create initial plan
        plan1 = planner.plan("Complex analysis task")
        
        # Simulate failures
        failures = [
            FailureRecord(
                task_id="Complex analysis task",
                tool_name="web_search",
                failure_type=FailureType.TIMEOUT,
                error_message="Request timed out"
            )
        ]
        
        # Replan
        plan2 = planner.replan("Complex analysis task", failures)
        
        assert plan2.strategy != plan1.strategy or plan2.timeout_multiplier > 1.0
    
    def test_record_success(self, planner):
        """Test recording successful strategies."""
        planner.record_success("task1", "default")
        planner.record_success("task2", "default")
        
        best = planner.get_best_strategy()
        assert best == "default"
    
    def test_get_best_strategy(self, planner):
        """Test best strategy retrieval."""
        planner.record_success("task1", "strategy_a")
        planner.record_success("task2", "strategy_a")
        planner.record_success("task3", "strategy_b")
        
        best = planner.get_best_strategy()
        assert best == "strategy_a"
    
    def test_get_stats(self, planner):
        """Test statistics retrieval."""
        planner.plan("Test task")
        
        stats = planner.get_stats()
        
        assert isinstance(stats, dict)
        assert "total_plans" in stats
        assert "best_strategy" in stats
    
    def test_clear_history(self, planner):
        """Test clearing history."""
        planner.plan("Test")
        planner.clear_history()
        
        stats = planner.get_stats()
        assert stats["total_plans"] == 0


class TestAdaptivePlannerTool:
    """Test AdaptivePlannerTool wrapper."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.mark.asyncio
    async def test_plan_action(self, temp_workspace):
        """Test plan action."""
        from jagabot.swarm.adaptive_planner import AdaptivePlannerTool
        
        tool = AdaptivePlannerTool(workspace=temp_workspace)
        result = await tool.execute(action="plan", task="Test task")
        
        data = json.loads(result)
        assert "task_id" in data
        assert "steps" in data
    
    @pytest.mark.asyncio
    async def test_replan_action(self, temp_workspace):
        """Test replan action."""
        from jagabot.swarm.adaptive_planner import AdaptivePlannerTool, FailureType
        
        tool = AdaptivePlannerTool(workspace=temp_workspace)
        
        # First create a plan
        await tool.execute(action="plan", task="Test task")
        
        # Then replan with failures
        result = await tool.execute(
            action="replan",
            task="Test task",
            failures=[{
                "task_id": "Test task",
                "tool_name": "test_tool",
                "failure_type": FailureType.TIMEOUT.value,
                "error_message": "Timeout"
            }]
        )
        
        data = json.loads(result)
        assert "strategy" in data
    
    @pytest.mark.asyncio
    async def test_stats_action(self, temp_workspace):
        """Test stats action."""
        from jagabot.swarm.adaptive_planner import AdaptivePlannerTool
        
        tool = AdaptivePlannerTool(workspace=temp_workspace)
        result = await tool.execute(action="stats")
        
        data = json.loads(result)
        assert "total_plans" in data
    
    @pytest.mark.asyncio
    async def test_best_strategy_action(self, temp_workspace):
        """Test best_strategy action."""
        from jagabot.swarm.adaptive_planner import AdaptivePlannerTool
        
        tool = AdaptivePlannerTool(workspace=temp_workspace)
        result = await tool.execute(action="best_strategy")
        
        data = json.loads(result)
        assert "best_strategy" in data
    
    @pytest.mark.asyncio
    async def test_clear_action(self, temp_workspace):
        """Test clear action."""
        from jagabot.swarm.adaptive_planner import AdaptivePlannerTool
        
        tool = AdaptivePlannerTool(workspace=temp_workspace)
        result = await tool.execute(action="clear")
        
        data = json.loads(result)
        assert "cleared" in data
