"""Built-in tools for AutoJaga agents."""

import json
from pathlib import Path
from typing import Any

from autojaga.agent.tools import Tool


class WebSearchTool(Tool):
    """Web search tool using DuckDuckGo."""
    
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key
    
    @property
    def name(self) -> str:
        return "web_search"
    
    @property
    def description(self) -> str:
        return (
            "Search the web for current information. "
            "Use for research, news, fact-checking."
        )
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results (1-10)",
                    "default": 5,
                },
            },
            "required": ["query"],
        }
    
    async def execute(self, query: str, num_results: int = 5, **kwargs) -> str:
        """Execute web search."""
        try:
            from duckduckgo_search import DDGS
            
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=num_results))
            
            if not results:
                return json.dumps({"query": query, "results": [], "message": "No results found"})
            
            formatted = []
            for r in results:
                formatted.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")[:300],
                })
            
            return json.dumps({"query": query, "results": formatted})
        except ImportError:
            return json.dumps({"error": "duckduckgo-search not installed. pip install duckduckgo-search"})
        except Exception as e:
            return json.dumps({"error": str(e)})


class ReadFileTool(Tool):
    """Read file contents."""
    
    def __init__(self, allowed_dir: Path | None = None):
        self.allowed_dir = allowed_dir
    
    @property
    def name(self) -> str:
        return "read_file"
    
    @property
    def description(self) -> str:
        return "Read the contents of a file."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read",
                },
            },
            "required": ["path"],
        }
    
    async def execute(self, path: str, **kwargs) -> str:
        """Read file contents."""
        p = Path(path).expanduser()
        
        if self.allowed_dir and not str(p.resolve()).startswith(str(self.allowed_dir.resolve())):
            return f"Error: Access denied. File must be within {self.allowed_dir}"
        
        if not p.exists():
            return f"Error: File not found: {path}"
        
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            return content[:50000]  # Limit to 50k chars
        except Exception as e:
            return f"Error reading file: {e}"


class WriteFileTool(Tool):
    """Write content to a file."""
    
    def __init__(self, allowed_dir: Path | None = None):
        self.allowed_dir = allowed_dir
    
    @property
    def name(self) -> str:
        return "write_file"
    
    @property
    def description(self) -> str:
        return "Write content to a file. Creates parent directories if needed."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to write to",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write",
                },
            },
            "required": ["path", "content"],
        }
    
    async def execute(self, path: str, content: str, **kwargs) -> str:
        """Write to file."""
        p = Path(path).expanduser()
        
        if self.allowed_dir and not str(p.resolve()).startswith(str(self.allowed_dir.resolve())):
            return f"Error: Access denied. File must be within {self.allowed_dir}"
        
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"Successfully wrote {len(content)} characters to {path}"
        except Exception as e:
            return f"Error writing file: {e}"


class ExecTool(Tool):
    """Execute shell commands."""
    
    def __init__(self, working_dir: str = ".", timeout: int = 60):
        self.working_dir = working_dir
        self.timeout = timeout
    
    @property
    def name(self) -> str:
        return "exec"
    
    @property
    def description(self) -> str:
        return "Execute a shell command. Use for running scripts, installing packages, etc."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute",
                },
            },
            "required": ["command"],
        }
    
    async def execute(self, command: str, **kwargs) -> str:
        """Execute command."""
        import subprocess
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.working_dir,
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"
            
            return output[:10000] if output else "(no output)"
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {self.timeout}s"
        except Exception as e:
            return f"Error executing command: {e}"
