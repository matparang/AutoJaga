#!/usr/bin/env python3
"""
Jagabot Direct Client - Simple direct access to Jagabot AgentLoop

Usage:
    from jagabot_direct import JagabotClient
    
    client = JagabotClient()
    response = await client.ask("What tools do you have?")
    print(response)
"""

import asyncio
from pathlib import Path
from typing import Optional

from jagabot.agent.loop import AgentLoop
from jagabot.providers.litellm_provider import LiteLLMProvider
from jagabot.bus.queue import MessageBus
from jagabot.config.schema import ExecToolConfig


class JagabotClient:
    """Simple client for direct Jagabot agent access."""
    
    def __init__(
        self,
        workspace: str | None = None,
        model: str | None = None,
        max_iterations: int = 20,
    ):
        """
        Initialize Jagabot client.
        
        Args:
            workspace: Workspace directory (default: ~/.jagabot/workspace)
            model: Model name (default: from config.json)
            max_iterations: Max agent iterations per request
        """
        self.workspace = Path(workspace) if workspace else Path.home() / ".jagabot" / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        
        # Load config if exists
        config_path = Path.home() / ".jagabot" / "config.json"
        if config_path.exists():
            import json
            with open(config_path) as f:
                config = json.load(f)
            if model is None:
                model = config.get("agents", {}).get("defaults", {}).get("model", "dashscope/qwen-plus")
        else:
            model = model or "dashscope/qwen-plus"
        
        # Create minimal message bus
        self.bus = MessageBus()
        
        # Create provider
        self.provider = LiteLLMProvider(
            api_key=config.get("providers", {}).get("dashscope", {}).get("apiKey", "") if config_path.exists() else "",
            api_base=config.get("providers", {}).get("dashscope", {}).get("apiBase") if config_path.exists() else None,
            default_model=model,
            provider_name="dashscope"
        )
        
        # Create agent loop
        self.agent = AgentLoop(
            bus=self.bus,
            provider=self.provider,
            workspace=self.workspace,
            model=model,
            max_iterations=max_iterations,
        )
        
        print(f"✅ JagabotClient initialized (model: {model})")
    
    async def ask(self, prompt: str, session_key: str = "cli") -> str:
        """
        Ask Jagabot a question and get response.
        
        Args:
            prompt: User's question/prompt
            session_key: Session identifier for conversation history
        
        Returns:
            Agent's response text
        """
        response = await self.agent.process_direct(
            content=prompt,
            session_key=session_key,
            channel="cli",
            chat_id="direct",
        )
        return response
    
    async def close(self):
        """Cleanup resources."""
        if hasattr(self, 'agent') and self.agent:
            self.agent.stop()


# ============================================================================
# Convenience function for one-off usage
# ============================================================================

async def ask_jagabot(prompt: str, workspace: str | None = None) -> str:
    """
    Ask Jagabot a question (convenience function).
    
    Usage:
        response = await ask_jagabot("What tools do you have?")
        print(response)
    """
    client = JagabotClient(workspace=workspace)
    try:
        return await client.ask(prompt)
    finally:
        await client.close()


# ============================================================================
# CLI usage
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 -m jagabot_direct <prompt>")
        print("Example: python3 -m jagabot_direct \"What tools do you have?\"")
        sys.exit(1)
    
    prompt = " ".join(sys.argv[1:])
    print(f"🤔 Asking: {prompt}\n")
    
    result = asyncio.run(ask_jagabot(prompt))
    print(f"\n✅ Response:\n{result}")
