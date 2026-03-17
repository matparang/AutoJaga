"""
MemoryFleet tool — long-term memory: store interactions, retrieve context,
consolidate lessons, get stats, optimize memory.

Wraps jagabot.memory.* (FractalManager + ALSManager + ConsolidationEngine)
as a single Tool ABC compliant tool for the agent loop.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jagabot.agent.tools.base import Tool
from jagabot.memory.fractal_manager import FractalManager
from jagabot.memory.als_manager import ALSManager
from jagabot.memory.consolidation import ConsolidationEngine
from jagabot.memory.memory_manager import MemoryManager

# Default workspace — overridden if workspace kwarg passed at init
_DEFAULT_WORKSPACE = Path.home() / ".jagabot" / "workspace"

# Auto-consolidate after this many interactions
_CONSOLIDATION_INTERVAL = 10

# Important-keyword detection
_IMPORTANT_KEYWORDS = {
    "remember", "important", "note", "lesson", "learn",
    "never forget", "keep in mind", "save", "critical",
}


class MemoryFleet:
    """
    Coordinates three memory layers:
      - ALSManager     → ALS.json      (identity / focus / reflections)
      - FractalManager → fractal_index.json (temporary working memory)
      - ConsolidationEngine            (fractal → MEMORY.md pipeline)
    """

    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace or _DEFAULT_WORKSPACE
        self.memory_dir = self.workspace / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.als_manager = ALSManager(self.memory_dir)
        self.fractal = FractalManager(self.memory_dir)
        self.consolidation = ConsolidationEngine(self.memory_dir, self.fractal)
        self.memory_mgr = MemoryManager(self.workspace)

        self._interaction_count = 0

    def on_interaction(
        self,
        user_message: str,
        agent_response: str,
        session_key: str = "",
        topic: str | None = None,
        confidence_level: str | None = None,
        belief_score: float | None = None,
    ) -> list[str]:
        """Process a completed interaction and store in memory."""
        events: list[str] = []

        combined = f"User: {user_message}\nAgent: {agent_response}"
        is_important = _detect_important(user_message, agent_response)

        extra_tags: list[str] = []
        if topic:
            extra_tags.append(f"topic:{topic}")
        if confidence_level:
            extra_tags.append(f"conf:{confidence_level}")
        if belief_score is not None:
            extra_tags.append(f"belief:{belief_score:.2f}")

        self.fractal.save_node(
            content=combined,
            summary=_make_summary(user_message, agent_response),
            important=is_important,
            session_key=session_key,
            tags=extra_tags if extra_tags else None,
        )

        if user_message.strip():
            self.als_manager.update_focus(user_message[:100])

        self._interaction_count += 1
        if self._interaction_count % _CONSOLIDATION_INTERVAL == 0 or self.consolidation.should_consolidate():
            try:
                self.consolidation.run()
            except Exception:
                pass  # non-fatal

        return events

    def get_context(self, query: str, k: int = 3) -> str:
        """Return context string of relevant memory for prompt injection."""
        parts: list[str] = []

        identity = self.als_manager.get_identity_context()
        if identity:
            parts.append(identity)

        nodes = self.fractal.retrieve_relevant(query, k=k)
        if nodes:
            node_lines = ["## Working Memory (relevant context)"]
            for node in nodes:
                node_lines.append(f"- [{node.timestamp[:16]}] {node.summary}")
            parts.append("\n".join(node_lines))

        return "\n\n".join(parts)

    def consolidate_now(self) -> int:
        """Force an immediate consolidation. Returns nodes consolidated."""
        return self.consolidation.run(force=True)

    def optimize_memory(self, dry_run: bool = False) -> dict:
        """Run strengthen → merge → prune cycle."""
        strengthened = self.fractal.strengthen_nodes()
        merged = self.fractal.merge_similar()
        pruned = self.fractal.prune_old(dry_run=dry_run)

        return {
            "strengthened": strengthened,
            "merged": merged,
            "pruned": len(pruned),
            "remaining": self.fractal.total_count,
            "dry_run": dry_run,
        }

    def get_exposure_count(self, topic: str) -> int:
        """Return how many fractal nodes mention *topic*."""
        count = 0
        topic_lower = topic.lower()
        for node in self.fractal.get_all_nodes():
            tags = node.tags or []
            if any(topic_lower in t.lower() for t in tags):
                count += 1
            elif topic_lower in (node.summary or "").lower():
                count += 1
        return count

    def get_all_topics(self) -> list[str]:
        """Extract all unique topic-like tags from fractal memory."""
        _skip_prefixes = (
            "conf:", "belief:", "reflection_type:", "importance:",
            "target:", "score:", "cycles:", "result:", "session:",
            "type:", "msg:",
        )
        topics: set[str] = set()
        for node in self.fractal.get_all_nodes():
            for tag in (node.tags or []):
                if ":" not in tag:
                    continue
                if any(tag.startswith(p) for p in _skip_prefixes):
                    continue
                value = tag.split(":", 1)[1]
                if value in ("None", "none", "") or value.lstrip("-").replace(".", "").isdigit():
                    continue
                topics.add(tag)
        return sorted(topics)


class MemoryFleetTool(Tool):
    """Tool ABC wrapper for MemoryFleet — long-term memory management."""

    _fleet: MemoryFleet | None = None

    @property
    def name(self) -> str:
        return "memory_fleet"

    @property
    def description(self) -> str:
        return (
            "Long-term memory system with TWO search modes: "
            "(1) Semantic retrieval via fractal nodes (vector-like similarity). "
            "(2) FTS5 full-text search via SQLite (stemming, phrase search, wildcards). "
            "Use 'retrieve' for semantic search, 'search' for FTS5 text search. "
            "Also: store interactions, consolidate lessons, view stats, optimize memory."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["store", "retrieve", "search", "consolidate", "stats", "optimize"],
                    "description": (
                        "store: save an interaction to memory. "
                        "retrieve: get relevant context for a query. "
                        "search: FTS5 full-text search with stemming (NEW). "
                        "consolidate: force consolidation of important nodes into permanent memory. "
                        "stats: get memory statistics. "
                        "optimize: strengthen/merge/prune memory nodes."
                    ),
                },
                "user_message": {
                    "type": "string",
                    "description": "User message to store (for 'store' action).",
                },
                "agent_response": {
                    "type": "string",
                    "description": "Agent response to store (for 'store' action).",
                },
                "query": {
                    "type": "string",
                    "description": "Search query (for 'retrieve' or 'search' action).",
                },
                "engine": {
                    "type": "string",
                    "enum": ["fractal", "fts5"],
                    "default": "fractal",
                    "description": "For 'retrieve': 'fractal'=semantic, 'fts5'=full-text search with stemming.",
                },
                "k": {
                    "type": "integer",
                    "description": "Number of results to return (for 'retrieve', default 3).",
                },
                "topic": {
                    "type": "string",
                    "description": "Topic tag for the interaction (for 'store' action).",
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "If true, only preview what optimize would do (for 'optimize').",
                },
            },
            "required": ["action"],
        }

    def _get_fleet(self) -> MemoryFleet:
        if self._fleet is None:
            self._fleet = MemoryFleet()
        return self._fleet

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "stats")
        fleet = self._get_fleet()

        if action == "store":
            user_msg = kwargs.get("user_message", "")
            agent_resp = kwargs.get("agent_response", "")
            if not user_msg and not agent_resp:
                return json.dumps({"error": "user_message or agent_response required"})
            events = fleet.on_interaction(
                user_message=user_msg,
                agent_response=agent_resp,
                topic=kwargs.get("topic"),
            )
            return json.dumps({
                "stored": True,
                "total_nodes": fleet.fractal.total_count,
                "events": events,
            })

        elif action == "retrieve":
            query = kwargs.get("query", "")
            engine = kwargs.get("engine", "fractal")  # "fractal" or "fts5"
            k = kwargs.get("k", 3)
            
            if not query:
                return json.dumps({"error": "query required for retrieve action"})
            
            if engine == "fts5":
                # Use FTS5 full-text search
                results = fleet.memory_mgr.search(query, limit=k)
                return json.dumps({
                    "query": query,
                    "engine": "FTS5",
                    "results": [
                        {
                            "content": r.content[:200],
                            "source": r.source,
                            "date": r.date,
                            "topic": r.topic,
                            "verified": r.verified,
                            "score": r.score,
                        }
                        for r in results
                    ],
                    "total_found": len(results),
                    "search_features": ["stemming", "temporal_decay", "MMR_dedup"],
                })
            else:
                # Use fractal semantic retrieval (default)
                context = fleet.get_context(query, k=k)
                nodes = fleet.fractal.retrieve_relevant(query, k=k)
                return json.dumps({
                    "context": context,
                    "engine": "fractal",
                    "matched_nodes": len(nodes),
                    "nodes": [{"id": n.id, "summary": n.summary, "tags": n.tags, "timestamp": n.timestamp} for n in nodes],
                })

        elif action == "search":
            # FTS5 full-text search with stemming
            query = kwargs.get("query", "")
            if not query:
                return json.dumps({"error": "query required for search action"})
            limit = kwargs.get("limit", 8)
            results = fleet.memory_mgr.search(query, limit=limit)
            return json.dumps({
                "query": query,
                "results": [
                    {
                        "content": r.content[:200],
                        "source": r.source,
                        "date": r.date,
                        "topic": r.topic,
                        "verified": r.verified,
                        "score": r.score,
                    }
                    for r in results
                ],
                "total_found": len(results),
                "search_type": "FTS5 with stemming + temporal decay + MMR dedup",
            })

        elif action == "consolidate":
            count = fleet.consolidate_now()
            return json.dumps({
                "consolidated": count,
                "total_nodes": fleet.fractal.total_count,
                "pending": fleet.fractal.pending_count,
            })

        elif action == "stats":
            stats = fleet.fractal.get_stats()
            stats["identity_stage"] = fleet.als_manager.stage
            stats["current_focus"] = fleet.als_manager.focus
            stats["topics"] = fleet.get_all_topics()[:20]
            return json.dumps(stats)

        elif action == "optimize":
            dry_run = kwargs.get("dry_run", False)
            result = fleet.optimize_memory(dry_run=dry_run)
            return json.dumps(result)

        else:
            return json.dumps({"error": f"Unknown action: {action}. Use store|retrieve|consolidate|stats|optimize."})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_important(user_msg: str, agent_resp: str) -> bool:
    combined = (user_msg + " " + agent_resp).lower()
    return any(kw in combined for kw in _IMPORTANT_KEYWORDS)


def _make_summary(user_msg: str, agent_resp: str) -> str:
    u = user_msg[:60].strip()
    a = agent_resp[:60].strip()
    return f"Q: {u} → A: {a}"
