"""Tests for jagabot.swarm.mailbox — JSONL append-only inbox."""
import json
import tempfile
import threading
from pathlib import Path

import pytest

from jagabot.swarm.mailbox import Mailbox, MESSAGE_TYPES


@pytest.fixture
def mb(tmp_path):
    return Mailbox(tmp_path / "inboxes")


# ── Send ─────────────────────────────────────────────────────────────

class TestSend:
    def test_send_basic(self, mb):
        msg_id = mb.send("alice", "bob", "hello")
        assert isinstance(msg_id, str)
        assert len(msg_id) == 12

    def test_send_creates_file(self, mb):
        mb.send("alice", "bob", "hello")
        inbox = mb._inbox_path("bob")
        assert inbox.exists()

    def test_send_jsonl_format(self, mb):
        mb.send("alice", "bob", "hello")
        inbox = mb._inbox_path("bob")
        line = inbox.read_text().strip()
        data = json.loads(line)
        assert data["from"] == "alice"
        assert data["to"] == "bob"
        assert data["content"] == "hello"

    def test_send_custom_type(self, mb):
        mb.send("alice", "bob", "test", msg_type="shutdown_request")
        msgs = mb.read_inbox("bob")
        assert msgs[0]["type"] == "shutdown_request"

    def test_send_invalid_type(self, mb):
        with pytest.raises(ValueError, match="Invalid msg_type"):
            mb.send("alice", "bob", "test", msg_type="invalid")

    def test_send_with_meta(self, mb):
        mb.send("alice", "bob", "hello", meta={"key": "value"})
        msgs = mb.read_inbox("bob")
        assert msgs[0]["meta"]["key"] == "value"

    def test_send_multiple(self, mb):
        mb.send("alice", "bob", "msg1")
        mb.send("charlie", "bob", "msg2")
        msgs = mb.read_inbox("bob")
        assert len(msgs) == 2

    def test_send_has_timestamp(self, mb):
        mb.send("alice", "bob", "hello")
        msgs = mb.read_inbox("bob")
        assert "timestamp" in msgs[0]
        assert isinstance(msgs[0]["timestamp"], float)

    def test_send_has_id(self, mb):
        mb.send("alice", "bob", "hello")
        msgs = mb.read_inbox("bob")
        assert "id" in msgs[0]


# ── Read Inbox ───────────────────────────────────────────────────────

class TestReadInbox:
    def test_read_empty(self, mb):
        assert mb.read_inbox("nobody") == []

    def test_read_drains(self, mb):
        mb.send("alice", "bob", "hello")
        msgs1 = mb.read_inbox("bob")
        msgs2 = mb.read_inbox("bob")
        assert len(msgs1) == 1
        assert len(msgs2) == 0

    def test_read_all_messages(self, mb):
        for i in range(5):
            mb.send("alice", "bob", f"msg {i}")
        msgs = mb.read_inbox("bob")
        assert len(msgs) == 5

    def test_read_preserves_order(self, mb):
        mb.send("alice", "bob", "first")
        mb.send("alice", "bob", "second")
        msgs = mb.read_inbox("bob")
        assert msgs[0]["content"] == "first"
        assert msgs[1]["content"] == "second"


# ── Peek Inbox ───────────────────────────────────────────────────────

class TestPeekInbox:
    def test_peek_empty(self, mb):
        assert mb.peek_inbox("nobody") == []

    def test_peek_does_not_drain(self, mb):
        mb.send("alice", "bob", "hello")
        msgs1 = mb.peek_inbox("bob")
        msgs2 = mb.peek_inbox("bob")
        assert len(msgs1) == 1
        assert len(msgs2) == 1


# ── Broadcast ────────────────────────────────────────────────────────

class TestBroadcast:
    def test_broadcast_basic(self, mb):
        bid = mb.broadcast("alice", "hi team", ["bob", "charlie"])
        assert isinstance(bid, str)
        assert len(bid) == 12

    def test_broadcast_delivers_to_all(self, mb):
        mb.broadcast("alice", "hi team", ["bob", "charlie"])
        assert len(mb.read_inbox("bob")) == 1
        assert len(mb.read_inbox("charlie")) == 1

    def test_broadcast_skips_sender(self, mb):
        mb.broadcast("alice", "hi team", ["alice", "bob"])
        assert len(mb.read_inbox("alice")) == 0
        assert len(mb.read_inbox("bob")) == 1

    def test_broadcast_includes_broadcast_id(self, mb):
        bid = mb.broadcast("alice", "hi", ["bob"])
        msgs = mb.read_inbox("bob")
        assert msgs[0]["meta"]["broadcast_id"] == bid


# ── Inbox Count ──────────────────────────────────────────────────────

class TestInboxCount:
    def test_count_empty(self, mb):
        assert mb.inbox_count("nobody") == 0

    def test_count_messages(self, mb):
        mb.send("a", "bob", "1")
        mb.send("a", "bob", "2")
        assert mb.inbox_count("bob") == 2


# ── Message Types ────────────────────────────────────────────────────

class TestMessageTypes:
    @pytest.mark.parametrize("msg_type", MESSAGE_TYPES)
    def test_valid_types(self, mb, msg_type):
        msg_id = mb.send("alice", "bob", "test", msg_type=msg_type)
        assert isinstance(msg_id, str)


# ── Thread Safety ────────────────────────────────────────────────────

class TestThreadSafety:
    def test_concurrent_sends(self, mb):
        """Multiple threads writing to the same inbox concurrently."""
        errors = []

        def sender(i):
            try:
                mb.send("sender", "target", f"msg {i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=sender, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        msgs = mb.read_inbox("target")
        assert len(msgs) == 20
