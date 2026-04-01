# jagabot/swarm/a2a_handoff.py
"""
A2A (Agent-to-Agent) Handoff Protocol

Formalises agent handoffs using structured headers.
Solves context bloat by forcing explicit state packaging
before handing off to a fresh agent.

The key insight: instead of killing a spinning run (Phase 1),
the Trajectory Monitor can trigger a clean handoff instead.

Flow:
    Agent A fills up / gets stuck / hits trajectory limit
            ↓
    HandoffPackager.package(agent_a_state)
            ↓
    HandoffPackage: {
        intent:             "DELEGATE",
        sender_id:          "FinAgent_01",
        recipient_role:     "researcher",
        context_snapshot:   essential facts only
        negative_constraints: verified failures
        k1_prior_required:  minimum trust needed
        goal_remaining:     what still needs doing
    }
            ↓
    Agent B starts fresh with clean context
    + negative constraints carried forward
    + bloat deleted

Wire into loop.py _run_agent_loop:
    from jagabot.swarm.a2a_handoff import HandoffPackager, HandoffRouter
    self.handoff_packager = HandoffPackager(workspace, librarian)
    self.handoff_router   = HandoffRouter(tool_registry)

Wire into trajectory monitor trigger:
    if not self.trajectory_monitor.on_text_generated(text):
        # Instead of just killing — package and hand off
        package = self.handoff_packager.package(
            current_goal    = original_query,
            session_context = session_text_so_far,
            tools_used      = tools_used_so_far,
            stuck_reason    = self.trajectory_monitor.get_stats().spin_reason,
        )
        result = await self.handoff_router.route(package)
        return result
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger


# ── 2026 A2A Standard Header ──────────────────────────────────────────
# Based on the A2A protocol concept from the blueprint.
# Lightweight — no external dependencies, pure Python dataclass.

INTENT_TYPES = {
    "DELEGATE":   "Hand off to specialist agent",
    "COLLABORATE":"Work together on shared goal",
    "VERIFY":     "Ask another agent to verify result",
    "ESCALATE":   "Pass to higher-capability agent",
    "RESUME":     "Resume a previously handed-off task",
}

RECIPIENT_ROLES = {
    "researcher":   "Deep web research and synthesis",
    "analyst":      "Quantitative analysis and computation",
    "historian":    "Historical context and precedent",
    "critic":       "Adversarial review and stress-testing",
    "synthesizer":  "Combining multiple agent outputs",
    "financial":    "Financial analysis and risk",
    "ideator":      "Creative idea generation (isolated)",
}


@dataclass
class HandoffPackage:
    """
    Structured handoff between agents.
    The 'context_snapshot' is the essential distillation —
    everything the recipient needs, nothing it doesn't.
    """
    # Routing
    intent:            str              # DELEGATE | VERIFY | etc.
    sender_id:         str              # originating agent ID
    recipient_role:    str              # target specialist role
    handoff_id:        str = field(
        default_factory=lambda: str(uuid.uuid4())[:8]
    )
    timestamp:         str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    # Goal
    original_goal:     str = ""         # what the user asked for
    goal_remaining:    str = ""         # what still needs doing
    goal_completed:    str = ""         # what Agent A achieved

    # Essential context (distilled — not the full conversation)
    context_snapshot:  str = ""         # key facts from Agent A
    negative_constraints: list = field(default_factory=list)
    verified_facts:    list = field(default_factory=list)

    # Calibration requirements
    k1_prior_required: float = 0.0     # min trust score needed
    domain:            str   = "general"
    perspective_hint:  str   = ""      # suggested perspective

    # Metadata
    stuck_reason:      str   = ""      # why handoff was triggered
    tools_tried:       list  = field(default_factory=list)
    quality_so_far:    float = 0.0

    def to_dict(self) -> dict:
        return {
            "intent":              self.intent,
            "sender_id":           self.sender_id,
            "recipient_role":      self.recipient_role,
            "handoff_id":          self.handoff_id,
            "timestamp":           self.timestamp,
            "original_goal":       self.original_goal,
            "goal_remaining":      self.goal_remaining,
            "goal_completed":      self.goal_completed,
            "context_snapshot":    self.context_snapshot,
            "negative_constraints":self.negative_constraints,
            "verified_facts":      self.verified_facts,
            "k1_prior_required":   self.k1_prior_required,
            "domain":              self.domain,
            "perspective_hint":    self.perspective_hint,
            "stuck_reason":        self.stuck_reason,
            "tools_tried":         self.tools_tried,
            "quality_so_far":      self.quality_so_far,
        }

    def to_agent_prompt(self) -> str:
        """
        Convert handoff package to a clean prompt for Agent B.
        Agent B starts fresh — no access to Agent A's full context.
        Just what's in this package.
        """
        lines = [
            f"# Handoff from {self.sender_id}",
            f"**Intent:** {self.intent} — {INTENT_TYPES.get(self.intent, '')}",
            f"**Your role:** {self.recipient_role} — "
            f"{RECIPIENT_ROLES.get(self.recipient_role, '')}",
            "",
            f"## Goal",
            f"Original: {self.original_goal}",
        ]

        if self.goal_completed:
            lines += [
                "",
                f"## Already completed (do not redo):",
                self.goal_completed,
            ]

        if self.goal_remaining:
            lines += [
                "",
                f"## Your task (what remains):",
                self.goal_remaining,
            ]

        if self.context_snapshot:
            lines += [
                "",
                f"## Essential context:",
                self.context_snapshot,
            ]

        if self.verified_facts:
            lines += [
                "",
                "## Verified facts (trust these):",
            ]
            for fact in self.verified_facts[:5]:
                lines.append(f"- ✅ {fact}")

        if self.negative_constraints:
            lines += [
                "",
                "## DO NOT repeat these (verified failures):",
            ]
            for constraint in self.negative_constraints[:5]:
                lines.append(f"- ❌ {constraint}")

        if self.stuck_reason:
            lines += [
                "",
                f"## Why previous agent handed off:",
                f"{self.stuck_reason}",
                "Start fresh — don't continue the same approach.",
            ]

        if self.k1_prior_required > 0:
            lines += [
                "",
                f"## Calibration requirement:",
                f"Only proceed with approaches that have "
                f"≥{self.k1_prior_required*100:.0f}% historical "
                f"trust score.",
            ]

        lines += [
            "",
            "---",
            "Begin your work. Report results directly.",
            "Do not describe what you're about to do — just do it.",
        ]

        return "\n".join(lines)

    @classmethod
    def from_dict(cls, data: dict) -> "HandoffPackage":
        return cls(**{
            k: v for k, v in data.items()
            if k in cls.__dataclass_fields__
        })


class HandoffPackager:
    """
    Packages agent state into a clean HandoffPackage.
    
    The key operation is DISTILLATION:
    - Extract essential facts from bloated context
    - Load negative constraints from Librarian
    - Identify what's done vs what remains
    - Discard everything else
    """

    def __init__(
        self,
        workspace:  Path,
        librarian:  object = None,
        brier:      object = None,
    ) -> None:
        self.workspace = Path(workspace)
        self.librarian = librarian
        self.brier     = brier
        self._log_dir  = workspace / "memory" / "handoffs"
        self._log_dir.mkdir(parents=True, exist_ok=True)

    def package(
        self,
        current_goal:    str,
        session_context: str,
        tools_used:      list       = None,
        stuck_reason:    str        = "",
        domain:          str        = "general",
        quality_so_far:  float      = 0.0,
        sender_id:       str        = "agent_main",
    ) -> HandoffPackage:
        """
        Package current agent state for handoff.
        Distils essential information, discards bloat.
        """
        tools_used = tools_used or []

        # Determine recipient role from stuck reason + domain
        recipient = self._select_recipient(
            stuck_reason, domain, tools_used
        )

        # Distil context — extract only essential facts
        snapshot = self._distil_context(session_context)

        # Extract verified facts from context
        verified = self._extract_verified_facts(session_context)

        # Load negative constraints
        negative = []
        if self.librarian:
            try:
                constraints_text = self.librarian.get_constraints(domain)
                if constraints_text:
                    # Extract just the claim lines
                    import re
                    negative = re.findall(
                        r'DO NOT claim: "([^"]+)"',
                        constraints_text
                    )
            except Exception:
                pass

        # Determine what's done vs remaining
        completed = self._extract_completed(session_context)
        remaining = self._infer_remaining(
            current_goal, completed, stuck_reason
        )

        # Minimum trust required based on domain
        k1_prior = self._get_k1_prior(domain)

        package = HandoffPackage(
            intent             = "DELEGATE",
            sender_id          = sender_id,
            recipient_role     = recipient,
            original_goal      = current_goal[:300],
            goal_remaining     = remaining,
            goal_completed     = completed,
            context_snapshot   = snapshot,
            negative_constraints=negative[:5],
            verified_facts     = verified[:5],
            k1_prior_required  = k1_prior,
            domain             = domain,
            stuck_reason       = stuck_reason,
            tools_tried        = list(set(tools_used))[:10],
            quality_so_far     = quality_so_far,
        )

        # Log handoff
        self._log_handoff(package)

        logger.info(
            f"HandoffPackager: packaged handoff "
            f"{package.handoff_id} → {recipient} "
            f"(reason: {stuck_reason[:50]})"
        )

        return package

    # ── Distillation helpers ─────────────────────────────────────────

    def _distil_context(self, context: str, max_chars: int = 500) -> str:
        """
        Extract essential facts from bloated context.
        Keep: conclusions, results, key numbers
        Discard: reasoning chains, failed attempts, tool outputs
        """
        import re
        lines       = context.split("\n")
        essential   = []
        keep_signals = [
            "conclusion:", "result:", "finding:", "verified:",
            "✅", "key:", "important:", "→", "confirmed:",
        ]

        for line in lines:
            line_stripped = line.strip()
            if (
                len(line_stripped) > 20 and
                any(s in line.lower() for s in keep_signals)
            ):
                essential.append(line_stripped[:150])
                if sum(len(e) for e in essential) > max_chars:
                    break

        if not essential:
            # Fallback: first meaningful sentences
            sentences = re.split(r'[.!?]\s+', context)
            for s in sentences[:3]:
                if len(s.strip()) > 30:
                    essential.append(s.strip()[:150])

        return "\n".join(essential)

    def _extract_verified_facts(self, context: str) -> list[str]:
        """Extract explicitly verified facts from context."""
        import re
        facts   = []
        pattern = re.compile(
            r'(?:✅|confirmed|verified)[^\n]*\n?([^\n]{20,150})',
            re.IGNORECASE
        )
        for m in pattern.finditer(context):
            fact = m.group(1).strip()
            if fact and len(fact) > 20:
                facts.append(fact[:120])
        return facts[:5]

    def _extract_completed(self, context: str) -> str:
        """Summarise what was accomplished."""
        import re
        done_signals = ["✅", "completed", "done:", "finished:"]
        lines = [
            l.strip() for l in context.split("\n")
            if any(s in l.lower() for s in done_signals)
            and len(l.strip()) > 20
        ]
        return "; ".join(lines[:3]) if lines else ""

    def _infer_remaining(
        self,
        goal:        str,
        completed:   str,
        stuck_reason:str,
    ) -> str:
        """Infer what still needs to be done."""
        if "spinning" in stuck_reason.lower() or \
           "steps_without_tool" in stuck_reason:
            return (
                f"Complete the original goal with direct tool calls. "
                f"Goal: {goal[:100]}"
            )
        if "token" in stuck_reason.lower():
            return (
                f"Synthesise and conclude. "
                f"Goal: {goal[:100]}. "
                f"Skip further research — focus on conclusions."
            )
        return f"Continue from where previous agent stopped: {goal[:100]}"

    def _select_recipient(
        self,
        stuck_reason: str,
        domain:       str,
        tools_tried:  list,
    ) -> str:
        """Select appropriate recipient role."""
        if "web_search" in tools_tried or "researcher" in tools_tried:
            return "analyst"   # already researched — need analysis
        if domain == "financial":
            return "financial"
        if "idea" in stuck_reason.lower():
            return "ideator"
        if "verify" in stuck_reason.lower():
            return "critic"
        return "researcher"    # default

    def _get_k1_prior(self, domain: str) -> float:
        """Get minimum trust required for domain."""
        if self.brier:
            try:
                # Use best available trust score for this domain
                best = max(
                    self.brier.trust_score(p, domain) or 0
                    for p in ["bull", "bear", "buffet"]
                )
                return round(best * 0.8, 2)  # require 80% of best
            except Exception:
                pass
        return 0.6  # default minimum

    def _log_handoff(self, package: HandoffPackage) -> None:
        """Log handoff to audit trail."""
        try:
            log_file = self._log_dir / "handoff_log.jsonl"
            with open(log_file, "a") as f:
                f.write(json.dumps(package.to_dict()) + "\n")
        except Exception:
            pass


class HandoffRouter:
    """
    Routes handoff packages to appropriate agents.
    
    The "Traffic Cop" from the blueprint —
    reads the handoff JSON and routes to correct tool.
    
    Does NOT contain AI logic — pure routing.
    """

    ROLE_TO_TOOL = {
        "researcher":  "researcher",
        "analyst":     "exec",
        "financial":   "financial_cv",
        "critic":      "tri_agent",
        "synthesizer": "quad_agent",
        "ideator":     "tri_agent",
        "historian":   "web_search",
    }

    def __init__(self, tool_registry: object = None) -> None:
        self.tool_registry = tool_registry

    async def route(
        self,
        package:      HandoffPackage,
        agent_runner: object = None,
    ) -> str:
        """
        Route handoff package to appropriate agent/tool.
        Returns the result from the recipient agent.
        """
        recipient_tool = self.ROLE_TO_TOOL.get(
            package.recipient_role, "researcher"
        )

        # Build clean prompt for recipient
        prompt = package.to_agent_prompt()

        logger.info(
            f"HandoffRouter: routing {package.handoff_id} "
            f"→ {package.recipient_role} "
            f"(tool: {recipient_tool})"
        )

        # Execute via agent runner
        if agent_runner:
            try:
                result = await agent_runner.process_message(
                    content     = prompt,
                    session_key = f"handoff_{package.handoff_id}",
                    yolo_mode   = False,
                    max_tools   = 8,
                )
                return result
            except Exception as e:
                logger.error(f"HandoffRouter: routing failed: {e}")
                return (
                    f"Handoff {package.handoff_id} failed: {e}\n"
                    f"Original goal: {package.original_goal}"
                )

        # Stub — wire agent_runner in loop.py
        return (
            f"Handoff {package.handoff_id} received by "
            f"{package.recipient_role}.\n"
            f"Wire agent_runner to HandoffRouter.route() "
            f"to execute."
        )

    def get_log(self, workspace: Path) -> list[dict]:
        """Return handoff audit log."""
        log_file = workspace / "memory" / "handoffs" / "handoff_log.jsonl"
        if not log_file.exists():
            return []
        try:
            return [
                json.loads(line)
                for line in log_file.read_text().splitlines()
                if line.strip()
            ]
        except Exception:
            return []
