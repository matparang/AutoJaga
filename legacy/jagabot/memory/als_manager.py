"""
ALS Manager — Agent identity state in ALS.json.
Handles current_focus, evolution_stage, recent_reflections.

Extracted from nanobot/soul/als_manager.py for jagabot v3.0.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

_MAX_REFLECTIONS = 20
_DEFAULT_STATE: dict[str, Any] = {
    "current_focus": "",
    "evolution_stage": 1,
    "recent_reflections": [],
    "last_updated": "",
}


class ALSManager:
    """
    Manages ALS.json — the agent's identity/focus layer.
    """

    def __init__(self, memory_dir: Path):
        self.als_path = memory_dir / "ALS.json"
        memory_dir.mkdir(parents=True, exist_ok=True)
        self._state = self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_focus(self, focus: str) -> None:
        """Set the agent's current focus/topic."""
        self._state["current_focus"] = focus
        self._state["last_updated"] = _now()
        self._save()

    def add_reflection(self, reflection: str) -> None:
        """Append a short reflection. Trims to MAX_REFLECTIONS."""
        reflections: list[str] = self._state.setdefault("recent_reflections", [])
        reflections.append(f"[{_now()}] {reflection}")
        if len(reflections) > _MAX_REFLECTIONS:
            self._state["recent_reflections"] = reflections[-_MAX_REFLECTIONS:]
        self._state["last_updated"] = _now()
        self._save()

    def set_stage(self, stage: int) -> None:
        """Update evolution stage."""
        if self._state.get("evolution_stage") != stage:
            self._state["evolution_stage"] = stage
            self._state["last_updated"] = _now()
            self._save()
            logger.info("ALS: identity stage updated to {}", stage)

    def get_topic_importance(self, topic: str) -> float | None:
        """Return user-importance score for *topic* (0–1), or None if unknown."""
        return None

    def get_identity_context(self) -> str:
        """Return a short identity context string for prompt injection."""
        focus = self._state.get("current_focus", "")
        stage = self._state.get("evolution_stage", 1)
        reflections = self._state.get("recent_reflections", [])

        lines = [f"## Agent Identity (Stage {stage})"]
        if focus:
            lines.append(f"Current focus: {focus}")
        if reflections:
            lines.append("Recent reflections:")
            for r in reflections[-5:]:
                lines.append(f"  - {r}")
        return "\n".join(lines)

    @property
    def stage(self) -> int:
        return self._state.get("evolution_stage", 1)

    @property
    def focus(self) -> str:
        return self._state.get("current_focus", "")

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        if self.als_path.exists():
            try:
                with open(self.als_path, encoding="utf-8") as f:
                    data = json.load(f)
                for k, v in _DEFAULT_STATE.items():
                    data.setdefault(k, v)
                return data
            except Exception as exc:
                logger.warning("ALSManager: failed to load {}, resetting: {}", self.als_path, exc)
        return dict(_DEFAULT_STATE)

    def _save(self) -> None:
        with open(self.als_path, "w", encoding="utf-8") as f:
            json.dump(self._state, f, indent=2, ensure_ascii=False)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")
