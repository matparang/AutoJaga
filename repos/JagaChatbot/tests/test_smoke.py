"""Smoke test for JagaChatbot.

Verifies:
1. Package imports correctly
2. ChatLoop initializes
3. Memory store works
4. Context builder works
"""

import pytest
from pathlib import Path
import tempfile


def test_package_imports():
    """Test that main package imports without errors."""
    from jagachatbot import ChatLoop, __version__
    assert __version__ == "1.0.0"
    assert ChatLoop is not None


def test_memory_store():
    """Test memory store read/write operations."""
    from jagachatbot.agent.memory import MemoryStore
    
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        store = MemoryStore(workspace)
        
        # Test long-term memory
        assert store.read_long_term() == ""
        store.write_long_term("Test fact: Python is great")
        assert "Python is great" in store.read_long_term()
        
        # Test history
        store.append_history("User said hello")
        assert store.history_file.exists()
        assert "hello" in store.history_file.read_text()


def test_context_builder():
    """Test context builder creates valid prompts."""
    from jagachatbot.agent.context import ContextBuilder
    
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        builder = ContextBuilder(workspace)
        
        # Test system prompt
        prompt = builder.build_system_prompt()
        assert "JagaChatbot" in prompt
        assert workspace.name in prompt
        
        # Test message building
        messages = builder.build_messages(
            history=[],
            current_message="Hello!",
        )
        assert len(messages) == 2  # system + user
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hello!"


def test_compressor():
    """Test token estimation and compression."""
    from jagachatbot.agent.compressor import estimate_tokens, micro_compact
    
    # Test token estimation
    messages = [
        {"role": "user", "content": "Hello there!"},
        {"role": "assistant", "content": "Hi! How can I help?"},
    ]
    tokens = estimate_tokens(messages)
    assert tokens > 0
    assert tokens < 1000  # Should be small for short messages
    
    # Test compression (no tool results to compress)
    result = micro_compact(messages)
    assert result == messages  # No changes expected


def test_config_loading():
    """Test config loads with defaults."""
    from jagachatbot.config import load_config, Config
    
    config = load_config()
    assert isinstance(config, Config)
    assert config.defaults.model == "openai/gpt-4o-mini"


def test_provider_interface():
    """Test provider base class is properly defined."""
    from jagachatbot.providers.base import LLMProvider, LLMResponse
    
    # LLMResponse should be a dataclass
    response = LLMResponse(content="Test", finish_reason="stop")
    assert response.content == "Test"
    assert response.has_content is True
    
    # LLMProvider should be abstract
    import inspect
    assert inspect.isabstract(LLMProvider)


@pytest.mark.asyncio
async def test_chat_loop_init():
    """Test ChatLoop can be initialized (without making API calls)."""
    from jagachatbot.agent.loop import ChatLoop
    from jagachatbot.providers.base import LLMProvider, LLMResponse
    
    # Create a mock provider
    class MockProvider(LLMProvider):
        async def chat(self, messages, **kwargs):
            return LLMResponse(content="Mock response", finish_reason="stop")
        
        def get_default_model(self):
            return "mock/model"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        provider = MockProvider()
        
        loop = ChatLoop(
            provider=provider,
            workspace=workspace,
        )
        
        # Test chat
        response = await loop.chat("Hello")
        assert response == "Mock response"
        
        # Test history was updated
        history = loop.get_history()
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
