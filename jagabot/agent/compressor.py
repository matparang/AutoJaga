"""Context compressor — token-aware message compression for long sessions.

Three-layer compression pipeline adapted from learn-claude-code s06:

Layer 1 (micro_compact): Replace old tool_result content with short placeholders.
         Runs every turn, cheap O(n).
Layer 2 (auto trigger):  When estimated tokens exceed threshold, trigger
         the existing AgentLoop._consolidate_memory().
Layer 3 (transcript):    Archive full message history to JSONL before compression.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------

def estimate_tokens(messages: list[dict[str, Any]]) -> int:
    """Rough token count: ~4 characters per token.

    Uses ``str(messages)`` which captures keys, values, and structure.
    Accurate enough for threshold decisions (within ~20% of tiktoken).
    """
    return len(str(messages)) // 4


# ---------------------------------------------------------------------------
# Layer 1: Micro-compact — replace old tool_result content
# ---------------------------------------------------------------------------

def micro_compact(
    messages: list[dict[str, Any]],
    keep_recent: int = 3,
) -> list[dict[str, Any]]:
    """Replace old tool_result content with short placeholders.

    Scans *assistant* messages for ``tool_calls`` entries and *tool* role
    messages for their results.  Keeps the most recent ``keep_recent``
    tool results intact; older ones are shrunk to
    ``"[Previous: used {tool_name}]"``.

    Works with the OpenAI/LiteLLM message format used by jagabot:
    - assistant: ``{"tool_calls": [{"id": ..., "function": {"name": ..., "arguments": ...}}]}``
    - tool:      ``{"role": "tool", "tool_call_id": ..., "content": "..."}``

    Also supports Anthropic-style messages (list content with type=tool_result).

    Mutates messages in-place and returns the same list.
    """
    # Build tool_name map: tool_call_id → function name
    tool_name_map: dict[str, str] = {}
    tool_result_indices: list[int] = []

    for idx, msg in enumerate(messages):
        role = msg.get("role", "")

        # OpenAI-style assistant tool_calls
        if role == "assistant":
            for tc in msg.get("tool_calls", []):
                fn = tc.get("function", {})
                tc_id = tc.get("id", "")
                if tc_id and fn.get("name"):
                    tool_name_map[tc_id] = fn["name"]

            # Anthropic-style content blocks
            content = msg.get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_name_map[block.get("id", "")] = block.get("name", "unknown")
                    elif hasattr(block, "type") and getattr(block, "type", None) == "tool_use":
                        tool_name_map[getattr(block, "id", ""), ] = getattr(block, "name", "unknown")

        # OpenAI-style tool results
        if role == "tool":
            tool_result_indices.append(idx)

        # Anthropic-style user messages with tool_result parts
        if role == "user" and isinstance(msg.get("content"), list):
            for part in msg["content"]:
                if isinstance(part, dict) and part.get("type") == "tool_result":
                    tool_result_indices.append(idx)
                    break  # one entry per message index

    if len(tool_result_indices) <= keep_recent:
        return messages

    # Only shrink older results (keep last keep_recent intact)
    to_shrink = tool_result_indices[:-keep_recent]

    for idx in to_shrink:
        msg = messages[idx]

        # OpenAI-style tool message
        if msg.get("role") == "tool":
            content = msg.get("content", "")
            if isinstance(content, str) and len(content) > 100:
                tc_id = msg.get("tool_call_id", "")
                name = tool_name_map.get(tc_id, "unknown")
                msg["content"] = f"[Previous: used {name}]"

        # Anthropic-style user message with tool_result parts
        elif msg.get("role") == "user" and isinstance(msg.get("content"), list):
            for part in msg["content"]:
                if isinstance(part, dict) and part.get("type") == "tool_result":
                    content = part.get("content", "")
                    if isinstance(content, str) and len(content) > 100:
                        tc_id = part.get("tool_use_id", "")
                        name = tool_name_map.get(tc_id, "unknown")
                        part["content"] = f"[Previous: used {name}]"

    return messages


# ---------------------------------------------------------------------------
# Transcript archival
# ---------------------------------------------------------------------------

def save_transcript(
    messages: list[dict[str, Any]],
    transcripts_dir: Path,
) -> Path:
    """Save full message history to a timestamped JSONL file.

    Returns the path to the saved transcript.
    """
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    path = transcripts_dir / f"transcript_{ts}.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for msg in messages:
            f.write(json.dumps(msg, default=str) + "\n")
    return path


# ---------------------------------------------------------------------------
# Auto-compact threshold check
# ---------------------------------------------------------------------------

DEFAULT_TOKEN_THRESHOLD = 40_000


def should_auto_compact(
    messages: list[dict[str, Any]],
    threshold: int = DEFAULT_TOKEN_THRESHOLD,
) -> bool:
    """Return True if estimated token count exceeds the threshold."""
    return estimate_tokens(messages) > threshold
