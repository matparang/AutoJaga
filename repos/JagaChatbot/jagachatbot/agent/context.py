"""Context builder for assembling agent prompts."""

import platform
from pathlib import Path
from typing import Any

from jagachatbot.agent.memory import MemoryStore


class ContextBuilder:
    """
    Builds the context (system prompt + messages) for the agent.
    
    Assembles memory and conversation history into a coherent prompt for the LLM.
    """
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory = MemoryStore(workspace)
    
    def build_system_prompt(self) -> str:
        """Build the system prompt from identity and memory."""
        parts = []
        
        # Core identity
        parts.append(self._get_identity())
        
        # Memory context
        memory = self.memory.get_memory_context()
        if memory:
            parts.append(f"# Memory\n\n{memory}")
        
        return "\n\n---\n\n".join(parts)
    
    def _get_identity(self) -> str:
        """Get the core identity section."""
        from datetime import datetime
        import time as _time
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        tz = _time.strftime("%Z") or "UTC"
        workspace_path = str(self.workspace.expanduser().resolve())
        system = platform.system()
        runtime = f"{'macOS' if system == 'Darwin' else system} {platform.machine()}, Python {platform.python_version()}"
        
        return f"""# JagaChatbot 🐈

You are JagaChatbot, a helpful AI assistant.

## Current Time
{now} ({tz})

## Runtime
{runtime}

## Workspace
Your workspace is at: {workspace_path}
- Long-term memory: {workspace_path}/memory/MEMORY.md
- History log: {workspace_path}/memory/HISTORY.md (grep-searchable)

Always be helpful, accurate, and concise. Think step by step when solving problems.
When remembering something important, write to {workspace_path}/memory/MEMORY.md"""
    
    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
    ) -> list[dict[str, Any]]:
        """
        Build the complete message list for an LLM call.

        Args:
            history: Previous conversation messages.
            current_message: The new user message.

        Returns:
            List of messages including system prompt.
        """
        messages = []

        # System prompt
        system_prompt = self.build_system_prompt()
        messages.append({"role": "system", "content": system_prompt})

        # History
        messages.extend(history)

        # Current message
        messages.append({"role": "user", "content": current_message})

        return messages
    
    def add_assistant_message(
        self,
        messages: list[dict[str, Any]],
        content: str | None,
    ) -> list[dict[str, Any]]:
        """Add an assistant message to the message list."""
        msg: dict[str, Any] = {"role": "assistant", "content": content or ""}
        messages.append(msg)
        return messages
