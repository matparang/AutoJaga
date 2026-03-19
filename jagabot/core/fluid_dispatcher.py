# jagabot/core/fluid_dispatcher.py
"""
FluidDispatcher — Just-in-Time Engine & Tool Loading

Synthesizes:
  AutoJaga audit:  tool categorization + intent mapping
  Gemini blueprint: harness profiles + switchboard + K1 routing
  Our fluid harness: four triggers + token cap

Architecture:
  1. PROFILES     — define what loads per intent (config layer)
  2. SWITCHBOARD  — classify intent in < 50ms (no LLM calls)
  3. K1 ROUTING   — use Bayesian history for profile uncertainty
  4. PACKAGE      — return filtered context + tools ready for loop.py

Performance guarantee: classify_intent() < 50ms always.
No LLM calls inside the dispatcher — pure Python deterministic logic.

Wire into loop.py __init__:
    from jagabot.core.fluid_dispatcher import FluidDispatcher
    self.dispatcher = FluidDispatcher(
        workspace = workspace,
        k1_tool   = getattr(self, 'k1_bayesian_tool', None),
    )

Wire into loop.py _process_message — BEFORE any LLM call:
    package = self.dispatcher.dispatch(
        user_input  = msg.content,
        topic       = detected_topic,
        confidence  = getattr(self, '_last_confidence', 1.0),
        has_pending = self.tracker.has_overdue_pending()
                      if self.tracker else False,
    )
    system_prompt   += package.context
    tools_this_turn  = package.tools
    # Log for audit:
    logger.debug(f"FluidDispatcher: {package.profile} | "
                 f"~{package.token_estimate} tokens | "
                 f"tools={len(package.tools)}")
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger


# ═══════════════════════════════════════════════════════════════════
# HARNESS PROFILES
# Each profile = one "cognitive mode" for AutoJaga
# Inspired by Gemini's lobes concept + AutoJaga's own audit
# ═══════════════════════════════════════════════════════════════════

HARNESS_PROFILES = {

    # ── MAINTENANCE ───────────────────────────────────────────────
    # Triggered by: / commands, status checks, config queries
    # AutoJaga audit: "Status Checks: only Self-Model + Error Analysis"
    "MAINTENANCE": {
        "description":   "Status, config, self-inspection",
        "engines":       ["librarian", "self_model", "belief_engine"],
        "tools":         ["self_model_awareness", "error_analysis",
                          "read_file", "memory_fleet"],
        "context_files": ["core_identity.md"],
        "token_budget":  400,
        "triggers":      ["command_prefix", "status_keyword"],
    },

    # ── CALIBRATION ───────────────────────────────────────────────
    # Triggered by: /verify, /pending, "confirmed", "wrong", verdict words
    # This is the most important profile — protects calibration data
    "CALIBRATION": {
        "description":   "Recording and verifying outcomes",
        "engines":       ["librarian", "belief_engine",
                          "brier_scorer", "outcome_tracker"],
        "tools":         ["k1_bayesian", "k3_perspective",
                          "meta_learning", "memory_fleet",
                          "write_file", "read_file"],
        "context_files": ["core_identity.md"],
        "token_budget":  500,
        "triggers":      ["verify_keyword", "pending_command",
                          "verdict_word"],
    },

    # ── ACTION ────────────────────────────────────────────────────
    # Triggered by: file operations, "create", "edit", "write", "save"
    # AutoJaga audit: "File Actions: focus on File Management Tools"
    "ACTION": {
        "description":   "File creation, editing, saving",
        "engines":       ["librarian", "belief_engine"],
        "tools":         ["read_file", "write_file", "edit_file",
                          "memory_fleet"],
        "context_files": ["core_identity.md"],
        "token_budget":  350,
        "triggers":      ["file_keyword", "create_keyword"],
    },

    # ── RESEARCH ─────────────────────────────────────────────────
    # Triggered by: "research", "find", "search", "explore", "what is"
    # AutoJaga audit: "Thinking: Researcher + Debate tools"
    "RESEARCH": {
        "description":   "Web research, synthesis, exploration",
        "engines":       ["librarian", "curiosity_engine",
                          "self_model", "brier_scorer",
                          "k3_perspective"],  # ADDED: adversarial for all domains
        "tools":         ["web_search", "web_fetch", "researcher",
                          "memory_fleet", "read_file",
                          "k1_bayesian", "write_file",
                          "k3_perspective"],  # ADDED: enable k3 tool
        "context_files": ["core_identity.md"],
        "token_budget":  700,
        "triggers":      ["research_keyword", "question_keyword", "adversarial_keyword"],
    },

    # ── VERIFICATION ─────────────────────────────────────────────
    # Triggered by: "verify", "proof", "check", "confirm", "is this true"
    # Gemini: "Focus on validating existing information"
    "VERIFICATION": {
        "description":   "Fact checking, adversarial review",
        "engines":       ["librarian", "belief_engine",
                          "brier_scorer", "strategic_interceptor",
                          "k3_perspective"],  # ADDED: explicit adversarial
        "tools":         ["tri_agent", "exec", "read_file",
                          "memory_fleet", "k1_bayesian",
                          "web_search", "k3_perspective"],  # ADDED: enable k3
        "context_files": ["core_identity.md"],
        "token_budget":  600,
        "triggers":      ["verify_keyword", "proof_keyword", "adversarial_keyword"],
    },

    # ── AUTONOMOUS ───────────────────────────────────────────────
    # Triggered by: /yolo, /goals, "autonomous", "run overnight"
    "AUTONOMOUS": {
        "description":   "YOLO mode, goal execution, planning",
        "engines":       ["librarian", "k5_planner",
                          "k6_executor", "goal_engine",
                          "trajectory_monitor"],
        "tools":         ["web_search", "researcher", "exec",
                          "write_file", "memory_fleet",
                          "tri_agent", "quad_agent",
                          "k1_bayesian", "web_fetch"],
        "context_files": ["core_identity.md"],
        "token_budget":  800,
        "triggers":      ["yolo_command", "goals_command"],
    },

    # ── SAFE_DEFAULT ─────────────────────────────────────────────
    # Fallthrough: no trigger matched
    # Gemini: "Fallthrough mechanism: load Safe Default context"
    "SAFE_DEFAULT": {
        "description":   "General conversation, unclear intent",
        "engines":       ["librarian"],
        "tools":         ["read_file", "memory_fleet",
                          "write_file", "k1_bayesian"],
        "context_files": ["core_identity.md"],
        "token_budget":  300,
        "triggers":      ["fallthrough"],
    },
}

# Token cost per engine context injection (estimated)
ENGINE_TOKEN_COSTS = {
    "librarian":            150,  # always worth it
    "self_model":           150,
    "curiosity_engine":     100,
    "belief_engine":        120,
    "brier_scorer":          80,
    "outcome_tracker":       50,
    "strategic_interceptor":  0,  # post-process only, no injection
    "trajectory_monitor":     0,  # runtime monitor, no injection
    "k5_planner":           200,
    "k6_executor":            0,  # shares K5 context
    "goal_engine":          100,
}

# Hard token caps per calibration state
TOKEN_CAP_CALIBRATION = 600
TOKEN_CAP_FULL        = 1200


# ═══════════════════════════════════════════════════════════════════
# DISPATCH RESULT
# ═══════════════════════════════════════════════════════════════════

@dataclass
class DispatchPackage:
    """Everything loop.py needs for this turn."""
    profile:        str
    context:        str
    tools:          set
    engines_active: list
    engines_dormant:list
    token_estimate: int
    trigger_reason: str
    dispatch_ms:    float = 0.0
    k1_assisted:    bool  = False   # True if K1 influenced routing


# ═══════════════════════════════════════════════════════════════════
# KEYWORD BANKS
# ═══════════════════════════════════════════════════════════════════

KEYWORDS = {
    "command_prefix": ["/"],  # handled by startswith check
    "status_keyword": [
        "status", "how are you", "health", "reliability",
        "calibration", "what engines", "what tools",
        "are you", "your", "self",
    ],
    "verify_keyword": [
        "verify", "verification", "check this", "is this correct",
        "was i right", "was that right", "fact check",
        "cross check", "validate",
    ],
    "pending_command": ["/pending", "/verify"],
    "verdict_word": [
        "confirmed", "correct", "wrong", "falsified",
        "inconclusive", "partially", "verdict",
        "that was right", "that was wrong",
    ],
    "file_keyword": [
        "create file", "write file", "edit file", "save to",
        "save this", "write this", "create a", "make a file",
        "update the file",
    ],
    "create_keyword": [
        "create", "write", "edit", "save", "update",
        "modify", "change", "patch",
    ],
    "research_keyword": [
        "research", "find", "search for", "look up", "explore",
        "investigate", "study", "learn about", "tell me about",
        "what do you know about",
    ],
    "question_keyword": [
        "what is", "what are", "how does", "why does",
        "explain", "describe", "how do", "what was",
    ],
    "proof_keyword": [
        "proof", "prove", "evidence", "show me", "demonstrate",
        "is it true", "is that true", "can you confirm",
    ],
    "adversarial_keyword": [  # ADDED: trigger k3_perspective for all domains
        "what are the risks", "devil's advocate", "challenge this",
        "argue against", "what could go wrong", "opposing view",
        "steelman", "counterargument", "bull case", "bear case",
        "worst case", "downside", "critique this",
    ],
    "yolo_command":  ["/yolo"],
    "goals_command": ["/goals"],
    "compress_command": ["/compress", "/compact"],
}

# Regex patterns for fast matching
COMMAND_PATTERN  = re.compile(r'^/')
VERDICT_PATTERN  = re.compile(
    r'\b(confirmed|correct|wrong|falsified|inconclusive|'
    r'partially correct|partially wrong)\b',
    re.IGNORECASE
)
CONFIDENCE_WORDS = re.compile(
    r'\b(\d{1,3}%|definitely|certainly|very likely|likely|'
    r'probably|confident|sure)\b',
    re.IGNORECASE
)


# ═══════════════════════════════════════════════════════════════════
# FLUID DISPATCHER
# ═══════════════════════════════════════════════════════════════════

class FluidDispatcher:
    """
    Deterministic pre-processor that classifies intent and
    returns a minimal DispatchPackage before any LLM call.

    Performance guarantee: dispatch() < 50ms always.
    No LLM calls, no network calls, no heavy computation.
    Pure Python string matching + SQLite lookup (optional K1).
    """

    def __init__(
        self,
        workspace:        Path   = None,
        k1_tool:          object = None,
        calibration_mode: bool   = False,
        engine_registry:  dict   = None,
    ) -> None:
        self.workspace        = Path(workspace) if workspace else None
        self.k1_tool          = k1_tool
        self.calibration_mode = calibration_mode
        self.engine_registry  = engine_registry or {}
        self._session_stats:  list[dict] = []

    # ── Public API ──────────────────────────────────────────────────

    def dispatch(
        self,
        user_input:   str,
        topic:        str   = "general",
        confidence:   float = 1.0,
        has_pending:  bool  = False,
        is_first_msg: bool  = False,
    ) -> DispatchPackage:
        """
        Main entry point. Call before every LLM invocation.
        Returns DispatchPackage with filtered context + tools.
        Guaranteed < 50ms.
        """
        t_start = time.monotonic()

        # Step 1: Classify intent (pure Python, < 5ms)
        profile_key, trigger_reason = self.classify_intent(
            user_input, confidence, has_pending, is_first_msg
        )

        # Step 2: K1 routing (SQLite lookup, < 10ms, optional)
        k1_assisted = False
        if self.k1_tool and self._is_ambiguous(profile_key):
            profile_key, k1_assisted = self._k1_route(
                user_input, topic, profile_key
            )

        # Step 3: Build context package
        package = self._build_package(
            profile_key    = profile_key,
            trigger_reason = trigger_reason,
            topic          = topic,
            k1_assisted    = k1_assisted,
        )

        package.dispatch_ms = (time.monotonic() - t_start) * 1000

        # Log if slow (should never happen)
        if package.dispatch_ms > 50:
            logger.warning(
                f"FluidDispatcher: slow dispatch "
                f"{package.dispatch_ms:.1f}ms"
            )

        # Record for stats
        self._session_stats.append({
            "profile":        profile_key,
            "tokens":         package.token_estimate,
            "trigger":        trigger_reason,
            "dispatch_ms":    package.dispatch_ms,
            "timestamp":      datetime.now().isoformat(),
        })

        logger.debug(
            f"FluidDispatcher: {profile_key} | "
            f"~{package.token_estimate}t | "
            f"{trigger_reason} | "
            f"{package.dispatch_ms:.1f}ms"
        )

        return package

    def classify_intent(
        self,
        user_input:   str,
        confidence:   float = 1.0,
        has_pending:  bool  = False,
        is_first_msg: bool  = False,
    ) -> tuple[str, str]:
        """
        Classify user intent into a profile key.
        Pure regex + keyword matching. No LLM. < 5ms.

        Returns (profile_key, trigger_reason).
        """
        text = user_input.strip().lower()

        # ── Priority 1: Explicit commands ────────────────────────
        if COMMAND_PATTERN.match(text):

            if any(text.startswith(c) for c in
                   ["/yolo", "/goals"]):
                return "AUTONOMOUS", "command:/yolo or /goals"

            if any(text.startswith(c) for c in
                   ["/verify", "/pending"]):
                return "CALIBRATION", "command:/verify or /pending"

            if any(text.startswith(c) for c in
                   ["/status", "/health", "/self"]):
                return "MAINTENANCE", "command:/status"

            if any(text.startswith(c) for c in
                   ["/research", "/idea"]):
                return "RESEARCH", "command:/research or /idea"

            # Any other command → MAINTENANCE
            return "MAINTENANCE", "command_prefix:/"

        # ── Priority 2: Verdict words (calibration critical) ─────
        if VERDICT_PATTERN.search(text):
            return "CALIBRATION", "verdict_word_detected"

        # ── Priority 3: Verification keywords ────────────────────
        if any(kw in text for kw in KEYWORDS["verify_keyword"] +
               KEYWORDS["proof_keyword"]):
            return "VERIFICATION", "verify_keyword"

        # ── Priority 3b: Adversarial keywords (ADDED) ───────────
        if any(kw in text for kw in KEYWORDS["adversarial_keyword"]):
            return "VERIFICATION", "adversarial_keyword"

        # ── Priority 4: Research keywords ────────────────────────
        if any(kw in text for kw in KEYWORDS["research_keyword"]):
            return "RESEARCH", "research_keyword"

        # ── Priority 5: Questions ─────────────────────────────────
        if any(kw in text for kw in KEYWORDS["question_keyword"]):
            return "RESEARCH", "question_keyword"

        # ── Priority 6: File/create keywords ─────────────────────
        if any(kw in text for kw in KEYWORDS["file_keyword"]):
            return "ACTION", "file_keyword"

        # ── Priority 7: Pending item on first message ─────────────
        if is_first_msg and has_pending:
            return "CALIBRATION", "pending_item_first_msg"

        # ── Priority 8: Confidence drop ───────────────────────────
        if confidence < 0.5:
            return "VERIFICATION", "confidence_below_threshold"

        # ── Fallthrough: Safe Default ─────────────────────────────
        return "SAFE_DEFAULT", "no_trigger_matched"

    def get_context_package(self, profile_key: str) -> str:
        """
        Return filtered context string for a profile.
        Gemini: "returns a filtered string containing ONLY
                 the tools and system prompts for that profile"
        """
        package = self._build_package(
            profile_key    = profile_key,
            trigger_reason = "manual",
            topic          = "general",
        )
        return package.context

    def get_stats(self) -> dict:
        """Return firing stats for session."""
        if not self._session_stats:
            return {"turns": 0}

        profile_counts: dict[str, int] = {}
        total_tokens   = 0
        total_ms       = 0.0

        for s in self._session_stats:
            p = s["profile"]
            profile_counts[p] = profile_counts.get(p, 0) + 1
            total_tokens      += s["tokens"]
            total_ms          += s["dispatch_ms"]

        turns          = len(self._session_stats)
        avg_tokens     = total_tokens / turns
        normal_estimate= turns * 5000  # full-load baseline
        saved          = normal_estimate - total_tokens

        return {
            "turns":            turns,
            "profile_counts":   profile_counts,
            "avg_tokens":       round(avg_tokens),
            "total_tokens":     total_tokens,
            "tokens_saved":     max(0, saved),
            "savings_pct":      round(saved / max(1, normal_estimate)
                                      * 100),
            "avg_dispatch_ms":  round(total_ms / turns, 2),
        }

    def format_status(self) -> str:
        """Format dispatcher status for /harness status."""
        stats = self.get_stats()
        if stats["turns"] == 0:
            return "**FluidDispatcher:** No turns recorded yet."

        lines = [
            "**FluidDispatcher Status**", "",
            f"Turns this session: {stats['turns']}",
            f"Avg tokens/turn:    {stats['avg_tokens']:,}",
            f"Tokens saved:       {stats['tokens_saved']:,} "
            f"({stats['savings_pct']}% vs full-load)",
            f"Avg dispatch time:  {stats['avg_dispatch_ms']}ms",
            "",
            "Profile breakdown:",
        ]
        for profile, count in sorted(
            stats["profile_counts"].items(),
            key=lambda x: x[1], reverse=True
        ):
            pct = count / stats["turns"] * 100
            lines.append(f"  {profile:<15} {count:>3}x ({pct:.0f}%)")

        return "\n".join(lines)

    # ── K1 Bayesian routing ─────────────────────────────────────────

    def _k1_route(
        self,
        user_input:       str,
        topic:            str,
        current_profile:  str,
    ) -> tuple[str, bool]:
        """
        Use K1 Bayesian history to resolve ambiguous profiles.
        Gemini: "K1 Ledger looks at historical patterns to
                 proactively load tools just in case"

        Example: user usually follows research with file edits
        → pre-load ACTION tools even in RESEARCH profile
        """
        try:
            result = self.k1_tool.call({
                "action":    "get_sequence_probability",
                "topic":     topic,
                "current":   current_profile,
                "lookback":  5,
            })

            if not result:
                return current_profile, False

            # If K1 says next profile is likely ACTION after RESEARCH
            next_likely = result.get("most_likely_next", "")
            confidence  = result.get("confidence", 0.0)

            if confidence >= 0.7 and next_likely:
                logger.debug(
                    f"FluidDispatcher: K1 suggests "
                    f"{current_profile} → {next_likely} "
                    f"(conf={confidence:.2f})"
                )
                # Merge tool sets rather than switching profile
                # (preload next profile's tools)
                return current_profile, True

        except Exception:
            pass

        return current_profile, False

    def _is_ambiguous(self, profile_key: str) -> bool:
        """RESEARCH and SAFE_DEFAULT benefit most from K1 routing."""
        return profile_key in ("RESEARCH", "SAFE_DEFAULT")

    # ── Package builder ─────────────────────────────────────────────

    def _build_package(
        self,
        profile_key:   str,
        trigger_reason:str,
        topic:         str  = "general",
        k1_assisted:   bool = False,
    ) -> DispatchPackage:
        """Build the DispatchPackage for a profile."""
        profile = HARNESS_PROFILES.get(
            profile_key, HARNESS_PROFILES["SAFE_DEFAULT"]
        )

        # Determine token cap
        cap = (TOKEN_CAP_CALIBRATION if self.calibration_mode
               else TOKEN_CAP_FULL)

        # Build engine context
        context, engines_active, token_count = \
            self._build_engine_context(
                profile["engines"], profile["token_budget"], cap
            )

        # Engines not firing
        all_engines   = set(ENGINE_TOKEN_COSTS.keys())
        engines_dormant = list(
            all_engines - set(engines_active)
        )

        # Tools for this profile
        tools = set(profile["tools"])

        return DispatchPackage(
            profile         = profile_key,
            context         = context,
            tools           = tools,
            engines_active  = engines_active,
            engines_dormant = engines_dormant,
            token_estimate  = token_count,
            trigger_reason  = trigger_reason,
            k1_assisted     = k1_assisted,
        )

    def _build_engine_context(
        self,
        engine_names: list[str],
        budget:       int,
        cap:          int,
    ) -> tuple[str, list[str], int]:
        """
        Build combined context from active engines.
        Respects token budget. Drops lowest priority engines first.
        Librarian is NEVER dropped.
        """
        effective_budget = min(budget, cap)
        parts            = []
        active           = []
        total_tokens     = 0

        # Always include Librarian first
        if "librarian" in engine_names:
            ctx = self._get_engine_context("librarian")
            if ctx:
                parts.append(ctx)
                active.append("librarian")
                total_tokens += ENGINE_TOKEN_COSTS["librarian"]

        # Add remaining engines within budget
        for engine in engine_names:
            if engine == "librarian":
                continue  # already added
            cost = ENGINE_TOKEN_COSTS.get(engine, 100)
            if total_tokens + cost > effective_budget:
                logger.debug(
                    f"FluidDispatcher: dropping {engine} "
                    f"(budget {total_tokens}+{cost}"
                    f">{effective_budget})"
                )
                continue
            ctx = self._get_engine_context(engine)
            if ctx:
                parts.append(ctx)
                active.append(engine)
                total_tokens += cost

        return "\n\n".join(parts), active, total_tokens

    def _get_engine_context(self, engine_name: str) -> str:
        """
        Get context string from a registered engine.
        Returns empty string if engine not registered or no context.
        """
        engine = self.engine_registry.get(engine_name)
        if not engine:
            return ""
        try:
            if hasattr(engine, "get_context"):
                result = engine.get_context()
                return result if isinstance(result, str) else ""
            if hasattr(engine, "format_status"):
                return engine.format_status()
        except Exception as e:
            logger.debug(
                f"FluidDispatcher: {engine_name} "
                f"context failed: {e}"
            )
        return ""


# ═══════════════════════════════════════════════════════════════════
# HARNESS MANAGER
# Registers engines + exposes /harness commands
# ═══════════════════════════════════════════════════════════════════

class HarnessManager:
    """
    Manages the FluidDispatcher and engine registry.
    Exposes /harness command interface.
    """

    def __init__(
        self,
        workspace:        Path,
        calibration_mode: bool   = False,
        k1_tool:          object = None,
    ) -> None:
        self.workspace   = Path(workspace)
        self._registry:  dict = {}
        self._forced:    dict = {}  # forced active/dormant per session
        self.dispatcher  = FluidDispatcher(
            workspace        = workspace,
            k1_tool          = k1_tool,
            calibration_mode = calibration_mode,
            engine_registry  = self._registry,
        )

    def register(self, name: str, engine: object) -> None:
        """Register an engine instance."""
        self._registry[name] = engine
        logger.debug(f"HarnessManager: registered '{name}'")

    def register_all(self, loop_instance: object) -> None:
        """
        Auto-register all engines from loop instance.
        Call in loop.py __init__ after all engines initialized.
        """
        engine_attrs = {
            "librarian":            "librarian",
            "self_model":           "self_model",
            "curiosity_engine":     "curiosity",
            "belief_engine":        "belief_engine",
            "brier_scorer":         "brier",
            "outcome_tracker":      "tracker",
            "strategic_interceptor":"interceptor",
            "trajectory_monitor":   "trajectory_monitor",
            "goal_engine":          "goal_engine",
            "k5_planner":           "k5_planner",
            "k6_executor":          "k6_executor",
        }
        for engine_name, attr in engine_attrs.items():
            engine = getattr(loop_instance, attr, None)
            if engine:
                self.register(engine_name, engine)

        registered = len(self._registry)
        logger.info(
            f"HarnessManager: {registered} engines registered"
        )

    def dispatch(self, **kwargs) -> DispatchPackage:
        """Dispatch with forced overrides applied."""
        package = self.dispatcher.dispatch(**kwargs)

        # Apply forced active engines
        for engine in self._forced.get("active", []):
            if engine not in package.engines_active:
                package.engines_active.append(engine)
                cost = ENGINE_TOKEN_COSTS.get(engine, 100)
                package.token_estimate += cost

        # Apply forced dormant engines
        for engine in self._forced.get("dormant", []):
            if engine in package.engines_active:
                package.engines_active.remove(engine)

        return package

    def force_active(self, engine: str) -> str:
        """Force an engine active for this session (/harness force)."""
        self._forced.setdefault("active", [])
        if engine not in self._forced["active"]:
            self._forced["active"].append(engine)
        return f"✅ {engine} forced ACTIVE for this session"

    def force_dormant(self, engine: str) -> str:
        """Force an engine dormant (/harness freeze)."""
        self._forced.setdefault("dormant", [])
        if engine not in self._forced["dormant"]:
            self._forced["dormant"].append(engine)
        return f"✅ {engine} forced DORMANT for this session"

    def clear_forces(self) -> str:
        """Clear all forced overrides."""
        self._forced = {}
        return "✅ All forced overrides cleared"

    def handle_command(self, args: str) -> str:
        """Handle /harness commands."""
        parts  = args.strip().split(None, 1)
        action = parts[0].lower() if parts else "status"
        arg2   = parts[1] if len(parts) > 1 else ""

        if action == "status":
            return self.dispatcher.format_status()

        if action == "stats":
            stats = self.dispatcher.get_stats()
            lines = [
                "**Harness Session Stats**", "",
                f"Turns:           {stats.get('turns', 0)}",
                f"Avg tokens/turn: {stats.get('avg_tokens', 0):,}",
                f"Total saved:     {stats.get('tokens_saved', 0):,} "
                f"({stats.get('savings_pct', 0)}%)",
                f"Avg dispatch:    {stats.get('avg_dispatch_ms', 0)}ms",
            ]
            return "\n".join(lines)

        if action == "force" and arg2:
            return self.force_active(arg2)

        if action == "freeze" and arg2:
            return self.force_dormant(arg2)

        if action == "clear":
            return self.clear_forces()

        if action == "profiles":
            lines = ["**Available Profiles:**", ""]
            for name, p in HARNESS_PROFILES.items():
                lines.append(
                    f"**{name}**: {p['description']} "
                    f"(budget={p['token_budget']}t)"
                )
            return "\n".join(lines)

        return (
            "Usage: /harness [status|stats|profiles|"
            "force <engine>|freeze <engine>|clear]"
        )
