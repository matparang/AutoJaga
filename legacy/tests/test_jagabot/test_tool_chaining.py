"""Tests verifying all financial tools are discoverable with rich descriptions and schemas."""

import json
import pytest
from jagabot.agent.tools.registry import ToolRegistry
from jagabot.agent.tools import (
    FinancialCVTool,
    MonteCarloTool,
    DynamicsTool,
    StatisticalTool,
    EarlyWarningTool,
    BayesianTool,
    CounterfactualTool,
    SensitivityTool,
    ParetoTool,
    VisualizationTool,
    VaRTool,
    CVaRTool,
    StressTestTool,
    CorrelationTool,
    RecoveryTimeTool,
    DecisionTool,
    EducationTool,
    AccountabilityTool,
    ResearcherTool,
    CopywriterTool,
    SelfImproverTool,
    PortfolioAnalyzerTool,
)


ALL_TOOLS = [
    FinancialCVTool,
    MonteCarloTool,
    DynamicsTool,
    StatisticalTool,
    EarlyWarningTool,
    BayesianTool,
    CounterfactualTool,
    SensitivityTool,
    ParetoTool,
    VisualizationTool,
    VaRTool,
    CVaRTool,
    StressTestTool,
    CorrelationTool,
    RecoveryTimeTool,
    DecisionTool,
    EducationTool,
    AccountabilityTool,
    ResearcherTool,
    CopywriterTool,
    SelfImproverTool,
    PortfolioAnalyzerTool,
]

EXPECTED_NAMES = {
    "financial_cv",
    "monte_carlo",
    "dynamics_oracle",
    "statistical_engine",
    "early_warning",
    "bayesian_reasoner",
    "counterfactual_sim",
    "sensitivity_analyzer",
    "pareto_optimizer",
    "visualization",
    "var",
    "cvar",
    "stress_test",
    "correlation",
    "recovery_time",
    "decision_engine",
    "education",
    "accountability",
    "researcher",
    "copywriter",
    "self_improver",
    "portfolio_analyzer",
}


@pytest.fixture
def registry():
    reg = ToolRegistry()
    for cls in ALL_TOOLS:
        reg.register(cls())
    return reg


class TestToolDiscovery:
    """All 10 financial tools must be registered and discoverable."""

    def test_all_ten_tools_registered(self, registry):
        defs = registry.get_definitions()
        names = {d["function"]["name"] for d in defs}
        assert EXPECTED_NAMES.issubset(names), f"Missing: {EXPECTED_NAMES - names}"

    def test_definitions_are_openai_format(self, registry):
        for defn in registry.get_definitions():
            assert defn["type"] == "function"
            fn = defn["function"]
            assert "name" in fn
            assert "description" in fn
            assert "parameters" in fn


class TestRichDescriptions:
    """Tool descriptions must be rich enough for LLM to know WHEN to call them."""

    MIN_DESCRIPTION_LENGTH = 100  # chars — rejects terse descriptions

    @pytest.mark.parametrize("tool_cls", ALL_TOOLS, ids=[t.__name__ for t in ALL_TOOLS])
    def test_description_is_rich(self, tool_cls):
        tool = tool_cls()
        desc = tool.description
        assert len(desc) >= self.MIN_DESCRIPTION_LENGTH, (
            f"{tool.name} description too short ({len(desc)} chars): {desc[:80]}..."
        )

    @pytest.mark.parametrize("tool_cls", ALL_TOOLS, ids=[t.__name__ for t in ALL_TOOLS])
    def test_description_has_call_guidance(self, tool_cls):
        tool = tool_cls()
        desc = tool.description.lower()
        assert any(kw in desc for kw in ["call this", "chain", "use after", "use before", "feed"]), (
            f"{tool.name} description lacks tool-calling guidance"
        )

    @pytest.mark.parametrize("tool_cls", ALL_TOOLS, ids=[t.__name__ for t in ALL_TOOLS])
    def test_description_mentions_methods_or_modes(self, tool_cls):
        tool = tool_cls()
        desc = tool.description.lower()
        assert any(kw in desc for kw in ["method", "mode", "pass ", "usage"]), (
            f"{tool.name} description doesn't explain methods/modes"
        )


class TestRichParameterSchemas:
    """Parameter schemas must have descriptions with examples."""

    @pytest.mark.parametrize("tool_cls", ALL_TOOLS, ids=[t.__name__ for t in ALL_TOOLS])
    def test_parameters_have_descriptions(self, tool_cls):
        tool = tool_cls()
        props = tool.parameters.get("properties", {})
        for prop_name, prop_schema in props.items():
            desc = prop_schema.get("description", "")
            assert len(desc) >= 10, (
                f"{tool.name}.{prop_name} has no/short description: '{desc}'"
            )

    def test_method_dispatch_tools_have_examples(self):
        """Tools that use method+params dispatch must have param examples."""
        dispatch_tools = [
            FinancialCVTool, DynamicsTool, StatisticalTool,
            EarlyWarningTool, BayesianTool, CounterfactualTool,
            SensitivityTool, ParetoTool,
        ]
        for cls in dispatch_tools:
            tool = cls()
            params_desc = tool.parameters["properties"]["params"]["description"]
            assert "example" in params_desc.lower() or "{" in params_desc, (
                f"{tool.name} params field lacks examples"
            )

    def test_monte_carlo_has_required_fields(self):
        tool = MonteCarloTool()
        required = tool.parameters.get("required", [])
        assert "current_price" in required
        assert "target_price" in required
        assert "vix" in required

    def test_visualization_has_required_fields(self):
        tool = VisualizationTool()
        required = tool.parameters.get("required", [])
        assert "mode" in required
        assert "current_price" in required


class TestToolSchemaValidity:
    """Schemas must be valid JSON Schema for OpenAI function calling."""

    @pytest.mark.parametrize("tool_cls", ALL_TOOLS, ids=[t.__name__ for t in ALL_TOOLS])
    def test_schema_is_serializable(self, tool_cls):
        tool = tool_cls()
        schema = tool.to_schema()
        serialized = json.dumps(schema)
        roundtripped = json.loads(serialized)
        assert roundtripped == schema

    @pytest.mark.parametrize("tool_cls", ALL_TOOLS, ids=[t.__name__ for t in ALL_TOOLS])
    def test_schema_has_valid_type(self, tool_cls):
        tool = tool_cls()
        params = tool.parameters
        assert params.get("type") == "object"
        assert "properties" in params


class TestFinancialSkillAutoload:
    """The financial SKILL.md must exist and be marked always=true."""

    def test_skill_file_exists(self):
        from pathlib import Path
        skill_path = Path(__file__).parents[2] / "jagabot" / "skills" / "financial" / "SKILL.md"
        assert skill_path.exists(), f"Financial SKILL.md not found at {skill_path}"

    def test_skill_has_always_flag(self):
        from pathlib import Path
        skill_path = Path(__file__).parents[2] / "jagabot" / "skills" / "financial" / "SKILL.md"
        content = skill_path.read_text()
        assert '"always":true' in content or '"always": true' in content, (
            "Financial SKILL.md must have always:true in metadata"
        )

    def test_skill_mentions_all_tools(self):
        from pathlib import Path
        skill_path = Path(__file__).parents[2] / "jagabot" / "skills" / "financial" / "SKILL.md"
        content = skill_path.read_text().lower()
        for name in EXPECTED_NAMES:
            assert name in content, f"SKILL.md doesn't mention tool '{name}'"
