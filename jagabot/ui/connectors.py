"""
JagabotUIBridge — single interface between the Streamlit UI and all
JAGABOT subsystems (Neo4j, KnowledgeGraph, MemoryFleet, MetaLearning,
Evolution, Subagents).

Provides graceful degradation: each subsystem initialises independently
so a Neo4j outage doesn't block the MemoryFleet, etc.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from jagabot.ui.config import UIConfig
from jagabot.ui.neo4j_connector import Neo4jConnector
from jagabot.ui.session import UISession

logger = logging.getLogger(__name__)


class JagabotUIBridge:
    """Façade that connects the Streamlit UI to every JAGABOT subsystem."""

    def __init__(self, config: UIConfig | None = None, workspace: Path | None = None):
        self.config = config or UIConfig.load()
        self._workspace = workspace or Path.home() / ".jagabot" / "workspace"
        self._workspace.mkdir(parents=True, exist_ok=True)

        # Session
        self.session = UISession()

        # --- Subsystems (initialised lazily / independently) ---
        self.neo4j: Neo4jConnector | None = None
        self._kg = None      # KnowledgeGraphViewer
        self._memory = None   # MemoryFleet
        self._meta = None     # MetaLearningEngine
        self._evo = None      # EvolutionEngine
        self._subagents = None  # SubagentManager

        self._init_subsystems()

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_subsystems(self) -> None:
        """Initialise each subsystem independently — failures are non-fatal."""
        # 1) Neo4j
        try:
            self.neo4j = Neo4jConnector(
                uri=self.config.NEO4J_URI,
                auth=self.config.neo4j_auth(),
            )
        except Exception as exc:
            logger.warning("Neo4j init failed: %s", exc)

        # 2) KnowledgeGraphViewer (file-based)
        try:
            from jagabot.agent.tools.knowledge_graph import KnowledgeGraphViewer

            self._kg = KnowledgeGraphViewer(str(self._workspace))
            self._kg.load()
        except Exception as exc:
            logger.warning("KnowledgeGraph init failed: %s", exc)

        # 3) MemoryFleet
        try:
            from jagabot.agent.tools.memory_fleet import MemoryFleet

            self._memory = MemoryFleet(self._workspace)
        except Exception as exc:
            logger.warning("MemoryFleet init failed: %s", exc)

        # 4) MetaLearningEngine
        try:
            from jagabot.engines.meta_learning import MetaLearningEngine

            self._meta = MetaLearningEngine(self._workspace)
        except Exception as exc:
            logger.warning("MetaLearning init failed: %s", exc)

        # 5) EvolutionEngine
        try:
            from jagabot.evolution.engine import EvolutionEngine

            self._evo = EvolutionEngine()
        except Exception as exc:
            logger.warning("EvolutionEngine init failed: %s", exc)

        # 6) SubagentManager
        try:
            from jagabot.subagents.manager import SubagentManager

            self._subagents = SubagentManager()
        except Exception as exc:
            logger.warning("SubagentManager init failed: %s", exc)

    # ------------------------------------------------------------------
    # Graph queries (Neo4j → fallback to file-based KG)
    # ------------------------------------------------------------------

    def get_graph(
        self, topic: str, depth: int = 2, limit: int = 50
    ) -> tuple[list[dict], list[dict]]:
        """Get (nodes, edges) for topic — tries Neo4j first, falls back to KG."""
        self.session.log_action("get_graph", {"topic": topic})

        # Try Neo4j first
        if self.neo4j and self.neo4j.connected:
            nodes, edges = self.neo4j.query_subgraph(topic, depth, limit)
            if nodes:
                return nodes, edges

        # Fallback: file-based KnowledgeGraphViewer
        if self._kg:
            try:
                self._kg.load()
                matched = self._kg.query_nodes(topic, limit)
                nodes = [
                    {
                        "id": n.get("id", ""),
                        "label": n.get("label", "")[:40],
                        "type": n.get("group", "Unknown"),
                        "properties": n,
                    }
                    for n in matched
                ]
                return nodes, []
            except Exception as exc:
                logger.error("KG fallback failed: %s", exc)

        return [], []

    def get_recent_analyses(self, limit: int = 50) -> list[dict]:
        """Return recent Analysis nodes from Neo4j."""
        self.session.log_action("get_recent_analyses")
        if self.neo4j and self.neo4j.connected:
            return self.neo4j.get_recent_analyses(limit)
        return []

    def find_gap(self, concept1: str, concept2: str) -> dict | None:
        """Find shortest path between two concepts."""
        self.session.log_action("find_gap", {"c1": concept1, "c2": concept2})
        if self.neo4j and self.neo4j.connected:
            return self.neo4j.find_path(concept1, concept2)
        return None

    def add_graph_node(
        self, name: str, node_type: str, properties: dict | None = None
    ) -> str | None:
        """Add a node to the Neo4j graph."""
        self.session.log_action("add_graph_node", {"name": name, "type": node_type})
        if self.neo4j and self.neo4j.connected:
            return self.neo4j.add_node(name, node_type, properties)
        return None

    # ------------------------------------------------------------------
    # Memory (MemoryFleet)
    # ------------------------------------------------------------------

    def save_to_memory(
        self, user_message: str, agent_response: str, topic: str | None = None
    ) -> list[str]:
        """Store an interaction in MemoryFleet. Returns event list."""
        self.session.log_action("save_to_memory", {"topic": topic})
        if self._memory:
            try:
                return self._memory.on_interaction(
                    user_message=user_message,
                    agent_response=agent_response,
                    topic=topic,
                )
            except Exception as exc:
                logger.error("save_to_memory failed: %s", exc)
        return []

    def get_memory_context(self, query: str, k: int = 3) -> str:
        """Retrieve relevant context from MemoryFleet."""
        self.session.log_action("get_memory_context", {"query": query})
        if self._memory:
            try:
                return self._memory.get_context(query, k=k)
            except Exception as exc:
                logger.error("get_memory_context failed: %s", exc)
        return ""

    # ------------------------------------------------------------------
    # MetaLearning
    # ------------------------------------------------------------------

    def track_action(self, action: str, data: dict | None = None) -> dict | None:
        """Record a UI action in MetaLearningEngine as a strategy result."""
        self.session.log_action("track_action", {"action": action})
        if self._meta:
            try:
                return self._meta.record_strategy_result(
                    strategy_name=f"ui_{action}",
                    success=True,
                    fitness_gain=0.01,
                )
            except Exception as exc:
                logger.error("track_action failed: %s", exc)
        return None

    # ------------------------------------------------------------------
    # Research (Subagents)
    # ------------------------------------------------------------------

    def research(self, topic: str) -> dict:
        """Trigger the 4-stage subagent research workflow."""
        self.session.log_action("research", {"topic": topic})
        if self._subagents:
            try:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                if loop and loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        result = pool.submit(
                            asyncio.run,
                            self._subagents.execute_workflow(topic),
                        ).result(timeout=30)
                    return result
                else:
                    return asyncio.run(
                        self._subagents.execute_workflow(topic)
                    )
            except Exception as exc:
                logger.error("research failed: %s", exc)
                return {"success": False, "error": str(exc)}
        return {"success": False, "error": "SubagentManager not available"}

    # ------------------------------------------------------------------
    # Evolution
    # ------------------------------------------------------------------

    def get_evolution_status(self) -> dict:
        """Return EvolutionEngine status."""
        self.session.log_action("get_evolution_status")
        if self._evo:
            try:
                return self._evo.get_status()
            except Exception as exc:
                logger.error("get_evolution_status failed: %s", exc)
        return {"error": "EvolutionEngine not available"}

    # ------------------------------------------------------------------
    # Combined stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return combined statistics from all subsystems."""
        stats: dict[str, Any] = {"session": self.session.get_summary()}

        # Neo4j
        if self.neo4j:
            stats["neo4j"] = self.neo4j.get_stats()
        else:
            stats["neo4j"] = {"connected": False}

        # KG file-based
        if self._kg:
            try:
                stats["knowledge_graph"] = self._kg.get_stats()
            except Exception:
                stats["knowledge_graph"] = {"error": "unavailable"}

        # Memory
        if self._memory:
            try:
                stats["memory"] = {
                    "fractal_nodes": self._memory.fractal.total_count,
                    "pending_consolidation": self._memory.fractal.pending_count,
                }
            except Exception:
                stats["memory"] = {"error": "unavailable"}

        # Evolution
        if self._evo:
            try:
                stats["evolution"] = self._evo.get_status()
            except Exception:
                stats["evolution"] = {"error": "unavailable"}

        return stats

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Clean up connections."""
        if self.neo4j:
            self.neo4j.close()
