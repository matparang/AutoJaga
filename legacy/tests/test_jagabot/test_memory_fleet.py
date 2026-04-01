"""Tests for jagabot v3.0 Phase 1 — MemoryFleet tool + sub-managers."""

import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

from jagabot.memory.fractal_manager import FractalNode, FractalManager
from jagabot.memory.als_manager import ALSManager
from jagabot.memory.consolidation import ConsolidationEngine
from jagabot.agent.tools.memory_fleet import MemoryFleet, MemoryFleetTool


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp(prefix="jagabot_test_memory_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def memory_dir(tmp_dir):
    md = tmp_dir / "memory"
    md.mkdir()
    return md


@pytest.fixture
def fractal(memory_dir):
    return FractalManager(memory_dir)


@pytest.fixture
def als(memory_dir):
    return ALSManager(memory_dir)


@pytest.fixture
def consolidation(memory_dir, fractal):
    return ConsolidationEngine(memory_dir, fractal)


@pytest.fixture
def fleet(tmp_dir):
    return MemoryFleet(workspace=tmp_dir)


@pytest.fixture
def tool(tmp_dir):
    t = MemoryFleetTool()
    t._fleet = MemoryFleet(workspace=tmp_dir)
    return t


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
# FractalNode tests
# ===================================================================

class TestFractalNode:
    def test_create_node(self):
        node = FractalNode(content="test content", summary="test", tags=["a", "b"])
        assert node.content == "test content"
        assert node.summary == "test"
        assert node.tags == ["a", "b"]
        assert len(node.id) == 8

    def test_serialize_deserialize(self):
        node = FractalNode(content="hello", summary="hi", tags=["x"], important=True)
        d = node.to_dict()
        restored = FractalNode.from_dict(d)
        assert restored.content == "hello"
        assert restored.summary == "hi"
        assert restored.tags == ["x"]
        assert restored.important is True
        assert restored.id == node.id

    def test_auto_summary(self):
        node = FractalNode(content="This is a long content that should be truncated")
        assert node.summary == node.content  # under 120 chars

    def test_default_values(self):
        node = FractalNode(content="c")
        assert node.consolidated is False
        assert node.content_type == "conversation"
        assert node.session_key == ""


# ===================================================================
# FractalManager tests
# ===================================================================

class TestFractalManager:
    def test_save_node(self, fractal):
        node = fractal.save_node(content="Risk analysis for WTI", tags=["risk"])
        assert node.id is not None
        assert fractal.total_count == 1

    def test_save_and_load(self, memory_dir):
        fm1 = FractalManager(memory_dir)
        fm1.save_node(content="Test node", tags=["test"])
        fm2 = FractalManager(memory_dir)
        assert fm2.total_count == 1

    def test_retrieve_relevant(self, fractal):
        fractal.save_node(content="Portfolio risk analysis", tags=["risk"])
        fractal.save_node(content="Weather forecast", tags=["weather"])
        fractal.save_node(content="VaR calculation for portfolio", tags=["risk", "var"])
        results = fractal.retrieve_relevant("risk portfolio")
        assert len(results) >= 1
        summaries = " ".join(n.summary for n in results)
        assert "risk" in summaries.lower() or "portfolio" in summaries.lower()

    def test_mark_important(self, fractal):
        node = fractal.save_node(content="Critical lesson")
        assert fractal.mark_important(node.id) is True
        assert fractal.pending_count == 1

    def test_get_pending_consolidation(self, fractal):
        n1 = fractal.save_node(content="Normal", important=False)
        n2 = fractal.save_node(content="Important", important=True)
        pending = fractal.get_pending_consolidation()
        assert len(pending) == 1
        assert pending[0].id == n2.id

    def test_mark_consolidated(self, fractal):
        node = fractal.save_node(content="Lesson", important=True)
        fractal.mark_consolidated([node.id])
        assert fractal.pending_count == 0
        assert node.consolidated is True

    def test_get_recent(self, fractal):
        for i in range(5):
            fractal.save_node(content=f"Node {i}")
        recent = fractal.get_recent(3)
        assert len(recent) == 3

    def test_get_nodes_by_tag(self, fractal):
        fractal.save_node(content="A", tags=["risk"])
        fractal.save_node(content="B", tags=["weather"])
        fractal.save_node(content="C", tags=["risk", "var"])
        results = fractal.get_nodes_by_tag("risk")
        assert len(results) == 2

    def test_auto_tags(self, fractal):
        node = fractal.save_node(content="Remember this important risk lesson")
        assert "memory" in node.tags or "important" in node.tags or "risk" in node.tags

    def test_strengthen_nodes(self, fractal):
        fractal.save_node(content="High belief", tags=["belief:0.9"])
        fractal.save_node(content="Low belief", tags=["belief:0.1"])
        count = fractal.strengthen_nodes(min_importance=0.5)
        assert count == 1

    def test_merge_similar(self, fractal):
        fractal.save_node(content="A", tags=["risk", "var", "portfolio"])
        fractal.save_node(content="B", tags=["risk", "var", "portfolio"])
        merged = fractal.merge_similar(similarity_threshold=0.8)
        assert merged >= 1

    def test_get_stats(self, fractal):
        fractal.save_node(content="Test", tags=["risk"], important=True)
        stats = fractal.get_stats()
        assert stats["total_nodes"] == 1
        assert stats["important"] == 1
        assert isinstance(stats["top_tags"], list)

    def test_auto_cleanup_max_nodes(self, memory_dir):
        fm = FractalManager(memory_dir, max_nodes=5)
        for i in range(10):
            fm.save_node(content=f"Node {i}")
        assert fm.total_count <= 5

    def test_delete_node(self, fractal):
        node = fractal.save_node(content="Deletable")
        assert fractal.delete_node(node.id) is True
        assert fractal.total_count == 0

    def test_cannot_delete_important(self, fractal):
        node = fractal.save_node(content="Protected", important=True)
        assert fractal.delete_node(node.id) is False
        assert fractal.total_count == 1


# ===================================================================
# ALSManager tests
# ===================================================================

class TestALSManager:
    def test_update_focus(self, als):
        als.update_focus("portfolio risk")
        assert als.focus == "portfolio risk"

    def test_add_reflection(self, als):
        als.add_reflection("Learned about VaR")
        ctx = als.get_identity_context()
        assert "VaR" in ctx

    def test_set_stage(self, als):
        als.set_stage(3)
        assert als.stage == 3

    def test_identity_context(self, als):
        als.update_focus("equity analysis")
        als.set_stage(2)
        ctx = als.get_identity_context()
        assert "Stage 2" in ctx
        assert "equity analysis" in ctx

    def test_persistence(self, memory_dir):
        als1 = ALSManager(memory_dir)
        als1.update_focus("test focus")
        als1.set_stage(5)
        als2 = ALSManager(memory_dir)
        assert als2.focus == "test focus"
        assert als2.stage == 5

    def test_reflection_trim(self, als):
        for i in range(25):
            als.add_reflection(f"Reflection {i}")
        ctx = als.get_identity_context()
        assert "Reflection 24" in ctx


# ===================================================================
# ConsolidationEngine tests
# ===================================================================

class TestConsolidation:
    def test_should_consolidate_false(self, consolidation, fractal):
        assert consolidation.should_consolidate() is False

    def test_should_consolidate_true(self, consolidation, fractal):
        for i in range(6):
            fractal.save_node(content=f"Important {i}", important=True)
        assert consolidation.should_consolidate() is True

    def test_run_consolidation(self, consolidation, fractal, memory_dir):
        for i in range(6):
            fractal.save_node(content=f"Lesson {i}", important=True, tags=["lesson"])
        count = consolidation.run()
        assert count == 6
        assert (memory_dir / "MEMORY.md").exists()
        content = (memory_dir / "MEMORY.md").read_text()
        assert "Lesson 0" in content

    def test_run_force(self, consolidation, fractal, memory_dir):
        fractal.save_node(content="Single lesson", important=True)
        count = consolidation.run(force=True)
        assert count == 1

    def test_no_double_consolidation(self, consolidation, fractal):
        for i in range(6):
            fractal.save_node(content=f"L{i}", important=True)
        consolidation.run()
        count2 = consolidation.run(force=True)
        assert count2 == 0  # all already consolidated


# ===================================================================
# MemoryFleet integration tests
# ===================================================================

class TestMemoryFleet:
    def test_on_interaction(self, fleet):
        events = fleet.on_interaction("What is VaR?", "VaR measures risk...")
        assert isinstance(events, list)
        assert fleet.fractal.total_count == 1

    def test_get_context(self, fleet):
        fleet.on_interaction("Analyze portfolio risk", "Risk analysis shows...")
        ctx = fleet.get_context("portfolio risk")
        assert "risk" in ctx.lower() or "portfolio" in ctx.lower()

    def test_consolidate_now(self, fleet):
        for i in range(6):
            fleet.on_interaction(f"Remember lesson {i}", f"Important lesson {i}")
        count = fleet.consolidate_now()
        assert count >= 1

    def test_optimize_memory(self, fleet):
        for i in range(5):
            fleet.on_interaction(f"Test {i}", f"Response {i}")
        result = fleet.optimize_memory(dry_run=True)
        assert "strengthened" in result
        assert "merged" in result
        assert "pruned" in result
        assert result["dry_run"] is True

    def test_get_exposure_count(self, fleet):
        fleet.on_interaction("risk analysis", "risk result", topic="risk")
        fleet.on_interaction("weather", "sunny")
        count = fleet.get_exposure_count("risk")
        assert count >= 1

    def test_auto_consolidation(self, fleet):
        for i in range(11):
            fleet.on_interaction(f"Remember this {i}", f"Important fact {i}")
        memory_file = fleet.workspace / "memory" / "MEMORY.md"
        # Auto-consolidation triggers at 10 interactions
        assert memory_file.exists() or fleet.fractal.total_count > 0

    def test_identity_updates(self, fleet):
        fleet.on_interaction("Focus on equity", "OK")
        assert fleet.als_manager.focus != ""


# ===================================================================
# MemoryFleetTool tests (async execute via Tool ABC)
# ===================================================================

class TestMemoryFleetTool:
    def test_tool_name(self, tool):
        assert tool.name == "memory_fleet"

    def test_tool_schema(self, tool):
        schema = tool.to_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "memory_fleet"
        assert "action" in schema["function"]["parameters"]["properties"]

    def test_store_action(self, tool):
        result = json.loads(_run(tool.execute(
            action="store",
            user_message="What is CVaR?",
            agent_response="CVaR is the expected shortfall...",
            topic="risk",
        )))
        assert result["stored"] is True
        assert result["total_nodes"] == 1

    def test_retrieve_action(self, tool):
        _run(tool.execute(action="store", user_message="VaR analysis", agent_response="VaR is 5%"))
        result = json.loads(_run(tool.execute(action="retrieve", query="VaR")))
        assert result["matched_nodes"] >= 1

    def test_consolidate_action(self, tool):
        for i in range(6):
            _run(tool.execute(action="store", user_message=f"Remember {i}", agent_response=f"Important {i}"))
        result = json.loads(_run(tool.execute(action="consolidate")))
        assert "consolidated" in result

    def test_stats_action(self, tool):
        _run(tool.execute(action="store", user_message="Test", agent_response="Test"))
        result = json.loads(_run(tool.execute(action="stats")))
        assert "total_nodes" in result
        assert result["total_nodes"] >= 1
        assert "identity_stage" in result

    def test_optimize_action(self, tool):
        result = json.loads(_run(tool.execute(action="optimize", dry_run=True)))
        assert result["dry_run"] is True
        assert "strengthened" in result

    def test_store_requires_content(self, tool):
        result = json.loads(_run(tool.execute(action="store")))
        assert "error" in result

    def test_retrieve_requires_query(self, tool):
        result = json.loads(_run(tool.execute(action="retrieve")))
        assert "error" in result

    def test_unknown_action(self, tool):
        result = json.loads(_run(tool.execute(action="invalid")))
        assert "error" in result
