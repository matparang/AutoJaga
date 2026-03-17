"""
Tool Profiler — performance statistics and degradation alerts.

Reads from the ToolHarness execution history to compute per-tool
performance metrics and flag tools that are running significantly
slower than their historical average.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from jagabot.core.tool_harness import _ToolExecution


@dataclass
class ToolStats:
    """Performance statistics for a single tool."""
    tool_name: str
    call_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_elapsed: float = 0.0
    min_elapsed: float = 0.0
    max_elapsed: float = 0.0
    p95_elapsed: float = 0.0
    failure_rate: float = 0.0


@dataclass
class DegradationAlert:
    """Alert for a tool running slower than expected."""
    tool_name: str
    current_avg: float
    baseline_avg: float
    ratio: float
    message: str = ""


class ToolProfiler:
    """
    Computes performance metrics from tool execution history.

    Usage:
        profiler = ToolProfiler(harness._history)
        stats = profiler.get_stats()
        alerts = profiler.check_degradation()
    """

    def __init__(
        self,
        history: list["_ToolExecution"],
        degradation_threshold: float = 2.0,
    ) -> None:
        self._history = history
        self._degradation_threshold = degradation_threshold

    def get_stats(self) -> dict[str, ToolStats]:
        """Compute per-tool performance statistics."""
        by_tool: dict[str, list["_ToolExecution"]] = {}
        for ex in self._history:
            by_tool.setdefault(ex.tool_name, []).append(ex)

        result = {}
        for name, execs in by_tool.items():
            elapsed_list = [ex.elapsed for ex in execs if ex.end_time is not None]
            successes = sum(1 for ex in execs if ex.status == "complete")
            failures = sum(1 for ex in execs if ex.status == "failed")
            total = len(execs)

            stats = ToolStats(
                tool_name=name,
                call_count=total,
                success_count=successes,
                failure_count=failures,
                failure_rate=failures / total if total > 0 else 0.0,
            )

            if elapsed_list:
                stats.avg_elapsed = statistics.mean(elapsed_list)
                stats.min_elapsed = min(elapsed_list)
                stats.max_elapsed = max(elapsed_list)
                if len(elapsed_list) >= 2:
                    sorted_e = sorted(elapsed_list)
                    idx = int(len(sorted_e) * 0.95)
                    stats.p95_elapsed = sorted_e[min(idx, len(sorted_e) - 1)]
                else:
                    stats.p95_elapsed = stats.max_elapsed

            result[name] = stats

        return result

    def check_degradation(self) -> list[DegradationAlert]:
        """
        Flag tools running significantly slower than average.

        Compares the last 5 calls against the overall average.
        Alerts if ratio exceeds the degradation threshold.
        """
        alerts = []
        by_tool: dict[str, list[float]] = {}
        for ex in self._history:
            if ex.end_time is not None:
                by_tool.setdefault(ex.tool_name, []).append(ex.elapsed)

        for name, all_elapsed in by_tool.items():
            if len(all_elapsed) < 5:
                continue

            overall_avg = statistics.mean(all_elapsed)
            recent = all_elapsed[-5:]
            recent_avg = statistics.mean(recent)

            if overall_avg > 0 and recent_avg / overall_avg >= self._degradation_threshold:
                ratio = recent_avg / overall_avg
                alert = DegradationAlert(
                    tool_name=name,
                    current_avg=round(recent_avg, 2),
                    baseline_avg=round(overall_avg, 2),
                    ratio=round(ratio, 1),
                    message=(
                        f"Tool '{name}' degraded: recent avg {recent_avg:.1f}s "
                        f"vs baseline {overall_avg:.1f}s ({ratio:.1f}x slower)"
                    ),
                )
                logger.warning(alert.message)
                alerts.append(alert)

        return alerts

    def slow_tools(self, threshold_seconds: float = 10.0) -> list[ToolStats]:
        """Return tools whose average exceeds the threshold."""
        stats = self.get_stats()
        return [s for s in stats.values() if s.avg_elapsed > threshold_seconds]
