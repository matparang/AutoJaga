"""
Progressive Complexity Router

Classifies query complexity and routes to appropriate response depth.
Prevents full protocol execution for simple questions.

Levels:
  SIMPLE   → answer directly, no tools, max 3 sentences
  STANDARD → use 1-2 tools, normal response
  COMPLEX  → full protocol, multiple tools
  RESEARCH → YOLO/deep research mode
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from loguru import logger


@dataclass
class ComplexityResult:
    level:       str    # SIMPLE / STANDARD / COMPLEX / RESEARCH
    max_tools:   int    # max tools to send
    max_tokens:  int    # suggested max output tokens
    concise:     bool   # force brief response
    reason:      str    # why this level


# Simple query signals — answer without tools
SIMPLE_SIGNALS = [
    # Definitions
    r"\bwhat (is|are|does)\b",
    r"\bdefine\b", r"\bexplain\b", r"\bdescribe\b",
    r"\bhow does\b", r"\bwhy (is|are|does)\b",
    # Greetings
    r"\bhello\b", r"\bhi\b", r"\bhey\b", r"\bthanks\b",
    r"\bthank you\b", r"\bgood (morning|afternoon|evening)\b",
    # Simple math
    r"\bwhat is \d+\s*[\+\-\×\÷\*\/]\s*\d+\b",
    r"\bcalculate \d+",
    # Yes/no questions
    r"\bcan you\b", r"\bdo you\b", r"\bare you\b",
    r"\bis it possible\b",
]

# Research/complex signals — full protocol
RESEARCH_SIGNALS = [
    r"\byolo\b", r"\bdeep research\b", r"\bfull analysis\b",
    r"\brun all agents\b", r"\bparallel\b", r"\bspawn\b",
    r"\bresearch.*yolo\b", r"\bfinancial.*yolo\b",
    r"\bcomprehensive\b", r"\bthorough\b", r"\bin-depth\b",
]

# Complex signals — need tools but not full YOLO
COMPLEX_SIGNALS = [
    r"\banalyze\b", r"\banalysis\b", r"\bcompare\b",
    r"\bforecast\b", r"\bpredict\b", r"\bsimulate\b",
    r"\brisk\b", r"\bportfolio\b", r"\bvolatility\b",
    r"\bhypothesis\b", r"\bresearch\b", r"\binvestigate\b",
]


def classify(query: str) -> ComplexityResult:
    """Classify query complexity and return routing config."""
    q = query.lower().strip()

    # Check RESEARCH first (highest priority)
    for pattern in RESEARCH_SIGNALS:
        if re.search(pattern, q):
            logger.debug(f"Complexity: RESEARCH (pattern: {pattern})")
            return ComplexityResult(
                level="RESEARCH", max_tools=10, max_tokens=4096,
                concise=False, reason=f"research signal: {pattern}"
            )

    # Check COMPLEX
    for pattern in COMPLEX_SIGNALS:
        if re.search(pattern, q):
            logger.debug(f"Complexity: COMPLEX (pattern: {pattern})")
            return ComplexityResult(
                level="COMPLEX", max_tools=6, max_tokens=2048,
                concise=False, reason=f"complex signal: {pattern}"
            )

    # Check SIMPLE
    for pattern in SIMPLE_SIGNALS:
        if re.search(pattern, q):
            # Double-check: if query also has ticker/stock → STANDARD
            if re.search(r"\b[A-Z]{2,5}\b", query) and any(
                s in q for s in ["price", "stock", "ticker", "market"]
            ):
                logger.debug("Complexity: STANDARD (ticker detected in simple query)")
                return ComplexityResult(
                    level="STANDARD", max_tools=3, max_tokens=1024,
                    concise=True, reason="ticker in simple query"
                )
            logger.debug(f"Complexity: SIMPLE (pattern: {pattern})")
            return ComplexityResult(
                level="SIMPLE", max_tools=2, max_tokens=512,
                concise=True, reason=f"simple signal: {pattern}"
            )

    # Default: STANDARD
    logger.debug("Complexity: STANDARD (default)")
    return ComplexityResult(
        level="STANDARD", max_tools=5, max_tokens=1536,
        concise=False, reason="default"
    )


def get_concise_instruction(level: str) -> str:
    """Return system instruction for response length."""
    if level == "SIMPLE":
        return "\n[CONCISE MODE: Answer in 1-3 sentences. No markdown tables. No headers.]"
    elif level == "STANDARD":
        return "\n[STANDARD MODE: Keep response focused. Use markdown only if it adds clarity.]"
    return ""
