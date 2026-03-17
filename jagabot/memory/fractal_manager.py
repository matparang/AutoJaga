"""
Fractal Manager — temporary working memory in fractal_index.json.
Stores conversation nodes with tags, summaries, and importance flags.

Extracted from nanobot/soul/fractal_manager.py for jagabot v3.0.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

_DEFAULT_MAX_NODES = 100


class FractalNode:
    """A single memory node in the fractal index."""

    __slots__ = (
        "id", "timestamp", "content", "summary", "tags",
        "content_type", "important", "consolidated", "session_key",
    )

    def __init__(
        self,
        content: str,
        summary: str = "",
        tags: list[str] | None = None,
        content_type: str = "conversation",
        important: bool = False,
        session_key: str = "",
        node_id: str | None = None,
        timestamp: str | None = None,
        consolidated: bool = False,
    ):
        self.id = node_id or str(uuid.uuid4())[:8]
        self.timestamp = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.content = content
        self.summary = summary or content[:120]
        self.tags = tags or []
        self.content_type = content_type
        self.important = important
        self.consolidated = consolidated
        self.session_key = session_key

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "content": self.content,
            "summary": self.summary,
            "tags": self.tags,
            "content_type": self.content_type,
            "important": self.important,
            "consolidated": self.consolidated,
            "session_key": self.session_key,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FractalNode":
        return cls(
            content=d.get("content", ""),
            summary=d.get("summary", ""),
            tags=d.get("tags", []),
            content_type=d.get("content_type", "conversation"),
            important=d.get("important", False),
            session_key=d.get("session_key", ""),
            node_id=d.get("id"),
            timestamp=d.get("timestamp"),
            consolidated=d.get("consolidated", False),
        )


class FractalManager:
    """
    Manages fractal_index.json — temporary working memory nodes.
    Nodes are tagged, searchable, and flagged for consolidation.
    """

    def __init__(self, memory_dir: Path, max_nodes: int = _DEFAULT_MAX_NODES):
        self.fractal_path = memory_dir / "fractal_index.json"
        self.max_nodes = max_nodes
        memory_dir.mkdir(parents=True, exist_ok=True)
        self._nodes: list[FractalNode] = self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_node(
        self,
        content: str,
        tags: list[str] | None = None,
        summary: str = "",
        content_type: str = "conversation",
        important: bool = False,
        session_key: str = "",
    ) -> FractalNode:
        """Create and persist a new memory node."""
        node = FractalNode(
            content=content,
            summary=summary or _auto_summary(content),
            tags=tags if tags is not None else _auto_tags(content),
            content_type=content_type,
            important=important,
            session_key=session_key,
        )
        self._nodes.append(node)
        self._auto_cleanup()
        self._save()
        logger.debug("Fractal: saved node {} (important={})", node.id, node.important)
        return node

    def retrieve_relevant(self, query: str, k: int = 5) -> list[FractalNode]:
        """Return up to k nodes most relevant to the query (keyword-based)."""
        query_words = set(query.lower().split())
        scored: list[tuple[int, FractalNode]] = []
        for node in self._nodes:
            if node.consolidated:
                continue
            score = _relevance_score(node, query_words)
            if score > 0:
                scored.append((score, node))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [n for _, n in scored[:k]]

    def mark_important(self, node_id: str) -> bool:
        """Flag a node as important (consolidation candidate)."""
        for node in self._nodes:
            if node.id == node_id:
                node.important = True
                self._save()
                return True
        return False

    def get_pending_consolidation(self) -> list[FractalNode]:
        """Return important nodes that have not yet been consolidated."""
        return [n for n in self._nodes if n.important and not n.consolidated]

    def mark_consolidated(self, node_ids: list[str]) -> int:
        """Mark nodes as consolidated. Returns count updated."""
        id_set = set(node_ids)
        count = 0
        for node in self._nodes:
            if node.id in id_set and not node.consolidated:
                node.consolidated = True
                count += 1
        if count:
            self._save()
        return count

    def get_recent(self, n: int = 10) -> list[FractalNode]:
        """Return the n most recent unconsolidated nodes."""
        unconsolidated = [nd for nd in self._nodes if not nd.consolidated]
        return unconsolidated[-n:]

    def get_all_nodes(self) -> list[FractalNode]:
        """Return ALL nodes (including consolidated)."""
        return list(self._nodes)

    def get_nodes_by_tag(self, tag: str, limit: int = 50) -> list[FractalNode]:
        """Return nodes containing *tag* (substring match) in their tags list."""
        tag_lower = tag.lower()
        matched = [
            nd for nd in self._nodes
            if any(tag_lower in t.lower() for t in (nd.tags or []))
        ]
        return matched[-limit:]

    @property
    def pending_count(self) -> int:
        return len(self.get_pending_consolidation())

    @property
    def total_count(self) -> int:
        return len(self._nodes)

    # ------------------------------------------------------------------
    # Memory restructuring
    # ------------------------------------------------------------------

    def strengthen_nodes(self, min_importance: float = 0.5) -> int:
        """Mark high-importance nodes as important and tag them 'strengthened'."""
        count = 0
        for node in self._nodes:
            score = self._tag_belief_score(node)
            if score is not None and score >= min_importance and "strengthened" not in node.tags:
                node.important = True
                node.tags.append("strengthened")
                count += 1
        if count:
            self._save()
        return count

    def prune_old(self, max_age_days: int = 30, min_importance: float = 0.1, dry_run: bool = False) -> list[FractalNode]:
        """Remove old, low-importance, non-important nodes."""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=max_age_days)
        pruned: list[FractalNode] = []
        for node in self._nodes:
            if node.important:
                continue
            try:
                ts = datetime.strptime(node.timestamp, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            if ts >= cutoff:
                continue
            score = self._tag_belief_score(node)
            if score is not None and score >= min_importance:
                continue
            pruned.append(node)
        if pruned and not dry_run:
            prune_ids = {n.id for n in pruned}
            self._nodes = [n for n in self._nodes if n.id not in prune_ids]
            self._save()
            logger.info("FractalManager: pruned {} old/weak nodes", len(pruned))
        return pruned

    def merge_similar(self, similarity_threshold: float = 0.8) -> int:
        """Merge nodes with very similar tags, keeping the newer one."""
        if len(self._nodes) < 2:
            return 0
        to_remove: set[str] = set()
        nodes = list(self._nodes)
        for i in range(len(nodes)):
            if nodes[i].id in to_remove:
                continue
            for j in range(i + 1, len(nodes)):
                if nodes[j].id in to_remove:
                    continue
                sim = self._tag_similarity(nodes[i], nodes[j])
                if sim >= similarity_threshold:
                    older, newer = (nodes[i], nodes[j]) if nodes[i].timestamp <= nodes[j].timestamp else (nodes[j], nodes[i])
                    for tag in older.tags:
                        if tag not in newer.tags:
                            newer.tags.append(tag)
                    if older.important:
                        newer.important = True
                    to_remove.add(older.id)
        if to_remove:
            self._nodes = [n for n in self._nodes if n.id not in to_remove]
            self._save()
            logger.info("FractalManager: merged {} similar nodes", len(to_remove))
        return len(to_remove)

    def delete_node(self, node_id: str) -> bool:
        """Delete a node by ID. Cannot delete important nodes."""
        for i, node in enumerate(self._nodes):
            if node.id == node_id:
                if node.important:
                    logger.warning("Cannot delete important node {}", node_id)
                    return False
                self._nodes.pop(i)
                self._save()
                return True
        return False

    def get_stats(self) -> dict:
        """Summary statistics for CLI display."""
        from collections import Counter
        tag_counts: Counter = Counter()
        ages: list[float] = []
        now = datetime.now()
        for node in self._nodes:
            for tag in node.tags:
                tag_counts[tag] += 1
            try:
                ts = datetime.strptime(node.timestamp, "%Y-%m-%d %H:%M:%S")
                ages.append((now - ts).days)
            except ValueError:
                pass
        return {
            "total_nodes":  len(self._nodes),
            "important":    sum(1 for n in self._nodes if n.important),
            "consolidated": sum(1 for n in self._nodes if n.consolidated),
            "top_tags":     tag_counts.most_common(10),
            "avg_age_days": round(sum(ages) / len(ages), 1) if ages else 0,
            "oldest_days":  max(ages) if ages else 0,
            "newest_days":  min(ages) if ages else 0,
        }

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    @staticmethod
    def _tag_belief_score(node: "FractalNode") -> float | None:
        for tag in node.tags:
            if tag.startswith("belief:"):
                try:
                    return float(tag.split(":", 1)[1])
                except ValueError:
                    pass
        return None

    @staticmethod
    def _tag_similarity(a: "FractalNode", b: "FractalNode") -> float:
        """Jaccard similarity of tag sets (excluding metadata-only tags)."""
        _skip = ("belief:", "conf:", "score:", "importance:", "strengthened")
        sa = {t for t in a.tags if not any(t.startswith(p) for p in _skip)}
        sb = {t for t in b.tags if not any(t.startswith(p) for p in _skip)}
        if not sa and not sb:
            return 0.0
        return len(sa & sb) / len(sa | sb) if (sa | sb) else 0.0

    def _auto_cleanup(self) -> None:
        """Keep at most max_nodes, preserving important unconsolidated nodes."""
        if len(self._nodes) <= self.max_nodes:
            return
        protected = [n for n in self._nodes if n.important and not n.consolidated]
        purgeable = [n for n in self._nodes if not (n.important and not n.consolidated)]
        keep_count = max(0, self.max_nodes - len(protected))
        kept = purgeable[-keep_count:] if keep_count > 0 else []
        old_count = len(self._nodes)
        self._nodes = sorted(protected + kept, key=lambda n: n.timestamp)
        if len(self._nodes) < old_count:
            logger.debug("Fractal: cleaned up {} nodes", old_count - len(self._nodes))

    def _load(self) -> list[FractalNode]:
        if self.fractal_path.exists():
            try:
                with open(self.fractal_path, encoding="utf-8") as f:
                    raw = json.load(f)
                return [FractalNode.from_dict(d) for d in raw.get("nodes", [])]
            except Exception as exc:
                logger.warning("FractalManager: failed to load {}: {}", self.fractal_path, exc)
        return []

    def _save(self) -> None:
        data = {"nodes": [n.to_dict() for n in self._nodes]}
        with open(self.fractal_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auto_summary(content: str, max_len: int = 120) -> str:
    """Extract first sentence or truncate."""
    for sep in (".", "!", "?", "\n"):
        idx = content.find(sep)
        if 0 < idx <= max_len:
            return content[: idx + 1].strip()
    return content[:max_len].strip()


def _auto_tags(content: str) -> list[str]:
    """Infer simple tags from content keywords."""
    tags: list[str] = []
    lower = content.lower()
    keyword_map = {
        "remember": "memory",
        "important": "important",
        "note": "note",
        "error": "error",
        "fix": "fix",
        "task": "task",
        "todo": "task",
        "learn": "learning",
        "lesson": "learning",
        "risk": "risk",
        "portfolio": "portfolio",
        "equity": "equity",
        "var": "risk",
        "stress": "risk",
        "monte carlo": "simulation",
    }
    for kw, tag in keyword_map.items():
        if kw in lower and tag not in tags:
            tags.append(tag)
    return tags


def _relevance_score(node: FractalNode, query_words: set[str]) -> int:
    """Score a node by keyword overlap with query."""
    score = 0
    node_text = (node.content + " " + node.summary + " " + " ".join(node.tags)).lower()
    node_words = set(node_text.split())
    overlap = query_words & node_words
    score += len(overlap) * 2
    if node.important:
        score += 3
    score += 1  # recency bonus
    return score
