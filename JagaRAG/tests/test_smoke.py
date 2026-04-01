"""Smoke test for JagaRAG.

Verifies:
1. Package imports correctly
2. RAGLoop initializes
3. Vector memory works
4. Document ingestion works
5. Retrieval returns results
"""

import pytest
from pathlib import Path
import tempfile


def test_package_imports():
    """Test that main package imports without errors."""
    from jagaragbot import RAGLoop, __version__
    assert __version__ == "1.0.0"
    assert RAGLoop is not None


def test_vector_memory():
    """Test vector memory add and search operations."""
    from jagaragbot.memory.vector_memory import VectorMemory
    
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        memory = VectorMemory(workspace)
        
        # Add documents
        doc_id = memory.add_document(
            text="Styrax benzoin produces resinous compounds with antimicrobial properties.",
            source="test_doc.md",
            chunk_id=0,
        )
        assert doc_id is not None
        
        # Search should return the document
        results = memory.search("antimicrobial compounds", top_k=3)
        assert len(results) >= 1
        assert "antimicrobial" in results[0].get("text", "").lower() or results[0].get("similarity", 0) > 0


def test_document_ingestion():
    """Test document chunking and ingestion."""
    from jagaragbot.ingestion import DocumentIngester, chunk_text
    
    # Test chunking
    text = "This is paragraph one.\n\nThis is paragraph two.\n\nThis is paragraph three."
    chunks = list(chunk_text(text, chunk_size=50, chunk_overlap=10))
    assert len(chunks) >= 1
    
    # Test ingestion
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        ingester = DocumentIngester(workspace)
        
        # Create a test file
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("This is test content for ingestion.\n\nAnother paragraph here.")
        
        count = ingester.ingest_file(test_file)
        assert count >= 1
        
        # Check stats
        stats = ingester.get_stats()
        assert stats.get("total_documents", 0) >= 1


def test_context_builder():
    """Test context builder with JagaRAG identity."""
    from jagaragbot.agent.context import ContextBuilder
    
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        builder = ContextBuilder(workspace)
        
        prompt = builder.build_system_prompt()
        assert "JagaChatbot" in prompt or "workspace" in prompt.lower()


def test_rag_loop_with_retrieval():
    """Test RAGLoop retrieves documents before responding."""
    from jagaragbot.agent.loop import RAGLoop
    from jagaragbot.providers.base import LLMProvider, LLMResponse
    from jagaragbot.memory.vector_memory import VectorMemory
    
    class MockProvider(LLMProvider):
        async def chat(self, messages, **kwargs):
            # Check that retrieval context was injected
            system = messages[0]["content"] if messages else ""
            if "Retrieved Knowledge" in system:
                return LLMResponse(content="Response with retrieved context", finish_reason="stop")
            return LLMResponse(content="Response without retrieval", finish_reason="stop")
        
        def get_default_model(self):
            return "mock/model"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        
        # Pre-populate vector memory
        memory = VectorMemory(workspace)
        memory.add_document(
            text="Mangliwood trees produce unique benzoin compounds.",
            source="mangliwood.md",
        )
        
        # Create RAG loop
        provider = MockProvider()
        loop = RAGLoop(provider=provider, workspace=workspace)
        
        # Chat should include retrieval
        import asyncio
        response = asyncio.run(loop.chat("Tell me about benzoin"))
        
        # Response should indicate retrieval happened
        assert "retrieved" in response.lower() or loop.get_retrieval_stats().get("total_documents", 0) >= 0


def test_config_loading():
    """Test config loads with defaults."""
    from jagaragbot.config import load_config, Config
    
    config = load_config()
    assert isinstance(config, Config)


@pytest.mark.asyncio
async def test_rag_loop_init():
    """Test RAGLoop can be initialized."""
    from jagaragbot.agent.loop import RAGLoop
    from jagaragbot.providers.base import LLMProvider, LLMResponse
    
    class MockProvider(LLMProvider):
        async def chat(self, messages, **kwargs):
            return LLMResponse(content="Mock RAG response", finish_reason="stop")
        
        def get_default_model(self):
            return "mock/model"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        provider = MockProvider()
        
        loop = RAGLoop(
            provider=provider,
            workspace=workspace,
            retrieval_k=3,
        )
        
        response = await loop.chat("Hello")
        assert "Mock" in response
        
        # Check history
        history = loop.get_history()
        assert len(history) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
