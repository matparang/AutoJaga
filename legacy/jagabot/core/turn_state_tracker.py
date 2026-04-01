"""
TurnStateTracker — tracks state across turns in a session.

Prevents drift by maintaining:
  - Active scenario definition
  - Locked assumptions (agreed facts)
  - Variables already established
  - Unresolved uncertainties
  - Prior corrections
  - Locked definitions

Injects state summary into each turn to maintain continuity.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger


@dataclass
class TurnState:
    """State tracked across turns."""
    scenario:          str         = ""     # current scenario being analyzed
    domain:            str         = ""     # current domain
    locked_assumptions: list[str] = field(default_factory=list)   # agreed facts
    established_vars:  dict[str, str] = field(default_factory=dict)  # name → value
    unresolved:        list[str]  = field(default_factory=list)    # open questions
    prior_corrections: list[str]  = field(default_factory=list)    # user corrections
    locked_definitions: dict[str, str] = field(default_factory=dict)  # term → def
    turn_count:        int        = 0
    last_updated:      str        = ""


class TurnStateTracker:
    """
    Tracks and persists state across turns.
    Injects relevant state context into each message.
    """

    def __init__(self):
        self._state = TurnState()
        self._active = False

    def start_scenario(self, scenario: str, domain: str) -> None:
        """Start tracking a new scenario."""
        self._state = TurnState(
            scenario     = scenario[:100],
            domain       = domain,
            last_updated = datetime.now().isoformat(),
        )
        self._active = True
        logger.debug(f"TurnState: new scenario '{scenario[:40]}' domain={domain}")

    def update(self, query: str, response: str, domain: str) -> None:
        """Update state after each turn."""
        self._state.turn_count  += 1
        self._state.last_updated = datetime.now().isoformat()

        # Auto-detect domain change
        if domain and domain != self._state.domain and domain != "general":
            self._state.domain = domain

        # Auto-detect locked assumptions from response
        import re
        # Look for definitive statements
        patterns = [
            r"the (\w+ \w+) is (\$?[\d.]+[%]?)",
            r"intervention lag[:\s]+([\w\s]+)",
            r"controlled variable[:\s]+([\w\s]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                fact = match.group(0)[:80]
                if fact not in self._state.locked_assumptions:
                    self._state.locked_assumptions.append(fact)

        # Keep locked assumptions list manageable
        if len(self._state.locked_assumptions) > 10:
            self._state.locked_assumptions = self._state.locked_assumptions[-10:]

    def add_correction(self, correction: str) -> None:
        """Record a user correction."""
        self._state.prior_corrections.append(
            f"[Turn {self._state.turn_count}] {correction[:100]}"
        )
        logger.debug(f"TurnState: correction recorded")

    def lock_definition(self, term: str, definition: str) -> None:
        """Lock a term definition for this session."""
        self._state.locked_definitions[term] = definition[:100]
        logger.debug(f"TurnState: locked definition '{term}'")

    def add_unresolved(self, question: str) -> None:
        """Add an unresolved uncertainty."""
        if question not in self._state.unresolved:
            self._state.unresolved.append(question[:100])

    def resolve(self, question: str) -> None:
        """Mark an uncertainty as resolved."""
        self._state.unresolved = [
            q for q in self._state.unresolved if question[:30] not in q
        ]

    def get_injection(self) -> str:
        """Build state injection for system prompt."""
        if not self._active or self._state.turn_count == 0:
            return ""

        lines = ["\n[SESSION STATE]"]

        if self._state.scenario:
            lines.append(f"Scenario: {self._state.scenario}")

        if self._state.locked_assumptions:
            lines.append("Locked assumptions (do not contradict):")
            for a in self._state.locked_assumptions[-5:]:
                lines.append(f"  ✓ {a}")

        if self._state.established_vars:
            lines.append("Established variables:")
            for k, v in list(self._state.established_vars.items())[-5:]:
                lines.append(f"  {k} = {v}")

        if self._state.unresolved:
            lines.append("Unresolved uncertainties:")
            for u in self._state.unresolved[-3:]:
                lines.append(f"  ? {u}")

        if self._state.prior_corrections:
            lines.append("Prior corrections (apply these):")
            for c in self._state.prior_corrections[-3:]:
                lines.append(f"  ⚠️ {c}")

        if self._state.locked_definitions:
            lines.append("Locked definitions:")
            for term, defn in list(self._state.locked_definitions.items())[-3:]:
                lines.append(f"  [{term}]: {defn}")

        if len(lines) <= 1:
            return ""

        return "\n".join(lines)

    def reset(self) -> None:
        """Reset state for new session."""
        self._state  = TurnState()
        self._active = False
        logger.debug("TurnState: reset")

    def get_stats(self) -> dict:
        return {
            "turn_count":         self._state.turn_count,
            "scenario":           self._state.scenario[:40],
            "locked_assumptions": len(self._state.locked_assumptions),
            "unresolved":         len(self._state.unresolved),
            "corrections":        len(self._state.prior_corrections),
        }
