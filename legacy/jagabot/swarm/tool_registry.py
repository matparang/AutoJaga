"""Swarm tool registry — maps tool names to their classes for worker instantiation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jagabot.agent.tools.base import Tool

_TOOL_MAP: dict[str, type] = {}


def _ensure_loaded() -> None:
    """Lazily populate the tool map from the canonical ALL_TOOLS list."""
    if _TOOL_MAP:
        return
    from jagabot.guardian.tools import ALL_TOOLS

    for cls in ALL_TOOLS:
        instance = cls()
        _TOOL_MAP[instance.name] = cls


def get_tool_class(name: str) -> type | None:
    """Return the Tool class for the given tool name, or None."""
    _ensure_loaded()
    return _TOOL_MAP.get(name)


def get_all_tool_names() -> list[str]:
    """Return sorted list of all registered swarm tool names."""
    _ensure_loaded()
    return sorted(_TOOL_MAP.keys())


def get_tool_count() -> int:
    """Return total number of available tools."""
    _ensure_loaded()
    return len(_TOOL_MAP)
