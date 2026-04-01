"""
Response Cache — reduces redundant LLM calls and tool fetches.

Caches:
  - Tool results (Yahoo Finance, web search) — 5 min TTL
  - Simple query responses — 2 min TTL
  - Financial data — 10 min TTL (prices change slowly)

Usage:
    cache = ResponseCache()
    cached = cache.get(key)
    if cached: return cached
    result = expensive_call()
    cache.set(key, result, ttl=300)
"""

from __future__ import annotations
import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from loguru import logger


@dataclass
class CacheEntry:
    value:      Any
    created_at: float
    ttl:        float  # seconds
    hits:       int = 0

    @property
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at


# TTL constants
TTL_YAHOO    = 600   # 10 min — stock prices
TTL_SEARCH   = 300   # 5 min  — web search results
TTL_SIMPLE   = 120   # 2 min  — simple factual answers
TTL_RESEARCH = 0     # no cache — research always fresh


class ResponseCache:
    """
    In-memory + disk cache for tool results and responses.
    Reduces redundant API calls and LLM processing.
    """

    def __init__(self, workspace: Path = None):
        self._memory: dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0
        self._tokens_saved = 0
        self.workspace = workspace

    def _make_key(self, tool: str, args: dict | str) -> str:
        """Create cache key from tool name + args."""
        raw = f"{tool}:{json.dumps(args, sort_keys=True) if isinstance(args, dict) else args}"
        return hashlib.md5(raw.encode()).hexdigest()[:16]

    def get(self, tool: str, args: dict | str) -> Any | None:
        """Return cached value or None if miss/expired."""
        key = self._make_key(tool, args)
        entry = self._memory.get(key)

        if entry is None:
            self._misses += 1
            return None

        if entry.is_expired:
            del self._memory[key]
            self._misses += 1
            logger.debug(f"Cache EXPIRED: {tool} (age={entry.age_seconds:.0f}s)")
            return None

        entry.hits += 1
        self._hits += 1
        logger.debug(
            f"Cache HIT: {tool} "
            f"(age={entry.age_seconds:.0f}s, hits={entry.hits})"
        )
        return entry.value

    def set(self, tool: str, args: dict | str, value: Any, ttl: float = TTL_SEARCH) -> None:
        """Store value in cache with TTL."""
        if ttl == 0:
            return  # TTL=0 means no caching
        key = self._make_key(tool, args)
        self._memory[key] = CacheEntry(
            value=value,
            created_at=time.time(),
            ttl=ttl,
        )
        logger.debug(f"Cache SET: {tool} (ttl={ttl}s)")

    def get_tool_ttl(self, tool_name: str) -> float:
        """Return appropriate TTL for a tool."""
        ttl_map = {
            "yahoo_finance":  TTL_YAHOO,
            "web_search_mcp": TTL_SEARCH,
            "web_search":     TTL_SEARCH,
            "memory_fleet":   TTL_SIMPLE,
            "researcher":     TTL_RESEARCH,
            "monte_carlo":    TTL_RESEARCH,
            "spawn":          TTL_RESEARCH,
        }
        return ttl_map.get(tool_name, TTL_SIMPLE)

    def evict_expired(self) -> int:
        """Remove expired entries. Returns count removed."""
        expired = [k for k, v in self._memory.items() if v.is_expired]
        for k in expired:
            del self._memory[k]
        if expired:
            logger.debug(f"Cache evicted {len(expired)} expired entries")
        return len(expired)

    def get_stats(self) -> dict:
        """Return cache performance stats."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0
        return {
            "hits":         self._hits,
            "misses":       self._misses,
            "hit_rate":     round(hit_rate, 2),
            "entries":      len(self._memory),
            "tokens_saved": self._tokens_saved,
        }

    def invalidate(self, tool: str = None) -> None:
        """Invalidate all entries or entries for specific tool."""
        if tool is None:
            self._memory.clear()
            logger.debug("Cache: full invalidation")
        else:
            # Can't efficiently filter by tool with MD5 keys
            # so just clear all — acceptable for manual invalidation
            self._memory.clear()
            logger.debug(f"Cache: invalidated for {tool}")
