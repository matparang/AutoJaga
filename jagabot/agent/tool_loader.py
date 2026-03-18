"""Tool registration loader — extracted from AgentLoop._register_default_tools.

Centralises the list of default tools so loop.py stays focused on
message processing and memory management.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jagabot.agent.tools.registry import ToolRegistry
    from jagabot.bus.queue import MessageBus
    from jagabot.agent.subagent import SubagentManager
    from jagabot.config.schema import ExecToolConfig
    from jagabot.cron.service import CronService
    from jagabot.providers.base import LLMProvider


def register_default_tools(
    registry: ToolRegistry,
    *,
    workspace: Path,
    restrict_to_workspace: bool,
    exec_config: "ExecToolConfig",
    brave_api_key: str | None,
    bus: "MessageBus",
    subagents: "SubagentManager",
    cron_service: "CronService | None",
    provider: "LLMProvider | None" = None,
    model: str | None = None,
) -> None:
    """Populate *registry* with the full default tool set."""

    from jagabot.agent.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
    from jagabot.agent.tools.shell import ExecTool
    from jagabot.agent.tools.web import WebSearchTool, WebFetchTool
    from jagabot.agent.tools.message import MessageTool
    from jagabot.agent.tools.spawn import SpawnTool
    from jagabot.agent.tools.cron import CronTool
    from jagabot.agent.tools.financial_cv import FinancialCVTool
    from jagabot.agent.tools.monte_carlo import MonteCarloTool
    from jagabot.agent.tools.dynamics import DynamicsTool
    from jagabot.agent.tools.statistical import StatisticalTool
    from jagabot.agent.tools.early_warning import EarlyWarningTool
    from jagabot.agent.tools.bayesian import BayesianTool
    from jagabot.agent.tools.counterfactual import CounterfactualTool
    from jagabot.agent.tools.sensitivity import SensitivityTool
    from jagabot.agent.tools.pareto import ParetoTool
    from jagabot.agent.tools.visualization import VisualizationTool
    from jagabot.agent.tools.var import VaRTool
    from jagabot.agent.tools.cvar import CVaRTool
    from jagabot.agent.tools.stress_test import StressTestTool
    from jagabot.agent.tools.correlation import CorrelationTool
    from jagabot.agent.tools.recovery_time import RecoveryTimeTool
    from jagabot.agent.tools.decision import DecisionTool
    from jagabot.agent.tools.education import EducationTool
    from jagabot.agent.tools.accountability import AccountabilityTool
    from jagabot.agent.tools.researcher import ResearcherTool
    from jagabot.agent.tools.copywriter import CopywriterTool
    from jagabot.agent.tools.self_improver import SelfImproverTool
    from jagabot.agent.tools.portfolio_analyzer import PortfolioAnalyzerTool
    from jagabot.agent.tools.memory_fleet import MemoryFleetTool
    from jagabot.agent.tools.knowledge_graph import KnowledgeGraphTool
    from jagabot.agent.tools.evaluation import EvaluationTool
    from jagabot.agent.tools.k1_bayesian import K1BayesianTool
    from jagabot.agent.tools.k3_perspective import K3PerspectiveTool
    from jagabot.agent.tools.meta_learning import MetaLearningTool
    from jagabot.agent.tools.subagent import SubagentTool
    from jagabot.agent.tools.evolution import EvolutionTool
    from jagabot.agent.tools.skill_trigger import SkillTriggerTool
    from jagabot.agent.tools.review import ReviewTool
    from jagabot.agent.tools.deepseek import DeepSeekTool
    from jagabot.agent.tools.codeact import CodeActTool
    from jagabot.agent.tools.flow import FlowTool
    from jagabot.agent.tools.debate import DebateTool
    from jagabot.agent.tools.tri_agent import TriAgentTool
    from jagabot.agent.tools.quad_agent import QuadAgentTool
    from jagabot.agent.tools.yolo_mode import YoloModeTool
    from jagabot.agent.tools.offline_swarm import OfflineSwarmTool
    from jagabot.skills.research import ResearchSkill

    allowed_dir = workspace if restrict_to_workspace else None

    # File tools
    registry.register(ReadFileTool(allowed_dir=allowed_dir))
    registry.register(WriteFileTool(allowed_dir=allowed_dir))
    registry.register(EditFileTool(allowed_dir=allowed_dir))
    registry.register(ListDirTool(allowed_dir=allowed_dir))

    # Shell tool (with resource guard)
    from jagabot.core.resource_guard import ResourceGuard
    _resource_guard = ResourceGuard(max_memory_mb=256, max_cpu_seconds=exec_config.timeout)
    registry.register(ExecTool(
        working_dir=str(workspace),
        timeout=exec_config.timeout,
        restrict_to_workspace=restrict_to_workspace,
        resource_guard=_resource_guard,
    ))

    # Web tools
    registry.register(WebSearchTool(api_key=brave_api_key))
    registry.register(WebFetchTool())

    # Message tool
    registry.register(MessageTool(send_callback=bus.publish_outbound))

    # Spawn tool (subagents)
    registry.register(SpawnTool(manager=subagents))
    
    # Register spawn_subagent alias — DeepSeek sometimes calls spawn_subagent instead of spawn
    from jagabot.agent.tools.spawn import SpawnTool as _SpawnTool
    class _SpawnAlias(_SpawnTool):
        @property
        def name(self) -> str:
            return "spawn_subagent"
    registry.register(_SpawnAlias(manager=subagents))

    # Cron tool (scheduling)
    if cron_service:
        registry.register(CronTool(cron_service))

    # Financial analysis tools
    registry.register(FinancialCVTool())
    registry.register(MonteCarloTool())
    registry.register(DynamicsTool())
    registry.register(StatisticalTool())
    registry.register(EarlyWarningTool())
    registry.register(BayesianTool())
    registry.register(CounterfactualTool())
    registry.register(SensitivityTool())
    registry.register(ParetoTool())
    registry.register(VisualizationTool())

    # FRM tools (v2.0)
    registry.register(VaRTool())
    registry.register(CVaRTool())
    registry.register(StressTestTool())
    registry.register(CorrelationTool())
    registry.register(RecoveryTimeTool())

    # Decision engine (v2.0)
    registry.register(DecisionTool())

    # Education & Accountability (v2.0)
    registry.register(EducationTool())
    registry.register(AccountabilityTool())

    # v2.1 workers
    registry.register(ResearcherTool())
    registry.register(CopywriterTool())
    registry.register(SelfImproverTool())

    # v2.4 — Deterministic portfolio analyzer
    registry.register(PortfolioAnalyzerTool())

    # v3.0 Phase 1 — Engine extraction tools
    registry.register(MemoryFleetTool())
    registry.register(KnowledgeGraphTool())
    registry.register(EvaluationTool())

    # v3.0 Phase 2 — Reasoning kernels
    registry.register(K1BayesianTool())
    registry.register(K3PerspectiveTool())

    # v3.0 Phase 3 — MetaLearning engine
    registry.register(MetaLearningTool())

    # v3.0 Phase 4A — Subagent pipeline
    registry.register(SubagentTool())

    # v3.0 Phase 4B — Evolution engine
    registry.register(EvolutionTool())

    # v3.2 Phase 5 — Skill trigger + review
    registry.register(SkillTriggerTool())
    registry.register(ReviewTool())

    # v3.9.0 — DeepSeek MCP integration
    registry.register(DeepSeekTool(
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
    ))

    # v3.10.0 — QuantaLogic CodeAct + Flow
    registry.register(CodeActTool())
    registry.register(FlowTool())

    # Persona debate tool (autoresearch integration)
    registry.register(DebateTool())

    # v4.0 — Tri-Agent verification loop
    if provider is not None:
        registry.register(TriAgentTool(
            provider=provider,
            workspace=workspace,
            model=model,
            restrict_to_workspace=restrict_to_workspace,
        ))

    # v4.1 — Quad-Agent isolated swarm
    if provider is not None:
        registry.register(QuadAgentTool(
            provider=provider,
            workspace=workspace,
            model=model,
            restrict_to_workspace=restrict_to_workspace,
        ))

    # v4.2 — Level-4 Offline Swarm tool
    registry.register(OfflineSwarmTool(workspace=workspace))

    # v4.2.1 — YOLO mode autonomous research tool
    registry.register(YoloModeTool())

    # v4.2.2 — A2A Coordinator (agent-aware handoff + arbitration)
    from jagabot.agent.tools.a2a_coordinator import A2ACoordinatorTool
    registry.register(A2ACoordinatorTool())

    # v4.2.3 — Self-Model Awareness will be registered in loop.py
    # v4.2.4 — Curiosity Awareness will be registered in loop.py
    # v4.2.5 — Confidence Awareness will be registered in loop.py
    # (all need engine references which are created in loop.py __init__)

    # v4.3 — Research Skill (AutoJaga)
    registry.register(ResearchSkill())
