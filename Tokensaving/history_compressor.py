"""
jagabot/core/history_compressor.py
────────────────────────────────────
Compresses old conversation turns into a summary block.

AUDIT FINDING: History grows unbounded. After 50 turns:
  100 messages × ~200 tokens = ~20,000 tokens sent on every call.

Usage
-----
    from jagabot.core.history_compressor import compress_history

    # In _run_agent_loop(), BEFORE the await self.provider.chat(...) call:
    messages = await compress_history(messages)
    # (remove 'await' if your loop is synchronous)

Config
------
    JAGABOT_HISTORY_COMPRESS=0    disable compression
    JAGABOT_COMPRESS_AFTER=6      turns before compression fires (default 6)
    JAGABOT_KEEP_RECENT=3         raw turns to always keep (default 3)
    JAGABOT_COMPRESS_MODEL=gpt-4o-mini
"""

from __future__ import annotations
import os
from loguru import logger

_ENABLED       = os.getenv("JAGABOT_HISTORY_COMPRESS", "1") == "1"
COMPRESS_AFTER = int(os.getenv("JAGABOT_COMPRESS_AFTER", "6"))
KEEP_RECENT    = int(os.getenv("JAGABOT_KEEP_RECENT", "3"))
COMPRESS_MODEL = os.getenv("JAGABOT_COMPRESS_MODEL", "gpt-4o-mini")

_client = None

def _get_client():
    global _client
    if _client is None:
        # Try async first, fall back to sync
        try:
            from openai import AsyncOpenAI
            _client = AsyncOpenAI()
        except Exception:
            from openai import OpenAI
            _client = OpenAI()
    return _client


async def compress_history(messages: list[dict]) -> list[dict]:
    """
    Async version — use if _run_agent_loop is async (which the audit confirms it is).
    Compresses old turns, keeps recent turns raw, preserves system messages.
    """
    if not _ENABLED:
        return messages

    system_msgs  = [m for m in messages if m.get("role") == "system"]
    non_sys      = [m for m in messages if m.get("role") != "system"]
    threshold    = COMPRESS_AFTER * 2  # user + assistant per turn

    if len(non_sys) <= threshold:
        return messages

    keep_n   = KEEP_RECENT * 2
    old_msgs = non_sys[:-keep_n]
    new_msgs = non_sys[-keep_n:]

    est_old = sum(len(m.get("content", "")) // 4 for m in old_msgs)
    logger.info(
        f"history_compressor: compressing {len(old_msgs)} messages "
        f"(~{est_old:,} tokens est.) → summary block"
    )

    summary = await _summarise_async(old_msgs)

    summary_block = {
        "role": "system",
        "content": "[Earlier conversation summarised]\n" + summary,
    }

    result = system_msgs + [summary_block] + new_msgs
    est_new = sum(len(m.get("content", "")) // 4 for m in result)
    logger.info(
        f"history_compressor: {est_old:,} → {est_new:,} tokens "
        f"(~{max(0, est_old - est_new):,} saved)"
    )
    return result


def compress_history_sync(messages: list[dict]) -> list[dict]:
    """
    Sync version — use if your loop is synchronous.
    Same logic as compress_history but without async/await.
    """
    if not _ENABLED:
        return messages

    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_sys     = [m for m in messages if m.get("role") != "system"]
    threshold   = COMPRESS_AFTER * 2

    if len(non_sys) <= threshold:
        return messages

    keep_n   = KEEP_RECENT * 2
    old_msgs = non_sys[:-keep_n]
    new_msgs = non_sys[-keep_n:]

    est_old = sum(len(m.get("content", "")) // 4 for m in old_msgs)
    logger.info(f"history_compressor: compressing {len(old_msgs)} messages (~{est_old:,} tokens)")

    summary = _summarise_sync(old_msgs)
    summary_block = {
        "role": "system",
        "content": "[Earlier conversation summarised]\n" + summary,
    }

    result = system_msgs + [summary_block] + new_msgs
    est_new = sum(len(m.get("content", "")) // 4 for m in result)
    logger.info(f"history_compressor: {est_old:,} → {est_new:,} tokens (~{max(0,est_old-est_new):,} saved)")
    return result


async def _summarise_async(messages: list[dict]) -> str:
    text = "\n".join(
        f"{m['role'].upper()}: {m.get('content', '')}" for m in messages
    )
    prompt = (
        "Summarise this conversation in ≤8 bullet points.\n"
        "Keep ONLY: decisions made, facts confirmed, tasks pending, "
        "errors encountered, key outputs.\n"
        "Omit greetings, filler, and redundant back-and-forth.\n\n"
        + text
    )
    try:
        client = _get_client()
        resp = await client.chat.completions.create(
            model=COMPRESS_MODEL,
            max_tokens=350,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning(f"history_compressor: async summarisation failed ({exc}) — using truncation")
        return _fallback_summary(messages)


def _summarise_sync(messages: list[dict]) -> str:
    text = "\n".join(
        f"{m['role'].upper()}: {m.get('content', '')}" for m in messages
    )
    prompt = (
        "Summarise this conversation in ≤8 bullet points.\n"
        "Keep ONLY: decisions, confirmed facts, pending tasks, errors, key outputs.\n"
        "Omit greetings and filler.\n\n" + text
    )
    try:
        client = _get_client()
        resp = client.chat.completions.create(
            model=COMPRESS_MODEL,
            max_tokens=350,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning(f"history_compressor: sync summarisation failed ({exc}) — using truncation")
        return _fallback_summary(messages)


def _fallback_summary(messages: list[dict]) -> str:
    lines = [f"• [{m['role']}] {m.get('content', '')[:200]}" for m in messages]
    return "\n".join(lines)
