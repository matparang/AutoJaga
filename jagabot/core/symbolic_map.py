"""
Symbolic Mapping Middleware

Replaces short symbols with full content at injection time.
Reduces token overhead for frequently referenced static content.

Flow:
  Agent output contains "[GUARDRAILS]"
  → Middleware detects symbol
  → Expands to full guardrail content
  → Injects into next message context

Symbols are one-way: compress on input, expand on output.
Static content (skills, policies) → use symbols
Dynamic content (tool results) → use cache
"""

from __future__ import annotations
import re
from pathlib import Path
from loguru import logger


# ── Symbol registry ───────────────────────────────────────────────
# Maps symbol → file path or inline content
SYMBOL_REGISTRY: dict[str, str] = {
    # Skills
    "[GUARDRAILS]":  "/root/nanojaga/jagabot/skills/adversarial-guardrails/SKILL.md",
    "[FIN-SKILL]":   "/root/nanojaga/jagabot/skills/financial/SKILL.md",
    "[PDS-SKILL]":   "/root/nanojaga/jagabot/skills/pds-scoring/SKILL.md",
    "[YOLO-SKILL]":  "/root/nanojaga/jagabot/skills/financial-research-yolo/SKILL.md",
    # Core docs
    "[CORE-ID]":     "/root/.jagabot/core_identity.md",
    "[MEMORY]":      "/root/memory/MEMORY.md",
    "[HISTORY]":     "/root/memory/HISTORY.md",
    # Inline symbols — short aliases for common phrases
    "[BRIER-OK]":    "BrierScorer calibration active — recording verified outcomes only",
    "[BDI-OK]":      "BDI Scorecard active — scoring belief/desire/intention/anomaly per turn",
    "[CACHE-OK]":    "ResponseCache active — tool results cached (Yahoo:10m, Web:5m, Memory:2m)",
    "[CCI-OK]":      "CCI active — only triggered tools sent per call",
}

# Reverse map: content summary → symbol (for compression)
# Used to compress outgoing messages
COMPRESS_PATTERNS: list[tuple[str, str]] = [
    # Long guardrail references → symbol
    (r"adversarial guardrails.*?v1\.\d", "[GUARDRAILS]"),
    (r"financial.*?skill.*?protocol", "[FIN-SKILL]"),
    (r"planning depth score.*?pds", "[PDS-SKILL]"),
]


class SymbolicMapper:
    """
    Middleware that expands symbols in messages and compresses
    repeated static content.
    """

    def __init__(self):
        self._cache: dict[str, str] = {}  # symbol → expanded content
        self._stats = {"expansions": 0, "tokens_saved": 0, "compressions": 0}

    def _load_file(self, path: str) -> str:
        """Load file content with caching."""
        if path in self._cache:
            return self._cache[path]
        try:
            content = Path(path).read_text(encoding="utf-8")
            self._cache[path] = content
            return content
        except FileNotFoundError:
            logger.debug(f"SymbolicMap: file not found: {path}")
            return f"[FILE NOT FOUND: {path}]"
        except Exception as e:
            logger.debug(f"SymbolicMap: error loading {path}: {e}")
            return f"[ERROR: {e}]"

    def expand(self, text: str) -> str:
        """Expand all symbols in text to their full content."""
        if not text:
            return text

        expanded = text
        for symbol, target in SYMBOL_REGISTRY.items():
            if symbol not in expanded:
                continue

            # Load content (file or inline)
            if target.startswith("/"):
                content = self._load_file(target)
            else:
                content = target

            expanded = expanded.replace(symbol, content)
            self._stats["expansions"] += 1
            # Estimate token savings (symbols are ~3 tokens, content ~500)
            saved = max(0, len(content) // 4 - 3)
            self._stats["tokens_saved"] -= saved  # negative = cost, not saving
            logger.debug(f"SymbolicMap: expanded {symbol} ({len(content)} chars)")

        return expanded

    def compress(self, text: str, max_chars: int = 500) -> str:
        """
        Compress repeated static content references to symbols.
        Used to shorten agent outputs before storing in history.
        """
        if not text or len(text) <= max_chars:
            return text

        compressed = text
        for pattern, symbol in COMPRESS_PATTERNS:
            match = re.search(pattern, compressed, re.IGNORECASE | re.DOTALL)
            if match:
                compressed = compressed[:match.start()] + symbol + compressed[match.end():]
                self._stats["compressions"] += 1
                logger.debug(f"SymbolicMap: compressed to {symbol}")

        return compressed

    def expand_messages(self, messages: list[dict]) -> list[dict]:
        """
        Expand symbols in a message list.
        Only expands in system messages to avoid polluting conversation.
        """
        expanded = []
        for msg in messages:
            if msg.get("role") == "system" and isinstance(msg.get("content"), str):
                new_content = self.expand(msg["content"])
                if new_content != msg["content"]:
                    expanded.append({**msg, "content": new_content})
                    continue
            expanded.append(msg)
        return expanded

    def inject_symbol_index(self, system_prompt: str) -> str:
        """
        Inject a compact symbol index into the system prompt.
        Tells the agent which symbols are available.
        """
        index_lines = [
            "\n## Available Symbols (use these to reference static content):",
        ]
        for symbol, target in SYMBOL_REGISTRY.items():
            if target.startswith("/"):
                name = Path(target).name
                index_lines.append(f"  {symbol} → {name}")
            else:
                index_lines.append(f"  {symbol} → {target[:60]}")

        return system_prompt + "\n".join(index_lines)

    def get_stats(self) -> dict:
        """Return compression/expansion statistics."""
        return self._stats.copy()


# ── Singleton instance ────────────────────────────────────────────
_mapper: SymbolicMapper | None = None

def get_mapper() -> SymbolicMapper:
    """Get or create the global SymbolicMapper instance."""
    global _mapper
    if _mapper is None:
        _mapper = SymbolicMapper()
    return _mapper

def expand(text: str) -> str:
    """Convenience function — expand symbols in text."""
    return get_mapper().expand(text)

def compress(text: str) -> str:
    """Convenience function — compress text to symbols."""
    return get_mapper().compress(text)
