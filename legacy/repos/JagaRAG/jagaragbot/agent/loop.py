"""Main RAG chat loop for JagaRAG."""

import asyncio
from pathlib import Path
from typing import Any
from datetime import datetime

from jagaragbot.agent.context import ContextBuilder
from jagaragbot.agent.memory import MemoryStore
from jagaragbot.agent.compressor import micro_compact, estimate_tokens
from jagaragbot.providers.base import LLMProvider, LLMResponse
from jagaragbot.memory.vector_memory import VectorMemory


class RAGLoop:
    """
    The RAG loop is the core processing engine for JagaRAG.
    
    Extends basic chat with:
    - Vector memory retrieval
    - Context-grounded responses
    - Source citations
    """
    
    def __init__(
        self,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        temperature: float = 0.7,
        memory_window: int = 50,
        retrieval_k: int = 3,
    ):
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.temperature = temperature
        self.memory_window = memory_window
        self.retrieval_k = retrieval_k
        
        self.context = ContextBuilder(workspace)
        self.memory = MemoryStore(workspace)
        self.vector_memory = VectorMemory(workspace)
        
        # Conversation history per session
        self._history: list[dict[str, Any]] = []
    
    async def chat(self, message: str) -> str:
        """
        Process a user message with RAG retrieval.
        
        Args:
            message: The user's message.
        
        Returns:
            The assistant's response text with retrieved context.
        """
        # Step 1: Retrieve relevant documents
        retrieved = self.vector_memory.search(message, top_k=self.retrieval_k)
        
        # Step 2: Build context with retrieved documents
        retrieval_context = self._format_retrieved(retrieved)
        
        # Step 3: Build messages with retrieval context
        messages = self.context.build_messages(
            history=self._history[-self.memory_window:],
            current_message=message,
        )
        
        # Inject retrieval context into system prompt
        if retrieval_context:
            messages[0]["content"] += f"\n\n{retrieval_context}"
        
        # Step 4: Call LLM
        response: LLMResponse = await self.provider.chat(
            messages=messages,
            model=self.model,
            temperature=self.temperature,
        )
        
        # Get response content
        content = response.content or ""
        
        # Step 5: Update history
        self._history.append({"role": "user", "content": message})
        self._history.append({"role": "assistant", "content": content})
        
        # Compress history if needed
        if estimate_tokens(self._history) > 30000:
            self._history = micro_compact(self._history)
        
        # Log to history file
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        retrieved_sources = [r.get("source", "unknown") for r in retrieved]
        self.memory.append_history(
            f"[{timestamp}] User: {message[:100]}...\n"
            f"[{timestamp}] Sources: {', '.join(retrieved_sources)}\n"
            f"[{timestamp}] Assistant: {content[:200]}..."
        )
        
        return content
    
    def _format_retrieved(self, retrieved: list[dict[str, Any]]) -> str:
        """Format retrieved documents for context injection."""
        if not retrieved:
            return ""
        
        lines = [
            "## Retrieved Knowledge",
            "",
            "Use the following retrieved documents to ground your response.",
            "Cite sources when using this information.",
            "",
        ]
        
        for i, doc in enumerate(retrieved, 1):
            source = doc.get("source", "unknown")
            text = doc.get("text", "")[:500]
            similarity = doc.get("similarity", 0)
            
            lines.append(f"### [{i}] {source} (relevance: {similarity:.2f})")
            lines.append(text)
            lines.append("")
        
        lines.append("---")
        lines.append("")
        
        return "\n".join(lines)
    
    def clear_history(self) -> None:
        """Clear the conversation history."""
        self._history = []
    
    def get_history(self) -> list[dict[str, Any]]:
        """Get the current conversation history."""
        return self._history.copy()
    
    def get_retrieval_stats(self) -> dict[str, Any]:
        """Get vector memory statistics."""
        return self.vector_memory.get_stats()
