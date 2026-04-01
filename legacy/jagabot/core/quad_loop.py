"""
Quad-Agent Isolated Swarm — Planner / Worker / Verifier / Adversary.

Extends the Tri-Agent pattern with a 4th Planner agent that provides
strategic adaptation. Each agent operates in an isolated sandbox
subdirectory with role-appropriate tool restrictions.

Protocol per cycle:
  1. Planner   → Analyzes task (cycle 1) or failure history → emits strategy
  2. Worker    → Executes per strategy (sandbox: worker_out/)
  3. Verifier  → Checks worker_out/ independently (read-only)
  4. If fail   → Planner adapts strategy → next cycle
  5. Adversary → Attacks copy of worker_out/ (sandbox: adversary_out/)
  6. Worker    → Repairs from adversary report
  7. Verifier  → Re-checks after repair
  8. All pass  → SUCCESS
"""

from __future__ import annotations

import asyncio
import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from jagabot.providers.base import LLMProvider

_AGENT_MAX_ITERATIONS = 10
_AGENT_TIMEOUT = 240  # was 120 — Qwen-Plus needs ~3-4 min for complex tasks


# ── System prompts ───────────────────────────────────────────────

_PLANNER_PROMPT = """\
You are PLANNER, a strategic coordination agent. Your job is to analyze \
the task and produce a clear execution plan for the WORKER agent.

RULES:
- Break the task into numbered steps
- Specify expected outputs (filenames, content format)
- If given FAILURE HISTORY, analyze what went wrong and adapt the strategy
- Focus on concrete, actionable instructions — no vague suggestions
- Do NOT execute anything yourself — only plan

Respond with a JSON plan:
{"strategy": "high-level approach", "steps": ["step1", "step2", ...], \
"expected_files": ["file1.txt", ...], "adaptations": "what changed from last attempt"}
"""

_WORKER_PROMPT = """\
You are WORKER, a task execution agent. Your job is to complete the assigned \
task accurately using the tools available to you.

RULES:
- Follow the PLANNER's strategy exactly
- Actually execute actions using tools (write_file, exec, etc.)
- Do NOT claim to have done something without using a tool
- Save all outputs to files in the workspace
- Report exactly what you did and what files you created
- If given REPAIR instructions, fix the issues described

Respond with a JSON summary:
{"status": "done", "files_created": [...], "summary": "..."}
"""

_VERIFIER_PROMPT = """\
You are VERIFIER, an independent verification agent. Your job is to check \
whether the WORKER's claimed results actually exist and are correct.

RULES:
- NEVER trust the worker's claims — verify everything from files
- Use read_file and list_dir to check all claimed files exist
- Read file contents and verify they match claimed results
- If the worker claimed statistics/computations, recompute from raw data
- You have READ-ONLY access — do not create or modify files

Respond with a JSON summary:
{"passed": true/false, "files_checked": [...], "mismatches": [...], "notes": "..."}
"""

_ADVERSARY_PROMPT = """\
You are ADVERSARY, a robustness testing agent. Your job is to intentionally \
break things in the workspace to test if the system can recover.

RULES:
- Pick ONE attack from: delete a file, corrupt a line, insert invalid data
- Only attack DATA files — never delete all files or destroy structure
- Report exactly what you did so the worker can attempt repair
- Be creative but proportional — test resilience, not cause catastrophe

Respond with a JSON summary:
{"attack": "description", "target": "filename", "details": "what was changed"}
"""


@dataclass
class QuadCycleLog:
    """Log of one quad-agent cycle."""
    cycle: int
    strategy: str = ""
    worker_result: str = ""
    verification_result: str = ""
    verification_passed: bool = False
    adversary_result: str = ""
    repair_result: str = ""
    repair_verified: bool = False


@dataclass
class QuadAgentResult:
    """Final result of the quad-agent loop."""
    status: str           # SUCCESS | PARTIAL | FAILURE
    cycles: int
    result: str           # Final worker output
    strategies: list[str] = field(default_factory=list)
    log: list[QuadCycleLog] = field(default_factory=list)
    elapsed: float = 0.0


class QuadAgentLoop:
    """
    Orchestrates Planner -> Worker -> Verifier -> Adversary cycles.

    Each agent operates in its own sandbox subdirectory with
    role-appropriate tool restrictions.
    """

    def __init__(
        self,
        provider: "LLMProvider",
        workspace: Path,
        model: str | None = None,
        max_cycles: int = 3,
        restrict_to_workspace: bool = True,
    ) -> None:
        self.provider = provider
        self.workspace = workspace
        self.model = model
        self.max_cycles = max_cycles
        self.restrict_to_workspace = restrict_to_workspace

    async def run(self, task: str) -> QuadAgentResult:
        """Execute the full quad-agent verification loop."""
        start = time.time()
        logs: list[QuadCycleLog] = []
        strategies: list[str] = []
        last_worker_result = ""

        # Create per-agent sandbox directories
        sandbox_root = self.workspace / "quad_agent_sandbox"
        worker_dir = sandbox_root / "worker_out"
        adversary_dir = sandbox_root / "adversary_out"
        for d in (worker_dir, adversary_dir):
            d.mkdir(parents=True, exist_ok=True)

        try:
            for cycle in range(1, self.max_cycles + 1):
                clog = QuadCycleLog(cycle=cycle)
                logger.info(f"Quad-agent cycle {cycle}/{self.max_cycles}")

                # ── 1. Planner creates / adapts strategy ─────────
                failure_history = self._build_failure_history(logs)
                if cycle == 1:
                    planner_msg = (
                        f"TASK:\n{task}\n\n"
                        f"Create a detailed execution plan for the WORKER agent. "
                        f"Specify exactly what files to create and what each should contain."
                    )
                else:
                    planner_msg = (
                        f"TASK:\n{task}\n\n"
                        f"FAILURE HISTORY (previous {cycle - 1} cycle(s)):\n"
                        f"{failure_history}\n\n"
                        f"Analyze what went wrong and create an ADAPTED strategy. "
                        f"Be specific about what to change."
                    )

                clog.strategy = await self._call_agent(
                    "planner", _PLANNER_PROMPT, planner_msg, sandbox_root,
                )
                strategies.append(clog.strategy)
                logger.info(f"Quad-agent cycle {cycle}: planner strategy ready")

                # ── 2. Worker executes per strategy ──────────────
                worker_msg = (
                    f"PLANNER STRATEGY:\n{clog.strategy}\n\n"
                    f"ORIGINAL TASK:\n{task}\n\n"
                    f"Execute the plan. Save all files to the current workspace directory."
                )
                if cycle > 1 and logs:
                    prev = logs[-1]
                    if not prev.verification_passed:
                        worker_msg += (
                            f"\n\nPREVIOUS VERIFICATION FEEDBACK:\n"
                            f"{prev.verification_result}\n"
                            f"Fix the issues identified above."
                        )

                clog.worker_result = await self._call_agent(
                    "worker", _WORKER_PROMPT, worker_msg, worker_dir,
                )
                last_worker_result = clog.worker_result
                logger.info(f"Quad-agent cycle {cycle}: worker done")

                # ── 3. Verifier checks worker output ─────────────
                verify_msg = (
                    f"The WORKER claims:\n{clog.worker_result}\n\n"
                    f"Original task: {task}\n\n"
                    f"Verify by reading actual files. Check existence and correctness."
                )
                clog.verification_result = await self._call_agent(
                    "verifier", _VERIFIER_PROMPT, verify_msg, worker_dir,
                )
                clog.verification_passed = _parse_passed(clog.verification_result)

                if not clog.verification_passed:
                    logger.warning(f"Quad-agent cycle {cycle}: verification FAILED")
                    logs.append(clog)
                    continue  # Planner will adapt next cycle

                logger.info(f"Quad-agent cycle {cycle}: verification PASSED")

                # ── 4. Copy worker output for adversary isolation ─
                # Adversary attacks a COPY, not the live workspace
                if adversary_dir.exists():
                    shutil.rmtree(adversary_dir)
                shutil.copytree(worker_dir, adversary_dir)

                # ── 5. Adversary attacks the copy ────────────────
                adversary_msg = (
                    f"The WORKER created these artifacts:\n{clog.worker_result}\n\n"
                    f"Attack ONE data file to test robustness. "
                    f"Choose: delete it, corrupt a line, or insert invalid data."
                )
                clog.adversary_result = await self._call_agent(
                    "adversary", _ADVERSARY_PROMPT, adversary_msg, adversary_dir,
                )
                logger.info(f"Quad-agent cycle {cycle}: adversary attacked")

                # ── 6. Worker repairs from adversary report ──────
                repair_msg = (
                    f"ADVERSARY ATTACK REPORT:\n{clog.adversary_result}\n\n"
                    f"PLANNER STRATEGY:\n{clog.strategy}\n\n"
                    f"Original task: {task}\n\n"
                    f"Detect the damage and repair. Ensure all files are correct."
                )
                clog.repair_result = await self._call_agent(
                    "worker", _WORKER_PROMPT, repair_msg, worker_dir,
                )

                # ── 7. Verifier re-checks after repair ───────────
                recheck_msg = (
                    f"After an adversary attack, the WORKER repaired:\n"
                    f"{clog.repair_result}\n\n"
                    f"Original task: {task}\n\n"
                    f"Re-verify everything. Check all files exist and are correct."
                )
                recheck_result = await self._call_agent(
                    "verifier", _VERIFIER_PROMPT, recheck_msg, worker_dir,
                )
                clog.repair_verified = _parse_passed(recheck_result)

                logs.append(clog)

                if clog.repair_verified:
                    logger.info(f"Quad-agent: SUCCESS after {cycle} cycle(s)")
                    return QuadAgentResult(
                        status="SUCCESS",
                        cycles=cycle,
                        result=last_worker_result,
                        strategies=strategies,
                        log=logs,
                        elapsed=time.time() - start,
                    )

                logger.warning(f"Quad-agent cycle {cycle}: repair verification FAILED")

            # Max cycles exhausted
            return QuadAgentResult(
                status="PARTIAL",
                cycles=self.max_cycles,
                result=last_worker_result,
                strategies=strategies,
                log=logs,
                elapsed=time.time() - start,
            )

        except Exception as e:
            logger.error(f"Quad-agent loop error: {e}")
            return QuadAgentResult(
                status="FAILURE",
                cycles=len(logs),
                result=f"Error: {e}",
                strategies=strategies,
                log=logs,
                elapsed=time.time() - start,
            )
        finally:
            try:
                if sandbox_root.exists():
                    shutil.rmtree(sandbox_root)
            except Exception as e:
                logger.debug(f"Sandbox cleanup failed: {e}")

    # ── Agent call ───────────────────────────────────────────────

    async def _call_agent(
        self,
        role: str,
        system_prompt: str,
        user_message: str,
        sandbox: Path,
    ) -> str:
        """Run a single agent (LLM + tool loop) and return its response."""
        from jagabot.agent.tools.registry import ToolRegistry
        from jagabot.agent.tools.filesystem import (
            ReadFileTool, WriteFileTool, EditFileTool, ListDirTool,
        )
        from jagabot.agent.tools.shell import ExecTool

        tools = ToolRegistry()
        allowed_dir = sandbox if self.restrict_to_workspace else None

        if role == "planner":
            # Planner gets read-only access to see what exists
            tools.register(ReadFileTool(allowed_dir=allowed_dir))
            tools.register(ListDirTool(allowed_dir=allowed_dir))
        elif role == "worker":
            tools.register(ReadFileTool(allowed_dir=allowed_dir))
            tools.register(WriteFileTool(allowed_dir=allowed_dir))
            tools.register(EditFileTool(allowed_dir=allowed_dir))
            tools.register(ListDirTool(allowed_dir=allowed_dir))
            tools.register(ExecTool(
                working_dir=str(sandbox), timeout=30,
                restrict_to_workspace=self.restrict_to_workspace,
            ))
        elif role == "verifier":
            tools.register(ReadFileTool(allowed_dir=allowed_dir))
            tools.register(ListDirTool(allowed_dir=allowed_dir))
            tools.register(ExecTool(
                working_dir=str(sandbox), timeout=15,
                restrict_to_workspace=self.restrict_to_workspace,
            ))
        elif role == "adversary":
            # Data-only: file ops but no exec
            tools.register(ReadFileTool(allowed_dir=allowed_dir))
            tools.register(WriteFileTool(allowed_dir=allowed_dir))
            tools.register(EditFileTool(allowed_dir=allowed_dir))
            tools.register(ListDirTool(allowed_dir=allowed_dir))

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        async def _loop() -> str | None:
            for _ in range(_AGENT_MAX_ITERATIONS):
                response = await self.provider.chat(
                    messages=messages,
                    tools=tools.get_definitions(),
                    model=self.model,
                )

                if response.has_tool_calls:
                    tool_call_dicts = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in response.tool_calls
                    ]
                    messages.append({
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": tool_call_dicts,
                    })

                    for tc in response.tool_calls:
                        result = await tools.execute(tc.name, tc.arguments)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "name": tc.name,
                            "content": result,
                        })
                else:
                    return response.content

            return None

        try:
            result = await asyncio.wait_for(_loop(), timeout=_AGENT_TIMEOUT)
        except asyncio.TimeoutError:
            result = f"Error: {role} agent timed out after {_AGENT_TIMEOUT}s"
            logger.warning(f"Quad-agent {role} timed out")

        return result or f"{role} completed but returned no response."

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _build_failure_history(logs: list[QuadCycleLog]) -> str:
        """Build a summary of previous cycle failures for the planner."""
        if not logs:
            return "No previous attempts."
        lines = []
        for clog in logs:
            lines.append(f"Cycle {clog.cycle}:")
            lines.append(f"  Strategy: {clog.strategy[:200]}...")
            lines.append(f"  Verification: {'PASS' if clog.verification_passed else 'FAIL'}")
            if not clog.verification_passed:
                lines.append(f"  Verifier feedback: {clog.verification_result[:300]}")
            if clog.adversary_result:
                lines.append(f"  Adversary: attacked")
                lines.append(f"  Repair verified: {'PASS' if clog.repair_verified else 'FAIL'}")
        return "\n".join(lines)


def _parse_passed(verification_text: str) -> bool:
    """Extract passed/failed from verifier response."""
    lower = verification_text.lower()
    try:
        start = verification_text.find("{")
        end = verification_text.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(verification_text[start:end])
            if "passed" in data:
                return bool(data["passed"])
    except (json.JSONDecodeError, KeyError):
        pass

    if '"passed": true' in lower or '"passed":true' in lower:
        return True
    if "all checks passed" in lower or "verification passed" in lower:
        return True
    if "no mismatches" in lower:
        return True
    return False
