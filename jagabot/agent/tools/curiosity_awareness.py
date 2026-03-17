"""
Curiosity Awareness Tool — Makes agent explicitly aware of curiosity opportunities.

This tool exposes the CuriosityEngine to the agent so it can:
1. Query curiosity suggestions for current session
2. See knowledge gaps ranked by curiosity score
3. Check bridge opportunities (cross-domain connections)
4. Review pending outcomes that are overdue
5. Track which curiosity-driven explorations paid off

Wire into loop.py __init__:
    registry.register(CuriosityAwarenessTool(
        curiosity_engine=self.curiosity,
    ))
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jagabot.agent.tools.base import Tool


class CuriosityAwarenessTool(Tool):
    """
    Curiosity awareness — explicit curiosity opportunities for the agent.
    
    The agent can explicitly query:
    - session_suggestions: What gaps are relevant to current session?
    - knowledge_gaps: List all knowledge gaps ranked by curiosity score
    - bridge_opportunities: Cross-domain connection opportunities
    - pending_outcomes: Overdue outcomes awaiting verification
    - exploration_history: Which curiosity explorations paid off?
    """

    name = "curiosity_awareness"
    description = (
        "Curiosity awareness — query knowledge gaps, bridge opportunities, and research suggestions.\n\n"
        "Actions:\n"
        "- session_suggestions: Get curiosity suggestions for current session\n"
        "- knowledge_gaps: List all knowledge gaps ranked by curiosity score\n"
        "- bridge_opportunities: Cross-domain connection opportunities\n"
        "- pending_outcomes: Overdue outcomes awaiting verification\n"
        "- exploration_history: Review which curiosity explorations paid off\n\n"
        "Use session_suggestions at session start to identify research opportunities.\n"
        "Use bridge_opportunities when user asks about cross-domain topics.\n"
        "Use pending_outcomes to identify verification priorities.\n\n"
        "Chain: At session start, check session_suggestions. If high-curiosity gap found, "
        "proactively mention to user."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "session_suggestions", "knowledge_gaps",
                    "bridge_opportunities", "pending_outcomes",
                    "exploration_history",
                ],
                "description": (
                    "session_suggestions: {current_query?, session_key?}. "
                    "knowledge_gaps: {domain?, limit?}. "
                    "bridge_opportunities: {domain1?, domain2?}. "
                    "pending_outcomes: {overdue_days?}. "
                    "exploration_history: {limit?}."
                ),
            },
            "current_query": {"type": "string", "description": "Current query for session_suggestions"},
            "session_key": {"type": "string", "description": "Session key for session_suggestions"},
            "domain": {"type": "string", "description": "Domain filter for knowledge_gaps"},
            "limit": {"type": "integer", "description": "Result limit"},
            "domain1": {"type": "string", "description": "First domain for bridge_opportunities"},
            "domain2": {"type": "string", "description": "Second domain for bridge_opportunities"},
            "overdue_days": {"type": "integer", "description": "Days overdue for pending_outcomes"},
        },
        "required": ["action"],
    }

    def __init__(
        self,
        curiosity_engine: object = None,
        workspace: Path = None,
    ) -> None:
        self.curiosity = curiosity_engine
        self.workspace = workspace or Path.home() / ".jagabot"

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")

        if not self.curiosity:
            return "⚠️  CuriosityEngine not initialized"

        if action == "session_suggestions":
            return self._session_suggestions(kwargs)

        if action == "knowledge_gaps":
            return self._knowledge_gaps(kwargs)

        if action == "bridge_opportunities":
            return self._bridge_opportunities(kwargs)

        if action == "pending_outcomes":
            return self._pending_outcomes(kwargs)

        if action == "exploration_history":
            return self._exploration_history(kwargs)

        return f"Unknown action: {action}"

    def _session_suggestions(self, kwargs: dict) -> str:
        """Get curiosity suggestions for current session."""
        current_query = kwargs.get("current_query", "")
        session_key = kwargs.get("session_key", "")

        suggestions = self.curiosity.get_session_suggestions(
            current_query=current_query,
            session_key=session_key,
        )

        if not suggestions.has_suggestions:
            return (
                "✅ **No high-curiosity opportunities for this session**\n\n"
                "Your knowledge gaps are either:\n"
                "- Already being explored\n"
                "- Low priority for current topic\n"
                "- Not yet identified\n\n"
                "Continue with current research direction."
            )

        lines = [
            f"💡 **Curiosity Opportunities** ({len(suggestions.targets)} found)",
            "",
        ]

        for i, target in enumerate(suggestions.targets[:5], 1):
            lines.append(
                f"**{i}. {target.topic}** (score: {target.curiosity_score:.2f})\n"
                f"   **Gap:** {target.gap_description[:100]}\n"
                f"   **Suggested:** {target.suggested_action[:100]}\n"
            )
            if target.bridge_insight:
                lines.append(f"   **Bridge:** {target.bridge_insight}")

        if suggestions.exploration_rate > 0.5:
            lines.append("")
            lines.append(
                f"**Note:** You've explored {suggestions.exploration_rate:.0%} of identified gaps. "
                f"Consider deepening existing research before expanding."
            )

        return "\n".join(lines)

    def _knowledge_gaps(self, kwargs: dict) -> str:
        """List all knowledge gaps ranked by curiosity score."""
        domain = kwargs.get("domain")
        limit = kwargs.get("limit", 10)

        gaps = self.curiosity.get_knowledge_gaps(domain=domain, limit=limit)

        if not gaps:
            return "✅ **No recorded knowledge gaps**\n\nYour self-model has no explicit gaps recorded yet."

        lines = [
            f"**Knowledge Gaps** ({len(gaps)} total)",
            "",
        ]

        for gap in gaps:
            priority_icon = {
                "high": "🔴",
                "medium": "🟡",
                "low": "🟢",
            }.get("high" if gap.curiosity_score > 0.7 else "medium" if gap.curiosity_score > 0.4 else "low", "⚪")

            lines.append(
                f"{priority_icon} **{gap.topic}** (score: {gap.curiosity_score:.2f})\n"
                f"   {gap.gap_description}\n"
                f"   **Type:** {gap.gap_type}\n"
                f"   **Suggested:** {gap.suggested_action[:80]}\n"
            )

        return "\n".join(lines)

    def _bridge_opportunities(self, kwargs: dict) -> str:
        """List cross-domain connection opportunities."""
        domain1 = kwargs.get("domain1")
        domain2 = kwargs.get("domain2")

        bridges = self.curiosity.get_bridge_opportunities(domain1=domain1, domain2=domain2)

        if not bridges:
            return (
                "✅ **No bridge opportunities found**\n\n"
                "Either:\n"
                "- Both domains are already well-explored\n"
                "- No cross-domain connections identified yet\n"
                "- Domains are too unrelated for meaningful bridges"
            )

        lines = [
            f"🌉 **Bridge Opportunities** ({len(bridges)} found)",
            "",
        ]

        for bridge in bridges:
            lines.append(
                f"**{bridge.domain1} ↔ {bridge.domain2}**\n"
                f"   **Insight:** {bridge.insight}\n"
                f"   **Curiosity Score:** {bridge.curiosity_score:.2f}\n"
                f"   **Suggested:** Research {bridge.suggested_topic} to connect these domains\n"
            )

        return "\n".join(lines)

    def _pending_outcomes(self, kwargs: dict) -> str:
        """List overdue outcomes awaiting verification."""
        overdue_days = kwargs.get("overdue_days", 3)

        pending = self.curiosity.get_pending_outcomes(overdue_days=overdue_days)

        if not pending:
            return f"✅ **No pending outcomes overdue by {overdue_days}+ days**\n\nAll outcomes are being tracked appropriately."

        lines = [
            f"⏳ **Pending Outcomes** ({len(pending)} overdue by {overdue_days}+ days)",
            "",
        ]

        for p in pending:
            lines.append(
                f"**{p.conclusion[:80]}...**\n"
                f"   **Days Pending:** {p.days_pending}\n"
                f"   **Domain:** {p.domain}\n"
                f"   **Priority:** {'🔴 High' if p.days_pending > 7 else '🟡 Medium'}\n"
            )

        lines.append("")
        lines.append(
            "Use `outcome_tracker.record_outcome()` to verify these conclusions. "
            "Overdue outcomes block curiosity engine from identifying related gaps."
        )

        return "\n".join(lines)

    def _exploration_history(self, kwargs: dict) -> str:
        """Review which curiosity explorations paid off."""
        limit = kwargs.get("limit", 10)

        history = self.curiosity.get_exploration_history(limit=limit)

        if not history:
            return "✅ **No curiosity-driven explorations recorded yet**\n\nStart exploring gaps to build history."

        lines = [
            f"**Exploration History** ({len(history)} explorations)",
            "",
        ]

        for entry in history:
            outcome_icon = {
                "success": "✅",
                "partial": "🔵",
                "failure": "❌",
            }.get(entry.outcome, "⚪")

            lines.append(
                f"{outcome_icon} **{entry.topic}** ({entry.date[:10]})\n"
                f"   **Curiosity Score:** {entry.curiosity_score:.2f}\n"
                f"   **Outcome:** {entry.outcome}\n"
                f"   **Quality:** {entry.quality:.2f}\n"
                f"   **Findings:** {entry.findings_count}\n"
            )

        # Calculate success rate
        successes = sum(1 for e in history if e.outcome == "success")
        success_rate = successes / len(history) if history else 0

        lines.append("")
        lines.append(
            f"**Success Rate:** {success_rate:.0%} ({successes}/{len(history)})\n"
            f"Higher success rate = better curiosity calibration"
        )

        return "\n".join(lines)
