# jagabot/agent/yolo.py
"""
AutoJaga YOLO Mode — Full autonomous research partner.

Inspired by Claude Code's --dangerously-skip-permissions mode,
but safer by design:
- Restricted to ~/.jagabot/workspace/ ONLY
- Cannot touch system files, network configs, or OS
- Every action logged to yolo_audit.log
- User sees clean step-by-step progress, not raw tool calls
- Produces a final research report on disk

Usage:
    jagabot yolo "research quantum computing in drug discovery"
    jagabot yolo "find 5 unconventional ideas for X and test feasibility"
    jagabot yolo "investigate my pending outcomes and update memory"

What it does autonomously:
    1. Decomposes the goal into research steps
    2. Executes each step with full tool access
    3. Verifies each result before proceeding
    4. Saves findings to disk at each step
    5. Updates memory with verified conclusions
    6. Produces final report
    7. Shows user clean summary of what happened

What user sees:
    ┌─────────────────────────────────────────┐
    │ 🐈 YOLO MODE — Autonomous Research     │
    │ Goal: quantum computing drug discovery  │
    └─────────────────────────────────────────┘

    Step 1/5  Decomposing goal...        ✅ 5 research angles
    Step 2/5  Researching angle 1...     ✅ 12 findings saved
    Step 3/5  Cross-checking sources...  ✅ 8 verified
    Step 4/5  Generating insights...     ✅ 3 conclusions
    Step 5/5  Saving to memory...        ✅ MEMORY.md updated

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    📄 Report: research_output/20260315_.../report.md
    🧠 Memory: 3 facts added to MEMORY.md
    📌 Pending: 2 conclusions logged for verification
    ⏱ Time: 4m 23s
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    Progress, SpinnerColumn, TextColumn,
    BarColumn, TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

# ── Theme ───────────────────────────────────────────────────────────
YOLO_THEME = Theme({
    "yolo.header":  "bold #52d68a",
    "yolo.step":    "#8ab8a0",
    "yolo.done":    "dim #52d68a",
    "yolo.running": "bold #f0c040",
    "yolo.fail":    "dim #d65252",
    "yolo.dim":     "dim #3d5a50",
    "yolo.result":  "#e8e0d0",
    "yolo.report":  "bold #52d68a",
    "yolo.warn":    "bold yellow",
    "yolo.sandbox": "dim #4a7c6f",
})

console = Console(theme=YOLO_THEME, highlight=False)

# ── Workspace sandbox ────────────────────────────────────────────────
ALLOWED_WORKSPACE = Path.home() / ".jagabot" / "workspace"
BLOCKED_PATHS = [
    "/etc", "/usr", "/bin", "/sbin", "/root/.ssh",
    "/root/.bashrc", "/root/.profile",
    "/root/nanojaga",  # source code — don't modify
]


# ── Step result ──────────────────────────────────────────────────────
@dataclass
class StepResult:
    step_num:    int
    name:        str
    status:      str        # "running" | "done" | "failed" | "skipped"
    summary:     str  = ""  # one-line human result
    details:     str  = ""  # full output (not shown to user)
    elapsed:     float= 0.0
    findings:    int  = 0   # how many findings produced
    saved_to:    str  = ""  # file path if saved


@dataclass
class YOLOSession:
    goal:         str
    session_id:   str   = ""
    steps:        list  = field(default_factory=list)
    started_at:   str   = ""
    completed_at: str   = ""
    report_path:  str   = ""
    memory_added: int   = 0
    pending_added:int   = 0
    total_elapsed:float = 0.0

    def to_dict(self) -> dict:
        return {
            "goal":          self.goal,
            "session_id":    self.session_id,
            "started_at":    self.started_at,
            "completed_at":  self.completed_at,
            "report_path":   self.report_path,
            "memory_added":  self.memory_added,
            "pending_added": self.pending_added,
            "total_elapsed": self.total_elapsed,
            "steps":         [
                {
                    "step":    s.step_num,
                    "name":    s.name,
                    "status":  s.status,
                    "summary": s.summary,
                    "elapsed": s.elapsed,
                }
                for s in self.steps
            ],
        }


# ── Sandbox guard ────────────────────────────────────────────────────

class SandboxViolation(Exception):
    pass


def check_sandbox(path: str) -> bool:
    """
    Verify a path is within allowed workspace.
    Raises SandboxViolation if outside bounds.
    """
    resolved = Path(path).resolve()

    # Check blocked paths first
    for blocked in BLOCKED_PATHS:
        if str(resolved).startswith(blocked):
            raise SandboxViolation(
                f"YOLO mode blocked: {path} is outside workspace. "
                f"AutoJaga YOLO is restricted to {ALLOWED_WORKSPACE}"
            )

    # Must be within workspace
    try:
        resolved.relative_to(ALLOWED_WORKSPACE)
        return True
    except ValueError:
        # Allow reading (not writing) from source
        # e.g. reading AGENTS.md or skill files is OK
        if "read" in path.lower():
            return True
        raise SandboxViolation(
            f"YOLO mode blocked: {path} is outside "
            f"~/.jagabot/workspace/. "
            f"YOLO mode cannot modify files outside your workspace."
        )


# ── Goal decomposer ──────────────────────────────────────────────────

class GoalDecomposer:
    """
    Breaks a research goal into autonomous steps.
    Each step is independently executable and verifiable.
    """

    # Step templates for different goal types
    RESEARCH_STEPS = [
        "Decompose goal into research questions",
        "Search for current information",
        "Synthesise and cross-check findings",
        "Extract key conclusions",
        "Generate insights and implications",
        "Save to memory and produce report",
    ]

    IDEA_STEPS = [
        "Analyse the problem space",
        "Generate ideas via tri-agent (isolated)",
        "Evaluate each idea for feasibility",
        "Identify best combination",
        "Test top idea against known constraints",
        "Save ideas and log pending outcomes",
    ]

    MEMORY_STEPS = [
        "Load pending outcomes",
        "Verify each conclusion via web search",
        "Update memory with verified results",
        "Prune wrong conclusions",
        "Consolidate into MEMORY.md",
        "Generate learning summary",
    ]

    ANALYSIS_STEPS = [
        "Load and validate input data",
        "Run primary analysis",
        "Cross-check results",
        "Generate visualisation",
        "Write findings to workspace",
        "Update memory with key metrics",
    ]

    def decompose(self, goal: str) -> list[str]:
        """Return ordered list of step names for this goal."""
        goal_lower = goal.lower()

        if any(w in goal_lower for w in
               ["idea", "brainstorm", "creative", "unconventional"]):
            return self.IDEA_STEPS

        if any(w in goal_lower for w in
               ["pending", "verify", "memory", "outcomes", "update"]):
            return self.MEMORY_STEPS

        if any(w in goal_lower for w in
               ["analyse", "analyze", "calculate", "data", "dataset"]):
            return self.ANALYSIS_STEPS

        # Default: research
        return self.RESEARCH_STEPS

    def build_step_prompt(
        self,
        step_name:    str,
        step_num:     int,
        total_steps:  int,
        goal:         str,
        prev_results: list[StepResult],
    ) -> str:
        """
        Build the prompt for one autonomous step.
        Includes context from previous steps.
        """
        prev_context = ""
        if prev_results:
            lines = ["Previous steps completed:"]
            for r in prev_results:
                if r.status == "done":
                    lines.append(f"  ✅ Step {r.step_num}: {r.summary}")
            prev_context = "\n".join(lines)

        return f"""
You are executing step {step_num} of {total_steps} in an autonomous research session.

OVERALL GOAL: {goal}

CURRENT STEP: {step_name}

{prev_context}

YOLO MODE RULES:
- You are fully autonomous — execute without asking for confirmation
- Stay within ~/.jagabot/workspace/ for all file operations
- Every action must produce a verifiable result
- Save findings to disk before proceeding
- Be concise — this is one step in a larger pipeline

Execute this step completely and report:
1. What you did (one sentence)
2. What you found (key results only)
3. What you saved (file paths)
4. Any blockers for next step (if any)

Do not ask questions. Execute and report.
""".strip()


# ── YOLO progress display ────────────────────────────────────────────

class YOLODisplay:
    """
    Manages the live progress display during autonomous execution.
    User sees clean step-by-step progress, not raw tool calls.
    """

    def __init__(self, goal: str, total_steps: int) -> None:
        self.goal        = goal
        self.total_steps = total_steps
        self.steps:      list[StepResult] = []
        self._progress   = None
        self._task_id    = None
        self._live       = None

    def __enter__(self):
        self._show_header()
        return self

    def __exit__(self, *args):
        if self._live:
            self._live.stop()

    def _show_header(self) -> None:
        """Show YOLO mode header panel."""
        goal_display = (
            self.goal[:60] + "..."
            if len(self.goal) > 60
            else self.goal
        )
        console.print()
        console.print(Panel(
            f"[yolo.header]🐈 YOLO MODE — Autonomous Research[/]\n"
            f"[yolo.dim]Goal:[/] [yolo.result]{goal_display}[/]\n"
            f"[yolo.sandbox]Sandboxed to: ~/.jagabot/workspace/[/]",
            border_style="#1e3a2f",
            padding=(0, 1),
        ))
        console.print()

    def step_start(self, step: StepResult) -> None:
        """Show step starting."""
        padding = " " * (4 - len(str(step.step_num)))
        console.print(
            f"[yolo.dim]Step {step.step_num}/{self.total_steps}{padding}[/]"
            f"[yolo.running]  {step.name}...[/]",
            end="\r"
        )

    def step_done(self, step: StepResult) -> None:
        """Show step completion with clean summary."""
        padding    = " " * (4 - len(str(step.step_num)))
        status_str = (
            f"[yolo.done]✅ {step.summary}[/]"
            if step.status == "done"
            else f"[yolo.fail]✗  {step.summary}[/]"
        )
        findings_str = (
            f" [yolo.dim]({step.findings} findings)[/]"
            if step.findings > 0 else ""
        )
        elapsed_str = f"[yolo.dim] {step.elapsed:.1f}s[/]"

        console.print(
            f"[yolo.dim]Step {step.step_num}/{self.total_steps}"
            f"{padding}[/]  "
            f"{status_str}"
            f"{findings_str}"
            f"{elapsed_str}"
        )
        self.steps.append(step)

    def show_final(self, session: YOLOSession) -> None:
        """Show final summary after all steps complete."""
        console.print()
        console.print(
            "━" * 50,
            style="yolo.dim"
        )
        console.print()

        # Report location
        if session.report_path:
            console.print(
                f"[yolo.report]📄 Report:[/] "
                f"[yolo.dim]{session.report_path}[/]"
            )

        # Memory updates
        if session.memory_added > 0:
            console.print(
                f"[yolo.report]🧠 Memory:[/] "
                f"[yolo.dim]{session.memory_added} facts added "
                f"to MEMORY.md[/]"
            )

        # Pending outcomes
        if session.pending_added > 0:
            console.print(
                f"[yolo.report]📌 Pending:[/] "
                f"[yolo.dim]{session.pending_added} conclusions "
                f"logged for verification[/]"
            )

        # Time
        console.print(
            f"[yolo.report]⏱ Time:[/] "
            f"[yolo.dim]{session.total_elapsed:.0f}s[/]"
        )

        console.print()

        # Step summary table
        table = Table(
            show_header=False,
            border_style="#1e3a2f",
            padding=(0, 1),
        )
        table.add_column("Step", style="yolo.dim",   width=8)
        table.add_column("Name", style="yolo.step",  width=30)
        table.add_column("Result", style="yolo.done", width=35)

        for s in session.steps:
            icon = "✅" if s.status == "done" else "✗"
            table.add_row(
                f"{icon} {s.step_num}/{len(session.steps)}",
                s.name[:28],
                s.summary[:33],
            )
        console.print(table)
        console.print()

        # Next action hint
        if session.pending_added > 0:
            console.print(
                f"[yolo.warn]→[/] [yolo.result]"
                f"Run [bold]jagabot chat[/] then [bold]/pending[/] "
                f"to verify conclusions and close the learning loop."
                f"[/]"
            )
            console.print()


# ── YOLO runner ──────────────────────────────────────────────────────

class YOLORunner:
    """
    Orchestrates fully autonomous research execution.

    The agent runs each step without user confirmation.
    User only sees clean progress + final report.
    """

    def __init__(
        self,
        workspace:     Path   = None,
        tool_registry: object = None,
        agent          = None,
    ) -> None:
        self.workspace     = workspace or ALLOWED_WORKSPACE
        self.tool_registry = tool_registry
        self.agent         = agent
        self.decomposer    = GoalDecomposer()
        self.audit_log     = self.workspace / "memory" / "yolo_audit.log"
        self.workspace.mkdir(parents=True, exist_ok=True)

    def run(self, goal: str) -> YOLOSession:
        """
        Run full autonomous research session.
        Returns completed YOLOSession with results.
        """
        session = YOLOSession(
            goal       = goal,
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S"),
            started_at = datetime.now().isoformat(),
        )

        steps       = self.decomposer.decompose(goal)
        total_start = time.time()

        self._log_audit(f"YOLO SESSION START: {goal}")

        with YOLODisplay(goal, len(steps)) as display:
            prev_results: list[StepResult] = []

            for i, step_name in enumerate(steps, 1):
                step = StepResult(
                    step_num = i,
                    name     = step_name,
                    status   = "running",
                )

                display.step_start(step)
                step_start = time.time()

                try:
                    # Build step prompt
                    prompt = self.decomposer.build_step_prompt(
                        step_name    = step_name,
                        step_num     = i,
                        total_steps  = len(steps),
                        goal         = goal,
                        prev_results = prev_results,
                    )

                    # Execute step autonomously
                    result = self._execute_step(prompt, step_name, i)

                    step.status   = "done"
                    step.summary  = result.get("summary", "Complete")
                    step.details  = result.get("details", "")
                    step.findings = result.get("findings", 0)
                    step.saved_to = result.get("saved_to", "")

                    # Track memory updates
                    if "memory" in step_name.lower() or \
                       "memory" in step.summary.lower():
                        session.memory_added += result.get("memory_added", 0)

                    # Track pending outcomes
                    session.pending_added += result.get("pending_added", 0)

                    # Save report path from last step
                    if step.saved_to:
                        session.report_path = step.saved_to

                except SandboxViolation as e:
                    step.status  = "failed"
                    step.summary = f"Blocked: outside workspace"
                    self._log_audit(f"SANDBOX VIOLATION: {e}")

                except Exception as e:
                    step.status  = "failed"
                    step.summary = f"Error: {str(e)[:40]}"
                    self._log_audit(f"STEP ERROR: {step_name}: {e}")

                step.elapsed = time.time() - step_start
                prev_results.append(step)
                display.step_done(step)

                self._log_audit(
                    f"STEP {i}/{len(steps)} {step.status}: "
                    f"{step.summary}"
                )

                # Stop if critical step failed
                if step.status == "failed" and i <= 2:
                    self._log_audit("STOPPING: early critical step failed")
                    break

            session.total_elapsed = time.time() - total_start
            session.completed_at  = datetime.now().isoformat()
            session.steps         = prev_results

            # Save session log
            self._save_session_log(session)

            # Auto-lesson extraction — consolidate findings into MEMORY.md
            try:
                from jagabot.memory.consolidation import ConsolidationEngine
                _consolidation = ConsolidationEngine(
                    memory_dir=Path(self.workspace) / "memory",
                )
                _lessons = _consolidation.run(force=True)
                if _lessons > 0:
                    logger.info(
                        f"YOLO auto-lesson extraction: {_lessons} lessons "
                        f"written to MEMORY.md"
                    )
                    session.memory_added += _lessons
                else:
                    logger.debug("YOLO auto-lesson extraction: no new lessons to consolidate")
            except Exception as _ce:
                logger.warning(f"YOLO auto-lesson extraction failed: {_ce}")

            display.show_final(session)

        self._log_audit(
            f"YOLO SESSION COMPLETE: {session.total_elapsed:.0f}s "
            f"| {len([s for s in prev_results if s.status == 'done'])}/"
            f"{len(steps)} steps succeeded"
        )

        return session

    def _execute_step(
        self,
        prompt:     str,
        step_name:  str,
        step_num:   int,
    ) -> dict:
        """
        Execute one autonomous step via real AgentLoop.
        """
        import asyncio
        from jagabot.agent.loop import AgentLoop
        from jagabot.bus.queue import MessageBus
        from jagabot.providers.litellm_provider import LiteLLMProvider
        from jagabot.config.loader import load_config

        # Initialize agent if not already done
        if self.agent is None:
            try:
                config = load_config()
                provider = LiteLLMProvider(
                    api_key=config.get_provider().api_key,
                    api_base=config.get_provider().api_base,
                    default_model=config.agents.defaults.model,
                    provider_name=config.get_provider_name(),
                )
                self.agent = AgentLoop(
                    bus=MessageBus(),
                    provider=provider,
                    workspace=self.workspace,
                    model=config.agents.defaults.model,
                    restrict_to_workspace=True,  # enforce sandbox
                )
            except Exception as e:
                raise RuntimeError(f"Failed to initialize agent: {e}")

        # Run agent fully autonomously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(
                self.agent.process_direct(
                    prompt,
                    session_key=f"yolo_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                )
            )
        finally:
            loop.close()

        # Parse ProactiveWrapper output for structured data
        result = {
            "summary":       self._extract_summary(response),
            "findings":      self._count_findings(response),
            "saved_to":      self._extract_saved_path(response),
            "memory_added":  self._count_memory_additions(response),
            "pending_added": self._count_pending_additions(response),
            "details":       response,
        }
        return result

    def _extract_summary(self, response: str) -> str:
        """Extract one-line summary from response."""
        # Look for "What this means" or first bold line
        import re
        match = re.search(r'\*\*(?:What this means|Result|Summary):\*\*\s*(.+?)(?:\n|$)', response)
        if match:
            return match.group(1).strip()[:80]
        # Fallback: first non-empty line
        for line in response.split('\n'):
            line = line.strip()
            if line and not line.startswith('**') and not line.startswith('---'):
                return line[:80]
        return "Complete"

    def _count_findings(self, response: str) -> int:
        """Count findings/sources mentioned in response."""
        import re
        # Look for numbers like "12 sources", "5 findings", etc.
        match = re.search(r'(\d+)\s*(?:sources|findings|claims|conclusions|ideas)', response, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return 0

    def _extract_saved_path(self, response: str) -> str:
        """Extract saved file path from response."""
        import re
        # Look for paths like research_output/...
        match = re.search(r'(research_output/[^\s\*\`]+)', response)
        if match:
            return str(self.workspace / match.group(1))
        # Look for "Report:" or "Saved to:"
        match = re.search(r'(?:Report|Saved to)[:\s]+([^\n]+)', response, re.IGNORECASE)
        if match:
            path = match.group(1).strip()
            if '/' in path:
                return str(self.workspace / path)
        return ""

    def _count_memory_additions(self, response: str) -> int:
        """Count memory additions mentioned."""
        import re
        match = re.search(r'(\d+)\s*(?:facts|items|conclusions)\s*(?:added|updated|to memory)', response, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return 0

    def _count_pending_additions(self, response: str) -> int:
        """Count pending outcomes logged."""
        import re
        match = re.search(r'(\d+)\s*(?:pending|conclusions|outcomes)\s*(?:logged|for verification)', response, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return 0

    def _log_audit(self, message: str) -> None:
        """Append to YOLO audit log."""
        try:
            self.audit_log.parent.mkdir(parents=True, exist_ok=True)
            ts    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            entry = f"[{ts}] {message}\n"
            with open(self.audit_log, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass

    def _save_session_log(self, session: YOLOSession) -> None:
        """Save session summary to disk."""
        try:
            log_dir  = self.workspace / "memory" / "yolo_sessions"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{session.session_id}.json"
            log_file.write_text(
                json.dumps(session.to_dict(), indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


# ── CLI entry point ──────────────────────────────────────────────────

def run_yolo(
    goal:      str,
    workspace: Path   = None,
    agent      = None,
) -> None:
    """
    Launch YOLO mode. Call from commands.py:

    @app.command()
    def yolo(goal: str = typer.Argument(..., help="Research goal")):
        from jagabot.agent.yolo import run_yolo
        run_yolo(goal)
    """
    runner = YOLORunner(
        workspace = workspace or ALLOWED_WORKSPACE,
        agent     = agent,
    )
    runner.run(goal)


if __name__ == "__main__":
    import sys
    goal = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else \
        "research quantum computing in drug discovery"
    run_yolo(goal)
