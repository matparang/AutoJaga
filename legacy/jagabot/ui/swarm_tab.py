"""Swarm Visualizer — Streamlit tab for real-time worker status.

Shows:
- Worker cards (IDLE / RUNNING / DONE / ERROR / STALLED)
- Aggregate stats panel
- Recent task history table
- Auto-refresh every 3 seconds
"""
from __future__ import annotations

import time
from typing import Optional

try:
    import streamlit as st

    _ST_AVAILABLE = True
except ImportError:  # pragma: no cover
    _ST_AVAILABLE = False

from jagabot.swarm.status import WorkerState, WorkerTracker

_STATE_EMOJI = {
    WorkerState.RUNNING: "🟢",
    WorkerState.IDLE: "⚪",
    WorkerState.DONE: "✅",
    WorkerState.ERROR: "❌",
    WorkerState.STALLED: "⚠️",
}

_STATE_COLOR = {
    WorkerState.RUNNING: "green",
    WorkerState.IDLE: "gray",
    WorkerState.DONE: "blue",
    WorkerState.ERROR: "red",
    WorkerState.STALLED: "orange",
}


def _format_elapsed(seconds: float) -> str:
    if seconds < 0.001:
        return "—"
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s}s"


def render_swarm_tab(tracker: Optional[WorkerTracker] = None) -> None:
    """Render the Swarm Visualizer tab content.

    Args:
        tracker: WorkerTracker instance. If None, a placeholder UI is shown.
    """
    if not _ST_AVAILABLE:
        return  # pragma: no cover

    st.header("🐝 Swarm Visualizer")
    st.caption("Real-time view of jagabot swarm workers, task queue, and performance metrics.")

    # ------------------------------------------------------------------ #
    # Auto-refresh control                                                 #
    # ------------------------------------------------------------------ #
    col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([2, 1, 1])
    with col_ctrl1:
        auto_refresh = st.checkbox("Auto-refresh (every 3s)", value=True, key="swarm_auto_refresh")
    with col_ctrl2:
        if st.button("🔄 Refresh Now", key="swarm_refresh_btn"):
            st.rerun()
    with col_ctrl3:
        history_limit = st.number_input("History rows", min_value=5, max_value=50, value=20, step=5, key="swarm_hist_limit")

    if tracker is None:
        st.info("No WorkerTracker attached. Start a swarm task to see live data here.")
        _render_demo_placeholder()
        return

    # ------------------------------------------------------------------ #
    # Stats bar                                                            #
    # ------------------------------------------------------------------ #
    stats = tracker.stats()
    active = tracker.active_workers()
    history = tracker.recent_history(limit=int(history_limit))

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("🟢 Running", stats["running"])
    col2.metric("✅ Completed", stats["completed"])
    col3.metric("❌ Errors", stats["errors"])
    col4.metric("⚠️ Stalled", stats["stalled"])
    col5.metric("⏱ Avg Time", f"{stats['avg_elapsed_s']}s" if stats["avg_elapsed_s"] else "—")

    st.divider()

    # ------------------------------------------------------------------ #
    # Active workers                                                       #
    # ------------------------------------------------------------------ #
    left, right = st.columns([3, 2])

    with left:
        st.subheader("Active Workers")
        if not active:
            st.info("No active workers right now.")
        else:
            for w in active:
                emoji = _STATE_EMOJI.get(w.state, "❓")
                elapsed = time.monotonic() - w.started_at if w.started_at else 0.0
                label = f"{emoji} **{w.tool_name}**"
                if w.method:
                    label += f".{w.method}"
                label += f"  •  `{w.task_id}`"
                with st.container():
                    st.markdown(label)
                    sub1, sub2 = st.columns(2)
                    sub1.caption(f"State: {w.state.value.upper()}")
                    sub2.caption(f"Elapsed: {_format_elapsed(elapsed)}")

    # ------------------------------------------------------------------ #
    # Tools used panel                                                     #
    # ------------------------------------------------------------------ #
    with right:
        st.subheader("Tools Used")
        if stats["tools_used"]:
            for tool in stats["tools_used"]:
                st.markdown(f"- `{tool}`")
        else:
            st.caption("None yet.")

    st.divider()

    # ------------------------------------------------------------------ #
    # Recent history table                                                 #
    # ------------------------------------------------------------------ #
    st.subheader("Recent Task History")
    if not history:
        st.info("No completed tasks yet.")
    else:
        import pandas as pd

        rows = []
        for w in history:
            rows.append({
                "Status": _STATE_EMOJI.get(w.state, "?"),
                "Tool": w.tool_name,
                "Method": w.method or "—",
                "Task ID": w.task_id[:8],
                "Elapsed": _format_elapsed(w.elapsed_s),
                "Error": (w.error or "")[:60],
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

    # ------------------------------------------------------------------ #
    # Auto-refresh                                                         #
    # ------------------------------------------------------------------ #
    if auto_refresh:
        time.sleep(3)
        st.rerun()


def _render_demo_placeholder() -> None:
    """Show a static demo layout when no tracker is available."""
    st.subheader("Preview (no live data)")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🟢 Running", "—")
    c2.metric("✅ Completed", "—")
    c3.metric("❌ Errors", "—")
    c4.metric("⚠️ Stalled", "—")
    c5.metric("⏱ Avg Time", "—")
    st.caption("Attach a WorkerTracker to see live swarm data.")
