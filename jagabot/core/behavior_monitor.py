"""
Behavior Monitor — learns normal agent patterns and flags anomalies.

Maintains a rolling window of per-turn metrics (tools used, iteration
count, response length) and flags turns that deviate significantly
from the established baseline.

Anomalies are informational warnings — they don't block responses.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from loguru import logger

_WINDOW_SIZE = 20


@dataclass
class TurnRecord:
    """Metrics for a single agent turn."""
    tools_used: list[str] = field(default_factory=list)
    iteration_count: int = 0
    response_length: int = 0


@dataclass
class Anomaly:
    """A detected behavioral anomaly."""
    category: str    # "tool_spike" | "response_length" | "iteration_count" | "zero_tools"
    message: str
    severity: str = "warning"  # "warning" | "info"


class BehaviorMonitor:
    """
    Tracks agent behavior over a rolling window and flags deviations.

    Usage:
        monitor = BehaviorMonitor()
        # After each message processing:
        monitor.record_turn(tools_used, iterations, len(response))
        anomalies = monitor.check_anomalies()
    """

    def __init__(self, window_size: int = _WINDOW_SIZE) -> None:
        self._window_size = window_size
        self._history: list[TurnRecord] = []
        self._last_user_message: str = ""  # Track for anomaly suppression

    def record_turn(
        self,
        tools_used: list[str],
        iteration_count: int,
        response_length: int,
        user_message: str = "",
    ) -> None:
        """Record metrics for the current turn."""
        self._history.append(TurnRecord(
            tools_used=list(tools_used),
            iteration_count=iteration_count,
            response_length=response_length,
        ))
        # Keep only the window
        if len(self._history) > self._window_size * 2:
            self._history = self._history[-self._window_size:]
        # Store user message for anomaly suppression
        if user_message:
            self._last_user_message = user_message

    def _user_requested_tool(self, tool_name: str, user_message: str) -> bool:
        """
        Return True if user explicitly named this tool in their message.
        Suppresses false anomaly warnings for explicit tool requests.
        """
        # Check if tool name appears in user message
        tool_variants = [
            tool_name,                          # quad_agent
            tool_name.replace("_", " "),        # quad agent  
            tool_name.replace("_", "-"),        # quad-agent
        ]
        msg_lower = user_message.lower()
        return any(variant in msg_lower for variant in tool_variants)

    def check_anomalies(self) -> list[Anomaly]:
        """
        Check the most recent turn against baseline.

        Requires at least 5 turns of history to establish baseline.
        """
        if len(self._history) < 5:
            return []

        current = self._history[-1]
        baseline = self._history[-min(len(self._history), self._window_size):-1]
        anomalies = []

        # ── Tool usage spike ─────────────────────────────────
        baseline_tool_counts = Counter()
        for turn in baseline:
            baseline_tool_counts.update(turn.tools_used)

        n_baseline = len(baseline)
        current_tool_counts = Counter(current.tools_used)

        for tool, count in current_tool_counts.items():
            avg_usage = baseline_tool_counts.get(tool, 0) / n_baseline
            if avg_usage > 0 and count > avg_usage * 3:
                # Suppress if user explicitly requested this tool
                if not self._user_requested_tool(tool, self._last_user_message):
                    anomalies.append(Anomaly(
                        category="tool_spike",
                        message=(
                            f"Tool '{tool}' used {count}x this turn "
                            f"(baseline avg: {avg_usage:.1f}x/turn)"
                        ),
                    ))

        # ── Response length anomaly ──────────────────────────
        avg_length = sum(t.response_length for t in baseline) / n_baseline
        if avg_length > 0 and current.response_length > avg_length * 3:
            anomalies.append(Anomaly(
                category="response_length",
                message=(
                    f"Response length {current.response_length} chars "
                    f"(baseline avg: {avg_length:.0f})"
                ),
            ))

        # ── Iteration count anomaly ──────────────────────────
        avg_iterations = sum(t.iteration_count for t in baseline) / n_baseline
        if avg_iterations > 0 and current.iteration_count > avg_iterations * 2:
            anomalies.append(Anomaly(
                category="iteration_count",
                message=(
                    f"Iteration count {current.iteration_count} "
                    f"(baseline avg: {avg_iterations:.1f})"
                ),
            ))

        # ── Zero tools when baseline uses tools ──────────────
        tool_turn_rate = sum(1 for t in baseline if t.tools_used) / n_baseline
        if (
            not current.tools_used
            and tool_turn_rate > 0.5
            and current.response_length > 500
        ):
            anomalies.append(Anomaly(
                category="zero_tools",
                message=(
                    f"No tools used despite {tool_turn_rate:.0%} of baseline "
                    f"turns using tools (response: {current.response_length} chars)"
                ),
                severity="info",
            ))

        for a in anomalies:
            logger.warning(f"Behavior anomaly [{a.category}]: {a.message}")

        return anomalies

    @property
    def turn_count(self) -> int:
        """Number of recorded turns."""
        return len(self._history)
