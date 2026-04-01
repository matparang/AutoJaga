"""
TaskStateManager — tracks what the agent has done this turn.

Prevents redundant tool calls and re-narration by:
1. Recording fetched data per turn
2. Injecting compact state summary into context
3. Blocking duplicate fetches before they reach LLM

Flow:
  Turn starts → state reset
  Tool executes → state records result
  Next LLM call → state injected as compact summary
  LLM sees: "[State: NVDA price=$178.56 (fetched), news=5 articles (fetched)]"
  → Agent skips re-fetching, skips narrating what it already did
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger


@dataclass
class FetchedItem:
    """A single fetched data item."""
    tool:      str
    key:       str    # e.g. "NVDA:quote"
    summary:   str    # compact 1-line summary
    fetched_at: str = field(default_factory=lambda: datetime.now().isoformat())


class TaskStateManager:
    """
    Tracks agent state within a single turn.
    Resets at the start of each new user message.
    """

    def __init__(self):
        self._fetched: dict[str, FetchedItem] = {}
        self._phase:   str = "init"
        self._turn_id: int = 0

    def reset(self, turn_id: int = 0) -> None:
        """Reset state for new turn."""
        self._fetched.clear()
        self._phase = "data_fetch"
        self._turn_id = turn_id
        logger.debug(f"TaskState: reset for turn {turn_id}")

    def record_fetch(self, tool: str, args: dict, result: str) -> None:
        """Record a successful tool fetch."""
        # Build compact key
        ticker = args.get("ticker", "")
        action = args.get("action", "")
        query  = args.get("query", "")[:30]
        key    = f"{tool}:{ticker}:{action}:{query}".strip(":")

        # Build compact summary
        if tool == "yahoo_finance":
            if action == "quote":
                import re
                price = re.search(r'"price":\s*([\d.]+)', result)
                summary = f"${price.group(1)}" if price else "fetched"
            elif action == "news":
                count = result.count('"title"')
                summary = f"{count} articles"
            elif action == "history":
                period = args.get("period", "?")
                summary = f"{period} history"
            elif action == "financials":
                summary = "financials"
            else:
                summary = "fetched"
        elif tool == "web_search_mcp":
            summary = f"search: {query}"
        elif tool == "memory_fleet":
            summary = f"memory: {action}"
        else:
            summary = "fetched"

        self._fetched[key] = FetchedItem(
            tool=tool, key=key, summary=summary
        )
        logger.debug(f"TaskState: recorded {key} = {summary}")

    def is_fetched(self, tool: str, args: dict) -> bool:
        """Check if this tool+args combo was already fetched."""
        ticker = args.get("ticker", "")
        action = args.get("action", "")
        query  = args.get("query", "")[:30]
        key    = f"{tool}:{ticker}:{action}:{query}".strip(":")
        return key in self._fetched

    def set_phase(self, phase: str) -> None:
        """Update current execution phase."""
        if phase != self._phase:
            logger.debug(f"TaskState: phase {self._phase} → {phase}")
            self._phase = phase

    def get_state_summary(self) -> str:
        """Return compact state summary for LLM injection."""
        if not self._fetched:
            return ""

        items = []
        for item in self._fetched.values():
            items.append(f"{item.tool.replace('yahoo_finance','YF').replace('web_search_mcp','WS')}:{item.summary}")

        summary = " | ".join(items)
        return f"[FETCHED: {summary}] [PHASE: {self._phase}] Skip re-fetching above data."

    def get_phase_instruction(self) -> str:
        """Return phase-specific instruction to reduce narration."""
        instructions = {
            "data_fetch":  "Fetch required data. No narration — just call tools.",
            "analysis":    "Analyze fetched data. Be concise. No re-stating data sources.",
            "synthesis":   "Synthesize findings. Output structured result only.",
            "output":      "Format final answer. No process explanation needed.",
        }
        return instructions.get(self._phase, "Execute. No narration.")

    def auto_advance_phase(self, tools_called: int) -> None:
        """Auto-advance phase based on tool call count."""
        if tools_called == 0:
            self._phase = "data_fetch"
        elif tools_called <= 3:
            self._phase = "analysis"
        elif tools_called <= 6:
            self._phase = "synthesis"
        else:
            self._phase = "output"

    def get_stats(self) -> dict:
        """Return state statistics."""
        return {
            "fetched_count": len(self._fetched),
            "phase":         self._phase,
            "turn_id":       self._turn_id,
            "keys":          list(self._fetched.keys()),
        }
