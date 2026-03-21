"""
Fuzzy search across all jagabot markdown files.

Searches:
  - /root/memory/MEMORY.md
  - /root/memory/HISTORY.md
  - /root/research_output/*.md
  - /root/.jagabot/memory/*.md
  - /root/nanojaga/jagabot/skills/*/SKILL.md

Returns ranked results with context snippets.
No external dependencies — pure Python.
"""

from __future__ import annotations
import re
import os
from dataclasses import dataclass, field
from pathlib import Path
from difflib import SequenceMatcher


@dataclass
class SearchResult:
    file:     Path
    score:    float      # 0-1 relevance score
    snippet:  str        # context around match
    line_num: int
    match:    str        # matched text


def _fuzzy_score(query: str, text: str) -> float:
    """Calculate fuzzy match score between query and text."""
    q = query.lower()
    t = text.lower()

    # Exact phrase match = 1.0 (highest priority)
    if q in t:
        return 1.0

    query_words = q.split()
    if not query_words:
        return 0.0

    # All words present = high score
    text_lower = t
    all_present = all(w in text_lower for w in query_words)
    if all_present:
        # Bonus if words appear close together
        positions = []
        for w in query_words:
            idx = text_lower.find(w)
            if idx >= 0:
                positions.append(idx)
        if positions:
            span = max(positions) - min(positions)
            proximity_bonus = max(0, 1.0 - span / 200)
            return 0.7 + (0.3 * proximity_bonus)

    # Partial word matching
    text_words = set(text_lower.split())
    word_hits  = sum(1 for w in query_words if any(w in tw for tw in text_words))
    word_score = word_hits / len(query_words)

    # Sequence similarity
    seq_score = SequenceMatcher(None, q, t[:len(q)*3]).ratio()

    return max(word_score * 0.8, seq_score)


def _get_snippet(lines: list[str], line_num: int, query: str, width: int = 120) -> str:
    """Get context snippet around a match."""
    start = max(0, line_num - 1)
    end   = min(len(lines), line_num + 2)
    snippet = " | ".join(l.strip() for l in lines[start:end] if l.strip())
    if len(snippet) > width:
        # Center around the match
        q_lower = query.lower()
        idx = snippet.lower().find(q_lower.split()[0] if q_lower.split() else q_lower)
        if idx > 0:
            start_idx = max(0, idx - 30)
            snippet = "..." + snippet[start_idx:start_idx + width] + "..."
        else:
            snippet = snippet[:width] + "..."
    return snippet


def get_search_paths() -> list[Path]:
    """Get all markdown files to search."""
    paths = []
    search_dirs = [
        Path("/root/memory"),
        Path("/root/.jagabot/memory"),
        Path("/root/nanojaga/jagabot/skills"),
    ]
    MAX_FILE_SIZE = 50_000  # 50KB limit — skip massive files like HISTORY.md
    for d in search_dirs:
        if not d.exists():
            continue
        if d.name == "skills":
            for skill_md in d.rglob("SKILL.md"):
                try:
                    if skill_md.stat().st_size <= MAX_FILE_SIZE:
                        paths.append(skill_md)
                except OSError:
                    pass
        else:
            for md in d.glob("*.md"):
                try:
                    if md.stat().st_size <= MAX_FILE_SIZE:
                        paths.append(md)
                except OSError:
                    pass

    # Research output — each session is a folder with report.md
    research_dir = Path("/root/research_output")
    if research_dir.exists():
        for report in research_dir.rglob("report.md"):
            try:
                if report.stat().st_size <= MAX_FILE_SIZE:
                    paths.append(report)
            except OSError:
                pass

    return paths


def search(
    query:      str,
    max_results: int  = 10,
    min_score:  float = 0.3,
    paths:      list[Path] = None,
) -> list[SearchResult]:
    """
    Fuzzy search across all markdown files.
    Returns ranked results.
    """
    if paths is None:
        paths = get_search_paths()

    results: list[SearchResult] = []

    for filepath in paths:
        try:
            text = filepath.read_text(encoding="utf-8", errors="ignore")
            lines = text.splitlines()
        except Exception:
            continue

        # Search line by line
        best_score = 0.0
        best_line  = 0
        best_match = ""

        for i, line in enumerate(lines):
            if not line.strip():
                continue
            score = _fuzzy_score(query, line)
            if score > best_score:
                best_score = score
                best_line  = i
                best_match = line.strip()

        if best_score >= min_score:
            snippet = _get_snippet(lines, best_line, query)
            results.append(SearchResult(
                file     = filepath,
                score    = round(best_score, 3),
                snippet  = snippet,
                line_num = best_line + 1,
                match    = best_match[:100],
            ))

    # Sort by score descending
    results.sort(key=lambda r: r.score, reverse=True)
    return results[:max_results]


def format_results(results: list[SearchResult], query: str) -> str:
    """Format search results for CLI display."""
    if not results:
        return f"No results found for '{query}'"

    lines = [
        "",
        "═" * 60,
        f"  🔍 SEARCH: '{query}'",
        f"  Found {len(results)} result(s)",
        "═" * 60,
    ]

    for i, r in enumerate(results, 1):
        # Relative path for display
        try:
            rel = r.file.relative_to(Path("/root"))
            display_path = f"~/{rel}"
        except ValueError:
            display_path = str(r.file)

        # Score bar
        bar_len  = int(r.score * 15)
        bar      = "█" * bar_len + "░" * (15 - bar_len)
        pct      = f"{r.score:.0%}"

        lines.extend([
            "",
            f"  [{i}] {display_path}:{r.line_num}",
            f"      Score: [{bar}] {pct}",
            f"      Match: {r.match[:80]}",
            f"      ┗ {r.snippet}",
        ])

    lines.append("\n" + "═" * 60 + "\n")
    return "\n".join(lines)
