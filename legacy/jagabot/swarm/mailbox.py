"""JSONL-based mailbox for multi-agent communication.

Adapted from learn-claude-code s09.  Each agent has an inbox file
(``{inbox_dir}/{agent_name}.jsonl``) that other agents append messages to.
Reading drains the file atomically (rename → read → delete).
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional


MESSAGE_TYPES = (
    "message",
    "broadcast",
    "shutdown_request",
    "shutdown_response",
    "plan_approval",
    "plan_response",
)


class Mailbox:
    """Append-only, drain-on-read JSONL inbox per agent."""

    def __init__(self, inbox_dir: Path) -> None:
        self.dir = inbox_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _inbox_path(self, name: str) -> Path:
        return self.dir / f"{name}.jsonl"

    def send(
        self,
        sender: str,
        to: str,
        content: str,
        msg_type: str = "message",
        meta: Optional[dict[str, Any]] = None,
    ) -> str:
        """Append a message to *to*'s inbox.  Returns the message ID."""
        if msg_type not in MESSAGE_TYPES:
            raise ValueError(f"Invalid msg_type {msg_type!r}; valid: {MESSAGE_TYPES}")
        msg_id = uuid.uuid4().hex[:12]
        envelope: dict[str, Any] = {
            "id": msg_id,
            "from": sender,
            "to": to,
            "type": msg_type,
            "content": content,
            "timestamp": time.time(),
        }
        if meta:
            envelope["meta"] = meta
        line = json.dumps(envelope) + "\n"
        with self._lock:
            with open(self._inbox_path(to), "a", encoding="utf-8") as f:
                f.write(line)
        return msg_id

    def read_inbox(self, name: str) -> list[dict[str, Any]]:
        """Read **and drain** all messages from *name*'s inbox.

        Atomically renames the file to a temp name so concurrent writers
        append to a fresh file.
        """
        inbox = self._inbox_path(name)
        if not inbox.exists():
            return []
        tmp = inbox.with_suffix(".draining")
        with self._lock:
            if not inbox.exists():
                return []
            os.replace(str(inbox), str(tmp))
        messages: list[dict[str, Any]] = []
        with open(tmp, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        messages.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        tmp.unlink(missing_ok=True)
        return messages

    def peek_inbox(self, name: str) -> list[dict[str, Any]]:
        """Read messages WITHOUT draining."""
        inbox = self._inbox_path(name)
        if not inbox.exists():
            return []
        messages: list[dict[str, Any]] = []
        with open(inbox, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        messages.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return messages

    def broadcast(
        self,
        sender: str,
        content: str,
        teammates: list[str],
        msg_type: str = "broadcast",
    ) -> str:
        """Send the same message to all *teammates*.  Returns a single broadcast ID."""
        broadcast_id = uuid.uuid4().hex[:12]
        for name in teammates:
            if name != sender:
                self.send(
                    sender=sender,
                    to=name,
                    content=content,
                    msg_type=msg_type,
                    meta={"broadcast_id": broadcast_id},
                )
        return broadcast_id

    def inbox_count(self, name: str) -> int:
        """Count messages in an inbox without draining."""
        return len(self.peek_inbox(name))
