"""
jagabot/core/tool_filter.py
─────────────────────────────
Wraps the existing TOOL_RELEVANCE map from context_builder.py and exposes
a single function: get_tools_for_query(query, all_tools) → filtered list.

This fixes loop.py:936 where ALL 93 tools are sent on every call.
"""

from __future__ import annotations
import os
from loguru import logger

# Pull in the existing relevance map from context_builder
# (it was built but never connected to the API call)
try:
    from jagabot.agent.context_builder import TOOL_RELEVANCE
    _HAS_RELEVANCE_MAP = True
except ImportError:
    TOOL_RELEVANCE = {}
    _HAS_RELEVANCE_MAP = False
    logger.warning("tool_filter: TOOL_RELEVANCE not found in context_builder — sending all tools")

# ── Always-on tools (sent regardless of topic) ─────────────────────
# Keep this list ≤ 3. These are tools the agent needs for basic orientation.
ALWAYS_SEND: set[str] = {
    "yahoo_finance",
    "web_search_mcp",
    "memory_fleet",
    "read_file",
    "self_model_awareness",
}

# ── Debug override ─────────────────────────────────────────────────
# Set JAGABOT_FULL_TOOLS=1 to bypass filtering (useful when debugging tool issues)
_FULL_TOOLS = os.getenv("JAGABOT_FULL_TOOLS", "0") == "1"

# ── Max tools to send per call ────────────────────────────────────
MAX_TOOLS = int(os.getenv("JAGABOT_MAX_TOOLS", "8"))


def get_tools_for_query(query: str, all_tools) -> list:
    """
    Return a filtered list of tool definitions for this query.

    Priority:
    1. JAGABOT_FULL_TOOLS=1  → send everything (debug)
    2. TOOL_RELEVANCE map    → send relevant tools + always-on
    3. Fallback              → send only ALWAYS_SEND tools
    """
    if _FULL_TOOLS:
        logger.warning(f"JAGABOT_FULL_TOOLS=1 — sending all tools")
        if hasattr(all_tools, 'get_definitions'):
            return all_tools.get_definitions()
        elif isinstance(all_tools, dict):
            return list(all_tools.values())
        else:
            return list(all_tools)

    # Determine relevant tool names from the existing TOOL_RELEVANCE map
    relevant_names: set[str] = set(ALWAYS_SEND)

    if _HAS_RELEVANCE_MAP and TOOL_RELEVANCE:
        query_lower = query.lower()
        for keyword, tool_names in TOOL_RELEVANCE.items():
            if keyword in query_lower:
                relevant_names.update(tool_names)
                logger.debug(f"tool_filter: keyword='{keyword}' matched → adding {tool_names}")

    # Get definitions — handle both dict and ToolRegistry
    if hasattr(all_tools, 'get_definitions'):
        all_defs = {t['function']['name']: t for t in all_tools.get_definitions()}
    elif isinstance(all_tools, dict):
        all_defs = all_tools
    else:
        logger.warning("tool_filter: unrecognised tools type — sending all")
        if hasattr(all_tools, 'get_definitions'):
            return all_tools.get_definitions()
        elif isinstance(all_tools, dict):
            return list(all_tools.values())
        else:
            return list(all_tools)

    # Filter to relevant names
    filtered = [
        tool_def for name, tool_def in all_defs.items()
        if name in relevant_names
    ]

    # Cap at MAX_TOOLS
    if len(filtered) > MAX_TOOLS:
        # Prioritise always-send, then take up to MAX_TOOLS
        always = [t for t in filtered if _tool_name(t) in ALWAYS_SEND]
        rest   = [t for t in filtered if _tool_name(t) not in ALWAYS_SEND]
        filtered = (always + rest)[:MAX_TOOLS]

    query_preview = query[:60] + '...' if len(query) > 60 else query
    logger.debug(
        f"tool_filter: {len(filtered)}/{len(all_defs)} tools selected "
        f"for query='{query_preview}'"
    )

    # Warn if relevant_names referenced tools not registered
    registered = set(all_defs.keys())
    missing = relevant_names - registered
    if missing:
        logger.debug(f"tool_filter: {len(missing)} configured tools not registered: {missing}")

    return filtered


def _tool_name(tool_def: dict) -> str:
    """Extract name from an OpenAI function-calling tool definition."""
    try:
        return tool_def['function']['name']
    except (KeyError, TypeError):
        return tool_def.get('name', '')
