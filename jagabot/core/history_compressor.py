"""
jagabot/core/history_compressor.py
─────────────────────────────────────
Compresses old conversation turns into a summary block.
Prevents linear token growth over long sessions.

Configuration via env vars:
  JAGABOT_COMPRESS_AFTER=6   turns before compression triggers (default: 6)
  JAGABOT_KEEP_RECENT=3      recent turns always kept raw (default: 3)
  JAGABOT_COMPRESS_MODEL=gpt-4o-mini  (default)
  JAGABOT_HISTORY_COMPRESS=0 to disable
"""

from __future__ import annotations
import os
from loguru import logger

_ENABLED       = os.getenv("JAGABOT_HISTORY_COMPRESS", "0") == "1"  # DISABLED until fixed
COMPRESS_AFTER = int(os.getenv("JAGABOT_COMPRESS_AFTER", "6"))
KEEP_RECENT    = int(os.getenv("JAGABOT_KEEP_RECENT", "3"))
COMPRESS_MODEL = os.getenv("JAGABOT_COMPRESS_MODEL", "gpt-4o-mini")

_client = None

def _get_client():
    global _client
    if _client is None:
        from openai import AsyncOpenAI
        _client = AsyncOpenAI()
    return _client


async def compress_history(messages: list[dict]) -> list[dict]:
    """
    Compress old messages into a summary block, keep recent turns raw.

    Parameters
    ----------
    messages : list of {"role": ..., "content": ...}
               The full messages list passed to the LLM (excluding system prompt).

    Returns
    -------
    Compressed messages list. Returns original if compression not needed.
    """
    if not _ENABLED:
        return messages

    # System messages should be kept separate - don't compress them
    # Only compress user/assistant conversation turns
    non_system = [m for m in messages if m.get("role") in ["user", "assistant"]]
    system_msgs = [m for m in messages if m.get("role") == "system"]
    
    threshold  = COMPRESS_AFTER * 2  # each turn = user + assistant

    if len(non_system) <= threshold:
        return messages

    keep_n   = KEEP_RECENT * 2
    old_msgs = non_system[:-keep_n]
    new_msgs = non_system[-keep_n:]

    est_saved = sum(len(m.get("content","")) // 4 for m in old_msgs)
    logger.info(
        f"history_compressor: compressing {len(old_msgs)} messages "
        f"(~{est_saved:,} tokens) → summary block"
    )

    summary = await _summarise(old_msgs)

    # REPLACE old messages with summary (not add to them)
    summary_block = {
        "role": "user",  # Use "user" role for summary
        "content": (
            f"[SUMMARY OF EARLIER CONVERSATION - {len(old_msgs)} messages compressed]\n"
            f"{summary}\n\n"
            f"[END OF SUMMARY - Continue conversation from here]\n"
        )
    }

    # Result = system messages + summary + recent messages ONLY
    result = system_msgs + [summary_block] + new_msgs
    
    # Calculate actual result size (should be smaller!)
    est_new = sum(len(m.get("content","")) // 4 for m in result)
    logger.info(
        f"history_compressor: {est_saved:,} → {est_new:,} tokens "
        f"(~{max(0,est_saved-est_new):,} saved)"
    )
    return result


async def _summarise(messages: list[dict]) -> str:
    text = "\n".join(
        f"{m['role'].upper()}: {m.get('content','')}" for m in messages
    )
    prompt = (
        "Summarise the following conversation in ≤8 bullet points.\n"
        "Keep ONLY: decisions made, facts confirmed, tasks pending, errors, "
        "tool outputs used.\n"
        "Omit greetings, filler, and back-and-forth.\n"
        "Keep summary UNDER 500 words.\n\n" + text
    )
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI()
        
        # Build base params
        create_params = {
            "model": COMPRESS_MODEL,
            "max_tokens": 500,
            "messages": [{"role": "user", "content": prompt}],
        }
        
        # OpenRouter compatibility: don't pass usage tracking
        if "openrouter" in COMPRESS_MODEL.lower():
            # Use extra_headers instead of extra_body for OpenRouter
            create_params["extra_headers"] = {"HTTP-Referer": "https://github.com/jagabot", "X-Title": "jagabot"}
        
        resp = await client.chat.completions.create(**create_params)
        summary = resp.choices[0].message.content.strip()
        # Truncate if still too long
        if len(summary) > 2000:
            summary = summary[:2000] + "..."
        return summary
    except Exception as exc:
        logger.warning(f"history_compressor: summarisation failed ({exc}) — using truncation")
        lines = [f"• [{m['role']}] {m.get('content','')[:200]}" for m in messages]
        return "\n".join(lines)
