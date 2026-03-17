"""Tests for v3.9.0 — DeepSeek MCP Server Integration.

Tests cover: server manager, MCP client, DeepSeekTool, and CLI commands.
All tests are offline (mock-based) — no live server required.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
import asyncio
import pytest

from jagabot.mcp.server_manager import MCPServerManager, _REPO_PATH, _DEFAULT_PORT
from jagabot.mcp.client import DeepSeekMCPClient, MCPClientError
from jagabot.agent.tools.deepseek import DeepSeekTool


# ── Helpers ─────────────────────────────────────────────────────────────

def _run(coro):
    return asyncio.run(coro)


# ── MCPServerManager ────────────────────────────────────────────────────

class TestMCPServerManager:

    def test_default_repo_path(self):
        m = MCPServerManager()
        assert m.repo_path == _REPO_PATH

    def test_custom_repo_path(self, tmp_path):
        m = MCPServerManager(repo_path=tmp_path)
        assert m.repo_path == tmp_path

    def test_default_port(self):
        m = MCPServerManager()
        assert m.port == _DEFAULT_PORT

    def test_custom_port(self):
        m = MCPServerManager(port=4000)
        assert m.port == 4000

    def test_base_url(self):
        m = MCPServerManager(host="127.0.0.1", port=3001)
        assert m.base_url == "http://127.0.0.1:3001"

    def test_entry_point(self):
        m = MCPServerManager()
        assert m.entry_point == _REPO_PATH / "build" / "index.js"

    def test_is_built_true(self, tmp_path):
        build = tmp_path / "build"
        build.mkdir()
        (build / "index.js").write_text("// stub")
        m = MCPServerManager(repo_path=tmp_path)
        assert m.is_built is True

    def test_is_built_false(self, tmp_path):
        m = MCPServerManager(repo_path=tmp_path)
        assert m.is_built is False

    def test_start_not_built(self, tmp_path):
        m = MCPServerManager(repo_path=tmp_path)
        result = m.start()
        assert result["success"] is False
        assert "not built" in result["error"]

    def test_start_already_running(self, tmp_path):
        build = tmp_path / "build"
        build.mkdir()
        (build / "index.js").write_text("// stub")
        m = MCPServerManager(repo_path=tmp_path)

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # still running
        mock_proc.pid = 9999
        m._process = mock_proc

        result = m.start()
        assert result["success"] is True
        assert result.get("already_running") is True

    def test_stop_no_process(self):
        m = MCPServerManager()
        result = m.stop()
        assert result["success"] is False

    def test_stop_running_process(self):
        m = MCPServerManager()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 1234
        m._process = mock_proc

        result = m.stop()
        assert result["success"] is True
        mock_proc.terminate.assert_called_once()
        assert m._process is None

    def test_status_stopped_no_process(self):
        m = MCPServerManager()
        st = m.status()
        assert st["status"] == "stopped"
        assert st["pid"] is None

    def test_status_running(self):
        m = MCPServerManager()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.pid = 5678
        m._process = mock_proc

        st = m.status()
        assert st["status"] == "running"
        assert st["pid"] == 5678
        assert "url" in st

    def test_status_stopped_exited(self):
        m = MCPServerManager()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1  # exited with code 1
        mock_proc.pid = 1111
        m._process = mock_proc

        st = m.status()
        assert st["status"] == "stopped"
        assert st["exit_code"] == 1

    def test_detect_info(self, tmp_path):
        m = MCPServerManager(repo_path=tmp_path, port=3001, host="127.0.0.1")
        info = m.detect_info()
        assert info["language"] == "node"
        assert info["transport"] == "streamable-http"
        assert info["port"] == 3001
        assert info["is_built"] is False


# ── DeepSeekMCPClient ────────────────────────────────────────────────────

class TestDeepSeekMCPClient:

    def _make_response(self, result):
        """Build a fake urllib response."""
        class _Resp:
            def read(self):
                return json.dumps({"jsonrpc": "2.0", "id": 1, "result": result}).encode()
            def __enter__(self): return self
            def __exit__(self, *a): pass
        return _Resp()

    def _make_error_response(self, code, message):
        class _Resp:
            def read(self):
                return json.dumps({"jsonrpc": "2.0", "id": 1, "error": {"code": code, "message": message}}).encode()
            def __enter__(self): return self
            def __exit__(self, *a): pass
        return _Resp()

    def test_request_id_increments(self):
        c = DeepSeekMCPClient()
        assert c._next_id() == 1
        assert c._next_id() == 2
        assert c._next_id() == 3

    def test_list_tools_parses_tools_key(self):
        c = DeepSeekMCPClient()
        tools_data = {"tools": [{"name": "chat_completion"}, {"name": "list_models"}]}
        with patch("urllib.request.urlopen", return_value=self._make_response(tools_data)):
            tools = c.list_tools()
        assert len(tools) == 2
        assert tools[0]["name"] == "chat_completion"

    def test_list_tools_handles_list_result(self):
        c = DeepSeekMCPClient()
        tools_data = [{"name": "tool_a"}, {"name": "tool_b"}]
        with patch("urllib.request.urlopen", return_value=self._make_response(tools_data)):
            tools = c.list_tools()
        assert len(tools) == 2

    def test_call_tool_success(self):
        c = DeepSeekMCPClient()
        result = {"content": [{"type": "text", "text": "Hello!"}]}
        with patch("urllib.request.urlopen", return_value=self._make_response(result)):
            out = c.call_tool("chat_completion", {"message": "hi"})
        assert out == result

    def test_call_tool_error_raises(self):
        c = DeepSeekMCPClient()
        with patch("urllib.request.urlopen", return_value=self._make_error_response(-32601, "Method not found")):
            with pytest.raises(MCPClientError, match="Method not found"):
                c.call_tool("unknown_tool")

    def test_chat_extracts_text(self):
        c = DeepSeekMCPClient()
        result = {"content": [{"type": "text", "text": "DeepSeek reply"}]}
        with patch.object(c, "call_tool", return_value=result):
            reply = c.chat("hello")
        assert reply == "DeepSeek reply"

    def test_chat_empty_response(self):
        c = DeepSeekMCPClient()
        with patch.object(c, "call_tool", return_value={}):
            reply = c.chat("hello")
        assert reply == ""

    def test_complete_extracts_text(self):
        c = DeepSeekMCPClient()
        result = {"content": [{"type": "text", "text": "completion text"}]}
        with patch.object(c, "call_tool", return_value=result):
            out = c.complete("my prompt")
        assert out == "completion text"

    def test_list_models_parses_list(self):
        c = DeepSeekMCPClient()
        models_json = json.dumps([{"id": "deepseek-chat"}, {"id": "deepseek-reasoner"}])
        result = {"content": [{"type": "text", "text": models_json}]}
        with patch.object(c, "call_tool", return_value=result):
            models = c.list_models()
        assert "deepseek-chat" in models
        assert "deepseek-reasoner" in models

    def test_list_models_parses_data_key(self):
        c = DeepSeekMCPClient()
        models_json = json.dumps({"data": [{"id": "deepseek-chat"}]})
        result = {"content": [{"type": "text", "text": models_json}]}
        with patch.object(c, "call_tool", return_value=result):
            models = c.list_models()
        assert models == ["deepseek-chat"]

    def test_ping_returns_true_on_success(self):
        c = DeepSeekMCPClient()
        with patch.object(c, "list_tools", return_value=[]):
            assert c.ping() is True

    def test_ping_returns_false_on_error(self):
        c = DeepSeekMCPClient()
        with patch.object(c, "list_tools", side_effect=MCPClientError("unreachable")):
            assert c.ping() is False

    def test_reset_conversation_success(self):
        c = DeepSeekMCPClient()
        with patch.object(c, "call_tool", return_value={}):
            assert c.reset_conversation("conv-1") is True

    def test_reset_conversation_failure(self):
        c = DeepSeekMCPClient()
        with patch.object(c, "call_tool", side_effect=MCPClientError("fail")):
            assert c.reset_conversation("conv-1") is False

    def test_network_error_raises_mcp_error(self):
        import urllib.error
        c = DeepSeekMCPClient()
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("connection refused")):
            with pytest.raises(MCPClientError, match="Cannot reach MCP server"):
                c.list_tools()


# ── DeepSeekTool ─────────────────────────────────────────────────────────

class TestDeepSeekTool:

    @pytest.fixture
    def tool(self):
        t = DeepSeekTool()
        t._client = MagicMock()
        t._manager = MagicMock()
        return t

    def test_name(self, tool):
        assert tool.name == "deepseek"

    def test_description_contains_actions(self, tool):
        desc = tool.description
        assert "chat" in desc
        assert "complete" in desc
        assert "list_models" in desc

    def test_parameters_schema(self, tool):
        schema = tool.parameters
        assert schema["type"] == "object"
        assert "action" in schema["properties"]
        assert "required" in schema
        assert "action" in schema["required"]

    def test_execute_chat(self, tool):
        tool._client.chat.return_value = "Hello from DeepSeek"
        result = _run(tool.execute(action="chat", message="hi"))
        assert result == "Hello from DeepSeek"
        tool._client.chat.assert_called_once()

    def test_execute_chat_no_message(self, tool):
        result = _run(tool.execute(action="chat"))
        assert "required" in result.lower() or "message" in result.lower()

    def test_execute_complete(self, tool):
        tool._client.complete.return_value = "completion result"
        result = _run(tool.execute(action="complete", message="prompt text"))
        assert result == "completion result"

    def test_execute_complete_no_message(self, tool):
        result = _run(tool.execute(action="complete"))
        assert "required" in result.lower() or "message" in result.lower()

    def test_execute_list_models(self, tool):
        tool._client.list_models.return_value = ["deepseek-chat", "deepseek-reasoner"]
        result = _run(tool.execute(action="list_models"))
        data = json.loads(result)
        assert "models" in data
        assert "deepseek-chat" in data["models"]

    def test_execute_list_models_empty(self, tool):
        tool._client.list_models.return_value = []
        result = _run(tool.execute(action="list_models"))
        data = json.loads(result)
        assert data["models"] == []

    def test_execute_status(self, tool):
        tool._manager.status.return_value = {"status": "running", "pid": 1234}
        result = _run(tool.execute(action="status"))
        data = json.loads(result)
        assert data["status"] == "running"

    def test_execute_start(self, tool):
        tool._manager.start.return_value = {"success": True, "pid": 5678}
        result = _run(tool.execute(action="start"))
        data = json.loads(result)
        assert data["success"] is True

    def test_execute_stop(self, tool):
        tool._manager.stop.return_value = {"success": True}
        result = _run(tool.execute(action="stop"))
        data = json.loads(result)
        assert data["success"] is True

    def test_execute_unknown_action(self, tool):
        result = _run(tool.execute(action="fly"))
        assert "Unknown action" in result

    def test_execute_chat_mcp_error(self, tool):
        tool._client.chat.side_effect = MCPClientError("server down")
        result = _run(tool.execute(action="chat", message="test"))
        assert "MCP error" in result

    def test_execute_complete_mcp_error(self, tool):
        tool._client.complete.side_effect = MCPClientError("timeout")
        result = _run(tool.execute(action="complete", message="test"))
        assert "MCP error" in result

    def test_execute_list_models_mcp_error(self, tool):
        tool._client.list_models.side_effect = MCPClientError("unreachable")
        result = _run(tool.execute(action="list_models"))
        assert "MCP error" in result

    def test_chat_passes_conversation_id(self, tool):
        tool._client.chat.return_value = "ok"
        _run(tool.execute(action="chat", message="hi", conversation_id="abc-123"))
        call_kwargs = tool._client.chat.call_args
        assert call_kwargs.kwargs.get("conversation_id") == "abc-123"

    def test_chat_passes_temperature(self, tool):
        tool._client.chat.return_value = "ok"
        _run(tool.execute(action="chat", message="hi", temperature=0.5))
        call_kwargs = tool._client.chat.call_args
        assert call_kwargs.kwargs.get("temperature") == 0.5


# ── Integration: tool in registry ────────────────────────────────────────

class TestDeepSeekToolRegistration:

    def test_tool_is_registered_in_loop(self):
        """DeepSeekTool must be registered in AgentLoop's default tools."""
        from jagabot.agent.loop import AgentLoop
        import inspect
        source = inspect.getsource(AgentLoop._register_default_tools)
        assert "DeepSeekTool" in source

    def test_tool_validates_params(self):
        tool = DeepSeekTool()
        errors = tool.validate_params({"action": "status"})
        assert errors == []

    def test_tool_validates_missing_required(self):
        tool = DeepSeekTool()
        errors = tool.validate_params({})
        assert any("action" in e for e in errors)
