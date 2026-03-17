"""Jagabot — The Guardian. Main orchestrator with 4-subagent sequential pipeline.

v2.2: Wrapped in ResilientPipeline — per-stage retry + partial fallback.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from jagabot.agent.memory import MemoryStore
from jagabot.agent.tools.registry import ToolRegistry
from jagabot.guardian.tools import register_jagabot_tools
from jagabot.guardian.subagents.websearch import websearch_agent
from jagabot.guardian.subagents.support import support_agent
from jagabot.guardian.subagents.billing import billing_agent
from jagabot.guardian.subagents.supervisor import supervisor_agent
from jagabot.guardian.subagents.resilience import (
    ResilientPipeline,
    StageSpec,
)

logger = logging.getLogger(__name__)


class Jagabot:
    """The Guardian — orchestrates a 4-subagent sequential pipeline.

    ONLY orchestrates and stores results in memory.
    NEVER calculates, NEVER structures, NEVER searches directly.

    Pipeline (v2.2 — resilient):
        1. WebSearch → fetches market data/news
        2. Support   → structures data + detects patterns (CV, EarlyWarning)
        3. Billing   → calculates probabilities + equity + margin (Monte Carlo, Stats)
        4. Supervisor→ compiles final report (Bayesian, Sensitivity, Pareto)

    Each stage retries up to 2× on failure and passes degraded fallback
    data downstream if all retries exhaust.
    """

    def __init__(
        self,
        workspace: Path | str,
        brave_api_key: str | None = None,
        registry: ToolRegistry | None = None,
    ):
        self.workspace = Path(workspace)
        self.memory = MemoryStore(self.workspace)
        self.brave_api_key = brave_api_key

        # Register all tools into registry
        self.tools = registry or ToolRegistry()
        register_jagabot_tools(self.tools)

    async def handle_query(
        self,
        user_query: str,
        portfolio: dict[str, Any],
        market_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Run the full 4-step sequential pipeline with resilience.

        Args:
            user_query: The user's question or analysis request.
            portfolio: Portfolio data (capital, positions, cash, etc.).
            market_data: Market data (current prices, historical changes, etc.).

        Returns:
            Dict with 'report' (narrative string) and all intermediate results.
        """
        session_id = f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Build the resilient pipeline with per-stage retry
        pipeline = ResilientPipeline([
            StageSpec(
                name="web",
                fn=lambda ctx: websearch_agent(
                    query=ctx["query"],
                    brave_api_key=ctx.get("brave_api_key"),
                ),
                max_retries=2,
                fallback={"news": [], "timestamp": "", "query": user_query,
                          "raw_results": [], "result_count": 0},
            ),
            StageSpec(
                name="support",
                fn=lambda ctx: support_agent(
                    market_data=ctx["market_data"],
                    web_results=ctx.get("web", {}),
                ),
                max_retries=2,
                fallback={"structured_data": {}, "cv_analysis": {},
                          "warnings": [], "risk_classification": "unknown",
                          "web_context": {}},
            ),
            StageSpec(
                name="billing",
                fn=lambda ctx: billing_agent(
                    portfolio=ctx["portfolio"],
                    market_data=ctx["market_data"],
                    support_results=ctx.get("support"),
                ),
                max_retries=2,
                fallback={"probability": 0.5, "equity": 0,
                          "margin_call": {"active": False},
                          "confidence_interval": {}, "derived_volatility": 0},
            ),
            StageSpec(
                name="supervisor",
                fn=lambda ctx: supervisor_agent(
                    web_results=ctx.get("web", {}),
                    support_results=ctx.get("support", {}),
                    billing_results=ctx.get("billing", {}),
                ),
                max_retries=2,
                fallback={"report": "Analysis unavailable due to pipeline errors.",
                          "bayesian_analysis": {}, "strategies": {},
                          "risk_level": "unknown", "margin_call_active": False},
            ),
        ])

        initial = {
            "query": user_query,
            "brave_api_key": self.brave_api_key,
            "portfolio": portfolio,
            "market_data": market_data,
        }

        pr = await pipeline.run(initial)

        # Assemble results
        results: dict[str, Any] = {
            "session_id": session_id,
            "query": user_query,
            "degraded": pr.degraded,
        }
        for stage in pr.stages:
            results[stage.name] = stage.data if stage.success else (
                pipeline.stages[[s.name for s in pipeline.stages].index(stage.name)].fallback
                or {"_degraded": True}
            )

        results["report"] = results.get("supervisor", {}).get("report", "")

        if pr.degraded:
            failed = [s.name for s in pr.stages if not s.success]
            logger.warning("Degraded pipeline — failed stages: %s", failed)
            results["report"] += (
                f"\n\n⚠️ Note: stages {failed} experienced errors. "
                "Results may be incomplete."
            )

        self._store_results(session_id, results)
        return results

    def _store_results(self, session_id: str, results: dict[str, Any]) -> None:
        """Persist pipeline results to memory."""
        # Append to history log
        report = results.get("report", "")
        risk_level = results.get("supervisor", {}).get("risk_level", "unknown")
        query = results.get("query", "")

        history_entry = (
            f"## [{session_id}] {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"Query: {query}\n"
            f"Risk Level: {risk_level}\n"
            f"Report summary: {report[:200]}...\n"
        )
        self.memory.append_history(history_entry)

        # Update long-term memory with latest analysis state
        existing = self.memory.read_long_term()
        update = (
            f"\n\n## Latest Jagabot Analysis ({session_id})\n"
            f"- Query: {query}\n"
            f"- Risk Level: {risk_level}\n"
            f"- Margin Call: {'ACTIVE' if results.get('billing', {}).get('margin_call', {}).get('active') else 'CLEAR'}\n"
            f"- Recommended Strategy: {results.get('supervisor', {}).get('strategies', {}).get('best', {}).get('name', 'N/A')}\n"
        )
        self.memory.write_long_term(existing + update)

    def get_registered_tools(self) -> list[str]:
        """Return list of registered tool names."""
        return self.tools.tool_names
