"""
jagabot/core/trivial_guard.py
──────────────────────────────
Skip the LLM entirely for inputs like "hi", "ok", "thanks", "exit".
A "hi" was costing ~37,200+ tokens with 93 tool definitions attached.

Usage:
    from jagabot.core.trivial_guard import is_trivial, trivial_response

    if is_trivial(user_input):
        return trivial_response(user_input)
"""

from __future__ import annotations
import os
import random

_ENABLED = os.getenv("JAGABOT_TRIVIAL_GUARD", "1") == "1"

TRIVIAL: set[str] = {
    "hi","hello","hey","hiya","howdy","sup","yo",
    "ok","okay","k","sure","yep","yeah","yes","no","nope","nah",
    "got it","understood","noted","cool","great","nice",
    "thanks","thank you","ty","thx","cheers",
    "exit","quit","bye","goodbye","later","cya","done",
    "hmm","hm","um","uh","ah",
}

CANNED: dict[str, list[str]] = {
    "hi":        ["Hey! What would you like to work on?", "Hi — what's on your mind?"],
    "hello":     ["Hello! Ready when you are."],
    "hey":       ["Hey! What's up?"],
    "thanks":    ["You're welcome!", "Happy to help!"],
    "thank you": ["Of course!", "Any time."],
    "ok":        ["Got it. What's next?"],
    "yes":       ["Noted. What would you like to do?"],
    "no":        ["No problem. Anything else?"],
    "bye":       ["See you! Session saved. 👋"],
    "exit":      ["Session ended. 👋"],
    "done":      ["All done! 👋"],
}

_DEFAULT = ["What would you like to work on?", "How can I help?", "Go ahead — I'm listening."]


def is_trivial(text: str) -> bool:
    if not _ENABLED:
        return False
    n = text.strip().lower()
    return len(n.split()) <= 5 and n in TRIVIAL


def trivial_response(text: str) -> str:
    n = text.strip().lower()
    return random.choice(CANNED.get(n, _DEFAULT))
