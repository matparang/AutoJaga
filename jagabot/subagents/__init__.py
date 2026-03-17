"""Jagabot subagents — 4-stage stateless pipeline for complex analysis.

Stages:
  1. WebSearch  — fetch live market data (prices, VIX, USD)
  2. Tools      — run financial calculations (MC, CV, VaR, CVaR)
  3. Models     — build integrated models via K1 Bayesian
  4. Reasoning  — apply K3 perspectives + K7 evaluation → final verdict

Usage:
  from jagabot.subagents import SubagentManager
  mgr = SubagentManager()
  result = await mgr.execute_workflow("Oil crisis analysis", {"assets": ["WTI"]})
"""

from jagabot.subagents.base import BaseSubagent
from jagabot.subagents.manager import SubagentManager
from jagabot.subagents.stages import (
    WebSearchStage,
    ToolsStage,
    ModelsStage,
    ReasoningStage,
)

__all__ = [
    "BaseSubagent",
    "SubagentManager",
    "WebSearchStage",
    "ToolsStage",
    "ModelsStage",
    "ReasoningStage",
]
