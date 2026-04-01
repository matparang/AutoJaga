"""
OutputContract — enforces structured answer requirements.

Instead of asking for "an analysis", defines exactly what fields
the response MUST contain, and verifies they are present.

Works with TaskDecomposer output contracts.
Post-processes responses to check compliance.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class ContractField:
    """One required field in an output contract."""
    name:       str
    required:   bool  = True
    found:      bool  = False
    detector:   str   = ""   # regex or keyword to detect presence


@dataclass
class ContractResult:
    """Result of contract verification."""
    passed:       bool
    score:        float        # 0-1
    missing:      list[str]
    found:        list[str]
    feedback:     str


# Domain-specific output contracts
DOMAIN_CONTRACTS: dict[str, list[ContractField]] = {
    "financial": [
        ContractField("controlled_variable",    detector=r"controlled var|portfolio|position"),
        ContractField("threshold",              detector=r"threshold|below|above|trigger|if.*drops|if.*rises"),
        ContractField("confidence",             detector=r"\d+%|\bconfidence\b|\bevidence\b"),
        ContractField("decision_rule",          detector=r"\bIF\b.*\bTHEN\b|\bif\b.*\bthen\b"),
        ContractField("reversal_condition",     detector=r"reverse|exit|stop.loss|when to|unless", required=False),
    ],
    "risk": [
        ContractField("breaks_first",           detector=r"breaks first|fails first|first failure"),
        ContractField("intervention_lag",       detector=r"intervention lag|lag|weeks to|days to"),
        ContractField("threat_velocity",        detector=r"threat velocity|velocity|escalates in"),
        ContractField("false_control",          detector=r"false.control|mislead|misleading|vanity metric"),
        ContractField("decision_rule",          detector=r"\bIF\b.*\bTHEN\b|\bif\b.*\bthen\b"),
    ],
    "operations": [
        ContractField("controlled_variable",    detector=r"controlled|variable|output"),
        ContractField("intervention_lag",       detector=r"lag|lead time|weeks|days"),
        ContractField("threshold",              detector=r"threshold|trigger|critical level"),
        ContractField("failure_chain",          detector=r"failure|breaks|cascade|chain"),
    ],
    "diagnosis": [
        ContractField("breaks_first",           detector=r"breaks first|fails first|primary failure"),
        ContractField("failure_type",           detector=r"sensor failure|model failure|decision failure|execution failure"),
        ContractField("causal_chain",           detector=r"causal|because|leads to|results in"),
        ContractField("false_control",          detector=r"false.control|mislead|vanity"),
    ],
    "general": [
        ContractField("direct_answer",          detector=r".+"),  # any content
        ContractField("confidence",             detector=r"\d+%|\bconfidence\b|\buncertain\b", required=False),
    ],
}


class OutputContractEnforcer:
    """
    Verifies response meets output contract requirements.
    Generates feedback for missing fields.
    """

    def __init__(self):
        self._history: list[ContractResult] = []

    def verify(
        self,
        response:  str,
        domain:    str,
        task_type: str,
        contract_fields: list[str] = None,
    ) -> ContractResult:
        """
        Verify response against output contract.
        Returns ContractResult with missing fields and feedback.
        """
        # Get contract for this domain
        if contract_fields:
            # Custom contract from TaskDecomposer
            fields = [
                ContractField(
                    name     = f,
                    detector = self._auto_detector(f),
                )
                for f in contract_fields
            ]
        else:
            fields = DOMAIN_CONTRACTS.get(domain,
                     DOMAIN_CONTRACTS.get(task_type,
                     DOMAIN_CONTRACTS["general"]))

        response_lower = response.lower()
        found    = []
        missing  = []

        for field in fields:
            if not field.required:
                continue
            detected = bool(re.search(field.detector, response, re.IGNORECASE))
            if detected:
                found.append(field.name)
                field.found = True
            else:
                missing.append(field.name)

        total    = len([f for f in fields if f.required])
        score    = len(found) / total if total > 0 else 1.0
        passed   = score >= 0.6

        feedback = ""
        if missing:
            feedback = (
                f"[OUTPUT CONTRACT] Response missing required fields: "
                f"{', '.join(missing)}. "
                f"Please add these before concluding."
            )

        result = ContractResult(
            passed   = passed,
            score    = round(score, 2),
            missing  = missing,
            found    = found,
            feedback = feedback,
        )

        self._history.append(result)
        logger.debug(
            f"OutputContract: {score:.0%} compliance "
            f"({len(found)}/{total} fields) domain={domain}"
        )
        if missing:
            logger.debug(f"OutputContract: missing — {missing}")

        return result

    def _auto_detector(self, field_name: str) -> str:
        """Auto-generate regex detector from field name."""
        detectors = {
            "what breaks first":              r"breaks first|fails first|primary failure",
            "failure type":                   r"sensor failure|model failure|decision failure|execution failure",
            "controlled variable":            r"controlled var|controlled variable",
            "observed variable":              r"observed var|lagging|leading indicator",
            "quantified threshold":           r"threshold|trigger|if.*then|>|<|\d+%",
            "confidence with evidence basis": r"confidence.*because|evidence.*confidence|\d+%.*evidence",
            "what would change the conclusion": r"what would change|would change|if.*instead",
            "explicit recommendation":        r"recommend|should|advise|my recommendation",
            "decision rule: IF/THEN/ELSE":   r"\bIF\b.*\bTHEN\b|\bif\b.*\bthen\b",
            "top 2 risks":                   r"risk[s]?\s*[12:]|first risk|second risk|key risk",
            "when to reverse":               r"reverse|exit|stop loss|unless|when to change",
            "causal chain":                  r"because|leads to|results in|caused by|→",
            "intervention lag vs threat velocity": r"lag|velocity|faster|slower|exceed",
            "confidence":                    r"\d+%|confidence|uncertain|evidence",
            "direct answer":                 r".+",
        }
        # Try exact match first
        if field_name.lower() in detectors:
            return detectors[field_name.lower()]
        # Try partial match
        for key, pattern in detectors.items():
            if any(w in field_name.lower() for w in key.split()):
                return pattern
        # Fallback: use field name words as keywords
        words = [w for w in field_name.lower().split() if len(w) > 3]
        return "|".join(words) if words else ".+"

    def get_compliance_rate(self) -> float:
        """Return average contract compliance rate."""
        if not self._history:
            return 1.0
        return sum(r.score for r in self._history) / len(self._history)
