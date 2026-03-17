"""Tests for jagabot v3.0 Phase 1 — KnowledgeGraph tool."""

import asyncio
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from jagabot.agent.tools.knowledge_graph import KnowledgeGraphViewer, KnowledgeGraphTool


@pytest.fixture
def tmp_workspace():
    d = tempfile.mkdtemp(prefix="jagabot_test_kg_")
    ws = Path(d)
    mem = ws / "memory"
    mem.mkdir()
    yield ws
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def populated_workspace(tmp_workspace):
    """Create workspace with fractal nodes and MEMORY.md."""
    mem = tmp_workspace / "memory"

    fractal_data = {
        "nodes": [
            {
                "id": "n1",
                "timestamp": "2026-03-01 10:00:00",
                "content": "Portfolio VaR analysis shows 5% daily risk",
                "summary": "VaR analysis for portfolio risk assessment",
                "tags": ["risk", "var", "portfolio"],
                "content_type": "conversation",
                "important": True,
                "consolidated": False,
            },
            {
                "id": "n2",
                "timestamp": "2026-03-02 14:00:00",
                "content": "Monte Carlo simulation with 10000 paths",
                "summary": "Monte Carlo simulation for price forecasting",
                "tags": ["simulation", "monte carlo"],
                "content_type": "conversation",
                "important": False,
                "consolidated": False,
            },
            {
                "id": "n3",
                "timestamp": "2026-03-03 09:00:00",
                "content": "Stress test at 65 shows equity at 380988",
                "summary": "Stress test equity at extreme scenario",
                "tags": ["risk", "stress", "equity"],
                "content_type": "conversation",
                "important": True,
                "consolidated": False,
            },
            {
                "id": "n4",
                "timestamp": "2026-03-04 11:00:00",
                "content": "Learning about correlation matrices",
                "summary": "Studying correlation for diversification",
                "tags": ["learning", "correlation"],
                "content_type": "conversation",
                "important": False,
                "consolidated": False,
            },
        ]
    }
    (mem / "fractal_index.json").write_text(json.dumps(fractal_data), encoding="utf-8")

    memory_md = """## Consolidated Lessons

### Consolidated 2026-03-01 12:00
- [2026-02-28 10:00] (risk, var) Always validate VaR with stress tests
- [2026-02-28 14:00] (portfolio, equity) Equity = capital + total_pnl for leveraged
"""
    (mem / "MEMORY.md").write_text(memory_md, encoding="utf-8")

    return tmp_workspace


@pytest.fixture
def viewer(populated_workspace):
    return KnowledgeGraphViewer(populated_workspace).load()


@pytest.fixture
def tool():
    return KnowledgeGraphTool()


def _run(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


# ===================================================================
# KnowledgeGraphViewer tests
# ===================================================================

class TestKnowledgeGraphViewer:
    def test_load_nodes(self, viewer):
        stats = viewer.get_stats()
        # 4 fractal + 2 memory.md = 6 nodes
        assert stats["total_nodes"] == 6

    def test_detect_groups(self, viewer):
        stats = viewer.get_stats()
        groups = stats["groups"]
        assert "risk" in groups  # n1 and n3 are risk
        assert "permanent" in groups  # memory.md nodes

    def test_find_connections(self, viewer):
        stats = viewer.get_stats()
        # n1 (risk,var,portfolio) and n3 (risk,stress,equity) share "risk"
        assert stats["total_edges"] > 0

    def test_most_connected(self, viewer):
        stats = viewer.get_stats()
        assert len(stats["most_connected"]) > 0

    def test_query_nodes_risk(self, viewer):
        results = viewer.query_nodes("risk")
        assert len(results) >= 2

    def test_query_nodes_monte(self, viewer):
        results = viewer.query_nodes("monte carlo")
        assert len(results) >= 1

    def test_query_no_match(self, viewer):
        results = viewer.query_nodes("cryptocurrency")
        assert len(results) == 0

    def test_generate_html(self, viewer, populated_workspace):
        path = viewer.generate_html("test_graph.html")
        assert path.exists()
        html = path.read_text()
        assert "vis.DataSet" in html
        assert "Jagabot Knowledge Graph" in html
        assert "forceAtlas2Based" in html

    def test_empty_workspace(self, tmp_workspace):
        v = KnowledgeGraphViewer(tmp_workspace).load()
        stats = v.get_stats()
        assert stats["total_nodes"] == 0
        assert stats["total_edges"] == 0

    def test_html_contains_nodes(self, viewer, populated_workspace):
        path = viewer.generate_html()
        html = path.read_text()
        # The HTML should contain our node data
        assert "VaR" in html or "risk" in html

    def test_query_limit(self, viewer):
        results = viewer.query_nodes("risk", limit=1)
        assert len(results) <= 1


# ===================================================================
# KnowledgeGraphTool tests
# ===================================================================

class TestKnowledgeGraphTool:
    def test_tool_name(self, tool):
        assert tool.name == "knowledge_graph"

    def test_tool_schema(self, tool):
        schema = tool.to_schema()
        assert schema["type"] == "function"
        assert "action" in schema["function"]["parameters"]["properties"]

    def test_stats_action(self, tool, populated_workspace):
        result = json.loads(_run(tool.execute(action="stats", workspace=str(populated_workspace))))
        assert "total_nodes" in result
        assert result["total_nodes"] == 6

    def test_generate_action(self, tool, populated_workspace):
        result = json.loads(_run(tool.execute(action="generate", workspace=str(populated_workspace))))
        assert "generated" in result
        assert result["nodes"] == 6

    def test_query_action(self, tool, populated_workspace):
        result = json.loads(_run(tool.execute(action="query", keyword="risk", workspace=str(populated_workspace))))
        assert result["matches"] >= 2

    def test_query_requires_keyword(self, tool, populated_workspace):
        result = json.loads(_run(tool.execute(action="query", workspace=str(populated_workspace))))
        assert "error" in result

    def test_unknown_action(self, tool, populated_workspace):
        result = json.loads(_run(tool.execute(action="invalid", workspace=str(populated_workspace))))
        assert "error" in result
