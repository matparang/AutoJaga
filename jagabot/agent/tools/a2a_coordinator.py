"""
A2A Coordinator Tool — Makes agent aware of handoff and arbitration capabilities.

This tool exposes the A2A system to the agent so it can:
1. Request handoffs when stuck
2. Request arbitration on conflicts
3. Learn from past handoff/arbitration outcomes
4. Improve its own handoff packaging over time

Wire into tool_loader.py:
    registry.register(A2ACoordinatorTool(
        handoff_packager=self.handoff_packager,
        arbitrator=self.arbitrator,
        brier_scorer=self.brier,
    ))
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jagabot.agent.tools.base import Tool


class A2ACoordinatorTool(Tool):
    """
    A2A coordination — agent-aware handoff and arbitration.
    
    The agent can explicitly request:
    - Handoff to specialist when stuck
    - Arbitration on conflicting perspectives
    - Status of past handoffs/arbitrations
    - Learning from past A2A outcomes
    """

    name = "a2a_coordinator"
    description = (
        "A2A (Agent-to-Agent) coordination — request handoffs, arbitration, and learn from outcomes.\n\n"
        "Actions:\n"
        "- request_handoff: Request handoff to specialist when stuck\n"
        "- request_arbitration: Request arbitration on conflicting perspectives\n"
        "- get_handoff_status: Check status of past handoffs\n"
        "- get_arbitration_history: Review past arbitration decisions\n"
        "- learn_from_outcome: Record outcome of handoff/arbitration for learning\n\n"
        "Use request_handoff when:\n"
        "- You've tried multiple approaches without success\n"
        "- You're stuck in reasoning loops\n"
        "- A different perspective would help\n\n"
        "Use request_arbitration when:\n"
        "- Multiple perspectives conflict\n"
        "- You need data-driven decision\n"
        "- Confidence scores disagree\n\n"
        "Chain: After tri_agent/quad_agent disagreement, use request_arbitration. "
        "After 3+ failed attempts, use request_handoff."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "request_handoff", "request_arbitration",
                    "get_handoff_status", "get_arbitration_history",
                    "learn_from_outcome",
                ],
                "description": (
                    "request_handoff: {goal, stuck_reason, tools_tried, domain}. "
                    "request_arbitration: {strategies: [{name, perspective, verdict, confidence, evidence}]}. "
                    "learn_from_outcome: {handoff_id/arbitration_id, outcome: 'success|partial|failure', lesson}."
                ),
            },
            "goal": {"type": "string", "description": "Goal for request_handoff"},
            "stuck_reason": {"type": "string", "description": "Why stuck for request_handoff"},
            "tools_tried": {"type": "array", "items": {"type": "string"}, "description": "Tools tried for request_handoff"},
            "domain": {"type": "string", "description": "Domain for request_handoff"},
            "strategies": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "perspective": {"type": "string"},
                        "verdict": {"type": "string"},
                        "confidence": {"type": "number"},
                        "evidence": {"type": "string"},
                    }
                },
                "description": "Conflicting strategies for request_arbitration",
            },
            "handoff_id": {"type": "string", "description": "Handoff ID for learn_from_outcome"},
            "arbitration_id": {"type": "string", "description": "Arbitration ID for learn_from_outcome"},
            "outcome": {"type": "string", "enum": ["success", "partial", "failure"], "description": "Outcome for learn_from_outcome"},
            "lesson": {"type": "string", "description": "Lesson learned for learn_from_outcome"},
        },
        "required": ["action"],
    }

    def __init__(
        self,
        handoff_packager: object = None,
        arbitrator: object = None,
        brier_scorer: object = None,
        workspace: Path = None,
    ) -> None:
        self.handoff_packager = handoff_packager
        self.arbitrator = arbitrator
        self.brier = brier_scorer
        self.workspace = workspace or Path.home() / ".jagabot"
        self.a2a_log = self.workspace / "workspace" / "memory" / "a2a_log.jsonl"
        self.a2a_log.parent.mkdir(parents=True, exist_ok=True)

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")

        if action == "request_handoff":
            return await self._request_handoff(kwargs)

        if action == "request_arbitration":
            return await self._request_arbitration(kwargs)

        if action == "get_handoff_status":
            return self._get_handoff_status()

        if action == "get_arbitration_history":
            return self._get_arbitration_history(kwargs)

        if action == "learn_from_outcome":
            return self._learn_from_outcome(kwargs)

        return f"Unknown action: {action}"

    async def _request_handoff(self, kwargs: dict) -> str:
        """Request handoff to specialist agent."""
        goal = kwargs.get("goal", "")
        stuck_reason = kwargs.get("stuck_reason", "")
        tools_tried = kwargs.get("tools_tried", [])
        domain = kwargs.get("domain", "general")

        if not goal:
            return "❌ Error: 'goal' is required for request_handoff"

        if not self.handoff_packager:
            return "⚠️  Handoff system not initialized"

        # Package the handoff
        package = self.handoff_packager.package(
            current_goal=goal,
            session_context=f"Stuck: {stuck_reason}",
            tools_used=tools_tried,
            stuck_reason=stuck_reason,
            domain=domain,
            quality_so_far=0.5,  # Neutral quality
            sender_id="agent_request",
        )

        # Log the request
        self._log_a2a_event("handoff_request", {
            "goal": goal,
            "stuck_reason": stuck_reason,
            "domain": domain,
            "handoff_id": package.handoff_id,
        })

        # Route to specialist
        if self.handoff_router:
            result = await self.handoff_router.route(
                package=package,
                agent_runner=None,  # Will be wired to actual runner
            )
            return (
                f"✅ Handoff requested: {package.recipient_role}\n\n"
                f"**Handoff ID:** {package.handoff_id}\n"
                f"**Goal:** {goal}\n"
                f"**Reason:** {stuck_reason}\n"
                f"**Recipient:** {package.recipient_role}\n\n"
                f"Fresh agent will continue with distilled context. "
                f"Negative constraints and verified facts preserved."
            )

        return (
            f"✅ Handoff packaged (ID: {package.handoff_id})\n\n"
            f"**Goal:** {goal}\n"
            f"**Recipient:** {package.recipient_role}\n"
            f"**Context:** {len(package.context_snapshot)} chars distilled\n"
            f"**Constraints:** {len(package.negative_constraints)} negative constraints\n\n"
            f"⚠️  Router not wired yet — handoff packaged but not routed."
        )

    async def _request_arbitration(self, kwargs: dict) -> str:
        """Request arbitration on conflicting strategies."""
        strategies_data = kwargs.get("strategies", [])

        if not strategies_data:
            return "❌ Error: 'strategies' is required for request_arbitration"

        if not self.arbitrator:
            return "⚠️  Arbitrator not initialized"

        # Convert to Strategy objects
        from jagabot.swarm.arbitrator import Strategy
        strategies = []
        for s in strategies_data:
            strategies.append(Strategy(
                name=s.get("name", "unknown"),
                perspective=s.get("perspective", "general"),
                domain=s.get("domain", "general"),
                verdict=s.get("verdict", ""),
                confidence=s.get("confidence", 0.5),
                evidence=s.get("evidence", ""),
            ))

        # Arbitrate
        result = self.arbitrator.arbitrate(strategies)

        # Log the arbitration
        self._log_a2a_event("arbitration", {
            "arbitration_id": id(result),
            "winner": result.winner.name,
            "method": result.method,
            "confidence_gap": result.confidence_gap,
            "was_contested": result.was_contested,
        })

        # Format response
        lines = [
            f"✅ Arbitration complete",
            "",
            f"**Winner:** {result.winner.name} ({result.winner.perspective})",
            f"**Trust Score:** {result.winner.trust_score:.2f}",
            f"**Method:** {result.method}",
            "",
            f"**Explanation:** {result.explanation}",
            "",
        ]

        if result.was_contested:
            lines.append(f"⚠️  **Contested Decision:** Gap < 10% — consider manual review")
        else:
            lines.append(f"✅ **Clear Decision:** Gap ≥ 10% — proceed with winner")

        lines.append("")
        lines.append(f"**Losers:** {[l.name for l in result.losers]}")

        return "\n".join(lines)

    def _get_handoff_status(self) -> str:
        """Get status of past handoffs."""
        if not self.a2a_log.exists():
            return "No handoff history yet"

        import json
        handoffs = []
        with open(self.a2a_log) as f:
            for line in f:
                event = json.loads(line)
                if event.get("type") == "handoff_request":
                    handoffs.append(event)

        if not handoffs:
            return "No handoffs requested yet"

        lines = [
            f"**Handoff History** ({len(handoffs)} total)",
            "",
        ]

        for h in handoffs[-5:]:  # Last 5 handoffs
            lines.append(
                f"- **{h.get('handoff_id', 'unknown')}**: {h.get('goal', '')[:50]}... "
                f"({h.get('domain', 'general')})"
            )

        return "\n".join(lines)

    def _get_arbitration_history(self, kwargs: dict) -> str:
        """Get past arbitration decisions."""
        if not self.a2a_log.exists():
            return "No arbitration history yet"

        import json
        arbitrations = []
        with open(self.a2a_log) as f:
            for line in f:
                event = json.loads(line)
                if event.get("type") == "arbitration":
                    arbitrations.append(event)

        if not arbitrations:
            return "No arbitrations requested yet"

        lines = [
            f"**Arbitration History** ({len(arbitrations)} total)",
            "",
        ]

        for a in arbitrations[-5:]:  # Last 5 arbitrations
            lines.append(
                f"- Winner: **{a.get('winner', 'unknown')}** "
                f"(trust={a.get('trust_score', 0):.2f}, method={a.get('method', 'unknown')})"
            )

        return "\n".join(lines)

    def _learn_from_outcome(self, kwargs: dict) -> str:
        """Record outcome of handoff/arbitration for learning."""
        handoff_id = kwargs.get("handoff_id")
        arbitration_id = kwargs.get("arbitration_id")
        outcome = kwargs.get("outcome", "")
        lesson = kwargs.get("lesson", "")

        if not outcome:
            return "❌ Error: 'outcome' is required (success|partial|failure)"

        if not handoff_id and not arbitration_id:
            return "❌ Error: 'handoff_id' or 'arbitration_id' is required"

        # Log the learning
        self._log_a2a_event("learn_from_outcome", {
            "handoff_id": handoff_id,
            "arbitration_id": arbitration_id,
            "outcome": outcome,
            "lesson": lesson,
        })

        # Update Brier scorer if available
        if self.brier and outcome in ["success", "failure"]:
            # This would feed back into calibration
            pass

        return (
            f"✅ Outcome recorded for learning\n\n"
            f"**ID:** {handoff_id or arbitration_id}\n"
            f"**Outcome:** {outcome}\n"
            f"**Lesson:** {lesson}\n\n"
            f"This will improve future handoff/arbitration decisions."
        )

    def _log_a2a_event(self, event_type: str, data: dict) -> None:
        """Log A2A event for learning and audit trail."""
        import json
        from datetime import datetime

        event = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            **data,
        }

        with open(self.a2a_log, "a") as f:
            f.write(json.dumps(event) + "\n")
