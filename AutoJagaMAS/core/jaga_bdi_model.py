"""
JagaBDIModel — Adapter 2
=========================
Wraps AutoJaga's CognitiveStack as a MASFactory Model adapter.

In plain English
----------------
Think of this as the department manager who receives the packaged file from
the receptionist (JagaBDIContextProvider) and decides whether to handle the
request with a junior staff member (Model 1 — Qwen 3B local) or escalate to
the senior partner (Model 2 — Claude Sonnet). The manager's decision logic
lives in CognitiveStack. This adapter translates between MASFactory's
invoke() contract and CognitiveStack's async process() call.

MASFactory API
--------------
- Model ABC: masfactory/adapters/model.py
  invoke(messages: list[dict], tools: list[dict]|None, settings: dict|None=None, **kwargs) -> dict
- Return dict must contain: type (ModelResponseType), content (str)
- ModelResponseType enum: CONTENT = "content", TOOL_CALL = "tool_call"

AutoJaga API used
-----------------
- CognitiveStack.process(query, profile, context, tools, agent_runner) → StackResult
  StackResult fields: output, complexity, model1_calls, model2_calls,
  plan_steps, escalated, repaired, total_tokens, elapsed_ms
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MASFactory import — graceful fallback
# ---------------------------------------------------------------------------
try:
    from masfactory.adapters.model import Model, ModelResponseType
    _MASFACTORY_AVAILABLE = True
except ImportError:
    _MASFACTORY_AVAILABLE = False

    class ModelResponseType:  # type: ignore[no-redef]
        CONTENT = "content"
        TOOL_CALL = "tool_call"

    class Model:  # type: ignore[no-redef]
        """Stub Model for environments without MASFactory."""
        def invoke(self, messages, tools=None, settings=None, **kwargs):
            raise NotImplementedError

    logger.warning(
        "masfactory not installed — JagaBDIModel running in stub mode. "
        "Install masfactory>=0.1.0 for production use."
    )

# ---------------------------------------------------------------------------
# AutoJaga CognitiveStack import
# ---------------------------------------------------------------------------
_LEGACY_ROOT = Path(__file__).resolve().parent.parent.parent / "legacy"
if str(_LEGACY_ROOT) not in sys.path:
    sys.path.insert(0, str(_LEGACY_ROOT))

try:
    from jagabot.core.cognitive_stack import CognitiveStack
    _STACK_AVAILABLE = True
except ImportError:
    _STACK_AVAILABLE = False
    CognitiveStack = None  # type: ignore[assignment,misc]
    logger.warning("legacy jagabot not importable — CognitiveStack unavailable.")


# ---------------------------------------------------------------------------
# Helper: run async coroutine from sync context
# ---------------------------------------------------------------------------

def _run_async(coro):
    """
    Run an async coroutine from a sync context.
    Uses existing event loop if one is running (e.g., inside Jupyter or an
    already-async framework); otherwise creates a new one.
    """
    try:
        loop = asyncio.get_running_loop()
        # We're inside an already-running loop — use nest_asyncio if available,
        # otherwise fall back to a thread pool.
        try:
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(coro)
        except ImportError:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
    except RuntimeError:
        # No running loop — create a new one
        return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Model implementation
# ---------------------------------------------------------------------------

class JagaBDIModel(Model):
    """
    MASFactory Model adapter backed by AutoJaga's CognitiveStack.

    Extracts the user query from the last user message in `messages`, routes it
    through CognitiveStack's two-tier architecture (Model 1 → Model 2 escalation
    if needed), and returns a standard MASFactory response dict that also carries
    BDI state metadata for downstream graph nodes to consume.
    """

    def __init__(
        self,
        model1_id: str = "ollama/qwen2.5:3b",
        model2_id: str = "anthropic/claude-sonnet-4-6",
        workspace: Path | str | None = None,
        calibration_mode: bool = False,
    ):
        """
        Parameters
        ----------
        model1_id:
            LiteLLM model identifier for the fast/cheap tier (default: local Ollama Qwen).
        model2_id:
            LiteLLM model identifier for the smart/reasoning tier (default: Claude Sonnet).
        workspace:
            Path to AutoJaga workspace directory.
        calibration_mode:
            If True, route all queries through Model 2 (calibration profile).
        """
        self.model1_id = model1_id
        self.model2_id = model2_id
        self.workspace = Path(workspace) if workspace else Path.home() / ".jagabot"
        self.calibration_mode = calibration_mode

        if not _STACK_AVAILABLE:
            self._stack = None
            logger.warning("CognitiveStack not available — invoke() will return error response.")
            return

        self._stack = CognitiveStack(
            model1_id=model1_id,
            model2_id=model2_id,
            calibration_mode=calibration_mode,
        )

    # ------------------------------------------------------------------
    # Model interface
    # ------------------------------------------------------------------

    def invoke(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        settings: dict | None = None,
        **kwargs: Any,
    ) -> dict:
        """
        Invoke the CognitiveStack for the given conversation messages.

        Parameters
        ----------
        messages:
            OpenAI-format message list: [{"role": "user"|"assistant"|"system", "content": "..."}]
        tools:
            Optional list of tool schema dicts (passed to CognitiveStack as tool names).
        settings:
            Optional dict with override settings: profile, context, calibration_mode.

        Returns
        -------
        dict with keys:
            type:         ModelResponseType.CONTENT (or TOOL_CALL if tool is requested)
            content:      str — the generated response text
            bdi_metadata: dict — BDI state from CognitiveStack (complexity, model tiers, etc.)
        """
        if self._stack is None:
            return {
                "type": ModelResponseType.CONTENT,
                "content": "[AutoJagaMAS] CognitiveStack not available — check legacy/ imports.",
                "bdi_metadata": {},
            }

        # Extract the user query from the last user message
        query = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                query = msg.get("content", "")
                break
        if not query:
            query = messages[-1].get("content", "") if messages else ""

        # Extract optional overrides from settings
        settings = settings or {}
        profile = settings.get("profile", "SAFE_DEFAULT")
        context = settings.get("context", "")
        if "calibration_mode" in settings:
            self._stack.calibration_mode = settings["calibration_mode"]

        # Convert tool list to set of tool names (CognitiveStack expects a set)
        tool_names: set = set()
        if tools:
            for t in tools:
                name = t.get("name") or t.get("function", {}).get("name", "")
                if name:
                    tool_names.add(name)

        # Run CognitiveStack.process() — it's async, we bridge it here
        try:
            result = _run_async(
                self._stack.process(
                    query=query,
                    profile=profile,
                    context=context,
                    tools=tool_names,
                    agent_runner=None,  # no live agent_runner in adapter context
                )
            )
        except Exception as exc:
            logger.error(f"CognitiveStack.process() failed: {exc}")
            return {
                "type": ModelResponseType.CONTENT,
                "content": f"[AutoJagaMAS] CognitiveStack error: {exc}",
                "bdi_metadata": {"error": str(exc)},
            }

        bdi_metadata = {
            "complexity": result.complexity,
            "model1_calls": result.model1_calls,
            "model2_calls": result.model2_calls,
            "plan_steps": result.plan_steps,
            "escalated": result.escalated,
            "repaired": result.repaired,
            "total_tokens": result.total_tokens,
            "elapsed_ms": result.elapsed_ms,
            "profile": profile,
        }

        logger.info(
            f"JagaBDIModel: {result.complexity} | "
            f"M1={result.model1_calls} M2={result.model2_calls} | "
            f"{result.elapsed_ms:.0f}ms"
        )

        return {
            "type": ModelResponseType.CONTENT,
            "content": result.output,
            "bdi_metadata": bdi_metadata,
        }
