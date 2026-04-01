"""Tests for v3.11.0 — Upsonic integration (UpsonicChatAgent + CLI + SwarmTab).

Run with:
    pytest tests/test_jagabot/test_upsonic.py -q
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    """Run coroutine synchronously."""
    return asyncio.run(coro)


# ===========================================================================
# UpsonicChatAgent — unit tests
# ===========================================================================

class TestUpsonicChatAgentImport:
    def test_module_importable(self):
        from jagabot.agent import upsonic_chat  # noqa: F401

    def test_upsonic_available_flag_is_bool(self):
        from jagabot.agent.upsonic_chat import _UPSONIC_AVAILABLE
        assert isinstance(_UPSONIC_AVAILABLE, bool)

    def test_safety_available_flag_is_bool(self):
        from jagabot.agent.upsonic_chat import _SAFETY_AVAILABLE
        assert isinstance(_SAFETY_AVAILABLE, bool)

    def test_session_registry_is_dict(self):
        from jagabot.agent.upsonic_chat import _session_registry
        assert isinstance(_session_registry, dict)


class TestUpsonicChatAgentInit:
    def _make_agent(self, session_id="test-sess", model="openai/gpt-4o"):
        """Build UpsonicChatAgent with all Upsonic internals mocked."""
        mock_memory = MagicMock()
        mock_upsonic_agent = MagicMock()
        mock_storage = MagicMock()

        with patch("jagabot.agent.upsonic_chat._UPSONIC_AVAILABLE", True), \
             patch("jagabot.agent.upsonic_chat.InMemoryStorage", return_value=mock_storage), \
             patch("jagabot.agent.upsonic_chat.Memory", return_value=mock_memory), \
             patch("jagabot.agent.upsonic_chat.Agent", return_value=mock_upsonic_agent), \
             patch("jagabot.agent.upsonic_chat._SAFETY_AVAILABLE", False):
            from jagabot.agent.upsonic_chat import UpsonicChatAgent
            agent = UpsonicChatAgent(session_id=session_id, model=model, apply_safety=False)
        return agent, mock_upsonic_agent, mock_memory

    def test_session_id_stored(self):
        agent, _, _ = self._make_agent(session_id="my-session")
        assert agent.session_id == "my-session"

    def test_model_stored(self):
        agent, _, _ = self._make_agent(model="anthropic/claude-3-sonnet")
        assert agent.model == "anthropic/claude-3-sonnet"

    def test_message_count_starts_at_zero(self):
        agent, _, _ = self._make_agent()
        assert agent._message_count == 0

    def test_repr_contains_session_id(self):
        agent, _, _ = self._make_agent(session_id="repr-test")
        assert "repr-test" in repr(agent)

    def test_init_fails_when_upsonic_not_available(self):
        with patch("jagabot.agent.upsonic_chat._UPSONIC_AVAILABLE", False):
            from jagabot.agent.upsonic_chat import UpsonicChatAgent, UpsonicChatAgentError
            with pytest.raises(UpsonicChatAgentError):
                UpsonicChatAgent(session_id="x")

    def test_auto_generates_session_id_when_none(self):
        mock_memory = MagicMock()
        with patch("jagabot.agent.upsonic_chat._UPSONIC_AVAILABLE", True), \
             patch("jagabot.agent.upsonic_chat.InMemoryStorage", return_value=MagicMock()), \
             patch("jagabot.agent.upsonic_chat.Memory", return_value=mock_memory), \
             patch("jagabot.agent.upsonic_chat.Agent", return_value=MagicMock()), \
             patch("jagabot.agent.upsonic_chat._SAFETY_AVAILABLE", False):
            from jagabot.agent.upsonic_chat import UpsonicChatAgent
            agent = UpsonicChatAgent(session_id=None)
            assert agent.session_id is not None
            assert len(agent.session_id) > 0

    def test_memory_created_with_session_id(self):
        mock_memory_cls = MagicMock(return_value=MagicMock())
        with patch("jagabot.agent.upsonic_chat._UPSONIC_AVAILABLE", True), \
             patch("jagabot.agent.upsonic_chat.InMemoryStorage", return_value=MagicMock()), \
             patch("jagabot.agent.upsonic_chat.Memory", mock_memory_cls), \
             patch("jagabot.agent.upsonic_chat.Agent", return_value=MagicMock()), \
             patch("jagabot.agent.upsonic_chat._SAFETY_AVAILABLE", False):
            from jagabot.agent.upsonic_chat import UpsonicChatAgent
            UpsonicChatAgent(session_id="mem-test")
            call_kwargs = mock_memory_cls.call_args.kwargs
            assert call_kwargs.get("session_id") == "mem-test"

    def test_full_session_memory_enabled(self):
        mock_memory_cls = MagicMock(return_value=MagicMock())
        with patch("jagabot.agent.upsonic_chat._UPSONIC_AVAILABLE", True), \
             patch("jagabot.agent.upsonic_chat.InMemoryStorage", return_value=MagicMock()), \
             patch("jagabot.agent.upsonic_chat.Memory", mock_memory_cls), \
             patch("jagabot.agent.upsonic_chat.Agent", return_value=MagicMock()), \
             patch("jagabot.agent.upsonic_chat._SAFETY_AVAILABLE", False):
            from jagabot.agent.upsonic_chat import UpsonicChatAgent
            UpsonicChatAgent(session_id="fsmem")
            call_kwargs = mock_memory_cls.call_args.kwargs
            assert call_kwargs.get("full_session_memory") is True


class TestUpsonicChatAsync:
    def _make_chat_agent(self, response: Any = "Test response"):
        mock_upsonic_agent = MagicMock()
        mock_upsonic_agent.do = MagicMock(return_value=response)

        with patch("jagabot.agent.upsonic_chat._UPSONIC_AVAILABLE", True), \
             patch("jagabot.agent.upsonic_chat.InMemoryStorage", return_value=MagicMock()), \
             patch("jagabot.agent.upsonic_chat.Memory", return_value=MagicMock()), \
             patch("jagabot.agent.upsonic_chat.Agent", return_value=mock_upsonic_agent), \
             patch("jagabot.agent.upsonic_chat._SAFETY_AVAILABLE", False):
            from jagabot.agent.upsonic_chat import UpsonicChatAgent
            agent = UpsonicChatAgent(session_id="chat-test")
        agent.agent = mock_upsonic_agent
        return agent, mock_upsonic_agent

    def test_chat_async_returns_string(self):
        agent, _ = self._make_chat_agent("Hello from Upsonic")
        result = _run(agent.chat_async("Hi there"))
        assert isinstance(result, str)
        assert result == "Hello from Upsonic"

    def test_chat_async_increments_message_count(self):
        agent, _ = self._make_chat_agent("ok")
        _run(agent.chat_async("first"))
        _run(agent.chat_async("second"))
        assert agent._message_count == 2

    def test_chat_async_none_response_returns_empty(self):
        agent, _ = self._make_chat_agent(None)
        result = _run(agent.chat_async("test"))
        assert result == ""

    def test_chat_sync_wrapper(self):
        agent, _ = self._make_chat_agent("sync result")
        result = agent.chat("sync message")
        assert result == "sync result"

    def test_chat_async_calls_agent_do(self):
        agent, mock_agent = self._make_chat_agent("done")
        _run(agent.chat_async("test message"))
        mock_agent.do.assert_called_once()

    def test_chat_async_passes_task_description(self):
        from upsonic import Task
        agent, mock_agent = self._make_chat_agent("done")
        _run(agent.chat_async("my message"))
        call_args = mock_agent.do.call_args
        task_arg = call_args[0][0]
        assert task_arg.description == "my message"


class TestUpsonicSessionRegistry:
    def setup_method(self):
        # Clear registry before each test
        from jagabot.agent import upsonic_chat
        upsonic_chat._session_registry.clear()

    def test_get_or_create_returns_agent(self):
        with patch("jagabot.agent.upsonic_chat._UPSONIC_AVAILABLE", True), \
             patch("jagabot.agent.upsonic_chat.InMemoryStorage", return_value=MagicMock()), \
             patch("jagabot.agent.upsonic_chat.Memory", return_value=MagicMock()), \
             patch("jagabot.agent.upsonic_chat.Agent", return_value=MagicMock()), \
             patch("jagabot.agent.upsonic_chat._SAFETY_AVAILABLE", False):
            from jagabot.agent.upsonic_chat import UpsonicChatAgent
            agent = UpsonicChatAgent.get_or_create("sess-1")
            assert agent is not None
            assert agent.session_id == "sess-1"

    def test_get_or_create_returns_same_instance(self):
        with patch("jagabot.agent.upsonic_chat._UPSONIC_AVAILABLE", True), \
             patch("jagabot.agent.upsonic_chat.InMemoryStorage", return_value=MagicMock()), \
             patch("jagabot.agent.upsonic_chat.Memory", return_value=MagicMock()), \
             patch("jagabot.agent.upsonic_chat.Agent", return_value=MagicMock()), \
             patch("jagabot.agent.upsonic_chat._SAFETY_AVAILABLE", False):
            from jagabot.agent.upsonic_chat import UpsonicChatAgent
            a1 = UpsonicChatAgent.get_or_create("sess-same")
            a2 = UpsonicChatAgent.get_or_create("sess-same")
            assert a1 is a2

    def test_active_sessions_returns_list(self):
        with patch("jagabot.agent.upsonic_chat._UPSONIC_AVAILABLE", True), \
             patch("jagabot.agent.upsonic_chat.InMemoryStorage", return_value=MagicMock()), \
             patch("jagabot.agent.upsonic_chat.Memory", return_value=MagicMock()), \
             patch("jagabot.agent.upsonic_chat.Agent", return_value=MagicMock()), \
             patch("jagabot.agent.upsonic_chat._SAFETY_AVAILABLE", False):
            from jagabot.agent.upsonic_chat import UpsonicChatAgent
            UpsonicChatAgent.get_or_create("s-a")
            UpsonicChatAgent.get_or_create("s-b")
            sessions = UpsonicChatAgent.active_sessions()
            assert "s-a" in sessions
            assert "s-b" in sessions

    def test_clear_session_removes_from_registry(self):
        with patch("jagabot.agent.upsonic_chat._UPSONIC_AVAILABLE", True), \
             patch("jagabot.agent.upsonic_chat.InMemoryStorage", return_value=MagicMock()), \
             patch("jagabot.agent.upsonic_chat.Memory", return_value=MagicMock()), \
             patch("jagabot.agent.upsonic_chat.Agent", return_value=MagicMock()), \
             patch("jagabot.agent.upsonic_chat._SAFETY_AVAILABLE", False):
            from jagabot.agent.upsonic_chat import UpsonicChatAgent
            UpsonicChatAgent.get_or_create("to-clear")
            assert "to-clear" in UpsonicChatAgent.active_sessions()
            removed = UpsonicChatAgent.clear_session("to-clear")
            assert removed is True
            assert "to-clear" not in UpsonicChatAgent.active_sessions()

    def test_clear_nonexistent_session_returns_false(self):
        from jagabot.agent.upsonic_chat import UpsonicChatAgent
        assert UpsonicChatAgent.clear_session("nonexistent") is False

    def test_stats_returns_dict(self):
        with patch("jagabot.agent.upsonic_chat._UPSONIC_AVAILABLE", True), \
             patch("jagabot.agent.upsonic_chat.InMemoryStorage", return_value=MagicMock()), \
             patch("jagabot.agent.upsonic_chat.Memory", return_value=MagicMock()), \
             patch("jagabot.agent.upsonic_chat.Agent", return_value=MagicMock()), \
             patch("jagabot.agent.upsonic_chat._SAFETY_AVAILABLE", False):
            from jagabot.agent.upsonic_chat import UpsonicChatAgent
            agent = UpsonicChatAgent(session_id="stats-test")
            stats = agent.stats()
            assert stats["session_id"] == "stats-test"
            assert "model" in stats
            assert "message_count" in stats
            assert "upsonic_available" in stats


# ===========================================================================
# CLI commands — unit tests (using Typer test runner)
# ===========================================================================

class TestUpsonicCLIImport:
    def test_upsonic_commands_importable(self):
        from jagabot.cli import upsonic_commands  # noqa: F401

    def test_upsonic_app_is_typer(self):
        import typer
        from jagabot.cli.upsonic_commands import upsonic_app
        assert isinstance(upsonic_app, typer.Typer)

    def test_chat_command_registered(self):
        from jagabot.cli.upsonic_commands import upsonic_app
        cmd_names = [cmd.name for cmd in upsonic_app.registered_commands]
        assert "chat" in cmd_names

    def test_status_command_registered(self):
        from jagabot.cli.upsonic_commands import upsonic_app
        cmd_names = [cmd.name for cmd in upsonic_app.registered_commands]
        assert "status" in cmd_names

    def test_clear_command_registered(self):
        from jagabot.cli.upsonic_commands import upsonic_app
        cmd_names = [cmd.name for cmd in upsonic_app.registered_commands]
        assert "clear" in cmd_names


class TestUpsonicCLIChat:
    def test_chat_invokes_get_or_create(self):
        from typer.testing import CliRunner
        from jagabot.cli.upsonic_commands import upsonic_app

        mock_agent = MagicMock()
        mock_agent.chat_async = AsyncMock(return_value="Portfolio looks healthy")

        with patch("jagabot.cli.upsonic_commands.UpsonicChatAgent") as MockClass:
            MockClass.get_or_create.return_value = mock_agent
            runner = CliRunner()
            result = runner.invoke(upsonic_app, ["chat", "Analyze my portfolio", "--session", "sess-cli", "--no-markdown"])

        assert result.exit_code == 0
        MockClass.get_or_create.assert_called_once()

    def test_chat_handles_none_agent_gracefully(self):
        from typer.testing import CliRunner
        from jagabot.cli.upsonic_commands import upsonic_app

        with patch("jagabot.cli.upsonic_commands.UpsonicChatAgent", None):
            runner = CliRunner()
            result = runner.invoke(upsonic_app, ["chat", "hello"])

        assert result.exit_code == 1

    def test_chat_json_flag_outputs_json(self):
        import json
        from typer.testing import CliRunner
        from jagabot.cli.upsonic_commands import upsonic_app

        mock_agent = MagicMock()
        mock_agent.chat_async = AsyncMock(return_value="result text")

        with patch("jagabot.cli.upsonic_commands.UpsonicChatAgent") as MockClass:
            MockClass.get_or_create.return_value = mock_agent
            runner = CliRunner()
            result = runner.invoke(upsonic_app, ["chat", "hello", "--json", "--no-markdown"])

        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert "response" in data
        assert data["response"] == "result text"


class TestUpsonicCLIStatus:
    def test_status_shows_availability(self):
        from typer.testing import CliRunner
        from jagabot.cli.upsonic_commands import upsonic_app

        with patch("jagabot.cli.upsonic_commands._UPSONIC_AVAILABLE", True, create=True):
            runner = CliRunner()
            result = runner.invoke(upsonic_app, ["status"])

        assert result.exit_code == 0

    def test_status_empty_sessions_message(self):
        from typer.testing import CliRunner
        from jagabot.cli.upsonic_commands import upsonic_app

        with patch("jagabot.cli.upsonic_commands._session_registry", {}, create=True):
            runner = CliRunner()
            result = runner.invoke(upsonic_app, ["status"])

        assert result.exit_code == 0


class TestUpsonicCLIClear:
    def test_clear_existing_session(self):
        from typer.testing import CliRunner
        from jagabot.cli.upsonic_commands import upsonic_app

        with patch("jagabot.cli.upsonic_commands.UpsonicChatAgent") as MockClass:
            MockClass.clear_session.return_value = True
            runner = CliRunner()
            result = runner.invoke(upsonic_app, ["clear", "my-session"])

        assert result.exit_code == 0
        assert "cleared" in result.output.lower() or "✓" in result.output

    def test_clear_missing_session(self):
        from typer.testing import CliRunner
        from jagabot.cli.upsonic_commands import upsonic_app

        with patch("jagabot.cli.upsonic_commands.UpsonicChatAgent") as MockClass:
            MockClass.clear_session.return_value = False
            runner = CliRunner()
            result = runner.invoke(upsonic_app, ["clear", "ghost-session"])

        assert result.exit_code == 0
        assert "not found" in result.output.lower()


# ===========================================================================
# CLI registration in commands.py
# ===========================================================================

class TestUpsonicCLIRegistration:
    def test_upsonic_app_registered_in_commands(self):
        from jagabot.cli.commands import app
        sub_names = [t.name for t in app.registered_groups]
        assert "upsonic" in sub_names


# ===========================================================================
# SwarmTab — unit tests
# ===========================================================================

class TestSwarmTabImport:
    def test_swarm_tab_importable(self):
        from jagabot.ui import swarm_tab  # noqa: F401

    def test_render_swarm_tab_callable(self):
        from jagabot.ui.swarm_tab import render_swarm_tab
        assert callable(render_swarm_tab)


class TestSwarmTabHelpers:
    def test_format_elapsed_zero(self):
        from jagabot.ui.swarm_tab import _format_elapsed
        assert _format_elapsed(0.0) == "—"

    def test_format_elapsed_seconds(self):
        from jagabot.ui.swarm_tab import _format_elapsed
        assert "s" in _format_elapsed(2.5)
        assert "2.5" in _format_elapsed(2.5)

    def test_format_elapsed_minutes(self):
        from jagabot.ui.swarm_tab import _format_elapsed
        result = _format_elapsed(90.0)
        assert "m" in result
        assert "1m" in result

    def test_state_emoji_mapping_complete(self):
        from jagabot.ui.swarm_tab import _STATE_EMOJI
        from jagabot.swarm.status import WorkerState
        for state in WorkerState:
            assert state in _STATE_EMOJI

    def test_state_color_mapping_complete(self):
        from jagabot.ui.swarm_tab import _STATE_COLOR
        from jagabot.swarm.status import WorkerState
        for state in WorkerState:
            assert state in _STATE_COLOR


class TestSwarmTabRender:
    """Test render_swarm_tab with mocked Streamlit."""

    def _mock_st(self):
        mock = MagicMock()
        mock.checkbox.return_value = False  # disable auto-refresh in tests
        mock.number_input.return_value = 10
        mock.button.return_value = False

        # Dynamically return the right number of column mocks based on the argument
        def _smart_columns(arg):
            n = arg if isinstance(arg, int) else len(arg)
            return tuple(MagicMock() for _ in range(n))

        mock.columns.side_effect = _smart_columns
        return mock

    def test_render_no_tracker_shows_info(self):
        from jagabot.ui import swarm_tab
        mock_st = self._mock_st()

        with patch.object(swarm_tab, "st", mock_st), \
             patch.object(swarm_tab, "_ST_AVAILABLE", True):
            swarm_tab.render_swarm_tab(tracker=None)

        mock_st.info.assert_called()

    def test_render_with_tracker_calls_stats(self):
        from jagabot.ui import swarm_tab
        from jagabot.swarm.status import WorkerTracker
        tracker = WorkerTracker()
        mock_st = self._mock_st()

        with patch.object(swarm_tab, "st", mock_st), \
             patch.object(swarm_tab, "_ST_AVAILABLE", True):
            swarm_tab.render_swarm_tab(tracker=tracker)

        # st.columns called at least for ctrl + stats + worker panel rows
        assert mock_st.columns.call_count >= 2

    def test_render_with_active_workers(self):
        from jagabot.ui import swarm_tab
        from jagabot.swarm.status import WorkerTracker
        tracker = WorkerTracker()
        tracker.register("task-001", "MonteCarlo", "run")

        mock_st = self._mock_st()

        with patch.object(swarm_tab, "st", mock_st), \
             patch.object(swarm_tab, "_ST_AVAILABLE", True):
            swarm_tab.render_swarm_tab(tracker=tracker)

        # ctrl + stats + panel + sub-cols per worker
        assert mock_st.columns.call_count >= 3

    def test_render_with_completed_tasks_shows_dataframe(self):
        from jagabot.ui import swarm_tab
        from jagabot.swarm.status import WorkerTracker
        tracker = WorkerTracker()
        tracker.register("t1", "VarTool", "calculate")
        tracker.mark_done("t1", success=True)

        mock_st = self._mock_st()

        with patch.object(swarm_tab, "st", mock_st), \
             patch.object(swarm_tab, "_ST_AVAILABLE", True):
            swarm_tab.render_swarm_tab(tracker=tracker)

        mock_st.dataframe.assert_called()

    def test_render_with_errored_task(self):
        from jagabot.ui import swarm_tab
        from jagabot.swarm.status import WorkerTracker
        tracker = WorkerTracker()
        tracker.register("t-err", "CVarTool", "compute")
        tracker.mark_done("t-err", success=False, error="Timeout exceeded")

        stats = tracker.stats()
        assert stats["errors"] == 1

    def test_empty_tracker_no_crash(self):
        from jagabot.ui import swarm_tab
        from jagabot.swarm.status import WorkerTracker
        tracker = WorkerTracker()
        mock_st = self._mock_st()

        with patch.object(swarm_tab, "st", mock_st), \
             patch.object(swarm_tab, "_ST_AVAILABLE", True):
            swarm_tab.render_swarm_tab(tracker=tracker)  # should not raise

    def test_not_available_returns_early(self):
        from jagabot.ui import swarm_tab
        mock_st = MagicMock()
        with patch.object(swarm_tab, "_ST_AVAILABLE", False), \
             patch.object(swarm_tab, "st", mock_st):
            swarm_tab.render_swarm_tab(tracker=None)
        mock_st.header.assert_not_called()


# ===========================================================================
# WorkerTracker integration (swarm status module)
# ===========================================================================

class TestWorkerTrackerIntegration:
    def test_register_and_mark_done(self):
        from jagabot.swarm.status import WorkerTracker
        t = WorkerTracker()
        t.register("x1", "ToolA")
        t.mark_done("x1", success=True)
        assert t.stats()["completed"] == 1

    def test_register_and_mark_error(self):
        from jagabot.swarm.status import WorkerTracker
        t = WorkerTracker()
        t.register("x2", "ToolB")
        t.mark_done("x2", success=False, error="oops")
        assert t.stats()["errors"] == 1

    def test_active_workers_during_run(self):
        from jagabot.swarm.status import WorkerTracker
        t = WorkerTracker()
        t.register("x3", "ToolC")
        active = t.active_workers()
        assert len(active) == 1
        assert active[0].tool_name == "ToolC"

    def test_recent_history_ordered_newest_first(self):
        from jagabot.swarm.status import WorkerTracker
        t = WorkerTracker()
        t.register("h1", "Tool1")
        t.mark_done("h1")
        t.register("h2", "Tool2")
        t.mark_done("h2")
        history = t.recent_history(limit=10)
        assert history[0].tool_name == "Tool2"  # newest first

    def test_stats_tools_used(self):
        from jagabot.swarm.status import WorkerTracker
        t = WorkerTracker()
        t.register("s1", "Alpha")
        t.mark_done("s1")
        t.register("s2", "Beta")
        t.mark_done("s2")
        assert "Alpha" in t.stats()["tools_used"]
        assert "Beta" in t.stats()["tools_used"]

    def test_clear_resets_all(self):
        from jagabot.swarm.status import WorkerTracker
        t = WorkerTracker()
        t.register("c1", "X")
        t.mark_done("c1")
        t.clear()
        assert t.stats()["completed"] == 0

    def test_heartbeat_keeps_worker_alive(self):
        from jagabot.swarm.status import WorkerTracker
        t = WorkerTracker()
        t.register("hb1", "ToolHB")
        t.heartbeat("hb1")
        active = t.active_workers()
        assert len(active) == 1

    def test_detect_stalled_marks_timed_out(self):
        import time
        from jagabot.swarm.status import WorkerTracker, WorkerState
        t = WorkerTracker(stall_timeout=0.01)
        t.register("stall1", "SlowTool")
        time.sleep(0.05)
        stalled = t.detect_stalled()
        assert len(stalled) == 1
        assert stalled[0].state == WorkerState.STALLED
