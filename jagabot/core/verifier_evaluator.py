"""
VerifierEvaluatorLoop

Post-response verification of reasoning quality.
Complements ResponseAuditor (numeric/file checks) with:
  - Claim support verification (every claim has evidence)
  - Reasoning consistency check (no contradictions)
  - Guardrail compliance check (rules applied correctly)
  - Confidence validity check (stated confidence justified)
  - Source quality check (unverified sources flagged)

Scoring:
  0.0-0.4: FAIL — response contains serious errors
  0.4-0.7: WARN — response has weaknesses, proceed with caveat
  0.7-1.0: PASS — response meets quality threshold

Integration:
  Runs AFTER ResponseAuditor
  If FAIL → request revision with specific feedback
  If WARN → append warning note to response
  If PASS → approve response
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class VerificationResult:
    """Result of one verification check."""
    check:    str
    passed:   bool
    score:    float    # 0-1
    issue:    str      # what's wrong (if failed)
    fix:      str      # how to fix it


@dataclass
class EvaluationReport:
    """Full evaluation of a response."""
    overall_score:  float
    verdict:        str    # "PASS" | "WARN" | "FAIL"
    checks:         list[VerificationResult]
    issues:         list[str]
    feedback:       str    # feedback for agent if revision needed
    caveat:         str    # caveat to append if WARN


class VerifierEvaluatorLoop:
    """
    Post-response reasoning quality verifier.
    Runs after ResponseAuditor to catch logical errors.
    """

    PASS_THRESHOLD = 0.70
    WARN_THRESHOLD = 0.40

    # Patterns that indicate unsupported claims
    UNSUPPORTED_CLAIM_PATTERNS = [
        r"\b(definitely|certainly|absolutely|guaranteed)\b",
        r"\b(always|never|all|none|every)\b(?!\s+(?:tool|step|phase))",
        r"\bwill\s+(definitely|certainly|absolutely)\b",
        r"\b100%\s+(?:sure|certain|confident|accurate)\b",
    ]

    # Patterns that indicate contradictions
    CONTRADICTION_PATTERNS = [
        (r"increasing", r"decreasing"),
        (r"bullish", r"bearish"),
        (r"buy", r"sell"),
        (r"high confidence", r"low confidence"),
        (r"verified", r"unverified"),
    ]

    # Guardrail compliance signals
    GUARDRAIL_SIGNALS = {
        "financial": ["guardrail check", "source quality", "confidence"],
        "research":  ["hypothesis", "evidence", "verified"],
        "general":   [],
    }

    def __init__(self, skip_domains: list[str] = None):
        self.skip_domains  = skip_domains or ["simple", "greeting"]
        self._eval_history: list[EvaluationReport] = []

    def _check_unsupported_claims(self, response: str) -> VerificationResult:
        """Check for unsupported absolute claims."""
        issues = []
        for pattern in self.UNSUPPORTED_CLAIM_PATTERNS:
            matches = re.findall(pattern, response, re.IGNORECASE)
            if matches:
                issues.append(f"Absolute claim: '{matches[0]}'")

        if not issues:
            return VerificationResult(
                check="unsupported_claims",
                passed=True, score=1.0,
                issue="", fix=""
            )

        score = max(0.3, 1.0 - (len(issues) * 0.2))
        return VerificationResult(
            check="unsupported_claims",
            passed=len(issues) <= 1,
            score=score,
            issue=f"Found {len(issues)} absolute claim(s): {issues[:2]}",
            fix="Replace absolute claims with probabilistic language (likely, suggests, indicates)"
        )

    def _check_contradictions(self, response: str) -> VerificationResult:
        """Check for internal contradictions."""
        response_lower = response.lower()
        contradictions = []

        for term_a, term_b in self.CONTRADICTION_PATTERNS:
            has_a = bool(re.search(term_a, response_lower))
            has_b = bool(re.search(term_b, response_lower))
            if has_a and has_b:
                # Check if they're in different sections (might be intentional)
                pos_a = response_lower.find(term_a)
                pos_b = response_lower.find(term_b)
                if abs(pos_a - pos_b) < 500:  # Close together = likely contradiction
                    contradictions.append(f"{term_a} vs {term_b}")

        if not contradictions:
            return VerificationResult(
                check="contradictions",
                passed=True, score=1.0,
                issue="", fix=""
            )

        return VerificationResult(
            check="contradictions",
            passed=False,
            score=0.4,
            issue=f"Potential contradictions: {contradictions}",
            fix="Clarify conflicting statements or explain why both apply in different contexts"
        )

    def _check_guardrail_compliance(
        self,
        response: str,
        domain: str,
        tools_used: list[str],
    ) -> VerificationResult:
        """Check if guardrails were applied for high-stakes domains."""
        if domain not in ("financial", "research"):
            return VerificationResult(
                check="guardrail_compliance",
                passed=True, score=1.0,
                issue="", fix=""
            )

        required_signals = self.GUARDRAIL_SIGNALS.get(domain, [])
        response_lower   = response.lower()
        missing          = [s for s in required_signals if s not in response_lower]

        # Financial domain: must have guardrail check if making recommendations
        if domain == "financial":
            has_recommendation = any(
                w in response_lower
                for w in ["buy", "sell", "hold", "invest", "recommend"]
            )
            has_guardrail = "guardrail" in response_lower or "source quality" in response_lower

            if has_recommendation and not has_guardrail:
                return VerificationResult(
                    check="guardrail_compliance",
                    passed=False,
                    score=0.5,
                    issue="Financial recommendation without guardrail check",
                    fix="Apply adversarial guardrail Rule 1 (source hierarchy) before financial recommendations"
                )

        if missing:
            return VerificationResult(
                check="guardrail_compliance",
                passed=len(missing) <= 1,
                score=0.7,
                issue=f"Missing guardrail signals: {missing}",
                fix=f"Include {domain} guardrail compliance check"
            )

        return VerificationResult(
            check="guardrail_compliance",
            passed=True, score=1.0,
            issue="", fix=""
        )

    def _check_confidence_validity(
        self,
        response: str,
        tools_used: list[str],
    ) -> VerificationResult:
        """Check if stated confidence is justified by evidence."""
        response_lower = response.lower()

        # Find stated confidence levels
        conf_matches = re.findall(r"(\d{2,3})%\s*confident", response_lower)
        conf_values  = [int(c) for c in conf_matches]

        if not conf_values:
            return VerificationResult(
                check="confidence_validity",
                passed=True, score=1.0,
                issue="", fix=""
            )

        # Check if high confidence is backed by tools
        high_conf = [c for c in conf_values if c >= 90]
        if high_conf and not tools_used:
            return VerificationResult(
                check="confidence_validity",
                passed=False,
                score=0.5,
                issue=f"High confidence ({high_conf}) stated without tool verification",
                fix="Either call a tool to verify, or lower confidence to ≤70% for unverified claims"
            )

        return VerificationResult(
            check="confidence_validity",
            passed=True, score=0.9,
            issue="", fix=""
        )

    def _check_source_quality(self, response: str) -> VerificationResult:
        """Check if low-quality sources are properly flagged."""
        response_lower = response.lower()

        # Check if web scraping used without quality flag
        uses_scraping = any(
            w in response_lower
            for w in ["duckduckgo", "web search", "web scraping", "search results"]
        )
        has_flag = any(
            w in response_lower
            for w in ["unverified", "degraded", "scraping", "verify", "source quality"]
        )

        if uses_scraping and not has_flag:
            return VerificationResult(
                check="source_quality",
                passed=False,
                score=0.6,
                issue="Web scraping used without quality disclosure",
                fix="Add source quality disclosure per Guardrail Rule 1"
            )

        return VerificationResult(
            check="source_quality",
            passed=True, score=1.0,
            issue="", fix=""
        )

    def evaluate(
        self,
        response:   str,
        domain:     str      = "general",
        tools_used: list[str] = None,
        complexity: str      = "STANDARD",
    ) -> EvaluationReport:
        """Run full evaluation on a response."""
        tools_used = tools_used or []

        # Skip evaluation for simple responses
        if complexity == "SIMPLE" or len(response) < 100:
            return EvaluationReport(
                overall_score=1.0, verdict="PASS",
                checks=[], issues=[], feedback="", caveat=""
            )

        checks = [
            self._check_unsupported_claims(response),
            self._check_contradictions(response),
            self._check_guardrail_compliance(response, domain, tools_used),
            self._check_confidence_validity(response, tools_used),
            self._check_source_quality(response),
        ]

        # Calculate overall score (weighted average)
        weights = [0.2, 0.25, 0.25, 0.15, 0.15]
        overall = sum(c.score * w for c, w in zip(checks, weights))

        # Collect issues
        issues   = [c.issue for c in checks if not c.passed and c.issue]
        feedback = ""
        caveat   = ""

        if overall >= self.PASS_THRESHOLD:
            verdict = "PASS"
        elif overall >= self.WARN_THRESHOLD:
            verdict = "WARN"
            caveat  = f"\n\n⚠️ Verification note: {'; '.join(issues[:2])}"
        else:
            verdict  = "FAIL"
            fixes    = [c.fix for c in checks if not c.passed and c.fix]
            feedback = (
                f"Response quality issues detected:\n"
                + "\n".join(f"- {issue}" for issue in issues)
                + "\n\nRequired fixes:\n"
                + "\n".join(f"- {fix}" for fix in fixes[:3])
            )

        report = EvaluationReport(
            overall_score = round(overall, 3),
            verdict       = verdict,
            checks        = checks,
            issues        = issues,
            feedback      = feedback,
            caveat        = caveat,
        )

        self._eval_history.append(report)
        if len(self._eval_history) > 50:
            self._eval_history = self._eval_history[-50:]

        logger.debug(
            f"VerifierEvaluator: {verdict} (score={overall:.2f}) "
            f"issues={len(issues)}"
        )

        if verdict == "FAIL":
            logger.warning(f"VerifierEvaluator FAIL: {issues}")

        return report

    def get_stats(self) -> dict:
        """Return evaluation statistics."""
        if not self._eval_history:
            return {"total": 0}
        verdicts = [r.verdict for r in self._eval_history]
        return {
            "total":    len(verdicts),
            "pass":     verdicts.count("PASS"),
            "warn":     verdicts.count("WARN"),
            "fail":     verdicts.count("FAIL"),
            "pass_rate": round(verdicts.count("PASS") / len(verdicts), 2),
        }
