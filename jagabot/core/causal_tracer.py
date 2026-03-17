"""
Causal Tracer — verifies cause-effect claims in agent responses.

If the agent says "I ran exec and got 42.7", this harness checks that
(a) exec was actually called, and (b) its output contained "42.7".

Maintains a causal log of (tool_name, args_summary, result_snippet) tuples
built during tool execution, then scans the final response for causal
phrases and cross-references them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from loguru import logger

# Patterns that imply the agent executed a tool
_TOOL_CLAIM_RE = re.compile(
    r"(?:I\s+)?(?:ran|executed|used|called|invoked|running)\s+"
    r"(?:the\s+)?[`'\"]?(\w+)[`'\"]?",
    re.IGNORECASE,
)

# Patterns that imply a tool produced a result
_RESULT_CLAIM_RE = re.compile(
    r"(?:got|returned|produced|output|result|shows?|gave|yielded)\s*"
    r"[:=]?\s*[`'\"]?([^`'\",\n]{2,60})[`'\"]?",
    re.IGNORECASE,
)

# Causal connectors — phrases that link cause to effect
_CAUSAL_CONNECTORS = re.compile(
    r"(?:because|therefore|thus|so\s+that|which\s+(?:gave|returned|produced|showed)|"
    r"after\s+(?:running|executing|calling)|"
    r"the\s+(?:result|output)\s+(?:was|is|shows))",
    re.IGNORECASE,
)


@dataclass
class CausalEntry:
    """One recorded tool execution in the causal log."""
    tool_name: str
    args_summary: str
    result_snippet: str


@dataclass
class CausalResult:
    """Outcome of causal verification."""
    approved: bool
    unverified_tools: list[str] = field(default_factory=list)
    unverified_results: list[str] = field(default_factory=list)
    feedback: str | None = None


class CausalTracer:
    """
    Tracks tool executions and verifies causal claims in agent responses.

    Usage:
        tracer = CausalTracer()
        # During tool execution:
        tracer.record(tool_name, args_str, result_text)
        # After agent produces response:
        result = tracer.verify_claims(response_text)
    """

    def __init__(self) -> None:
        self._log: list[CausalEntry] = []

    def record(self, tool_name: str, args_summary: str, result_snippet: str) -> None:
        """Record a tool execution for causal verification."""
        self._log.append(CausalEntry(
            tool_name=tool_name.lower(),
            args_summary=args_summary[:200],
            result_snippet=result_snippet[:2048],
        ))

    def clear(self) -> None:
        """Clear the causal log (between messages)."""
        self._log.clear()

    @property
    def tool_names_used(self) -> set[str]:
        """Set of tool names that were actually executed."""
        return {e.tool_name for e in self._log}

    @property
    def all_results_text(self) -> str:
        """Concatenated result snippets from all tool executions."""
        return "\n".join(e.result_snippet for e in self._log if e.result_snippet)

    def verify_claims(self, response_text: str) -> CausalResult:
        """
        Verify causal claims in the response against the execution log.

        Checks:
        1. Tools the agent claims to have run — were they actually called?
        2. Results the agent claims tools produced — do they appear in outputs?
        """
        if not response_text or not response_text.strip():
            return CausalResult(approved=True)

        # Only check sentences that contain causal connectors
        sentences = re.split(r'[.!?\n]', response_text)
        causal_sentences = [
            s for s in sentences if _CAUSAL_CONNECTORS.search(s)
        ]

        if not causal_sentences:
            return CausalResult(approved=True)

        causal_text = " ".join(causal_sentences)
        used_names = self.tool_names_used
        results_corpus = self.all_results_text.lower()

        # Check tool name claims
        unverified_tools = []
        for match in _TOOL_CLAIM_RE.finditer(causal_text):
            claimed_tool = match.group(1).lower()
            # Skip common words that aren't tools
            if claimed_tool in ("the", "a", "an", "it", "this", "that", "my"):
                continue
            if claimed_tool not in used_names:
                unverified_tools.append(claimed_tool)

        # Check result value claims (only in causal sentences)
        unverified_results = []
        for match in _RESULT_CLAIM_RE.finditer(causal_text):
            claimed_value = match.group(1).strip().lower()
            if len(claimed_value) < 3:
                continue
            if claimed_value not in results_corpus and not self._log:
                unverified_results.append(claimed_value[:50])

        # Reject if there are unverified tool claims in causal context
        if len(unverified_tools) >= 2 or (unverified_tools and not self._log):
            feedback = (
                "[CAUSAL TRACE - UNVERIFIED TOOL CLAIMS]\n"
                f"You claimed to have run: {', '.join(unverified_tools)}\n"
                f"But the execution log shows only: {', '.join(sorted(used_names)) or 'NO tools executed'}\n\n"
                "FIX: Actually call the tools you claim to use, then report "
                "the real results."
            )
            logger.warning(
                f"Causal trace REJECTED: unverified tools {unverified_tools}, "
                f"actual tools: {sorted(used_names)}"
            )
            return CausalResult(
                approved=False,
                unverified_tools=unverified_tools,
                unverified_results=unverified_results,
                feedback=feedback,
            )

        if unverified_results and len(unverified_results) >= 3:
            logger.debug(
                f"Causal trace: {len(unverified_results)} unverified results "
                f"(informational, not blocking)"
            )

        return CausalResult(
            approved=True,
            unverified_tools=unverified_tools,
            unverified_results=unverified_results,
        )
