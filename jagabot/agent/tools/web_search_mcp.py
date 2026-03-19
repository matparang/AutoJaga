"""
Web Search Tool — lightweight DuckDuckGo bridge.
No API key, no browser, no Playwright needed.
Fast (~1-2 seconds per query).
"""
import json
import subprocess
from pathlib import Path
from typing import Any
from jagabot.agent.tools.base import Tool

BRIDGE = Path(__file__).parent / "web_search_bridge.py"


class WebSearchMcpTool(Tool):
    """Real-time web search via DuckDuckGo — no API key needed."""

    name = "web_search_mcp"
    description = (
        "Search the web in real-time for current news and information.\n"
        "No API key required. Fast DuckDuckGo search.\n\n"
        "Actions:\n"
        "- search: Search for any topic, news, or information\n"
        "- fetch: Get content from a specific URL\n\n"
        "Use for: current news, recent events, research, fact-checking.\n"
        "Example: web_search_mcp(action='search', query='TSLA news today', limit=5)"
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search", "fetch"],
                "description": "search=web search, fetch=get specific URL content",
            },
            "query": {
                "type": "string",
                "description": "Search query or URL (for fetch)",
            },
            "limit": {
                "type": "integer",
                "description": "Number of results (1-10, default 5)",
                "default": 5,
            },
        },
        "required": ["action", "query"],
    }

    async def execute(
        self,
        action: str,
        query: str,
        limit: int = 5,
        **kwargs: Any,
    ) -> str:
        if not BRIDGE.exists():
            return json.dumps({"error": f"Search bridge not found at {BRIDGE}"})
        try:
            result = subprocess.run(
                ["python3", str(BRIDGE), action, query, str(limit)],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode != 0:
                return json.dumps({"error": result.stderr[:200]})
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            return json.dumps({"error": "Web search timed out"})
        except Exception as e:
            return json.dumps({"error": str(e)})
