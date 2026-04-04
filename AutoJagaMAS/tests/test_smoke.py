"""
test_smoke.py — AutoJagaMAS Smoke Tests
========================================
Validates that the core AutoJagaMAS components can be imported, instantiated,
and exercised without:
  - External API calls (all LLM calls are mocked)
  - GPU dependency (no CUDA imports)
  - A running Ollama server

Run with:
    cd AutoJagaMAS && python -m pytest tests/test_smoke.py -v

or:
    python -m unittest tests.test_smoke -v
"""

from __future__ import annotations

import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Ensure AutoJagaMAS package root is on path
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent  # AutoJagaMAS/
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ---------------------------------------------------------------------------
# Helper: inject a mock masfactory package so imports succeed
# ---------------------------------------------------------------------------

def _inject_masfactory_stubs():
    """
    Inject minimal masfactory stub modules so AutoJagaMAS code that imports
    from masfactory does not raise ImportError in test environments.
    """
    # masfactory top-level
    mf = types.ModuleType("masfactory")
    sys.modules.setdefault("masfactory", mf)

    # masfactory.adapters.context
    ctx_pkg = types.ModuleType("masfactory.adapters")
    sys.modules.setdefault("masfactory.adapters", ctx_pkg)

    ctx_ctx = types.ModuleType("masfactory.adapters.context")
    sys.modules.setdefault("masfactory.adapters.context", ctx_ctx)

    # ContextProvider stub
    class _CP:
        def get_blocks(self, query, *, top_k=8):
            return []

    # ContextBlock stub
    class _CB:
        def __init__(self, *, text, uri="", chunk_id="", score=1.0, title="", metadata=None):
            self.text = text
            self.uri = uri
            self.chunk_id = chunk_id
            self.score = score
            self.title = title
            self.metadata = metadata or {}

    # ContextQuery stub
    class _CQ:
        def __init__(self, query_text="", inputs=None, attributes=None, node_name=""):
            self.query_text = query_text
            self.inputs = inputs or {}
            self.attributes = attributes or {}
            self.node_name = node_name

    provider_mod = types.ModuleType("masfactory.adapters.context.provider")
    provider_mod.ContextProvider = _CP
    sys.modules.setdefault("masfactory.adapters.context.provider", provider_mod)

    types_mod = types.ModuleType("masfactory.adapters.context.types")
    types_mod.ContextBlock = _CB
    types_mod.ContextQuery = _CQ
    sys.modules.setdefault("masfactory.adapters.context.types", types_mod)

    # masfactory.adapters.model
    class _MRT:
        CONTENT = "content"
        TOOL_CALL = "tool_call"

    class _Model:
        def invoke(self, messages, tools=None, settings=None, **kwargs):
            raise NotImplementedError

    model_mod = types.ModuleType("masfactory.adapters.model")
    model_mod.Model = _Model
    model_mod.ModelResponseType = _MRT
    sys.modules.setdefault("masfactory.adapters.model", model_mod)

    # masfactory.components.agents.agent
    agents_pkg = types.ModuleType("masfactory.components")
    sys.modules.setdefault("masfactory.components", agents_pkg)
    agents_agents = types.ModuleType("masfactory.components.agents")
    sys.modules.setdefault("masfactory.components.agents", agents_agents)

    class _Agent:
        def __init__(self, name="", instructions="", model=None, **kwargs):
            self.name = name
            self.instructions = instructions
            self._model = model

        def think(self, messages, settings=None):
            if self._model:
                return self._model.invoke(messages, settings=settings)
            return {"type": "content", "content": "", "bdi_metadata": {}}

        def step(self, input_dict):
            return self.think([{"role": "user", "content": input_dict.get("query", "")}])

    agent_mod = types.ModuleType("masfactory.components.agents.agent")
    agent_mod.Agent = _Agent
    sys.modules.setdefault("masfactory.components.agents.agent", agent_mod)

    # masfactory.graphs.root_graph
    graphs_pkg = types.ModuleType("masfactory.graphs")
    sys.modules.setdefault("masfactory.graphs", graphs_pkg)

    root_mod = types.ModuleType("masfactory.graphs.root_graph")
    root_mod.RootGraph = None  # force StubGraph path
    sys.modules.setdefault("masfactory.graphs.root_graph", root_mod)


# Inject stubs before any AutoJagaMAS imports
_inject_masfactory_stubs()


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestContractImport(unittest.TestCase):
    """Test that the contracts module imports and works correctly."""

    def test_intent_roundtrip(self):
        """JagaShellIntent serialises to JSON and back without data loss."""
        from contracts.jagashell_contract import JagaShellIntent

        intent = JagaShellIntent(
            query="Styrax sumatrana density records Malaysia",
            intent_type="research",
            source_node="conductor",
            target_node="botanist",
            profile="RESEARCH",
            confidence=0.9,
        )
        json_str = intent.to_json()
        self.assertIsInstance(json_str, str)

        recovered = JagaShellIntent.from_json(json_str)
        self.assertEqual(recovered.query, intent.query)
        self.assertEqual(recovered.intent_id, intent.intent_id)
        self.assertEqual(recovered.profile, "RESEARCH")

    def test_result_roundtrip(self):
        """JagaShellResult serialises to JSON and back without data loss."""
        from contracts.jagashell_contract import JagaShellResult

        result = JagaShellResult(
            output="Styrax sumatrana air-dry density: 580–620 kg/m³ (Peninsular Malaysia).",
            producing_node="botanist",
            complexity="simple",
            confidence=0.85,
            model1_calls=1,
            model2_calls=0,
        )
        json_str = result.to_json()
        recovered = JagaShellResult.from_json(json_str)
        self.assertEqual(recovered.output, result.output)
        self.assertEqual(recovered.complexity, "simple")
        self.assertFalse(recovered.escalated)

    def test_result_from_graph_output(self):
        """JagaShellResult.from_graph_output() builds correctly from swarm dict."""
        from contracts.jagashell_contract import JagaShellResult, JagaShellIntent

        intent = JagaShellIntent(query="density", source_node="conductor", target_node="botanist")
        graph_output = {
            "output": "Density: 600 kg/m³",
            "bdi_metadata": {
                "persona": "botanist",
                "complexity": "simple",
                "model1_calls": 1,
                "model2_calls": 0,
                "escalated": False,
                "elapsed_ms": 250.0,
            },
            "node_results": {"botanist": {}, "synthesiser": {}},
        }
        result = JagaShellResult.from_graph_output(graph_output, intent=intent)
        self.assertEqual(result.output, "Density: 600 kg/m³")
        self.assertEqual(result.intent_id, intent.intent_id)
        self.assertEqual(result.producing_node, "botanist")
        self.assertEqual(result.model1_calls, 1)


class TestModelAdapter(unittest.TestCase):
    """Test JagaBDIModel with mocked CognitiveStack."""

    def _make_stack_result(self, output="Mock LLM output"):
        """Create a mock StackResult-like object."""
        result = MagicMock()
        result.output = output
        result.complexity = "simple"
        result.model1_calls = 1
        result.model2_calls = 0
        result.plan_steps = 0
        result.escalated = False
        result.repaired = False
        result.total_tokens = 42
        result.elapsed_ms = 120.5
        return result

    def test_invoke_returns_content_type(self):
        """JagaBDIModel.invoke() returns a dict with type=CONTENT and content."""
        from core.jaga_bdi_model import JagaBDIModel

        model = JagaBDIModel.__new__(JagaBDIModel)
        model.model1_id = "ollama/qwen2.5:3b"
        model.model2_id = "anthropic/claude-sonnet-4-6"
        model.workspace = Path("/tmp")
        model.calibration_mode = False

        mock_stack = MagicMock()
        mock_stack.process = MagicMock(return_value=MagicMock())
        import asyncio

        async def _mock_process(**kwargs):
            return self._make_stack_result("Styrax density is approximately 600 kg/m³.")

        mock_stack.process = _mock_process
        model._stack = mock_stack

        response = model.invoke(
            messages=[
                {"role": "user", "content": "Styrax sumatrana density records Malaysia"}
            ]
        )

        self.assertIn("type", response)
        self.assertIn("content", response)
        self.assertIn("bdi_metadata", response)
        self.assertEqual(response["content"], "Styrax density is approximately 600 kg/m³.")
        self.assertIsInstance(response["bdi_metadata"], dict)

    def test_bdi_metadata_present(self):
        """BDI metadata must be present in the response dict."""
        from core.jaga_bdi_model import JagaBDIModel

        model = JagaBDIModel.__new__(JagaBDIModel)
        model.model1_id = "ollama/qwen2.5:3b"
        model.model2_id = "anthropic/claude-sonnet-4-6"
        model.workspace = Path("/tmp")
        model.calibration_mode = False

        async def _mock_process(**kwargs):
            return self._make_stack_result("some output")

        mock_stack = MagicMock()
        mock_stack.process = _mock_process
        model._stack = mock_stack

        response = model.invoke(
            messages=[{"role": "user", "content": "test query"}]
        )
        meta = response["bdi_metadata"]
        self.assertIn("complexity", meta)
        self.assertIn("model1_calls", meta)
        self.assertIn("model2_calls", meta)
        self.assertIn("escalated", meta)
        self.assertIn("elapsed_ms", meta)


class TestAgentPersonaLoading(unittest.TestCase):
    """Test JagaBDIAgent persona loading."""

    def test_conductor_persona_loads(self):
        """JagaBDIAgent loads conductor.yaml and extracts role."""
        from agents.jaga_bdi_agent import JagaBDIAgent

        agent = JagaBDIAgent.__new__(JagaBDIAgent)
        persona_data = JagaBDIAgent._load_persona("conductor")
        self.assertIn("role", persona_data)
        self.assertIn("system_prompt", persona_data)
        self.assertIn("engines_active", persona_data)

    def test_botanist_persona_loads(self):
        """JagaBDIAgent loads botanist.yaml."""
        from agents.jaga_bdi_agent import JagaBDIAgent

        persona_data = JagaBDIAgent._load_persona("botanist")
        self.assertIn("role", persona_data)
        self.assertIn("model_preference", persona_data)

    def test_missing_persona_returns_empty(self):
        """Missing persona YAML returns empty dict (graceful degradation)."""
        from agents.jaga_bdi_agent import JagaBDIAgent

        persona_data = JagaBDIAgent._load_persona("nonexistent_persona_xyz")
        self.assertIsInstance(persona_data, dict)
        self.assertEqual(len(persona_data), 0)


class TestMangliBDISwarm(unittest.TestCase):
    """
    Smoke test: boot conductor, spawn botanist, run Styrax query, check result.

    All LLM calls are mocked — no external API calls, no GPU needed.
    """

    def _make_mock_agent_response(self, content: str) -> dict:
        return {
            "type": "content",
            "content": content,
            "bdi_metadata": {
                "complexity": "simple",
                "model1_calls": 1,
                "model2_calls": 0,
                "escalated": False,
                "elapsed_ms": 100.0,
                "persona": "botanist",
                "profile": "RESEARCH",
            },
            "persona": "botanist",
        }

    def test_swarm_runs_and_returns_result(self):
        """
        Boots the Mangliwood swarm and verifies the output structure.
        Conductor spawns botanist with websearch intent.
        """
        from graphs.mangliwood_swarm import build_mangliwood_swarm
        from core.jaga_bdi_model import JagaBDIModel

        expected_output = (
            "Styrax sumatrana specimens from Peninsular Malaysia display an air-dry density "
            "of 580–640 kg/m³, notably higher than the Styrax genus mean (450–520 kg/m³). "
            "This density anomaly correlates with elevated cinnamic acid ester concentrations "
            "in the resin and the absence of Phytophthora root-rot — three paradoxes that "
            "the swarm is investigating as a unified adaptive response."
        )

        # Patch JagaBDIModel.invoke so no real LLM calls are made
        with patch.object(JagaBDIModel, "invoke", return_value=self._make_mock_agent_response(expected_output)):
            graph = build_mangliwood_swarm(workspace=None)
            result = graph.run("Styrax sumatrana density records Malaysia")

        self.assertIsInstance(result, dict)
        self.assertIn("output", result)
        self.assertIn("node_results", result)
        self.assertIn("bdi_metadata", result)

    def test_result_has_bdi_state(self):
        """BDI state must be present in the graph result."""
        from graphs.mangliwood_swarm import build_mangliwood_swarm
        from core.jaga_bdi_model import JagaBDIModel

        with patch.object(JagaBDIModel, "invoke", return_value=self._make_mock_agent_response("test")):
            graph = build_mangliwood_swarm(workspace=None)
            result = graph.run("test query")

        # node_results should have at least one agent's output
        self.assertIsInstance(result["node_results"], dict)
        self.assertGreater(len(result["node_results"]), 0)

        # bdi_metadata should be present (may be from last agent)
        bdi = result.get("bdi_metadata", {})
        self.assertIsInstance(bdi, dict)

    def test_botanist_websearch_intent(self):
        """Botanist agent receives a websearch-intent query and returns BDI metadata."""
        from agents.jaga_bdi_agent import JagaBDIAgent
        from core.jaga_bdi_model import JagaBDIModel

        mock_response = {
            "type": "content",
            "content": "Styrax sumatrana: density 600 kg/m³, high resin yield.",
            "bdi_metadata": {
                "complexity": "simple",
                "model1_calls": 1,
                "model2_calls": 0,
                "escalated": False,
                "elapsed_ms": 85.0,
                "profile": "RESEARCH",
            },
        }

        with patch.object(JagaBDIModel, "invoke", return_value=mock_response):
            agent = JagaBDIAgent(persona="botanist", workspace=None)
            response = agent.think(
                messages=[{"role": "user", "content": "Styrax sumatrana density records Malaysia"}]
            )

        self.assertEqual(response["content"], "Styrax sumatrana: density 600 kg/m³, high resin yield.")
        self.assertIn("bdi_metadata", response)
        self.assertIn("persona", response)
        self.assertEqual(response["persona"], "botanist")


class TestNoCUDADependency(unittest.TestCase):
    """Assert that AutoJagaMAS does not import CUDA-dependent libraries."""

    def test_no_torch_cuda(self):
        """torch.cuda must not be imported by any AutoJagaMAS module."""
        cuda_modules = [k for k in sys.modules if "cuda" in k.lower()]
        self.assertEqual(
            cuda_modules, [],
            f"CUDA modules were imported: {cuda_modules}. "
            "AutoJagaMAS must not depend on GPU libraries."
        )

    def test_no_torch_import(self):
        """torch must not be imported as a side effect of AutoJagaMAS imports."""
        torch_modules = [k for k in sys.modules if k == "torch" or k.startswith("torch.")]
        self.assertEqual(
            torch_modules, [],
            f"torch was imported: {torch_modules}. "
            "AutoJagaMAS must run on CPU-only environments."
        )


class TestConfigLoading(unittest.TestCase):
    """Test that ajm_config.json is valid JSON and has required keys."""

    def test_config_loads(self):
        """ajm_config.json must load and contain model_presets and routing."""
        config_path = _ROOT / "config" / "ajm_config.json"
        self.assertTrue(config_path.exists(), f"Config not found: {config_path}")

        with open(config_path) as f:
            config = json.load(f)

        self.assertIn("model_presets", config)
        self.assertIn("routing", config)
        self.assertIn("1", config["model_presets"])
        self.assertIn("2", config["model_presets"])

    def test_routing_covers_all_profiles(self):
        """All AutoJaga profiles must have a routing entry."""
        config_path = _ROOT / "config" / "ajm_config.json"
        with open(config_path) as f:
            config = json.load(f)

        required_profiles = {"SIMPLE", "MAINTENANCE", "ACTION", "SAFE_DEFAULT",
                             "RESEARCH", "VERIFICATION", "CALIBRATION", "AUTONOMOUS"}
        routing = config.get("routing", {})
        for profile in required_profiles:
            self.assertIn(profile, routing, f"Profile '{profile}' missing from routing config.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
