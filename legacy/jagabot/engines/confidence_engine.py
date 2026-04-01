# jagabot/engines/confidence_engine.py
"""
ConfidenceEngine — Structured uncertainty communication.

The gap between "I don't know" and genuinely useful uncertainty:

  Basic:     "I'm not sure"
  Structured:"This is uncertain because of a DATA GAP —
              no real-world outcomes have been verified yet.
              This is different from being inherently uncertain."

Two types of uncertainty (from epistemology):
  Aleatory:  inherent randomness — cannot be reduced with more data
             "WTI price in 6 months is aleatory uncertain"
  Epistemic: knowledge gaps — CAN be reduced with more data
             "CVaR timing accuracy is epistemic uncertain —
              we just haven't measured it enough yet"

This distinction matters for a research partner because:
  Epistemic → "let's get more data" (actionable)
  Aleatory  → "let's use probability ranges" (different action)

Five confidence levels (not just high/medium/low):
  VERIFIED:     confirmed by real execution/outcomes
  HIGH:         strong evidence, well-supported
  MODERATE:     reasonable evidence, some uncertainty
  LOW:          weak evidence, significant uncertainty
  UNKNOWN:      no basis for confidence estimate

Wire into loop.py __init__:
    from jagabot.engines.confidence_engine import ConfidenceEngine
    self.confidence_engine = ConfidenceEngine(
        workspace    = workspace,
        brier_scorer = self.brier,
        self_model   = self.self_model,
    )

Wire into loop.py _process_message END (before showing response):
    final_content = self.confidence_engine.annotate_response(
        response    = final_content,
        topic       = detected_topic,
        tools_used  = tools_used,
        exec_output = exec_outputs,  # actual verified numbers
    )

Wire into ProactiveWrapper:
    # Replace generic confidence adjustment with structured version
    confidence_note = self.confidence_engine.get_confidence_note(
        response = response,
        topic    = topic,
    )
    if confidence_note:
        response += f"\n\n{confidence_note}"
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger


# ── Confidence levels ─────────────────────────────────────────────────
class ConfidenceLevel:
    VERIFIED  = "verified"   # confirmed by real execution
    HIGH      = "high"       # strong evidence
    MODERATE  = "moderate"   # reasonable evidence
    LOW       = "low"        # weak evidence
    UNKNOWN   = "unknown"    # no basis


# ── Uncertainty types ─────────────────────────────────────────────────
class UncertaintyType:
    ALEATORY   = "aleatory"   # inherent randomness
    EPISTEMIC  = "epistemic"  # knowledge gap (reducible)
    CONFLICTING= "conflicting"# contradictory evidence
    OUTDATED   = "outdated"   # stale information
    NONE       = "none"       # no uncertainty


# ── Claim patterns ────────────────────────────────────────────────────
CONFIDENCE_PATTERNS = {
    # High confidence signals
    "verified": [
        r'verified',
        r'confirmed by exec',
        r'actual output',
        r'✅.*exec',
        r'from file',
    ],
    # Moderate confidence signals
    "moderate": [
        r'based on',
        r'suggests',
        r'indicates',
        r'appears to',
        r'likely',
    ],
    # Low confidence signals
    "low": [
        r"i'm not (?:sure|certain)",
        r'uncertain',
        r'unclear',
        r'insufficient data',
        r'no data',
        r'cannot verify',
    ],
    # Aleatory uncertainty signals
    "aleatory": [
        r'inherently random',
        r'stochastic',
        r'market (?:risk|uncertainty)',
        r'future (?:price|value|outcome)',
        r'volatility',
        r'probability distribution',
    ],
    # Epistemic uncertainty signals
    "epistemic": [
        r'no (?:data|record|history)',
        r'not yet (?:tested|verified|confirmed)',
        r'pending',
        r'insufficient (?:data|evidence)',
        r'need more',
        r'unknown track record',
    ],
}

# Words that inflate confidence — check against calibration
OVERCONFIDENT_WORDS = [
    "definitely", "certainly", "absolutely", "guaranteed",
    "always", "never fails", "100%", "proven",
]

# Words that appropriately hedge
HEDGED_WORDS = [
    "suggests", "indicates", "appears", "likely", "probably",
    "based on available data", "preliminary", "my analysis shows",
]


@dataclass
class ClaimAnalysis:
    """Analysis of a single claim's confidence and uncertainty."""
    text:              str
    confidence_level:  str    = ConfidenceLevel.UNKNOWN
    uncertainty_type:  str    = UncertaintyType.NONE
    is_overconfident:  bool   = False
    has_evidence:      bool   = False
    evidence_type:     str    = ""  # "exec" | "file" | "memory" | "reasoning"
    suggested_hedge:   str    = ""
    calibration_note:  str    = ""


@dataclass
class ResponseConfidence:
    """Confidence analysis of a full response."""
    overall_level:     str              = ConfidenceLevel.MODERATE
    claims:            list             = field(default_factory=list)
    uncertainty_types: list             = field(default_factory=list)
    overconfident_count: int            = 0
    verified_count:    int              = 0
    needs_annotation:  bool            = False
    summary_note:      str             = ""


class ConfidenceEngine:
    """
    Structured uncertainty communication for AutoJaga.

    Does three things:
    1. ANALYSE: identify confidence level of each claim
    2. CLASSIFY: separate aleatory from epistemic uncertainty
    3. ANNOTATE: add structured confidence notes to responses

    The key output:
    Instead of: "CVaR warns 2 days before breach" (overconfident)
    Outputs:    "CVaR timing is EPISTEMIC UNCERTAIN — we have 0
                verified outcomes in this domain. This gap is
                reducible: run more simulations to know."

    Instead of: "WTI price will be $65 next month" (overconfident)
    Outputs:    "WTI price prediction is ALEATORY UNCERTAIN —
                market prices are inherently stochastic. Use
                probability ranges: 60-75% probability of $60-70."
    """

    def __init__(
        self,
        workspace:    Path,
        brier_scorer: object = None,
        self_model:   object = None,
    ) -> None:
        self.workspace  = Path(workspace)
        self.memory_dir = self.workspace / "memory"
        self.brier      = brier_scorer
        self.self_model = self_model
        self.db_path    = self.memory_dir / "confidence.db"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ── Public API ────────────────────────────────────────────────────

    def annotate_response(
        self,
        response:    str,
        topic:       str       = "general",
        tools_used:  list      = None,
        exec_output: str       = "",
    ) -> str:
        """
        Annotate a response with structured confidence information.
        Called before showing response to user.

        Only adds annotations when:
        - Response contains verifiable claims
        - Overconfidence detected vs calibration history
        - Important uncertainty not already expressed
        """
        tools_used = tools_used or []

        analysis = self._analyse_response(
            response, topic, tools_used, exec_output
        )

        if not analysis.needs_annotation:
            return response  # clean — no annotation needed

        # Build annotation
        note = self._build_confidence_note(analysis, topic)
        if not note:
            return response

        # Append note (don't modify original response)
        return response.rstrip() + f"\n\n{note}"

    def get_confidence_note(
        self,
        response: str,
        topic:    str = "general",
    ) -> str:
        """
        Get a brief confidence note for a response.
        Used by ProactiveWrapper.
        Returns empty string if no note needed.
        """
        analysis = self._analyse_response(response, topic, [], "")
        if not analysis.needs_annotation:
            return ""
        return self._build_confidence_note(analysis, topic)

    def classify_uncertainty(
        self,
        claim:  str,
        topic:  str = "general",
    ) -> tuple[str, str]:
        """
        Classify a claim's uncertainty type.
        Returns (uncertainty_type, explanation).

        Used by StrategicInterceptor before pivot decision.
        """
        claim_lower = claim.lower()

        # Check aleatory signals
        for pattern in CONFIDENCE_PATTERNS["aleatory"]:
            if re.search(pattern, claim_lower):
                return (
                    UncertaintyType.ALEATORY,
                    "This involves inherent randomness that cannot be "
                    "eliminated with more data. Express as probability ranges."
                )

        # Check epistemic signals
        for pattern in CONFIDENCE_PATTERNS["epistemic"]:
            if re.search(pattern, claim_lower):
                return (
                    UncertaintyType.EPISTEMIC,
                    "This is a knowledge gap — more data or verification "
                    "would reduce this uncertainty. "
                    "Flag as pending verification."
                )

        # Check domain calibration
        if self.brier and topic != "general":
            trust = self.brier.trust_score("bear", topic)
            if trust is not None and trust < 0.5:
                return (
                    UncertaintyType.EPISTEMIC,
                    f"Low calibration in {topic} domain "
                    f"(trust={trust:.2f}). "
                    "Historical accuracy insufficient to support "
                    "confident claims."
                )

        return UncertaintyType.NONE, ""

    # ── Stub methods for ConfidenceAwarenessTool ─────────────────────
    # These are called by the awareness tool but not yet implemented

    def analyze_claim(self, claim: str, domain: str = "general") -> object:
        """
        Analyze a claim's confidence level.
        Returns ClaimAnalysis object (stub for now).
        """
        from dataclasses import dataclass
        
        @dataclass
        class ClaimAnalysis:
            text: str = ""
            confidence_level: str = "unknown"
            uncertainty_type: str = "none"
            evidence_strength: str = "insufficient"
            calibration_note: str = ""
            suggested_hedge: str = ""
        
        # Simple heuristic analysis
        confidence = "unknown"
        if self.brier and domain != "general":
            trust = self.brier.trust_score("bear", domain)
            if trust and trust > 0.75:
                confidence = "moderate"
            elif trust and trust < 0.4:
                confidence = "low"
        
        return ClaimAnalysis(
            text=claim,
            confidence_level=confidence,
            uncertainty_type=self.classify_uncertainty(claim, domain)[0],
            evidence_strength="insufficient",
            calibration_note=f"Domain '{domain}' calibration check needed",
            suggested_hedge="Consider hedging: 'preliminary analysis suggests'"
        )

    def check_overconfidence(self, text: str) -> object:
        """
        Check text for overconfident language.
        Returns OverconfidenceResult object (stub for now).
        """
        from dataclasses import dataclass
        
        @dataclass
        class OverconfidenceResult:
            overconfidence_detected: bool = False
            overconfident_phrases: list = None
            suggested_hedges: dict = None
            domain_calibration_warning: str = ""
        
        result = OverconfidenceResult(
            overconfident_phrases=[],
            suggested_hedges={},
        )
        
        # Check for overconfident words
        for word in OVERCONFIDENT_WORDS:
            if word.lower() in text.lower():
                result.overconfidence_detected = True
                result.overconfident_phrases.append(word)
                result.suggested_hedges[word] = f"Consider: 'suggests' instead of '{word}'"
        
        return result

    def get_calibration_history(self, domain: str = None, limit: int = 10) -> list:
        """
        Get calibration history (stub for now).
        Returns list of calibration entries.
        """
        from dataclasses import dataclass
        
        @dataclass
        class CalibrationEntry:
            claim: str = ""
            original_confidence: str = ""
            outcome: str = "pending"
            domain: str = ""
        
        # Return empty list for now - will be populated from outcome_tracker
        return []

    def assess_claim(
        self,
        claim:     str,
        topic:     str  = "general",
        from_exec: bool = False,
    ) -> ClaimAnalysis:
        """
        Assess confidence level of a single claim.
        Used internally and by external callers.
        """
        analysis = ClaimAnalysis(text=claim[:200])

        # Highest confidence: from exec output
        if from_exec or self._appears_from_exec(claim):
            analysis.confidence_level = ConfidenceLevel.VERIFIED
            analysis.has_evidence     = True
            analysis.evidence_type    = "exec"
            return analysis

        # Check for overconfident language
        claim_lower = claim.lower()
        for word in OVERCONFIDENT_WORDS:
            if word in claim_lower:
                analysis.is_overconfident = True
                analysis.suggested_hedge  = self._suggest_hedge(word)
                break

        # Check for explicit evidence
        if any(
            s in claim_lower
            for s in ["from file", "read_file returned", "grep found"]
        ):
            analysis.confidence_level = ConfidenceLevel.HIGH
            analysis.has_evidence     = True
            analysis.evidence_type    = "file"
            return analysis

        if any(
            s in claim_lower
            for s in ["memory.md", "history.md", "verified fact"]
        ):
            analysis.confidence_level = ConfidenceLevel.HIGH
            analysis.has_evidence     = True
            analysis.evidence_type    = "memory"
            return analysis

        # Check hedging patterns
        if any(
            re.search(p, claim_lower)
            for p in CONFIDENCE_PATTERNS["moderate"]
        ):
            analysis.confidence_level = ConfidenceLevel.MODERATE
            return analysis

        # Check low confidence patterns
        if any(
            re.search(p, claim_lower)
            for p in CONFIDENCE_PATTERNS["low"]
        ):
            analysis.confidence_level = ConfidenceLevel.LOW
            return analysis

        # Check calibration data
        calibration_note = self._get_calibration_note(topic)
        if calibration_note:
            analysis.calibration_note = calibration_note

        # Default: moderate
        analysis.confidence_level = ConfidenceLevel.MODERATE
        return analysis

    def record_claim_outcome(
        self,
        claim:    str,
        topic:    str,
        correct:  bool,
        level_at_time: str,
    ) -> None:
        """
        Record whether a claim at a given confidence level was correct.
        Builds calibration history for confidence levels.
        """
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO claim_outcomes
            (claim, topic, level_at_time, correct, recorded_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            claim[:200], topic, level_at_time,
            1 if correct else 0,
            datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()

    def get_level_accuracy(self, level: str) -> Optional[float]:
        """
        Return historical accuracy for claims at a confidence level.
        E.g., "when we said HIGH confidence, were we right X% of time?"
        """
        conn   = sqlite3.connect(self.db_path)
        result = conn.execute("""
            SELECT AVG(correct), COUNT(*)
            FROM claim_outcomes
            WHERE level_at_time = ?
        """, (level,)).fetchone()
        conn.close()

        if not result or result[1] < 3:
            return None
        return result[0]

    def format_status(self) -> str:
        """Format confidence engine status for /status command."""
        lines = ["**ConfidenceEngine**", ""]

        levels = [
            ConfidenceLevel.VERIFIED,
            ConfidenceLevel.HIGH,
            ConfidenceLevel.MODERATE,
            ConfidenceLevel.LOW,
        ]

        has_data = False
        for level in levels:
            accuracy = self.get_level_accuracy(level)
            if accuracy is not None:
                has_data = True
                target   = {
                    "verified": 0.95,
                    "high":     0.80,
                    "moderate": 0.65,
                    "low":      0.40,
                }.get(level, 0.5)
                gap  = accuracy - target
                icon = "✅" if gap >= -0.05 else "⚠️"
                lines.append(
                    f"{icon} {level:<10} "
                    f"actual={accuracy:.0%} "
                    f"target={target:.0%} "
                    f"gap={gap:+.0%}"
                )

        if not has_data:
            lines.append(
                "No calibration data yet. "
                "Records claim outcomes as verdicts are given."
            )

        lines += [
            "",
            "Uncertainty types tracked:",
            f"  Aleatory:   inherent randomness — use ranges",
            f"  Epistemic:  knowledge gaps — get more data",
        ]

        return "\n".join(lines)

    # ── Analysis ──────────────────────────────────────────────────────

    def _analyse_response(
        self,
        response:    str,
        topic:       str,
        tools_used:  list,
        exec_output: str,
    ) -> ResponseConfidence:
        """Analyse full response for confidence issues."""
        analysis = ResponseConfidence()

        has_exec   = "exec" in tools_used or bool(exec_output)
        resp_lower = response.lower()

        # Count overconfident claims
        for word in OVERCONFIDENT_WORDS:
            if word in resp_lower:
                analysis.overconfident_count += 1

        # Count verified claims (from exec)
        exec_signals = ["✅", "exec output", "actual result", "verified:"]
        for sig in exec_signals:
            if sig in resp_lower:
                analysis.verified_count += 1

        # Check calibration vs expressed confidence
        if self.brier:
            try:
                trust = self.brier.trust_score("bear", topic)
                if trust is not None and trust < 0.5:
                    # Low trust domain — check if hedging adequately
                    has_hedge = any(w in resp_lower for w in HEDGED_WORDS)
                    has_overconf = any(
                        w in resp_lower for w in OVERCONFIDENT_WORDS
                    )
                    if has_overconf and not has_hedge:
                        analysis.needs_annotation = True
                        analysis.summary_note = (
                            f"Low calibration in {topic} "
                            f"(trust={trust:.2f})"
                        )
            except Exception:
                pass

        # Check for mixed signals (overconfident + uncertain)
        has_uncertain = any(
            re.search(p, resp_lower)
            for p in CONFIDENCE_PATTERNS["low"]
        )
        if analysis.overconfident_count > 0 and has_uncertain:
            analysis.needs_annotation = True
            analysis.summary_note = "Mixed confidence signals detected"

        # Determine overall level
        if analysis.verified_count > analysis.overconfident_count:
            analysis.overall_level = ConfidenceLevel.HIGH
        elif analysis.overconfident_count > 2:
            analysis.overall_level = ConfidenceLevel.LOW
            analysis.needs_annotation = True
        else:
            analysis.overall_level = ConfidenceLevel.MODERATE

        # Detect uncertainty types present
        for unc_type, patterns in [
            ("aleatory",  CONFIDENCE_PATTERNS["aleatory"]),
            ("epistemic", CONFIDENCE_PATTERNS["epistemic"]),
        ]:
            if any(re.search(p, resp_lower) for p in patterns):
                analysis.uncertainty_types.append(unc_type)

        return analysis

    def _build_confidence_note(
        self,
        analysis: ResponseConfidence,
        topic:    str,
    ) -> str:
        """Build a structured confidence note."""
        lines = []

        # Calibration warning
        if analysis.summary_note:
            lines.append(
                f"*⚠️ Confidence note: {analysis.summary_note}. "
                f"Treat claims in '{topic}' as preliminary until "
                f"verified by real outcomes.*"
            )

        # Uncertainty type guide
        if "aleatory" in analysis.uncertainty_types:
            lines.append(
                "*📊 Aleatory uncertainty present — "
                "some predictions are inherently probabilistic. "
                "Use ranges rather than point estimates.*"
            )

        if "epistemic" in analysis.uncertainty_types:
            lines.append(
                "*🔬 Epistemic uncertainty present — "
                "this gap is reducible with more data or verification. "
                "Consider: run a test, verify with real data.*"
            )

        # Overconfidence warning
        if analysis.overconfident_count > 1:
            lines.append(
                f"*Note: {analysis.overconfident_count} high-confidence "
                f"expressions detected. "
                f"Domain calibration: "
                f"{self._get_domain_trust_summary(topic)}*"
            )

        return "\n".join(lines) if lines else ""

    # ── Helpers ───────────────────────────────────────────────────────

    def _appears_from_exec(self, text: str) -> bool:
        """Check if a claim appears to come from exec output."""
        exec_markers = [
            "exec output:", "actual output:", ">>",
            "✅ executed", "python output",
        ]
        return any(m in text.lower() for m in exec_markers)

    def _suggest_hedge(self, overconfident_word: str) -> str:
        """Suggest a hedged alternative for an overconfident word."""
        hedges = {
            "definitely":  "based on available evidence",
            "certainly":   "the evidence suggests",
            "absolutely":  "analysis indicates",
            "guaranteed":  "historically likely",
            "always":      "typically",
            "100%":        "with high confidence",
            "proven":      "supported by evidence",
        }
        return hedges.get(overconfident_word, "likely")

    def _get_calibration_note(self, topic: str) -> str:
        """Get calibration note from BrierScorer."""
        if not self.brier:
            return ""
        try:
            trust = self.brier.trust_score("bear", topic)
            if trust is None:
                return ""
            if trust < 0.4:
                return (
                    f"Low domain trust ({trust:.2f}) — "
                    "express high uncertainty"
                )
            if trust > 0.8:
                return f"High domain trust ({trust:.2f})"
            return ""
        except Exception:
            return ""

    def _get_domain_trust_summary(self, topic: str) -> str:
        """Get brief domain trust summary."""
        if not self.brier:
            return "unknown (no calibration data)"
        try:
            trust = self.brier.trust_score("bear", topic)
            if trust is None:
                return "insufficient data"
            return f"{trust:.2f}/1.0 in {topic}"
        except Exception:
            return "unavailable"

    # ── Database ──────────────────────────────────────────────────────

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS claim_outcomes (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                claim           TEXT    NOT NULL,
                topic           TEXT    NOT NULL,
                level_at_time   TEXT    NOT NULL,
                correct         INTEGER NOT NULL,
                recorded_at     TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS uncertainty_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                topic           TEXT    NOT NULL,
                uncertainty_type TEXT   NOT NULL,
                description     TEXT    NOT NULL,
                logged_at       TEXT    NOT NULL
            );
        """)
        conn.commit()
        conn.close()
