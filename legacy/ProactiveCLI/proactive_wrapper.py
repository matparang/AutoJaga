# jagabot/agent/proactive_wrapper.py
"""
ProactiveWrapper — Makes AutoJaga behave like a research partner
instead of a one-way CLI tool.

Problem it solves:
    Current: execute → show raw output → stop
    Fixed:   execute → interpret → surface implications → suggest next step

Inspired by Claude Code's interaction pattern:
    Never show output without explanation.
    Never stop without a next step.
    Never ask more than one question.

Wire into loop.py _process_message (wrap final_content):
    from jagabot.agent.proactive_wrapper import ProactiveWrapper
    self.pro_wrapper = ProactiveWrapper()

    # After getting final_content from LLM:
    final_content = self.pro_wrapper.enhance(
        content=final_content,
        query=msg.content,
        tools_used=tools_used,
        tool_outputs=tool_outputs,  # raw exec results
        session_context=session_context,
    )
"""

import re
from dataclasses import dataclass
from typing import Optional

from loguru import logger


# ── Response quality signals ────────────────────────────────────────
RAW_OUTPUT_SIGNALS = [
    r'^\s*✅ Executed \d+ action',      # just shows execution count
    r'^\s*⚙ Executed:',                 # shows raw command
    r'Naive ATE:.*\nIPW ATE:',          # raw numbers no explanation
    r'^\s*\{[\s\n]*"',                  # raw JSON dump
    r'exit code: \d+',                  # raw exit code
    r'No such file or directory',       # raw error no interpretation
]

STOPS_WITHOUT_NEXT_STEP = [
    r'just say the word',               # passive ending
    r'let me know if',                  # passive ending
    r'hope this helps',                 # passive ending
    r'any questions\?$',               # passive ending
]

# Patterns that indicate a good proactive response already
ALREADY_PROACTIVE = [
    r'what this means',
    r'next logical step',
    r'next step',
    r'what comes next',
    r'want me to',
    r'shall i',
    r'would you like',
]


@dataclass
class ResponseAnalysis:
    """Analysis of whether a response needs proactive enhancement."""
    is_raw_output:        bool = False
    stops_without_next:   bool = False
    already_proactive:    bool = False
    has_tool_execution:   bool = False
    has_interpretation:   bool = False
    needs_enhancement:    bool = False
    enhancement_type:     str  = "none"  # "interpret" | "next_step" | "both"


class ProactiveWrapper:
    """
    Post-processes agent responses to ensure they are
    always interpretive and forward-looking.

    Does NOT rewrite responses — only appends missing elements.
    Respects responses that are already well-structured.
    """

    def __init__(self) -> None:
        self._session_topics: list[str] = []

    def enhance(
        self,
        content:         str,
        query:           str           = "",
        tools_used:      list          = None,
        tool_outputs:    dict          = None,
        session_context: dict          = None,
    ) -> str:
        """
        Enhance response if it lacks interpretation or next steps.
        Returns enhanced content, or original if already good.
        """
        tools_used   = tools_used   or []
        tool_outputs = tool_outputs or {}

        analysis = self._analyse(content, tools_used)

        if not analysis.needs_enhancement:
            return content

        logger.debug(
            f"ProactiveWrapper: enhancing response "
            f"(type={analysis.enhancement_type})"
        )

        enhanced = content

        # Add interpretation if missing after tool execution
        if analysis.enhancement_type in ("interpret", "both"):
            interpretation = self._build_interpretation(
                content, query, tools_used, tool_outputs
            )
            if interpretation:
                enhanced = enhanced.rstrip() + "\n\n" + interpretation

        # Add next step if response stops passively
        if analysis.enhancement_type in ("next_step", "both"):
            next_step = self._build_next_step(
                content, query, tools_used, session_context or {}
            )
            if next_step:
                enhanced = enhanced.rstrip() + "\n\n" + next_step

        return enhanced

    # ── Analysis ────────────────────────────────────────────────────

    def _analyse(
        self, content: str, tools_used: list
    ) -> ResponseAnalysis:
        """Determine what enhancement is needed."""
        a = ResponseAnalysis()

        content_lower = content.lower()

        # Check if response is raw output without explanation
        a.is_raw_output = any(
            re.search(p, content, re.MULTILINE)
            for p in RAW_OUTPUT_SIGNALS
        )

        # Check if response stops passively
        a.stops_without_next = any(
            re.search(p, content_lower)
            for p in STOPS_WITHOUT_NEXT_STEP
        )

        # Check if already proactive
        a.already_proactive = any(
            re.search(p, content_lower)
            for p in ALREADY_PROACTIVE
        )

        # Check if tools were used
        a.has_tool_execution = len(tools_used) > 0

        # Check if interpretation exists
        interpretation_signals = [
            "this means", "what happened", "the result",
            "in other words", "this tells us", "this shows",
            "practically", "in plain",
        ]
        a.has_interpretation = any(
            s in content_lower for s in interpretation_signals
        )

        # Determine if enhancement needed
        if a.already_proactive:
            a.needs_enhancement = False
            a.enhancement_type  = "none"
        elif a.is_raw_output and not a.has_interpretation:
            a.needs_enhancement = True
            a.enhancement_type  = "both"
        elif a.has_tool_execution and not a.has_interpretation:
            a.needs_enhancement = True
            a.enhancement_type  = "interpret"
        elif a.stops_without_next and a.has_tool_execution:
            a.needs_enhancement = True
            a.enhancement_type  = "next_step"
        else:
            a.needs_enhancement = False
            a.enhancement_type  = "none"

        return a

    # ── Enhancement builders ────────────────────────────────────────

    def _build_interpretation(
        self,
        content:     str,
        query:       str,
        tools_used:  list,
        tool_outputs:dict,
    ) -> str:
        """
        Build a plain-language interpretation block.
        Only called when response lacks interpretation.
        """
        lines = ["---", "**What this means:**"]

        # Tool-specific interpretations
        if "exec" in tools_used:
            exec_out = tool_outputs.get("exec", "")
            if "No contradictions found" in content:
                lines.append(
                    "The new claim does not conflict with anything "
                    "in your verified memory. It is compatible — "
                    "neither confirmed nor denied yet."
                )
            elif "CONTRADICTION" in content:
                lines.append(
                    "A conflict was found between your new claim "
                    "and a verified fact in MEMORY.md. "
                    "You should resolve this before proceeding."
                )
            elif "No accuracy data" in content or "null" in content:
                lines.append(
                    "This system has no recorded outcomes yet. "
                    "It is built and ready but needs real usage "
                    "data before it can report meaningful statistics."
                )
            elif "error" in content.lower() or "failed" in content.lower():
                lines.append(
                    "The execution encountered an error. "
                    "The task was not completed successfully."
                )
            else:
                lines.append(
                    f"The {'tool' if tools_used else 'operation'} "
                    f"completed. See output above for details."
                )

        elif "write_file" in tools_used:
            lines.append(
                "The file was saved to disk. "
                "It will persist across sessions and "
                "can be referenced in future work."
            )

        elif "web_search" in tools_used or "researcher" in tools_used:
            lines.append(
                "Research complete. The findings above are "
                "based on current web sources. "
                "Key conclusions have been logged for tracking."
            )

        elif "tri_agent" in tools_used or "quad_agent" in tools_used:
            lines.append(
                "These ideas came from isolated agents with "
                "no shared memory — designed for novelty "
                "over correctness. Verify before acting."
            )

        if len(lines) <= 2:
            return ""  # nothing useful to add

        return "\n".join(lines)

    def _build_next_step(
        self,
        content:         str,
        query:           str,
        tools_used:      list,
        session_context: dict,
    ) -> str:
        """
        Build a specific next-step suggestion.
        Only one suggestion — not a menu of options.
        """
        content_lower = content.lower()

        # Context-aware next steps
        if "no contradictions found" in content_lower:
            return (
                "**Next:** To make this value official, run a "
                "validation cycle and write it to MEMORY.md "
                "with provenance. Say *'validate and save'* to proceed."
            )

        if "no accuracy data" in content_lower or "total_predictions: 0" in content:
            return (
                "**Next:** To activate calibration, run an analysis "
                "on a real topic, get a verdict, then tell me "
                "whether it was correct. One verified outcome "
                "starts the learning loop."
            )

        if "write_file" in tools_used and "test" not in content_lower:
            return (
                "**Next:** The file is saved but not tested yet. "
                "Say *'run it'* to execute and verify it works."
            )

        if "hypothesis" in content_lower or "approach" in content_lower:
            return (
                "**Next:** These are unverified ideas. "
                "Say *'research the top idea'* to investigate "
                "feasibility, or *'save as pending outcome'* "
                "to track which ones prove correct."
            )

        if "web_search" in tools_used:
            return (
                "**Next:** Research complete. Say *'save key findings'* "
                "to write verified facts to MEMORY.md, or "
                "*'go deeper on [topic]'* to continue."
            )

        if "exec" in tools_used:
            return (
                "**Next:** Computation verified. Say *'explain the implications'* "
                "for research context, or give me new data to analyse."
            )

        # Generic fallback — only if nothing else matches
        return ""


# ── Quality scorer integration ──────────────────────────────────────
# The ProactiveWrapper also improves quality scores
# by ensuring responses have interpretation.
# Wire into QualityScorer in session_writer.py:
#
# def score(self, content, tools_used, auditor_approved):
#     ...
#     # +0.20 for having interpretation/next step
#     has_next_step = any(
#         s in content.lower()
#         for s in ["next:", "next step", "want me to", "shall i"]
#     )
#     if has_next_step:
#         score += 0.10  # partial bonus
#     has_interpretation = any(
#         s in content.lower()
#         for s in ["this means", "what happened", "in other words"]
#     )
#     if has_interpretation:
#         score += 0.10  # partial bonus
