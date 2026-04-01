"""Tests for jagabot.swarm.teams — TeammateManager with inbox polling."""
import json
import tempfile
import time
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from jagabot.swarm.mailbox import Mailbox
from jagabot.swarm.teams import TeammateManager


@pytest.fixture
def env(tmp_path):
    mb = Mailbox(tmp_path / "inboxes")
    tm = TeammateManager(tmp_path / "team", mb)
    return tm, mb


# ── Spawn ────────────────────────────────────────────────────────────

class TestSpawn:
    def test_spawn_basic(self, env):
        tm, mb = env
        result = tm.spawn("alice", "analyst")
        assert "alice" in result
        assert "spawned" in result

    def test_spawn_creates_config(self, env):
        tm, mb = env
        tm.spawn("alice", "analyst")
        cfg = json.loads(tm._config_path().read_text())
        assert "alice" in cfg["teammates"]
        assert cfg["teammates"]["alice"]["role"] == "analyst"

    def test_spawn_duplicate(self, env):
        tm, mb = env
        tm.spawn("alice", "analyst")
        time.sleep(0.1)
        result = tm.spawn("alice", "analyst")
        assert "already running" in result

    def test_spawn_thread_alive(self, env):
        tm, mb = env
        tm.spawn("alice", "analyst")
        time.sleep(0.1)
        assert tm.is_alive("alice")
        tm.stop("alice")

    def test_spawn_with_handler(self, env):
        tm, mb = env
        handler = MagicMock()
        tm.spawn("alice", "analyst", handler=handler)
        time.sleep(0.3)
        mb.send("bob", "alice", "hi")
        time.sleep(2.0)
        handler.assert_called()
        tm.stop("alice")


# ── Stop ─────────────────────────────────────────────────────────────

class TestStop:
    def test_stop_basic(self, env):
        tm, mb = env
        tm.spawn("alice", "analyst")
        time.sleep(0.1)
        result = tm.stop("alice")
        assert "stop" in result
        time.sleep(1.5)
        assert not tm.is_alive("alice")

    def test_stop_all(self, env):
        tm, mb = env
        tm.spawn("alice", "analyst")
        tm.spawn("bob", "trader")
        time.sleep(0.1)
        tm.stop_all()
        time.sleep(1.5)
        assert not tm.is_alive("alice")
        assert not tm.is_alive("bob")


# ── List / Members ───────────────────────────────────────────────────

class TestList:
    def test_list_empty(self, env):
        tm, mb = env
        result = tm.list_all()
        assert "No teammates" in result

    def test_list_all(self, env):
        tm, mb = env
        tm.spawn("alice", "analyst")
        time.sleep(0.1)
        result = tm.list_all()
        assert "alice" in result
        assert "analyst" in result
        tm.stop("alice")

    def test_member_names(self, env):
        tm, mb = env
        tm.spawn("alice", "analyst")
        tm.spawn("bob", "trader")
        time.sleep(0.1)
        names = tm.member_names()
        assert "alice" in names
        assert "bob" in names
        tm.stop_all()

    def test_member_names_empty(self, env):
        tm, mb = env
        assert tm.member_names() == []


# ── Message handling ─────────────────────────────────────────────────

class TestMessageHandling:
    def test_shutdown_request(self, env):
        tm, mb = env
        tm.spawn("alice", "analyst")
        time.sleep(0.2)
        mb.send("boss", "alice", "shutdown_request", msg_type="shutdown_request",
                meta={"request_id": "req1"})
        time.sleep(2.0)
        assert not tm.is_alive("alice")

    def test_messages_processed(self, env):
        tm, mb = env
        received = []

        def handler(name, msg):
            received.append(msg)

        tm.spawn("alice", "analyst", handler=handler)
        time.sleep(0.2)
        mb.send("bob", "alice", "task1")
        mb.send("charlie", "alice", "task2")
        time.sleep(2.0)
        assert len(received) >= 2
        tm.stop("alice")


# ── Config persistence ───────────────────────────────────────────────

class TestConfig:
    def test_config_persists(self, env):
        tm, mb = env
        tm.spawn("alice", "analyst")
        time.sleep(0.1)
        cfg = tm._load_config()
        assert "alice" in cfg["teammates"]
        tm.stop("alice")

    def test_config_multiple_teammates(self, env):
        tm, mb = env
        tm.spawn("alice", "analyst")
        tm.spawn("bob", "trader")
        time.sleep(0.1)
        cfg = tm._load_config()
        assert len(cfg["teammates"]) == 2
        tm.stop_all()

    def test_config_has_spawned_at(self, env):
        tm, mb = env
        tm.spawn("alice", "analyst")
        time.sleep(0.1)
        cfg = tm._load_config()
        assert "spawned_at" in cfg["teammates"]["alice"]
        tm.stop("alice")
