"""Mission Control TUI — real-time swarm dashboard using rich.Live."""

from __future__ import annotations

from typing import Any

from jagabot.swarm.status import WorkerTracker, WorkerState


def generate_dashboard(
    tracker: WorkerTracker,
    orchestrator_status: dict[str, Any] | None = None,
    watchdog_health: dict[str, Any] | None = None,
    cost_summary: dict[str, Any] | None = None,
) -> str:
    """Generate a text-based dashboard snapshot.

    This produces a formatted string that can be rendered by rich.Console
    or printed directly. For TUI use, wrap with rich.Live for auto-refresh.
    """
    lines: list[str] = []

    # ── Header ──
    lines.append("╔══════════════════════════════════════════════════════════╗")
    lines.append("║         🐝  JAGABOT MISSION CONTROL  🐝                ║")
    lines.append("╚══════════════════════════════════════════════════════════╝")
    lines.append("")

    # ── Worker Status ──
    stats = tracker.stats()
    lines.append("┌─ Workers ─────────────────────────────────────────────┐")
    lines.append(f"│  Running: {stats['running']:>3}  │  Stalled: {stats['stalled']:>3}  "
                 f"│  Completed: {stats['completed']:>5}  │  Errors: {stats['errors']:>3}  │")
    if stats['avg_elapsed_s'] > 0:
        lines.append(f"│  Avg Time: {stats['avg_elapsed_s']:.3f}s  │  "
                     f"Tools Used: {len(stats['tools_used'])}  │")
    lines.append("└────────────────────────────────────────────────────────┘")
    lines.append("")

    # ── Active Tasks ──
    active = tracker.active_workers()
    if active:
        lines.append("┌─ Active Tasks ─────────────────────────────────────────┐")
        for w in active[:10]:
            state_icon = "🔄" if w.state == WorkerState.RUNNING else "⚠️"
            lines.append(f"│  {state_icon} {w.tool_name}/{w.method or '?':<25} "
                         f"task={w.task_id}  │")
        if len(active) > 10:
            lines.append(f"│  ... and {len(active) - 10} more                      │")
        lines.append("└────────────────────────────────────────────────────────┘")
        lines.append("")

    # ── Orchestrator Info ──
    if orchestrator_status:
        lines.append("┌─ Orchestrator ─────────────────────────────────────────┐")
        lines.append(f"│  Max Workers: {orchestrator_status.get('max_workers', '?')}  │  "
                     f"Tools: {orchestrator_status.get('available_tools', '?')}  │  "
                     f"Analyses: {orchestrator_status.get('total_analyses', '?')}  │")
        lines.append("└────────────────────────────────────────────────────────┘")
        lines.append("")

    # ── Costs ──
    if cost_summary:
        lines.append("┌─ Costs ─────────────────────────────────────────────────┐")
        lines.append(f"│  Today: ${cost_summary.get('daily', 0):.4f}  │  "
                     f"Month: ${cost_summary.get('monthly', 0):.4f}  │")
        budgets = cost_summary.get("budgets", {})
        if budgets:
            for period, amount in budgets.items():
                lines.append(f"│  Budget ({period}): ${amount:.4f}  │")
        lines.append("└────────────────────────────────────────────────────────┘")
        lines.append("")

    # ── Watchdog ──
    if watchdog_health:
        running = "✅" if watchdog_health.get("running") else "❌"
        alerts = watchdog_health.get("total_alerts", 0)
        critical = watchdog_health.get("recent_critical", 0)
        lines.append("┌─ Watchdog ──────────────────────────────────────────────┐")
        lines.append(f"│  Status: {running}  │  Alerts: {alerts}  │  Critical: {critical}  │")
        sys_info = watchdog_health.get("system", {})
        if "cpu_percent" in sys_info:
            lines.append(f"│  CPU: {sys_info['cpu_percent']:.1f}%  │  "
                         f"Memory: {sys_info['memory_percent']:.1f}%  │  "
                         f"Available: {sys_info.get('memory_available_mb', '?')}MB  │")
        lines.append("└────────────────────────────────────────────────────────┘")
        lines.append("")

    # ── Recent History ──
    history = tracker.recent_history(5)
    if history:
        lines.append("┌─ Recent Tasks ─────────────────────────────────────────┐")
        for w in history:
            icon = "✅" if w.state == WorkerState.DONE else "❌"
            lines.append(f"│  {icon} {w.tool_name}/{w.method or '?':<20} "
                         f"{w.elapsed_s:.3f}s  │")
        lines.append("└────────────────────────────────────────────────────────┘")

    return "\n".join(lines)
