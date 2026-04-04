"""
mangliwood_swarm.py — Mangliwood Research Swarm Graph
======================================================
Demo graph showing a 5-agent BDI-powered research swarm investigating
Styrax sumatrana (Mangliwood) specimens from Peninsular Malaysia.

Graph topology:
    entry → conductor → [botanist, chemist, pathologist] → synthesiser → exit

Each node is a JagaBDIAgent backed by AutoJaga's CognitiveStack.
Simple specialist queries route to local Qwen; complex synthesis routes to Claude.

Usage::

    from AutoJagaMAS.graphs.mangliwood_swarm import build_mangliwood_swarm
    graph = build_mangliwood_swarm()
    result = graph.run("Styrax sumatrana density records Malaysia")
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_MODULE_DIR = Path(__file__).resolve().parent.parent  # AutoJagaMAS/
if str(_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_MODULE_DIR))

# ---------------------------------------------------------------------------
# MASFactory import — graceful fallback
# ---------------------------------------------------------------------------
try:
    from masfactory.graphs.root_graph import RootGraph
    _MASFACTORY_AVAILABLE = True
except ImportError:
    _MASFACTORY_AVAILABLE = False
    RootGraph = None  # type: ignore[assignment,misc]
    logger.warning(
        "masfactory not installed — build_mangliwood_swarm() will return a stub graph. "
        "Install masfactory>=0.1.0 for production use."
    )

# ---------------------------------------------------------------------------
# Local imports
# ---------------------------------------------------------------------------
from agents.jaga_bdi_agent import JagaBDIAgent


# ---------------------------------------------------------------------------
# Stub graph for environments without MASFactory
# ---------------------------------------------------------------------------

class _StubGraph:
    """
    Minimal swarm runner used when MASFactory is not installed.

    Executes agents sequentially (not in parallel) so smoke tests pass
    without a real graph framework installed.
    """

    def __init__(self, name: str, nodes: list[tuple[str, Any]], edges: list[tuple[str, str]]):
        self.name = name
        self._nodes: dict[str, Any] = {n: agent for n, agent in nodes}
        self._edges = edges

    def run(self, query: str, **kwargs) -> dict:
        """Run the swarm sequentially and collect results."""
        results: dict[str, Any] = {}
        messages = [{"role": "user", "content": query}]

        # Simple sequential execution following edge order
        visited: set = set()
        for src, dst in self._edges:
            if dst in ("entry", "exit"):
                continue
            if dst not in visited and dst in self._nodes:
                agent = self._nodes[dst]
                try:
                    response = agent.think(messages=messages)
                    results[dst] = response
                    # Append agent output as assistant message for next agent
                    content = response.get("content", "")
                    if content:
                        messages.append({"role": "assistant", "content": f"[{dst}]: {content}"})
                except Exception as exc:
                    logger.error(f"Agent {dst} failed: {exc}")
                    results[dst] = {"content": f"[error: {exc}]", "bdi_metadata": {}}
                visited.add(dst)

        # Return synthesiser output as primary result
        synthesiser_result = results.get("synthesiser", {})
        return {
            "output": synthesiser_result.get("content", ""),
            "node_results": results,
            "bdi_metadata": synthesiser_result.get("bdi_metadata", {}),
        }


# ---------------------------------------------------------------------------
# Graph factory
# ---------------------------------------------------------------------------

def build_mangliwood_swarm(
    workspace: Path | str | None = None,
    model1_id: str = "ollama/qwen2.5:3b",
    model2_id: str = "anthropic/claude-sonnet-4-6",
) -> Any:
    """
    Build the Mangliwood research swarm graph.

    Parameters
    ----------
    workspace:
        AutoJaga workspace directory (passed to each agent).
    model1_id:
        LiteLLM model identifier for the fast/local tier.
    model2_id:
        LiteLLM model identifier for the cloud/reasoning tier.

    Returns
    -------
    RootGraph (or _StubGraph if MASFactory is not installed).
    The graph exposes a .run(query: str) method.
    """
    common = dict(workspace=workspace, model1_id=model1_id, model2_id=model2_id)

    # ── Nodes ──────────────────────────────────────────────────────────
    # Each tuple: (node_name, agent_instance)
    nodes = [
        # Conductor: orchestrates the swarm, uses cloud model (complex synthesis)
        ("conductor",   JagaBDIAgent(persona="conductor",   **common)),

        # Botanist: morphology/ecology specialist, uses local model (retrieval tasks)
        ("botanist",    JagaBDIAgent(persona="botanist",    **common)),

        # Chemist: resin composition specialist, uses local model (retrieval tasks)
        ("chemist",     JagaBDIAgent(persona="chemist",     **common)),

        # Pathologist: disease/resistance specialist, uses local model (retrieval tasks)
        ("pathologist", JagaBDIAgent(persona="pathologist", **common)),

        # Synthesiser: combines all findings into research brief, uses cloud model
        ("synthesiser", JagaBDIAgent(persona="synthesiser", **common)),
    ]

    # ── Edges ──────────────────────────────────────────────────────────
    edges = [
        # Entry → Conductor: query arrives, conductor decomposes it
        ("entry",       "conductor"),

        # Conductor → 3 specialists (fan-out, can run in parallel)
        ("conductor",   "botanist"),
        ("conductor",   "chemist"),
        ("conductor",   "pathologist"),

        # 3 specialists → Synthesiser (fan-in, waits for all three)
        ("botanist",    "synthesiser"),
        ("chemist",     "synthesiser"),
        ("pathologist", "synthesiser"),

        # Synthesiser → Exit: research brief delivered
        ("synthesiser", "exit"),
    ]

    if _MASFACTORY_AVAILABLE and RootGraph is not None:
        # Build a real MASFactory graph
        return RootGraph(
            name="mangliwood_research",
            nodes=nodes,
            edges=edges,
        )
    else:
        # Stub graph for environments without MASFactory
        logger.warning("Using _StubGraph — install masfactory for full graph support.")
        return _StubGraph(name="mangliwood_research", nodes=nodes, edges=edges)
