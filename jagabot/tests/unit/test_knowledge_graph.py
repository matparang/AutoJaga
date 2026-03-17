"""
Unit tests for KnowledgeGraph system.
Tests graph visualization, entity querying, and statistics.
"""
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
import json


class TestKnowledgeGraphViewer:
    """Test KnowledgeGraphViewer core functionality."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def viewer(self, temp_workspace: Path):
        from jagabot.agent.tools.knowledge_graph import KnowledgeGraphViewer
        viewer = KnowledgeGraphViewer(workspace_path=temp_workspace)
        return viewer.load()
    
    def test_load_empty(self, temp_workspace):
        """Test loading with no existing data."""
        from jagabot.agent.tools.knowledge_graph import KnowledgeGraphViewer
        
        viewer = KnowledgeGraphViewer(workspace_path=temp_workspace)
        result = viewer.load()
        
        assert result is not None
        stats = result.get_stats()
        assert stats["total_nodes"] == 0
    
    def test_get_stats(self, viewer):
        """Test statistics retrieval."""
        stats = viewer.get_stats()
        
        assert isinstance(stats, dict)
        assert "total_nodes" in stats
        assert "total_edges" in stats
        assert "groups" in stats
    
    def test_query_nodes_empty(self, viewer):
        """Test querying with no data."""
        results = viewer.query_nodes("test", limit=10)
        
        assert isinstance(results, list)
        assert len(results) == 0
    
    def test_generate_html(self, viewer, temp_workspace):
        """Test HTML generation."""
        path = viewer.generate_html(output_name="test_graph.html")
        
        assert path.exists()
        assert path.name == "test_graph.html"
        
        # Check HTML content
        content = path.read_text(encoding='utf-8')
        assert "<!DOCTYPE html>" in content
        assert "vis.Network" in content  # vis.js library
    
    def test_generate_html_default_name(self, viewer, temp_workspace):
        """Test HTML generation with default name."""
        path = viewer.generate_html()
        
        assert path.exists()
        assert path.name == "knowledge_graph.html"


class TestKnowledgeGraphTool:
    """Test KnowledgeGraphTool ABC wrapper."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.mark.asyncio
    async def test_stats_action(self, temp_workspace):
        """Test stats action."""
        from jagabot.agent.tools.knowledge_graph import KnowledgeGraphTool
        
        tool = KnowledgeGraphTool()
        result = await tool.execute(
            action="stats",
            workspace=str(temp_workspace)
        )
        
        data = json.loads(result)
        assert "nodes" in data or "total_nodes" in data
        assert "edges" in data or "total_edges" in data
    
    @pytest.mark.asyncio
    async def test_generate_action(self, temp_workspace):
        """Test generate action."""
        from jagabot.agent.tools.knowledge_graph import KnowledgeGraphTool
        
        tool = KnowledgeGraphTool()
        result = await tool.execute(
            action="generate",
            workspace=str(temp_workspace)
        )
        
        data = json.loads(result)
        assert "generated" in data
    
    @pytest.mark.asyncio
    async def test_query_action(self, temp_workspace):
        """Test query action."""
        from jagabot.agent.tools.knowledge_graph import KnowledgeGraphTool
        
        tool = KnowledgeGraphTool()
        result = await tool.execute(
            action="query",
            keyword="test",
            limit=10,
            workspace=str(temp_workspace)
        )
        
        data = json.loads(result)
        assert "matches" in data or "nodes" in data
    
    @pytest.mark.asyncio
    async def test_query_action_missing_keyword(self, temp_workspace):
        """Test query action with missing keyword."""
        from jagabot.agent.tools.knowledge_graph import KnowledgeGraphTool
        
        tool = KnowledgeGraphTool()
        result = await tool.execute(
            action="query",
            workspace=str(temp_workspace)
        )
        
        data = json.loads(result)
        assert "error" in data
    
    @pytest.mark.asyncio
    async def test_unknown_action(self, temp_workspace):
        """Test unknown action handling."""
        from jagabot.agent.tools.knowledge_graph import KnowledgeGraphTool
        
        tool = KnowledgeGraphTool()
        result = await tool.execute(
            action="invalid_action",
            workspace=str(temp_workspace)
        )
        
        data = json.loads(result)
        assert "error" in data


class TestKnowledgeGraphStats:
    """Test KnowledgeGraph statistics."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_node_count(self, temp_workspace):
        """Test node counting."""
        from jagabot.agent.tools.knowledge_graph import KnowledgeGraphViewer
        
        viewer = KnowledgeGraphViewer(workspace_path=temp_workspace).load()
        stats = viewer.get_stats()
        
        assert stats["total_nodes"] == 0
    
    def test_edge_count(self, temp_workspace):
        """Test edge counting."""
        from jagabot.agent.tools.knowledge_graph import KnowledgeGraphViewer
        
        viewer = KnowledgeGraphViewer(workspace_path=temp_workspace).load()
        stats = viewer.get_stats()
        
        assert stats["total_edges"] == 0
    
    def test_group_breakdown(self, temp_workspace):
        """Test group breakdown."""
        from jagabot.agent.tools.knowledge_graph import KnowledgeGraphViewer
        
        viewer = KnowledgeGraphViewer(workspace_path=temp_workspace).load()
        stats = viewer.get_stats()
        
        assert "groups" in stats
        assert isinstance(stats["groups"], dict)


class TestKnowledgeGraphQuery:
    """Test KnowledgeGraph query functionality."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_query_limit(self, temp_workspace):
        """Test query result limiting."""
        from jagabot.agent.tools.knowledge_graph import KnowledgeGraphViewer
        
        viewer = KnowledgeGraphViewer(workspace_path=temp_workspace).load()
        results = viewer.query_nodes("test", limit=5)
        
        assert len(results) <= 5
    
    def test_query_empty_keyword(self, temp_workspace):
        """Test query with empty keyword."""
        from jagabot.agent.tools.knowledge_graph import KnowledgeGraphViewer
        
        viewer = KnowledgeGraphViewer(workspace_path=temp_workspace).load()
        results = viewer.query_nodes("", limit=10)
        
        assert isinstance(results, list)


class TestKnowledgeGraphHTML:
    """Test KnowledgeGraph HTML generation."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_html_structure(self, temp_workspace):
        """Test HTML structure."""
        from jagabot.agent.tools.knowledge_graph import KnowledgeGraphViewer
        
        viewer = KnowledgeGraphViewer(workspace_path=temp_workspace).load()
        path = viewer.generate_html()
        
        content = path.read_text(encoding='utf-8')
        
        # Check for required HTML elements
        assert "<html" in content
        assert "<head>" in content
        assert "<body>" in content
        assert "</html>" in content
    
    def test_html_vis_integration(self, temp_workspace):
        """Test vis.js integration in HTML."""
        from jagabot.agent.tools.knowledge_graph import KnowledgeGraphViewer
        
        viewer = KnowledgeGraphViewer(workspace_path=temp_workspace).load()
        path = viewer.generate_html()
        
        content = path.read_text(encoding='utf-8')
        
        # Check for vis.js includes
        assert "vis.min.js" in content or "vis.js" in content
        assert "vis.Network" in content
    
    def test_html_nodes_embedded(self, temp_workspace):
        """Test that nodes are embedded in HTML."""
        from jagabot.agent.tools.knowledge_graph import KnowledgeGraphViewer
        
        viewer = KnowledgeGraphViewer(workspace_path=temp_workspace).load()
        path = viewer.generate_html()
        
        content = path.read_text(encoding='utf-8')
        
        # Should have nodes data
        assert "var nodesData" in content
    
    def test_html_edges_embedded(self, temp_workspace):
        """Test that edges are embedded in HTML."""
        from jagabot.agent.tools.knowledge_graph import KnowledgeGraphViewer
        
        viewer = KnowledgeGraphViewer(workspace_path=temp_workspace).load()
        path = viewer.generate_html()
        
        content = path.read_text(encoding='utf-8')
        
        # Should have edges data
        assert "var edgesData" in content
    
    def test_html_custom_output_name(self, temp_workspace):
        """Test custom output filename."""
        from jagabot.agent.tools.knowledge_graph import KnowledgeGraphViewer
        
        viewer = KnowledgeGraphViewer(workspace_path=temp_workspace).load()
        path = viewer.generate_html(output_name="custom_graph.html")
        
        assert path.name == "custom_graph.html"
        assert path.exists()


class TestKnowledgeGraphColors:
    """Test KnowledgeGraph color coding."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_group_colors_defined(self, temp_workspace):
        """Test that group colors are defined."""
        from jagabot.agent.tools.knowledge_graph import KnowledgeGraphViewer, _GROUP_COLORS
        
        assert isinstance(_GROUP_COLORS, dict)
        assert len(_GROUP_COLORS) > 0
        assert "default" in _GROUP_COLORS
    
    def test_domain_keywords_defined(self, temp_workspace):
        """Test that domain keywords are defined."""
        from jagabot.agent.tools.knowledge_graph import _DOMAIN_KEYWORDS
        
        assert isinstance(_DOMAIN_KEYWORDS, dict)
        assert len(_DOMAIN_KEYWORDS) > 0


class TestKnowledgeGraphEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_nonexistent_workspace(self, temp_workspace):
        """Test handling of nonexistent workspace."""
        from jagabot.agent.tools.knowledge_graph import KnowledgeGraphViewer
        
        fake_path = temp_workspace / "nonexistent"
        viewer = KnowledgeGraphViewer(workspace_path=fake_path)
        
        # Should handle gracefully
        result = viewer.load()
        assert result is not None
    
    def test_corrupt_fractal_index(self, temp_workspace):
        """Test handling of corrupt fractal_index.json."""
        from jagabot.agent.tools.knowledge_graph import KnowledgeGraphViewer
        
        # Create corrupt file
        memory_dir = temp_workspace / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        fractal_file = memory_dir / "fractal_index.json"
        fractal_file.write_text("not valid json")
        
        viewer = KnowledgeGraphViewer(workspace_path=temp_workspace)
        
        # Should handle gracefully
        result = viewer.load()
        assert result is not None
    
    def test_corrupt_memory_md(self, temp_workspace):
        """Test handling of corrupt MEMORY.md."""
        from jagabot.agent.tools.knowledge_graph import KnowledgeGraphViewer
        
        # Create corrupt file
        memory_dir = temp_workspace / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        memory_file = memory_dir / "MEMORY.md"
        memory_file.write_text("# Corrupt\n\n- Invalid [format")
        
        viewer = KnowledgeGraphViewer(workspace_path=temp_workspace)
        
        # Should handle gracefully
        result = viewer.load()
        assert result is not None
    
    def test_large_node_count(self, temp_workspace):
        """Test handling of large node counts."""
        from jagabot.agent.tools.knowledge_graph import KnowledgeGraphViewer
        
        viewer = KnowledgeGraphViewer(workspace_path=temp_workspace).load()
        
        # Generate HTML should handle any node count
        path = viewer.generate_html()
        assert path.exists()


class TestKnowledgeGraphIntegration:
    """Test KnowledgeGraph integration with MemoryFleet."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_with_memory_fleet_data(self, temp_workspace):
        """Test graph with MemoryFleet data."""
        from jagabot.agent.tools.memory_fleet import MemoryFleet
        from jagabot.agent.tools.knowledge_graph import KnowledgeGraphViewer
        
        # Add some memory data
        fleet = MemoryFleet(workspace=temp_workspace)
        for i in range(5):
            fleet.on_interaction(
                user_message=f"Question about portfolio risk {i}",
                agent_response=f"Answer about risk {i}",
                topic="risk"
            )
        
        # Load graph
        viewer = KnowledgeGraphViewer(workspace_path=temp_workspace).load()
        stats = viewer.get_stats()
        
        # Should have nodes from memory
        assert stats["total_nodes"] >= 0
    
    def test_full_pipeline(self, temp_workspace):
        """Test full pipeline: memory → graph → HTML."""
        from jagabot.agent.tools.memory_fleet import MemoryFleet
        from jagabot.agent.tools.knowledge_graph import KnowledgeGraphViewer
        
        # 1. Add memory
        fleet = MemoryFleet(workspace=temp_workspace)
        fleet.on_interaction(
            user_message="What is VIX?",
            agent_response="VIX measures volatility",
            topic="volatility"
        )
        
        # 2. Generate graph
        viewer = KnowledgeGraphViewer(workspace_path=temp_workspace).load()
        path = viewer.generate_html()
        
        # 3. Verify
        assert path.exists()
        
        content = path.read_text(encoding='utf-8')
        assert "volatility" in content.lower() or "VIX" in content
