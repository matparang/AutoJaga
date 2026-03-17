# jagabot/cli/tui.py
"""
AutoJaga TUI — Full terminal interface.
Built with Textual. Split layout: chat always visible,
panels toggle with keyboard shortcuts.

Install: pip install textual --break-system-packages

Run: python -m jagabot.cli.tui
  or: jagabot tui
"""

from __future__ import annotations

import asyncio
import json
import random
from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import (
    Footer,
    Header,
    Input,
    Label,
    Log,
    Markdown,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
)
from textual.timer import Timer


# ── Palette ────────────────────────────────────────────────────────
# Dark terminal aesthetic — amber/green on near-black
# Feels like a real research terminal, not a web app

JAGABOT_CSS = """
/* ── Root ──────────────────────────────────────── */
Screen {
    background: #0a0a0f;
    color: #e8e0d0;
}

/* ── Header bar ────────────────────────────────── */
#header-bar {
    height: 3;
    background: #0d1117;
    border-bottom: solid #1e3a2f;
    padding: 0 2;
    layout: horizontal;
    content-align: left middle;
}

#header-title {
    color: #52d68a;
    text-style: bold;
    width: auto;
    padding: 0 2 0 0;
}

#header-model {
    color: #4a7c6f;
    width: auto;
    padding: 0 2;
}

#header-status {
    color: #52d68a;
    width: auto;
    padding: 0 2;
}

#header-time {
    dock: right;
    color: #3d5a50;
    width: auto;
    padding: 0 2;
}

/* ── Main split layout ──────────────────────────── */
#main-layout {
    layout: horizontal;
    height: 1fr;
}

/* ── Left panel (toggleable) ────────────────────── */
#left-panel {
    width: 32;
    min-width: 32;
    background: #0d1117;
    border-right: solid #1e3a2f;
    display: block;
}

#left-panel.hidden {
    display: none;
}

/* ── Chat area (always visible) ─────────────────── */
#chat-area {
    width: 1fr;
    layout: vertical;
    background: #0a0a0f;
}

#chat-log {
    height: 1fr;
    background: #0a0a0f;
    border: none;
    padding: 1 2;
    scrollbar-color: #1e3a2f #0a0a0f;
}

#input-bar {
    height: 3;
    background: #0d1117;
    border-top: solid #1e3a2f;
    layout: horizontal;
    padding: 0 1;
}

#prompt-label {
    color: #52d68a;
    width: auto;
    content-align: left middle;
    padding: 0 1;
}

#chat-input {
    width: 1fr;
    background: #0d1117;
    color: #e8e0d0;
    border: none;
}

#chat-input:focus {
    border: none;
    outline: none;
}

/* ── Right panel (toggleable) ───────────────────── */
#right-panel {
    width: 38;
    min-width: 38;
    background: #0d1117;
    border-left: solid #1e3a2f;
    display: block;
}

#right-panel.hidden {
    display: none;
}

/* ── Panel sections ─────────────────────────────── */
.panel-section {
    border-bottom: solid #1a2a24;
    padding: 1 1 0 1;
    height: auto;
}

.panel-title {
    color: #3d8a60;
    text-style: bold;
    padding: 0 0 1 0;
}

/* ── Agent status ───────────────────────────────── */
.agent-row {
    height: 1;
    layout: horizontal;
}

.agent-name {
    width: 14;
    color: #8ab8a0;
}

.agent-dot {
    width: 3;
}

.agent-dot.active {
    color: #52d68a;
}

.agent-dot.idle {
    color: #2a4a38;
}

.agent-dot.error {
    color: #d65252;
}

.agent-info {
    width: 1fr;
    color: #4a6a5a;
}

/* ── Tool execution ─────────────────────────────── */
#tool-log {
    height: 12;
    background: #0d1117;
    padding: 0 1;
    scrollbar-color: #1e3a2f #0d1117;
}

/* ── Swarm monitor ──────────────────────────────── */
.worker-row {
    height: 1;
    layout: horizontal;
}

.worker-label {
    width: 10;
    color: #6a8a7a;
}

.worker-bar {
    width: 1fr;
    color: #52d68a;
}

.worker-bar.idle {
    color: #1e3a2f;
}

/* ── Output browser ─────────────────────────────── */
#output-list {
    height: 10;
    padding: 0 1;
    scrollbar-color: #1e3a2f #0d1117;
}

.output-item {
    height: 1;
    color: #4a7c6f;
}

.output-item:hover {
    color: #52d68a;
    background: #0f1f18;
}

/* ── Session history ────────────────────────────── */
#history-list {
    height: 8;
    padding: 0 1;
}

.history-item {
    height: 1;
    color: #3d5a50;
}

/* ── Chat messages ──────────────────────────────── */
.msg-user {
    color: #8ab8ff;
    padding: 0 0 0 0;
}

.msg-agent {
    color: #e8e0d0;
    padding: 0 0 1 2;
}

.msg-system {
    color: #3d8a60;
    padding: 0 0 1 0;
    text-style: italic;
}

.msg-tool {
    color: #4a6a5a;
    padding: 0 0 0 2;
}

.msg-error {
    color: #d65252;
    padding: 0 0 0 2;
}

.msg-timestamp {
    color: #2a3a30;
}

/* ── Footer ─────────────────────────────────────── */
Footer {
    background: #0d1117;
    color: #3d5a50;
    border-top: solid #1e3a2f;
}
"""


# ── Widgets ────────────────────────────────────────────────────────

class HeaderBar(Static):
    """Top status bar showing agent identity and state."""

    model_name: reactive[str] = reactive("Qwen-Plus")
    status: reactive[str] = reactive("READY")
    is_thinking: reactive[bool] = reactive(False)

    def compose(self) -> ComposeResult:
        yield Static("🐈 JAGABOT", id="header-title")
        yield Static("", id="header-model")
        yield Static("", id="header-status")
        yield Static("", id="header-time")

    def on_mount(self) -> None:
        self.update_time_timer = self.set_interval(1.0, self._update_time)
        self._update_model()
        self._update_status()

    def _update_time(self) -> None:
        try:
            self.query_one("#header-time", Static).update(
                datetime.now().strftime("%H:%M:%S")
            )
        except NoMatches:
            pass

    def _update_model(self) -> None:
        try:
            self.query_one("#header-model", Static).update(
                f"[ {self.model_name} ]"
            )
        except NoMatches:
            pass

    def _update_status(self) -> None:
        try:
            dot = "⣾" if self.is_thinking else "●"
            color = "thinking" if self.is_thinking else "ready"
            self.query_one("#header-status", Static).update(
                f"{dot} {self.status}"
            )
        except NoMatches:
            pass

    def set_thinking(self, thinking: bool) -> None:
        self.is_thinking = thinking
        self.status = "THINKING..." if thinking else "READY"
        self._update_status()


class AgentStatusPanel(Static):
    """Left panel section: agent kernel health."""

    AGENTS = [
        ("K1 Bayesian",  "active",  "calibrated"),
        ("K3 Perspect",  "active",  "3 views"),
        ("K7 Eval",      "idle",    "standby"),
        ("MetaLearn",    "active",  "tracking"),
        ("Evolution",    "idle",    "standby"),
        ("MemoryFleet",  "active",  "3 layers"),
        ("TriAgent",     "idle",    "ready"),
        ("QuadAgent",    "idle",    "ready"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("AGENT STATUS", classes="panel-title")
        for name, state, info in self.AGENTS:
            dot = "●" if state == "active" else "○"
            dot_class = f"agent-dot {state}"
            with Horizontal(classes="agent-row"):
                yield Static(name, classes="agent-name")
                yield Static(dot, classes=dot_class)
                yield Static(info, classes="agent-info")

    def set_agent_state(self, name: str, state: str, info: str = "") -> None:
        """Update a specific agent's display state."""
        # Re-render on state change
        self.refresh()


class ToolExecutionPanel(Static):
    """Left panel section: live tool call log."""

    def compose(self) -> ComposeResult:
        yield Static("TOOL EXECUTION", classes="panel-title")
        yield RichLog(id="tool-log", highlight=True, markup=True)

    def log_tool(
        self,
        tool: str,
        status: str = "running",
        elapsed: float = 0.0,
    ) -> None:
        try:
            log = self.query_one("#tool-log", RichLog)
            ts = datetime.now().strftime("%H:%M:%S")
            if status == "running":
                icon = "[yellow]▶[/yellow]"
            elif status == "done":
                icon = "[green]✅[/green]"
            elif status == "failed":
                icon = "[red]✗[/red]"
            else:
                icon = "[dim]·[/dim]"

            elapsed_str = f"{elapsed:.1f}s" if elapsed > 0 else "..."
            log.write(
                f"[dim]{ts}[/dim] {icon} [cyan]{tool}[/cyan] "
                f"[dim]{elapsed_str}[/dim]"
            )
        except NoMatches:
            pass


class SwarmMonitor(Static):
    """Right panel section: swarm worker activity bars."""

    WORKERS = 4
    worker_states: reactive[list] = reactive(
        [0.0, 0.0, 0.0, 0.0]
    )

    def compose(self) -> ComposeResult:
        yield Static("SWARM MONITOR", classes="panel-title")
        for i in range(self.WORKERS):
            with Horizontal(classes="worker-row"):
                yield Static(f"Worker {i+1}", classes="worker-label")
                yield Static("░░░░░░░░░░░░", classes="worker-bar idle", id=f"worker-{i}")

    def set_worker(self, idx: int, progress: float) -> None:
        """Update worker progress bar (0.0 - 1.0)."""
        try:
            bar = self.query_one(f"#worker-{idx}", Static)
            filled = int(progress * 12)
            empty = 12 - filled
            if progress > 0:
                bar.update("█" * filled + "░" * empty)
                bar.remove_class("idle")
                bar.add_class("active")
            else:
                bar.update("░" * 12)
                bar.remove_class("active")
                bar.add_class("idle")
        except NoMatches:
            pass

    def clear_all(self) -> None:
        for i in range(self.WORKERS):
            self.set_worker(i, 0.0)


class OutputBrowser(Static):
    """Right panel section: browse saved research outputs."""

    def compose(self) -> ComposeResult:
        yield Static("RESEARCH OUTPUTS", classes="panel-title")
        outputs = self._load_recent_outputs()
        with ScrollableContainer(id="output-list"):
            if outputs:
                for name, ts in outputs:
                    yield Static(
                        f"[dim]{ts}[/dim] {name}",
                        classes="output-item"
                    )
            else:
                yield Static(
                    "[dim]No outputs yet[/dim]",
                    classes="output-item"
                )

    def _load_recent_outputs(self) -> list[tuple[str, str]]:
        """Load recent research output folders."""
        output_dir = Path.home() / ".jagabot" / "workspace" / "research_output"
        if not output_dir.exists():
            return []
        folders = sorted(output_dir.iterdir(), reverse=True)[:8]
        results = []
        for f in folders:
            if f.is_dir():
                # Parse timestamp from folder name (20260315_094049_topic)
                parts = f.name.split("_", 2)
                if len(parts) >= 2:
                    try:
                        ts = datetime.strptime(
                            f"{parts[0]}_{parts[1]}", "%Y%m%d_%H%M%S"
                        ).strftime("%H:%M")
                        topic = parts[2][:20] if len(parts) > 2 else "session"
                        results.append((topic, ts))
                    except ValueError:
                        results.append((f.name[:24], ""))
        return results

    def refresh_outputs(self) -> None:
        """Reload output list."""
        try:
            container = self.query_one("#output-list", ScrollableContainer)
            container.remove_children()
            outputs = self._load_recent_outputs()
            for name, ts in outputs:
                container.mount(
                    Static(f"[dim]{ts}[/dim] {name}", classes="output-item")
                )
        except NoMatches:
            pass


class SessionHistory(Static):
    """Right panel section: recent session queries."""

    def compose(self) -> ComposeResult:
        yield Static("SESSION HISTORY", classes="panel-title")
        history = self._load_history()
        with ScrollableContainer(id="history-list"):
            if history:
                for item in history:
                    yield Static(item, classes="history-item")
            else:
                yield Static(
                    "[dim]No history yet[/dim]",
                    classes="history-item"
                )

    def _load_history(self) -> list[str]:
        """Load recent queries from session files."""
        session_dir = Path.home() / ".jagabot" / "sessions"
        if not session_dir.exists():
            return []
        results = []
        files = sorted(session_dir.glob("*.jsonl"), reverse=True)[:3]
        for f in files:
            try:
                lines = f.read_text().strip().split("\n")
                for line in reversed(lines[-10:]):
                    try:
                        msg = json.loads(line)
                        if msg.get("role") == "user":
                            content = msg.get("content", "")[:28]
                            results.append(f"› {content}")
                            if len(results) >= 6:
                                return results
                    except Exception:
                        pass
            except Exception:
                pass
        return results


class ChatLog(ScrollableContainer):
    """Main chat display area."""

    def add_user(self, text: str) -> None:
        ts = datetime.now().strftime("%H:%M")
        self.mount(Static(
            f"[dim]{ts}[/dim] [bold #8ab8ff]You:[/bold #8ab8ff] {text}",
            classes="msg-user"
        ))
        self.scroll_end(animate=False)

    def add_agent(self, text: str) -> None:
        ts = datetime.now().strftime("%H:%M")
        # Truncate very long responses for display
        display = text[:800] + "..." if len(text) > 800 else text
        self.mount(Static(
            f"[dim]{ts}[/dim] [bold #52d68a]🐈 jagabot:[/bold #52d68a]\n"
            f"  {display}",
            classes="msg-agent"
        ))
        self.scroll_end(animate=False)

    def add_tool(self, tool: str, status: str = "running") -> None:
        icon = "▶" if status == "running" else "✅" if status == "done" else "✗"
        self.mount(Static(
            f"  [dim]{icon} {tool}...[/dim]",
            classes="msg-tool"
        ))
        self.scroll_end(animate=False)

    def add_system(self, text: str) -> None:
        self.mount(Static(
            f"[dim italic]{text}[/dim italic]",
            classes="msg-system"
        ))
        self.scroll_end(animate=False)

    def add_error(self, text: str) -> None:
        self.mount(Static(
            f"  [red]⚠ {text}[/red]",
            classes="msg-error"
        ))
        self.scroll_end(animate=False)


# ── Main App ───────────────────────────────────────────────────────

class JagabotTUI(App):
    """
    AutoJaga Terminal UI.
    Split layout: chat always visible, panels toggle.
    """

    CSS = JAGABOT_CSS
    TITLE = "jagabot"
    SUB_TITLE = "autonomous research partner"

    BINDINGS = [
        Binding("ctrl+l", "toggle_left",  "Left Panel",  show=True),
        Binding("ctrl+r", "toggle_right", "Right Panel", show=True),
        Binding("ctrl+o", "open_output",  "Open Output", show=True),
        Binding("ctrl+s", "show_swarm",   "Swarm",       show=True),
        Binding("ctrl+c", "quit",         "Quit",        show=True),
    ]

    left_visible: reactive[bool] = reactive(True)
    right_visible: reactive[bool] = reactive(True)
    thinking: reactive[bool] = reactive(False)

    def compose(self) -> ComposeResult:
        # Header
        with Horizontal(id="header-bar"):
            yield Static("🐈 JAGABOT", id="header-title")
            yield Static(f"[ Qwen-Plus ]", id="header-model")
            yield Static("● READY", id="header-status")
            yield Static(
                datetime.now().strftime("%H:%M:%S"),
                id="header-time"
            )

        # Main layout
        with Horizontal(id="main-layout"):

            # Left panel — agent status + tool execution
            with Vertical(id="left-panel"):
                with Container(classes="panel-section"):
                    yield AgentStatusPanel()
                with Container(classes="panel-section"):
                    yield ToolExecutionPanel()

            # Chat — always visible
            with Vertical(id="chat-area"):
                yield ChatLog(id="chat-log")
                with Horizontal(id="input-bar"):
                    yield Static("›", id="prompt-label")
                    yield Input(
                        placeholder="Ask jagabot anything...",
                        id="chat-input"
                    )

            # Right panel — swarm + outputs + history
            with Vertical(id="right-panel"):
                with Container(classes="panel-section"):
                    yield SwarmMonitor()
                with Container(classes="panel-section"):
                    yield OutputBrowser()
                with Container(classes="panel-section"):
                    yield SessionHistory()

        yield Footer()

    def on_mount(self) -> None:
        """Initialize TUI on startup."""
        self.query_one("#chat-input", Input).focus()
        self._time_timer = self.set_interval(1.0, self._tick_time)

        # Welcome message
        chat = self.query_one("#chat-log", ChatLog)
        chat.add_system(
            "jagabot v0.1.3 · autonomous research partner · "
            "Ctrl+L toggle left · Ctrl+R toggle right · Ctrl+C quit"
        )
        chat.add_system(
            "Type your research question below. "
            "Use quad_agent or tri_agent for deep exploration."
        )

    def _tick_time(self) -> None:
        try:
            self.query_one("#header-time", Static).update(
                datetime.now().strftime("%H:%M:%S")
            )
        except NoMatches:
            pass

    # ── Input handling ─────────────────────────────────────────────

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user pressing Enter in chat input."""
        query = event.value.strip()
        if not query:
            return

        # Clear input
        self.query_one("#chat-input", Input).value = ""

        # Show user message
        chat = self.query_one("#chat-log", ChatLog)
        chat.add_user(query)

        # Set thinking state
        self._set_thinking(True)

        # Process in background
        asyncio.create_task(self._process_query(query))

    async def _process_query(self, query: str) -> None:
        """
        Send query to jagabot agent and display response.
        Replace this with your actual agent call.
        """
        chat = self.query_one("#chat-log", ChatLog)
        tool_panel = self.query_one(ToolExecutionPanel)
        swarm = self.query_one(SwarmMonitor)

        try:
            # ── Connect to your actual agent here ──────────────────
            # Replace this block with your real agent call:
            #
            # from jagabot.agent.loop import AgentLoop
            # response = await self.agent.process(query)
            #
            # The simulation below shows the TUI working correctly.
            # ───────────────────────────────────────────────────────

            response = await self._call_agent(query, chat, tool_panel, swarm)
            chat.add_agent(response)

            # Refresh output browser after response
            self.query_one(OutputBrowser).refresh_outputs()

        except Exception as e:
            chat.add_error(f"Agent error: {e}")
        finally:
            self._set_thinking(False)
            swarm.clear_all()

    async def _call_agent(
        self,
        query: str,
        chat: ChatLog,
        tool_panel: ToolExecutionPanel,
        swarm: SwarmMonitor,
    ) -> str:
        """
        Agent call stub — replace with real agent integration.

        To wire to real jagabot:
        1. Import your AgentLoop
        2. Hook tool_panel.log_tool() into ToolHarness callbacks
        3. Hook swarm.set_worker() into WorkerPool callbacks
        4. Return final_content from _process_message()
        """
        # ── STUB: simulate agent thinking ──────────────────────────
        # Remove this entire method body when wiring to real agent

        tools_to_show = self._guess_tools(query)

        for i, tool in enumerate(tools_to_show):
            chat.add_tool(tool, "running")
            tool_panel.log_tool(tool, "running")
            # Animate swarm workers for multi-agent tasks
            if "agent" in tool:
                for w in range(4):
                    swarm.set_worker(w, (w + 1) / 4)
                    await asyncio.sleep(0.1)
            await asyncio.sleep(0.4)
            tool_panel.log_tool(tool, "done", elapsed=0.4)

        await asyncio.sleep(0.5)

        return (
            f"✅ Research complete.\n\n"
            f"Query: *{query[:60]}*\n\n"
            f"**Wire `_call_agent()` to your real AgentLoop** to see "
            f"actual responses here. The TUI is fully functional — "
            f"just replace the stub in `tui.py → _call_agent()`."
        )

    def _guess_tools(self, query: str) -> list[str]:
        """Guess likely tools for display — replace with real hooks."""
        q = query.lower()
        if any(w in q for w in ["idea", "brainstorm", "creative"]):
            return ["tri_agent", "quad_agent", "meta_learning"]
        elif any(w in q for w in ["calculate", "compute", "data"]):
            return ["exec", "write_file", "read_file"]
        elif any(w in q for w in ["research", "search"]):
            return ["web_search", "researcher", "memory_fleet"]
        else:
            return ["memory_fleet", "k3_perspective"]

    # ── Panel toggles ──────────────────────────────────────────────

    def action_toggle_left(self) -> None:
        panel = self.query_one("#left-panel")
        if "hidden" in panel.classes:
            panel.remove_class("hidden")
            self.left_visible = True
        else:
            panel.add_class("hidden")
            self.left_visible = False

    def action_toggle_right(self) -> None:
        panel = self.query_one("#right-panel")
        if "hidden" in panel.classes:
            panel.remove_class("hidden")
            self.right_visible = True
        else:
            panel.add_class("hidden")
            self.right_visible = False

    def action_open_output(self) -> None:
        """Open most recent research output in system viewer."""
        output_dir = (
            Path.home() / ".jagabot" / "workspace" / "research_output"
        )
        if output_dir.exists():
            folders = sorted(output_dir.iterdir(), reverse=True)
            if folders:
                import subprocess
                report = folders[0] / "report.md"
                if report.exists():
                    subprocess.Popen(["less", str(report)])

    def action_show_swarm(self) -> None:
        """Flash swarm panel to draw attention."""
        swarm = self.query_one(SwarmMonitor)
        for i in range(4):
            swarm.set_worker(i, random.random())

    def _set_thinking(self, thinking: bool) -> None:
        """Update header status during agent processing."""
        self.thinking = thinking
        try:
            status = self.query_one("#header-status", Static)
            if thinking:
                status.update("⣾ THINKING...")
                self._think_timer = self.set_interval(
                    0.1, self._spin_indicator
                )
            else:
                if hasattr(self, "_think_timer"):
                    self._think_timer.stop()
                status.update("● READY")
        except NoMatches:
            pass

    _spin_frames = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]
    _spin_idx = 0

    def _spin_indicator(self) -> None:
        try:
            status = self.query_one("#header-status", Static)
            frame = self._spin_frames[self._spin_idx % len(self._spin_frames)]
            self._spin_idx += 1
            status.update(f"{frame} THINKING...")
        except NoMatches:
            pass


# ── Entry point ────────────────────────────────────────────────────

def run_tui() -> None:
    """Launch the TUI. Call from CLI commands."""
    app = JagabotTUI()
    app.run()


if __name__ == "__main__":
    run_tui()
