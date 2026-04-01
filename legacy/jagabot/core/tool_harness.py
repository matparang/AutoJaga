"""
tool_harness.py — Universal tool execution harness.

Tracks every tool invocation (start/complete/fail), provides elapsed-time
logging, and runs a unified anti-fabrication check on the final response.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from loguru import logger


# Estimated durations (seconds) for tools that may be slow.
# Tools not listed default to 5s.
_ESTIMATED_DURATIONS: dict[str, int] = {
    "debate": 120,
    "monte_carlo": 45,
    "swarm_analysis": 90,
    "web_search": 10,
    "web_fetch": 10,
    "exec": 15,
    "memory_consolidation": 20,
}

# ── Fabrication-detection patterns ──────────────────────────────

_WRITE_TOOL_NAMES = frozenset({"write_file", "create_file", "save_file", "edit_file"})

_FUTURE_CONTEXT = re.compile(
    r"(?:will|shall|going\s+to|plan\s+to|need\s+to|want\s+to|intend\s+to"
    r"|akan|nak|hendak|mahu|perlu|boleh)\s",
    re.IGNORECASE,
)

_PAST_CLAIM = re.compile(
    r"(?:created|wrote|written|saved|generated|made|produced"
    r"|dah|sudah|telah|siap|disimpan|dibuat|ditulis)\s",
    re.IGNORECASE,
)

_FILENAME_IN_QUOTES = re.compile(
    r"[`\"']([^`\"']*?\.(?:txt|py|json|md|yaml|yml|csv|log|sh|toml|cfg|ini))[`\"']",
    re.IGNORECASE,
)

# Also match unquoted file paths after creation verbs
_FILENAME_AFTER_VERB = re.compile(
    r"(?:created|wrote|saved|generated|made|produced|overwrote|updated)\s+"
    r"([^\s,\"'`\n]+?\.(?:txt|py|json|md|yaml|yml|csv|log|sh|toml|cfg|ini))",
    re.IGNORECASE,
)

_DEBATE_RESULT_PATTERNS = re.compile(
    r"(?:bull.*?(?:position|score)\s*[:=]?\s*\d|"
    r"bear.*?(?:position|score)\s*[:=]?\s*\d|"
    r"buffett.*?(?:position|score)\s*[:=]?\s*\d|"
    r"consensus.*?(?:reached|YES|NO)|"
    r"rounds?\s+completed\s*[:=]?\s*\d|"
    r"fact.?citations?\s*[:=]?\s*\d|"
    r"epistemic.?quality)",
    re.IGNORECASE,
)

_MONTE_CARLO_PATTERNS = re.compile(
    r"(?:simulation\s+(?:result|output|ran|completed)|"
    r"monte\s+carlo\s+(?:result|output|shows|indicates)|"
    r"(?:confidence|probability)\s+(?:interval|of)\s*[:=]?\s*[\d.]+%?|"
    r"p[- ]?value\s*[:=]?\s*[\d.])",
    re.IGNORECASE,
)

# Map tool names to their fabrication patterns
_TOOL_FAB_PATTERNS: dict[str, tuple[re.Pattern, int]] = {
    "debate": (_DEBATE_RESULT_PATTERNS, 2),       # need ≥2 matches
    "monte_carlo": (_MONTE_CARLO_PATTERNS, 2),
}


class _ToolExecution:
    """Internal record for a single tool invocation."""

    __slots__ = ("tool_id", "tool_name", "start_time", "end_time",
                 "status", "result_file", "error", "result_text")

    def __init__(self, tool_id: str, tool_name: str) -> None:
        self.tool_id = tool_id
        self.tool_name = tool_name
        self.start_time = time.monotonic()
        self.end_time: float | None = None
        self.status = "running"
        self.result_file: str | None = None
        self.error: str | None = None
        self.result_text: str | None = None

    @property
    def elapsed(self) -> float:
        end = self.end_time or time.monotonic()
        return round(end - self.start_time, 2)


class ToolHarness:
    """
    Universal tool execution harness (singleton-style, one per AgentLoop).

    Responsibilities
    ----------------
    1. **Track** — register / complete / fail every tool invocation.
    2. **Log** — emit structured log lines with durations.
    3. **Verify** — unified anti-fabrication check on final response text.
    """

    def __init__(self, workspace: Path | str | None = None) -> None:
        self.workspace = Path(workspace) if workspace else Path.home() / ".jagabot" / "workspace"
        self._active: dict[str, _ToolExecution] = {}
        self._history: list[_ToolExecution] = []
        self._id_counter = 0
        self._on_start_cb = None
        self._on_done_cb = None

    def set_callbacks(self, on_start=None, on_done=None) -> None:
        """Set callbacks for tool execution display."""
        self._on_start_cb = on_start
        self._on_done_cb = on_done

    # ── Lifecycle ────────────────────────────────────────────────

    def register(self, tool_name: str) -> str:
        """Register a new tool execution. Returns a unique tool_id."""
        self._id_counter += 1
        tool_id = f"{tool_name}_{self._id_counter}_{int(time.time())}"
        ex = _ToolExecution(tool_id, tool_name)
        self._active[tool_id] = ex
        est = _ESTIMATED_DURATIONS.get(tool_name, 5)
        logger.debug(f"Harness: {tool_name} started (est ~{est}s) [{tool_id}]")
        
        # Fire callback for live display
        if self._on_start_cb:
            self._on_start_cb(tool_name)
        
        return tool_id

    def complete(self, tool_id: str, result_file: str | None = None,
                 result_text: str | None = None) -> float:
        """Mark tool as completed. Returns elapsed seconds."""
        ex = self._active.pop(tool_id, None)
        if ex is None:
            return 0.0
        ex.end_time = time.monotonic()
        ex.status = "complete"
        ex.result_file = result_file
        # Store truncated output for epistemic auditing (cap at 4KB)
        if result_text:
            ex.result_text = result_text[:4096]
        self._history.append(ex)
        elapsed = ex.elapsed
        if elapsed > 10:
            logger.info(f"Harness: {ex.tool_name} completed in {elapsed}s [{tool_id}]")
        else:
            logger.debug(f"Harness: {ex.tool_name} completed in {elapsed}s [{tool_id}]")
        
        # Fire callback for live display
        if self._on_done_cb:
            self._on_done_cb(ex.tool_name, elapsed, "ok")
        
        return elapsed

    def fail(self, tool_id: str, error: str = "") -> float:
        """Mark tool as failed. Returns elapsed seconds."""
        ex = self._active.pop(tool_id, None)
        if ex is None:
            return 0.0
        ex.end_time = time.monotonic()
        ex.status = "failed"
        ex.error = error
        self._history.append(ex)
        logger.warning(f"Harness: {ex.tool_name} failed after {ex.elapsed}s — {error[:120]}")
        
        # Fire callback for live display
        if self._on_done_cb:
            self._on_done_cb(ex.tool_name, ex.elapsed, "error")
        
        return ex.elapsed

    def estimated_duration(self, tool_name: str) -> int:
        """Return estimated duration in seconds for a tool."""
        return _ESTIMATED_DURATIONS.get(tool_name, 5)

    @property
    def tool_output_corpus(self) -> str:
        """Concatenate all completed tool result texts for epistemic auditing."""
        parts = []
        for ex in self._history:
            if ex.result_text:
                parts.append(ex.result_text)
        return "\n".join(parts)

    @property
    def profiler(self):
        """Lazy-initialized ToolProfiler reading from execution history."""
        from jagabot.core.profiler import ToolProfiler
        return ToolProfiler(self._history)

    # ── Unified response verification ────────────────────────────

    def verify_response(self, content: str, tools_used: list[str]) -> str:
        """
        Run all anti-fabrication checks on the agent's final response.

        Consolidates file-claim verification and tool-result fabrication
        detection into a single pass.
        """
        if not content:
            return content

        content = self._verify_file_claims(content, tools_used)
        content = self._verify_tool_fabrication(content, tools_used)
        return content

    # ── File claim verification (from CSiveaudit + Toostict) ─────

    def _verify_file_claims(self, content: str, tools_used: list[str]) -> str:
        used_write_tool = bool(_WRITE_TOOL_NAMES & set(tools_used))

        # Collect filenames from both quoted and unquoted patterns
        all_files: list[str] = []
        all_files.extend(_FILENAME_IN_QUOTES.findall(content))
        all_files.extend(_FILENAME_AFTER_VERB.findall(content))

        if not all_files:
            return content

        # Normalize filenames: strip leading/trailing quotes and backticks
        def normalize_path(fp: str) -> str:
            return fp.strip("\"'`").strip()

        # Extract actual written file paths from tool results
        # write_file returns: "Successfully wrote X bytes to {path} (verified on disk)"
        written_paths: set[str] = set()
        for ex in self._history:
            if ex.tool_name in _WRITE_TOOL_NAMES and ex.status == "complete" and ex.result_text:
                import re as re_mod
                matches = re_mod.findall(
                    r'(?:wrote|written|created|to)\s+(?:\d+\s+bytes\s+to\s+)?([^\s(]+?\.(?:txt|py|json|md|yaml|yml|csv|log|sh|toml|cfg|ini))',
                    ex.result_text, re_mod.IGNORECASE
                )
                for m in matches:
                    written_paths.add(m.strip("\"'`"))

        past_claims: list[str] = []
        seen: set[str] = set()

        for fp in all_files:
            fp_normalized = normalize_path(fp)
            if fp_normalized in seen:
                continue
            seen.add(fp_normalized)

            idx = content.lower().find(fp_normalized.lower())
            ctx_before = content[max(0, idx - 120):idx]
            ctx_after = content[idx + len(fp_normalized):idx + len(fp_normalized) + 80]
            ctx = ctx_before + " " + ctx_after

            if _FUTURE_CONTEXT.search(ctx):
                continue  # planning mention — ignore
            if _PAST_CLAIM.search(ctx):
                past_claims.append(fp_normalized)

        if not past_claims:
            return content

        if used_write_tool:
            # Cross-reference: check if claimed files exist OR match written paths
            missing = []
            for fp in past_claims:
                fp_path = Path(fp) if Path(fp).is_absolute() else self.workspace / fp
                if fp_path.exists():
                    continue  # File exists at claimed path
                
                # Check if any written path matches (by filename or full path)
                found_match = False
                for wp in written_paths:
                    wp_path = Path(wp) if Path(wp).is_absolute() else self.workspace / wp
                    if wp_path.exists() and (wp_path == fp_path or wp_path.name == fp_path.name):
                        found_match = True
                        break
                
                if not found_match:
                    missing.append(fp)
            
            if missing:
                warning = (
                    "\n\n⚠️ **VERIFICATION WARNING**: Tool was called but "
                    f"these files were NOT found on disk: {missing}"
                )
                logger.warning(f"Harness file check: tool used but files missing: {missing}")
                return content + warning
            return content

        not_exist = [
            fp for fp in past_claims
            if not (Path(fp) if Path(fp).is_absolute() else self.workspace / fp).exists()
        ]
        if not_exist:
            warning = (
                "\n\n⚠️ **VERIFICATION FAILED**: Claimed to have created "
                f"{not_exist} but NO write tool was executed and the file(s) "
                "do NOT exist on disk. This was a false claim — please ignore it."
            )
            logger.warning(f"Harness file check FAILED — false claim: {not_exist}, tools_used={tools_used}")
            return content + warning

        return content

    # ── Tool-result fabrication detection ─────────────────────────

    def _verify_tool_fabrication(self, content: str, tools_used: list[str]) -> str:
        """Detect fabricated results for tools that were NOT called."""
        tools_set = set(tools_used)

        for tool_name, (pattern, threshold) in _TOOL_FAB_PATTERNS.items():
            # Skip check if the tool (or a subagent that might run it) was used
            if tool_name in tools_set or "spawn" in tools_set:
                continue
            matches = pattern.findall(content)
            if len(matches) >= threshold:
                warning = (
                    f"\n\n⚠️ **VERIFICATION WARNING**: This response contains "
                    f"{tool_name}-style results ({len(matches)} patterns matched) "
                    f"but the `{tool_name}` tool was NOT called. These results may "
                    f"be fabricated. Use the `{tool_name}` tool to get real results."
                )
                logger.warning(
                    f"Harness fabrication detected — {tool_name}: "
                    f"{len(matches)} patterns, tools_used={tools_used}"
                )
                content += warning

        return content
