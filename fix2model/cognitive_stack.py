# jagabot/core/cognitive_stack.py
"""
CognitiveStack — Two-tier model architecture for AutoJaga.

Based on GPT's architectural input + our existing routing rules.

The upgrade from ModelSwitchboard:
  Before: pattern matching decides model before LLM call
  After:  Model 1 (mini) CLASSIFIES the task first,
          then either handles it directly OR
          escalates to Model 2 (4o) for planning,
          then Model 1 executes the plan steps

Flow:
  User request
       ↓
  Model 1: classify complexity (fast, cheap, ~100 tokens)
       ↓
  Simple?  → Model 1 answers directly
  Complex? → Model 2 produces structured plan
               ↓
             Model 1 executes each plan step
               ↓
             Validator checks output
               ↓
             Problem? → escalate to Model 2 for repair
                          ↓
                        new plan → Model 1 executes again

This saves 70-90% of Model 2 tokens vs current approach
because Model 2 only produces PLANS, not full answers.
Model 1 does all the actual execution work.

AutoJaga integration:
  CognitiveStack REPLACES the simple ModelSwitchboard routing.
  FluidDispatcher still runs first (tool/engine selection).
  CognitiveStack then handles model tier decision.

Wire into loop.py __init__:
    from jagabot.core.cognitive_stack import CognitiveStack
    self.cognitive_stack = CognitiveStack(
        workspace        = workspace,
        config_path      = config_path,
        calibration_mode = config.get("calibration_mode", False),
    )

Wire into loop.py _process_message:
    result = await self.cognitive_stack.process(
        query        = msg.content,
        profile      = harness_package.profile,
        context      = system_prompt,
        tools        = harness_package.tools,
        agent_runner = self,
    )
    final_content = result.output
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

from loguru import logger


# ── Complexity levels ─────────────────────────────────────────────────
class Complexity:
    SIMPLE   = "simple"    # Model 1 handles directly
    COMPLEX  = "complex"   # Model 2 plans, Model 1 executes
    CRITICAL = "critical"  # Model 2 handles entirely (calibration)


# ── Task plan from Model 2 ────────────────────────────────────────────
@dataclass
class TaskPlan:
    """
    Structured plan produced by Model 2.
    Model 1 executes each step.
    """
    steps:      list[str]
    reasoning:  str   = ""
    confidence: float = 0.8
    model_used: str   = ""


@dataclass
class StackResult:
    """Result from CognitiveStack.process()."""
    output:          str
    complexity:      str
    model1_calls:    int   = 0
    model2_calls:    int   = 0
    plan_steps:      int   = 0
    escalated:       bool  = False
    repaired:        bool  = False
    total_tokens:    int   = 0
    elapsed_ms:      float = 0.0


# ── Classification prompt ─────────────────────────────────────────────
CLASSIFIER_PROMPT = """Classify this task. Reply with JSON only.

SIMPLE tasks (handle directly, no deep reasoning needed):
- Factual lookup from memory or files
- Formatting or summarizing existing content  
- File read/write/list operations
- Status reporting
- Simple calculations with known formula
- Acknowledgements and control commands

COMPLEX tasks (need planning and reasoning):
- Multi-step research or analysis
- Synthesizing multiple sources
- Planning a sequence of actions
- Debugging or diagnosing problems
- Comparing options with tradeoffs
- Cross-domain reasoning

CRITICAL tasks (calibration — always Model 2 full):
- Recording verdicts (confirmed/wrong/inconclusive)
- Calibration data writes (k1_bayesian, brier_scorer)
- Self-modification (AGENTS.md, evolution, solidify)
- tri_agent or quad_agent calls

Task: {query}

Reply with exactly:
{{"complexity": "simple"|"complex"|"critical",
  "reason": "one sentence why",
  "confidence": 0.0-1.0}}"""


PLANNER_PROMPT = """You are a planning model. Produce a structured execution plan.

DO NOT answer the question directly.
ONLY produce a list of concrete steps for an executor to follow.

Task: {query}
Context: {context}

Reply with exactly:
{{"task_plan": ["step 1", "step 2", ...],
  "reasoning": "why these steps",
  "confidence": 0.0-1.0}}

Keep steps concrete and specific. Maximum 6 steps."""


REPAIR_PROMPT = """An execution step failed. Diagnose and produce a repair plan.

Original task: {query}
Failed step: {failed_step}
Error: {error}
Previous output: {previous_output}

Produce a repair plan:
{{"repair_steps": ["step 1", "step 2", ...],
  "diagnosis": "what went wrong and why",
  "confidence": 0.0-1.0}}"""


CONFIDENCE_GATE_PROMPT = """Review this output and assess confidence.

Task: {query}
Output: {output}

Reply with:
{{"confidence": 0.0-1.0,
  "issues": ["issue 1", ...] or [],
  "needs_escalation": true|false}}"""


class CognitiveStack:
    """
    Two-tier cognitive architecture for AutoJaga.

    Tier 1 (Model 1 = mini):
      - Classifies every task
      - Executes simple tasks directly
      - Executes plan steps from Model 2
      - Runs confidence gate validation

    Tier 2 (Model 2 = 4o):
      - Plans complex tasks (structured output only)
      - Diagnoses failures and produces repair plans
      - Handles critical calibration tasks fully
      - Never executes routine steps

    Key insight from GPT:
      Model 2 outputs PLANS not ANSWERS.
      Model 1 does all the actual work.
      This saves 70-90% of expensive tokens.
    """

    CONFIDENCE_THRESHOLD = 0.70   # below this → escalate to Model 2
    MAX_REPAIR_ATTEMPTS  = 2

    def __init__(
        self,
        workspace:        Path,
        config_path:      Path   = None,
        calibration_mode: bool   = False,
        model1_id:        str    = "gpt-4o-mini",
        model2_id:        str    = "gpt-4o",
        on_escalate:      Callable = None,  # callback for UI
    ) -> None:
        self.workspace        = Path(workspace)
        self.config_path      = config_path
        self.calibration_mode = calibration_mode
        self.model1_id        = model1_id
        self.model2_id        = model2_id
        self.on_escalate      = on_escalate
        self._session_log:    list[dict] = []
        self._load_models_from_config()

    # ── Public API ────────────────────────────────────────────────────

    async def process(
        self,
        query:        str,
        profile:      str    = "SAFE_DEFAULT",
        context:      str    = "",
        tools:        set    = None,
        agent_runner: object = None,
    ) -> StackResult:
        """
        Main entry point. Routes through cognitive stack.

        Flow:
          1. Model 1 classifies complexity
          2a. Simple → Model 1 handles directly
          2b. Complex → Model 2 plans → Model 1 executes steps
          2c. Critical → Model 2 handles entirely
          3. Confidence gate (Model 1 validates output)
          4. If confidence low → escalate to Model 2
        """
        t_start     = time.monotonic()
        m1_calls    = 0
        m2_calls    = 0
        escalated   = False
        repaired    = False
        plan_steps  = 0

        # Step 1: Classify (Model 1)
        complexity, classify_reason = await self._classify(
            query, profile, agent_runner
        )
        m1_calls += 1

        logger.debug(
            f"CognitiveStack: {complexity} — {classify_reason}"
        )

        # Step 2a: CRITICAL — Model 2 handles entirely
        if complexity == Complexity.CRITICAL:
            output   = await self._model2_full(
                query, context, agent_runner
            )
            m2_calls += 1
            self._log(query, complexity, m1_calls, m2_calls, 0)
            return StackResult(
                output       = output,
                complexity   = complexity,
                model1_calls = m1_calls,
                model2_calls = m2_calls,
                elapsed_ms   = (time.monotonic() - t_start) * 1000,
            )

        # Step 2b: SIMPLE — Model 1 handles directly
        if complexity == Complexity.SIMPLE:
            output   = await self._model1_execute(
                query, context, agent_runner
            )
            m1_calls += 1

            # Confidence gate
            confidence = await self._confidence_gate(
                query, output, agent_runner
            )
            m1_calls += 1

            if confidence >= self.CONFIDENCE_THRESHOLD:
                self._log(query, complexity, m1_calls, m2_calls, 0)
                return StackResult(
                    output       = output,
                    complexity   = complexity,
                    model1_calls = m1_calls,
                    model2_calls = m2_calls,
                    elapsed_ms   = (time.monotonic() - t_start) * 1000,
                )
            else:
                # Escalate to Model 2
                escalated = True
                logger.info(
                    f"CognitiveStack: escalating — "
                    f"confidence={confidence:.2f} < "
                    f"{self.CONFIDENCE_THRESHOLD}"
                )
                if self.on_escalate:
                    self.on_escalate(query, confidence)
                output   = await self._model2_full(
                    query, context, agent_runner
                )
                m2_calls += 1

        # Step 2c: COMPLEX — Model 2 plans, Model 1 executes
        else:
            # Model 2 produces structured plan
            plan     = await self._model2_plan(
                query, context, agent_runner
            )
            m2_calls += 1
            plan_steps = len(plan.steps)

            logger.debug(
                f"CognitiveStack: {plan_steps} step plan from Model 2"
            )

            # Model 1 executes each step
            step_outputs = []
            for i, step in enumerate(plan.steps, 1):
                logger.debug(
                    f"CognitiveStack: executing step {i}/{plan_steps}: "
                    f"{step[:60]}"
                )
                try:
                    step_out = await self._model1_execute(
                        f"{step}\n\n(Part of: {query})",
                        context,
                        agent_runner,
                    )
                    m1_calls += 1
                    step_outputs.append(step_out)
                except Exception as e:
                    # Step failed — escalate for repair
                    logger.warning(
                        f"CognitiveStack: step {i} failed: {e}"
                    )
                    repair = await self._model2_repair(
                        query       = query,
                        failed_step = step,
                        error       = str(e),
                        prev_output = "\n".join(step_outputs),
                        agent_runner= agent_runner,
                    )
                    m2_calls += 1
                    repaired  = True

                    # Execute repair steps
                    for r_step in repair.steps[:3]:
                        try:
                            r_out = await self._model1_execute(
                                r_step, context, agent_runner
                            )
                            m1_calls += 1
                            step_outputs.append(r_out)
                        except Exception:
                            pass
                    break

            # Synthesize step outputs into final answer (Model 1)
            output = await self._model1_synthesize(
                query, step_outputs, agent_runner
            )
            m1_calls += 1

        elapsed = (time.monotonic() - t_start) * 1000
        self._log(query, complexity, m1_calls, m2_calls, plan_steps)

        return StackResult(
            output       = output,
            complexity   = complexity,
            model1_calls = m1_calls,
            model2_calls = m2_calls,
            plan_steps   = plan_steps,
            escalated    = escalated,
            repaired     = repaired,
            elapsed_ms   = elapsed,
        )

    def get_stats(self) -> dict:
        """Return cognitive stack statistics for session."""
        if not self._session_log:
            return {"turns": 0}

        total = len(self._session_log)
        by_complexity = {}
        total_m1 = total_m2 = 0
        escalations = repairs = 0

        for s in self._session_log:
            c = s["complexity"]
            by_complexity[c] = by_complexity.get(c, 0) + 1
            total_m1   += s["m1_calls"]
            total_m2   += s["m2_calls"]

        total_calls   = total_m1 + total_m2
        m1_pct        = total_m1 / max(1, total_calls) * 100
        m2_pct        = total_m2 / max(1, total_calls) * 100

        return {
            "turns":           total,
            "by_complexity":   by_complexity,
            "total_m1_calls":  total_m1,
            "total_m2_calls":  total_m2,
            "m1_pct":          round(m1_pct),
            "m2_pct":          round(m2_pct),
            "cost_estimate":   self._estimate_cost(
                total_m1, total_m2
            ),
        }

    def format_status(self) -> str:
        """Format for /status command."""
        stats = self.get_stats()
        if stats["turns"] == 0:
            return "**CognitiveStack:** No turns yet."

        lines = [
            "**CognitiveStack**", "",
            f"Model 1 ({self.model1_id}): "
            f"{stats['total_m1_calls']} calls "
            f"({stats['m1_pct']}%)",
            f"Model 2 ({self.model2_id}): "
            f"{stats['total_m2_calls']} calls "
            f"({stats['m2_pct']}%)",
            f"Est. cost: ${stats['cost_estimate']:.4f}",
            "",
            "By complexity:",
        ]
        for c, count in stats["by_complexity"].items():
            pct = count / stats["turns"] * 100
            lines.append(f"  {c:<10} {count:>3}x ({pct:.0f}%)")

        return "\n".join(lines)

    # ── Model calls ───────────────────────────────────────────────────

    async def _classify(
        self,
        query:        str,
        profile:      str,
        agent_runner: object,
    ) -> tuple[str, str]:
        """
        Step 1: Model 1 classifies complexity.
        Fast, cheap, ~100 tokens.
        Falls back to rule-based if LLM unavailable.
        """
        # Fast rule-based pre-check (< 1ms, no LLM needed)
        complexity = self._rule_based_classify(query, profile)
        if complexity:
            return complexity, "rule_based"

        # LLM classification (Model 1)
        if not agent_runner:
            return Complexity.SIMPLE, "no_runner_fallback"

        try:
            prompt = CLASSIFIER_PROMPT.format(query=query[:200])
            response = await self._call_model(
                model        = self.model1_id,
                prompt       = prompt,
                max_tokens   = 100,
                agent_runner = agent_runner,
            )
            data = json.loads(response)
            return data["complexity"], data.get("reason", "")

        except Exception as e:
            logger.debug(f"CognitiveStack: classify failed: {e}")
            return Complexity.SIMPLE, "classify_error_fallback"

    def _rule_based_classify(
        self, query: str, profile: str
    ) -> Optional[str]:
        """
        Fast rule-based classification before LLM call.
        Handles the obvious cases without any API call.
        """
        text = query.lower().strip()

        # CRITICAL — always (from routing rules)
        critical_signals = [
            "confirmed", "wrong", "falsified",
            "inconclusive", "partially correct",
            "k1_bayesian", "brier_scorer",
            "tri_agent", "quad_agent",
        ]
        if any(s in text for s in critical_signals):
            return Complexity.CRITICAL

        # Commands that are always SIMPLE
        simple_commands = [
            "/status", "/help", "/harness", "/sessions",
            "/compress", "/clear", "/model status",
        ]
        if any(text.startswith(c) for c in simple_commands):
            return Complexity.SIMPLE

        # Commands that are always COMPLEX
        complex_commands = ["/yolo", "/research", "/idea"]
        if any(text.startswith(c) for c in complex_commands):
            return Complexity.COMPLEX

        # Profile shortcuts
        if profile in ("MAINTENANCE", "ACTION", "SAFE_DEFAULT"):
            return Complexity.SIMPLE
        if profile in ("AUTONOMOUS",):
            return Complexity.COMPLEX
        if profile == "CALIBRATION":
            return Complexity.CRITICAL

        return None  # needs LLM classification

    async def _model1_execute(
        self,
        prompt:       str,
        context:      str,
        agent_runner: object,
    ) -> str:
        """Model 1 executes a task or step."""
        if not agent_runner:
            return f"[stub] Model 1 executed: {prompt[:60]}"
        return await self._call_model(
            model        = self.model1_id,
            prompt       = prompt,
            context      = context,
            max_tokens   = 1500,
            agent_runner = agent_runner,
        )

    async def _model1_synthesize(
        self,
        original_query: str,
        step_outputs:   list[str],
        agent_runner:   object,
    ) -> str:
        """Model 1 synthesizes step outputs into final answer."""
        if not step_outputs:
            return "No steps completed."

        combined = "\n\n".join(
            f"Step {i+1}: {out[:400]}"
            for i, out in enumerate(step_outputs)
        )
        prompt = (
            f"Synthesize these step results into a final answer.\n\n"
            f"Original question: {original_query}\n\n"
            f"Step results:\n{combined}\n\n"
            f"Final answer:"
        )
        return await self._model1_execute(
            prompt, "", agent_runner
        )

    async def _model2_plan(
        self,
        query:        str,
        context:      str,
        agent_runner: object,
    ) -> TaskPlan:
        """
        Model 2 produces a structured plan.
        Does NOT produce the final answer — only a plan.
        This is the key insight from GPT.
        """
        if not agent_runner:
            return TaskPlan(
                steps=[f"Execute: {query[:80]}"],
                reasoning="stub plan"
            )

        try:
            prompt = PLANNER_PROMPT.format(
                query   = query[:300],
                context = context[:500],
            )
            response = await self._call_model(
                model        = self.model2_id,
                prompt       = prompt,
                max_tokens   = 400,
                agent_runner = agent_runner,
            )
            data = json.loads(response)
            return TaskPlan(
                steps      = data.get("task_plan", [query]),
                reasoning  = data.get("reasoning", ""),
                confidence = data.get("confidence", 0.8),
                model_used = self.model2_id,
            )
        except Exception as e:
            logger.debug(f"CognitiveStack: plan failed: {e}")
            return TaskPlan(
                steps     = [query],
                reasoning = f"plan_error: {e}",
            )

    async def _model2_full(
        self,
        query:        str,
        context:      str,
        agent_runner: object,
    ) -> str:
        """
        Model 2 handles task entirely.
        Used for CRITICAL tasks and low-confidence escalations.
        """
        if not agent_runner:
            return f"[stub] Model 2 handled: {query[:60]}"
        return await self._call_model(
            model        = self.model2_id,
            prompt       = query,
            context      = context,
            max_tokens   = 3000,
            agent_runner = agent_runner,
        )

    async def _model2_repair(
        self,
        query:        str,
        failed_step:  str,
        error:        str,
        prev_output:  str,
        agent_runner: object,
    ) -> TaskPlan:
        """Model 2 diagnoses failure and produces repair plan."""
        if not agent_runner:
            return TaskPlan(
                steps     = [f"Retry: {failed_step}"],
                reasoning = "stub repair"
            )
        try:
            prompt = REPAIR_PROMPT.format(
                query          = query[:200],
                failed_step    = failed_step[:200],
                error          = error[:200],
                previous_output= prev_output[:300],
            )
            response = await self._call_model(
                model        = self.model2_id,
                prompt       = prompt,
                max_tokens   = 300,
                agent_runner = agent_runner,
            )
            data = json.loads(response)
            return TaskPlan(
                steps     = data.get("repair_steps", [failed_step]),
                reasoning = data.get("diagnosis", ""),
            )
        except Exception as e:
            return TaskPlan(
                steps=[f"Retry: {failed_step}"],
                reasoning=f"repair_error: {e}"
            )

    async def _confidence_gate(
        self,
        query:        str,
        output:       str,
        agent_runner: object,
    ) -> float:
        """
        Model 1 validates its own output confidence.
        If confidence < threshold → escalate to Model 2.
        GPT: "prevents unnecessary expensive calls"
        """
        if not agent_runner or not output:
            return 1.0

        try:
            prompt = CONFIDENCE_GATE_PROMPT.format(
                query  = query[:200],
                output = output[:400],
            )
            response = await self._call_model(
                model        = self.model1_id,
                prompt       = prompt,
                max_tokens   = 100,
                agent_runner = agent_runner,
            )
            data = json.loads(response)
            return float(data.get("confidence", 0.8))
        except Exception:
            return 0.8  # default — assume acceptable

    async def _call_model(
        self,
        model:        str,
        prompt:       str,
        context:      str       = "",
        max_tokens:   int       = 1000,
        agent_runner: object    = None,
    ) -> str:
        """
        Call a specific model.
        In AutoJaga this routes through the existing LLM client
        with model_id overridden for this call only.
        """
        if not agent_runner:
            return f"[stub:{model}] {prompt[:50]}"
        try:
            # Override model for this specific call
            return await agent_runner.call_llm(
                prompt     = prompt,
                context    = context,
                model_id   = model,
                max_tokens = max_tokens,
            )
        except AttributeError:
            # Fallback: use agent's process_message with model hint
            return await agent_runner.process_message(
                content  = prompt,
                model_id = model,
            )

    # ── Helpers ───────────────────────────────────────────────────────

    def _load_models_from_config(self) -> None:
        """Load model IDs from config.json presets."""
        if not self.config_path:
            return
        try:
            config = json.loads(
                Path(self.config_path).read_text()
            )
            presets = config.get("model_presets", {})
            if "1" in presets:
                self.model1_id = presets["1"]["model_id"]
            if "2" in presets:
                self.model2_id = presets["2"]["model_id"]
            logger.debug(
                f"CognitiveStack: M1={self.model1_id} "
                f"M2={self.model2_id}"
            )
        except Exception:
            pass

    def _estimate_cost(
        self, m1_calls: int, m2_calls: int
    ) -> float:
        avg_tokens_m1 = 800   # classifier + executor calls
        avg_tokens_m2 = 400   # planner only — not full answers
        cost_m1 = m1_calls * avg_tokens_m1 / 1000 * 0.00015
        cost_m2 = m2_calls * avg_tokens_m2 / 1000 * 0.00250
        return round(cost_m1 + cost_m2, 5)

    def _log(
        self,
        query:      str,
        complexity: str,
        m1_calls:   int,
        m2_calls:   int,
        plan_steps: int,
    ) -> None:
        self._session_log.append({
            "query":      query[:60],
            "complexity": complexity,
            "m1_calls":   m1_calls,
            "m2_calls":   m2_calls,
            "plan_steps": plan_steps,
            "timestamp":  datetime.now().isoformat(),
        })
