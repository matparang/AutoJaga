"""JSON-RPC 2.0 client for DeepSeek MCP Streamable HTTP transport."""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any

_MCP_ENDPOINT = "/mcp"


class MCPClientError(Exception):
    """Raised when the MCP server returns an error or is unreachable."""


class DeepSeekMCPClient:
    """Minimal JSON-RPC 2.0 client for the DeepSeek MCP Streamable HTTP server.

    Uses only stdlib (urllib) so no extra dependencies are required.
    The MCP Streamable HTTP transport accepts POST requests with JSON-RPC
    2.0 envelopes and returns JSON responses (non-streaming path).
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 3001, path: str = _MCP_ENDPOINT) -> None:
        self.base_url = f"http://{host}:{port}{path}"
        self._request_id = 0

    # ------------------------------------------------------------------
    # Low-level JSON-RPC
    # ------------------------------------------------------------------

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _call(self, method: str, params: dict | list | None = None, timeout: int = 30) -> Any:
        """Send a JSON-RPC 2.0 request and return the ``result`` field."""
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            self.base_url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.URLError as exc:
            raise MCPClientError(f"Cannot reach MCP server at {self.base_url}: {exc}") from exc

        if "error" in data:
            err = data["error"]
            raise MCPClientError(f"MCP error {err.get('code')}: {err.get('message')}")
        return data.get("result")

    # ------------------------------------------------------------------
    # MCP standard methods
    # ------------------------------------------------------------------

    def initialize(self) -> dict[str, Any]:
        """Perform MCP initialize handshake."""
        return self._call("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "jagabot", "version": "3.9.0"},
        })

    def list_tools(self) -> list[dict[str, Any]]:
        """Return all tools exposed by the MCP server."""
        result = self._call("tools/list")
        if result is None:
            return []
        return result.get("tools", result) if isinstance(result, dict) else result

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call a named MCP tool and return its content."""
        result = self._call("tools/call", {"name": name, "arguments": arguments or {}})
        return result or {}

    # ------------------------------------------------------------------
    # Convenience wrappers for DeepSeek-specific tools
    # ------------------------------------------------------------------

    def chat(
        self,
        message: str,
        conversation_id: str | None = None,
        model: str = "deepseek-chat",
        temperature: float | None = None,
    ) -> str:
        """Send a chat message and return the text reply."""
        args: dict[str, Any] = {"message": message, "model": model}
        if conversation_id:
            args["conversation_id"] = conversation_id
        if temperature is not None:
            args["temperature"] = temperature

        result = self.call_tool("chat_completion", args)
        # Response is a list of content blocks
        contents = result.get("content", [])
        if isinstance(contents, list):
            texts = [c.get("text", "") for c in contents if isinstance(c, dict)]
            return "\n".join(t for t in texts if t)
        return str(contents)

    def complete(self, prompt: str, model: str = "deepseek-chat") -> str:
        """Text completion (FIM / raw prompt)."""
        result = self.call_tool("completion", {"prompt": prompt, "model": model})
        contents = result.get("content", [])
        if isinstance(contents, list):
            texts = [c.get("text", "") for c in contents if isinstance(c, dict)]
            return "\n".join(t for t in texts if t)
        return str(contents)

    def list_models(self) -> list[str]:
        """Return available DeepSeek model IDs."""
        result = self.call_tool("list_models")
        contents = result.get("content", [])
        if isinstance(contents, list):
            for block in contents:
                text = block.get("text", "")
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, list):
                        return [m.get("id", m) if isinstance(m, dict) else str(m) for m in parsed]
                    if isinstance(parsed, dict) and "data" in parsed:
                        return [m.get("id", "") for m in parsed["data"]]
                except (json.JSONDecodeError, TypeError):
                    pass
        return []

    def reset_conversation(self, conversation_id: str) -> bool:
        """Clear a stored conversation."""
        try:
            self.call_tool("reset_conversation", {"conversation_id": conversation_id})
            return True
        except MCPClientError:
            return False

    def ping(self, timeout: int = 5) -> bool:
        """Return True if the server is reachable."""
        try:
            self.list_tools()
            return True
        except MCPClientError:
            return False
