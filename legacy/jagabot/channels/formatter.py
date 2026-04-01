"""Response formatter for Telegram-optimized 3-part output.

Detects section markers in LLM responses, enforces per-section word limits,
and splits long content into Telegram-safe message chunks (≤4096 chars).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Section markers the LLM is instructed to use
_PART1_MARKERS = ("🧠",)
_PART2_MARKERS = ("📊",)
_PART3_MARKERS = ("📈", "⚠️", "💡")

# Regex that matches any of the part-opening emojis at the start of a line
_SECTION_RE = re.compile(
    r"^("
    r"🧠|"        # Part 1 — understanding
    r"📊|"        # Part 2 — analysis
    r"📈|⚠️|💡"  # Part 3 — details
    r")\s",
    re.MULTILINE,
)

TELEGRAM_CHAR_LIMIT = 4096
DEFAULT_WORD_LIMITS = {"part1": 300, "part2": 500, "part3": 300}


@dataclass
class Section:
    """A parsed section of a 3-part response."""
    label: str          # "part1", "part2", "part3"
    content: str        # Full text including the header line
    word_count: int = 0

    def __post_init__(self):
        self.word_count = len(self.content.split())


@dataclass
class FormattedResponse:
    """Result of formatting: one or more message parts ready for sending."""
    parts: list[str] = field(default_factory=list)

    @property
    def message_count(self) -> int:
        return len(self.parts)


class ResponseFormatter:
    """Formats LLM output for Telegram delivery.

    1. Detect 3-part structure (🧠 / 📊 / 📈⚠️💡).
    2. Enforce per-section word limits.
    3. Split into ≤4096-char messages for Telegram.
    """

    def __init__(
        self,
        word_limits: dict[str, int] | None = None,
        char_limit: int = TELEGRAM_CHAR_LIMIT,
    ):
        self.word_limits = word_limits or dict(DEFAULT_WORD_LIMITS)
        self.char_limit = char_limit

    # ── Public API ────────────────────────────────────────────────────

    def format_for_telegram(self, content: str) -> list[str]:
        """Parse, limit, and split content into Telegram-ready messages.

        Returns a list of strings, each ≤ char_limit.
        """
        if not content or not content.strip():
            return [content or ""]

        sections = self.detect_sections(content)

        if sections:
            # Enforce word limits per section
            limited = [self.enforce_word_limit(s.content, self.word_limits.get(s.label, 500))
                       for s in sections]
            # Each section becomes its own message (if it fits)
            parts: list[str] = []
            for text in limited:
                text = text.strip()
                if not text:
                    continue
                parts.extend(self.split_long_message(text))
            return parts if parts else [content.strip()]
        else:
            # No 3-part structure detected — just split on size
            return self.split_long_message(content.strip())

    # ── Section detection ─────────────────────────────────────────────

    def detect_sections(self, content: str) -> list[Section]:
        """Detect 3-part sections by emoji markers.

        Returns list of Section objects (may be 0–3 sections).
        An empty list means the content has no recognisable structure.
        """
        matches = list(_SECTION_RE.finditer(content))
        if not matches:
            return []

        sections: list[Section] = []
        for i, m in enumerate(matches):
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            text = content[start:end].strip()
            emoji = m.group(1)
            label = self._emoji_to_label(emoji)
            sections.append(Section(label=label, content=text))

        return sections

    # ── Word-limit enforcement ────────────────────────────────────────

    @staticmethod
    def enforce_word_limit(text: str, limit: int) -> str:
        """Truncate text to *limit* words, appending '…' if cut."""
        words = text.split()
        if len(words) <= limit:
            return text
        truncated = " ".join(words[:limit])
        # Try to end at a sentence boundary
        for end in (".", "!", "?", "\n"):
            idx = truncated.rfind(end)
            if idx > len(truncated) // 2:
                return truncated[: idx + 1] + "\n\n…"
        return truncated + " …"

    # ── Message splitting ─────────────────────────────────────────────

    def split_long_message(self, text: str) -> list[str]:
        """Split text into chunks that each fit within char_limit.

        Splits at paragraph (double-newline) boundaries first,
        then single-newline, then hard-cuts as last resort.
        """
        if len(text) <= self.char_limit:
            return [text]

        chunks: list[str] = []
        remaining = text

        while remaining:
            if len(remaining) <= self.char_limit:
                chunks.append(remaining)
                break

            # Find a paragraph break within the limit
            cut = self._find_break(remaining, self.char_limit, "\n\n")
            if cut == -1:
                cut = self._find_break(remaining, self.char_limit, "\n")
            if cut == -1:
                # Hard cut at last space
                cut = remaining.rfind(" ", 0, self.char_limit)
            if cut <= 0:
                cut = self.char_limit  # absolute fallback

            chunks.append(remaining[:cut].rstrip())
            remaining = remaining[cut:].lstrip("\n")

        return [c for c in chunks if c.strip()]

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _emoji_to_label(emoji: str) -> str:
        if emoji in _PART1_MARKERS:
            return "part1"
        if emoji in _PART2_MARKERS:
            return "part2"
        if emoji in _PART3_MARKERS:
            return "part3"
        return "part2"  # default

    @staticmethod
    def _find_break(text: str, limit: int, delimiter: str) -> int:
        """Find the last occurrence of *delimiter* within *limit* chars."""
        idx = text.rfind(delimiter, 0, limit)
        return idx if idx > 0 else -1
