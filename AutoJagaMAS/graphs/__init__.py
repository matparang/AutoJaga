"""AutoJagaMAS graphs — MASFactory graph definitions for multi-agent workflows."""

from .mangliwood_swarm import build_mangliwood_swarm
from .base_mas_template import build_mas_graph

__all__ = ["build_mangliwood_swarm", "build_mas_graph"]
