# jagabot/core/model_switchboard.py
"""
ModelSwitchboard — Dynamic model selection for AutoJaga.

Integrates with:
  FluidDispatcher  → auto-switches model based on profile
  CalibrationMode  → forces Model 2 for calibration turns
  Telegram         → inline keyboard for manual switch
  CLI              → /model command

Two-tier model strategy:
  Model 1 (FAST):   cheap model for routine turns
                    Action, Maintenance, Safe_Default profiles
                    Example: gpt-4o-mini, qwen-plus

  Model 2 (SMART):  capable model for reasoning turns
                    Research, Verification, Calibration, Autonomous
                    Example: gpt-4o, qwen-max, claude-sonnet

AutoJaga can also self-switch:
  If agent detects it's "outclassed" (confidence drop,
  complex multi-step reasoning, calibration turn) →
  calls tool_switch_model(2) before responding.

Config structure (config.json):
{
  "model_presets": {
    "1": {
      "name": "GPT-4o-mini (Fast)",
      "model_id": "gpt-4o-mini",
      "provider": "openai",
      "purpose": "routine",
      "max_tokens": 2000,
      "token_cost_per_1k_input": 0.00015
    },
    "2": {
      "name": "GPT-4o (Smart)",
      "model_id": "gpt-4o",
      "provider": "openai",
      "purpose": "reasoning",
      "max_tokens": 4000,
      "token_cost_per_1k_input": 0.0025
    }
  },
  "current_model": "1",
  "auto_switch": true
}

Wire into loop.py __init__:
    from jagabot.core.model_switchboard import ModelSwitchboard
    self.switchboard = ModelSwitchboard(
        config_path = config_path,
        workspace   = workspace,
    )

Wire into loop.py _process_message — AFTER FluidDispatcher:
    # Auto-switch based on profile
    model_config = self.switchboard.resolve_model(
        profile    = harness_package.profile,
        confidence = getattr(self, '_last_confidence', 1.0),
        manual_override = getattr(self, '_manual_model', None),
    )
    # Use model_config for this turn's LLM call
    self._current_model_id = model_config.model_id
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger


# ── Model profile mappings ────────────────────────────────────────────
# Which fluid harness profiles use which model tier
PROFILE_MODEL_MAP = {
    # Model 1 (Fast/Cheap) — routine work
    "MAINTENANCE":  1,
    "ACTION":       1,
    "SAFE_DEFAULT": 1,

    # Model 2 (Smart) — reasoning required
    "RESEARCH":      2,
    "VERIFICATION":  2,
    "CALIBRATION":   2,   # always Model 2 — data integrity
    "AUTONOMOUS":    2,   # always Model 2 — complex planning
}

# Default presets if config.json has no model_presets
DEFAULT_PRESETS = {
    "1": {
        "name":                    "GPT-4o-mini (Fast)",
        "model_id":                "gpt-4o-mini",
        "provider":                "openai",
        "purpose":                 "routine",
        "max_tokens":              2000,
        "token_cost_per_1k_input": 0.00015,
        "token_cost_per_1k_output":0.00060,
    },
    "2": {
        "name":                    "GPT-4o (Smart)",
        "model_id":                "gpt-4o",
        "provider":                "openai",
        "purpose":                 "reasoning",
        "max_tokens":              4000,
        "token_cost_per_1k_input": 0.00250,
        "token_cost_per_1k_output":0.01000,
    },
}

# Triggers that force Model 2 regardless of profile
FORCE_MODEL2_SIGNALS = [
    "calibrat", "verify", "proof", "brier", "k1_bayesian",
    "belief", "confidence interval", "tri_agent", "adversar",
    "self.model", "/yolo", "/verify", "/pending",
]


@dataclass
class ModelConfig:
    """Active model configuration for one turn."""
    preset_id:    str
    model_id:     str
    provider:     str
    name:         str
    max_tokens:   int
    cost_input:   float
    cost_output:  float
    reason:       str   # why this model was selected
    auto_selected:bool  = True


class ModelSwitchboard:
    """
    Manages model selection per turn.

    Decision priority:
    1. Manual override (/model 1 or /model 2) → always respected
    2. Calibration mode → always Model 2
    3. FluidDispatcher profile → PROFILE_MODEL_MAP
    4. Confidence drop → Model 2
    5. Force signals in query → Model 2
    6. Default → Model 1
    """

    def __init__(
        self,
        config_path: Path = None,
        workspace:   Path = None,
    ) -> None:
        self.config_path    = Path(config_path) if config_path else None
        self.workspace      = Path(workspace) if workspace else None
        self._presets:      dict = {}
        self._current:      str  = "1"
        self._manual:       Optional[str] = None  # user override
        self._session_log:  list[dict] = []
        self._load_config()

    # ── Public API ───────────────────────────────────────────────────

    def resolve_model(
        self,
        profile:          str   = "SAFE_DEFAULT",
        confidence:       float = 1.0,
        query:            str   = "",
        calibration_mode: bool  = False,
        manual_override:  str   = None,
    ) -> ModelConfig:
        """
        Determine which model to use for this turn.
        Returns ModelConfig with model_id ready for LLM call.
        """
        # Priority 1: manual override from user
        if manual_override or self._manual:
            preset_id = manual_override or self._manual
            return self._make_config(
                preset_id, f"manual_override:/model {preset_id}"
            )

        # Priority 2: calibration mode always uses Model 2
        if calibration_mode:
            return self._make_config(
                "2", "calibration_mode=True"
            )

        # Priority 3: force signals in query
        query_lower = query.lower()
        if any(s in query_lower for s in FORCE_MODEL2_SIGNALS):
            return self._make_config(
                "2", "force_signal_in_query"
            )

        # Priority 4: profile mapping
        tier = PROFILE_MODEL_MAP.get(profile, 1)
        if tier == 2:
            return self._make_config(
                "2", f"profile={profile} requires Model 2"
            )

        # Priority 5: confidence drop
        if confidence < 0.5:
            return self._make_config(
                "2", f"confidence={confidence:.2f} below 0.5"
            )

        # Default: Model 1 for routine turns
        return self._make_config(
            "1", f"profile={profile} → routine (Model 1)"
        )

    def manual_switch(self, preset_id: str) -> str:
        """
        Manually switch model for rest of session.
        Called by /model command.
        """
        if preset_id not in self._presets:
            return (
                f"❌ Unknown preset: {preset_id}\n"
                f"Available: {', '.join(self._presets.keys())}"
            )

        self._manual = preset_id
        self._current = preset_id
        self._save_current_to_config(preset_id)

        preset = self._presets[preset_id]
        self._log_switch(preset_id, "manual_command")

        return (
            f"✅ Switched to **Model {preset_id}**: "
            f"{preset['name']}\n"
            f"Purpose: {preset['purpose']}\n"
            f"This applies to all turns until you switch again.\n"
            f"Use `/model auto` to restore automatic switching."
        )

    def set_auto(self) -> str:
        """Re-enable automatic switching."""
        self._manual = None
        return "✅ Auto model switching restored."

    def get_status(self) -> str:
        """Format model status for /model status."""
        lines = ["**Model Switchboard**", ""]

        for pid, preset in self._presets.items():
            active = "→ ACTIVE" if pid == self._current else ""
            manual = " (manual)" if pid == self._manual else ""
            cost   = preset.get("token_cost_per_1k_input", 0)
            lines.append(
                f"**Model {pid}** {active}{manual}\n"
                f"  Name:    {preset['name']}\n"
                f"  Model:   {preset['model_id']}\n"
                f"  Purpose: {preset['purpose']}\n"
                f"  Cost:    ${cost:.5f}/1k input tokens"
            )
            lines.append("")

        # Auto-switch status
        if self._manual:
            lines.append(
                f"⚠️ Manual override active: Model {self._manual}\n"
                f"Use `/model auto` to restore auto-switching."
            )
        else:
            lines.append("✅ Auto-switching active (profile-based)")

        # Session stats
        if self._session_log:
            m1_count = sum(
                1 for s in self._session_log if s["preset"] == "1"
            )
            m2_count = sum(
                1 for s in self._session_log if s["preset"] == "2"
            )
            total    = len(self._session_log)
            lines += [
                "",
                f"**This session:** {total} turns",
                f"  Model 1 (fast):  {m1_count} turns "
                f"({m1_count/max(1,total)*100:.0f}%)",
                f"  Model 2 (smart): {m2_count} turns "
                f"({m2_count/max(1,total)*100:.0f}%)",
                f"  Estimated cost:  "
                f"${self._estimate_session_cost():.4f}",
            ]

        return "\n".join(lines)

    def get_session_stats(self) -> dict:
        """Return session model usage statistics."""
        if not self._session_log:
            return {"turns": 0}

        m1 = [s for s in self._session_log if s["preset"] == "1"]
        m2 = [s for s in self._session_log if s["preset"] == "2"]
        total = len(self._session_log)

        return {
            "total_turns":    total,
            "model1_turns":   len(m1),
            "model2_turns":   len(m2),
            "model1_pct":     len(m1) / max(1, total) * 100,
            "model2_pct":     len(m2) / max(1, total) * 100,
            "estimated_cost": self._estimate_session_cost(),
            "auto_switches":  sum(
                1 for s in self._session_log if s.get("auto")
            ),
        }

    def record_turn(
        self,
        preset_id:    str,
        input_tokens: int = 0,
        output_tokens:int = 0,
        reason:       str = "",
        auto:         bool = True,
    ) -> None:
        """Record a turn for session statistics."""
        self._session_log.append({
            "preset":        preset_id,
            "input_tokens":  input_tokens,
            "output_tokens": output_tokens,
            "reason":        reason,
            "auto":          auto,
            "timestamp":     datetime.now().isoformat(),
        })

    def get_tool_definition(self) -> dict:
        """
        Return tool definition for AGENTS.md / tool registry.
        Allows agent to self-switch when outclassed.
        """
        return {
            "type": "object",
            "properties": {
                "preset_id": {
                    "type": "string",
                    "enum": ["1", "2"],
                    "description": (
                        "Model preset: '1' for fast/cheap routine work, "
                        "'2' for smart/reasoning tasks"
                    ),
                },
                "reason": {
                    "type": "string",
                    "description": "Why switching is needed (e.g., 'complex causal analysis')"
                },
            },
            "required": ["preset_id"],
        }

    def switch_model(self, preset_id: str, reason: str = "") -> str:
        """
        Switch model for this turn only.
        Called by agent via tool call.
        """
        if preset_id not in self._presets:
            return f"❌ Unknown preset: {preset_id}. Use '1' or '2'."

        old_preset = self._current
        self._current = preset_id

        preset = self._presets[preset_id]
        self._log_switch(preset_id, f"agent_request: {reason[:50]}")

        return (
            f"✅ Switched to **Model {preset_id}**: {preset['name']}\n"
            f"Reason: {reason or 'complex task'}\n"
            f"Model will revert to auto-selection on next turn."
        )

    # ── Telegram inline keyboard ─────────────────────────────────────

    def get_telegram_keyboard(self) -> list:
        """
        Return inline keyboard buttons for Telegram.
        Wire into Telegram channel handler.
        """
        buttons = []
        for pid, preset in self._presets.items():
            active = "✅ " if pid == self._current else ""
            buttons.append([{
                "text":          f"{active}Model {pid}: {preset['name']}",
                "callback_data": f"switch_model_{pid}",
            }])
        buttons.append([{
            "text":          "🔄 Auto (profile-based)",
            "callback_data": "switch_model_auto",
        }])
        return buttons

    def handle_telegram_callback(self, callback_data: str) -> str:
        """Handle Telegram inline button press."""
        if callback_data == "switch_model_auto":
            return self.set_auto()
        if callback_data.startswith("switch_model_"):
            preset_id = callback_data.replace("switch_model_", "")
            return self.manual_switch(preset_id)
        return "Unknown callback"

    # ── Config I/O ───────────────────────────────────────────────────

    def _load_config(self) -> None:
        """Load model presets from config.json."""
        if not self.config_path or not self.config_path.exists():
            self._presets = DEFAULT_PRESETS
            return

        try:
            config = json.loads(self.config_path.read_text())
            self._presets  = config.get(
                "model_presets", DEFAULT_PRESETS
            )
            self._current  = str(
                config.get("current_model", "1")
            )
            logger.debug(
                f"ModelSwitchboard: loaded {len(self._presets)} "
                f"presets, current={self._current}"
            )
        except Exception as e:
            logger.warning(
                f"ModelSwitchboard: config load failed: {e} "
                f"— using defaults"
            )
            self._presets = DEFAULT_PRESETS

    def _save_current_to_config(self, preset_id: str) -> None:
        """Save current model selection to config.json."""
        if not self.config_path or not self.config_path.exists():
            return
        try:
            config = json.loads(self.config_path.read_text())
            config["current_model"] = preset_id
            self.config_path.write_text(
                json.dumps(config, indent=2)
            )
        except Exception as e:
            logger.debug(
                f"ModelSwitchboard: config save failed: {e}"
            )

    # ── Helpers ──────────────────────────────────────────────────────

    def _make_config(
        self, preset_id: str, reason: str
    ) -> ModelConfig:
        """Build ModelConfig from preset."""
        preset = self._presets.get(preset_id, self._presets["1"])
        self._current = preset_id
        self._log_switch(preset_id, reason)

        return ModelConfig(
            preset_id    = preset_id,
            model_id     = preset["model_id"],
            provider     = preset.get("provider", "openai"),
            name         = preset["name"],
            max_tokens   = preset.get("max_tokens", 2000),
            cost_input   = preset.get(
                "token_cost_per_1k_input", 0.00015
            ),
            cost_output  = preset.get(
                "token_cost_per_1k_output", 0.00060
            ),
            reason       = reason,
            auto_selected= not bool(self._manual),
        )

    def _log_switch(self, preset_id: str, reason: str) -> None:
        """Log model switch to history."""
        if not self.workspace:
            return
        try:
            history = self.workspace / "memory" / "HISTORY.md"
            # Only log manual switches — not every auto-switch
            if "manual" in reason:
                with open(history, "a") as f:
                    f.write(
                        f"\n{datetime.now().strftime('%Y-%m-%d %H:%M')} | "
                        f"MODEL_SWITCH | "
                        f"preset={preset_id} | "
                        f"reason={reason}\n"
                    )
        except Exception:
            pass

    def _estimate_session_cost(self) -> float:
        """Rough cost estimate for this session."""
        total = 0.0
        for s in self._session_log:
            preset = self._presets.get(s["preset"], {})
            cost_in  = preset.get("token_cost_per_1k_input", 0)
            cost_out = preset.get("token_cost_per_1k_output", 0)
            total += (
                s.get("input_tokens", 1000) / 1000 * cost_in +
                s.get("output_tokens", 300)  / 1000 * cost_out
            )
        return total
