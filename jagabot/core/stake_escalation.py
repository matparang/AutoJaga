"""
StakeAwareEscalation

Scores decision stakes and escalates verification depth accordingly.
Prevents catastrophic failures by requiring more evidence for
high-stakes decisions.

Stake levels:
  LOW:          Simple queries, factual questions
  MEDIUM:       Research, analysis, recommendations
  HIGH:         Financial advice, medical info, legal guidance
  CATASTROPHIC: Irreversible actions, large financial decisions,
                safety-critical operations

Escalation rules:
  LOW:          1 source, standard verification
  MEDIUM:       2 sources, verifier check required
  HIGH:         3+ sources, guardrail check mandatory, human caveat
  CATASTROPHIC: Maximum verification, explicit uncertainty, refuse
                if insufficient evidence
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from loguru import logger


@dataclass
class StakeAssessment:
    """Result of stake scoring for a query/response."""
    level:           str    # LOW / MEDIUM / HIGH / CATASTROPHIC
    score:           float  # 0-1
    reasons:         list[str]
    min_sources:     int    # minimum sources required
    requires_caveat: bool
    requires_human:  bool   # escalate to human review
    max_confidence:  float  # cap on stated confidence
    instruction:     str    # injection into system prompt


# Stake signal patterns
CATASTROPHIC_SIGNALS = [
    r"\b(sell all|sell everything|all.in|bet everything)\b",
    r"\b(life savings|retirement fund|entire portfolio)\b",
    r"\b(surgery|medication dosage|drug interaction|overdose)\b",
    r"\b(legal advice|sue|lawsuit|criminal)\b",
    r"\b(delete|destroy|format|wipe)\b.*\b(data|database|server)\b",
    r"\b(irreversible|permanent|cannot be undone)\b",
]

HIGH_SIGNALS = [
    r"\b(invest|buy|sell|trade)\b.*\b(\$\d+|\d+k|\d+K)\b",
    r"\b(should I (buy|sell|invest))\b",
    r"\b(financial (advice|decision|recommendation))\b",
    r"\b(medical|health|diagnosis|symptom|treatment)\b",
    r"\b(legal|law|court|contract|compliance)\b",
    r"\b(hire|fire|layoff|termination)\b",
    r"\byolo\b.*\b(financial|stock|invest)\b",
]

MEDIUM_SIGNALS = [
    r"\b(recommend|suggest|advise)\b",
    r"\b(analyze|analysis|assess|evaluate)\b",
    r"\b(research|hypothesis|study|experiment)\b",
    r"\b(predict|forecast|expect|likely)\b",
    r"\b(compare|vs|versus|between)\b",
]


class StakeAwareEscalation:
    """
    Scores query stakes and returns escalation instructions.
    """

    def __init__(self):
        self._history: list[StakeAssessment] = []

    def assess(self, query: str, response: str = "") -> StakeAssessment:
        """Assess stakes for a query+response pair."""
        combined = f"{query} {response}".lower()
        reasons  = []

        # Check catastrophic signals first
        for pattern in CATASTROPHIC_SIGNALS:
            if re.search(pattern, combined, re.IGNORECASE):
                reasons.append(f"catastrophic signal: {pattern}")
                assessment = StakeAssessment(
                    level           = "CATASTROPHIC",
                    score           = 1.0,
                    reasons         = reasons,
                    min_sources     = 4,
                    requires_caveat = True,
                    requires_human  = True,
                    max_confidence  = 0.3,
                    instruction     = (
                        "\n[CATASTROPHIC STAKE DETECTED] "
                        "This query involves potentially irreversible consequences. "
                        "REQUIRED: State maximum uncertainty. "
                        "Recommend professional consultation. "
                        "Do NOT provide specific actionable advice. "
                        "Max confidence: 30%."
                    )
                )
                logger.warning(f"StakeEscalation: CATASTROPHIC — {reasons[0]}")
                self._history.append(assessment)
                return assessment

        # Check high signals
        high_matches = []
        for pattern in HIGH_SIGNALS:
            if re.search(pattern, combined, re.IGNORECASE):
                high_matches.append(pattern)

        if high_matches:
            reasons = [f"high signal: {p}" for p in high_matches[:2]]
            assessment = StakeAssessment(
                level           = "HIGH",
                score           = 0.75,
                reasons         = reasons,
                min_sources     = 3,
                requires_caveat = True,
                requires_human  = False,
                max_confidence  = 0.65,
                instruction     = (
                    "\n[HIGH STAKE DECISION] "
                    "Requires minimum 3 verified sources. "
                    "Apply full adversarial guardrails. "
                    "Include explicit uncertainty statement. "
                    "Recommend professional consultation. "
                    "Max confidence: 65%."
                )
            )
            logger.info(f"StakeEscalation: HIGH — {len(high_matches)} signals")
            self._history.append(assessment)
            return assessment

        # Check medium signals
        medium_matches = []
        for pattern in MEDIUM_SIGNALS:
            if re.search(pattern, combined, re.IGNORECASE):
                medium_matches.append(pattern)

        if medium_matches:
            assessment = StakeAssessment(
                level           = "MEDIUM",
                score           = 0.4,
                reasons         = [f"medium signal: {p}" for p in medium_matches[:2]],
                min_sources     = 2,
                requires_caveat = False,
                requires_human  = False,
                max_confidence  = 0.85,
                instruction     = (
                    "\n[MEDIUM STAKE] "
                    "Requires 2+ sources for key claims. "
                    "Apply standard guardrails."
                )
            )
            self._history.append(assessment)
            return assessment

        # Default: LOW
        assessment = StakeAssessment(
            level           = "LOW",
            score           = 0.1,
            reasons         = ["no high-stake signals detected"],
            min_sources     = 1,
            requires_caveat = False,
            requires_human  = False,
            max_confidence  = 1.0,
            instruction     = ""
        )
        self._history.append(assessment)
        return assessment

    def get_stats(self) -> dict:
        """Return stake assessment statistics."""
        if not self._history:
            return {"total": 0}
        levels = [a.level for a in self._history]
        return {
            "total":         len(levels),
            "catastrophic":  levels.count("CATASTROPHIC"),
            "high":          levels.count("HIGH"),
            "medium":        levels.count("MEDIUM"),
            "low":           levels.count("LOW"),
        }
