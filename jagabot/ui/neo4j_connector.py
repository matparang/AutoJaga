"""
Neo4jConnector — thin wrapper around the Neo4j Python driver.

Provides graph queries used by the Streamlit Knowledge Graph UI.
Gracefully degrades when Neo4j is unavailable.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Optional import — allows codebase to work without neo4j installed
try:
    from neo4j import GraphDatabase
    from neo4j.exceptions import ServiceUnavailable, AuthError

    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False

    class ServiceUnavailable(Exception):  # type: ignore[no-redef]
        pass

    class AuthError(Exception):  # type: ignore[no-redef]
        pass


class Neo4jConnector:
    """Manages a single Neo4j driver instance with graceful fallback."""

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        auth: tuple[str, str] | None = None,
    ):
        self.uri = uri
        self.auth = auth
        self.driver = None
        self._connected = False

        if not NEO4J_AVAILABLE:
            logger.warning("neo4j package not installed — running in offline mode")
            return

        try:
            self.driver = GraphDatabase.driver(uri, auth=auth)
            self.driver.verify_connectivity()
            self._connected = True
            logger.info("Neo4j connected at %s", uri)
        except (ServiceUnavailable, AuthError, OSError) as exc:
            logger.warning("Neo4j unavailable (%s) — running in offline mode", exc)
            self.driver = None
            self._connected = False

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._connected and self.driver is not None

    def verify_connection(self) -> bool:
        """Return True if Neo4j is reachable."""
        if not self.driver:
            return False
        try:
            self.driver.verify_connectivity()
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Graph queries
    # ------------------------------------------------------------------

    def query_subgraph(
        self, topic: str, depth: int = 2, limit: int = 50
    ) -> tuple[list[dict], list[dict]]:
        """Return (nodes, edges) matching *topic* up to *depth* hops.

        Returns empty lists if disconnected.
        """
        if not self.connected:
            return [], []

        nodes: dict[int, dict] = {}
        edges: list[dict] = []

        depth = max(1, min(int(depth), 5))  # sanitise

        try:
            with self.driver.session() as session:
                result = session.run(
                    """
                    MATCH path = (n)-[r*1..%d]-(m)
                    WHERE any(prop IN keys(n)
                              WHERE toString(n[prop]) CONTAINS $topic)
                    RETURN path
                    LIMIT $limit
                    """
                    % depth,
                    topic=topic,
                    limit=limit,
                )
                for record in result:
                    path = record["path"]
                    for node in path.nodes:
                        if node.element_id not in nodes:
                            nodes[node.element_id] = self._node_to_dict(node)
                    for rel in path.relationships:
                        edges.append(
                            {
                                "from": rel.start_node.element_id,
                                "to": rel.end_node.element_id,
                                "label": rel.type,
                            }
                        )
        except Exception as exc:
            logger.error("query_subgraph failed: %s", exc)

        return list(nodes.values()), edges

    def get_recent_analyses(self, limit: int = 50) -> list[dict]:
        """Return Analysis nodes ordered by timestamp desc."""
        if not self.connected:
            return []

        analyses: list[dict] = []
        try:
            with self.driver.session() as session:
                result = session.run(
                    """
                    MATCH (a:Analysis)
                    RETURN a
                    ORDER BY a.timestamp DESC
                    LIMIT $limit
                    """,
                    limit=limit,
                )
                for record in result:
                    a = record["a"]
                    analyses.append(
                        {
                            "id": a.get("id", ""),
                            "query": str(a.get("query", ""))[:80],
                            "timestamp": a.get("timestamp", ""),
                            "probability": a.get("probability", 0),
                            "result": a.get("result", ""),
                        }
                    )
        except Exception as exc:
            logger.error("get_recent_analyses failed: %s", exc)

        return analyses

    def find_path(
        self, concept1: str, concept2: str, max_depth: int = 5
    ) -> dict | None:
        """Find shortest path between two concepts. Returns dict or None."""
        if not self.connected:
            return None

        try:
            with self.driver.session() as session:
                result = session.run(
                    """
                    MATCH (n1), (n2)
                    WHERE any(p IN keys(n1) WHERE toString(n1[p]) CONTAINS $c1)
                      AND any(p IN keys(n2) WHERE toString(n2[p]) CONTAINS $c2)
                    WITH n1, n2 LIMIT 1
                    MATCH path = shortestPath((n1)-[*..%d]-(n2))
                    RETURN path
                    """
                    % max_depth,
                    c1=concept1,
                    c2=concept2,
                )
                record = result.single()
                if not record:
                    return None

                path = record["path"]
                path_nodes = [self._node_to_dict(n) for n in path.nodes]
                path_rels = [r.type for r in path.relationships]
                return {"nodes": path_nodes, "relationships": path_rels}
        except Exception as exc:
            logger.error("find_path failed: %s", exc)
            return None

    def get_stats(self) -> dict[str, Any]:
        """Return database-level statistics."""
        if not self.connected:
            return {"node_count": 0, "rel_count": 0, "labels": [], "connected": False}

        try:
            with self.driver.session() as session:
                nc = session.run(
                    "MATCH (n) RETURN count(n) as c"
                ).single()["c"]
                rc = session.run(
                    "MATCH ()-[r]->() RETURN count(r) as c"
                ).single()["c"]
                labels = session.run(
                    "CALL db.labels() YIELD label RETURN collect(label) as labels"
                ).single()["labels"]
            return {
                "node_count": nc,
                "rel_count": rc,
                "labels": labels,
                "connected": True,
            }
        except Exception as exc:
            logger.error("get_stats failed: %s", exc)
            return {"node_count": 0, "rel_count": 0, "labels": [], "connected": False}

    def add_node(
        self, name: str, node_type: str, properties: dict | None = None
    ) -> str | None:
        """Create a node with given label and properties. Returns element_id."""
        if not self.connected:
            return None

        props = dict(properties or {})
        props["name"] = name

        try:
            with self.driver.session() as session:
                result = session.run(
                    f"CREATE (n:{node_type} $props) RETURN elementId(n) as eid",
                    props=props,
                )
                return result.single()["eid"]
        except Exception as exc:
            logger.error("add_node failed: %s", exc)
            return None

    def close(self) -> None:
        """Close the driver."""
        if self.driver:
            try:
                self.driver.close()
            except Exception:
                pass
            self.driver = None
            self._connected = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _node_to_dict(node) -> dict:
        """Convert a Neo4j Node to a plain dict."""
        labels = list(node.labels) if node.labels else ["Unknown"]
        return {
            "id": node.element_id,
            "label": node.get("name", node.get("query", f"Node"))[:40],
            "type": labels[0],
            "properties": dict(node),
        }
