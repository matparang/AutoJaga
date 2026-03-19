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
                model = config.get("agents", {}).get("defaults", {}).get("model", "deepseek/deepseek-chat")
        else:
            model = model or "deepseek/deepseek-chat"
        
        # Create minimal message bus
        self.bus = MessageBus()
        
        # Create provider
        self.provider = LiteLLMProvider(
            api_key=config.get("providers", {}).get("deepseek", {}).get("apiKey", "") if config_path.exists() else "",
            api_base=config.get("providers", {}).get("deepseek", {}).get("apiBase") if config_path.exists() else None,
            default_model=model,
            provider_name="deepseek"
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
        print("\nChallenge mode: python3 -m jagabot_direct \"challenge financial\"")
        print("Domains: financial, research, calibration, engineering")
        sys.exit(1)

    prompt = " ".join(sys.argv[1:])
    
    # Challenge mode
    if prompt.lower().startswith("challenge"):
        domain = None
        if "financial" in prompt.lower():
            domain = "financial"
        elif "research" in prompt.lower():
            domain = "research"
        elif "calibration" in prompt.lower():
            domain = "calibration"
        elif "engineering" in prompt.lower():
            domain = "engineering"
        
        client = JagabotClient()
        challenge = client.agent.challenge_gen.next(domain=domain)
        formatted = client.agent.challenge_gen.format_for_agent(challenge)
        print(formatted)
        answer = input("\nYour answer: ").strip()
        confidence = float(input("Confidence: ").strip() or "0.7")
        result = client.agent.challenge_gen.record_outcome(
            challenge.id, answer, confidence
        )
        if result:
            print(f"\n{'✅ CORRECT' if result.was_correct else '❌ WRONG'}")
            print(f"Brier score: {result.brier_score:.3f}")
            print(f"Stats: {client.agent.challenge_gen.get_stats()}")
        exit(0)
    
    print(f"🤔 Asking: {prompt}\n")

    result = asyncio.run(ask_jagabot(prompt))
    print(f"\n✅ Response:\n{result}")
