"""
Context Compression Index (CCI)

Replaces full tool definitions with a compressed lookup table.
Only expands full definitions for triggered tools.
Reduces token overhead from ~15k to ~2k per call.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class ToolEntry:
    """Compressed tool index entry."""
    id:       str
    name:     str
    keywords: list[str]
    cost:     str  # LOW / MED / HIGH
    summary:  str  # max 50 chars


# Master index — one line per tool
TOOL_INDEX: list[ToolEntry] = [
    ToolEntry("T01", "memory_fleet",      ["remember","recall","history","memory","store","retrieve"],     "LOW",  "Store/retrieve long-term memory"),
    ToolEntry("T02", "yahoo_finance",     ["stock","price","ticker","shares","market","pe","ratio","cap"], "LOW",  "Live stock data from Yahoo Finance"),
    ToolEntry("T03", "web_search_mcp",    ["search","news","current","today","latest","web","find"],       "LOW",  "Real-time web search via DuckDuckGo"),
    ToolEntry("T04", "spawn",             ["spawn","subagent","parallel","background","agent"],             "MED",  "Spawn background subagent"),
    ToolEntry("T05", "monte_carlo",       ["simulate","probability","risk","forecast","scenario"],          "HIGH", "Monte Carlo price simulation"),
    ToolEntry("T06", "decision_engine",   ["bull","bear","buffet","perspective","invest","analysis"],       "MED",  "Bull/bear/buffet analysis"),
    ToolEntry("T07", "financial_cv",      ["volatility","cv","coefficient","variation","risk"],             "LOW",  "Coefficient of variation analysis"),
    ToolEntry("T08", "var",               ["var","value at risk","downside","loss"],                        "LOW",  "Value at Risk calculation"),
    ToolEntry("T09", "read_file",         ["read","file","open","content","load"],                          "LOW",  "Read file from filesystem"),
    ToolEntry("T10", "write_file",        ["write","save","create","file","export"],                        "LOW",  "Write file to filesystem"),
    ToolEntry("T11", "exec",              ["run","execute","command","bash","script","python"],              "MED",  "Execute shell command"),
    ToolEntry("T12", "knowledge_graph",   ["graph","knowledge","connect","visualize","network"],             "MED",  "Knowledge graph visualization"),
    ToolEntry("T13", "self_model_awareness",["capability","reliability","domain","trust","self"],           "LOW",  "Self-assessment and reliability"),
    ToolEntry("T14", "researcher",        ["research","paper","study","literature","academic"],              "HIGH", "Deep research tool"),
    ToolEntry("T15", "web_search",        ["search","google","bing","web","online"],                        "LOW",  "Web search (legacy)"),
    ToolEntry("T16", "early_warning",     ["warning","signal","alert","margin","call"],                     "LOW",  "Early warning signals"),
    ToolEntry("T17", "stress_test",       ["stress","test","scenario","crash","extreme"],                   "MED",  "Portfolio stress testing"),
    ToolEntry("T18", "meta_learning",     ["learn","improve","strategy","meta","evolve"],                   "LOW",  "MetaLearning strategy recording"),
    ToolEntry("T19", "k1_bayesian",       ["bayesian","prior","posterior","belief","probability"],          "MED",  "Bayesian belief update"),
    ToolEntry("T20", "challenge",         ["challenge","calibrate","quiz","test","question"],                "LOW",  "Calibration challenge"),
]


def scan(query: str) -> list[ToolEntry]:
    """Scan query for keyword matches — returns triggered tools."""
    query_lower = query.lower()
    triggered = []
    for entry in TOOL_INDEX:
        if any(kw in query_lower for kw in entry.keywords):
            triggered.append(entry)
    return triggered


def build_index_table() -> str:
    """Build compressed index table for LLM context."""
    lines = [
        "TOOL INDEX (use IDs to request full tool definitions):",
        "| ID  | Name                    | Summary                          | Cost |",
        "|-----|-------------------------|----------------------------------|------|",
    ]
    for e in TOOL_INDEX:
        lines.append(f"| {e.id} | {e.name:<23} | {e.summary:<32} | {e.cost:<4} |")
    return "\n".join(lines)


def get_token_estimate(triggered: list[ToolEntry]) -> int:
    """Estimate token savings vs full definitions."""
    avg_full_def = 300  # avg tokens per full tool definition
    index_tokens = 600  # compressed index table
    triggered_tokens = len(triggered) * avg_full_def
    saved = (len(TOOL_INDEX) * avg_full_def) - (index_tokens + triggered_tokens)
    return max(0, saved)


def report(query: str) -> dict:
    """Full CCI report for a query."""
    triggered = scan(query)
    savings = get_token_estimate(triggered)
    logger.debug(
        f"CCI: {len(triggered)}/{len(TOOL_INDEX)} tools triggered "
        f"(~{savings} tokens saved)"
    )
    return {
        "triggered_tools": [e.name for e in triggered],
        "triggered_count": len(triggered),
        "total_tools": len(TOOL_INDEX),
        "estimated_savings": savings,
        "index_table": build_index_table(),
    }
