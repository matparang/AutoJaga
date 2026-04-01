"""Main chat loop for JagaChatbot."""

import asyncio
from pathlib import Path
from typing import Any
from datetime import datetime

from jagachatbot.agent.context import ContextBuilder
from jagachatbot.agent.memory import MemoryStore
from jagachatbot.agent.compressor import micro_compact, estimate_tokens
from jagachatbot.providers.base import LLMProvider, LLMResponse


class ChatLoop:
    """
    The chat loop is the core processing engine for JagaChatbot.
    
    It:
    1. Receives user messages
    2. Builds context with history and memory
    3. Calls the LLM
    4. Returns responses
    """
    
    def __init__(
        self,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        temperature: float = 0.7,
        memory_window: int = 50,
    ):
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.temperature = temperature
        self.memory_window = memory_window
        
        self.context = ContextBuilder(workspace)
        self.memory = MemoryStore(workspace)
        
        # Conversation history per session
        self._history: list[dict[str, Any]] = []
    
    async def chat(self, message: str) -> str:
        """
        Process a single user message and return the response.
        
        Args:
            message: The user's message.
        
        Returns:
            The assistant's response text.
        """
        # Build messages
        messages = self.context.build_messages(
            history=self._history[-self.memory_window:],
            current_message=message,
        )
        
        # Call LLM
        response: LLMResponse = await self.provider.chat(
            messages=messages,
            model=self.model,
            temperature=self.temperature,
        )
        
        # Get response content
        content = response.content or ""
        
        # Update history
        self._history.append({"role": "user", "content": message})
        self._history.append({"role": "assistant", "content": content})
        
        # Compress history if needed
        if estimate_tokens(self._history) > 30000:
            self._history = micro_compact(self._history)
        
        # Log to history file
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.memory.append_history(
            f"[{timestamp}] User: {message[:100]}...\n"
            f"[{timestamp}] Assistant: {content[:200]}..."
        )
        
        return content
    
    def clear_history(self) -> None:
        """Clear the conversation history."""
        self._history = []
    
    def get_history(self) -> list[dict[str, Any]]:
        """Get the current conversation history."""
        return self._history.copy()
