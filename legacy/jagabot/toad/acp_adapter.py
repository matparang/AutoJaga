"""
ACP Adapter - Exposes AutoJaga as TOAD-compatible agent

Agent Client Protocol (ACP) adapter that allows TOAD TUI to communicate
with AutoJaga's agent loop and tools.
"""

import asyncio
import json
from pathlib import Path
from typing import AsyncIterator, Dict, Any, List, Optional

from loguru import logger


class AutoJagaACP:
    """
    AutoJaga agent compatible with TOAD's Agent Client Protocol.
    
    This adapter exposes AutoJaga's 45+ tools and multi-agent capabilities
    through the ACP interface that TOAD understands.
    """
    
    def __init__(self, workspace: Optional[Path] = None):
        """
        Initialize AutoJaga ACP adapter.
        
        Args:
            workspace: AutoJaga workspace directory (default: ~/.jagabot/workspace)
        """
        self.workspace = workspace or Path.home() / ".jagabot" / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        
        self._tools: Optional[List[Dict]] = None
        self._agent_loop = None
        
        logger.info(f"AutoJagaACP initialized with workspace: {self.workspace}")
    
    @property
    def name(self) -> str:
        """Agent name for TOAD display"""
        return "AutoJaga"
    
    @property
    def version(self) -> str:
        """Agent version"""
        return "5.0.0"
    
    @property
    def description(self) -> str:
        """Agent description for TOAD"""
        return "Financial research AI assistant with 45+ tools and multi-agent swarms"
    
    def _load_tools(self) -> List[Dict[str, Any]]:
        """
        Load AutoJaga tools as ACP-compatible tool definitions.
        
        Returns:
            List of tool definitions in ACP format
        """
        if self._tools is not None:
            return self._tools
        
        try:
            from jagabot.agent.tools.registry import ToolRegistry
            from jagabot.agent.tool_loader import register_default_tools
            from jagabot.config.schema import ExecToolConfig
            from jagabot.bus.queue import MessageBus
            from jagabot.agent.subagent import SubagentManager
            from jagabot.providers.litellm import LiteLLMProvider
            from jagabot.cron.service import CronService
            
            registry = ToolRegistry()
            
            # Create minimal dependencies for tool loading
            bus = MessageBus()
            provider = LiteLLMProvider()
            subagents = SubagentManager(
                provider=provider,
                workspace=self.workspace,
                bus=bus,
            )
            cron_service = CronService(bus)
            
            # Register all default tools
            register_default_tools(
                registry,
                workspace=self.workspace,
                restrict_to_workspace=False,
                exec_config=ExecToolConfig(),
                brave_api_key=None,
                bus=bus,
                subagents=subagents,
                cron_service=cron_service,
                provider=provider,
            )
            
            # Convert to ACP format
            self._tools = registry.get_definitions()
            logger.info(f"Loaded {len(self._tools)} AutoJaga tools")
            
            return self._tools
            
        except Exception as e:
            logger.error(f"Failed to load AutoJaga tools: {e}")
            # Return minimal tool set for basic functionality
            return self._get_minimal_tools()
    
    def _get_minimal_tools(self) -> List[Dict[str, Any]]:
        """Get minimal set of tools when full loading fails"""
        # Return basic tool definitions for core functionality
        return [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web for information",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"}
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read contents of a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path"}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write content to a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path"},
                            "content": {"type": "string", "description": "File content"}
                        },
                        "required": ["path", "content"]
                    }
                }
            }
        ]
    
    @property
    def tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools"""
        return self._load_tools()
    
    async def run(
        self,
        prompt: str,
        attachments: Optional[List[Path]] = None,
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Run AutoJaga agent with ACP protocol.
        
        Args:
            prompt: User prompt from TOAD
            attachments: Optional file attachments
            **kwargs: Additional ACP parameters
        
        Yields:
            ACP protocol messages (status, content, complete)
        """
        logger.info(f"AutoJagaACP received prompt: {prompt[:100]}...")
        
        try:
            # Yield thinking status
            yield {
                "type": "status",
                "message": "AutoJaga is thinking...",
                "state": "running"
            }
            
            # Process attachments if any
            attachment_paths = [str(p) for p in attachments] if attachments else []
            
            # Build context with attachments
            context = self._build_context(prompt, attachment_paths)
            
            # Execute with AutoJaga agent
            async for message in self._execute_agent(context):
                yield message
            
            # Yield completion
            yield {
                "type": "complete",
                "success": True
            }
            
        except Exception as e:
            logger.error(f"AutoJagaACP execution failed: {e}")
            yield {
                "type": "error",
                "message": str(e)
            }
            yield {
                "type": "complete",
                "success": False
            }
    
    def _build_context(self, prompt: str, attachments: List[str]) -> Dict[str, Any]:
        """
        Build execution context from prompt and attachments.
        
        Args:
            prompt: User prompt
            attachments: List of attachment file paths
        
        Returns:
            Context dict for agent execution
        """
        context = {
            "prompt": prompt,
            "attachments": attachments,
            "workspace": str(self.workspace),
            "timestamp": asyncio.get_event_loop().time()
        }
        
        # Read attachment contents if any
        if attachments:
            attachment_contents = []
            for path in attachments:
                try:
                    p = Path(path)
                    if p.exists():
                        content = p.read_text()
                        attachment_contents.append({
                            "path": str(p),
                            "content": content[:10000]  # Limit size
                        })
                except Exception as e:
                    logger.warning(f"Failed to read attachment {path}: {e}")
            
            context["attachment_contents"] = attachment_contents
        
        return context
    
    async def _execute_agent(self, context: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        """
        Execute AutoJaga agent and stream results.
        
        Args:
            context: Execution context
        
        Yields:
            ACP content messages
        """
        try:
            # Try to use full agent loop if available
            result = await self._run_agent_loop(context)
            
            # Yield result as markdown content
            yield {
                "type": "content",
                "format": "markdown",
                "content": result
            }
            
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            yield {
                "type": "content",
                "format": "markdown",
                "content": f"❌ **Error**: {str(e)}"
            }
    
    async def _run_agent_loop(self, context: Dict[str, Any]) -> str:
        """
        Run AutoJaga agent loop with context.
        
        Args:
            context: Execution context
        
        Returns:
            Agent response string
        """
        try:
            from jagabot.agent.loop import AgentLoop
            from jagabot.bus.queue import MessageBus
            from jagabot.providers.litellm import LiteLLMProvider
            
            # Create minimal agent setup
            bus = MessageBus()
            provider = LiteLLMProvider()
            
            agent = AgentLoop(
                bus=bus,
                provider=provider,
                workspace=self.workspace,
            )
            
            # For now, use simplified execution
            # Full integration would wire up the complete agent loop
            prompt = context["prompt"]
            
            # Execute tools based on prompt analysis
            result = await self._execute_tools_for_prompt(prompt, context)
            
            return result
            
        except ImportError as e:
            logger.warning(f"Full agent loop not available: {e}")
            # Fallback to simple tool execution
            return await self._execute_tools_for_prompt(
                context["prompt"],
                context
            )
    
    async def _execute_tools_for_prompt(
        self,
        prompt: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Execute appropriate tools for the prompt.
        
        This is a simplified execution path that analyzes the prompt
        and calls relevant AutoJaga tools.
        
        Args:
            prompt: User prompt
            context: Execution context
        
        Returns:
            Tool execution results as markdown
        """
        from jagabot.agent.tools.registry import ToolRegistry
        
        registry = ToolRegistry()
        self._load_tools()
        
        # Analyze prompt to determine which tools to use
        prompt_lower = prompt.lower()
        
        results = []
        
        # Financial analysis
        if any(word in prompt_lower for word in ["risk", "portfolio", "var", "cvar"]):
            result = await self._run_financial_analysis(prompt, registry)
            results.append(result)
        
        # Research
        if any(word in prompt_lower for word in ["research", "analyze", "study"]):
            result = await self._run_research(prompt, registry)
            results.append(result)
        
        # General tool execution
        if not results:
            result = await self._run_general_query(prompt, registry)
            results.append(result)
        
        return "\n\n".join(results)
    
    async def _run_financial_analysis(
        self,
        prompt: str,
        registry: "ToolRegistry"
    ) -> str:
        """Run financial analysis tools"""
        lines = ["## 📊 Financial Analysis\n"]
        
        # Try to get portfolio analyzer
        if registry.has("portfolio_analyzer"):
            try:
                tool = registry.get("portfolio_analyzer")
                result = await tool.execute(
                    query=prompt,
                    current_price=100.0,
                    target_price=120.0
                )
                lines.append(f"**Portfolio Analysis:**\n{result}")
            except Exception as e:
                lines.append(f"*Portfolio analysis unavailable: {e}*")
        
        # Try Monte Carlo
        if registry.has("monte_carlo"):
            try:
                tool = registry.get("monte_carlo")
                result = await tool.execute(
                    current_price=100.0,
                    target_price=120.0,
                    vix=25.0,
                    days=30
                )
                lines.append(f"\n**Monte Carlo Simulation:**\n{result}")
            except Exception as e:
                lines.append(f"*Monte Carlo unavailable: {e}*")
        
        return "\n".join(lines)
    
    async def _run_research(
        self,
        prompt: str,
        registry: "ToolRegistry"
    ) -> str:
        """Run research tools"""
        lines = ["## 🔍 Research Results\n"]
        
        # Try web search
        if registry.has("web_search"):
            try:
                tool = registry.get("web_search")
                result = await tool.execute(query=prompt)
                lines.append(f"**Web Search:**\n{result}")
            except Exception as e:
                lines.append(f"*Web search unavailable: {e}*")
        
        # Try researcher
        if registry.has("researcher"):
            try:
                tool = registry.get("researcher")
                result = await tool.execute(query=prompt)
                lines.append(f"\n**Research:**\n{result}")
            except Exception as e:
                lines.append(f"*Researcher unavailable: {e}*")
        
        return "\n".join(lines)
    
    async def _run_general_query(
        self,
        prompt: str,
        registry: "ToolRegistry"
    ) -> str:
        """Run general query with available tools"""
        lines = ["## 🤖 AutoJaga Response\n"]
        
        # Try to use LLM provider directly
        try:
            from jagabot.providers.litellm import LiteLLMProvider
            provider = LiteLLMProvider()
            
            response = await provider.chat(
                messages=[
                    {"role": "system", "content": "You are AutoJaga, a helpful financial AI assistant."},
                    {"role": "user", "content": prompt}
                ],
                tools=[]
            )
            
            lines.append(response.content or "No response generated")
            
        except Exception as e:
            lines.append(f"*Query processing unavailable: {e}*")
            lines.append(f"\nYour query: {prompt}")
        
        return "\n".join(lines)


# ACP Protocol Entry Point
async def acp_run(
    prompt: str,
    attachments: List[Path] = None,
    **kwargs
) -> AsyncIterator[Dict[str, Any]]:
    """
    ACP protocol entry point for TOAD.
    
    This function is called by TOAD when the AutoJaga agent is selected.
    """
    adapter = AutoJagaACP()
    async for message in adapter.run(prompt, attachments, **kwargs):
        yield message
