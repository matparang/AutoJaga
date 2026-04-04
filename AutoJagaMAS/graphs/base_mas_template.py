"""
base_mas_template.py — Reusable MAS Graph Template
===================================================
Factory function for building BDI-powered Multi-Agent System graphs with
AutoJaga's CognitiveStack at each node.

Use this when you want to create a new domain-specific swarm without
copy-pasting the Mangliwood setup. Define your persona configs and edge
definitions, pass them here, and get a ready-to-run graph back.

Usage::

    from AutoJagaMAS.graphs.base_mas_template import build_mas_graph

    graph = build_mas_graph(
        name="my_swarm",
        persona_configs=[
            {"node_name": "lead",    "persona": "conductor"},
            {"node_name": "analyst", "persona": "botanist"},
        ],
        edges=[
            ("entry", "lead"),
            ("lead",  "analyst"),
            ("analyst", "exit"),
        ],
    )
    result = graph.run("my query")
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
    logger.warning("masfactory not installed — build_mas_graph() will return a stub graph.")

# ---------------------------------------------------------------------------
# Local imports
# ---------------------------------------------------------------------------
from agents.jaga_bdi_agent import JagaBDIAgent


# ---------------------------------------------------------------------------
# Stub graph (same as mangliwood_swarm._StubGraph — kept here for reuse)
# ---------------------------------------------------------------------------

class _StubGraph:
    """
    Minimal sequential graph runner for use without MASFactory.
    Suitable for unit tests and CI environments without GPU/API keys.
    """

    def __init__(self, name: str, nodes: list[tuple[str, Any]], edges: list[tuple[str, str]]):
        self.name = name
        self._nodes: dict[str, Any] = {n: agent for n, agent in nodes}
        self._edges = edges

    def run(self, query: str, **kwargs) -> dict:
        messages = [{"role": "user", "content": query}]
        results: dict[str, Any] = {}
        visited: set = set()

        for src, dst in self._edges:
            if dst in ("entry", "exit"):
                continue
            if dst not in visited and dst in self._nodes:
                agent = self._nodes[dst]
                try:
                    response = agent.think(messages=messages)
                    results[dst] = response
                    content = response.get("content", "")
                    if content:
                        messages.append({"role": "assistant", "content": f"[{dst}]: {content}"})
                except Exception as exc:
                    logger.error(f"Agent {dst} failed: {exc}")
                    results[dst] = {"content": f"[error: {exc}]", "bdi_metadata": {}}
                visited.add(dst)

        last_node = None
        for _, dst in reversed(self._edges):
            if dst != "exit" and dst in results:
                last_node = dst
                break

        last_result = results.get(last_node or "", {})
        return {
            "output": last_result.get("content", ""),
            "node_results": results,
            "bdi_metadata": last_result.get("bdi_metadata", {}),
        }


# ---------------------------------------------------------------------------
# Template factory
# ---------------------------------------------------------------------------

def build_mas_graph(
    name: str,
    persona_configs: list[dict],
    edges: list[tuple[str, str]],
    workspace: Path | str | None = None,
    model1_id: str = "ollama/qwen2.5:3b",
    model2_id: str = "anthropic/claude-sonnet-4-6",
) -> Any:
    """
    Build a BDI-powered MAS graph from persona configs and edge definitions.

    Parameters
    ----------
    name:
        Graph name (used for logging and MASFactory registration).
    persona_configs:
        List of dicts, each with keys:
          - node_name (str): identifier used in edges
          - persona (str): persona YAML file name (without .yaml)
          - kwargs (dict, optional): extra kwargs for JagaBDIAgent
    edges:
        List of (source, destination) tuples defining the graph topology.
        Use "entry" and "exit" as terminal node names.
    workspace:
        AutoJaga workspace directory.
    model1_id:
        LiteLLM model identifier for the fast/local tier.
    model2_id:
        LiteLLM model identifier for the cloud/reasoning tier.

    Returns
    -------
    RootGraph or _StubGraph — exposes .run(query: str) -> dict.

    Example
    -------
    ::

        graph = build_mas_graph(
            name="climate_swarm",
            persona_configs=[
                {"node_name": "lead",      "persona": "conductor"},
                {"node_name": "physicist", "persona": "chemist"},
                {"node_name": "summary",   "persona": "synthesiser"},
            ],
            edges=[
                ("entry",     "lead"),
                ("lead",      "physicist"),
                ("physicist", "summary"),
                ("summary",   "exit"),
            ],
        )
    """
    common = dict(workspace=workspace, model1_id=model1_id, model2_id=model2_id)

    nodes = []
    for cfg in persona_configs:
        node_name = cfg["node_name"]
        persona = cfg["persona"]
        extra = cfg.get("kwargs", {})
        agent = JagaBDIAgent(persona=persona, **{**common, **extra})
        nodes.append((node_name, agent))

    if _MASFACTORY_AVAILABLE and RootGraph is not None:
        return RootGraph(name=name, nodes=nodes, edges=edges)
    else:
        logger.warning(f"Using _StubGraph for '{name}' — install masfactory for full support.")
        return _StubGraph(name=name, nodes=nodes, edges=edges)
