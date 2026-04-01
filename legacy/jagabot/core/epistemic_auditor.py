"""
Epistemic Auditor — catches "clever hallucinations" where the LLM
simulates tool execution by generating plausible numbers/files without
actually running any tools.

Cross-references specific numeric claims in the response against the
actual tool output corpus. If the agent claims "mean = 42.7" but no
tool ever returned "42.7", the claim is flagged as unverified.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from loguru import logger

# Matches decimal numbers like 42.7, 3.14, 0.95 (but not version-like x.y.z)
_DECIMAL_RE = re.compile(r'(?<!\d[.])\b(\d+\.\d{1,6})\b(?!\.\d)')

# Common decimals that appear naturally in text — skip these
# Includes round numbers, simple fractions, and common metrics
_COMMON_DECIMALS = frozenset({
    # Round numbers (whole numbers with .0)
    "0.0", "1.0", "2.0", "3.0", "4.0", "5.0", "6.0", "7.0", "8.0", "9.0", "10.0",
    "15.0", "20.0", "25.0", "30.0", "40.0", "50.0", "60.0", "70.0", "80.0", "90.0", "100.0",
    "1000.0", "10000.0",
    # Simple fractions
    "0.5", "1.5", "2.5", "3.5", "4.5", "5.5", "6.5", "7.5", "8.5", "9.5",
    "0.25", "0.75", "1.25", "1.75", "2.25", "2.75",
    # Common percentages as decimals
    "0.01", "0.05", "0.1", "0.2", "0.25", "0.50", "0.75", "0.8", "0.9",
    # Common ratios
    "0.33", "0.67", "0.125", "0.375", "0.625", "0.875",
})

# Numbers that look like decimals but are NOT financial claims
# These should never be flagged as "unverified"
_SKIP_PATTERNS = [
    # Legal citations: HIPAA §164.514, CCPA §1798.100
    r'\b\d{1,4}\.\d{1,3}\b(?=\s*[\(\[])',        # e.g. 164.514 (HIPAA)
    r'§\s*\d{1,4}\.\d{1,3}',                      # e.g. §164.524
    r'\b1[67]\d{2}\.\d{1,3}\b',                   # e.g. 1798.100

    # Percentages already shown as whole numbers
    r'\b\d{1,3}%',                                 # e.g. 70%, 40%

    # Rankings and scores (1-10 scale)
    r'\b[1-9]/10\b',                               # e.g. 6/10, 4/10

    # Dollar amounts (cost estimates)
    r'\$\d+(?:\.\d{1,2})?(?:/mo)?',               # e.g. $15/mo, $300

    # Time references
    r'\b\d+\s*(?:min|sec|hr|hours?|minutes?)\b',  # e.g. 25 min, 60 sec
]

# Phrases that signal a number is illustrative, not a real claim
_ILLUSTRATIVE_PHRASES = [
    "e.g.", "e.g,", "for example", "for instance",
    "illustrative", "example:", "example value",
    "suppose", "imagine", "hypothetically",
    "let's say", "say,", "such as",
    "improved from", "increased to", "dropped to",
    "went from", "changed from",
]

# Response starters that indicate pure explanation mode
_EXPLAIN_STARTERS = [
    "yes — i have", "yes, i have", "yes — automatic",
    "closing the self-improvement", "here's how it works",
    "here is how", "the self-improvement loop",
]

# Minimum unverified decimal claims to trigger rejection
# Increased from 3 to 4 to reduce false positives on round numbers
_REJECTION_THRESHOLD = 4


@dataclass
class EpistemicResult:
    """Outcome of an epistemic audit."""
    approved: bool
    unverified_claims: list[str] = field(default_factory=list)
    feedback: str | None = None


class EpistemicAuditor:
    """
    Cross-references numeric claims in the LLM response against
    actual tool outputs collected during the session.

    If the response contains specific decimal numbers that never
    appeared in any tool output, they are flagged as fabricated.
    """

    def __init__(self, threshold: int = _REJECTION_THRESHOLD) -> None:
        self.threshold = threshold

    def _get_surrounding(self, decimal: str, content: str, chars: int = 60) -> str:
        """Get text surrounding a decimal for context checking."""
        pattern = re.compile(
            r'.{0,' + str(chars) + r'}' + re.escape(decimal) + r'.{0,' + str(chars) + r'}',
            re.DOTALL
        )
        match = pattern.search(content)
        return match.group(0).lower() if match else decimal.lower()

    def _is_skip_pattern(self, decimal: str, context: str) -> bool:
        """
        Return True if this decimal should NOT be flagged.
        Checks surrounding context for legal/cost/time patterns.
        """
        # Find the decimal in context with surrounding chars
        pattern = re.compile(
            r'.{0,20}' + re.escape(decimal) + r'.{0,20}'
        )
        match = pattern.search(context)
        surrounding = match.group(0) if match else decimal

        for skip in _SKIP_PATTERNS:
            if re.search(skip, surrounding):
                return True
        return False

    def _is_illustrative(self, decimal: str, content: str) -> bool:
        """
        Return True if decimal appears near illustrative language.
        These are example numbers in explanations, not real claims.
        """
        surrounding = self._get_surrounding(decimal, content, chars=60)
        return any(phrase in surrounding for phrase in _ILLUSTRATIVE_PHRASES)

    def _is_from_exec_output(self, decimal: str, content: str) -> bool:
        """
        Return True if decimal appears inside an exec output block.
        Numbers from actual code execution are verified by definition.
        """
        # Look for exec output markers
        exec_block_pattern = re.compile(
            r'(?:Output:|Result:|Executed:|✅.*?output|>>)(.*?)(?:\n\n|\Z)',
            re.DOTALL | re.IGNORECASE
        )
        for match in exec_block_pattern.finditer(content):
            if decimal in match.group(1):
                return True
        return False

    def should_skip_decimal(self, decimal: str, content: str) -> bool:
        """
        Master check — return True if this decimal should NOT
        be counted as an unverified claim.

        Apply in audit() before flagging a decimal.
        """
        return (
            self._is_skip_pattern(decimal, content)
            or self._is_illustrative(decimal, content)
            or self._is_from_exec_output(decimal, content)
        )

    def audit(self, response_text: str, tool_output_corpus: str, tools_used: list | None = None) -> EpistemicResult:
        """
        Check whether numeric claims in the response are grounded
        in actual tool outputs.

        Args:
            response_text: The LLM's draft response.
            tool_output_corpus: Concatenated text of all tool outputs
                                from this session (current + history).
            tools_used: Optional list of tools used (for explanation mode detection).

        Returns:
            EpistemicResult with approval status and any unverified claims.
        """
        if not response_text or not response_text.strip():
            return EpistemicResult(approved=True)

        # Early return for pure explanation responses
        # If response starts with explanation phrases and no tools used,
        # illustrative numbers are not financial claims
        content_lower = response_text.lower()
        is_explanation = any(s in content_lower for s in _EXPLAIN_STARTERS)
        no_tools_used = not tools_used or len(tools_used) == 0

        if is_explanation and no_tools_used:
            # Pure explanation response — skip decimal verification
            # Illustrative numbers in explanations are not financial claims
            logger.debug("Epistemic audit: skipping decimal check for explanation response")
            return EpistemicResult(approved=True)

        # Extract decimal claims from response
        claimed_decimals = set(_DECIMAL_RE.findall(response_text))
        claimed_decimals -= _COMMON_DECIMALS

        if not claimed_decimals:
            return EpistemicResult(approved=True)

        # If no tools were run at all, any specific decimal is suspicious
        corpus_lower = tool_output_corpus.lower() if tool_output_corpus else ""

        unverified = []
        for num in sorted(claimed_decimals):
            if num not in corpus_lower and not self.should_skip_decimal(num, response_text):
                unverified.append(num)

        if len(unverified) >= self.threshold:
            feedback = (
                "[EPISTEMIC AUDIT - FABRICATION DETECTED]\n"
                f"Your response contains {len(unverified)} specific numeric values "
                f"that do NOT appear in any tool output: {', '.join(unverified[:5])}\n\n"
                "This means you likely SIMULATED the computation instead of "
                "actually running it.\n\n"
                "FIX: Use the exec tool to run the actual computation, then "
                "report the REAL numbers from the tool output. Do NOT invent "
                "statistics or metrics."
            )
            logger.warning(
                f"Epistemic audit REJECTED: {len(unverified)} unverified decimals "
                f"(threshold={self.threshold}): {unverified[:5]}"
            )
            return EpistemicResult(
                approved=False,
                unverified_claims=unverified,
                feedback=feedback,
            )

        logger.debug(
            f"Epistemic audit passed: {len(claimed_decimals)} decimals, "
            f"{len(unverified)} unverified (below threshold {self.threshold})"
        )
        return EpistemicResult(approved=True, unverified_claims=unverified)
