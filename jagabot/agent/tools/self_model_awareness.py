"""
SelfModel Awareness Tool — Makes agent explicitly aware of its own capabilities.

This tool exposes the SelfModelEngine to the agent so it can:
1. Query its own reliability per domain
2. Check capability success rates
3. See knowledge gaps explicitly
4. Report honestly on what it knows/doesn't know
5. Update self-model from interactions

Wire into tool_loader.py:
    registry.register(SelfModelAwarenessTool(
        self_model_engine=self.self_model,
    ))
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jagabot.agent.tools.base import Tool


class SelfModelAwarenessTool(Tool):
    """
    Self-model awareness — explicit self-knowledge for the agent.
    
    The agent can explicitly query:
    - domain_reliability: How reliable am I in this domain?
    - capability_success: What's my success rate on this capability?
    - knowledge_gaps: What don't I know yet?
    - full_status: Complete self-model status report
    - update_self_model: Record new self-knowledge from interaction
    """

    name = "self_model_awareness"
    description = (
        "Self-model awareness — query your own capabilities, reliability, and knowledge gaps.\n\n"
        "Actions:\n"
        "- domain_reliability: Check your reliability in a specific domain\n"
        "- capability_success: Check your success rate on a capability\n"
        "- knowledge_gaps: List your current knowledge gaps\n"
        "- full_status: Get complete self-model status report\n"
        "- update_self_model: Record new self-knowledge from interaction\n\n"
        "Use domain_reliability BEFORE making claims in that domain.\n"
        "Use knowledge_gaps to identify what needs research.\n"
        "Use full_status for /status command or self-reflection.\n\n"
        "Chain: Before financial predictions, check domain_reliability. "
        "If unreliable, hedge language and express uncertainty."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "domain_reliability", "capability_success",
                    "knowledge_gaps", "full_status",
                    "update_self_model",
                ],
                "description": (
                    "domain_reliability: {domain}. "
                    "capability_success: {capability}. "
                    "knowledge_gaps: {domain?}. "
                    "full_status: {}. "
                    "update_self_model: {domain, capability, quality, claim}."
                ),
            },
            "domain": {"type": "string", "description": "Domain for domain_reliability"},
            "capability": {"type": "string", "description": "Capability for capability_success"},
            "quality": {"type": "number", "description": "Quality score for update_self_model"},
            "claim": {"type": "string", "description": "Claim made for update_self_model"},
        },
        "required": ["action"],
    }

    def __init__(
        self,
        self_model_engine: object = None,
        workspace: Path = None,
    ) -> None:
        self.self_model = self_model_engine
        self.workspace = workspace or Path.home() / ".jagabot"
        
        # Log initialization state
        from loguru import logger
        if self.self_model:
            logger.info(f"SelfModelAwarenessTool initialized with SelfModelEngine")
        else:
            logger.warning(f"SelfModelAwarenessTool initialized WITHOUT SelfModelEngine - will be wired later")

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")

        if not self.self_model:
            from loguru import logger
            logger.error(f"SelfModelAwarenessTool.execute() called but self_model is None!")
            return (
                "⚠️  **SelfModelEngine not initialized**\n\n"
                "The self-modeling system exists but hasn't been wired yet. "
                "This should be fixed in loop.py __init__ by setting:\n\n"
                "```python\n"
                "self_aware_tool.self_model = self.self_model\n"
                "```\n\n"
                "Check logs for wiring confirmation."
            )

        if action == "domain_reliability":
            return self._domain_reliability(kwargs)

        if action == "capability_success":
            return self._capability_success(kwargs)

        if action == "knowledge_gaps":
            return self._knowledge_gaps(kwargs)

        if action == "full_status":
            return self._full_status()

        if action == "update_self_model":
            return self._update_self_model(kwargs)

        return f"Unknown action: {action}"

    def _domain_reliability(self, kwargs: dict) -> str:
        """Check reliability in a specific domain."""
        domain = kwargs.get("domain", "general")

        domain_model = self.self_model.get_domain_model(domain)

        if not domain_model:
            return (
                f"❓ **No data for domain: {domain}**\n\n"
                f"You have no sessions recorded in this domain yet. "
                f"Express uncertainty explicitly — don't infer reliability "
                f"from training data."
            )

        # Format reliability status
        status_icon = {
            "reliable": "✅",
            "moderate": "🔵",
            "unreliable": "⚠️",
            "unknown": "❓",
        }.get(domain_model.confidence_level, "❓")

        lines = [
            f"{status_icon} **Domain Reliability: {domain}**",
            "",
            f"**Status:** {domain_model.confidence_level}",
            f"**Reliability Score:** {domain_model.reliability:.2f}",
            f"**Sessions:** {domain_model.session_count}",
            f"**Quality Avg:** {domain_model.quality_avg:.2f}",
            "",
        ]

        if domain_model.verified_facts > 0:
            lines.append(f"**Verified Facts:** {domain_model.verified_facts} ✅")
        if domain_model.wrong_claims > 0:
            lines.append(f"**Wrong Claims:** {domain_model.wrong_claims} ❌")
        if domain_model.pending_outcomes > 0:
            lines.append(f"**Pending Outcomes:** {domain_model.pending_outcomes} ⏳")

        lines.append("")

        # Add confidence guide
        if domain_model.confidence_level == "reliable":
            lines.append(
                "**Confidence Guide:** You have a good track record here. "
                "You can express moderate confidence in well-established findings, "
                "but still verify novel claims."
            )
        elif domain_model.confidence_level == "moderate":
            lines.append(
                "**Confidence Guide:** Mixed track record. "
                "Use hedged language: 'my analysis suggests', 'preliminary finding'. "
                "Verify claims before presenting as fact."
            )
        elif domain_model.confidence_level == "unreliable":
            lines.append(
                "**Confidence Guide:** ⚠️ **POOR TRACK RECORD**. "
                "Express HIGH uncertainty. Use phrases like: "
                "'needs verification', 'preliminary', 'uncertain'. "
                "Prefer conservative perspectives. Flag all claims as needing verification."
            )
        else:
            lines.append(
                "**Confidence Guide:** No data yet. "
                "Express uncertainty explicitly. Don't claim certainty without evidence."
            )

        return "\n".join(lines)

    def _capability_success(self, kwargs: dict) -> str:
        """Check success rate on a specific capability."""
        capability = kwargs.get("capability", "")

        if not capability:
            # List all capabilities
            caps = self.self_model.get_all_capabilities()
            lines = ["**Your Capabilities:**", ""]
            for cap in caps[:10]:
                lines.append(f"- {cap}")
            lines.append("")
            lines.append("Use `capability_success` with specific capability name for details.")
            return "\n".join(lines)

        cap_model = self.self_model.get_capability_model(capability)

        if not cap_model:
            return (
                f"❓ **No data for capability: {capability}**\n\n"
                f"You haven't used this capability enough to establish reliability."
            )

        status_icon = {
            "high": "✅",
            "medium": "🔵",
            "low": "⚠️",
            "unknown": "❓",
        }.get(cap_model.reliability, "❓")

        return (
            f"{status_icon} **Capability: {capability}**\n\n"
            f"**Reliability:** {cap_model.reliability}\n"
            f"**Used:** {cap_model.use_count}x\n"
            f"**Success Rate:** {cap_model.success_rate:.0%}\n\n"
            f"**Notes:** {cap_model.notes or 'No qualitative notes yet.'}"
        )

    def _knowledge_gaps(self, kwargs: dict) -> str:
        """List current knowledge gaps."""
        domain = kwargs.get("domain")

        gaps = self.self_model.get_knowledge_gaps(domain=domain)

        if not gaps:
            return "✅ **No recorded knowledge gaps**\n\nYour self-model has no explicit gaps recorded yet."

        lines = [
            f"**Knowledge Gaps** ({len(gaps)} total)",
            "",
        ]

        for gap in gaps[:10]:  # Show top 10
            priority_icon = {
                "high": "🔴",
                "medium": "🟡",
                "low": "🟢",
            }.get("high" if gap.priority > 0.7 else "medium" if gap.priority > 0.4 else "low", "⚪")

            lines.append(
                f"{priority_icon} **{gap.topic}** ({gap.gap_type})\n"
                f"   {gap.description}\n"
            )

        if len(gaps) > 10:
            lines.append(f"... and {len(gaps) - 10} more gaps")

        lines.append("")
        lines.append(
            "Use these gaps to guide research priorities. "
            "High-priority gaps should be filled first."
        )

        return "\n".join(lines)

    def _full_status(self) -> str:
        """Get complete self-model status report."""
        return self.self_model.get_full_status()

    def _update_self_model(self, kwargs: dict) -> str:
        """Record new self-knowledge from interaction."""
        domain = kwargs.get("domain", "general")
        capability = kwargs.get("capability")
        quality = kwargs.get("quality", 0.5)
        claim = kwargs.get("claim", "")

        # Update domain model
        if domain:
            self.self_model.update_domain_reliability(
                domain=domain,
                quality=quality,
            )

        # Update capability model
        if capability:
            self.self_model.update_capability_success(
                capability=capability,
                success=quality > 0.6,
            )

        # Record claim if provided
        if claim:
            self.self_model.record_claim(
                claim=claim,
                domain=domain,
                verified=quality > 0.7,
            )

        return (
            f"✅ Self-model updated\n\n"
            f"**Domain:** {domain}\n"
            f"**Capability:** {capability or 'N/A'}\n"
            f"**Quality:** {quality:.2f}\n\n"
            f"Your self-model now reflects this interaction. "
            f"Future responses will be shaped by this updated self-knowledge."
        )
