"""
FuzzySearchTool — lets jagabot search its own markdown files.

Enables agent to:
- Find past research sessions
- Auto-discover skill protocols  
- Check past conclusions before answering
- Build on previous analysis
"""

from __future__ import annotations
from pathlib import Path
from jagabot.agent.tools.base import Tool


class FuzzySearchTool(Tool):
    name = "fuzzy_search"
    description = (
        "Search jagabot's own markdown files — memory, research sessions, skills. "
        "Use to find past analysis, skill protocols, or previous conclusions. "
        "Actions: search"
    )

    def to_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search terms e.g. 'NVDA risk analysis' or 'failure decomposition'"
                        },
                        "scope": {
                            "type": "string",
                            "enum": ["all", "memory", "research", "skills"],
                            "description": "Where to search: all=everywhere, memory=MEMORY.md+HISTORY.md, research=past sessions, skills=SKILL.md files"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Max results to return (default: 5)"
                        },
                        "min_score": {
                            "type": "number",
                            "description": "Min relevance 0-1 (default: 0.5)"
                        },
                    },
                    "required": ["query"],
                },
            },
        }

    async def execute(self, query: str, scope: str = "all", max_results: int = 5, min_score: float = 0.5) -> str:
        try:
            from jagabot.core.fuzzy_search import search, get_search_paths

            # Filter paths by scope
            all_paths = get_search_paths()
            if scope == "memory":
                paths = [p for p in all_paths if "memory" in str(p).lower() or p.name in ("MEMORY.md", "HISTORY.md")]
            elif scope == "research":
                paths = [p for p in all_paths if "research_output" in str(p)]
            elif scope == "skills":
                paths = [p for p in all_paths if "skills" in str(p) and p.name == "SKILL.md"]
            else:
                paths = all_paths

            results = search(query, max_results=max_results, min_score=min_score, paths=paths)

            if not results:
                return f"No results found for '{query}' in scope='{scope}'"

            # Format compact output for LLM context
            lines = [f"Search results for '{query}' ({len(results)} found):"]
            for i, r in enumerate(results, 1):
                try:
                    rel = r.file.relative_to(Path("/root"))
                    display = f"~/{rel}"
                except ValueError:
                    display = str(r.file)

                lines.append(
                    f"\n[{i}] {display} (score={r.score:.0%}, line {r.line_num})"
                    f"\n    Match: {r.match[:80]}"
                    f"\n    Context: {r.snippet[:120]}"
                )

            return "\n".join(lines)

        except Exception as e:
            return f"FuzzySearch error: {e}"
