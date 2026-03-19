"""Agent loop: the core processing engine."""

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from loguru import logger

from jagabot.bus.events import InboundMessage, OutboundMessage
from jagabot.bus.queue import MessageBus
from jagabot.providers.base import LLMProvider
from jagabot.agent.context import ContextBuilder
from jagabot.agent.tools.registry import ToolRegistry
from jagabot.agent.tools.message import MessageTool
from jagabot.agent.tools.spawn import SpawnTool
from jagabot.agent.tools.cron import CronTool
from jagabot.agent.memory import MemoryStore
from jagabot.agent.subagent import SubagentManager
from jagabot.session.manager import SessionManager
from jagabot.core.tool_harness import ToolHarness
from jagabot.core.auditor import ResponseAuditor
from jagabot.core.tool_filter import get_tools_for_query
from jagabot.core.fluid_dispatcher import FluidDispatcher
from jagabot.core.model_switchboard import ModelSwitchboard
from jagabot.core.repetition_guard import RepetitionGuard
from jagabot.core.trajectory_monitor import TrajectoryMonitor


def _normalize_json_escapes(json_str: str) -> str:
    """
    Normalize common JSON escape issues from LLM output.
    
    LLMs often output \\n (double-escaped) when they mean \n in JSON strings.
    This function fixes common escape sequence issues before JSON parsing.
    """
    # Replace double-escaped newlines with single-escaped newlines
    # This handles cases where LLM outputs "\\n" instead of "\n" in JSON strings
    json_str = json_str.replace('\\\\n', '\\n')
    json_str = json_str.replace('\\\\t', '\\t')
    json_str = json_str.replace('\\\\r', '\\r')
    json_str = json_str.replace('\\\\\"', '\\"')
    json_str = json_str.replace('\\\\\\\\', '\\\\')
    return json_str


class AgentLoop:
    """
    The agent loop is the core processing engine.
    
    It:
    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """
    
    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        max_iterations: int = 30,
        temperature: float = 0.7,
        memory_window: int = 50,
        brave_api_key: str | None = None,
        exec_config: "ExecToolConfig | None" = None,
        cron_service: "CronService | None" = None,
        restrict_to_workspace: bool = False,
        session_manager: SessionManager | None = None,
    ):
        from jagabot.config.schema import ExecToolConfig
        from jagabot.cron.service import CronService
        self.bus = bus
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.temperature = temperature
        self.memory_window = memory_window
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace
        
        self.context = ContextBuilder(workspace)
        self.sessions = session_manager or SessionManager(workspace)
        self.tools = ToolRegistry()
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            brave_api_key=brave_api_key,
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
        )
        
        self._running = False
        self.harness = ToolHarness(workspace)
        self.rep_guard = RepetitionGuard()
        self.trajectory_monitor = TrajectoryMonitor()
        
        # Session checkpointing (prevents memory loss on crash)
        from jagabot.core.session_checkpoint import load_latest_checkpoint
        self._checkpoint_dir = workspace / "checkpoints"
        self._last_checkpoint_turn = 0
        
        # Try to load existing checkpoint
        checkpoint = load_latest_checkpoint(workspace)
        if checkpoint:
            logger.info(f"Found checkpoint from turn {checkpoint['turn']} - use /resume to restore")
        
        # ParallelRunner — real multi-agent execution
        try:
            from jagabot.swarm.parallel_runner import ParallelRunner
            self.parallel_runner = ParallelRunner(
                provider=provider,
                workspace=workspace,
                brier_scorer=None,  # wired after brier init below
            )
            logger.info("ParallelRunner initialized")
        except Exception as _pr_err:
            logger.warning(f"ParallelRunner init failed: {_pr_err}")
            self.parallel_runner = None

        # BDI Scorecard tracker
        try:
            from jagabot.core.bdi_scorecard import BDIScorecardTracker
            self.bdi_tracker = BDIScorecardTracker(workspace)
            logger.info("BDI Scorecard initialized")
        except Exception as _bdi_err:
            logger.warning(f"BDI Scorecard init failed: {_bdi_err}")
            self.bdi_tracker = None

        # BeliefEngine — calibrated belief states downstream of BrierScorer
        try:
            from jagabot.core.belief_engine import BeliefEngine
            self.belief_engine = BeliefEngine(
                workspace=workspace,
                brier_scorer=None,  # wired after brier init
            )
            logger.info("BeliefEngine initialized")
        except Exception as _be_err:
            logger.warning(f"BeliefEngine init failed: {_be_err}")
            self.belief_engine = None

        # Cross-Domain Insight Engine
        try:
            from jagabot.core.cross_domain_engine import CrossDomainEngine
            self.cross_domain_engine = CrossDomainEngine(
                workspace=workspace,
                brier_scorer=None,
            )
            logger.info("CrossDomainEngine initialized")
        except Exception as _cd_err:
            logger.warning(f"CrossDomainEngine init failed: {_cd_err}")
            self.cross_domain_engine = None

        # Hypothesis Engine
        try:
            from jagabot.core.hypothesis_engine import HypothesisEngine
            self.hypothesis_engine = HypothesisEngine(
                workspace=workspace,
                brier_scorer=None,  # wired after brier init
            )
            logger.info("HypothesisEngine initialized")
        except Exception as _he_err:
            logger.warning(f"HypothesisEngine init failed: {_he_err}")
            self.hypothesis_engine = None

        # ChallengeProblems generator
        try:
            from jagabot.core.challenge_problems import ChallengeProblemGenerator
            self.challenge_gen = ChallengeProblemGenerator(
                workspace=workspace,
                brier_scorer=None,  # wired after brier init
            )
            logger.info("ChallengeProblemGenerator initialized")
        except Exception as _cp_err:
            logger.warning(f"ChallengeProblemGenerator init failed: {_cp_err}")
            self.challenge_gen = None

        # CognitiveStack — two-tier model architecture (M1 classifies, M2 plans, M1 executes)
        try:
            from jagabot.core.cognitive_stack import CognitiveStack
            self.cognitive_stack = CognitiveStack(
                workspace        = workspace,
                config_path      = Path.home() / ".jagabot" / "config.json",
                calibration_mode = False,  # Can be configured
            )
            logger.info(
                f"CognitiveStack: M1={self.cognitive_stack.model1_id} "
                f"M2={self.cognitive_stack.model2_id}"
            )
        except Exception as _cs_err:
            import traceback
            logger.error(f"CognitiveStack init failed: {_cs_err}")
            self.cognitive_stack = None
        self.auditor = ResponseAuditor(self.harness, max_retries=2)

        from jagabot.agent.outcome_tracker import OutcomeTracker
        self.outcome_tracker = OutcomeTracker(workspace, self.tools)
        self._session_reminded = False  # only remind once per session

        from jagabot.agent.session_writer import SessionWriter
        self.writer = SessionWriter(workspace, tool_registry=self.tools, outcome_tracker=self.outcome_tracker)

        from jagabot.agent.context_builder import ContextBuilder as DynamicContextBuilder
        from jagabot.agent.session_index import SessionIndex
        from jagabot.engines.engine_improver import EngineImprover
        from jagabot.agent.memory_outcome_bridge import MemoryOutcomeBridge
        from jagabot.agent.connection_detector import ConnectionDetector

        self.ctx_builder = DynamicContextBuilder(workspace, Path("/root/.jagabot/core_identity.md"))
        self.session_index = SessionIndex(workspace)
        self.engine_improver = EngineImprover(workspace, self.tools)
        self.mem_bridge = MemoryOutcomeBridge(workspace, self.tools)
        self.connector = ConnectionDetector(workspace, self.tools)
        self._first_message = True
        self._session_count = 0

        from jagabot.agent.proactive_wrapper import ProactiveWrapper
        self.pro_wrapper = ProactiveWrapper()

        # RepetitionGuard already initialized at line ~104
        # from jagabot.core.repetition_guard import RepetitionGuard
        # self.rep_guard = RepetitionGuard()

        from jagabot.memory.memory_manager import MemoryManager
        self.memory_mgr = MemoryManager(workspace)

        # Phase 1 — Trajectory Monitor (watch for spinning)
        # Already initialized at line ~105
        # from jagabot.core.trajectory_monitor import TrajectoryMonitor
        # self.trajectory_monitor = TrajectoryMonitor()

        # Phase 2 — Brier Scorer (calibration tracking)
        from jagabot.kernels.brier_scorer import BrierScorer
        self.brier = BrierScorer(workspace / "memory" / "brier.db")

        # Phase 3 — Librarian (negative constraints)
        from jagabot.core.librarian import Librarian
        self.librarian = Librarian(workspace, brier_scorer=self.brier)

        # Phase 4 — Strategic Interceptor (AUQ)
        from jagabot.core.strategic_interceptor import StrategicInterceptor
        self.interceptor = StrategicInterceptor(
            brier_scorer=self.brier,
            tool_registry=self.tools,
        )

        # WIRING: Feed BrierScorer trust into CognitiveStack
        if self.cognitive_stack and hasattr(self, 'brier'):
            self.cognitive_stack.brier = self.brier
            logger.info("CognitiveStack ← BrierScorer wired")

        if self.parallel_runner and hasattr(self, 'brier'):
            self.parallel_runner.brier_scorer = self.brier
            logger.info("ParallelRunner ← BrierScorer wired")

        if self.challenge_gen and hasattr(self, 'brier'):
            self.challenge_gen.brier = self.brier
            logger.info("ChallengeProblemGenerator ← BrierScorer wired")

        if self.hypothesis_engine and hasattr(self, 'brier'):
            self.hypothesis_engine.brier = self.brier
            logger.info("HypothesisEngine ← BrierScorer wired")

        if self.cross_domain_engine and hasattr(self, 'brier'):
            self.cross_domain_engine.brier = self.brier
            logger.info("CrossDomainEngine ← BrierScorer wired")

        if self.belief_engine and hasattr(self, 'brier'):
            self.belief_engine.brier = self.brier
            logger.info("BeliefEngine ← BrierScorer wired")

        # System Health Monitor (unified health scoring)
        from jagabot.core.system_health_monitor import SystemHealthMonitor
        self.health_monitor = SystemHealthMonitor(workspace)

        # A2A Handoff (Phase 1 upgrade — handoff instead of kill)
        from jagabot.swarm.a2a_handoff import HandoffPackager, HandoffRouter
        self.handoff_packager = HandoffPackager(
            workspace=workspace,
            librarian=self.librarian,
            brier=self.brier,
        )
        self.handoff_router = HandoffRouter(
            tool_registry=self.tools,
        )

        # Strategy Arbitrator (Phase 2 — Brier-based conflict resolution)
        from jagabot.swarm.arbitrator import StrategyArbitrator
        self.arbitrator = StrategyArbitrator(
            brier_scorer=self.brier,
            workspace=workspace,
        )

        # A2A Coordinator Tool (agent-aware handoff + arbitration)
        from jagabot.agent.tools.a2a_coordinator import A2ACoordinatorTool
        a2a_tool = self.tools.get("a2a_coordinator")
        if a2a_tool:
            # Replace placeholder with fully wired version
            a2a_tool.handoff_packager = self.handoff_packager
            a2a_tool.handoff_router = self.handoff_router
            a2a_tool.arbitrator = self.arbitrator
            a2a_tool.brier = self.brier
            a2a_tool.workspace = workspace

        # Self-Model Engine (preventive — shapes agent behavior before generation)
        from jagabot.engines.self_model_engine import SelfModelEngine
        self.self_model = SelfModelEngine(
            workspace=workspace,
            brier_scorer=self.brier,
            session_index=self.session_index,
            outcome_tracker=self.outcome_tracker,
        )
        logger.info(f"SelfModelEngine initialized: {self.self_model is not None}")

        # Self-Model Awareness Tool (agent-aware of own capabilities)
        # Register and wire directly here (needs SelfModelEngine reference)
        from jagabot.agent.tools.self_model_awareness import SelfModelAwarenessTool
        self_aware_tool = SelfModelAwarenessTool(
            self_model_engine=self.self_model,
            workspace=workspace,
        )
        self.tools.register(self_aware_tool)
        logger.info(f"SelfModelAwarenessTool registered and wired: self_model={self_aware_tool.self_model is not None}")

        # CuriosityEngine (proactive gap surfacing)
        from jagabot.engines.curiosity_engine import CuriosityEngine
        self.curiosity = CuriosityEngine(
            workspace=workspace,
            self_model=self.self_model,
            session_index=self.session_index,
            connection_det=self.connector,
        )
        logger.info(f"CuriosityEngine initialized")

        # ConfidenceEngine (structured uncertainty communication)
        from jagabot.engines.confidence_engine import ConfidenceEngine
        self.confidence_engine = ConfidenceEngine(
            workspace=workspace,
            brier_scorer=self.brier,
            self_model=self.self_model,
        )
        logger.info(f"ConfidenceEngine initialized")

        # Register awareness tools (need engine references)
        from jagabot.agent.tools.self_model_awareness import SelfModelAwarenessTool
        from jagabot.agent.tools.curiosity_awareness import CuriosityAwarenessTool
        from jagabot.agent.tools.confidence_awareness import ConfidenceAwarenessTool
        
        # Re-wire with actual engine references (tools were created earlier without engines)
        self_aware_tool = SelfModelAwarenessTool(
            self_model_engine=self.self_model,
            workspace=workspace,
        )
        curiosity_aware_tool = CuriosityAwarenessTool(
            curiosity_engine=self.curiosity,
            workspace=workspace,
        )
        confidence_aware_tool = ConfidenceAwarenessTool(
            confidence_engine=self.confidence_engine,
            workspace=workspace,
        )
        
        self.tools.register(self_aware_tool)
        self.tools.register(curiosity_aware_tool)
        self.tools.register(confidence_aware_tool)
        
        logger.info(f"SelfModelAwarenessTool registered: {self_aware_tool.self_model is not None}")
        logger.info(f"CuriosityAwarenessTool registered: {curiosity_aware_tool.curiosity is not None}")
        logger.info(f"ConfidenceAwarenessTool registered: {confidence_aware_tool.confidence_engine is not None}")

        # Model switchboard tool (agent can self-switch when outclassed)
        if hasattr(self, 'switchboard'):
            from jagabot.agent.tools.base import Tool
            from typing import Any
            
            class ModelSwitchTool(Tool):
                @property
                def name(self) -> str:
                    return "switch_model"
                
                @property
                def description(self) -> str:
                    return (
                        "Switch to a more capable model for this turn. "
                        "Call when task requires complex reasoning, calibration, "
                        "or multi-step verification. Only call when genuinely needed."
                    )
                
                @property
                def parameters(self) -> dict[str, Any]:
                    return self.switchboard.get_tool_definition()
                
                async def execute(self, **kwargs: Any) -> str:
                    preset_id = kwargs.get("preset_id", "2")
                    reason = kwargs.get("reason", "")
                    return self.switchboard.switch_model(preset_id, reason)
            
            # Wire switchboard reference into tool
            switch_tool = ModelSwitchTool()
            switch_tool.switchboard = self.switchboard
            self.tools.register(switch_tool)
            logger.info(f"ModelSwitchTool registered: agent can self-switch models")

        from jagabot.core.behavior_monitor import BehaviorMonitor
        from jagabot.core.recovery import WorkspaceCheckpoint
        from jagabot.core.context_compressor import ContextCompressor
        self.behavior_monitor = BehaviorMonitor()
        self.checkpoint = WorkspaceCheckpoint(workspace)
        self.context_compressor = ContextCompressor()

        self._register_default_tools()
    
    def _register_default_tools(self) -> None:
        """Register the default set of tools (delegated to tool_loader)."""
        from jagabot.agent.tool_loader import register_default_tools

        register_default_tools(
            self.tools,
            workspace=self.workspace,
            restrict_to_workspace=self.restrict_to_workspace,
            exec_config=self.exec_config,
            brave_api_key=self.brave_api_key,
            bus=self.bus,
            subagents=self.subagents,
            cron_service=self.cron_service,
            provider=self.provider,
            model=self.model,
        )
    
    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        self._running = True
        logger.info("Agent loop started")
        
        while self._running:
            try:
                # Wait for next message
                msg = await asyncio.wait_for(
                    self.bus.consume_inbound(),
                    timeout=1.0
                )
                
                # Process it
                try:
                    response = await self._process_message(msg)
                    if response:
                        await self.bus.publish_outbound(response)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Send error response
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=f"Sorry, I encountered an error: {str(e)}"
                    ))
            except asyncio.TimeoutError:
                continue
    
    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")

    async def call_llm(
        self,
        prompt: str,
        context: str = "",
        model_id: str = None,
        max_tokens: int = 1000,
    ) -> str:
        """
        Call LLM with a specific model_id override.
        Used by CognitiveStack to route to M1 or M2 per step.
        
        Args:
            prompt: User prompt
            context: Optional system context
            model_id: Model to use (overrides default)
            max_tokens: Max tokens in response
        
        Returns:
            LLM response content
        """
        model_id = model_id or self._current_model_id
        
        messages = []
        if context:
            messages.append({"role": "system", "content": context})
        messages.append({"role": "user", "content": prompt})
        
        # Use provider's chat method directly
        from jagabot.providers.base import LLMResponse
        response: LLMResponse = await self.provider.chat(
            messages=messages,
            model=model_id,
            max_tokens=max_tokens,
            temperature=0.7,
        )
        
        return response.content or ""

    # ------------------------------------------------------------------
    # Response claim verification is handled by self.harness
    # (see jagabot/core/tool_harness.py)
    # ------------------------------------------------------------------

    async def _process_message(self, msg: InboundMessage, session_key: str | None = None) -> OutboundMessage | None:
        """
        Process a single inbound message.
        
        Args:
            msg: The inbound message to process.
            session_key: Override session key (used by process_direct).
        
        Returns:
            The response message, or None if no response needed.
        """
        # Handle system messages (subagent announces)
        # The chat_id contains the original "channel:chat_id" to route back to
        if msg.channel == "system":
            return await self._process_system_message(msg)

        # PHASE 5 — TRIVIAL GUARD: Skip LLM for greetings/acks
        from jagabot.core.trivial_guard import is_trivial, trivial_response
        from jagabot.core.token_budget import budget

        if is_trivial(msg.content):
            reply = trivial_response(msg.content)
            budget.record_skip()
            logger.info(f"Trivial guard fired — LLM call skipped for: '{msg.content}'")
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=reply,
                metadata=msg.metadata or {},
            )

        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        logger.info(f"Processing message from {msg.channel}:{msg.sender_id}: {preview}")

        # FLUID DISPATCH — classify intent, load only relevant tools/context
        from jagabot.core.fluid_dispatcher import FluidDispatcher
        if not hasattr(self, 'dispatcher'):
            self.dispatcher = FluidDispatcher(
                workspace=self.workspace,
                k1_tool=None,  # Can wire k1_bayesian later
            )
        
        package = self.dispatcher.dispatch(
            user_input=msg.content,
            topic="general",  # Can use topic detector
            confidence=getattr(self, '_last_confidence', 1.0),
            has_pending=False,
        )
        logger.debug(f"FluidDispatcher: {package.profile} | ~{package.token_estimate} tokens | tools={len(package.tools)}")

        # MODEL SWITCHBOARD — select model based on profile
        from jagabot.core.model_switchboard import ModelSwitchboard
        if not hasattr(self, 'switchboard'):
            self.switchboard = ModelSwitchboard(
                config_path=Path.home() / ".jagabot" / "config.json",  # Use Path from imports
                workspace=self.workspace,
            )
        
        model_config = self.switchboard.resolve_model(
            profile=package.profile,
            confidence=getattr(self, '_last_confidence', 1.0),
            manual_override=None,
        )
        logger.debug(f"ModelSwitchboard: {model_config.model_id} ({model_config.reason})")
        self._current_model_id = model_config.model_id

        # WIRING: BrierScorer trust → CognitiveStack calibration mode
        if self.cognitive_stack and hasattr(self, 'brier'):
            _topic = locals().get('topic', 'general')
            _trust = self.brier.trust_score("general", _topic)
            _trust = _trust if _trust is not None else 1.0
            self._last_confidence = _trust

            # Route through BeliefEngine for calibrated recommendation
            if self.belief_engine:
                _belief = self.belief_engine.update(
                    domain         = _topic,
                    perspective    = "general",
                    raw_confidence = _trust,
                )
                _cog_rec = self.belief_engine.get_cognitive_recommendation(_topic)
                if _cog_rec == "CRITICAL":
                    self.cognitive_stack.calibration_mode = True
                    logger.info(
                        f"BeliefEngine → CognitiveStack: CRITICAL "
                        f"(calibrated={_belief.calibrated_confidence:.2f})"
                    )
                else:
                    self.cognitive_stack.calibration_mode = False
                    logger.debug(
                        f"BeliefEngine → CognitiveStack: {_cog_rec} "
                        f"(calibrated={_belief.calibrated_confidence:.2f})"
                    )
            else:
                if _trust < 0.5:
                    self.cognitive_stack.calibration_mode = True
                else:
                    self.cognitive_stack.calibration_mode = False

        # Reset repetition guard for new user turn
        self.rep_guard.reset_for_new_turn()

        # Reset trajectory monitor for new turn
        self.trajectory_monitor.reset()

        # Load relevant memory context for this query
        memory_context = self.memory_mgr.get_context(
            query=msg.content,
            session_key=session_key or msg.session_key,
        )

        # Phase 3 — Librarian: inject negative constraints
        topic = self.memory_mgr._detect_topic(msg.content)
        negative_constraints = self.librarian.get_constraints(topic=topic)

        # Self-Model Engine: inject self-knowledge into Layer 1
        self_context = self.self_model.get_context(
            query=msg.content,
            topic=topic,
        )

        # Get or create session
        key = session_key or msg.session_key
        session = self.sessions.get_or_create(key)

        # CuriosityEngine: surface relevant gaps at session start (first message only)
        if self._first_message:
            curiosity_suggestions = self.curiosity.get_session_suggestions(
                current_query=msg.content,
                session_key=key,
            )
            if curiosity_suggestions.has_suggestions:
                logger.info(f"Curiosity Engine: {len(curiosity_suggestions.targets)} suggestions surfaced")
            
            # Auto-check domain reliability for high-stakes domains
            topic = detect_topic(msg.content) if 'detect_topic' in dir() else "general"
            if topic in ["financial", "healthcare", "causal"]:
                reliability = self.self_model.get_domain_model(topic)
                if reliability and reliability.reliability < 0.5:
                    logger.warning(f"Pre-check: {topic} domain has low reliability ({reliability.reliability:.2f}) — will enforce hedging")

        # ── Session startup reminder (first message only) ───────────
        if self._first_message:
            self._first_message = False
            # Connection detection — proactive research partner behavior
            connections = self.connector.detect(
                current_query=msg.content,
                session_key=session.key,
            )
            if connections.has_insights:
                logger.info(f"💡 Connections found: {len(connections.connections)}")
                # Show user-facing message
                return OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=connections.format_for_user(),
                    metadata=msg.metadata or {},
                )

            # Session index reminder
            reminder = self.session_index.get_startup_reminder()
            if reminder:
                logger.info(f"📚 Session reminder shown: {reminder[:80]}...")
                return OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=reminder,
                    metadata=msg.metadata or {},
                )
            
            # Pending outcomes reminder
            # PARALLEL AGENT TRIGGER — real multi-agent execution (runs every message)
        _parallel_keywords = [
            "run subagents", "run all agents", "parallel agents",
            "each subagent", "all perspectives", "bull bear buffet",
            "run perspectives", "multi-agent analysis",
        ]
        if (
            self.parallel_runner is not None
            and any(kw in msg.content.lower() for kw in _parallel_keywords)
        ):
            logger.info(f"ParallelRunner: triggered for '{msg.content[:50]}'")
            try:
                parallel_result = await self.parallel_runner.run(
                    task=msg.content,
                    agents=[
                        {"role": "bull", "system": "You are an optimistic analyst. Find opportunities and upside. End with VERDICT/CONFIDENCE/EVIDENCE."},
                        {"role": "bear", "system": "You are a skeptical analyst. Find risks and downside. End with VERDICT/CONFIDENCE/EVIDENCE."},
                        {"role": "buffet", "system": "You are a value-focused analyst. Find long-term fundamentals. End with VERDICT/CONFIDENCE/EVIDENCE."},
                    ],
                    converge_via="arbitration",
                )
                final_content = getattr(parallel_result, 'converged_output', str(parallel_result))
                return OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=final_content,
                    metadata=msg.metadata or {},
                )
            except Exception as _pr_err:
                logger.warning(f"ParallelRunner failed, falling back to single agent: {_pr_err}")
                # Falls through to normal processing
        
        # Skip reminder if user is currently submitting an outcome verdict
        _is_verdict = any(
            kw in msg.content.lower()
            for kw in [
                "outcome:", "verdict:", "correct", "wrong", "partial",
                "skip outcomes", "inconclusive", "spawn", "subagent",
                "run all agents", "parallel", "multi-agent",
            ]
        )
        pending = self.outcome_tracker.get_pending_reminder()
        if pending and not _is_verdict and not self._session_reminded:
            self._session_reminded = True  # never show again this session
            logger.info("📌 Pending outcomes reminder shown")
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=pending,
                metadata=msg.metadata or {},
            )

        # ── Check if user is providing outcome feedback ─────────────
        # Skip verdict detection for self-reflection and analysis queries
        _skip_verdict = any(s in msg.content.lower() for s in [
            "pathological failure", "hidden assumption", "counter-scenario",
            "adversarial", "guardrail", "self-reflect", "reasoning chain",
            "failure analysis", "edge case", "logic loop", "analyze your",
            "critique your", "what went wrong", "your mistakes",
            "incorrect answer", "wrong answer", "false positive",
        ])
        feedback = None if _skip_verdict else self.outcome_tracker.record_outcome_by_context(msg.content)
        if feedback:
            # User said "that was correct/wrong" — loop closed
            logger.info("✅ Outcome recorded via natural language")
            # Return feedback as response (skip full agent processing)
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=feedback,
                metadata=msg.metadata or {},
            )

        # Handle slash commands
        cmd = msg.content.strip().lower()
        if cmd == "/new":
            await self._consolidate_memory(session, archive_all=True)
            session.clear()
            self.sessions.save(session)
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
                                  content="🐈 New session started. Memory consolidated.")
        if cmd == "/help":
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
                                  content="🐈 jagabot commands:\n/new — Start a new conversation\n/help — Show available commands")
        
        # Consolidate memory before processing if session is too large
        if len(session.messages) > self.memory_window:
            await self._consolidate_memory(session)
        
        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(msg.channel, msg.chat_id)
        
        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(msg.channel, msg.chat_id)
        
        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(msg.channel, msg.chat_id)
        
        # Build initial messages (use get_history for LLM-formatted messages)
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            media=msg.media if msg.media else None,
            channel=msg.channel,
            chat_id=msg.chat_id,
        )

        # Inject compressed context summary for long sessions
        if self.context_compressor.turn_count >= 10:
            compressed = self.context_compressor.get_compressed_context()
            if compressed and messages and messages[0].get("role") == "system":
                messages[0]["content"] += (
                    "\n\n--- Conversation history summary ---\n" + compressed
                )
        
        # Layer 1: micro-compact old tool results to save tokens
        from jagabot.agent.compressor import micro_compact, should_auto_compact, save_transcript
        micro_compact(messages)

        # Layer 2: auto-compact if tokens exceed threshold
        if should_auto_compact(messages):
            transcripts_dir = self.workspace / "transcripts"
            save_transcript(messages, transcripts_dir)
            if len(session.messages) > 4:
                await self._consolidate_memory(session)

        # Agent loop with audit-in-the-loop verification
        self.auditor.causal_tracer.clear()  # Fresh causal log per message
        self.auditor.clear_log()  # Clear audit log and pending missing files
        
        # Phase 4 — Means-End Analysis: for complex tasks enumerate approaches
        _fluid_profile = package.profile if 'package' in locals() else "SAFE_DEFAULT"
        _is_complex = _fluid_profile in ("RESEARCH", "CALIBRATION", "VERIFICATION")
        if _is_complex and self.cognitive_stack and self.bdi_tracker:
            try:
                _mea_prompt = (
                    f"Task: {msg.content[:200]}\n\n"
                    f"Before executing, briefly list 2-3 possible approaches "
                    f"and select the best one. Format:\n"
                    f"APPROACH 1: ...\nAPPROACH 2: ...\nAPPROACH 3: ...\n"
                    f"SELECTED: [number] because [reason]\n"
                    f"Keep this under 100 words."
                )
                _mea_response = await self.provider.chat(
                    messages=[{"role": "user", "content": _mea_prompt}],
                    model=self.cognitive_stack.model1_id,
                    max_tokens=150,
                    temperature=0.3,
                )
                _mea_text = _mea_response.content if _mea_response else ""
                _approach_count = _mea_text.lower().count("approach")
                if _approach_count >= 2:
                    self.bdi_tracker.record_means_end(_approach_count)
                    # Inject selected approach into context
                    if messages and messages[0].get("role") == "system":
                        messages[0]["content"] += (
                            f"\n\n[Means-End Analysis]\n{_mea_text}"
                        )
                    logger.info(f"Means-End: {_approach_count} approaches considered")
            except Exception as _mea_err:
                logger.debug(f"Means-End Analysis skipped: {_mea_err}")
        
        messages, final_content, tools_used = await self._run_agent_loop(
            messages, self.max_iterations,
            user_query=msg.content,  # Pass query for tool filtering
        )
        
        # Log response preview
        preview = final_content[:120] + "..." if len(final_content) > 120 else final_content
        logger.info(f"Response to {msg.channel}:{msg.sender_id}: {preview}")

        # ── Audit loop: verify & self-correct before user sees it ──
        auditor_approved = False  # Track final auditor approval status
        for _audit_pass in range(self.auditor.max_retries + 1):
            result = self.auditor.audit(final_content, tools_used, attempt=_audit_pass, messages=messages)
            if result.approved:
                final_content = result.content
                auditor_approved = True
                break

            if _audit_pass >= self.auditor.max_retries:
                # All retries exhausted — return with warning as last resort
                final_content = result.content
                logger.warning("Auditor: max retries exhausted, returning with warning")
                break

            # Inject feedback and attempt ACTION execution (not just a new plan)
            logger.info(f"Auditor: retry {_audit_pass + 1} — injecting feedback")
            messages.append({"role": "user", "content": result.feedback})

            # Ask the assistant to return a strict JSON plan of tool actions so
            # the runtime can execute them deterministically. This avoids the
            # assistant replying with a natural-language "I will do X" without
            # actually calling any tools.
            plan_request = (
                "Please respond ONLY with a JSON array (no prose). Each item must be "
                "an object with keys: \"tool\" (string) and \"args\" (object). "
                "IMPORTANT: Do NOT use brace expansion like {a,b,c} - use separate commands instead."
                "Example: [{\"tool\":\"exec\",\"args\":{\"command\":\"mkdir -p /root/.jagabot/workspace/tools\"}}, {\"tool\":\"exec\",\"args\":{\"command\":\"mkdir -p /root/.jagabot/workspace/analysis\"}}]"
            )
            messages.append({"role": "user", "content": plan_request})

            # Request plan as text (no tools) and try to parse JSON
            try:
                plan_resp = await self.provider.chat(
                    messages=messages,
                    tools=[],
                    model=self.model,
                    temperature=self.temperature,
                )
                plan_text = (plan_resp.content or "").strip()
            except Exception as exc:
                logger.warning(f"Plan extraction call failed: {exc}")
                # Fallback to previous behaviour: let the agent try to call tools
                messages, final_content, extra_tools = await self._run_agent_loop(
                    messages, max_iterations=15,
                )
                tools_used.extend(extra_tools)
                continue

            # Try to extract JSON array from the assistant's reply (allow code fences)
            plan_json = None
            try:
                # Find the first JSON array ([...] ) in the text
                m = re.search(r"(\[.*\])", plan_text, flags=re.DOTALL)
                json_str = m.group(1) if m else plan_text
                # Remove markdown fences if present
                if json_str.startswith("```"):
                    json_str = json_str.strip('`\n')
                # Normalize escaped newlines in string values: LLMs often output \\n
                # which should be \n in actual JSON. Fix common escape issues.
                json_str = _normalize_json_escapes(json_str)
                plan_json = json.loads(json_str)
            except Exception as exc:
                logger.warning(f"Could not parse plan JSON: {exc}; plan_text={plan_text[:200]!r}")
                # Fallback: inject a clearer prompt and let the agent try with tools
                messages.append({
                    "role": "user",
                    "content": (
                        "⚠️ JSON parsing failed. Please use ACTUAL tool calls (function calling) to complete the task.\n"
                        "Do NOT output JSON text. Instead, use the tool calls provided by your interface.\n"
                        f"Available tools: {', '.join(t['function']['name'] for t in self.tools.get_definitions())}"
                    )
                })
                messages, final_content, extra_tools = await self._run_agent_loop(
                    messages, max_iterations=15,
                )
                tools_used.extend(extra_tools)
                continue

            # Ensure plan is a list of actions
            if not isinstance(plan_json, list):
                logger.warning("Plan JSON is not a list; falling back to LLM-executed tools.")
                messages.append({
                    "role": "user",
                    "content": (
                        "⚠️ Plan format incorrect. Please use ACTUAL tool calls (function calling) to complete the task.\n"
                        "Do NOT output JSON text or prose. Instead, use the tool calls provided by your interface.\n"
                        f"Available tools: {', '.join(t['function']['name'] for t in self.tools.get_definitions())}"
                    )
                })
                messages, final_content, extra_tools = await self._run_agent_loop(
                    messages, max_iterations=15,
                )
                tools_used.extend(extra_tools)
                continue

            # Execute each action in the plan deterministically
            for idx, action in enumerate(plan_json):
                if not isinstance(action, dict) or "tool" not in action:
                    logger.warning(f"Skipping invalid plan entry at index {idx}: {action}")
                    continue
                tool_name = action["tool"]
                args = action.get("args", {}) or {}

                tools_used.append(tool_name)

                h_id = self.harness.register(tool_name)

                try:
                    result = await self.tools.execute(tool_name, args)

                    # Retry once on simple string error
                    if isinstance(result, str) and result.startswith("Error"):
                        logger.warning(f"Tool {tool_name} failed, retrying once")
                        result = await self.tools.execute(tool_name, args)

                    if isinstance(result, str) and result.startswith("Error"):
                        self.harness.fail(h_id, result[:200])
                        result_str = result
                    else:
                        result_str = str(result) if result is not None else ""
                        self.harness.complete(h_id, result_text=result_str)
                except Exception as exc:
                    err = f"Error executing tool {tool_name}: {exc}"
                    logger.exception(err)
                    self.harness.fail(h_id, str(exc)[:200])
                    result_str = err

                # Create a synthetic tool_call_id for history
                tool_call_id = f"plan:{int(time.time()*1000)}:{_audit_pass}:{idx}"

                # Create a synthetic assistant message that contains the tool_calls
                # entry the provider expects; tool-role messages MUST follow an
                # assistant message that declared matching tool_calls.
                try:
                    tool_call_dict = {
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(args, ensure_ascii=False),
                        },
                    }
                    # Add assistant message referencing the tool call
                    messages = self.context.add_assistant_message(
                        messages, content="", tool_calls=[tool_call_dict]
                    )
                except Exception:
                    logger.debug("Failed to add synthetic assistant tool_calls message; proceeding to attach tool result")

                # Now append the tool result message (valid because an assistant
                # message with matching tool_calls precedes it)
                messages = self.context.add_tool_result(messages, tool_call_id, tool_name, result_str)

                # Record causal tracer entry
                try:
                    self.auditor.causal_tracer.record(tool_name, json.dumps(args)[:200], result_str[:2048])
                except Exception:
                    # Non-critical — continue executing remaining actions
                    logger.debug("Causal tracer record failed for plan action")

            # After executing the plan actions, VERIFY files exist before summarizing
            # This is CRITICAL for audit loop corrective actions
            execution_results = []
            files_still_missing = []
            tool_outputs = []  # Collect actual tool outputs for final response
            
            for entry in plan_json:
                tool_name = entry.get("tool", "unknown")
                args = entry.get("args", {})

                # For write_file operations, verify the file actually exists on disk
                if tool_name in ("write_file", "create_file", "save_file"):
                    file_path = args.get("path", "")
                    if file_path:
                        # Resolve path (handle relative paths)
                        resolved_path = Path(file_path) if Path(file_path).is_absolute() else self.workspace / file_path
                        if resolved_path.exists():
                            execution_results.append((tool_name, args, "verified"))
                            tool_outputs.append(f"✅ Created {file_path}")
                        else:
                            execution_results.append((tool_name, args, "FAILED - file not on disk"))
                            files_still_missing.append(str(resolved_path))
                elif tool_name == "read_file":
                    # For read_file, we already have the result in harness history
                    file_path = args.get("path", "unknown")
                    execution_results.append((tool_name, args, "read"))
                    tool_outputs.append(f"📄 Read {file_path} (see content above)")
                elif tool_name == "exec":
                    # For exec, show the command
                    cmd = args.get("command", "")[:80]
                    execution_results.append((tool_name, args, "executed"))
                    tool_outputs.append(f"⚙️ Executed: {cmd}...")
                else:
                    execution_results.append((tool_name, args, "executed"))
                    tool_outputs.append(f"✅ {tool_name} completed")

            # If files are still missing after corrective actions, block approval
            if files_still_missing:
                logger.error(f"TEST 4 FIX: Files still missing after corrective action: {files_still_missing}")
                # Force another audit retry by injecting a hard failure message
                messages.append({
                    "role": "user",
                    "content": (
                        f"🚨 CRITICAL VERIFICATION FAILURE:\n"
                        f"You claimed to create these files: {files_still_missing}\n"
                        f"But they DO NOT EXIST on disk!\n\n"
                        f"MANDATORY ACTION: Use write_file to create EACH missing file NOW.\n"
                        f"Do NOT say 'Test complete' until ALL files are verified on disk.\n"
                        f"Retry will continue until files exist or max retries exhausted."
                    )
                })
                # Continue to next audit pass - this will trigger another retry
                final_content = f"⚠️ Verification pending: {len(files_still_missing)} file(s) not found"
                continue

            # RE-VERIFY after executing corrective actions
            # This is CRITICAL - don't trust "executed", verify on disk directly
            logger.info(f"Audit pass {_audit_pass + 1}: Re-verifying files on disk")

            # Direct disk verification of pending missing files
            all_exist, still_missing = self.auditor.verify_pending_files(self.workspace)

            if not all_exist:
                # Files still missing - inject hard failure feedback and continue retry
                logger.error(f"Re-verification FAILED: Files still missing: {still_missing}")
                messages.append({
                    "role": "user",
                    "content": (
                        f"🚨 CRITICAL VERIFICATION FAILURE (Test 4 Fix):\n"
                        f"You claimed to create these files: {still_missing}\n"
                        f"But they DO NOT EXIST on disk after tool execution!\n\n"
                        f"MANDATORY ACTION: Use write_file to create EACH missing file NOW.\n"
                        f"Do NOT say 'Test complete' until ALL files are verified on disk.\n"
                        f"Retry will continue until files exist or max retries exhausted."
                    )
                })
                continue

            # Re-verification passed - all files exist
            # Generate a natural response summarizing what was done
            logger.info(f"Re-verification PASSED after {_audit_pass + 1} retries - all files on disk")
            
            # Build a proper response from tool outputs
            if tool_outputs:
                final_content = "\n".join(tool_outputs)
            else:
                final_content = "✅ Task completed successfully."
            break

        # ── Behavior monitoring (informational anomaly detection) ──
        iteration_count = len([t for t in tools_used])  # approx iterations
        self.behavior_monitor.record_turn(
            tools_used=tools_used,
            iteration_count=iteration_count,
            response_length=len(final_content),
            user_message=msg.content,
        )
        anomalies = self.behavior_monitor.check_anomalies()
        if anomalies:
            logger.info(f"Behavior monitor: {len(anomalies)} anomalie(s) detected")

        # Save to session (include tool names so consolidation sees what happened)
        session.add_message("user", msg.content)
        session.add_message("assistant", final_content,
                            tools_used=tools_used if tools_used else None)
        self.sessions.save(session)

        # ── Auto-save research output to disk (Karpathy-style) ──
        self.writer.save(
            content=final_content,
            query=msg.content,
            tools_used=tools_used,
            session_key=session.key,
            auditor_approved=auditor_approved,
            anomaly_count=len(self.behavior_monitor.check_anomalies()),
        )

        # BDI Scorecard — record autonomy score for this turn
        if self.bdi_tracker:
            try:
                from jagabot.core.bdi_scorecard import score_turn
                _anomalies = len(self.behavior_monitor.check_anomalies())
                _tool_errors = sum(
                    1 for t in (tools_used or [])
                    if isinstance(t, dict) and t.get("error")
                )
                _belief_state = self.bdi_tracker.get_belief_state() if self.bdi_tracker else None
                _desire_state = self.bdi_tracker.get_desire_state() if self.bdi_tracker else None
                _intention_state = self.bdi_tracker.get_intention_state() if self.bdi_tracker else None
                _bdi = score_turn(
                    tools_used=tools_used or [],
                    quality=self.writer.scorer.score(
                        content=final_content,
                        tools_used=tools_used,
                    ),
                    anomaly_count=_anomalies,
                    tool_errors=_tool_errors,
                    belief_state=_belief_state,
                    desire_state=_desire_state,
                    intention_state=_intention_state,
                )
                self.bdi_tracker.record(_bdi)
            except Exception as _e:
                logger.debug(f"BDI scoring failed: {_e}")

        # Add per-output reliability note (FIX 3)
        if self.self_model and final_content and len(final_content) > 100:
            # Get quality score from writer
            session_quality = getattr(self.writer, '_last_quality', None)
            
            # Detect topic for domain reliability
            topic = "general"
            text_lower = msg.content.lower()
            if any(w in text_lower for w in ["stock", "portfolio", "risk", "margin", "financial"]):
                topic = "financial"
            elif any(w in text_lower for w in ["research", "study", "hypothesis"]):
                topic = "research"
            elif any(w in text_lower for w in ["code", "software", "engineering"]):
                topic = "engineering"
            
            # Get domain reliability from self_model
            domain_trust = None
            if hasattr(self.self_model, 'get_domain_reliability'):
                try:
                    domain_trust = self.self_model.get_domain_reliability(topic)
                except Exception:
                    pass
            
            # Only show note if trust is below threshold or quality is notable
            reliability_note = None
            if domain_trust is not None and domain_trust < 0.65:
                reliability_note = (
                    f"\n\n*[Reliability: {domain_trust:.0%} confidence in {topic} domain — "
                    f"verify key claims]*"
                )
            elif session_quality is not None and session_quality < 0.6:
                reliability_note = (
                    f"\n\n*[Quality score: {session_quality:.0%} — lower confidence response]*"
                )
            
            if reliability_note:
                final_content = final_content + reliability_note
                logger.debug(f"Reliability note added: topic={topic}, trust={domain_trust}, quality={session_quality}")

        # ── ProactiveWrapper: ensure response has interpretation ────
        final_content = self.pro_wrapper.enhance(
            content=final_content,
            query=msg.content,
            tools_used=tools_used,
        )

        # ── Update session index ────────────────────────────────────
        quality_score = self.writer.scorer.score(
            content=final_content,
            tools_used=tools_used,
            auditor_approved=auditor_approved,
        )
        self.session_index.update(
            session_key=session.key,
            query=msg.content,
            content=final_content,
            quality=quality_score,
            tools_used=tools_used,
            pending_outcomes=len(self.outcome_tracker._load_pending()),
        )

        # ── Automatic Evaluation (FIX 5) — post-response hook ───────
        # Only for complex profiles (RESEARCH, VERIFICATION, CALIBRATION)
        harness_profile = getattr(self, '_last_profile', 'SAFE_DEFAULT')
        if (
            harness_profile in ("RESEARCH", "VERIFICATION", "CALIBRATION") and
            len(final_content) > 200  # skip trivial responses
        ):
            try:
                eval_result = self._auto_evaluate(
                    content=final_content,
                    query=msg.content,
                    topic=self._detect_topic(msg.content),
                )
                if eval_result and eval_result.get("issues"):
                    logger.info(
                        f"AutoEval: {len(eval_result['issues'])} issue(s) found"
                    )
                    # Store for /eval command
                    self._last_eval = eval_result
            except Exception as _ae_err:
                logger.debug(f"AutoEval skipped: {_ae_err}")

        # ── Run improvement cycle every 10 sessions ─────────────────
        self._session_count += 1
        if self._session_count % 10 == 0 and self.engine_improver.should_run():
            logger.info("🔧 Running engine improvement cycle...")
            self.engine_improver.run_improvement_cycle()

        # Record turn for context compressor (milestone summaries)
        self.context_compressor.add_turn(msg.content, final_content, tools_used)

        # Store findings and update user model
        quality_score = self.writer.scorer.score(
            content=final_content,
            tools_used=tools_used,
            auditor_approved=auditor_approved,
        )
        
        # Detect topic locally
        def detect_topic(text: str) -> str:
            text_lower = text.lower()
            # Simple topic detection based on keywords
            topic_map = {
                "quantum": ["quantum", "qubit", "superposition"],
                "healthcare": ["hospital", "patient", "clinical", "drug", "medical"],
                "financial": ["stock", "portfolio", "risk", "margin", "equity", "var"],
                "causal": ["causal", "ipw", "confounder", "regression"],
                "research": ["hypothesis", "experiment", "study", "paper"],
                "ideas": ["brainstorm", "idea", "creative", "novel"],
                "engineering": ["agent", "tool", "harness", "kernel", "engine"],
                "learning": ["calibration", "accuracy", "self-improvement", "meta"],
            }
            scores = {}
            for topic, keywords in topic_map.items():
                scores[topic] = sum(1 for kw in keywords if kw in text_lower)
            best = max(scores, key=scores.get) if scores else "general"
            return best if scores.get(best, 0) > 0 else "general"
        
        self.memory_mgr.store_turn(
            query=msg.content,
            response=final_content,
            tools_used=tools_used,
            quality=quality_score,
            topic=detect_topic(msg.content),
        )

        # Self-Model Engine: update from this interaction
        self.self_model.update_from_turn(
            query=msg.content,
            response=final_content,
            tools_used=tools_used,
            quality=quality_score,
            topic=detect_topic(msg.content),
            session_key=session.key,
        )
        
        # Reliability Logger: automatically log domain, confidence, outcome
        topic = detect_topic(msg.content)
        if topic != "general":
            # Log to HISTORY.md for tracking
            from datetime import datetime
            history_file = self.workspace / "memory" / "HISTORY.md"
            if history_file.exists():
                with open(history_file, "a") as f:
                    f.write(f"\n[{datetime.now().isoformat()}] RELIABILITY_LOG | domain={topic} | quality={quality_score:.2f} | tools={len(tools_used)}\n")
                logger.debug(f"Reliability logged: domain={topic}, quality={quality_score:.2f}")

        # ── Prevent instruction echo ─────────────────────────────────
        # Strip any content that matches the user's input
        user_msg = msg.content.strip()
        if user_msg and user_msg in final_content:
            final_content = final_content.replace(user_msg, "").strip()
            # Clean up any resulting double newlines
            final_content = re.sub(r'\n\s*\n', '\n\n', final_content).strip()

        # ConfidenceEngine: annotate response with structured uncertainty
        final_content = self.confidence_engine.annotate_response(
            response=final_content,
            topic=topic,  # ConfidenceEngine uses 'topic' not 'domain'
            tools_used=tools_used,
        )
        
        # Pre-Check Guardrail: enforce hedging in low-reliability domains
        if topic in ["financial", "healthcare", "causal"]:
            reliability = self.self_model.get_domain_model(topic)
            if reliability and reliability.reliability < 0.5:
                # Automatically add hedging note
                hedge_note = f"\n\n⚠️ **Domain Reliability Warning:** My track record in {topic} is poor (reliability={reliability.reliability:.2f}). These findings should be verified with real-world data before acting on them."
                final_content += hedge_note
                logger.info(f"Pre-check guardrail: added hedging note for {topic} domain")

        # ── Phase 4 — Strategic Interceptor (AUQ) ────────────────────
        # Check for overconfidence before showing to user
        intercept_result = self.interceptor.intercept(
            response    = final_content,
            query       = msg.content,
            tools_used  = tools_used,
            session_key = session.key,
        )
        
        if intercept_result.needs_pivot:
            # Force perspective pivot
            logger.info(f"Phase 4: Intercepting — trust too low, pivoting perspective")
            final_content = intercept_result.adjusted_response

        # Phase 2 — Brier Scorer: adjust confidence numbers
        final_content = self.brier.adjust_response_confidence(
            response    = final_content,
            perspective = "general",  # Could detect from content
            domain      = topic,
        )

        # WIRING: BrierScorer — NOT recorded here (outcome unknown)
        # BrierScorer.record() is ONLY called by outcome_tracker.record_verified_outcome()
        # when user provides verified verdict (correct/wrong/partial)
        # Recording actual=1.0 here would corrupt calibration data
        logger.debug(
            f"BrierScorer: deferred for '{topic}' — will record when outcome verified"
        )

        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content,
            metadata=msg.metadata or {},  # Pass through for channel-specific needs (e.g. Slack thread_ts)
        )
    
    async def _run_agent_loop(
        self,
        messages: list[dict],
        max_iterations: int = 30,
        user_query: str = "",  # For tool filtering
    ) -> tuple[list[dict], str, list[str]]:
        """
        Run the core agent loop: LLM call → tool execution → repeat.

        Returns:
            (messages, final_content, tools_used)
        """
        iteration = 0
        final_content = None
        tools_used: list[str] = []
        _consecutive_failures: dict[str, int] = {}
        _duplicate_commands: dict[str, int] = {}  # (name+args_hash) -> count
        _MAX_TOOL_RETRIES = 3

        while iteration < max_iterations:
            iteration += 1

            # PHASE 1 — TOOL FILTERING: Send only relevant tools from FluidDispatcher
            # Use tools from package if available, otherwise filter by query
            if 'package' in locals() and package.tools:
                tools_payload = package.tools
            else:
                tools_payload = get_tools_for_query(user_query, self.tools)
            logger.debug(f"API call: {len(tools_payload)} tools sent, model={self._current_model_id}")

            # PHASE 3 — HISTORY COMPRESSION: Prevent unbounded token growth
            from jagabot.core.history_compressor import compress_history
            messages = await compress_history(messages)

            # Use dynamically selected model for this turn
            response = await self.provider.chat(
                messages=messages,
                tools=tools_payload,
                model=self._current_model_id,  # Dynamic model from switchboard
                temperature=self.temperature,
            )

            # PHASE 4 — BUDGET TRACKING: Track token usage
            # Note: Some providers (OpenRouter) don't return usage in streaming mode
            if hasattr(response, 'usage') and response.usage:
                from jagabot.core.token_budget import budget
                # Handle both dict and object usage formats
                usage = response.usage
                if isinstance(usage, dict):
                    input_tokens = usage.get('prompt_tokens', 0)
                    output_tokens = usage.get('completion_tokens', 0)
                else:
                    input_tokens = getattr(usage, 'prompt_tokens', 0)
                    output_tokens = getattr(usage, 'completion_tokens', 0)
                budget_result = budget.record(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    model=getattr(response, 'model', self._current_model_id),
                    messages=messages,  # For checkpoint on budget exceeded
                    workspace=self.workspace,
                    interactive=True,  # Enable interactive budget handling
                )
                
                # Handle interactive budget exceeded
                if budget_result == "BUDGET_EXCEEDED_ASK_USER":
                    logger.warning("⚠️  Session budget exceeded — pausing for user decision")
                    # Save checkpoint and return control to user
                    from jagabot.core.session_checkpoint import save_checkpoint
                    save_checkpoint(messages, self._calls, self.workspace)
                    
                    # Return message to user asking what to do
                    return self.context.add_assistant_message(
                        messages,
                        "⚠️ **Session budget exceeded.**\n\n"
                        "Checkpoint saved. Please choose:\n"
                        "1. Continue this session (budget override) — just continue typing\n"
                        "2. Start new session — use `/new`\n"
                        "3. Check budget — use `/budget status`\n"
                        "4. Set higher budget — use `jagabot budget set-session <tokens>`\n\n"
                        "Your conversation is saved. Type anything to continue or use a command.",
                    )
            else:
                # No usage data — skip budget tracking for this turn
                logger.debug("Budget tracking: no usage data from provider (streaming mode?)")

            if response.has_tool_calls:
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                )

                for tool_call in response.tool_calls:
                    tools_used.append(tool_call.name)
                    args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                    logger.info(f"Tool call: {tool_call.name}({args_str[:200]})")

                    # Duplicate command detection (reduced threshold: 2 -> block on 3rd)
                    cmd_key = f"{tool_call.name}:{hash(args_str)}"
                    _duplicate_commands[cmd_key] = _duplicate_commands.get(cmd_key, 0) + 1
                    if _duplicate_commands[cmd_key] >= 2:
                        result = (
                            f"🛑 DUPLICATE COMMAND BLOCKED: You have run '{tool_call.name}' "
                            f"with identical arguments {_duplicate_commands[cmd_key]} times. "
                            f"This is not advancing the task.\n\n"
                            f"REQUIRED: Read the relevant source file(s), analyze the error, "
                            f"and propose a DIFFERENT approach. Do NOT re-run the same command.\n"
                            f"Available tools: {', '.join(t['function']['name'] for t in self.tools.get_definitions())}"
                        )
                        logger.warning(f"Duplicate command blocked: {tool_call.name} x{_duplicate_commands[cmd_key]}")
                        messages = self.context.add_tool_result(
                            messages, tool_call.id, tool_call.name, result,
                        )
                        continue

                    # RepetitionGuard — prevent same tool call with same args
                    if self.rep_guard.is_repeat(tool_call.name, tool_call.arguments):
                        cached = self.rep_guard.get_cached(tool_call.name, tool_call.arguments)
                        logger.debug(f"RepetitionGuard: skipping repeat {tool_call.name}")
                        # Return cached result instead of re-executing
                        messages = self.context.add_tool_result(
                            messages, tool_call.id, tool_call.name, cached,
                        )
                        continue

                    # BDI Phase 2: reset belief tracking at start of first tool call
                    if len(tools_used) == 1 and self.bdi_tracker:
                        self.bdi_tracker.reset_turn()

                    h_id = self.harness.register(tool_call.name)

                    if _consecutive_failures.get(tool_call.name, 0) >= _MAX_TOOL_RETRIES:
                        result = (
                            f"Error: Tool '{tool_call.name}' has failed {_MAX_TOOL_RETRIES} "
                            f"times consecutively. It may not exist or be misconfigured. "
                            f"Use a different approach or available tools: "
                            f"{', '.join(t['function']['name'] for t in self.tools.get_definitions())}"
                        )
                        logger.warning(f"Circuit breaker tripped for tool {tool_call.name}")
                        self.harness.fail(h_id, "circuit breaker")
                        result = f"Error: Circuit breaker tripped for tool '{tool_call.name}'"
                        if self.bdi_tracker:
                            self.bdi_tracker.record_belief_update(
                                tool_name=tool_call.name,
                                success=False,
                                circuit_breaker=True,
                            )
                            self.bdi_tracker.record_desire_challenge(
                                tool_name=tool_call.name,
                                challenge_type="circuit_breaker",
                                alternatives_suggested=True,
                            )
                    else:
                        result = await self.tools.execute(tool_call.name, tool_call.arguments)

                        if isinstance(result, str) and result.startswith("Error"):
                            logger.warning(f"Tool {tool_call.name} failed, retrying once")
                            if self.bdi_tracker:
                                self.bdi_tracker.record_belief_update(
                                    tool_name=tool_call.name,
                                    success=False,
                                    error_message=result[:100],
                                )
                                self.bdi_tracker.record_desire_challenge(
                                    tool_name=tool_call.name,
                                    challenge_type="tool_error",
                                    persisting=True,
                                )
                            result = await self.tools.execute(
                                tool_call.name, tool_call.arguments,
                            )

                        # Record harness status and build result message
                        if isinstance(result, str) and result.startswith("Error"):
                            self.harness.fail(h_id, result[:200])
                        else:
                            result_str = str(result) if result else ""
                            self.harness.complete(h_id, result_text=result_str)
                            if self.bdi_tracker:
                                self.bdi_tracker.record_belief_update(
                                    tool_name=tool_call.name,
                                    success=True,
                                )
                                # Check if this was a recovery (tool previously failed)
                                if _consecutive_failures.get(tool_call.name, 0) > 0:
                                    self.bdi_tracker.record_desire_challenge(
                                        tool_name=tool_call.name,
                                        challenge_type="recovered",
                                        success_after_failure=True,
                                    )
                            # Record in RepetitionGuard for caching
                            self.rep_guard.record(tool_call.name, tool_call.arguments, result_str)

                            # Phase 1 — Trajectory Monitor: record tool call
                            self.trajectory_monitor.on_tool_called(tool_call.name)

                    # Track consecutive failures and inject error analysis prompt
                    if isinstance(result, str) and result.startswith("Error"):
                        _consecutive_failures[tool_call.name] = (
                            _consecutive_failures.get(tool_call.name, 0) + 1
                        )
                        
                        # Inject mandatory error analysis prompt for failed tools
                        error_analysis_prompt = (
                            f"\n\n⚠️ ERROR ANALYSIS REQUIRED BEFORE RETRY:\n"
                            f"Tool '{tool_call.name}' failed. BEFORE running it again:\n"
                            f"1. READ the relevant source file(s) using read_file\n"
                            f"2. ANALYZE the error traceback (note line numbers and file paths)\n"
                            f"3. EXPLAIN why the error occurred in your own words\n"
                            f"4. PROPOSE and EXECUTE a specific fix (edit code, adjust data, or change approach)\n"
                            f"5. DO NOT re-run the same command without making changes first\n"
                        )
                        result = result + error_analysis_prompt
                    else:
                        _consecutive_failures[tool_call.name] = 0

                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result,
                    )

                    # Record in causal tracer for cause-effect verification
                    self.auditor.causal_tracer.record(
                        tool_call.name, args_str[:200],
                        str(result)[:2048] if result else "",
                    )
            else:
                # If the assistant produced prose that describes actions it will
                # perform (e.g., "I will run X", "Starting Y", or mentioning
                # a tool name), but DID NOT emit structured tool_calls, we should
                # request a strict JSON plan and execute it so the runtime does
                # the promised work instead of only describing it.
                content_lower = (response.content or "").lower()
                
                # Exclusion phrases - if present, don't trigger plan execution
                exclusion_phrases = [
                    "summary", "summarize", "summarise",
                    "what did", "what was", "what is",
                    "show me", "list", "display",
                    "tell me", "explain", "report",
                    "how many", "count",
                ]
                is_summary_request = any(p in content_lower for p in exclusion_phrases)
                
                plan_phrases = [
                    "i will", "i'll", "i will now", "i will proceed", "i will run",
                    "i will execute", "starting", "started", "will start", "will begin",
                    "please run", "please execute", "i will now do", "i will do",
                ]

                tool_defs = self.tools.get_definitions()
                tool_names = [d["function"]["name"].lower() for d in tool_defs]
                mentions_tool = any(tn in content_lower for tn in tool_names)

                # Only trigger plan execution if it mentions action phrases AND tool names
                # but NOT if it's a summary/query request
                wants_to_act = (any(p in content_lower for p in plan_phrases) and mentions_tool) and not is_summary_request

                if not wants_to_act:
                    # No explicit plan-like language or tool names — return the text
                    final_content = response.content
                    break

                # If spawn tool was used this turn, don't retry — subagents are running
                if "spawn" in tools_used:
                    logger.info("Spawn tool used — skipping JSON plan retry, subagents running")
                    final_content = response.content
                    break

                logger.info("Assistant returned plan-like text without tool_calls; requesting executable JSON plan")

                plan_request = (
                    "Please respond ONLY with a JSON array (no prose). Each item must be "
                    "an object with keys: \"tool\" (string) and \"args\" (object). "
                    "IMPORTANT: Do NOT use brace expansion like {a,b,c} - use separate commands instead."
                    "Example: [{\"tool\":\"exec\",\"args\":{\"command\":\"mkdir -p /root/.jagabot/workspace/tools\"}}, {\"tool\":\"exec\",\"args\":{\"command\":\"mkdir -p /root/.jagabot/workspace/analysis\"}}]"
                )

                messages.append({"role": "user", "content": plan_request})

                try:
                    plan_resp = await self.provider.chat(
                        messages=messages,
                        tools=[],  # no tools — force a JSON/plain-text reply
                        model=self.model,
                        temperature=self.temperature,
                    )
                    plan_text = (plan_resp.content or "").strip()
                except Exception as exc:
                    logger.warning(f"Plan extraction call failed: {exc}")
                    # Fall back to returning the assistant's original prose
                    break

                plan_json = None
                try:
                    m = re.search(r"(\[.*\])", plan_text, flags=re.DOTALL)
                    json_str = m.group(1) if m else plan_text
                    if json_str.startswith("```"):
                        json_str = json_str.strip('`\n')
                    plan_json = json.loads(json_str)
                except Exception as exc:
                    logger.warning(f"Could not parse plan JSON: {exc}; plan_text={plan_text[:200]!r}")
                    break

                if not isinstance(plan_json, list):
                    logger.warning("Plan JSON is not a list; ignoring and returning assistant text")
                    break

                # Execute each action in the plan deterministically
                execution_results = []
                for idx, action in enumerate(plan_json):
                    if not isinstance(action, dict) or "tool" not in action:
                        logger.warning(f"Skipping invalid plan entry at index {idx}: {action}")
                        continue
                    tool_name = action["tool"]
                    args = action.get("args", {}) or {}

                    tools_used.append(tool_name)

                    h_id = self.harness.register(tool_name)

                    try:
                        result = await self.tools.execute(tool_name, args)

                        # Retry once on simple string error
                        if isinstance(result, str) and result.startswith("Error"):
                            logger.warning(f"Tool {tool_name} failed, retrying once")
                            result = await self.tools.execute(tool_name, args)

                        if isinstance(result, str) and result.startswith("Error"):
                            self.harness.fail(h_id, result[:200])
                            result_str = result
                        else:
                            result_str = str(result) if result is not None else ""
                            self.harness.complete(h_id, result_text=result_str)
                    except Exception as exc:
                        err = f"Error executing tool {tool_name}: {exc}"
                        logger.exception(err)
                        self.harness.fail(h_id, str(exc)[:200])
                        result_str = err

                    # Store result for summary
                    execution_results.append((tool_name, args, result_str))

                    # Synthesize an assistant message declaring the tool call
                    # (providers expect a preceding assistant tool_calls entry)
                    tool_call_id = f"plan:auto:{int(time.time()*1000)}:{idx}"
                    try:
                        tool_call_dict = {
                            "id": tool_call_id,
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": json.dumps(args, ensure_ascii=False),
                            },
                        }
                        messages = self.context.add_assistant_message(messages, content="", tool_calls=[tool_call_dict])
                    except Exception:
                        logger.debug("Failed to add synthetic assistant tool_calls message; proceeding to attach tool result")

                    # Append the tool result message (valid since assistant message was added)
                    messages = self.context.add_tool_result(messages, tool_call_id, tool_name, result_str)

                    # Record causal tracer entry
                    try:
                        self.auditor.causal_tracer.record(tool_name, json.dumps(args)[:200], result_str[:2048])
                    except Exception:
                        logger.debug("Causal tracer record failed for plan action")

                # After executing the plan actions, generate a natural summary
                summary_lines = []
                for tool_name, args, result_str in execution_results:
                    if tool_name in ("write_file", "create_file", "save_file"):
                        path = args.get("path", "unknown")
                        summary_lines.append(f"✅ Created {path}")
                    elif tool_name == "read_file":
                        path = args.get("path", "unknown")
                        summary_lines.append(f"📄 Read {path}")
                    elif tool_name == "exec":
                        cmd = args.get("command", "")[:60]
                        summary_lines.append(f"⚙️ Executed: {cmd}...")
                    elif tool_name == "list_dir":
                        path = args.get("path", "unknown")
                        summary_lines.append(f"📁 Listed {path}")
                    else:
                        summary_lines.append(f"✅ {tool_name} completed")
                    
                    # Include important result content (not JSON)
                    if result_str and tool_name not in ("write_file", "create_file", "save_file"):
                        # Show result for read operations
                        if len(result_str) < 500:
                            summary_lines.append(f"```\n{result_str}\n```")
                        else:
                            summary_lines.append(f"```\n{result_str[:500]}...\n```")

                final_content = "\n".join(summary_lines) if summary_lines else "✅ Task completed."

                # We have executed the promised actions — exit loop
                break

        if final_content is None:
            if iteration >= max_iterations and tools_used:
                # Agent did real work but ran out of iterations before producing
                # a text response.  Make one final no-tools call to get a summary.
                logger.info(
                    f"Iteration limit ({max_iterations}) hit with {len(tools_used)} "
                    f"tool calls — requesting final summary"
                )
                messages.append({
                    "role": "user",
                    "content": (
                        "You have reached the iteration limit. Summarise what you "
                        "accomplished so far based on the tool results above. "
                        "Do NOT call any more tools — just reply with a text summary."
                    ),
                })
                try:
                    summary_resp = await self.provider.chat(
                        messages=messages,
                        tools=[],  # no tools — force text response
                        model=self.model,
                        temperature=self.temperature,
                    )
                    final_content = summary_resp.content or (
                        f"Completed {len(tools_used)} tool operations but could not "
                        f"generate a summary."
                    )
                except Exception as exc:
                    logger.warning(f"Summary call failed: {exc}")
                    final_content = (
                        f"Completed {len(tools_used)} tool operations. "
                        f"Tools used: {', '.join(dict.fromkeys(tools_used))}."
                    )
            elif iteration >= max_iterations:
                final_content = f"Reached {max_iterations} iterations without completion."
            else:
                final_content = "I've completed processing but have no response to give."

        return messages, final_content, tools_used

    async def _process_system_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a system message (e.g., subagent announce).

        The chat_id field contains "original_channel:original_chat_id" to route
        the response back to the correct destination.
        
        TEST 4 FIX: If subagent verification failed, escalate to quad-agent or
        re-run with direct tools.
        """
        logger.info(f"Processing system message from {msg.sender_id}")

        # Parse origin from chat_id (format: "channel:chat_id")
        if ":" in msg.chat_id:
            parts = msg.chat_id.split(":", 1)
            origin_channel = parts[0]
            origin_chat_id = parts[1]
        else:
            # Fallback — log so we can trace misrouted results
            logger.warning(
                f"System message from '{msg.sender_id}' has no ':' in chat_id '{msg.chat_id}' — "
                "falling back to cli channel. Result may be routed to wrong session."
            )
            origin_channel = "cli"
            origin_chat_id = msg.chat_id

        # Use the origin session for context
        session_key = f"{origin_channel}:{origin_chat_id}"
        session = self.sessions.get_or_create(session_key)

        # Check if this is a subagent verification failure
        is_verification_failure = (
            msg.sender_id == "subagent" and
            "SUBAGENT VERIFICATION FAILURE" in (msg.content or "")
        )

        if is_verification_failure:
            # Extract the original task from the message
            # Message format: "[Subagent 'label' failed]\n\nTask: {task}\n\nResult: ..."
            import re
            task_match = re.search(r'Task:\s*(.+?)(?=\n\nResult:|$)', msg.content, re.DOTALL)
            original_task = task_match.group(1).strip() if task_match else "Unknown task"
            
            logger.error(f"Subagent verification failure detected. Re-running with direct tools: {original_task}")
            
            # Re-run the task using direct tool calls (not subagent)
            messages = self.context.build_messages(
                history=session.get_history(),
                current_message=(
                    f"⚠️ SUBAGENT FAILED - Use DIRECT TOOLS:\n"
                    f"The subagent claimed to complete this task but files were not created:\n\n"
                    f"Original task: {original_task}\n\n"
                    f"IMPORTANT: Do NOT use spawn/subagent. Use write_file, exec, and other tools DIRECTLY.\n"
                    f"After each file creation, VERIFY it exists before proceeding.\n\n"
                    f"{msg.content}"
                ),
                channel=origin_channel,
                chat_id=origin_chat_id,
            )
            
            # Run agent loop with tools to actually create the files
            messages, final_content, tools_used = await self._run_agent_loop(messages, max_iterations=15)
            
            # Verify files after direct execution
            if tools_used:
                # Check harness for any remaining missing files
                auditor_result = self.auditor.audit(final_content, tools_used, attempt=0, messages=messages)
                if not auditor_result.approved:
                    final_content = (
                        f"⚠️ DIRECT TOOL EXECUTION ALSO FAILED:\n"
                        f"{auditor_result.feedback}\n\n"
                        f"Please try again with simpler, step-by-step commands."
                    )
            
            # Save session and send result
            session.add_message("system", msg.content)
            session.add_message("assistant", final_content, tools_used=tools_used if tools_used else None)
            self.sessions.save(session)
            
            return OutboundMessage(
                channel=origin_channel,
                chat_id=origin_chat_id,
                content=final_content or "Task re-executed with direct tools."
            )

        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(origin_channel, origin_chat_id)
        
        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(origin_channel, origin_chat_id)
        
        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(origin_channel, origin_chat_id)
        
        # Build messages with the announce content
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            channel=origin_channel,
            chat_id=origin_chat_id,
        )
        
        # Agent loop (limited for announce handling)
        iteration = 0
        final_content = None
        _sys_consecutive_failures: dict[str, int] = {}
        
        while iteration < self.max_iterations:
            iteration += 1
            
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model,
                temperature=self.temperature
            )
            
            if response.has_tool_calls:
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                )
                
                for tool_call in response.tool_calls:
                    args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                    logger.info(f"Tool call: {tool_call.name}({args_str[:200]})")

                    if _sys_consecutive_failures.get(tool_call.name, 0) >= 3:
                        result = (
                            f"Error: Tool '{tool_call.name}' has failed 3 times. "
                            f"Use a different tool or respond without it."
                        )
                        logger.warning(f"Circuit breaker tripped for tool {tool_call.name}")
                    else:
                        result = await self.tools.execute(tool_call.name, tool_call.arguments)

                    if isinstance(result, str) and result.startswith("Error"):
                        _sys_consecutive_failures[tool_call.name] = _sys_consecutive_failures.get(tool_call.name, 0) + 1
                    else:
                        _sys_consecutive_failures[tool_call.name] = 0

                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                final_content = response.content
                break
        
        if final_content is None:
            final_content = "Background task completed."
        
        # Save to session (mark as system message in history)
        session.add_message("user", f"[System: {msg.sender_id}] {msg.content}")
        session.add_message("assistant", final_content)
        self.sessions.save(session)
        
        return OutboundMessage(
            channel=origin_channel,
            chat_id=origin_chat_id,
            content=final_content
        )
    
    async def _consolidate_memory(self, session, archive_all: bool = False) -> None:
        """Consolidate old messages into MEMORY.md + HISTORY.md, then trim session."""
        if not session.messages:
            return
        memory = MemoryStore(self.workspace)
        if archive_all:
            old_messages = session.messages
            keep_count = 0
        else:
            keep_count = min(10, max(2, self.memory_window // 2))
            old_messages = session.messages[:-keep_count]
        if not old_messages:
            return
        logger.info(f"Memory consolidation started: {len(session.messages)} messages, archiving {len(old_messages)}, keeping {keep_count}")

        # Format messages for LLM (include tool names when available)
        lines = []
        for m in old_messages:
            if not m.get("content"):
                continue
            # Fix: content may be dict/list from tool responses
            content = m.get("content", "")
            if isinstance(content, (dict, list)):
                import json
                content = json.dumps(content, default=str)[:500]
            elif not isinstance(content, str):
                content = str(content)[:500]
            tools = f" [tools: {', '.join(m['tools_used'])}]" if m.get("tools_used") else ""
            lines.append(f"[{m.get('timestamp', '?')[:16]}] {m['role'].upper()}{tools}: {content}")
        conversation = "\n".join(lines)
        current_memory = memory.read_long_term()

        prompt = f"""You are a memory consolidation agent. Process this conversation and return a JSON object with exactly two keys:

1. "history_entry": A SHORT paragraph (2-3 sentences MAX, under 200 words) summarizing the key events/decisions. Start with a timestamp like [YYYY-MM-DD HH:MM].

2. "memory_update": The updated long-term memory content. Keep it concise. Add any new facts: user preferences, project context, technical decisions. If nothing new, return the existing content unchanged.

IMPORTANT: Keep your response SHORT. Do not write long summaries. Total response must be under 500 tokens.

## Current Long-term Memory
{current_memory or "(empty)"}

## Conversation to Process
{conversation}

Respond with ONLY valid JSON, no markdown fences."""

        def _parse_consolidation_response(text: str) -> dict:
            """
            Robustly extract the JSON object from an LLM response.
            Handles markdown fences (``` and ```json), partial wrapping, and
            unterminated strings by falling back to regex extraction.
            """
            text = text.strip()
            # Strip ```json ... ``` or ``` ... ``` fences
            fence_match = re.match(r"^```(?:json)?\s*\n?(.*?)```\s*$", text, re.DOTALL)
            if fence_match:
                text = fence_match.group(1).strip()
            # Try direct parse first
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
            # Fallback: extract the outermost {...} block
            brace_match = re.search(r"\{.*\}", text, re.DOTALL)
            if brace_match:
                try:
                    return json.loads(brace_match.group(0))
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"Could not parse JSON from LLM response: {text[:200]!r}")

        async def _call_consolidation_llm(prompt_text: str) -> dict:
            response = await self.provider.chat(
                messages=[
                    {"role": "system", "content": "You are a memory consolidation agent. Respond only with valid JSON, no markdown fences. Keep response under 500 tokens."},
                    {"role": "user", "content": prompt_text},
                ],
                model=self.model,
                max_tokens=1024,
            )
            return _parse_consolidation_response(response.content or "")

        try:
            try:
                result = await _call_consolidation_llm(prompt)
            except (ValueError, Exception) as first_err:
                logger.warning(f"Memory consolidation first attempt failed ({first_err}), retrying with strict prompt")
                strict_prompt = (
                    "Return ONLY a raw JSON object with exactly two string keys: "
                    "\"history_entry\" and \"memory_update\". No markdown, no explanation.\n\n"
                    + prompt
                )
                result = await _call_consolidation_llm(strict_prompt)

            if entry := result.get("history_entry"):
                memory.append_history(entry)
            if update := result.get("memory_update"):
                if update != current_memory:
                    memory.write_long_term(update)

            session.messages = session.messages[-keep_count:] if keep_count else []
            self.sessions.save(session)
            logger.info(f"Memory consolidation done, session trimmed to {len(session.messages)} messages")
        except Exception as e:
            logger.error(f"Memory consolidation failed: {e}")
            # Fallback: still trim session and write a minimal history entry so
            # the agent doesn't get stuck in an ever-growing context.
            try:
                memory.append_history(
                    f"[{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}] "
                    f"(Memory consolidation failed — {len(old_messages)} messages archived without summary. Error: {e})"
                )
                session.messages = session.messages[-keep_count:] if keep_count else []
                self.sessions.save(session)
                logger.info("Memory consolidation fallback: session trimmed, placeholder history entry written")
            except Exception as fallback_err:
                logger.error(f"Memory consolidation fallback also failed: {fallback_err}")

    def _detect_topic(self, text: str) -> str:
        """Detect topic/domain from text for reliability scoring."""
        text_lower = text.lower()
        if any(w in text_lower for w in ["stock", "portfolio", "risk", "margin", "financial", "var", "cvar"]):
            return "financial"
        elif any(w in text_lower for w in ["research", "study", "hypothesis", "experiment", "paper"]):
            return "research"
        elif any(w in text_lower for w in ["code", "software", "engineering", "api", "python"]):
            return "engineering"
        elif any(w in text_lower for w in ["health", "medical", "drug", "clinical", "patient"]):
            return "healthcare"
        elif any(w in text_lower for w in ["calibration", "confidence", "brier", "forecast"]):
            return "calibration"
        return "general"

    def _auto_evaluate(
        self,
        content: str,
        query: str,
        topic: str,
    ) -> dict:
        """
        Lightweight post-response evaluation.
        Checks for common issues without requiring historical predictions.
        
        Returns dict with:
            - issues: list of issue strings (empty if none)
            - score: overall quality score 0-1
            - topic: detected topic
        """
        issues = []
        score = 1.0
        
        # Check for hedging language (too much uncertainty)
        hedge_count = sum(1 for w in ["might", "could", "possibly", "uncertain", "may"] if w in content.lower())
        if hedge_count > 5:
            issues.append(f"Excessive hedging ({hedge_count} instances) — consider being more decisive")
            score -= 0.1
        
        # Check for unsupported claims
        if any(w in content.lower() for w in ["clearly", "obviously", "definitely"]) and topic in ("financial", "healthcare"):
            issues.append("Strong claims in high-stakes domain — verify with sources")
            score -= 0.15
        
        # Check for missing citations in research
        if topic == "research" and "source" not in content.lower() and "citation" not in content.lower():
            if len(content) > 300:  # Long research response without sources
                issues.append("Research response lacks source citations")
                score -= 0.1
        
        # Check for code without verification
        if topic == "engineering" and "def " in content and "test" not in content.lower():
            issues.append("Code provided without test verification")
            score -= 0.05
        
        # Check for financial claims without numbers
        if topic == "financial":
            has_numbers = any(c.isdigit() for c in content)
            if not has_numbers and len(content) > 200:
                issues.append("Financial analysis lacks quantitative support")
                score -= 0.15
        
        # Clamp score
        score = max(0.0, min(1.0, score))
        
        return {
            "issues": issues,
            "score": round(score, 2),
            "topic": topic,
            "query": query[:100],
        }

    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        max_iterations: int | None = None,
    ) -> str:
        """
        Process a message directly (for CLI or cron usage).
        
        Args:
            content: The message content.
            session_key: Session identifier (overrides channel:chat_id for session lookup).
            channel: Source channel (for tool context routing).
            chat_id: Source chat ID (for tool context routing).
            max_iterations: Override the default max iterations for this call.
        
        Returns:
            The agent's response.
        """
        msg = InboundMessage(
            channel=channel,
            sender_id="user",
            chat_id=chat_id,
            content=content
        )
        
        # Temporarily override max_iterations if requested
        original_max = self.max_iterations
        if max_iterations is not None:
            self.max_iterations = max_iterations
        try:
            response = await self._process_message(msg, session_key=session_key)
        finally:
            self.max_iterations = original_max
        return response.content if response else ""
