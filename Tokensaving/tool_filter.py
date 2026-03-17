"""
jagabot/core/tool_filter.py
────────────────────────────
Wraps the existing TOOL_RELEVANCE map from context_builder.py and exposes
a single function: get_tools_for_query(query, all_tools) → filtered list.

THE AUDIT FOUND: 93 tools × ~400 tokens = ~37,200 tokens sent on EVERY call.
context_builder.py already has a TOOL_RELEVANCE map at lines 42-77 but it
was never connected to the actual API call at loop.py:936.

This file is the bridge.

Usage
-----
    from jagabot.core.tool_filter import get_tools_for_query

    # In loop.py, replace line 936:
    # BEFORE: tools=self.tools.get_definitions()
    # AFTER:  tools=get_tools_for_query(user_input, self.tools)

Control
-------
    JAGABOT_FULL_TOOLS=1   bypass all filtering (debug mode)
    JAGABOT_MAX_TOOLS=8    cap tools per call (default: 8)
"""

from __future__ import annotations
import os
from loguru import logger

# ── Pull in the existing relevance map ───────────────────────────────────────
# context_builder.py already built this — we just need to use it
try:
    from jagabot.agent.context_builder import TOOL_RELEVANCE
    _HAS_MAP = True
    logger.debug(f"tool_filter: loaded TOOL_RELEVANCE map ({len(TOOL_RELEVANCE)} keywords)")
except ImportError:
    TOOL_RELEVANCE = {}
    _HAS_MAP = False
    logger.warning("tool_filter: TOOL_RELEVANCE not found in context_builder — falling back to ALWAYS_SEND only")

# ── Always-on tools (sent on every call, no matter what) ─────────────────────
# Keep this ≤ 3 tools — these are for basic agent orientation
ALWAYS_SEND: set[str] = {
    "memory_fleet",
    "read_file",
    "self_model_awareness",
}

# ── Config ────────────────────────────────────────────────────────────────────
_FULL_TOOLS = os.getenv("JAGABOT_FULL_TOOLS", "0") == "1"
MAX_TOOLS   = int(os.getenv("JAGABOT_MAX_TOOLS", "8"))


# ── Public API ────────────────────────────────────────────────────────────────

def get_tools_for_query(query: str, tools_registry) -> list:
    """
    Return a filtered tool definition list for the OpenAI API call.

    Parameters
    ----------
    query          : The current user message (used for keyword matching)
    tools_registry : The agent's ToolRegistry instance (has .get_definitions())

    Returns
    -------
    Filtered list of tool definition dicts for the `tools=` API parameter.
    """
    # ── Debug override ────────────────────────────────────────────────────────
    if _FULL_TOOLS:
        all_defs = tools_registry.get_definitions()
        logger.warning(f"JAGABOT_FULL_TOOLS=1 — sending all {len(all_defs)} tools (debug)")
        return all_defs

    # ── Get all definitions as name → def dict ────────────────────────────────
    raw_defs = tools_registry.get_definitions()
    all_defs: dict[str, dict] = {}
    for td in raw_defs:
        name = _extract_name(td)
        if name:
            all_defs[name] = td

    # ── Build relevant name set using TOOL_RELEVANCE map ─────────────────────
    relevant_names: set[str] = set(ALWAYS_SEND)
    query_lower = query.lower()

    if _HAS_MAP:
        for keyword, tool_names in TOOL_RELEVANCE.items():
            if keyword in query_lower:
                if isinstance(tool_names, (list, set, tuple)):
                    relevant_names.update(tool_names)
                elif isinstance(tool_names, str):
                    relevant_names.add(tool_names)
                logger.debug(f"tool_filter: '{keyword}' matched → {tool_names}")

    # ── Filter ────────────────────────────────────────────────────────────────
    filtered = [td for name, td in all_defs.items() if name in relevant_names]

    # Enforce MAX_TOOLS cap — always-send tools get priority
    if len(filtered) > MAX_TOOLS:
        always = [td for td in filtered if _extract_name(td) in ALWAYS_SEND]
        rest   = [td for td in filtered if _extract_name(td) not in ALWAYS_SEND]
        filtered = (always + rest)[:MAX_TOOLS]

    # Warn about configured tools that aren't registered
    missing = relevant_names - set(all_defs.keys())
    if missing:
        logger.debug(f"tool_filter: {len(missing)} configured tool(s) not registered: {missing}")

    logger.debug(
        f"tool_filter: {len(filtered)}/{len(all_defs)} tools "
        f"| query='{query[:50]}{'...' if len(query)>50 else ''}'"
    )
    return filtered


def _extract_name(tool_def: dict) -> str:
    """Extract the function name from an OpenAI tool definition dict."""
    try:
        return tool_def["function"]["name"]
    except (KeyError, TypeError):
        return tool_def.get("name", "")
