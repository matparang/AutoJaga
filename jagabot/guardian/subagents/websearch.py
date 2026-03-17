"""WebSearch subagent — fetches latest market data and news."""

import json
from datetime import datetime
from typing import Any

from jagabot.agent.tools.web import WebSearchTool, WebFetchTool


async def websearch_agent(
    query: str,
    brave_api_key: str | None = None,
    count: int = 5,
) -> dict[str, Any]:
    """Fetch latest market data and news for a query.

    This subagent uses jagabot's existing web tools.
    It does NOT access memory — only the orchestrator stores results.

    Args:
        query: User's search query (e.g., "oil prices WTI March 2026").
        brave_api_key: Optional Brave Search API key.
        count: Number of search results.

    Returns:
        Dict with 'news', 'timestamp', 'query', and raw search text.
    """
    search_tool = WebSearchTool(api_key=brave_api_key, max_results=count)
    results_text = await search_tool.execute(query=query, count=count)

    # Parse search results into structured list
    news_items = []
    current_item = {}
    for line in results_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Lines like "1. Title"
        if line[0].isdigit() and ". " in line:
            if current_item:
                news_items.append(current_item)
            parts = line.split(". ", 1)
            current_item = {"rank": int(parts[0]), "title": parts[1] if len(parts) > 1 else ""}
        elif line.startswith("http"):
            current_item["url"] = line
        elif current_item and "title" in current_item:
            current_item["snippet"] = line

    if current_item:
        news_items.append(current_item)

    return {
        "query": query,
        "news": news_items,
        "raw_results": results_text,
        "result_count": len(news_items),
        "timestamp": datetime.now().isoformat(),
    }
