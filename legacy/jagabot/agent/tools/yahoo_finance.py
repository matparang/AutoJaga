"""
Yahoo Finance Tool — calls Python bridge directly.
No MCP overhead for internal jagabot use.
"""
import json
import subprocess
from pathlib import Path
from typing import Any

from jagabot.agent.tools.base import Tool

BRIDGE = Path(__file__).parent.parent.parent.parent / \
    "deepseek-mcp-server" / "src" / "yahoo_finance_bridge.py"


class YahooFinanceTool(Tool):
    """Real-time stock data from Yahoo Finance — no API key needed."""

    name = "yahoo_finance"
    description = (
        "Get real-time stock market data from Yahoo Finance.\n\n"
        "Actions:\n"
        "- quote: Current price, P/E ratio, market cap, 52-week range\n"
        "- history: Price history (periods: 1d, 5d, 1mo, 3mo, 6mo, 1y)\n"
        "- news: Latest news articles for a ticker\n"
        "- financials: Revenue, margins, cash flow\n\n"
        "Use for: stock analysis, portfolio tracking, market research.\n"
        "Chain: After quote, use decision_engine for bull/bear/buffet analysis."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["quote", "history", "news", "financials"],
                "description": "Data type: quote=price, history=chart, news=articles, financials=statements",
            },
            "ticker": {
                "type": "string",
                "description": "Stock ticker symbol e.g. AAPL, MSFT, NVDA, TSLA, BTC-USD",
            },
            "period": {
                "type": "string",
                "description": "History period: 1d, 5d, 1mo, 3mo, 6mo, 1y (only for history)",
                "default": "1mo",
            },
        },
        "required": ["action", "ticker"],
    }

    async def execute(
        self,
        action: str,
        ticker: str,
        period: str = "1mo",
        **kwargs: Any,
    ) -> str:
        """Fetch data from Yahoo Finance via Python bridge."""
        if not BRIDGE.exists():
            return json.dumps({"error": f"Yahoo Finance bridge not found at {BRIDGE}"})

        try:
            result = subprocess.run(
                ["python3", str(BRIDGE), action, ticker.upper(), period],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode != 0:
                return json.dumps({"error": result.stderr[:200]})
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            return json.dumps({"error": "Yahoo Finance request timed out"})
        except Exception as e:
            return json.dumps({"error": str(e)})
