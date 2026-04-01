"""
Tri-Agent Verification Loop — Worker / Verifier / Adversary.

Orchestrates three LLM-powered agents that continuously check each other:

  Worker    → Executes the task (full tool access)
  Verifier  → Re-reads raw files, checks claims independently (read-only)
  Adversary → Injects faults to test robustness (file ops)

Protocol per cycle:
  1. Worker executes task
  2. Verifier checks worker's claims against actual files
  3. If mismatch → Worker gets feedback, retries (back to 1)
  4. If verified → Adversary attacks
  5. Worker detects & repairs damage
  6. Verifier re-checks after repair
  7. All pass → SUCCESS
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

# Maximum iterations per agent call (prevent runaway loops)
_AGENT_MAX_ITERATIONS = 10
_AGENT_TIMEOUT = 240  # was 120 — Qwen-Plus needs ~3-4 min for complex tasks


# ── System prompts ───────────────────────────────────────────────

_WORKER_PROMPT = """\
You are WORKER, a task execution agent. Your job is to complete the assigned \
task accurately using the tools available to you.

RULES:
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
- Only attack files in the workspace that were created by the worker
- Report exactly what you did so the worker can attempt repair
- Be creative but not destructive to system files

Respond with a JSON summary:
{"attack": "description", "target": "filename", "details": "what was changed"}
"""


@dataclass
class CycleLog:
    """Log of one tri-agent cycle."""
    cycle: int
    worker_result: str = ""
    verification_result: str = ""
    verification_passed: bool = False
    adversary_result: str = ""
    repair_result: str = ""
    repair_verified: bool = False


@dataclass
class TriAgentResult:
    """Final result of the tri-agent loop."""
    status: str           # SUCCESS | PARTIAL | FAILURE
    cycles: int
    result: str           # Final worker output
    log: list[CycleLog] = field(default_factory=list)
    elapsed: float = 0.0


class TriAgentLoop:
    """
    Orchestrates Worker → Verifier → Adversary verification cycles.

    Each agent is an LLM call with a specialized system prompt and
    restricted tool set. Communication is via structured JSON in the
    message history.
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

    async def run(self, task: str) -> TriAgentResult:
        """Execute the full tri-agent verification loop."""
        start = time.time()
        logs: list[CycleLog] = []
        last_worker_result = ""

        # Create sandboxed sub-workspace for this run
        sandbox = self.workspace / "tri_agent_sandbox"
        sandbox.mkdir(parents=True, exist_ok=True)

        try:
            for cycle in range(1, self.max_cycles + 1):
                clog = CycleLog(cycle=cycle)
                logger.info(f"Tri-agent cycle {cycle}/{self.max_cycles}")

                # ── 1. Worker executes ───────────────────────────
                worker_msg = task if cycle == 1 else (
                    f"REPAIR NEEDED based on previous feedback:\n"
                    f"{clog.verification_result or clog.adversary_result}\n\n"
                    f"Original task: {task}\n"
                    f"Fix the issues and re-execute."
                )
                clog.worker_result = await self._call_agent(
                    "worker", _WORKER_PROMPT, worker_msg, sandbox,
                )
                last_worker_result = clog.worker_result

                # ── 2. Verifier checks ───────────────────────────
                verify_msg = (
                    f"The WORKER claims the following:\n"
                    f"{clog.worker_result}\n\n"
                    f"Original task: {task}\n\n"
                    f"Verify these claims by reading the actual files in the workspace. "
                    f"Check that all claimed files exist and contents are correct."
                )
                clog.verification_result = await self._call_agent(
                    "verifier", _VERIFIER_PROMPT, verify_msg, sandbox,
                )

                # Parse verification result
                clog.verification_passed = self._parse_passed(clog.verification_result)

                if not clog.verification_passed:
                    logger.warning(f"Tri-agent cycle {cycle}: verification FAILED")
                    logs.append(clog)
                    continue  # Next cycle — worker will get feedback

                logger.info(f"Tri-agent cycle {cycle}: verification PASSED")

                # ── 3. Adversary attacks ─────────────────────────
                adversary_msg = (
                    f"The WORKER created these artifacts:\n"
                    f"{clog.worker_result}\n\n"
                    f"Attack ONE file to test robustness. "
                    f"Choose from: delete it, corrupt a line, or insert invalid data."
                )
                clog.adversary_result = await self._call_agent(
                    "adversary", _ADVERSARY_PROMPT, adversary_msg, sandbox,
                )

                # ── 4. Worker repairs ────────────────────────────
                repair_msg = (
                    f"ADVERSARY ATTACK REPORT:\n"
                    f"{clog.adversary_result}\n\n"
                    f"Original task: {task}\n\n"
                    f"Detect the damage and repair it. Ensure all files are correct."
                )
                clog.repair_result = await self._call_agent(
                    "worker", _WORKER_PROMPT, repair_msg, sandbox,
                )

                # ── 5. Verifier re-checks after repair ──────────
                recheck_msg = (
                    f"After an adversary attack, the WORKER repaired:\n"
                    f"{clog.repair_result}\n\n"
                    f"Original task: {task}\n\n"
                    f"Re-verify everything. Check all files exist and are correct."
                )
                recheck_result = await self._call_agent(
                    "verifier", _VERIFIER_PROMPT, recheck_msg, sandbox,
                )
                clog.repair_verified = self._parse_passed(recheck_result)

                logs.append(clog)

                if clog.repair_verified:
                    logger.info(f"Tri-agent: SUCCESS after {cycle} cycle(s)")
                    return TriAgentResult(
                        status="SUCCESS",
                        cycles=cycle,
                        result=last_worker_result,
                        log=logs,
                        elapsed=time.time() - start,
                    )

                logger.warning(f"Tri-agent cycle {cycle}: repair verification FAILED")

            # Max cycles exhausted
            return TriAgentResult(
                status="PARTIAL",
                cycles=self.max_cycles,
                result=last_worker_result,
                log=logs,
                elapsed=time.time() - start,
            )

        except Exception as e:
            logger.error(f"Tri-agent loop error: {e}")
            return TriAgentResult(
                status="FAILURE",
                cycles=len(logs),
                result=f"Error: {e}",
                log=logs,
                elapsed=time.time() - start,
            )
        finally:
            # Clean up sandbox
            try:
                if sandbox.exists():
                    shutil.rmtree(sandbox)
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

        if role == "worker":
            tools.register(ReadFileTool(allowed_dir=allowed_dir))
            tools.register(WriteFileTool(allowed_dir=allowed_dir))
            tools.register(EditFileTool(allowed_dir=allowed_dir))
            tools.register(ListDirTool(allowed_dir=allowed_dir))
            tools.register(ExecTool(
                working_dir=str(sandbox), timeout=30,
                restrict_to_workspace=self.restrict_to_workspace,
            ))
        elif role == "verifier":
            # Read-only — no write/edit tools
            tools.register(ReadFileTool(allowed_dir=allowed_dir))
            tools.register(ListDirTool(allowed_dir=allowed_dir))
            tools.register(ExecTool(
                working_dir=str(sandbox), timeout=15,
                restrict_to_workspace=self.restrict_to_workspace,
            ))
        elif role == "adversary":
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
            logger.warning(f"Tri-agent {role} timed out")

        return result or f"{role} completed but returned no response."

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _parse_passed(verification_text: str) -> bool:
        """Extract passed/failed from verifier response."""
        lower = verification_text.lower()
        # Try JSON parsing first
        try:
            # Find JSON object in the response
            start = verification_text.find("{")
            end = verification_text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(verification_text[start:end])
                if "passed" in data:
                    return bool(data["passed"])
        except (json.JSONDecodeError, KeyError):
            pass

        # Fallback: heuristic
        if '"passed": true' in lower or '"passed":true' in lower:
            return True
        if "all checks passed" in lower or "verification passed" in lower:
            return True
        if "no mismatches" in lower:
            return True
        return False
