"""
JagaBDIContextProvider — Adapter 1
===================================
Wraps AutoJaga's FluidDispatcher as a MASFactory ContextProvider.

In plain English
----------------
Think of this as a smart receptionist at a Malaysian government office.
When a visitor (query) arrives, the receptionist doesn't just hand them a
number — she quickly reads their request, decides which department they need
(RESEARCH, MAINTENANCE, ACTION, etc.) and packages up the relevant files and
tools before sending them to the right counter. That packaged bundle is the
DispatchPackage. This adapter converts that bundle into MASFactory's
ContextBlock format so any MASFactory graph node can consume it.

MASFactory API
--------------
- ContextProvider ABC: masfactory/adapters/context/provider.py
- ContextBlock dataclass: masfactory/adapters/context/types.py
  Fields: text, uri, chunk_id, score, title, metadata (dict)
- ContextQuery dataclass: masfactory/adapters/context/types.py
  Fields: query_text, inputs, attributes, node_name

AutoJaga API used
-----------------
- FluidDispatcher.dispatch() → DispatchPackage
  DispatchPackage fields: profile, context, tools (set), engines_active (list),
  engines_dormant (list), token_estimate (int), trigger_reason, dispatch_ms,
  k1_assisted (bool)
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MASFactory import — graceful fallback for environments without MASFactory
# ---------------------------------------------------------------------------
try:
    from masfactory.adapters.context.provider import ContextProvider
    from masfactory.adapters.context.types import ContextBlock, ContextQuery
    _MASFACTORY_AVAILABLE = True
except ImportError:
    _MASFACTORY_AVAILABLE = False

    # Minimal stubs so the module is importable and testable without MASFactory
    class ContextProvider:  # type: ignore[no-redef]
        """Stub ContextProvider for environments without MASFactory installed."""
        def get_blocks(self, query, *, top_k: int = 8):
            raise NotImplementedError

    class ContextQuery:  # type: ignore[no-redef]
        """Stub ContextQuery."""
        def __init__(self, query_text: str = "", inputs=None, attributes=None, node_name: str = ""):
            self.query_text = query_text
            self.inputs = inputs or {}
            self.attributes = attributes or {}
            self.node_name = node_name

    class ContextBlock:  # type: ignore[no-redef]
        """Stub ContextBlock."""
        def __init__(self, *, text: str, uri: str = "", chunk_id: str = "",
                     score: float = 1.0, title: str = "", metadata: dict | None = None):
            self.text = text
            self.uri = uri
            self.chunk_id = chunk_id
            self.score = score
            self.title = title
            self.metadata = metadata or {}

    logger.warning(
        "masfactory not installed — JagaBDIContextProvider running in stub mode. "
        "Install masfactory>=0.1.0 for production use."
    )

# ---------------------------------------------------------------------------
# AutoJaga FluidDispatcher import
# ---------------------------------------------------------------------------
_LEGACY_ROOT = Path(__file__).resolve().parent.parent.parent / "legacy"
if str(_LEGACY_ROOT) not in sys.path:
    sys.path.insert(0, str(_LEGACY_ROOT))

try:
    from jagabot.core.fluid_dispatcher import FluidDispatcher, DispatchPackage
    _FLUID_AVAILABLE = True
except ImportError:
    _FLUID_AVAILABLE = False
    FluidDispatcher = None  # type: ignore[assignment,misc]
    DispatchPackage = None  # type: ignore[assignment,misc]
    logger.warning("legacy jagabot not importable — FluidDispatcher unavailable.")


# ---------------------------------------------------------------------------
# Provider implementation
# ---------------------------------------------------------------------------

class JagaBDIContextProvider(ContextProvider):
    """
    Wraps AutoJaga's FluidDispatcher as a MASFactory ContextProvider.

    Each call to get_blocks() dispatches the query through the BDI engine and
    returns two ContextBlocks:

    1. **context_text** — the pre-built system context string from the dispatch
       package (core identity, tool list, profile preamble).
    2. **bdi_state** — machine-readable BDI metadata: profile, active/dormant
       engines, available tools, token estimate, and k1-assisted flag. Stored
       as JSON-safe values in ContextBlock.metadata so downstream nodes can
       branch on cognitive state without parsing free text.
    """

    def __init__(self, workspace: Path | str | None = None, k1_tool=None):
        """
        Parameters
        ----------
        workspace:
            Path to the AutoJaga workspace directory (contains memory/, AGENTS.md, etc.).
            Defaults to ~/.jagabot if not supplied.
        k1_tool:
            Optional K1 Bayesian tool to wire into the dispatcher for confidence-
            adjusted routing. Can be None for standalone use.
        """
        if workspace is None:
            workspace = Path.home() / ".jagabot"
        self.workspace = Path(workspace)

        if not _FLUID_AVAILABLE:
            self._dispatcher = None
            logger.warning("FluidDispatcher not available — get_blocks() will return empty list.")
            return

        self._dispatcher = FluidDispatcher(
            workspace=self.workspace,
            k1_tool=k1_tool,
        )

    # ------------------------------------------------------------------
    # ContextProvider interface
    # ------------------------------------------------------------------

    def get_blocks(self, query: ContextQuery, *, top_k: int = 8) -> list:
        """
        Dispatch the query through AutoJaga's BDI engine and return context blocks.

        Parameters
        ----------
        query:
            MASFactory ContextQuery with query_text, inputs, attributes, node_name.
        top_k:
            Maximum number of blocks to return (unused beyond first 2 for now,
            reserved for future multi-context expansion).

        Returns
        -------
        list[ContextBlock]
            Typically two blocks: one for context text, one for BDI state.
        """
        if self._dispatcher is None:
            return []

        query_text = getattr(query, "query_text", str(query))

        try:
            package: DispatchPackage = self._dispatcher.dispatch(
                user_input=query_text,
                topic="general",
                confidence=1.0,
                has_pending=False,
            )
        except Exception as exc:
            logger.error(f"FluidDispatcher.dispatch() failed: {exc}")
            return []

        blocks = []

        # Block 1: context text (system prompt preamble from dispatch package)
        if package.context:
            blocks.append(
                ContextBlock(
                    text=package.context,
                    uri="autojaga://fluid_dispatcher/context",
                    chunk_id=f"ctx_{package.profile}",
                    score=1.0,
                    title=f"AutoJaga BDI Context [{package.profile}]",
                    metadata={
                        "source": "FluidDispatcher",
                        "profile": package.profile,
                        "token_estimate": package.token_estimate,
                    },
                )
            )

        # Block 2: BDI state metadata
        # DispatchPackage.tools is a set — not directly JSON-serialisable, so convert to list.
        blocks.append(
            ContextBlock(
                text=(
                    f"BDI Profile: {package.profile}\n"
                    f"Active engines: {', '.join(package.engines_active) or 'none'}\n"
                    f"Dormant engines: {', '.join(package.engines_dormant) or 'none'}\n"
                    f"Available tools: {', '.join(sorted(str(t) for t in package.tools)) or 'none'}\n"
                    f"Trigger reason: {package.trigger_reason}\n"
                    f"K1 assisted: {package.k1_assisted}"
                ),
                uri="autojaga://fluid_dispatcher/bdi_state",
                chunk_id=f"bdi_{package.profile}",
                score=0.95,
                title="AutoJaga BDI State",
                metadata={
                    "source": "FluidDispatcher",
                    "profile": package.profile,
                    "engines_active": package.engines_active,
                    "engines_dormant": package.engines_dormant,
                    "tools": sorted(str(t) for t in package.tools),
                    "token_estimate": package.token_estimate,
                    "trigger_reason": package.trigger_reason,
                    "dispatch_ms": package.dispatch_ms,
                    "k1_assisted": package.k1_assisted,
                },
            )
        )

        return blocks[:top_k]
