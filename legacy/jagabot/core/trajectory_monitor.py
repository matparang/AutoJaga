# jagabot/core/trajectory_monitor.py
"""
Phase 1 — Observer Layer: Trajectory Monitor

Watches the agent's thought-to-action ratio.
Kills runs when agent is "spinning" — thinking
without acting (the narration-without-execution bug).

Concepts:
    Entropy:   high = agent confused, scattered
               low  = agent focused, executing
    
    Thought-to-action ratio:
               high = too much reasoning, not enough tools
               low  = good — agent acting on thoughts

Wire into loop.py __init__:
    from jagabot.core.trajectory_monitor import TrajectoryMonitor
    self.trajectory_monitor = TrajectoryMonitor()

Wire into loop.py _run_agent_loop:
    # After each text generation (before tool call):
    should_continue = self.trajectory_monitor.on_text_generated(
        text=response_chunk,
        has_tool_call=bool(tool_calls_detected),
    )
    if not should_continue:
        return self._handle_spin_detected()
    
    # After each tool call:
    self.trajectory_monitor.on_tool_called(tool_name)

Wire into loop.py _process_message START:
    self.trajectory_monitor.reset()  # fresh per user turn
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger


# ── Config ───────────────────────────────────────────────────────────
MAX_STEPS_WITHOUT_TOOL    = 5    # kill after 5 text steps with no tool
MAX_TOTAL_STEPS           = 30   # absolute cap per turn
MAX_TOKENS_WITHOUT_ACTION = 800  # token budget before forced action
SPIN_COOLDOWN_SECS        = 2.0  # min time between spin detections


@dataclass
class StepRecord:
    """Record of one agent step (text or tool)."""
    step_type:  str    # "text" | "tool"
    content:    str
    tokens:     int
    timestamp:  float
    tool_name:  str = ""


@dataclass 
class TrajectoryStats:
    """Live trajectory statistics for current turn."""
    total_steps:            int   = 0
    text_steps:             int   = 0
    tool_steps:             int   = 0
    tokens_since_last_tool: int   = 0
    total_tokens:           int   = 0
    steps_since_last_tool:  int   = 0
    last_tool_called:       str   = ""
    spin_detected:          bool  = False
    spin_reason:            str   = ""

    @property
    def thought_to_action_ratio(self) -> float:
        """
        Lower is better — agent acting more than thinking.
        > 0.8 = too much thinking
        < 0.3 = healthy balance
        """
        if self.tool_steps == 0:
            return 1.0
        return self.text_steps / max(1, self.tool_steps)

    @property
    def entropy_score(self) -> float:
        """
        0.0 = focused (low entropy)
        1.0 = scattered (high entropy)
        
        Based on steps since last tool call —
        longer without action = higher entropy.
        """
        return min(
            1.0,
            self.steps_since_last_tool / MAX_STEPS_WITHOUT_TOOL
        )


class TrajectoryMonitor:
    """
    Monitors agent trajectory and detects spinning.
    
    Spinning = agent generating text without taking action.
    This manifests as the "narration instead of execution" bug.
    
    When spin is detected:
    - Returns False from on_text_generated()
    - Caller should inject: "Stop describing. Execute now."
    """

    def __init__(
        self,
        max_steps_without_tool:    int   = MAX_STEPS_WITHOUT_TOOL,
        max_total_steps:           int   = MAX_TOTAL_STEPS,
        max_tokens_without_action: int   = MAX_TOKENS_WITHOUT_ACTION,
        log_dir:                   Path  = None,
    ) -> None:
        self.max_steps_without_tool    = max_steps_without_tool
        self.max_total_steps           = max_total_steps
        self.max_tokens_without_action = max_tokens_without_action
        self.log_dir                   = log_dir
        self._steps:    list[StepRecord] = []
        self._stats:    TrajectoryStats  = TrajectoryStats()
        self._last_spin_time: float      = 0.0

    # ── Public API ───────────────────────────────────────────────────

    def reset(self) -> None:
        """Reset for new user turn. Call at start of _process_message."""
        self._steps = []
        self._stats = TrajectoryStats()
        self._last_spin_time = 0.0

    def on_text_generated(
        self,
        text:          str,
        has_tool_call: bool = False,
    ) -> bool:
        """
        Called when agent generates text.
        Returns True = continue, False = kill (spin detected).
        
        has_tool_call: set True if this text contains a tool call
                       (tool call resets the spin counter)
        """
        tokens = self._estimate_tokens(text)

        # Record step
        self._steps.append(StepRecord(
            step_type = "text",
            content   = text[:100],
            tokens    = tokens,
            timestamp = time.time(),
        ))

        # Update stats
        self._stats.total_steps += 1
        self._stats.text_steps  += 1
        self._stats.total_tokens += tokens

        if has_tool_call:
            # Tool call resets spin counter
            self._stats.steps_since_last_tool  = 0
            self._stats.tokens_since_last_tool = 0
        else:
            self._stats.steps_since_last_tool  += 1
            self._stats.tokens_since_last_tool += tokens

        # Check spin conditions
        spin, reason = self._check_spin()
        if spin:
            self._stats.spin_detected = True
            self._stats.spin_reason   = reason
            self._log_spin(reason)
            return False  # kill

        return True  # continue

    def on_tool_called(self, tool_name: str) -> None:
        """Called when agent executes a tool. Resets spin counter."""
        self._steps.append(StepRecord(
            step_type = "tool",
            content   = tool_name,
            tokens    = 0,
            timestamp = time.time(),
            tool_name = tool_name,
        ))
        self._stats.total_steps          += 1
        self._stats.tool_steps           += 1
        self._stats.steps_since_last_tool = 0
        self._stats.tokens_since_last_tool= 0
        self._stats.last_tool_called      = tool_name

    def get_stats(self) -> TrajectoryStats:
        """Return current trajectory statistics."""
        return self._stats

    def get_intervention_message(self) -> str:
        """
        Returns message to inject when spin detected.
        Forces agent to stop narrating and start acting.
        """
        reason = self._stats.spin_reason
        steps  = self._stats.steps_since_last_tool

        if "token" in reason:
            return (
                "[TRAJECTORY OVERRIDE] You have generated "
                f"{self._stats.tokens_since_last_tool} tokens "
                "without calling a tool. STOP describing. "
                "Execute the next required tool call NOW. "
                "Show results, not plans."
            )
        else:
            return (
                "[TRAJECTORY OVERRIDE] You have taken "
                f"{steps} reasoning steps without action. "
                "STOP. Call the most relevant tool immediately. "
                "One tool call, then report what it returned."
            )

    def summary(self) -> str:
        """Human-readable trajectory summary."""
        s = self._stats
        return (
            f"Steps: {s.total_steps} "
            f"(text={s.text_steps}, tools={s.tool_steps}) | "
            f"T:A ratio: {s.thought_to_action_ratio:.2f} | "
            f"Entropy: {s.entropy_score:.2f} | "
            f"Spin: {'YES — ' + s.spin_reason if s.spin_detected else 'No'}"
        )

    # ── Spin detection ───────────────────────────────────────────────

    def _check_spin(self) -> tuple[bool, str]:
        """Check if agent is spinning. Returns (is_spinning, reason)."""
        s = self._stats

        # Condition 1: too many steps without tool
        if s.steps_since_last_tool >= self.max_steps_without_tool:
            return True, (
                f"steps_without_tool={s.steps_since_last_tool} "
                f">= threshold={self.max_steps_without_tool}"
            )

        # Condition 2: too many tokens without action
        if s.tokens_since_last_tool >= self.max_tokens_without_action:
            return True, (
                f"tokens_without_action={s.tokens_since_last_tool} "
                f">= threshold={self.max_tokens_without_action}"
            )

        # Condition 3: absolute step cap
        if s.total_steps >= self.max_total_steps:
            return True, (
                f"total_steps={s.total_steps} "
                f">= cap={self.max_total_steps}"
            )

        # Condition 4: high entropy + no recent tool
        if s.entropy_score > 0.9 and s.tool_steps == 0:
            return True, (
                f"entropy={s.entropy_score:.2f} with zero tool calls"
            )

        return False, ""

    def _log_spin(self, reason: str) -> None:
        """Log spin detection."""
        logger.warning(
            f"TrajectoryMonitor: SPIN DETECTED — {reason}\n"
            f"  {self.summary()}"
        )
        if self.log_dir:
            try:
                log_file = (
                    self.log_dir / "trajectory_spins.jsonl"
                )
                import json
                with open(log_file, "a") as f:
                    f.write(json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        "reason":    reason,
                        "stats": {
                            "total_steps":  self._stats.total_steps,
                            "text_steps":   self._stats.text_steps,
                            "tool_steps":   self._stats.tool_steps,
                            "t_a_ratio":    self._stats.thought_to_action_ratio,
                            "entropy":      self._stats.entropy_score,
                        }
                    }) + "\n")
            except Exception:
                pass

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimate: ~4 chars per token."""
        return len(text) // 4
