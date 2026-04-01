"""Smoke test for AutoJaga-Base.

Verifies:
1. Package imports correctly
2. AgentLoop initializes
3. Tool registry works
4. BDI scoring works
5. Swarm orchestration works
"""

import pytest
from pathlib import Path
import tempfile


def test_package_imports():
    """Test that main package imports without errors."""
    from autojaga import AgentLoop, __version__
    assert __version__ == "1.0.0"
    assert AgentLoop is not None


def test_tool_registry():
    """Test tool registration and lookup."""
    from autojaga.agent.tools import ToolRegistry, Tool
    
    class MockTool(Tool):
        @property
        def name(self):
            return "mock_tool"
        
        @property
        def description(self):
            return "A mock tool"
        
        @property
        def parameters(self):
            return {"type": "object", "properties": {}}
        
        async def execute(self, **kwargs):
            return "mock result"
    
    registry = ToolRegistry()
    tool = MockTool()
    
    registry.register(tool)
    assert "mock_tool" in registry
    assert registry.get("mock_tool") is tool
    
    definitions = registry.get_definitions()
    assert len(definitions) == 1
    assert definitions[0]["function"]["name"] == "mock_tool"


def test_bdi_scoring():
    """Test BDI scorecard."""
    from autojaga.core.bdi_scorecard import score_turn, BDIScore
    
    # Test a good turn
    score = score_turn(
        tools_used=["web_search", "read_file", "write_file"],
        quality=0.85,
        anomaly_count=0,
        tool_errors=0,
    )
    
    assert isinstance(score, BDIScore)
    assert score.total >= 6.0  # Should be "Emerging" or better
    assert "Autonomous" in score.label or "Emerging" in score.label
    
    # Test a bad turn
    bad_score = score_turn(
        tools_used=[],
        quality=0.3,
        anomaly_count=5,
        tool_errors=3,
    )
    
    assert bad_score.total < 4.0
    assert "Reactive" in bad_score.label


def test_tool_harness():
    """Test tool harness tracking."""
    from autojaga.core.tool_harness import ToolHarness
    
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        harness = ToolHarness(workspace)
        
        # Start and complete a tool
        harness.start("call_1", "web_search")
        harness.complete("call_1", "some results")
        
        summary = harness.get_execution_summary()
        assert summary["total"] == 1
        assert summary["completed"] == 1
        assert "web_search" in summary["tools_used"]


def test_fabrication_detection():
    """Test fabrication detection."""
    from autojaga.core.tool_harness import ToolHarness
    
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        harness = ToolHarness(workspace)
        
        # Claim file creation without using write_file
        response = "I created the file 'report.md' with the analysis."
        warnings = harness.check_fabrication(response)
        
        assert len(warnings) >= 1
        assert "fabrication" in warnings[0].lower() or "Fabrication" in warnings[0]


def test_fluid_dispatcher():
    """Test intent classification."""
    from autojaga.core.fluid_dispatcher import classify_intent, dispatch
    
    # Research intent
    assert classify_intent("research quantum computing") == "RESEARCH"
    assert classify_intent("what is machine learning") == "RESEARCH"
    
    # Action intent
    assert classify_intent("create a new file") == "ACTION"
    assert classify_intent("write the report") == "ACTION"
    
    # Analysis intent
    assert classify_intent("analyze this data") == "ANALYSIS"
    
    # Default to CHAT
    assert classify_intent("hello there") == "CHAT"
    
    # Dispatch returns tools
    package = dispatch("research the topic")
    assert package.profile == "RESEARCH"
    assert "web_search" in package.tools


def test_builtin_tools():
    """Test built-in tool creation."""
    from autojaga.agent.builtin_tools import WebSearchTool, ReadFileTool, WriteFileTool
    
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        
        ws_tool = WebSearchTool()
        assert ws_tool.name == "web_search"
        
        rf_tool = ReadFileTool(allowed_dir=workspace)
        assert rf_tool.name == "read_file"
        
        wf_tool = WriteFileTool(allowed_dir=workspace)
        assert wf_tool.name == "write_file"


def test_swarm_config():
    """Test swarm specialist configuration."""
    from autojaga.swarm import SpecialistConfig, Conductor
    from autojaga.providers.base import LLMProvider, LLMResponse
    
    class MockProvider(LLMProvider):
        async def chat(self, messages, **kwargs):
            return LLMResponse(content="Mock specialist response")
        
        def get_default_model(self):
            return "mock/model"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        provider = MockProvider()
        
        # Create custom specialist
        config = SpecialistConfig(
            name="TestSpecialist",
            role="Testing Expert",
            persona="Focused on testing software",
            tools=["web_search"],
        )
        
        # Create conductor with custom specialists
        conductor = Conductor(
            provider=provider,
            workspace=workspace,
            specialists=[config],
        )
        
        assert len(conductor.specialist_configs) == 1


@pytest.mark.asyncio
async def test_agent_loop_init():
    """Test AgentLoop can be initialized with mock provider."""
    from autojaga.agent.loop import AgentLoop
    from autojaga.providers.base import LLMProvider, LLMResponse
    
    class MockProvider(LLMProvider):
        async def chat(self, messages, tools=None, **kwargs):
            # Return a response without tool calls
            return LLMResponse(content="Mock response", tool_calls=[])
        
        def get_default_model(self):
            return "mock/model"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        provider = MockProvider()
        
        loop = AgentLoop(
            provider=provider,
            workspace=workspace,
        )
        
        # Check tools are registered
        assert "web_search" in loop.tools.get_names()
        assert "read_file" in loop.tools.get_names()
        
        # Test chat
        response = await loop.chat("Hello")
        assert response == "Mock response"


def test_config_loading():
    """Test config loads with defaults."""
    from autojaga.config import load_config, Config
    
    config = load_config()
    assert isinstance(config, Config)
    assert config.defaults.max_tool_iterations == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
