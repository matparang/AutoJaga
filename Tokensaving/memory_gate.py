"""
jagabot/core/memory_gate.py
────────────────────────────
Gates memory retrieval so it only fires on substantive inputs.

AUDIT FINDING: get_context() was called on every turn including "hi",
returning up to 8 memory entries (~600 tokens) but producing 0 useful facts.

Usage
-----
    from jagabot.core.memory_gate import should_retrieve_memory

    # Replace unconditional memory calls in loop.py:
    if should_retrieve_memory(user_input):
        memory_context = await self.memory_manager.get_context(user_input)
    else:
        memory_context = []
        logger.debug("MemoryManager: skipped (input too short)")

Config
------
    JAGABOT_MEMORY_GATE=0              disable gating
    JAGABOT_MIN_WORDS_MEMORY=4         min word count threshold (default 4)
"""

from __future__ import annotations
import os

_ENABLED       = os.getenv("JAGABOT_MEMORY_GATE", "1") == "1"
MIN_WORD_COUNT = int(os.getenv("JAGABOT_MIN_WORDS_MEMORY", "4"))

# Short queries that bypass the word-count gate because they're high-signal
_BYPASS_KEYWORDS: tuple[str, ...] = (
    "remember", "engine", "status", "check", "solidif",
    "show", "recall", "history", "pending", "wired", "working",
    "list", "audit", "fix", "debug",
)


def should_retrieve_memory(text: str) -> bool:
    """
    Return True if memory retrieval is worth running for this input.

    Logic (in order):
    1. Gate disabled → always True
    2. High-signal keyword present → True (even if short)
    3. Word count >= MIN_WORD_COUNT → True
    4. Otherwise → False
    """
    if not _ENABLED:
        return True

    normalised = text.strip().lower()

    # High-signal bypass — "solidify engine?" is short but meaningful
    if any(kw in normalised for kw in _BYPASS_KEYWORDS):
        return True

    return len(normalised.split()) >= MIN_WORD_COUNT
