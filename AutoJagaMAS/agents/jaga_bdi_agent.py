"""
JagaBDIAgent — MASFactory Agent subclass with AutoJaga BDI cognitive stack.

Subclasses MASFactory's Agent (not DynamicAgent) because we control the
instructions via persona YAML files — dynamic instruction injection is not
needed here.

In plain English
----------------
Each specialist researcher in the Mangliwood swarm (botanist, chemist, etc.)
is a JagaBDIAgent. They have a fixed role defined by their persona YAML
(like a job description on file), but their thinking is powered by
AutoJaga's two-tier CognitiveStack — so a simple question goes to the
fast local Qwen model, while a complex analysis escalates to Claude Sonnet.

The think() method is overridden to inject BDI state (profile, complexity,
escalation flag) into the response metadata so the graph edges can carry
cognitive state from node to node.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MASFactory import — graceful fallback
# ---------------------------------------------------------------------------
try:
    from masfactory.components.agents.agent import Agent
    _MASFACTORY_AVAILABLE = True
except ImportError:
    _MASFACTORY_AVAILABLE = False

    class Agent:  # type: ignore[no-redef]
        """Stub Agent for environments without MASFactory installed."""
        def __init__(self, name: str, instructions: str, model=None, **kwargs):
            self.name = name
            self.instructions = instructions
            self._model = model

        def think(self, messages: list[dict], settings: dict | None = None) -> dict:
            raise NotImplementedError

        def step(self, input_dict: dict) -> dict:
            raise NotImplementedError

    logger.warning(
        "masfactory not installed — JagaBDIAgent running in stub mode. "
        "Install masfactory>=0.1.0 for production use."
    )

# ---------------------------------------------------------------------------
# JagaBDIModel import (Adapter 2)
# ---------------------------------------------------------------------------
_MODULE_DIR = Path(__file__).resolve().parent.parent  # AutoJagaMAS/
sys.path.insert(0, str(_MODULE_DIR))

try:
    from core.jaga_bdi_model import JagaBDIModel
    _MODEL_AVAILABLE = True
except ImportError:
    _MODEL_AVAILABLE = False
    JagaBDIModel = None  # type: ignore[assignment,misc]
    logger.warning("JagaBDIModel not importable — JagaBDIAgent will use None model.")

# Path to persona YAML files
_PERSONAS_DIR = _MODULE_DIR / "personas"


# ---------------------------------------------------------------------------
# Agent implementation
# ---------------------------------------------------------------------------

class JagaBDIAgent(Agent):
    """
    MASFactory Agent subclass powered by AutoJaga's CognitiveStack.

    Parameters
    ----------
    persona:
        Name of the persona YAML file (without .yaml extension).
        E.g., "conductor" loads AutoJagaMAS/personas/conductor.yaml.
    workspace:
        Optional path to AutoJaga workspace directory.
    model1_id:
        Override for Model 1 (fast/local tier). Persona YAML may also specify
        model_preference which takes precedence.
    model2_id:
        Override for Model 2 (cloud/reasoning tier).
    **kwargs:
        Passed through to Agent.__init__().
    """

    def __init__(
        self,
        persona: str,
        workspace: Path | str | None = None,
        model1_id: str = "ollama/qwen2.5:3b",
        model2_id: str = "anthropic/claude-sonnet-4-6",
        **kwargs: Any,
    ):
        self.persona_name = persona
        self._persona_data = self._load_persona(persona)
        self._bdi_state: dict = {}

        # Resolve model IDs (persona YAML may override)
        pref = self._persona_data.get("model_preference", "")
        if pref == "local":
            model1_id = model1_id  # keep local tier as primary
        elif pref == "cloud":
            model1_id = model2_id  # prefer cloud tier

        # Build the BDI-backed model
        if _MODEL_AVAILABLE:
            bdi_model = JagaBDIModel(
                model1_id=model1_id,
                model2_id=model2_id,
                workspace=workspace,
            )
        else:
            bdi_model = None

        # Build system instructions from persona
        role = self._persona_data.get("role", persona)
        system_prompt = self._persona_data.get("system_prompt", f"You are a {role}.")

        super().__init__(
            name=role,
            instructions=system_prompt,
            model=bdi_model,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Core override: think()
    # ------------------------------------------------------------------

    def think(self, messages: list[dict], settings: dict | None = None) -> dict:
        """
        Override Agent.think() to inject BDI state into response metadata.

        Calls the underlying JagaBDIModel.invoke(), then attaches BDI metadata
        to the response so graph edges can carry cognitive state downstream.

        Parameters
        ----------
        messages:
            OpenAI-format message list.
        settings:
            Optional settings dict (passed through to model.invoke()).

        Returns
        -------
        dict — MASFactory model response with added 'bdi_metadata' and 'persona' keys.
        """
        if self._model is None:
            return {
                "type": "content",
                "content": "[JagaBDIAgent] No model available.",
                "bdi_metadata": {},
                "persona": self.persona_name,
            }

        # Inject persona context into settings
        effective_settings = dict(settings or {})
        engines_active = self._persona_data.get("engines_active", [])
        if engines_active:
            effective_settings.setdefault("engines_active", engines_active)

        response = self._model.invoke(
            messages=messages,
            tools=None,
            settings=effective_settings,
        )

        # Attach BDI metadata for graph edge propagation
        bdi_meta = response.get("bdi_metadata", {})
        bdi_meta["persona"] = self.persona_name
        bdi_meta["role"] = self._persona_data.get("role", self.persona_name)
        bdi_meta["engines_active"] = engines_active
        self._bdi_state = bdi_meta

        response["bdi_metadata"] = bdi_meta
        response["persona"] = self.persona_name
        return response

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def bdi_state(self) -> dict:
        """Return the last BDI state from think(). Useful for graph introspection."""
        return self._bdi_state

    @staticmethod
    def _load_persona(persona_name: str) -> dict:
        """
        Load persona YAML from personas/ directory.

        Returns empty dict if file not found (graceful degradation).
        """
        yaml_path = _PERSONAS_DIR / f"{persona_name}.yaml"
        if not yaml_path.exists():
            logger.warning(f"Persona file not found: {yaml_path} — using defaults.")
            return {}
        try:
            with open(yaml_path, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            logger.debug(f"Loaded persona: {persona_name} ({data.get('role', '?')})")
            return data
        except Exception as exc:
            logger.error(f"Failed to load persona {persona_name}: {exc}")
            return {}
