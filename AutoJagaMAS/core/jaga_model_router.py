"""
JagaModelRouter — Adapter 3
============================
Wraps AutoJaga's ModelSwitchboard for MASFactory node-level model routing.

In plain English
----------------
Think of this as the routing desk at a Malaysian law firm. When a case arrives,
a paralegal reads the file (DispatchPackage) and decides: is this routine
correspondence that can go to a junior associate (Qwen 3B local — fast, cheap),
or is this a complex litigation matter that needs a senior partner (Claude
Sonnet — powerful, API-based)? The routing desk doesn't do the work — it just
decides who should. That's JagaModelRouter.

Routing rules
-------------
  SIMPLE / MAINTENANCE / ACTION / SAFE_DEFAULT  →  ollama/qwen2.5:3b  (local)
  RESEARCH / VERIFICATION / CALIBRATION / AUTONOMOUS  →  anthropic/claude-sonnet-4-6  (API)

AutoJaga API used
-----------------
- ModelSwitchboard.resolve_model(profile, confidence, ...) → ModelConfig
  ModelConfig fields: preset_id, model_id, provider, name, max_tokens,
  cost_input, cost_output, reason, auto_selected
- PROFILE_MODEL_MAP: dict mapping profile strings → tier int (1 or 2)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# AutoJaga imports
# ---------------------------------------------------------------------------
_LEGACY_ROOT = Path(__file__).resolve().parent.parent.parent / "legacy"
if str(_LEGACY_ROOT) not in sys.path:
    sys.path.insert(0, str(_LEGACY_ROOT))

try:
    from jagabot.core.model_switchboard import ModelSwitchboard, PROFILE_MODEL_MAP
    _SWITCHBOARD_AVAILABLE = True
except ImportError:
    _SWITCHBOARD_AVAILABLE = False
    ModelSwitchboard = None  # type: ignore[assignment,misc]
    PROFILE_MODEL_MAP = {}   # type: ignore[assignment]
    logger.warning("legacy jagabot not importable — ModelSwitchboard unavailable.")

# ---------------------------------------------------------------------------
# Profile → model identifier mapping (canonical for AutoJagaMAS)
# ---------------------------------------------------------------------------

# Local tier: fast, CPU-resident, no API key needed
_LOCAL_MODEL = "ollama/qwen2.5:3b"

# Cloud tier: reasoning-capable, requires ANTHROPIC_API_KEY
_CLOUD_MODEL = "anthropic/claude-sonnet-4-6"

# Profiles that map to the local tier
_LOCAL_PROFILES = frozenset({
    "SIMPLE",
    "MAINTENANCE",
    "ACTION",
    "SAFE_DEFAULT",
})

# Profiles that map to the cloud tier
_CLOUD_PROFILES = frozenset({
    "RESEARCH",
    "VERIFICATION",
    "CALIBRATION",
    "AUTONOMOUS",
})


class JagaModelRouter:
    """
    Wraps ModelSwitchboard for MASFactory node-level model routing.

    Usage::

        router = JagaModelRouter()
        model_id = router.route(dispatch_package)
        # → "ollama/qwen2.5:3b" or "anthropic/claude-sonnet-4-6"
    """

    def __init__(
        self,
        workspace: Path | str | None = None,
        config_path: Path | str | None = None,
        local_model: str = _LOCAL_MODEL,
        cloud_model: str = _CLOUD_MODEL,
    ):
        """
        Parameters
        ----------
        workspace:
            AutoJaga workspace directory.
        config_path:
            Path to model config JSON. Defaults to ~/.jagabot/config.json.
        local_model:
            LiteLLM model identifier for routine (local) work.
        cloud_model:
            LiteLLM model identifier for complex/reasoning work.
        """
        self.workspace = Path(workspace) if workspace else Path.home() / ".jagabot"
        self.local_model = local_model
        self.cloud_model = cloud_model

        cfg = Path(config_path) if config_path else self.workspace / "config.json"

        if _SWITCHBOARD_AVAILABLE:
            try:
                self._switchboard = ModelSwitchboard(
                    config_path=cfg,
                    workspace=self.workspace,
                )
            except Exception as exc:
                logger.warning(f"ModelSwitchboard init failed: {exc} — using profile map only.")
                self._switchboard = None
        else:
            self._switchboard = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route(self, dispatch_package: Any) -> str:
        """
        Determine the model identifier to use for this dispatch package.

        Falls back through three layers:
        1. Try ModelSwitchboard.resolve_model() for config-driven routing.
        2. Fall back to static profile map (_LOCAL_PROFILES / _CLOUD_PROFILES).
        3. If profile is unknown, use local model as safe default.

        Parameters
        ----------
        dispatch_package:
            AutoJaga DispatchPackage (or any object with a .profile attribute).

        Returns
        -------
        str — LiteLLM model identifier ready to pass to litellm.completion().
        """
        profile = getattr(dispatch_package, "profile", "SAFE_DEFAULT")
        confidence = 1.0

        # Layer 1: ModelSwitchboard (config-driven)
        if self._switchboard is not None:
            try:
                model_config = self._switchboard.resolve_model(
                    profile=profile,
                    confidence=confidence,
                    manual_override=None,
                )
                model_id = model_config.model_id
                # Wrap with LiteLLM provider prefix if not already prefixed
                if "/" not in model_id:
                    provider = getattr(model_config, "provider", "")
                    if provider:
                        model_id = f"{provider}/{model_id}"
                logger.debug(f"JagaModelRouter: Switchboard → {model_id} ({model_config.reason})")
                return model_id
            except Exception as exc:
                logger.warning(f"ModelSwitchboard.resolve_model() failed: {exc} — falling back.")

        # Layer 2: Static profile map
        model_id = self._profile_to_model(profile)
        logger.debug(f"JagaModelRouter: Profile map → {model_id} (profile={profile})")
        return model_id

    def route_by_profile(self, profile: str) -> str:
        """Convenience method — route by profile string directly."""
        return self._profile_to_model(profile)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _profile_to_model(self, profile: str) -> str:
        """Map an AutoJaga profile string to a LiteLLM model identifier."""
        if profile in _LOCAL_PROFILES:
            return self.local_model
        if profile in _CLOUD_PROFILES:
            return self.cloud_model
        # Unknown profile — safe default is local (no API key needed)
        logger.warning(
            f"JagaModelRouter: unknown profile '{profile}' — defaulting to local model."
        )
        return self.local_model
