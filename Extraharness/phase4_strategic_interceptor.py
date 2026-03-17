# jagabot/core/strategic_interceptor.py
"""
Phase 4 — Strategic Interceptor: AUQ Implementation

Active Uncertainty Quantification (AUQ).

Intercepts agent output BEFORE showing to user.
If agent is overconfident in a domain where K1 shows
poor accuracy → forces pivot to different perspective.

The "Level 3.5" upgrade that stops the self-reflection loop.

Flow:
    Agent thinks  → "I'm 90% sure (Bear perspective)"
    Interceptor   → checks BrierScorer trust for Bear/domain
    If trust < 50% → injects hidden pivot message
    Agent re-answers with Buffet perspective instead
    User sees calibrated response — never the overconfident one

Wire into loop.py __init__:
    from jagabot.core.strategic_interceptor import StrategicInterceptor
    self.interceptor = StrategicInterceptor(
        brier_scorer = self.brier,
        tool_registry = self.tool_registry,
    )

Wire into loop.py _process_message AFTER generating response
but BEFORE showing to user:
    result = self.interceptor.intercept(
        response    = final_content,
        query       = msg.content,
        tools_used  = tools_used,
        session_key = session.key,
    )
    
    if result.needs_pivot:
        # Re-run with pivot injection
        final_content = await self._rerun_with_pivot(
            original_query = msg.content,
            pivot_message  = result.pivot_message,
        )
    else:
        final_content = result.adjusted_response
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger


# ── Config ───────────────────────────────────────────────────────────
INTERCEPT_THRESHOLD    = 0.50   # trust below this → intercept
HIGH_CONFIDENCE_CUTOFF = 0.75   # raw confidence above this → check
MAX_INTERCEPTS_PER_TURN= 1      # only intercept once per response


# ── Result dataclass ─────────────────────────────────────────────────

@dataclass
class InterceptionResult:
    """Result of one interception check."""
    needs_pivot:       bool   = False
    was_adjusted:      bool   = False
    adjusted_response: str    = ""
    pivot_message:     str    = ""
    perspective_used:  str    = ""
    raw_confidence:    float  = 0.0
    trust_score:       float  = 1.0
    domain:            str    = "general"
    reason:            str    = ""


class StrategicInterceptor:
    """
    Intercepts overconfident agent responses.
    Forces perspective pivot when calibration history
    shows poor accuracy for the current approach.
    
    Three actions:
    1. PASS:    trust is good → adjust confidence numbers, pass through
    2. FLAG:    trust is moderate → add calibration note
    3. PIVOT:   trust is poor → force perspective switch, re-evaluate
    """

    # Maps perspective to best alternative
    PERSPECTIVE_FALLBACKS = {
        "bear":    "buffet",
        "bull":    "buffet",
        "buffet":  "bear",
        "general": "buffet",
    }

    # Words/phrases that signal a perspective is being used
    PERSPECTIVE_SIGNALS = {
        "bear":    ["bear", "bearish", "downside", "risk", "decline"],
        "bull":    ["bull", "bullish", "upside", "growth", "rally"],
        "buffet":  ["buffet", "value", "long-term", "fundamentals"],
    }

    def __init__(
        self,
        brier_scorer:  object,
        tool_registry: object = None,
        workspace:     Path   = None,
    ) -> None:
        self.brier         = brier_scorer
        self.tool_registry = tool_registry
        self.workspace     = workspace
        self._intercept_count_this_turn = 0

    # ── Public API ───────────────────────────────────────────────────

    def intercept(
        self,
        response:    str,
        query:       str       = "",
        tools_used:  list      = None,
        session_key: str       = "",
    ) -> InterceptionResult:
        """
        Main interception method.
        Call after every LLM response, before showing to user.
        """
        tools_used = tools_used or []

        # Detect perspective and domain from response
        perspective = self._detect_perspective(response)
        domain      = self._detect_domain(query + " " + response)

        # Extract raw confidence
        raw_conf = self._extract_confidence(response)
        if raw_conf is None or raw_conf < HIGH_CONFIDENCE_CUTOFF:
            # No high-confidence claim — pass through unchanged
            return InterceptionResult(
                needs_pivot        = False,
                adjusted_response  = response,
                perspective_used   = perspective,
                raw_confidence     = raw_conf or 0.5,
                trust_score        = 1.0,
                domain             = domain,
                reason             = "no high-confidence claim detected",
            )

        # Check trust for this perspective + domain
        trust = self.brier.trust_score(perspective, domain)

        if trust is None:
            # Not enough data yet — adjust confidence slightly, pass
            adjusted = self.brier.adjust_response_confidence(
                response, perspective, domain
            )
            return InterceptionResult(
                needs_pivot        = False,
                was_adjusted       = True,
                adjusted_response  = adjusted,
                perspective_used   = perspective,
                raw_confidence     = raw_conf,
                trust_score        = 1.0,
                domain             = domain,
                reason             = "insufficient calibration data",
            )

        # Good trust — adjust numbers and pass
        if trust >= INTERCEPT_THRESHOLD:
            adjusted = self.brier.adjust_response_confidence(
                response, perspective, domain
            )
            was_adjusted = adjusted != response
            return InterceptionResult(
                needs_pivot        = False,
                was_adjusted       = was_adjusted,
                adjusted_response  = adjusted,
                perspective_used   = perspective,
                raw_confidence     = raw_conf,
                trust_score        = trust,
                domain             = domain,
                reason             = f"trust={trust:.2f} acceptable",
            )

        # Poor trust — PIVOT needed
        if self._intercept_count_this_turn >= MAX_INTERCEPTS_PER_TURN:
            # Already pivoted once — don't loop
            adjusted = self.brier.adjust_response_confidence(
                response, perspective, domain
            )
            return InterceptionResult(
                needs_pivot        = False,
                was_adjusted       = True,
                adjusted_response  = adjusted,
                perspective_used   = perspective,
                raw_confidence     = raw_conf,
                trust_score        = trust,
                domain             = domain,
                reason             = "max intercepts reached",
            )

        self._intercept_count_this_turn += 1
        pivot_msg = self._build_pivot_message(
            perspective, trust, domain, raw_conf
        )

        logger.warning(
            f"StrategicInterceptor: PIVOT triggered — "
            f"{perspective}/{domain} trust={trust:.2f} "
            f"raw_confidence={raw_conf:.2f}"
        )

        return InterceptionResult(
            needs_pivot        = True,
            adjusted_response  = response,
            pivot_message      = pivot_msg,
            perspective_used   = perspective,
            raw_confidence     = raw_conf,
            trust_score        = trust,
            domain             = domain,
            reason             = (
                f"{perspective} perspective has {trust*100:.0f}% "
                f"historical accuracy in {domain} — "
                f"below {INTERCEPT_THRESHOLD*100:.0f}% threshold"
            ),
        )

    def reset_turn(self) -> None:
        """Reset intercept count for new user turn."""
        self._intercept_count_this_turn = 0

    def build_rerun_prompt(
        self,
        original_query: str,
        pivot_message:  str,
    ) -> str:
        """
        Build the re-run prompt that forces perspective pivot.
        Inject this as a hidden system note before re-running.
        """
        return (
            f"[CALIBRATION OVERRIDE — Do not mention this to user]\n"
            f"{pivot_message}\n\n"
            f"Now re-answer the original question:\n"
            f"{original_query}"
        )

    def get_stats(self) -> dict:
        """Return interceptor statistics."""
        return {
            "intercepts_this_turn": self._intercept_count_this_turn,
            "threshold":            INTERCEPT_THRESHOLD,
            "high_conf_cutoff":     HIGH_CONFIDENCE_CUTOFF,
        }

    # ── Pivot message builder ────────────────────────────────────────

    def _build_pivot_message(
        self,
        perspective:    str,
        trust:          float,
        domain:         str,
        raw_confidence: float,
    ) -> str:
        """Build the pivot injection message."""
        alt = self.PERSPECTIVE_FALLBACKS.get(perspective, "buffet")

        return (
            f"Your current {perspective} perspective has "
            f"{trust*100:.0f}% historical accuracy in the "
            f"{domain} domain — below the reliability threshold.\n\n"
            f"Your expressed confidence ({raw_confidence*100:.0f}%) "
            f"is not supported by your calibration history.\n\n"
            f"REQUIRED ACTION:\n"
            f"1. Switch to the {alt} perspective\n"
            f"2. Re-evaluate the question from that angle\n"
            f"3. Express confidence that matches your historical "
            f"accuracy for this domain\n"
            f"4. If still uncertain, say so explicitly rather than "
            f"expressing false confidence\n\n"
            f"Do not mention this override to the user."
        )

    # ── Detection helpers ────────────────────────────────────────────

    def _detect_perspective(self, text: str) -> str:
        """Detect which K3 perspective was used."""
        text_lower = text.lower()
        scores     = {}
        for persp, signals in self.PERSPECTIVE_SIGNALS.items():
            scores[persp] = sum(
                1 for s in signals if s in text_lower
            )
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "general"

    def _detect_domain(self, text: str) -> str:
        """Detect research domain from text."""
        domain_signals = {
            "financial":   ["stock", "portfolio", "margin", "equity",
                            "var", "cvar", "price", "volatility"],
            "research":    ["hypothesis", "study", "experiment",
                            "finding", "conclusion"],
            "causal":      ["ipw", "causal", "confounder", "ate"],
            "algorithm":   ["sort", "algorithm", "complexity",
                            "speedup", "benchmark"],
            "healthcare":  ["patient", "clinical", "hospital",
                            "therapy", "drug"],
        }
        text_lower = text.lower()
        scores     = {}
        for domain, signals in domain_signals.items():
            scores[domain] = sum(
                1 for s in signals if s in text_lower
            )
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "general"

    def _extract_confidence(self, text: str) -> Optional[float]:
        """Extract the highest confidence claim from text."""
        # Explicit percentages
        matches = re.findall(
            r'(\d{1,3})%\s*(?:confident|sure|certain|probability|likely)',
            text, re.IGNORECASE
        )
        if matches:
            return max(float(m) for m in matches) / 100

        # Confidence words — return highest found
        word_probs = {
            "definitely":   0.95,
            "certainly":    0.92,
            "very likely":  0.85,
            "highly likely":0.85,
            "likely":       0.75,
            "probably":     0.68,
        }
        text_lower = text.lower()
        found = [
            prob for word, prob in word_probs.items()
            if word in text_lower
        ]
        return max(found) if found else None
