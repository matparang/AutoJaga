# jagabot/core/repetition_guard.py
"""
RepetitionGuard — Prevents agent from calling the same
tool with the same arguments multiple times per session.

Fixes the "reads SKILL.md 3 times" bug.
Fixes the "runs exec on same file repeatedly" bug.

Wire into loop.py __init__:
    from jagabot.core.repetition_guard import RepetitionGuard
    self.rep_guard = RepetitionGuard()

Wire into loop.py _run_agent_loop BEFORE executing tool call:
    # Before executing tool:
    if self.rep_guard.is_repeat(tool_name, tool_args):
        cached = self.rep_guard.get_cached(tool_name, tool_args)
        logger.debug(f"RepetitionGuard: skipping repeat {tool_name}")
        # Return cached result instead of re-executing
        return cached
    
    # Execute tool normally
    result = await tool.execute(tool_args)
    
    # Cache the result
    self.rep_guard.record(tool_name, tool_args, result)

Wire into loop.py _process_message START:
    # Reset guard at start of each new USER message
    # (but NOT between tool calls within one response)
    self.rep_guard.reset_for_new_turn()
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from loguru import logger


@dataclass
class ToolCall:
    """Record of a tool call made this session."""
    tool_name:  str
    args_hash:  str
    args:       dict
    result:     str
    timestamp:  str
    call_count: int = 1


class RepetitionGuard:
    """
    Tracks tool calls within a session.
    Prevents identical repeated calls.
    
    Two modes:
    - BLOCK:  return cached result for identical calls
    - WARN:   log warning but allow the call
    
    read_file on .md files → BLOCK (never useful to re-read)
    exec with same command → BLOCK (same code = same result)
    web_search same query  → BLOCK (results won't change)
    write_file             → ALLOW (writing same content is OK)
    memory tools           → ALLOW (state may have changed)
    """

    # Tools that should never repeat with same args
    BLOCK_ON_REPEAT = {
        "read_file",
        "exec",
        "web_search",
        "web_fetch",
        "list_dir",
    }

    # Tools that are always allowed to repeat
    ALLOW_REPEAT = {
        "write_file",
        "edit_file",
        "memory_fleet",
        "k1_bayesian",
        "k3_perspective",
        "meta_learning",
    }

    def __init__(self) -> None:
        self._session_calls: dict[str, ToolCall] = {}
        self._turn_calls:    dict[str, ToolCall] = {}

    def is_repeat(
        self,
        tool_name: str,
        tool_args: dict,
    ) -> bool:
        """
        Check if this exact tool call has already been made
        in this session.
        Returns True if it should be blocked/cached.
        """
        if tool_name in self.ALLOW_REPEAT:
            return False

        if tool_name not in self.BLOCK_ON_REPEAT:
            return False

        key = self._make_key(tool_name, tool_args)
        if key in self._session_calls:
            call = self._session_calls[key]
            logger.debug(
                f"RepetitionGuard: {tool_name} already called "
                f"{call.call_count}x this session with same args"
            )
            return True

        return False

    def get_cached(
        self,
        tool_name: str,
        tool_args: dict,
    ) -> Optional[str]:
        """Return cached result for a repeated tool call."""
        key = self._make_key(tool_name, tool_args)
        call = self._session_calls.get(key)
        if call:
            call.call_count += 1
            return call.result
        return None

    def record(
        self,
        tool_name: str,
        tool_args: dict,
        result:    str,
    ) -> None:
        """Record a tool call result for future cache hits."""
        key = self._make_key(tool_name, tool_args)
        self._session_calls[key] = ToolCall(
            tool_name  = tool_name,
            args_hash  = key,
            args       = tool_args,
            result     = result,
            timestamp  = datetime.now().isoformat(),
        )
        self._turn_calls[key] = self._session_calls[key]

    def reset_for_new_turn(self) -> None:
        """
        Reset turn-level tracking at start of each user message.
        Session-level cache persists across turns.
        """
        self._turn_calls = {}

    def reset_session(self) -> None:
        """Full reset — use when starting a new session."""
        self._session_calls = {}
        self._turn_calls    = {}

    def get_stats(self) -> dict:
        """Return repetition stats for debugging."""
        total_calls  = sum(
            c.call_count for c in self._session_calls.values()
        )
        unique_calls = len(self._session_calls)
        blocked      = total_calls - unique_calls

        return {
            "total_calls":  total_calls,
            "unique_calls": unique_calls,
            "blocked_repeats": blocked,
            "tools_called": list({
                c.tool_name
                for c in self._session_calls.values()
            }),
        }

    @staticmethod
    def _make_key(tool_name: str, tool_args: dict) -> str:
        """Create a stable hash key for tool + args combo."""
        try:
            args_str = json.dumps(tool_args, sort_keys=True)
        except Exception:
            args_str = str(tool_args)
        raw = f"{tool_name}:{args_str}"
        return hashlib.md5(raw.encode()).hexdigest()


# ── Synthesis injector ──────────────────────────────────────────────
# When a cached read_file result is returned,
# inject a hint to synthesise rather than show raw content

SYNTHESIS_PROMPT = """
You have already read this file. The user wants an explanation.
DO NOT show the file content again.
DO NOT call read_file again.
Synthesise what you read into a plain-language explanation.
Answer the user's question directly using what you already know.
"""


def inject_synthesis_hint(
    user_message: str,
    cached_tool:  str,
) -> str:
    """
    When RepetitionGuard blocks a re-read,
    inject synthesis hint into the user message context.
    """
    explain_triggers = [
        "explain", "in words", "what does", "tell me",
        "describe", "what is", "how does", "mean",
        "plain language", "simply", "summary",
    ]

    msg_lower = user_message.lower()
    if any(t in msg_lower for t in explain_triggers):
        return SYNTHESIS_PROMPT

    return ""
