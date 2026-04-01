"""
AgentLoop — Main processing loop for AutoJaga agents.

Orchestrates:
- Tool registration and execution
- BDI scoring
- Anti-fabrication checking
- History management
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any
from datetime import datetime

from autojaga.agent.tools import ToolRegistry, ToolCallRequest
from autojaga.agent.builtin_tools import WebSearchTool, ReadFileTool, WriteFileTool, ExecTool
from autojaga.core.bdi_scorecard import score_turn, BDIScorecardTracker
from autojaga.core.tool_harness import ToolHarness
from autojaga.core.fluid_dispatcher import dispatch


class AgentLoop:
    """
    The main agent processing loop.
    
    Features:
    - Tool binding and execution
    - BDI scoring per turn
    - Anti-fabrication harness
    - Conversation history management
    """
    
    def __init__(
        self,
        provider: "LLMProvider",
        workspace: Path,
        model: str | None = None,
        temperature: float = 0.7,
        max_tool_iterations: int = 10,
    ):
        self.provider = provider
        self.workspace = Path(workspace)
        self.model = model or provider.get_default_model()
        self.temperature = temperature
        self.max_tool_iterations = max_tool_iterations
        
        # Tool system
        self.tools = ToolRegistry()
        self._register_default_tools()
        
        # Harness and scoring
        self.harness = ToolHarness(workspace)
        self.bdi_tracker = BDIScorecardTracker(workspace)
        
        # History
        self._history: list[dict[str, Any]] = []
        
        # Turn tracking
        self._tools_used: list[str] = []
        self._tool_errors: int = 0
    
    def _register_default_tools(self) -> None:
        """Register built-in tools."""
        allowed_dir = self.workspace
        
        self.tools.register(WebSearchTool())
        self.tools.register(ReadFileTool(allowed_dir=allowed_dir))
        self.tools.register(WriteFileTool(allowed_dir=allowed_dir))
        self.tools.register(ExecTool(
            working_dir=str(self.workspace),
            timeout=60,
        ))
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt."""
        from datetime import datetime
        import time as _time
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        tz = _time.strftime("%Z") or "UTC"
        
        return f"""# AutoJaga 🐈

You are AutoJaga, an autonomous AI agent that can use tools to accomplish tasks.

## Current Time
{now} ({tz})

## Workspace
Your workspace is at: {self.workspace}

## Available Tools
You have access to these tools:
{', '.join(self.tools.get_names())}

## Rules
1. Use tools to gather information and take actions
2. Verify your work - don't claim success without checking
3. Be honest about what you can and cannot do
4. When using tools, explain what you're doing and why

When you're done with a task, provide a clear summary of what you accomplished."""
    
    async def chat(self, message: str) -> str:
        """
        Process a user message with tool execution.
        
        Args:
            message: The user's message.
        
        Returns:
            The agent's response.
        """
        # Reset turn tracking
        self._tools_used = []
        self._tool_errors = 0
        self.harness.reset()
        
        # Dispatch to get recommended tools
        package = dispatch(message)
        
        # Build initial messages
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._build_system_prompt()},
        ]
        messages.extend(self._history[-20:])  # Last 20 messages
        messages.append({"role": "user", "content": message})
        
        # Tool execution loop
        iteration = 0
        final_content = ""
        
        while iteration < self.max_tool_iterations:
            iteration += 1
            
            # Call LLM
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model,
                temperature=self.temperature,
            )
            
            # Check for tool calls
            if response.tool_calls:
                # Build assistant message with tool calls
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in response.tool_calls
                ]
                messages.append({
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": tool_call_dicts,
                })
                
                # Execute each tool
                for tool_call in response.tool_calls:
                    self._tools_used.append(tool_call.name)
                    
                    # Track in harness
                    self.harness.start(tool_call.id, tool_call.name)
                    
                    try:
                        result = await self.tools.execute(
                            tool_call.name,
                            tool_call.arguments,
                        )
                        
                        # Track completion
                        result_file = None
                        if tool_call.name == "write_file":
                            result_file = tool_call.arguments.get("path", "")
                        self.harness.complete(tool_call.id, result, result_file)
                        
                    except Exception as e:
                        result = f"Error: {str(e)}"
                        self.harness.fail(tool_call.id, str(e))
                        self._tool_errors += 1
                    
                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.name,
                        "content": result,
                    })
            else:
                # No more tool calls - we're done
                final_content = response.content or ""
                break
        
        # Check for fabrication
        fab_warnings = self.harness.check_fabrication(final_content)
        if fab_warnings:
            final_content += "\n\n---\n" + "\n".join(fab_warnings)
        
        # Score the turn
        quality = 0.7 if not fab_warnings else 0.4
        bdi_score = score_turn(
            tools_used=self._tools_used,
            quality=quality,
            anomaly_count=len(fab_warnings),
            tool_errors=self._tool_errors,
        )
        self.bdi_tracker.record(bdi_score)
        
        # Update history
        self._history.append({"role": "user", "content": message})
        self._history.append({"role": "assistant", "content": final_content})
        
        return final_content
    
    def get_bdi_summary(self) -> dict[str, Any]:
        """Get BDI scoring summary."""
        return {
            "average": self.bdi_tracker.get_average(),
            "trend": self.bdi_tracker.get_trend(),
        }
    
    def get_tool_summary(self) -> dict[str, Any]:
        """Get tool execution summary."""
        return self.harness.get_execution_summary()
    
    def clear_history(self) -> None:
        """Clear conversation history."""
        self._history = []


# Import provider at runtime to avoid circular imports
from autojaga.providers.base import LLMProvider
