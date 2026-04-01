"""
Tests for JAGABOT UI — Config, Session, Neo4jConnector, JagabotUIBridge.

All Neo4j calls are mocked so tests run without a live database.
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ====================================================================
# Helper
# ====================================================================
def _run(coro):
    """Run an async coroutine synchronously."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


# ====================================================================
# UIConfig tests
# ====================================================================
class TestUIConfig:
    def test_defaults(self):
        from jagabot.ui.config import UIConfig

        cfg = UIConfig()
        assert cfg.NEO4J_URI == "bolt://localhost:7687"
        assert cfg.NEO4J_USER == "neo4j"
        assert cfg.NEO4J_PASSWORD is None
        assert cfg.NEO4J_AUTH_ENABLED is False
        assert cfg.MAX_NODES == 50
        assert cfg.DEFAULT_DEPTH == 2

    def test_load_defaults(self):
        from jagabot.ui.config import UIConfig

        cfg = UIConfig.load()
        assert isinstance(cfg.NEO4J_URI, str)
        assert cfg.STREAMLIT_PORT == 8501

    def test_env_vars_override(self):
        from jagabot.ui.config import UIConfig

        with patch.dict(
            os.environ,
            {
                "NEO4J_URI": "bolt://remote:7687",
                "NEO4J_USER": "admin",
                "NEO4J_PASSWORD": "secret",
                "NEO4J_AUTH_ENABLED": "true",
            },
        ):
            cfg = UIConfig.load()
            assert cfg.NEO4J_URI == "bolt://remote:7687"
            assert cfg.NEO4J_USER == "admin"
            assert cfg.NEO4J_PASSWORD == "secret"
            assert cfg.NEO4J_AUTH_ENABLED is True

    def test_env_auth_disabled(self):
        from jagabot.ui.config import UIConfig

        with patch.dict(os.environ, {"NEO4J_AUTH_ENABLED": "false"}):
            cfg = UIConfig.load()
            assert cfg.NEO4J_AUTH_ENABLED is False

    def test_config_file_loading(self):
        from jagabot.ui.config import UIConfig

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".jagabot" / "config.json"
            config_path.parent.mkdir(parents=True)
            config_path.write_text(
                json.dumps(
                    {
                        "neo4j": {
                            "uri": "bolt://filehost:7687",
                            "user": "fileuser",
                            "password": "filepass",
                            "auth_enabled": True,
                        },
                        "ui": {"max_nodes": 100, "default_depth": 3, "port": 9000},
                    }
                )
            )
            with patch("pathlib.Path.home", return_value=Path(tmpdir)):
                # Clear env vars so file takes effect
                env = {
                    k: v
                    for k, v in os.environ.items()
                    if not k.startswith("NEO4J_")
                }
                with patch.dict(os.environ, env, clear=True):
                    cfg = UIConfig.load()
                    assert cfg.NEO4J_URI == "bolt://filehost:7687"
                    assert cfg.NEO4J_USER == "fileuser"
                    assert cfg.NEO4J_PASSWORD == "filepass"
                    assert cfg.NEO4J_AUTH_ENABLED is True
                    assert cfg.MAX_NODES == 100
                    assert cfg.DEFAULT_DEPTH == 3
                    assert cfg.STREAMLIT_PORT == 9000

    def test_broken_config_file_graceful(self):
        from jagabot.ui.config import UIConfig

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".jagabot" / "config.json"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("NOT JSON")
            with patch("pathlib.Path.home", return_value=Path(tmpdir)):
                env = {
                    k: v
                    for k, v in os.environ.items()
                    if not k.startswith("NEO4J_")
                }
                with patch.dict(os.environ, env, clear=True):
                    cfg = UIConfig.load()
                    assert cfg.NEO4J_URI == "bolt://localhost:7687"

    def test_neo4j_auth_returns_tuple_when_enabled(self):
        from jagabot.ui.config import UIConfig

        cfg = UIConfig()
        cfg.NEO4J_AUTH_ENABLED = True
        cfg.NEO4J_PASSWORD = "secret"
        assert cfg.neo4j_auth() == ("neo4j", "secret")

    def test_neo4j_auth_returns_none_when_disabled(self):
        from jagabot.ui.config import UIConfig

        cfg = UIConfig()
        cfg.NEO4J_AUTH_ENABLED = False
        assert cfg.neo4j_auth() is None

    def test_neo4j_auth_returns_none_when_no_password(self):
        from jagabot.ui.config import UIConfig

        cfg = UIConfig()
        cfg.NEO4J_AUTH_ENABLED = True
        cfg.NEO4J_PASSWORD = None
        assert cfg.neo4j_auth() is None

    def test_to_dict(self):
        from jagabot.ui.config import UIConfig

        cfg = UIConfig()
        d = cfg.to_dict()
        assert "neo4j_uri" in d
        assert "max_nodes" in d
        assert "streamlit_port" in d
        assert d["neo4j_auth_enabled"] is False

    def test_theme_colors(self):
        from jagabot.ui.config import UIConfig

        cfg = UIConfig()
        assert cfg.BG_PRIMARY == "#1e1e1e"
        assert cfg.ACCENT_BLUE == "#569cd6"
        assert cfg.ACCENT_GREEN == "#6a9955"
        assert cfg.ACCENT_ORANGE == "#ce9178"
        assert cfg.ACCENT_YELLOW == "#dcdcaa"


# ====================================================================
# UISession tests
# ====================================================================
class TestUISession:
    def test_creation(self):
        from jagabot.ui.session import UISession

        s = UISession()
        assert s.session_id
        assert s.user_id == "default"
        assert s.history == []

    def test_custom_user_id(self):
        from jagabot.ui.session import UISession

        s = UISession(user_id="trader1")
        assert s.user_id == "trader1"

    def test_log_action(self):
        from jagabot.ui.session import UISession

        s = UISession()
        s.log_action("search", {"topic": "oil"})
        assert len(s.history) == 1
        assert s.history[0]["action"] == "search"
        assert s.history[0]["data"]["topic"] == "oil"
        assert "time" in s.history[0]

    def test_log_action_no_data(self):
        from jagabot.ui.session import UISession

        s = UISession()
        s.log_action("click")
        assert s.history[0]["data"] == {}

    def test_multiple_actions(self):
        from jagabot.ui.session import UISession

        s = UISession()
        for i in range(5):
            s.log_action(f"action_{i}")
        assert len(s.history) == 5

    def test_get_summary(self):
        from jagabot.ui.session import UISession

        s = UISession(user_id="u1")
        s.log_action("a")
        s.log_action("b")
        summary = s.get_summary()
        assert summary["user_id"] == "u1"
        assert summary["action_count"] == 2
        assert "session_id" in summary
        assert summary["duration_seconds"] >= 0
        assert summary["actions"] == ["a", "b"]

    def test_get_history(self):
        from jagabot.ui.session import UISession

        s = UISession()
        s.log_action("x", {"k": "v"})
        h = s.get_history()
        assert len(h) == 1
        assert h[0]["action"] == "x"
        # Should be a copy
        h.append({"fake": True})
        assert len(s.history) == 1


# ====================================================================
# Neo4jConnector tests (mocked)
# ====================================================================
class TestNeo4jConnector:
    def test_init_without_neo4j_package(self):
        """When neo4j is not importable, connector is offline."""
        from jagabot.ui.neo4j_connector import Neo4jConnector

        with patch("jagabot.ui.neo4j_connector.NEO4J_AVAILABLE", False):
            c = Neo4jConnector.__new__(Neo4jConnector)
            c.uri = "bolt://localhost:7687"
            c.auth = None
            c.driver = None
            c._connected = False
            assert not c.connected
            assert c.verify_connection() is False

    def test_offline_query_subgraph(self):
        from jagabot.ui.neo4j_connector import Neo4jConnector

        c = Neo4jConnector.__new__(Neo4jConnector)
        c.uri = "bolt://localhost:7687"
        c.auth = None
        c.driver = None
        c._connected = False
        nodes, edges = c.query_subgraph("test")
        assert nodes == []
        assert edges == []

    def test_offline_get_recent_analyses(self):
        from jagabot.ui.neo4j_connector import Neo4jConnector

        c = Neo4jConnector.__new__(Neo4jConnector)
        c.driver = None
        c._connected = False
        assert c.get_recent_analyses() == []

    def test_offline_find_path(self):
        from jagabot.ui.neo4j_connector import Neo4jConnector

        c = Neo4jConnector.__new__(Neo4jConnector)
        c.driver = None
        c._connected = False
        assert c.find_path("a", "b") is None

    def test_offline_get_stats(self):
        from jagabot.ui.neo4j_connector import Neo4jConnector

        c = Neo4jConnector.__new__(Neo4jConnector)
        c.driver = None
        c._connected = False
        stats = c.get_stats()
        assert stats["connected"] is False
        assert stats["node_count"] == 0

    def test_offline_add_node(self):
        from jagabot.ui.neo4j_connector import Neo4jConnector

        c = Neo4jConnector.__new__(Neo4jConnector)
        c.driver = None
        c._connected = False
        assert c.add_node("x", "Y") is None

    def test_close_when_no_driver(self):
        from jagabot.ui.neo4j_connector import Neo4jConnector

        c = Neo4jConnector.__new__(Neo4jConnector)
        c.driver = None
        c._connected = False
        c.close()  # should not raise
        assert c.driver is None

    def test_close_with_driver(self):
        from jagabot.ui.neo4j_connector import Neo4jConnector

        c = Neo4jConnector.__new__(Neo4jConnector)
        mock_driver = MagicMock()
        c.driver = mock_driver
        c._connected = True
        c.close()
        mock_driver.close.assert_called_once()
        assert c.driver is None
        assert not c._connected

    def test_connected_property(self):
        from jagabot.ui.neo4j_connector import Neo4jConnector

        c = Neo4jConnector.__new__(Neo4jConnector)
        c.driver = MagicMock()
        c._connected = True
        assert c.connected is True

        c._connected = False
        assert c.connected is False

        c._connected = True
        c.driver = None
        assert c.connected is False

    def test_verify_connection_success(self):
        from jagabot.ui.neo4j_connector import Neo4jConnector

        c = Neo4jConnector.__new__(Neo4jConnector)
        c.driver = MagicMock()
        c._connected = True
        assert c.verify_connection() is True

    def test_verify_connection_failure(self):
        from jagabot.ui.neo4j_connector import Neo4jConnector

        c = Neo4jConnector.__new__(Neo4jConnector)
        c.driver = MagicMock()
        c.driver.verify_connectivity.side_effect = Exception("fail")
        c._connected = True
        assert c.verify_connection() is False

    def test_node_to_dict(self):
        from jagabot.ui.neo4j_connector import Neo4jConnector

        mock_node = MagicMock()
        mock_node.labels = frozenset(["Analysis"])
        mock_node.element_id = "4:abc:1"
        mock_node.get.side_effect = lambda k, default="": {
            "name": "Test Node",
            "query": "test query",
        }.get(k, default)
        mock_node.__iter__ = MagicMock(return_value=iter([("name", "Test Node")]))
        mock_node.keys.return_value = ["name"]
        mock_node.__getitem__ = lambda self, k: "Test Node"

        d = Neo4jConnector._node_to_dict(mock_node)
        assert d["id"] == "4:abc:1"
        assert d["type"] == "Analysis"
        assert "label" in d

    def test_query_subgraph_mocked(self):
        """Test query_subgraph with a fully mocked Neo4j session."""
        from jagabot.ui.neo4j_connector import Neo4jConnector

        c = Neo4jConnector.__new__(Neo4jConnector)
        c._connected = True

        # Build mock path
        mock_node1 = MagicMock()
        mock_node1.element_id = "id1"
        mock_node1.labels = frozenset(["opening"])
        mock_node1.get.return_value = "Sicilian"
        mock_node1.__iter__ = MagicMock(return_value=iter([]))
        mock_node1.keys.return_value = []

        mock_node2 = MagicMock()
        mock_node2.element_id = "id2"
        mock_node2.labels = frozenset(["position"])
        mock_node2.get.return_value = "e4 c5"
        mock_node2.__iter__ = MagicMock(return_value=iter([]))
        mock_node2.keys.return_value = []

        mock_rel = MagicMock()
        mock_rel.start_node.element_id = "id1"
        mock_rel.end_node.element_id = "id2"
        mock_rel.type = "has_position"

        mock_path = MagicMock()
        mock_path.nodes = [mock_node1, mock_node2]
        mock_path.relationships = [mock_rel]

        mock_record = MagicMock()
        mock_record.__getitem__ = lambda s, k: mock_path

        mock_session = MagicMock()
        mock_session.run.return_value = [mock_record]
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session
        c.driver = mock_driver

        nodes, edges = c.query_subgraph("Sicilian", depth=2, limit=10)
        assert len(nodes) == 2
        assert len(edges) == 1
        assert edges[0]["label"] == "has_position"

    def test_get_stats_mocked(self):
        from jagabot.ui.neo4j_connector import Neo4jConnector

        c = Neo4jConnector.__new__(Neo4jConnector)
        c._connected = True

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        call_count = [0]

        def mock_run(query, **kwargs):
            result = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:
                result.single.return_value = {"c": 42}
            elif call_count[0] == 2:
                result.single.return_value = {"c": 100}
            else:
                result.single.return_value = {"labels": ["A", "B"]}
            return result

        mock_session.run = mock_run
        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session
        c.driver = mock_driver

        stats = c.get_stats()
        assert stats["node_count"] == 42
        assert stats["rel_count"] == 100
        assert stats["connected"] is True

    def test_query_subgraph_depth_clamped(self):
        """Depth is clamped to [1, 5]."""
        from jagabot.ui.neo4j_connector import Neo4jConnector

        c = Neo4jConnector.__new__(Neo4jConnector)
        c._connected = True
        c.driver = MagicMock()

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.run.return_value = []
        c.driver.session.return_value = mock_session

        # depth=99 should be clamped to 5
        c.query_subgraph("test", depth=99, limit=10)
        query_str = mock_session.run.call_args[0][0]
        assert "*1..5" in query_str

    def test_query_subgraph_exception_graceful(self):
        from jagabot.ui.neo4j_connector import Neo4jConnector

        c = Neo4jConnector.__new__(Neo4jConnector)
        c._connected = True
        c.driver = MagicMock()

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_session.run.side_effect = Exception("DB error")
        c.driver.session.return_value = mock_session

        nodes, edges = c.query_subgraph("test")
        assert nodes == []
        assert edges == []


# ====================================================================
# JagabotUIBridge tests
# ====================================================================
class TestJagabotUIBridge:
    def _make_bridge(self, tmpdir):
        """Create a bridge with mocked subsystems."""
        from jagabot.ui.config import UIConfig
        from jagabot.ui.connectors import JagabotUIBridge

        config = UIConfig()
        # Patch Neo4j to avoid real connections
        with patch(
            "jagabot.ui.connectors.Neo4jConnector"
        ) as MockNeo4j:
            mock_neo4j = MagicMock()
            mock_neo4j.connected = True
            mock_neo4j.get_stats.return_value = {
                "node_count": 10,
                "rel_count": 20,
                "labels": ["A"],
                "connected": True,
            }
            MockNeo4j.return_value = mock_neo4j

            bridge = JagabotUIBridge(config=config, workspace=Path(tmpdir))
            bridge.neo4j = mock_neo4j
            return bridge

    def test_init(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = self._make_bridge(tmpdir)
            assert bridge.session is not None
            assert bridge.config is not None

    def test_get_graph_neo4j_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = self._make_bridge(tmpdir)
            bridge.neo4j.query_subgraph.return_value = (
                [{"id": "1", "label": "test", "type": "A"}],
                [{"from": "1", "to": "2", "label": "r"}],
            )
            nodes, edges = bridge.get_graph("test")
            assert len(nodes) == 1
            assert len(edges) == 1
            bridge.neo4j.query_subgraph.assert_called_once()

    def test_get_graph_fallback_to_kg(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = self._make_bridge(tmpdir)
            bridge.neo4j.connected = False
            # Mock KG viewer
            bridge._kg = MagicMock()
            bridge._kg.query_nodes.return_value = [
                {"id": "k1", "label": "kg_node", "group": "test"}
            ]
            nodes, edges = bridge.get_graph("test")
            assert len(nodes) == 1
            assert nodes[0]["label"][:7] == "kg_node"
            assert edges == []

    def test_get_graph_both_offline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = self._make_bridge(tmpdir)
            bridge.neo4j.connected = False
            bridge.neo4j.query_subgraph.return_value = ([], [])
            bridge._kg = None
            nodes, edges = bridge.get_graph("test")
            assert nodes == []
            assert edges == []

    def test_get_recent_analyses(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = self._make_bridge(tmpdir)
            bridge.neo4j.get_recent_analyses.return_value = [
                {"id": "a1", "query": "oil"}
            ]
            result = bridge.get_recent_analyses()
            assert len(result) == 1

    def test_get_recent_analyses_offline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = self._make_bridge(tmpdir)
            bridge.neo4j.connected = False
            bridge.neo4j = None
            assert bridge.get_recent_analyses() == []

    def test_find_gap(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = self._make_bridge(tmpdir)
            bridge.neo4j.find_path.return_value = {
                "nodes": [{"label": "A"}, {"label": "B"}],
                "relationships": ["connects"],
            }
            result = bridge.find_gap("A", "B")
            assert result is not None
            assert len(result["nodes"]) == 2

    def test_find_gap_no_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = self._make_bridge(tmpdir)
            bridge.neo4j.find_path.return_value = None
            assert bridge.find_gap("X", "Y") is None

    def test_add_graph_node(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = self._make_bridge(tmpdir)
            bridge.neo4j.add_node.return_value = "eid:123"
            eid = bridge.add_graph_node("Test", "Concept")
            assert eid == "eid:123"

    def test_save_to_memory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = self._make_bridge(tmpdir)
            bridge._memory = MagicMock()
            bridge._memory.on_interaction.return_value = ["stored"]
            result = bridge.save_to_memory("user msg", "agent resp", topic="oil")
            assert result == ["stored"]

    def test_save_to_memory_no_fleet(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = self._make_bridge(tmpdir)
            bridge._memory = None
            result = bridge.save_to_memory("u", "a")
            assert result == []

    def test_get_memory_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = self._make_bridge(tmpdir)
            bridge._memory = MagicMock()
            bridge._memory.get_context.return_value = "some context"
            assert bridge.get_memory_context("oil") == "some context"

    def test_get_memory_context_no_fleet(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = self._make_bridge(tmpdir)
            bridge._memory = None
            assert bridge.get_memory_context("oil") == ""

    def test_track_action(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = self._make_bridge(tmpdir)
            bridge._meta = MagicMock()
            bridge._meta.record_strategy_result.return_value = {"strategy": "ui_click"}
            result = bridge.track_action("click")
            assert result is not None
            bridge._meta.record_strategy_result.assert_called_once_with(
                strategy_name="ui_click", success=True, fitness_gain=0.01
            )

    def test_track_action_no_meta(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = self._make_bridge(tmpdir)
            bridge._meta = None
            assert bridge.track_action("click") is None

    def test_get_evolution_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = self._make_bridge(tmpdir)
            bridge._evo = MagicMock()
            bridge._evo.get_status.return_value = {
                "cycle": 10,
                "fitness": 0.85,
                "total_mutations": 3,
            }
            result = bridge.get_evolution_status()
            assert result["fitness"] == 0.85

    def test_get_evolution_status_no_engine(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = self._make_bridge(tmpdir)
            bridge._evo = None
            result = bridge.get_evolution_status()
            assert "error" in result

    def test_research(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = self._make_bridge(tmpdir)
            bridge._subagents = MagicMock()

            async def mock_workflow(query, data=None):
                return {"success": True, "web": {}, "tools": {}}

            bridge._subagents.execute_workflow = mock_workflow
            result = bridge.research("oil crisis")
            assert result["success"] is True

    def test_research_no_subagents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = self._make_bridge(tmpdir)
            bridge._subagents = None
            result = bridge.research("oil")
            assert result["success"] is False
            assert "not available" in result["error"]

    def test_get_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = self._make_bridge(tmpdir)
            bridge._kg = None
            bridge._memory = None
            bridge._evo = None
            stats = bridge.get_stats()
            assert "session" in stats
            assert "neo4j" in stats
            assert stats["neo4j"]["connected"] is True

    def test_session_tracks_actions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = self._make_bridge(tmpdir)
            bridge.neo4j.query_subgraph.return_value = ([], [])
            bridge.get_graph("test")
            bridge.get_graph("oil")
            h = bridge.session.get_history()
            assert len(h) == 2
            assert h[0]["action"] == "get_graph"

    def test_close(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bridge = self._make_bridge(tmpdir)
            bridge.close()
            bridge.neo4j.close.assert_called_once()
