"""
Confidence Awareness Tool — Makes agent explicitly aware of uncertainty calibration.

This tool exposes the ConfidenceEngine to the agent so it can:
1. Check confidence level for specific claims
2. Identify overconfident language in responses
3. Get structured uncertainty annotations
4. Review claim verification history
5. Learn appropriate hedging for different uncertainty types

Wire into loop.py __init__:
    registry.register(ConfidenceAwarenessTool(
        confidence_engine=self.confidence_engine,
    ))
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jagabot.agent.tools.base import Tool


class ConfidenceAwarenessTool(Tool):
    """
    Confidence awareness — explicit uncertainty calibration for the agent.
    
    The agent can explicitly query:
    - claim_confidence: Check confidence level for a specific claim
    - response_annotation: Get structured uncertainty annotations for response
    - overconfidence_check: Identify overconfident language
    - uncertainty_type: Distinguish aleatory vs epistemic uncertainty
    - calibration_history: Review past claim verification outcomes
    """

    name = "confidence_awareness"
    description = (
        "Confidence awareness — query uncertainty calibration and get structured annotations.\n\n"
        "Actions:\n"
        "- claim_confidence: Check confidence level for a specific claim\n"
        "- response_annotation: Get structured uncertainty annotations for response\n"
        "- overconfidence_check: Identify overconfident language in text\n"
        "- uncertainty_type: Distinguish aleatory vs epistemic uncertainty\n"
        "- calibration_history: Review past claim verification outcomes\n\n"
        "Use claim_confidence BEFORE making strong claims.\n"
        "Use response_annotation to add structured uncertainty notes.\n"
        "Use overconfidence_check to self-edit before responding.\n\n"
        "Chain: Before financial predictions, check claim_confidence. "
        "If low calibration, use hedged language."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "claim_confidence", "response_annotation",
                    "overconfidence_check", "uncertainty_type",
                    "calibration_history",
                ],
                "description": (
                    "claim_confidence: {claim, domain}. "
                    "response_annotation: {response, domain, tools_used}. "
                    "overconfidence_check: {text}. "
                    "uncertainty_type: {claim}. "
                    "calibration_history: {domain?, limit?}."
                ),
            },
            "claim": {"type": "string", "description": "Claim text for claim_confidence"},
            "domain": {"type": "string", "description": "Domain for claim_confidence"},
            "response": {"type": "string", "description": "Response text for response_annotation"},
            "tools_used": {"type": "array", "items": {"type": "string"}, "description": "Tools used for response_annotation"},
            "text": {"type": "string", "description": "Text to check for overconfidence_check"},
        },
        "required": ["action"],
    }

    def __init__(
        self,
        confidence_engine: object = None,
        workspace: Path = None,
    ) -> None:
        self.confidence_engine = confidence_engine
        self.workspace = workspace or Path.home() / ".jagabot"

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")

        if not self.confidence_engine:
            return "⚠️  ConfidenceEngine not initialized"

        if action == "claim_confidence":
            return self._claim_confidence(kwargs)

        if action == "response_annotation":
            return self._response_annotation(kwargs)

        if action == "overconfidence_check":
            return self._overconfidence_check(kwargs)

        if action == "uncertainty_type":
            return self._uncertainty_type(kwargs)

        if action == "calibration_history":
            return self._calibration_history(kwargs)

        return f"Unknown action: {action}"

    def _claim_confidence(self, kwargs: dict) -> str:
        """Check confidence level for a specific claim."""
        claim = kwargs.get("claim", "")
        domain = kwargs.get("domain", "general")

        if not claim:
            return "❌ Error: 'claim' is required for claim_confidence"

        analysis = self.confidence_engine.analyze_claim(
            claim=claim,
            domain=domain,
        )

        confidence_icon = {
            "verified": "✅",
            "high": "🟢",
            "moderate": "🔵",
            "low": "🟡",
            "unknown": "❓",
        }.get(analysis.confidence_level, "❓")

        lines = [
            f"{confidence_icon} **Claim Confidence: {analysis.confidence_level.upper()}**",
            "",
            f"**Claim:** {claim[:100]}",
            f"**Domain:** {domain}",
            "",
            f"**Uncertainty Type:** {analysis.uncertainty_type}",
            f"**Evidence Strength:** {analysis.evidence_strength}",
            "",
        ]

        if analysis.calibration_note:
            lines.append(f"**Note:** {analysis.calibration_note}")

        if analysis.suggested_hedge:
            lines.append(f"**Suggested Hedge:** {analysis.suggested_hedge}")

        return "\n".join(lines)

    def _response_annotation(self, kwargs: dict) -> str:
        """Get structured uncertainty annotations for response."""
        response = kwargs.get("response", "")
        domain = kwargs.get("domain", "general")
        tools_used = kwargs.get("tools_used", [])

        if not response:
            return "❌ Error: 'response' is required for response_annotation"

        # ConfidenceEngine uses 'topic' not 'domain'
        annotated = self.confidence_engine.annotate_response(
            response=response,
            topic=domain,  # Use 'topic' parameter name
            tools_used=tools_used,
        )

        # Count annotations
        annotation_count = annotated.count("⚠️") + annotated.count("🔵") + annotated.count("✅")

        lines = [
            f"**Response Annotation** ({annotation_count} annotations)",
            "",
            annotated,
        ]

        return "\n".join(lines)

    def _overconfidence_check(self, kwargs: dict) -> str:
        """Identify overconfident language in text."""
        text = kwargs.get("text", "")

        if not text:
            return "❌ Error: 'text' is required for overconfidence_check"

        result = self.confidence_engine.check_overconfidence(text)

        if not result.overconfidence_detected:
            return (
                "✅ **No overconfidence detected**\n\n"
                "Your language is appropriately calibrated. "
                "Continue using hedged language where appropriate."
            )

        lines = [
            f"⚠️ **Overconfidence Detected** ({len(result.overconfident_phrases)} phrases)",
            "",
        ]

        for phrase in result.overconfident_phrases[:5]:
            lines.append(f"- \"{phrase[:80]}...\"")
            if phrase in result.suggested_hedges:
                lines.append(f"  → Suggested: {result.suggested_hedges[phrase]}")

        if result.domain_calibration_warning:
            lines.append("")
            lines.append(f"**Domain Warning:** {result.domain_calibration_warning}")

        lines.append("")
        lines.append(
            "Replace overconfident phrases with suggested hedges. "
            "Express uncertainty explicitly in low-calibration domains."
        )

        return "\n".join(lines)

    def _uncertainty_type(self, kwargs: dict) -> str:
        """Distinguish aleatory vs epistemic uncertainty."""
        claim = kwargs.get("claim", "")

        if not claim:
            return "❌ Error: 'claim' is required for uncertainty_type"

        uncertainty_type = self.confidence_engine.classify_uncertainty(claim)

        type_icon = {
            "aleatory": "🎲",
            "epistemic": "📚",
            "conflicting": "⚖️",
            "outdated": "🕐",
            "none": "✅",
        }.get(uncertainty_type, "❓")

        lines = [
            f"{type_icon} **Uncertainty Type: {uncertainty_type.upper()}**",
            "",
            f"**Claim:** {claim[:100]}",
            "",
        ]

        if uncertainty_type == "aleatory":
            lines.append(
                "**Meaning:** Inherent randomness — cannot be reduced with more data.\n"
                "**Action:** Use probability ranges, express as distributions.\n"
                "**Example:** \"WTI price next month is inherently uncertain (aleatory)\""
            )
        elif uncertainty_type == "epistemic":
            lines.append(
                "**Meaning:** Knowledge gap — CAN be reduced with more data.\n"
                "**Action:** Run simulations, gather real data, verify claims.\n"
                "**Example:** \"CVaR timing accuracy needs more measurements (epistemic)\""
            )
        elif uncertainty_type == "conflicting":
            lines.append(
                "**Meaning:** Contradictory evidence from different sources.\n"
                "**Action:** Reconcile sources, check methodology, flag inconsistency.\n"
                "**Example:** \"Studies show conflicting results on this claim\""
            )
        elif uncertainty_type == "outdated":
            lines.append(
                "**Meaning:** Information is stale — may no longer be accurate.\n"
                "**Action:** Refresh data, check for recent developments.\n"
                "**Example:** \"This data is 90 days old — verify current status\""
            )
        else:
            lines.append(
                "**Meaning:** No significant uncertainty detected.\n"
                "**Action:** Proceed with appropriate confidence level."
            )

        return "\n".join(lines)

    def _calibration_history(self, kwargs: dict) -> str:
        """Review past claim verification outcomes."""
        domain = kwargs.get("domain")
        limit = kwargs.get("limit", 10)

        history = self.confidence_engine.get_calibration_history(domain=domain, limit=limit)

        if not history:
            return (
                "✅ **No calibration history yet**\n\n"
                "Claims haven't been verified against real outcomes yet. "
                "Use outcome_tracker to record verdicts and build calibration data."
            )

        lines = [
            f"**Calibration History** ({len(history)} claims)",
            "",
        ]

        # Calculate calibration stats
        verified = sum(1 for h in history if h.outcome == "verified")
        wrong = sum(1 for h in history if h.outcome == "wrong")
        calibration_rate = verified / len(history) if history else 0

        for entry in history[:10]:
            outcome_icon = {
                "verified": "✅",
                "wrong": "❌",
                "inconclusive": "❓",
            }.get(entry.outcome, "⚪")

            lines.append(
                f"{outcome_icon} **{entry.claim[:60]}...**\n"
                f"   **Original Confidence:** {entry.original_confidence}\n"
                f"   **Outcome:** {entry.outcome}\n"
                f"   **Domain:** {entry.domain}\n"
            )

        lines.append("")
        lines.append(
            f"**Calibration Rate:** {calibration_rate:.0%} ({verified}/{len(history)})\n"
            f"Higher rate = better confidence calibration"
        )

        return "\n".join(lines)
