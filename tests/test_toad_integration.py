"""
Test AutoJaga + TOAD integration
"""

import pytest
from pathlib import Path
import sys

# Add nanojaga to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_acp_adapter_imports():
    """Test ACP adapter imports correctly"""
    try:
        from jagabot.toad.acp_adapter import AutoJagaACP
        print("✅ ACP adapter imported successfully")
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        pytest.fail(f"ACP adapter import failed: {e}")


def test_acp_adapter_initialization():
    """Test ACP adapter initializes"""
    from jagabot.toad.acp_adapter import AutoJagaACP
    from tempfile import TemporaryDirectory
    
    with TemporaryDirectory() as tmpdir:
        adapter = AutoJagaACP(workspace=Path(tmpdir))
        assert adapter is not None
        assert adapter.workspace.exists()
        assert adapter.name == "AutoJaga"
        assert adapter.version == "5.0.0"


def test_tools_loaded():
    """Test AutoJaga tools are loaded"""
    from jagabot.toad.acp_adapter import AutoJagaACP
    from tempfile import TemporaryDirectory
    
    with TemporaryDirectory() as tmpdir:
        adapter = AutoJagaACP(workspace=Path(tmpdir))
        tools = adapter._load_tools()
        
        # Should have at least minimal tools
        assert len(tools) >= 3, f"Expected at least 3 tools, got {len(tools)}"
        
        # Check for basic tools
        tool_names = [t["function"]["name"] for t in tools]
        assert any(name in tool_names for name in ["web_search", "read_file", "write_file"])


@pytest.mark.asyncio
async def test_agent_run_basic():
    """Test agent runs with ACP protocol"""
    from jagabot.toad.acp_adapter import AutoJagaACP
    from tempfile import TemporaryDirectory
    
    with TemporaryDirectory() as tmpdir:
        adapter = AutoJagaACP(workspace=Path(tmpdir))
        results = []
        
        async for message in adapter.run("What is VIX?"):
            results.append(message)
            assert "type" in message
        
        # Should have status and complete messages
        types = [m["type"] for m in results]
        assert "status" in types or "content" in types
        assert "complete" in types


def test_cli_launcher_exists():
    """Test CLI launcher file exists"""
    cli_path = Path(__file__).parent.parent / "jagabot" / "cli" / "toad.py"
    assert cli_path.exists(), f"CLI launcher not found at {cli_path}"


def test_config_exists():
    """Test TOAD configuration file exists"""
    config_path = Path(__file__).parent.parent / "jagabot" / "toad" / "toad_config.yaml"
    assert config_path.exists(), f"Config not found at {config_path}"


def test_config_valid():
    """Test TOAD configuration is valid YAML"""
    import yaml
    config_path = Path(__file__).parent.parent / "jagabot" / "toad" / "toad_config.yaml"
    
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    assert "agent" in config
    assert "workspace" in config
    assert config["agent"]["name"] == "AutoJaga"


if __name__ == "__main__":
    # Run basic tests
    print("Running TOAD integration tests...")
    
    test_acp_adapter_imports()
    test_acp_adapter_initialization()
    test_tools_loaded()
    test_cli_launcher_exists()
    test_config_exists()
    test_config_valid()
    
    print("\n✅ All TOAD integration tests passed!")
