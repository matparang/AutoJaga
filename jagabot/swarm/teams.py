"""Teammate manager — spawn named agent threads with inbox polling.

Adapted from learn-claude-code s09.  Each teammate runs as a daemon thread
that polls its Mailbox inbox, processes messages, and idles between rounds.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger

from jagabot.swarm.mailbox import Mailbox


class TeammateManager:
    """Manages spawned teammate threads with configuration persistence."""

    def __init__(self, team_dir: Path, mailbox: Mailbox) -> None:
        self.dir = team_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.mailbox = mailbox
        self._threads: dict[str, threading.Thread] = {}
        self._running: dict[str, bool] = {}
        self._lock = threading.Lock()

    def _config_path(self) -> Path:
        return self.dir / "config.json"

    def _load_config(self) -> dict[str, Any]:
        cp = self._config_path()
        if cp.exists():
            return json.loads(cp.read_text(encoding="utf-8"))
        return {"teammates": {}}

    def _save_config(self, config: dict[str, Any]) -> None:
        self._config_path().write_text(json.dumps(config, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Spawn & lifecycle
    # ------------------------------------------------------------------

    def spawn(
        self,
        name: str,
        role: str,
        prompt: str = "",
        handler: Optional[Callable[[str, dict[str, Any]], None]] = None,
    ) -> str:
        """Spawn a named teammate.  Returns confirmation string."""
        with self._lock:
            if name in self._threads and self._threads[name].is_alive():
                return f"[{name}] already running"

            config = self._load_config()
            config["teammates"][name] = {
                "role": role,
                "prompt": prompt,
                "spawned_at": time.time(),
            }
            self._save_config(config)

            self._running[name] = True
            t = threading.Thread(
                target=self._teammate_loop,
                args=(name, role, prompt, handler),
                daemon=True,
                name=f"teammate-{name}",
            )
            self._threads[name] = t
            t.start()
        return f"[{name}] spawned as {role}"

    def stop(self, name: str) -> str:
        """Signal a teammate to stop."""
        with self._lock:
            self._running[name] = False
        return f"[{name}] stop signal sent"

    def stop_all(self) -> None:
        """Stop all teammates."""
        with self._lock:
            for name in list(self._running):
                self._running[name] = False

    def list_all(self) -> str:
        """Human-readable list of teammates and status."""
        config = self._load_config()
        if not config.get("teammates"):
            return "No teammates."
        lines = []
        for name, info in config["teammates"].items():
            alive = name in self._threads and self._threads[name].is_alive()
            status = "🟢 running" if alive else "⚪ stopped"
            lines.append(f"  {name} ({info['role']}) — {status}")
        return "\n".join(lines)

    def member_names(self) -> list[str]:
        """Return list of teammate names."""
        config = self._load_config()
        return list(config.get("teammates", {}).keys())

    def is_alive(self, name: str) -> bool:
        """Check if a teammate's thread is alive."""
        return name in self._threads and self._threads[name].is_alive()

    # ------------------------------------------------------------------
    # Thread target
    # ------------------------------------------------------------------

    def _teammate_loop(
        self,
        name: str,
        role: str,
        prompt: str,
        handler: Optional[Callable[[str, dict[str, Any]], None]] = None,
    ) -> None:
        """Main loop for a teammate thread.  Polls inbox and processes."""
        logger.info(f"Teammate [{name}] started as {role}")
        idle_count = 0
        max_idle = 120  # 2 min idle before auto-stop

        while self._running.get(name, False):
            messages = self.mailbox.read_inbox(name)

            if messages:
                idle_count = 0
                for msg in messages:
                    logger.debug(f"[{name}] processing msg from {msg.get('from')}: {msg.get('type')}")
                    if handler:
                        try:
                            handler(name, msg)
                        except Exception as exc:
                            logger.error(f"[{name}] handler error: {exc}")
                    # Check for shutdown request
                    if msg.get("type") == "shutdown_request":
                        logger.info(f"[{name}] received shutdown request")
                        self.mailbox.send(
                            sender=name,
                            to=msg["from"],
                            content="acknowledged",
                            msg_type="shutdown_response",
                            meta={"request_id": msg.get("meta", {}).get("request_id")},
                        )
                        self._running[name] = False
                        break
            else:
                idle_count += 1
                if idle_count > max_idle:
                    logger.info(f"[{name}] idle timeout — stopping")
                    break

            time.sleep(1)

        logger.info(f"Teammate [{name}] stopped")
