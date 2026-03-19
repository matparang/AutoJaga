"""
Web Search MCP Tool — wraps web-search-mcp server.
Provides real-time web search via Bing/Brave/DuckDuckGo.
No API key required.
"""
import json
import subprocess
from pathlib import Path
from typing import Any

from loguru import logger

from jagabot.agent.tools.base import Tool

MCP_SERVER = Path("/root/nanojaga/web-search-mcp/dist/index.js")


def _call_mcp(method: str, params: dict, timeout: int = 45) -> dict:
    """Send JSON-RPC call to MCP server via stdio."""
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }, ensure_ascii=False)
    
    try:
        result = subprocess.run(
            ["node", str(MCP_SERVER)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8',
        )
        
        # MCP server may output startup logs to stderr
        # Only check returncode for actual errors
        if result.returncode != 0 and result.stderr.strip():
            logger.debug(f"MCP stderr: {result.stderr[:200]}")
        
        # Parse stdout for JSON-RPC response
        if not result.stdout.strip():
            return {"error": "No response from MCP server"}
            
        return json.loads(result.stdout)
        
    except subprocess.TimeoutExpired:
        return {"error": "Web search timed out after 45s"}
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON response: {str(e)[:100]}"}
    except Exception as e:
        return {"error": str(e)}


class WebSearchMcpTool(Tool):
    """Real-time web search via Bing/Brave/DuckDuckGo — no API key needed."""

    name = "web_search_mcp"
    description = (
        "Search the web in real-time for current information.\n"
        "Uses Bing → Brave → DuckDuckGo fallback chain.\n"
        "No API key required.\n\n"
        "Actions:\n"
        "- search: Full web search with page content extraction (comprehensive)\n"
        "- summaries: Quick search snippets only (faster)\n"
        "- fetch: Get content from a specific URL\n\n"
        "Use for: current news, recent events, research, fact-checking.\n"
        "Chain: After search, use researcher or tri_agent for analysis."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search", "summaries", "fetch"],
                "description": "search=full content extraction, summaries=snippets only, fetch=single URL content",
            },
            "query": {
                "type": "string",
                "description": "Search query (for search/summaries) or URL (for fetch)",
            },
            "limit": {
                "type": "integer",
                "description": "Number of results to return (1-10, default 5)",
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
        """Execute web search via MCP server."""
        if not MCP_SERVER.exists():
            return json.dumps({"error": f"Web search MCP not found at {MCP_SERVER}"})

        # Map actions to MCP tool names
        tool_map = {
            "search":    "full-web-search",
            "summaries": "get-web-search-summaries",
            "fetch":     "get-single-web-page-content",
        }
        mcp_tool = tool_map.get(action, "get-web-search-summaries")

        # Build MCP tool call parameters
        if action == "fetch":
            # Fetch action requires URL instead of query
            mcp_params = {"url": query}
        else:
            # Search/summaries use query + limit
            mcp_params = {
                "query": query,
                "limit": min(max(limit, 1), 10),  # Clamp to 1-10
            }

        # Call MCP server
        response = _call_mcp("tools/call", {
            "name": mcp_tool,
            "arguments": mcp_params,
        }, timeout=60)

        # Handle errors
        if "error" in response:
            logger.warning(f"Web search error: {response['error']}")
            return json.dumps(response)

        # Extract text content from MCP response
        result = response.get("result", {})
        content_list = result.get("content", [])
        
        if content_list and isinstance(content_list, list):
            # Extract text from content array
            texts = [
                c.get("text", "") 
                for c in content_list 
                if c.get("type") == "text" and c.get("text")
            ]
            if texts:
                return "\n\n".join(texts)
        
        # Fallback: return raw result
        if result:
            return json.dumps(result, indent=2, ensure_ascii=False)
        
        return json.dumps({"error": "No content returned from web search"})
