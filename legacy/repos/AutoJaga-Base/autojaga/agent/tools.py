"""Base tool interface for AutoJaga agents."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCallRequest:
    """A tool call request from the LLM."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    """Result from a tool execution."""
    success: bool
    content: str
    error: str | None = None


class Tool(ABC):
    """
    Abstract base class for tools.
    
    Tools are capabilities that agents can invoke to interact with the world.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what the tool does."""
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema for tool parameters."""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """
        Execute the tool with given arguments.
        
        Args:
            **kwargs: Tool-specific arguments.
        
        Returns:
            String result of the tool execution.
        """
        pass
    
    def get_definition(self) -> dict[str, Any]:
        """Get OpenAI-format tool definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }


class ToolRegistry:
    """
    Registry for available tools.
    
    Manages tool registration, lookup, and execution.
    """
    
    def __init__(self):
        self._tools: dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
    
    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def __contains__(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools
    
    def get_definitions(self) -> list[dict[str, Any]]:
        """Get all tool definitions for LLM."""
        return [tool.get_definition() for tool in self._tools.values()]
    
    def get_names(self) -> list[str]:
        """Get all registered tool names."""
        return list(self._tools.keys())
    
    async def execute(self, name: str, arguments: dict[str, Any]) -> str:
        """
        Execute a tool by name.
        
        Args:
            name: Tool name.
            arguments: Tool arguments.
        
        Returns:
            Tool result as string.
        """
        tool = self._tools.get(name)
        if tool is None:
            return f"Error: Unknown tool '{name}'"
        
        try:
            return await tool.execute(**arguments)
        except Exception as e:
            return f"Error executing {name}: {str(e)}"
