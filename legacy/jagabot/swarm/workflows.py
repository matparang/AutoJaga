"""Predefined swarm workflows — ready-to-use scheduled analysis patterns."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WorkflowPreset:
    """A predefined workflow template."""
    name: str
    query: str
    cron_expr: str
    description: str


PRESETS: dict[str, WorkflowPreset] = {
    "market_monitor": WorkflowPreset(
        name="Market Monitor",
        query="Analyze current market conditions: oil prices, VIX levels, key risk indicators",
        cron_expr="0 */4 * * *",  # every 4 hours
        description="Scan market conditions every 4 hours",
    ),
    "daily_risk": WorkflowPreset(
        name="Daily Risk Report",
        query="Run full risk analysis: VaR, CVaR, stress test, early warning signals for portfolio",
        cron_expr="0 8 * * *",  # daily at 8am
        description="Comprehensive daily risk assessment at 8am",
    ),
    "fund_review": WorkflowPreset(
        name="Weekly Fund Review",
        query="Review fund manager performance: accountability check, red flags, decision analysis",
        cron_expr="0 9 * * 1",  # Monday 9am
        description="Weekly fund manager accountability review",
    ),
    "nightly_self_review": WorkflowPreset(
        name="Nightly Self-Review",
        query="Self-improvement review: analyze recent predictions, check accuracy, suggest improvements",
        cron_expr="0 23 * * *",  # daily at 11pm
        description="Nightly self-assessment and improvement analysis",
    ),
}


def get_preset(name: str) -> WorkflowPreset | None:
    """Get a workflow preset by name."""
    return PRESETS.get(name)


def list_presets() -> list[WorkflowPreset]:
    """Return all available presets."""
    return list(PRESETS.values())
