"""
Context Compressor — structured turn tracking with milestone summaries.

Complements the existing ``jagabot.agent.compressor`` (micro-compact / auto-
compact / transcript archival) by adding a *proactive* layer:

- Every turn is stored as a structured record (user input, tool names, short
  response summary).
- Every ``summary_interval`` turns a milestone is generated (topics, tools,
  outcome).
- ``get_compressed_context()`` returns last 3 milestones + last 5 turns for
  injection into the system prompt, keeping the LLM aware of older history
  without filling the context window.
"""
from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


# ── Dataclasses ──────────────────────────────────────────────────

@dataclass
class TurnRecord:
    """One conversation turn."""
    turn: int
    user: str
    agent_summary: str
    tools: list[str]
    timestamp: float = field(default_factory=time.time)


@dataclass
class Milestone:
    """Summary of a block of turns."""
    turns_range: str          # e.g. "6-10"
    topics: list[str]
    tools_used: list[str]
    outcome: str


# ── Main class ───────────────────────────────────────────────────

class ContextCompressor:
    """Proactive turn tracker with periodic milestone summaries."""

    def __init__(
        self,
        max_recent: int = 20,
        summary_interval: int = 5,
    ) -> None:
        self.max_recent = max_recent
        self.summary_interval = summary_interval
        self._turn_count = 0
        self.recent: deque[TurnRecord] = deque(maxlen=max_recent)
        self.milestones: list[Milestone] = []

    # ── Properties ───────────────────────────────────────────────

    @property
    def turn_count(self) -> int:
        return self._turn_count

    # ── Public API ───────────────────────────────────────────────

    def add_turn(
        self,
        user_input: str,
        agent_response: str,
        tools_used: list[str] | None = None,
    ) -> None:
        """Record a completed conversation turn."""
        self._turn_count += 1
        rec = TurnRecord(
            turn=self._turn_count,
            user=_truncate(user_input, 120),
            agent_summary=_summarise_response(agent_response, tools_used or []),
            tools=list(tools_used or []),
        )
        self.recent.append(rec)

        if self._turn_count % self.summary_interval == 0:
            self._create_milestone()

    def get_compressed_context(self) -> str:
        """Build a compressed context string suitable for system prompt injection."""
        parts: list[str] = []

        # Milestones (last 3)
        for ms in self.milestones[-3:]:
            topics = ", ".join(ms.topics[:4]) or "general"
            parts.append(
                f"[Turns {ms.turns_range}] {topics} -- "
                f"tools: {', '.join(ms.tools_used[:5]) or 'none'} -- {ms.outcome}"
            )

        # Recent turns (last 5)
        recent_list = list(self.recent)[-5:]
        if recent_list:
            parts.append("--- Recent turns ---")
            for tr in recent_list:
                tools_tag = f" [{', '.join(tr.tools[:3])}]" if tr.tools else ""
                parts.append(f"Turn {tr.turn}: User: {tr.user}")
                parts.append(f"  -> Agent{tools_tag}: {tr.agent_summary}")

        return "\n".join(parts)

    # ── Internal ─────────────────────────────────────────────────

    def _create_milestone(self) -> None:
        recent_block = [
            r for r in self.recent
            if r.turn > self._turn_count - self.summary_interval
        ]
        if not recent_block:
            return

        first = recent_block[0].turn
        last = recent_block[-1].turn

        all_tools: list[str] = []
        for r in recent_block:
            all_tools.extend(r.tools)

        ms = Milestone(
            turns_range=f"{first}-{last}",
            topics=_extract_topics(recent_block),
            tools_used=sorted(set(all_tools)),
            outcome=_determine_outcome(recent_block),
        )
        self.milestones.append(ms)


# ── Helpers ──────────────────────────────────────────────────────

def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


_FILE_RE = re.compile(r"[\w/.-]+\.\w{1,5}")
_ERROR_WORDS = {"error", "fail", "exception", "traceback", "refused", "denied"}
_SUCCESS_WORDS = {"success", "done", "created", "complete", "approved", "saved", "passed"}


def _summarise_response(response: str, tools: list[str]) -> str:
    """Extract key signals from an agent response."""
    if not response:
        return "(empty)"

    points: list[str] = []

    # Tool usage
    if tools:
        points.append(f"used {', '.join(tools[:3])}")

    # File mentions
    files = _FILE_RE.findall(response)
    if files:
        unique = list(dict.fromkeys(files))[:3]
        points.append(f"files: {', '.join(unique)}")

    # Error / success signals
    lower = response.lower()
    if any(w in lower for w in _ERROR_WORDS):
        points.append("error detected")
    elif any(w in lower for w in _SUCCESS_WORDS):
        points.append("success")

    if points:
        return " | ".join(points)

    return _truncate(response, 100)


def _extract_topics(records: list[TurnRecord]) -> list[str]:
    """Rough topic extraction from user inputs."""
    topics: list[str] = []
    for r in records:
        words = r.user.lower().split()
        # Take first 3 meaningful words (skip very short ones)
        meaningful = [w for w in words if len(w) > 3][:2]
        if meaningful:
            topics.extend(meaningful)
    # Deduplicate preserving order
    seen: set[str] = set()
    result: list[str] = []
    for t in topics:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result[:5]


def _determine_outcome(records: list[TurnRecord]) -> str:
    """Summarise the block outcome."""
    error_count = sum(1 for r in records if "error" in r.agent_summary.lower())
    success_count = sum(1 for r in records if "success" in r.agent_summary.lower())

    if error_count > len(records) // 2:
        return "mostly errors"
    if success_count > len(records) // 2:
        return "mostly successful"
    return "mixed results"
