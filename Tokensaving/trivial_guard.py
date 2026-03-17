"""
jagabot/core/trivial_guard.py
──────────────────────────────
Intercepts trivial inputs before they hit the LLM.

AUDIT FINDING: "hi" was costing ~60,000 tokens because:
- All 93 tool definitions were still attached
- Memory context was retrieved
- Full conversation history was sent

This guard prevents all of that for single-word/short acknowledgement inputs.

Usage
-----
    from jagabot.core.trivial_guard import is_trivial, trivial_response

    # Wire at the TOP of _process_message(), before any other logic:
    if is_trivial(user_input):
        reply = trivial_response(user_input)
        budget.record_skip()
        logger.info(f"Trivial guard fired — LLM call skipped for: '{user_input}'")
        return reply

Config
------
    JAGABOT_TRIVIAL_GUARD=0   disable this guard entirely
"""

from __future__ import annotations
import os, random

_ENABLED = os.getenv("JAGABOT_TRIVIAL_GUARD", "1") == "1"

TRIVIAL: set[str] = {
    # Greetings
    "hi", "hello", "hey", "hiya", "howdy", "sup", "yo",
    # Acknowledgements
    "ok", "okay", "k", "sure", "yep", "yeah", "yes", "no", "nope", "nah",
    "got it", "understood", "noted", "cool", "great", "nice",
    # Thanks
    "thanks", "thank you", "ty", "thx", "cheers",
    # Exit / control
    "exit", "quit", "bye", "goodbye", "later", "cya", "done",
    # Filler
    "hmm", "hm", "um", "uh", "ah",
}

CANNED: dict[str, list[str]] = {
    "hi":        ["Hey! What would you like to work on?", "Hi — what's on your mind?"],
    "hello":     ["Hello! Ready when you are."],
    "hey":       ["Hey! What's up?"],
    "thanks":    ["You're welcome!", "Happy to help!"],
    "thank you": ["Of course!", "Any time."],
    "ok":        ["Got it. What's next?"],
    "okay":      ["Sure thing. What's next?"],
    "yes":       ["Noted. What would you like to do?"],
    "no":        ["No problem. Anything else?"],
    "cool":      ["😎 What's next?"],
    "great":     ["Great! What's next?"],
    "bye":       ["See you! Session saved. 🐈"],
    "exit":      ["Session ended. 🐈"],
    "quit":      ["Session ended. 🐈"],
    "done":      ["All done! 🐈"],
}

_DEFAULT = [
    "What would you like to work on?",
    "How can I help?",
    "Go ahead — I'm listening.",
]


def is_trivial(text: str) -> bool:
    """Return True if this input should skip the LLM entirely."""
    if not _ENABLED:
        return False
    normalised = text.strip().lower()
    # Max 5 words to avoid false positives on real sentences
    return len(normalised.split()) <= 5 and normalised in TRIVIAL


def trivial_response(text: str) -> str:
    """Return an appropriate canned response without calling the LLM."""
    normalised = text.strip().lower()
    options = CANNED.get(normalised, _DEFAULT)
    return random.choice(options)
