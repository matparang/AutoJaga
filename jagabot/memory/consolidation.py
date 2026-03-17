"""
Consolidation Engine — moves important fractal nodes into permanent MEMORY.md.

Extracted from nanobot/soul/consolidation.py for jagabot v3.0.
Triune translator sync removed (not available in jagabot).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from jagabot.memory.fractal_manager import FractalManager, FractalNode

_CONSOLIDATION_THRESHOLD = 5
_MEMORY_SECTION_HEADER = "## Consolidated Lessons"


class ConsolidationEngine:
    """
    Extracts important fractal nodes → formats as lessons → appends to MEMORY.md.
    Marks consolidated nodes so they are not re-processed.
    """

    def __init__(self, memory_dir: Path, fractal: "FractalManager"):
        self.memory_dir = memory_dir
        self.memory_file = memory_dir / "MEMORY.md"
        self.fractal = fractal
        memory_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def should_consolidate(self) -> bool:
        """Return True when enough pending nodes have accumulated."""
        return self.fractal.pending_count >= _CONSOLIDATION_THRESHOLD

    def run(self, force: bool = False) -> int:
        """
        Run consolidation if threshold reached (or forced).
        Returns number of nodes consolidated.
        """
        if not force and not self.should_consolidate():
            return 0

        pending = self.fractal.get_pending_consolidation()
        if not pending:
            return 0

        logger.info("ConsolidationEngine: consolidating {} nodes", len(pending))

        lessons = self._extract_lessons(pending)
        if lessons:
            self._append_to_memory_md(lessons)

        consolidated_ids = [n.id for n in pending]
        self.fractal.mark_consolidated(consolidated_ids)

        logger.info("ConsolidationEngine: done, wrote {} lessons", len(lessons))
        return len(pending)

    def scan_fractal_for_important(self) -> list["FractalNode"]:
        """Return pending consolidation nodes."""
        return self.fractal.get_pending_consolidation()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _extract_lessons(self, nodes: list["FractalNode"]) -> list[str]:
        """Format nodes into human-readable lesson strings."""
        lessons: list[str] = []
        for node in nodes:
            ts = node.timestamp[:16]
            tags_str = ", ".join(node.tags) if node.tags else node.content_type
            summary = node.summary or node.content[:150]
            lessons.append(f"- [{ts}] ({tags_str}) {summary}")
        return lessons

    def _append_to_memory_md(self, lessons: list[str]) -> None:
        """Append a dated lessons block to MEMORY.md."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        block = f"\n### Consolidated {now}\n" + "\n".join(lessons) + "\n"

        if self.memory_file.exists():
            existing = self.memory_file.read_text(encoding="utf-8")
        else:
            existing = f"{_MEMORY_SECTION_HEADER}\n"

        if _MEMORY_SECTION_HEADER not in existing:
            existing = existing.rstrip() + f"\n\n{_MEMORY_SECTION_HEADER}\n"

        self.memory_file.write_text(existing + block, encoding="utf-8")
        logger.debug("ConsolidationEngine: appended {} lessons to MEMORY.md", len(lessons))
