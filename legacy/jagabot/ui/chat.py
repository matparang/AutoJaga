"""JAGABOT Chat — conversational interface (Streamlit 6th tab).

v3.6: Interactive chat with query classification, pipeline execution,
inline dashboards, and conversation history.
v3.7: Optional local voice integration (STT/TTS) with graceful degradation.

Uses SubagentManager for full pipeline and ParallelLab for focused
tool workflows. All state lives in ``st.session_state``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["render_chat"]

# Voice availability (safe — never raises)
try:
    from jagabot.voice import VOICE_AVAILABLE
except Exception:
    VOICE_AVAILABLE = False

# ------------------------------------------------------------------
# Query classification keywords
# ------------------------------------------------------------------

_KEYWORDS: dict[str, list[str]] = {
    "portfolio": ["portfolio", "posisi", "modal", "equity", "margin", "leveraj", "leverage"],
    "risk": ["risk", "risiko", "var", "cvar", "stress", "volatil", "vix", "drawdown"],
    "fund_manager": ["fund manager", "advisor", "broker", "penasihat", "pengurus dana"],
    "general": ["hello", "hi", "hey", "thank", "terima kasih", "help", "tolong", "apa boleh"],
}

# Maps query types → ParallelLab workflows for focused analysis
_QUERY_WORKFLOWS: dict[str, str] = {
    "portfolio": "portfolio_review",
    "risk": "risk_analysis",
}


def classify_query(query: str) -> str:
    """Classify a user query into a category.

    Returns one of: ``portfolio``, ``risk``, ``fund_manager``,
    ``general``, or ``unknown``.
    """
    q = query.lower()
    for category, keywords in _KEYWORDS.items():
        if any(kw in q for kw in keywords):
            return category
    return "unknown"


def format_tool_results(stage_results: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract a flat list of tool execution summaries from pipeline output.

    Works with both ``execute_workflow`` (stage-keyed) and
    ``execute_batch`` / ``submit_and_execute`` (results-keyed) output.
    """
    tools: list[dict[str, Any]] = []

    # ParallelLab / batch results
    if "results" in stage_results:
        for r in stage_results["results"]:
            task = r.get("task", {})
            tools.append({
                "name": task.get("tool", r.get("tool", "?")),
                "success": r.get("success", False),
                "duration": r.get("execution_time", 0),
            })
        return tools

    # SubagentManager pipeline results (stage-keyed)
    for stage_name in ("websearch", "tools", "models", "reasoning"):
        stage = stage_results.get(stage_name, {})
        if not isinstance(stage, dict):
            continue
        # ToolsStage puts results under various keys
        for key in ("tool_results", "results"):
            items = stage.get(key, [])
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        tools.append({
                            "name": item.get("tool", stage_name),
                            "success": item.get("success", True),
                            "duration": item.get("execution_time", 0),
                        })
        # If stage itself has success flag but no nested results
        if not tools and stage.get("success") is not None:
            tools.append({
                "name": stage_name,
                "success": stage.get("success", False),
                "duration": stage.get("execution_time", stage.get("elapsed_s", 0)),
            })

    return tools


def format_dashboard_metrics(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract key-value metrics from tool results for st.metric display.

    Returns list of ``{"label": ..., "value": ...}`` dicts.
    """
    metrics: list[dict[str, Any]] = []

    # Batch results → extract from each tool output
    for r in result.get("results", []):
        output = r.get("output", {})
        if isinstance(output, dict):
            tool_name = r.get("task", {}).get("tool", r.get("tool", ""))
            for k, v in output.items():
                if isinstance(v, (int, float)):
                    metrics.append({"label": f"{tool_name}: {k}", "value": v})
                elif isinstance(v, str) and len(v) < 60:
                    metrics.append({"label": f"{tool_name}: {k}", "value": v})

    # Pipeline results → scan stages
    for stage_name in ("tools", "models", "reasoning"):
        stage = result.get(stage_name, {})
        if isinstance(stage, dict):
            for k, v in stage.items():
                if k in ("success", "stage", "error"):
                    continue
                if isinstance(v, (int, float)):
                    metrics.append({"label": f"{stage_name}: {k}", "value": v})

    # Limit to top 12 for readability
    return metrics[:12]


def _run_async(coro: Any) -> Any:
    """Run an async coroutine safely (works inside Streamlit's event loop)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result(timeout=60)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def _process_query(query: str, context: dict[str, Any]) -> dict[str, Any]:
    """Process a user query and return structured response.

    Returns ``{"message": str, "dashboard": list|None, "tools": list|None}``.
    """
    start = time.monotonic()
    qtype = classify_query(query)

    try:
        if qtype in _QUERY_WORKFLOWS:
            result = _run_focused_workflow(qtype, query, context)
        elif qtype == "fund_manager":
            result = _run_fund_manager_check(query, context)
        elif qtype == "general":
            result = _handle_general(query)
        else:
            result = _run_pipeline(query, context)
    except Exception as exc:
        logger.error("Chat query processing failed: %s", exc)
        result = {
            "message": f"⚠️ Maaf, terjadi masalah: {exc}",
            "dashboard": None,
            "tools": None,
        }

    elapsed = round(time.monotonic() - start, 2)
    result.setdefault("message", "")
    result["message"] += f"\n\n_⏱️ {elapsed}s_"
    return result


def _run_focused_workflow(
    qtype: str, query: str, context: dict[str, Any],
) -> dict[str, Any]:
    """Run a ParallelLab workflow for portfolio/risk queries."""
    from jagabot.subagents.manager import SubagentManager

    workflow = _QUERY_WORKFLOWS[qtype]
    mgr = SubagentManager()
    data = dict(context)
    data["query"] = query

    result = _run_async(mgr.run_parallel_analysis(workflow, data))

    tools = format_tool_results(result)
    dashboard = format_dashboard_metrics(result)

    completed = result.get("completed", 0)
    total = result.get("total", 0)
    wall = result.get("wall_time", 0)

    if qtype == "portfolio":
        msg = (
            f"✅ **Analisis portfolio selesai** ({completed}/{total} tools, {wall}s)\n\n"
            "Berikut ringkasan hasil analisis:"
        )
    else:
        msg = (
            f"✅ **Analisis risiko selesai** ({completed}/{total} tools, {wall}s)\n\n"
            "Berikut ringkasan risiko portfolio anda:"
        )

    return {"message": msg, "dashboard": dashboard, "tools": tools}


def _run_fund_manager_check(
    query: str, context: dict[str, Any],
) -> dict[str, Any]:
    """Run full pipeline for fund manager verification queries."""
    from jagabot.subagents.manager import SubagentManager

    mgr = SubagentManager()
    data = dict(context)
    data["query"] = query

    result = _run_async(mgr.execute_workflow(query, data))

    tools = format_tool_results(result)
    dashboard = format_dashboard_metrics(result)
    success = result.get("success", False)

    if success:
        msg = (
            "🔍 **Semakan fund manager selesai.**\n\n"
            "JAGABOT telah analisis dakwaan fund manager anda "
            "menggunakan pipeline penuh (WebSearch → Tools → Models → Reasoning)."
        )
    else:
        failed = result.get("failed_stage", "unknown")
        msg = f"⚠️ Pipeline terhenti di stage **{failed}**. Sila cuba lagi."

    return {"message": msg, "dashboard": dashboard, "tools": tools}


def _run_pipeline(query: str, context: dict[str, Any]) -> dict[str, Any]:
    """Run full SubagentManager pipeline for unknown/complex queries."""
    from jagabot.subagents.manager import SubagentManager

    mgr = SubagentManager()
    data = dict(context)
    data["query"] = query

    result = _run_async(mgr.execute_workflow(query, data))

    tools = format_tool_results(result)
    dashboard = format_dashboard_metrics(result)
    success = result.get("success", False)

    if success:
        msg = "✅ **Analisis selesai.** Berikut hasilnya:"
    else:
        failed = result.get("failed_stage", "unknown")
        msg = f"⚠️ Pipeline terhenti di stage **{failed}**."

    return {"message": msg, "dashboard": dashboard, "tools": tools}


def _handle_general(query: str) -> dict[str, Any]:
    """Handle greetings and general questions without running tools."""
    q = query.lower()
    if any(w in q for w in ("hello", "hi", "hey")):
        msg = (
            "👋 Hai! Saya **JAGABOT**, Financial Guardian anda.\n\n"
            "Saya boleh bantu dengan:\n"
            "- 📊 **Analisis portfolio** — \"Check portfolio modal 1.5M\"\n"
            "- ⚠️ **Analisis risiko** — \"Apa risiko VaR saya?\"\n"
            "- 🔍 **Semakan fund manager** — \"Fund manager kata risiko sederhana\"\n"
            "- 💡 **Soalan umum** — apa sahaja berkaitan kewangan"
        )
    elif any(w in q for w in ("thank", "terima kasih")):
        msg = "🙏 Sama-sama! Ada apa lagi yang saya boleh bantu?"
    elif any(w in q for w in ("help", "tolong")):
        msg = (
            "💡 **Cara menggunakan JAGABOT Chat:**\n\n"
            "1. Taip soalan anda di bawah\n"
            "2. JAGABOT akan jalankan tools yang sesuai\n"
            "3. Hasil muncul sebagai dashboard inline\n\n"
            "Contoh: _\"Analisis portfolio minyak modal 1.5M dengan leveraj 2.5\"_"
        )
    else:
        msg = "👋 Ada apa yang saya boleh bantu hari ini?"

    return {"message": msg, "dashboard": None, "tools": None}


# ------------------------------------------------------------------
# Streamlit render function
# ------------------------------------------------------------------

def render_chat() -> None:
    """Render the JAGABOT Chat tab inside Streamlit."""
    try:
        import streamlit as st
    except ImportError:
        return

    # Initialize session state
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": (
                "👋 Hai! Saya **JAGABOT**, Financial Guardian anda. "
                "Ada apa yang saya boleh bantu?"
            ),
            "time": datetime.now(),
            "dashboard": None,
            "tools": None,
        })

    if "chat_context" not in st.session_state:
        st.session_state.chat_context = {}

    st.header("💬 Chat dengan JAGABOT")
    st.caption("Tanya soalan kewangan — JAGABOT akan jalankan analisis secara automatik.")

    # Voice toggle (only shown when voice deps are installed)
    voice_enabled = False
    if VOICE_AVAILABLE:
        voice_enabled = st.checkbox("🎤 Voice", value=False, key="chat_voice_toggle")
        if voice_enabled:
            _init_voice_session(st)

    # Sidebar info
    with st.sidebar:
        st.subheader("💬 Chat Info")
        st.metric("Messages", len(st.session_state.chat_messages))
        if VOICE_AVAILABLE:
            st.caption(f"🎤 Voice: {'ON' if voice_enabled else 'OFF'}")
        else:
            st.caption("🎤 Voice: not installed")
        if st.button("🧹 Clear Chat"):
            st.session_state.chat_messages = [{
                "role": "assistant",
                "content": "👋 Chat cleared. Ada apa yang saya boleh bantu?",
                "time": datetime.now(),
                "dashboard": None,
                "tools": None,
            }]
            st.session_state.chat_context = {}
            st.rerun()

    # Display chat history
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

            # Inline dashboard metrics
            dashboard = msg.get("dashboard")
            if dashboard:
                st.markdown("---")
                cols = st.columns(min(len(dashboard), 4))
                for i, m in enumerate(dashboard):
                    with cols[i % len(cols)]:
                        st.metric(m["label"], m["value"])

            # Tool execution summary
            tools = msg.get("tools")
            if tools:
                with st.expander("🔧 Tool Executions", expanded=False):
                    for t in tools:
                        status = "✅" if t["success"] else "❌"
                        dur = t.get("duration", 0)
                        st.text(f"{status} {t['name']}: {dur:.2f}s")

            # Timestamp
            ts = msg.get("time")
            if ts:
                st.caption(f"🕒 {ts:%H:%M:%S}")

    # Voice input controls
    if voice_enabled:
        _render_voice_controls(st)

    # Chat input
    prompt = st.chat_input("Tanya JAGABOT apa sahaja...")

    if prompt:
        _handle_text_input(st, prompt, voice_enabled)


# ------------------------------------------------------------------
# Voice helpers (v3.7)
# ------------------------------------------------------------------

def _init_voice_session(st: Any) -> None:
    """Lazily create VoiceService in session state."""
    if "voice_service" not in st.session_state:
        from jagabot.voice import VoiceService, VoiceConfig
        st.session_state["voice_service"] = VoiceService(VoiceConfig())


def _render_voice_controls(st: Any) -> None:
    """Render microphone push-to-talk buttons."""
    vs = st.session_state.get("voice_service")
    if vs is None:
        return

    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("🎤 Mula Rakam", key="voice_start", use_container_width=True):
            started = vs.start_recording()
            if started:
                st.session_state["voice_recording"] = True
                st.info("🔴 Sedang merakam... tekan Berhenti bila selesai.")
            else:
                st.warning("⚠️ Tidak dapat memulakan rakaman.")
    with col2:
        if st.button("⏹️ Berhenti", key="voice_stop", use_container_width=True):
            if st.session_state.get("voice_recording"):
                text = vs.transcribe_recording()
                st.session_state["voice_recording"] = False
                if text:
                    st.success(f"📝 Transkripsi: {text}")
                    _handle_text_input(st, f"🎤 {text}", voice_enabled=True)
                else:
                    st.warning("⚠️ Tiada pertuturan dikesan.")

    # Status indicator
    status = vs.get_status()
    with col3:
        if st.session_state.get("voice_recording"):
            st.markdown("🔴 **Merakam...**")
        elif status["stt_available"]:
            st.markdown(f"🎤 Sedia ({status['language'].upper()})")
        else:
            st.markdown("⚠️ Model STT tidak tersedia")


def _handle_text_input(st: Any, prompt: str, voice_enabled: bool = False) -> None:
    """Process a text prompt (from keyboard or voice) and display response."""
    # Add user message
    user_msg = {
        "role": "user",
        "content": prompt,
        "time": datetime.now(),
    }
    st.session_state.chat_messages.append(user_msg)

    # Show user message
    with st.chat_message("user"):
        st.markdown(prompt)

    # Process & respond
    with st.chat_message("assistant"):
        with st.spinner("JAGABOT sedang berfikir..."):
            response = _process_query(prompt, st.session_state.chat_context)

        st.markdown(response["message"])

        dashboard = response.get("dashboard")
        if dashboard:
            st.markdown("---")
            cols = st.columns(min(len(dashboard), 4))
            for i, m in enumerate(dashboard):
                with cols[i % len(cols)]:
                    st.metric(m["label"], m["value"])

        tools = response.get("tools")
        if tools:
            with st.expander("🔧 Tool Executions", expanded=False):
                for t in tools:
                    status_icon = "✅" if t["success"] else "❌"
                    dur = t.get("duration", 0)
                    st.text(f"{status_icon} {t['name']}: {dur:.2f}s")

    # TTS — speak response if voice is enabled
    if voice_enabled:
        vs = st.session_state.get("voice_service")
        if vs and vs.tts_available:
            # Strip markdown for cleaner speech
            plain = response["message"].replace("**", "").replace("_", "").replace("#", "")
            vs.synthesize(plain)

    # Persist assistant message
    assistant_msg = {
        "role": "assistant",
        "content": response["message"],
        "time": datetime.now(),
        "dashboard": dashboard,
        "tools": tools,
    }
    st.session_state.chat_messages.append(assistant_msg)
