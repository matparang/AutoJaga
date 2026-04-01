"""DeepSeek MCP tool — gives the agent access to DeepSeek AI via the local MCP server."""

from __future__ import annotations

import json
from typing import Any

from jagabot.agent.tools.base import Tool
from jagabot.mcp.client import DeepSeekMCPClient, MCPClientError
from jagabot.mcp.server_manager import MCPServerManager


class DeepSeekTool(Tool):
    """Interact with DeepSeek AI models via the local MCP server.

    Actions
    -------
    chat         — send a message and receive a reply
    complete     — raw text/FIM completion
    list_models  — list available DeepSeek models
    status       — check MCP server status
    start        — start the MCP server
    stop         — stop the MCP server
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 3001,
        deepseek_api_key: str = "",
    ) -> None:
        self._host = host
        self._port = port
        self._api_key = deepseek_api_key
        self._manager = MCPServerManager(port=port, host=host)
        self._client = DeepSeekMCPClient(host=host, port=port)

    # ------------------------------------------------------------------
    # Tool ABC
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "deepseek"

    @property
    def description(self) -> str:
        return (
            "Access DeepSeek AI models via the local MCP server. "
            "Actions: chat (send message), complete (text completion), "
            "list_models, status, start, stop."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["chat", "complete", "list_models", "status", "start", "stop"],
                    "description": "Action to perform",
                },
                "message": {
                    "type": "string",
                    "description": "Message or prompt text (for chat/complete actions)",
                },
                "model": {
                    "type": "string",
                    "description": "DeepSeek model ID (default: deepseek-chat)",
                },
                "conversation_id": {
                    "type": "string",
                    "description": "Conversation ID for multi-turn chat (optional)",
                },
                "temperature": {
                    "type": "number",
                    "description": "Sampling temperature 0.0–2.0 (optional)",
                },
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")

        if action == "chat":
            return await self._chat(kwargs)
        elif action == "complete":
            return await self._complete(kwargs)
        elif action == "list_models":
            return await self._list_models()
        elif action == "status":
            return json.dumps(self._manager.status())
        elif action == "start":
            return json.dumps(self._manager.start(deepseek_api_key=self._api_key))
        elif action == "stop":
            return json.dumps(self._manager.stop())
        else:
            return f"Unknown action: {action!r}. Use: chat, complete, list_models, status, start, stop"

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    async def _chat(self, kwargs: dict) -> str:
        message = kwargs.get("message", "")
        if not message:
            return "Error: 'message' is required for action=chat"
        try:
            reply = self._client.chat(
                message=message,
                conversation_id=kwargs.get("conversation_id"),
                model=kwargs.get("model", "deepseek-chat"),
                temperature=kwargs.get("temperature"),
            )
            return reply or "(empty response)"
        except MCPClientError as exc:
            return f"MCP error: {exc}"

    async def _complete(self, kwargs: dict) -> str:
        message = kwargs.get("message", "")
        if not message:
            return "Error: 'message' is required for action=complete"
        try:
            result = self._client.complete(
                prompt=message,
                model=kwargs.get("model", "deepseek-chat"),
            )
            return result or "(empty response)"
        except MCPClientError as exc:
            return f"MCP error: {exc}"

    async def _list_models(self) -> str:
        try:
            models = self._client.list_models()
            if models:
                return json.dumps({"models": models})
            return json.dumps({"models": [], "note": "Server returned no models or is unreachable"})
        except MCPClientError as exc:
            return f"MCP error: {exc}"
