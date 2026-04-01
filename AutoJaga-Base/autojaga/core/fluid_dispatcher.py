"""
Fluid Dispatcher — Intent classification and tool routing.

Classifies user intent and returns the appropriate tool set for the task.
No LLM calls — pure deterministic Python logic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


# Intent profiles
PROFILES = {
    "RESEARCH": {
        "description": "Web research, information gathering",
        "tools": ["web_search", "read_file", "write_file"],
        "triggers": ["research", "find", "search", "what is", "how does", "explain"],
    },
    "ACTION": {
        "description": "File operations, code execution",
        "tools": ["read_file", "write_file", "exec"],
        "triggers": ["create", "write", "save", "edit", "run", "execute"],
    },
    "ANALYSIS": {
        "description": "Data analysis, reasoning",
        "tools": ["read_file", "exec", "web_search"],
        "triggers": ["analyze", "compare", "evaluate", "assess"],
    },
    "CHAT": {
        "description": "General conversation",
        "tools": [],
        "triggers": [],  # Default fallback
    },
}


@dataclass
class DispatchPackage:
    """Result of dispatch — tools and context for this turn."""
    profile: str
    tools: list[str]
    description: str
    intent_confidence: float


def classify_intent(user_input: str) -> str:
    """
    Classify user intent from input text.
    
    Returns profile name (RESEARCH, ACTION, ANALYSIS, CHAT).
    Runs in <5ms — no LLM calls.
    """
    input_lower = user_input.lower()
    
    # Check each profile's triggers
    for profile_name, config in PROFILES.items():
        triggers = config.get("triggers", [])
        for trigger in triggers:
            if trigger in input_lower:
                return profile_name
    
    # Default to CHAT
    return "CHAT"


def dispatch(user_input: str) -> DispatchPackage:
    """
    Dispatch user input to appropriate tool set.
    
    Args:
        user_input: The user's message.
    
    Returns:
        DispatchPackage with tools and context.
    """
    profile = classify_intent(user_input)
    config = PROFILES.get(profile, PROFILES["CHAT"])
    
    return DispatchPackage(
        profile=profile,
        tools=config.get("tools", []),
        description=config.get("description", ""),
        intent_confidence=0.9 if profile != "CHAT" else 0.5,
    )


def get_profile_tools(profile: str) -> list[str]:
    """Get tool list for a profile."""
    return PROFILES.get(profile, {}).get("tools", [])


def get_all_profiles() -> dict[str, Any]:
    """Get all profile configurations."""
    return PROFILES.copy()
