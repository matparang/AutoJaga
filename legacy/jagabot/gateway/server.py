"""WebSocket gateway server for PinchChat integration.

Implements the OpenClaw-compatible gateway protocol that PinchChat expects:
- Request/response pattern (type: req → type: res)
- Event broadcasting (type: event)
- Token-based authentication
- Session management
- Chat streaming with delta/final/error states
- Tool call visualization events
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Awaitable

import websockets
from loguru import logger


@dataclass
class ConnectedClient:
    """A connected PinchChat client."""
    ws: Any
    client_id: str = "webchat"
    authenticated: bool = False
    active_session: str = "agent:main:main"
    connected_at: float = field(default_factory=time.time)


class GatewayServer:
    """WebSocket gateway server implementing PinchChat's protocol.
    
    Protocol:
    - Client sends: {"type": "req", "id": "...", "method": "...", "params": {...}}
    - Server responds: {"type": "res", "id": "...", "ok": true/false, "payload": {...}}
    - Server pushes: {"type": "event", "event": "...", "payload": {...}}
    """

    def __init__(
        self,
        agent_loop: Any,
        session_manager: Any,
        workspace: Path,
        auth_token: str = "",
        host: str = "0.0.0.0",
        port: int = 18789,
        agent_name: str = "Jagabot",
        agent_emoji: str = "🐯",
    ):
        self.agent = agent_loop
        self.sessions = session_manager
        self.workspace = workspace
        self.auth_token = auth_token
        self.host = host
        self.port = port
        self.agent_name = agent_name
        self.agent_emoji = agent_emoji
        self.clients: dict[str, ConnectedClient] = {}
        self._active_runs: dict[str, asyncio.Task] = {}
        self._abort_flags: dict[str, asyncio.Event] = {}

    async def start(self) -> None:
        """Start the WebSocket gateway server."""
        logger.info(f"Gateway server starting on ws://{self.host}:{self.port}")
        async with websockets.serve(
            self._handle_connection,
            self.host,
            self.port,
            max_size=10 * 1024 * 1024,  # 10MB
        ):
            await asyncio.Future()  # run forever

    async def _handle_connection(self, ws: Any) -> None:
        """Handle a new WebSocket connection."""
        client_id = str(uuid.uuid4())[:8]
        client = ConnectedClient(ws=ws, client_id=client_id)
        self.clients[client_id] = client
        logger.info(f"Client connected: {client_id}")

        # Send connect challenge
        await self._send_event(ws, "connect.challenge", {"nonce": str(uuid.uuid4())})

        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from {client_id}")
                    continue

                if msg.get("type") == "req":
                    await self._handle_request(client, msg)
                else:
                    logger.debug(f"Unknown message type from {client_id}: {msg.get('type')}")
        except websockets.ConnectionClosed:
            logger.info(f"Client disconnected: {client_id}")
        finally:
            self.clients.pop(client_id, None)

    async def _handle_request(self, client: ConnectedClient, msg: dict) -> None:
        """Route a request to the appropriate handler."""
        req_id = msg.get("id", "")
        method = msg.get("method", "")
        params = msg.get("params", {})

        handlers = {
            "connect": self._handle_connect,
            "sessions.list": self._handle_sessions_list,
            "sessions.create": self._handle_sessions_create,
            "sessions.delete": self._handle_sessions_delete,
            "chat.send": self._handle_chat_send,
            "chat.history": self._handle_chat_history,
            "chat.abort": self._handle_chat_abort,
            "agent.identity.get": self._handle_agent_identity,
        }

        handler = handlers.get(method)
        if handler:
            try:
                result = await handler(client, params)
                await self._send_response(client.ws, req_id, True, result)
            except Exception as e:
                logger.error(f"Handler error for {method}: {e}")
                await self._send_response(client.ws, req_id, False, {"error": str(e)})
        else:
            logger.warning(f"Unknown method: {method}")
            await self._send_response(client.ws, req_id, False, {"error": f"unknown method: {method}"})

    # ── Protocol handlers ────────────────────────────────────────────

    async def _handle_connect(self, client: ConnectedClient, params: dict) -> dict:
        """Handle connect/authentication."""
        auth = params.get("auth", {})
        token = auth.get("token", "") or auth.get("password", "")

        # Accept if no auth token configured, or token matches
        if self.auth_token and token != self.auth_token:
            raise ValueError("Invalid authentication token")

        client.authenticated = True
        client_info = params.get("client", {})
        client.client_id = client_info.get("id", client.client_id)

        logger.info(f"Client authenticated: {client.client_id}")
        return {
            "protocol": 3,
            "agent": {
                "name": self.agent_name,
                "emoji": self.agent_emoji,
            },
        }

    async def _handle_agent_identity(self, client: ConnectedClient, params: dict) -> dict:
        """Return agent identity info."""
        return {
            "name": self.agent_name,
            "emoji": self.agent_emoji,
            "agentId": "main",
        }

    async def _handle_sessions_list(self, client: ConnectedClient, params: dict) -> dict:
        """List all sessions."""
        raw_sessions = self.sessions.list_sessions()
        sessions = []
        for s in raw_sessions:
            key = s.get("key", "unknown")
            # Load session to get message count
            session = self.sessions.get_or_create(key)
            msg_count = len(session.messages)
            last_preview = ""
            if session.messages:
                last_msg = session.messages[-1]
                content = last_msg.get("content", "")
                last_preview = content[:80] + "..." if len(content) > 80 else content

            sessions.append({
                "key": f"agent:main:{key}",
                "sessionKey": f"agent:main:{key}",
                "label": key,
                "messageCount": msg_count,
                "channel": "webchat",
                "kind": "agent",
                "agentId": "main",
                "updatedAt": _iso_to_ms(s.get("updated_at")),
                "lastMessagePreview": last_preview,
            })

        # Always ensure a default session exists
        if not any(s["key"] == "agent:main:main" for s in sessions):
            sessions.insert(0, {
                "key": "agent:main:main",
                "sessionKey": "agent:main:main",
                "label": "Main",
                "messageCount": 0,
                "channel": "webchat",
                "kind": "agent",
                "agentId": "main",
                "updatedAt": int(time.time() * 1000),
                "lastMessagePreview": "",
            })

        return {"sessions": sessions}

    async def _handle_sessions_create(self, client: ConnectedClient, params: dict) -> dict:
        """Create a new session."""
        agent_id = params.get("agentId", "main")
        ts = int(time.time() * 1000)
        key = f"agent:{agent_id}:webchat-{ts}"
        internal_key = f"webchat-{ts}"

        # Create the session internally
        self.sessions.get_or_create(internal_key)

        return {
            "key": key,
            "sessionKey": key,
            "session": {
                "key": key,
                "label": f"Chat {ts}",
                "messageCount": 0,
                "channel": "webchat",
                "agentId": agent_id,
            },
        }

    async def _handle_sessions_delete(self, client: ConnectedClient, params: dict) -> dict:
        """Delete a session."""
        key = params.get("key", "")
        internal_key = _extract_internal_key(key)
        self.sessions.delete(internal_key)
        return {"deleted": True}

    async def _handle_chat_history(self, client: ConnectedClient, params: dict) -> dict:
        """Return chat history for a session."""
        session_key = params.get("sessionKey", "agent:main:main")
        limit = params.get("limit", 100)
        internal_key = _extract_internal_key(session_key)

        session = self.sessions.get_or_create(internal_key)
        messages = []

        for msg in session.messages[-limit:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            timestamp = msg.get("timestamp", "")

            chat_msg: dict[str, Any] = {
                "role": role,
                "content": [{"type": "text", "text": content}],
                "timestamp": timestamp,
            }

            # Include tool info if present
            tools_used = msg.get("tools_used")
            if tools_used and role == "assistant":
                for tool_name in tools_used:
                    chat_msg["content"].insert(0, {
                        "type": "tool_use",
                        "name": tool_name,
                        "input": {},
                        "id": f"tool-{uuid.uuid4().hex[:8]}",
                    })

            messages.append(chat_msg)

        return {"messages": messages}

    async def _handle_chat_send(self, client: ConnectedClient, params: dict) -> dict:
        """Handle a chat message from PinchChat."""
        session_key = params.get("sessionKey", "agent:main:main")
        message = params.get("message", "")
        internal_key = _extract_internal_key(session_key)

        if not message.strip():
            return {"ok": True}

        run_id = f"run-{uuid.uuid4().hex[:12]}"
        abort_event = asyncio.Event()
        self._abort_flags[session_key] = abort_event

        # Process asynchronously so we can stream
        task = asyncio.create_task(
            self._process_and_stream(client, session_key, internal_key, message, run_id, abort_event)
        )
        self._active_runs[session_key] = task
        return {"ok": True, "runId": run_id}

    async def _handle_chat_abort(self, client: ConnectedClient, params: dict) -> dict:
        """Abort an active chat generation."""
        session_key = params.get("sessionKey", "agent:main:main")
        abort_event = self._abort_flags.get(session_key)
        if abort_event:
            abort_event.set()

        task = self._active_runs.get(session_key)
        if task and not task.done():
            task.cancel()

        # Send aborted event
        await self._broadcast_chat_event(session_key, "aborted", run_id="")
        return {"ok": True}

    # ── Streaming engine ─────────────────────────────────────────────

    async def _process_and_stream(
        self,
        client: ConnectedClient,
        session_key: str,
        internal_key: str,
        message: str,
        run_id: str,
        abort_event: asyncio.Event,
    ) -> None:
        """Process a message through the agent and stream results to PinchChat."""
        try:
            from jagabot.bus.events import InboundMessage

            msg = InboundMessage(
                channel="webchat",
                sender_id="user",
                chat_id=internal_key,
                content=message,
            )

            session = self.sessions.get_or_create(internal_key)

            # Consolidate if needed
            if len(session.messages) > self.agent.memory_window:
                await self.agent._consolidate_memory(session)

            # Update tool contexts
            from jagabot.agent.tools.message import MessageTool
            from jagabot.agent.tools.spawn import SpawnTool
            from jagabot.agent.tools.cron import CronTool

            message_tool = self.agent.tools.get("message")
            if isinstance(message_tool, MessageTool):
                message_tool.set_context("webchat", internal_key)

            spawn_tool = self.agent.tools.get("spawn")
            if isinstance(spawn_tool, SpawnTool):
                spawn_tool.set_context("webchat", internal_key)

            cron_tool = self.agent.tools.get("cron")
            if isinstance(cron_tool, CronTool):
                cron_tool.set_context("webchat", internal_key)

            # Build messages
            messages = self.agent.context.build_messages(
                history=session.get_history(),
                current_message=message,
                channel="webchat",
                chat_id=internal_key,
            )

            iteration = 0
            final_content = None
            tools_used: list[str] = []

            while iteration < self.agent.max_iterations:
                if abort_event.is_set():
                    await self._broadcast_chat_event(session_key, "aborted", run_id=run_id)
                    return

                iteration += 1

                # Call LLM with streaming
                response = await self.agent.provider.chat(
                    messages=messages,
                    tools=self.agent.tools.get_definitions(),
                    model=self.agent.model,
                    temperature=self.agent.temperature,
                )

                if response.has_tool_calls:
                    # Send tool call events to PinchChat
                    tool_call_dicts = []
                    for tc in response.tool_calls:
                        tool_call_dicts.append({
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        })

                        # Emit tool start event
                        await self._broadcast_agent_event(session_key, {
                            "stream": "tool",
                            "data": {
                                "phase": "start",
                                "toolCallId": tc.id,
                                "name": tc.name,
                                "args": tc.arguments,
                            },
                        })

                    # Add assistant message with tool calls
                    messages = self.agent.context.add_assistant_message(
                        messages, response.content, tool_call_dicts,
                        reasoning_content=response.reasoning_content,
                    )

                    # Execute tools
                    for tc in response.tool_calls:
                        tools_used.append(tc.name)
                        args_str = json.dumps(tc.arguments, ensure_ascii=False)
                        logger.info(f"Tool call: {tc.name}({args_str[:200]})")
                        result = await self.agent.tools.execute(tc.name, tc.arguments)
                        messages = self.agent.context.add_tool_result(
                            messages, tc.id, tc.name, result,
                        )

                        # Emit tool result event
                        await self._broadcast_agent_event(session_key, {
                            "stream": "tool",
                            "data": {
                                "phase": "result",
                                "toolCallId": tc.id,
                                "name": tc.name,
                                "result": result[:2000] if len(result) > 2000 else result,
                            },
                        })

                    # Interleaved CoT
                    messages.append({"role": "user", "content": "Reflect on the results and decide next steps."})

                    # Send partial text as delta if the LLM included reasoning
                    if response.content:
                        await self._broadcast_chat_event(
                            session_key, "delta", run_id=run_id,
                            message={"content": [{"type": "text", "text": response.content}]},
                        )
                else:
                    final_content = response.content
                    break

            if final_content is None:
                final_content = f"Reached {self.agent.max_iterations} iterations without completion."

            # Stream final content as delta then final
            await self._broadcast_chat_event(
                session_key, "delta", run_id=run_id,
                message={"content": [{"type": "text", "text": final_content}]},
            )

            # Save to session
            session.add_message("user", message)
            session.add_message("assistant", final_content,
                                tools_used=tools_used if tools_used else None)
            self.sessions.save(session)

            # Send final event (PinchChat will reload history)
            await self._broadcast_chat_event(session_key, "final", run_id=run_id)

        except asyncio.CancelledError:
            await self._broadcast_chat_event(session_key, "aborted", run_id=run_id)
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await self._broadcast_chat_event(
                session_key, "error", run_id=run_id,
                error_message=str(e),
            )
        finally:
            self._active_runs.pop(session_key, None)
            self._abort_flags.pop(session_key, None)

    # ── Event broadcasting ───────────────────────────────────────────

    async def _send_event(self, ws: Any, event: str, payload: dict) -> None:
        """Send an event to a specific client."""
        try:
            await ws.send(json.dumps({
                "type": "event",
                "event": event,
                "payload": payload,
            }))
        except websockets.ConnectionClosed:
            pass

    async def _send_response(self, ws: Any, req_id: str, ok: bool, payload: dict) -> None:
        """Send a response to a request."""
        try:
            await ws.send(json.dumps({
                "type": "res",
                "id": req_id,
                "ok": ok,
                "payload": payload,
            }))
        except websockets.ConnectionClosed:
            pass

    async def _broadcast_chat_event(
        self,
        session_key: str,
        state: str,
        run_id: str = "",
        message: dict | None = None,
        error_message: str | None = None,
    ) -> None:
        """Broadcast a chat event to all connected clients."""
        payload: dict[str, Any] = {
            "sessionKey": session_key,
            "state": state,
            "runId": run_id,
        }
        if message:
            payload["message"] = message
        if error_message:
            payload["errorMessage"] = error_message

        for client in list(self.clients.values()):
            if client.authenticated:
                await self._send_event(client.ws, "chat", payload)

    async def _broadcast_agent_event(self, session_key: str, payload: dict) -> None:
        """Broadcast an agent event (tool calls, etc.) to all connected clients."""
        for client in list(self.clients.values()):
            if client.authenticated:
                await self._send_event(client.ws, "agent", {**payload, "sessionKey": session_key})


# ── Helpers ──────────────────────────────────────────────────────────

def _extract_internal_key(pinchchat_key: str) -> str:
    """Convert PinchChat session key to internal jagabot key.
    
    PinchChat uses: agent:main:webchat-123
    Jagabot uses: webchat-123
    
    Special case: agent:main:main → webchat:direct (default jagabot session)
    """
    parts = pinchchat_key.split(":")
    if len(parts) >= 3:
        internal = ":".join(parts[2:])
        if internal == "main":
            return "webchat:direct"
        return internal
    if pinchchat_key == "main":
        return "webchat:direct"
    return pinchchat_key


def _iso_to_ms(iso_str: str | None) -> int:
    """Convert ISO timestamp string to milliseconds since epoch."""
    if not iso_str:
        return int(time.time() * 1000)
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(iso_str)
        return int(dt.timestamp() * 1000)
    except (ValueError, TypeError):
        return int(time.time() * 1000)
