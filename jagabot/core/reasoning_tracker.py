"""
ReasoningTracker — surfaces agent thinking to CLI in real-time.

Hooks into tool_harness callbacks to show:
  🔍 Fetching NVDA quote...
  ✅ Got price: $178.56 (1.6s)
  📊 Running Monte Carlo simulation...
  ✅ Simulation complete (0.3s)
  🧠 Analyzing risk...
  ✅ Analysis done

Only active when verbose=True or JAGABOT_VERBOSE=1
"""

from __future__ import annotations
import time
import os
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger

# Tool display icons
TOOL_ICONS = {
    "yahoo_finance":      "📈",
    "web_search_mcp":     "🔍",
    "web_search":         "🌐",
    "memory_fleet":       "🧠",
    "monte_carlo":        "🎲",
    "financial_cv":       "📊",
    "decision_engine":    "⚖️",
    "read_file":          "📄",
    "write_file":         "💾",
    "exec":               "⚙️",
    "spawn":              "🚀",
    "self_model_awareness": "🪞",
    "stress_test":        "🔬",
    "var":                "📉",
    "cvar":               "📉",
    "early_warning":      "⚠️",
    "researcher":         "📚",
}

PHASE_MESSAGES = {
    "data_fetch":  "📥 Fetching data",
    "analysis":    "📊 Analyzing",
    "synthesis":   "🔗 Synthesizing findings",
    "output":      "✍️  Preparing response",
    "init":        "🚀 Starting",
}


@dataclass
class ReasoningStep:
    """One step in the reasoning chain."""
    tool:       str
    status:     str    # "running" | "done" | "failed"
    started_at: float  = field(default_factory=time.time)
    ended_at:   float  = 0.0
    detail:     str    = ""

    @property
    def elapsed(self) -> str:
        if self.ended_at:
            return f"{self.ended_at - self.started_at:.1f}s"
        return f"{time.time() - self.started_at:.1f}s"


class ReasoningTracker:
    """
    Tracks and displays agent reasoning steps in real-time.
    Hooks into tool_harness on_start/on_done callbacks.
    """

    def __init__(self, verbose: bool = False):
        self.verbose    = verbose or os.getenv("JAGABOT_VERBOSE", "0") == "1"
        self._steps:    dict[str, ReasoningStep] = {}
        self._phase:    str = "init"
        self._turn_id:  str = ""
        self._tool_count: int = 0
        self._start_time: float = time.time()

    def start_turn(self, query: str, complexity: str = "STANDARD") -> None:
        """Called at start of each turn."""
        self._steps.clear()
        self._tool_count = 0
        self._start_time = time.time()
        self._turn_id    = str(int(time.time()))

        if self.verbose:
            icon = "🔬" if complexity == "RESEARCH" else "💭" if complexity == "COMPLEX" else "⚡"
            print(f"\n{icon} [{complexity}] Processing: {query[:60]}{'...' if len(query) > 60 else ''}")

    def on_tool_start(self, tool_name: str, tool_id: str, args: dict = None) -> None:
        """Called when a tool starts executing."""
        self._tool_count += 1
        step = ReasoningStep(tool=tool_name, status="running")
        self._steps[tool_id] = step

        if self.verbose:
            icon  = TOOL_ICONS.get(tool_name, "🔧")
            label = self._get_tool_label(tool_name, args or {})
            print(f"  {icon} {label}...", end="", flush=True)

    def on_tool_done(self, tool_name: str, tool_id: str, result: str = "", elapsed: float = 0) -> None:
        """Called when a tool completes."""
        if tool_id in self._steps:
            self._steps[tool_id].status   = "done"
            self._steps[tool_id].ended_at = time.time()
            self._steps[tool_id].detail   = result[:80] if result else ""

        if self.verbose:
            summary = self._get_result_summary(tool_name, result)
            print(f" ✅ {summary} ({elapsed:.1f}s)")

    def on_tool_fail(self, tool_name: str, tool_id: str, error: str = "") -> None:
        """Called when a tool fails."""
        if tool_id in self._steps:
            self._steps[tool_id].status   = "failed"
            self._steps[tool_id].ended_at = time.time()

        if self.verbose:
            print(f" ❌ {error[:60]}")

    def update_phase(self, phase: str) -> None:
        """Update current reasoning phase."""
        if phase != self._phase and self.verbose:
            msg = PHASE_MESSAGES.get(phase, f"→ {phase}")
            if phase not in ("init", "data_fetch"):  # skip first two
                print(f"  {msg}...")
        self._phase = phase

    def finish_turn(self, response_preview: str = "") -> None:
        """Called when turn completes."""
        if self.verbose:
            elapsed = time.time() - self._start_time
            tools   = self._tool_count
            print(f"  ✨ Done ({elapsed:.1f}s, {tools} tool{'s' if tools != 1 else ''})")

    def _get_tool_label(self, tool_name: str, args: dict) -> str:
        """Get human-readable label for a tool call."""
        if tool_name == "yahoo_finance":
            ticker = args.get("ticker", "?")
            action = args.get("action", "quote")
            labels = {"quote": f"Getting {ticker} price", "news": f"Fetching {ticker} news",
                      "history": f"Loading {ticker} history", "financials": f"Pulling {ticker} financials"}
            return labels.get(action, f"Yahoo Finance: {ticker}")
        elif tool_name in ("web_search_mcp", "web_search"):
            q = args.get("query", "")[:40]
            return f"Searching: {q}"
        elif tool_name == "memory_fleet":
            action = args.get("action", "retrieve")
            q = args.get("query", "")[:30]
            return f"Memory {action}: {q}" if q else f"Memory {action}"
        elif tool_name == "monte_carlo":
            return "Running Monte Carlo simulation"
        elif tool_name == "exec":
            cmd = args.get("command", "")[:40]
            return f"Executing: {cmd}"
        elif tool_name == "read_file":
            path = args.get("path", "")
            return f"Reading: {path.split('/')[-1]}"
        return tool_name.replace("_", " ").title()

    def _get_result_summary(self, tool_name: str, result: str) -> str:
        """Get compact result summary."""
        if not result:
            return "done"
        if tool_name == "yahoo_finance":
            import re
            price = re.search(r'"price":\s*([\d.]+)', result)
            if price:
                return f"${price.group(1)}"
        if tool_name in ("web_search_mcp", "web_search"):
            count = result.count('"title"') or result.count('\n')
            return f"{min(count, 10)} results"
        if tool_name == "monte_carlo":
            import re
            prob = re.search(r'probability["\s:]+([0-9.]+)', result, re.IGNORECASE)
            return f"prob={prob.group(1)}" if prob else "done"
        return "done"

    def get_summary(self) -> dict:
        """Return summary of reasoning steps."""
        return {
            "tool_count": self._tool_count,
            "steps":      [{"tool": s.tool, "status": s.status, "elapsed": s.elapsed}
                           for s in self._steps.values()],
            "phase":      self._phase,
        }
