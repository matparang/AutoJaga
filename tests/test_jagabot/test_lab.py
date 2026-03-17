"""Tests for JAGABOT Lab v3.3 — tool registry, parameter form, code generator,
ground truth, notebook manager.

All tests are unit tests with no Streamlit runtime requirement.
"""

import json
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# LabToolRegistry
# ---------------------------------------------------------------------------
from jagabot.ui.lab.tool_registry import LabToolRegistry


class TestLabToolRegistry:
    """LabToolRegistry discovery & categorisation."""

    @pytest.fixture(autouse=True)
    def _registry(self):
        self.reg = LabToolRegistry()

    def test_discovers_32_tools(self):
        assert self.reg.tool_count() == 32

    def test_no_other_category(self):
        cats = self.reg.get_categories()
        assert "other" not in cats, f"Uncategorised tools: {cats.get('other')}"

    def test_expected_categories_present(self):
        cats = self.reg.get_categories()
        for expected in ("risk", "probability", "decision", "analysis", "skills", "utility"):
            assert expected in cats, f"Missing category: {expected}"

    def test_risk_category_has_var(self):
        cats = self.reg.get_categories()
        assert "var" in cats["risk"]

    def test_risk_category_has_monte_carlo(self):
        cats = self.reg.get_categories()
        assert "monte_carlo" in cats["risk"]

    def test_get_tool_info_returns_dict(self):
        info = self.reg.get_tool_info("var")
        assert isinstance(info, dict)
        assert "tool" in info
        assert "description" in info
        assert "parameters" in info
        assert "category" in info

    def test_get_tool_info_unknown_returns_empty(self):
        assert self.reg.get_tool_info("nonexistent") == {}

    def test_var_has_dispatch_methods(self):
        methods = self.reg.get_tool_methods("var")
        assert "parametric_var" in methods
        assert "historical_var" in methods

    def test_stress_test_has_position_stress(self):
        methods = self.reg.get_tool_methods("stress_test")
        assert "position_stress" in methods

    def test_decision_engine_methods(self):
        methods = self.reg.get_tool_methods("decision_engine")
        assert "bear_perspective" in methods
        assert "bull_perspective" in methods
        assert "buffet_perspective" in methods
        assert "collapse_perspectives" in methods

    def test_financial_cv_methods(self):
        methods = self.reg.get_tool_methods("financial_cv")
        assert len(methods) >= 3

    def test_simple_tool_no_methods(self):
        # visualization tool has no dispatch methods
        methods = self.reg.get_tool_methods("visualization")
        assert methods == []

    def test_get_tools_returns_all(self):
        tools = self.reg.get_tools()
        assert len(tools) == 32
        for name, info in tools.items():
            assert isinstance(name, str)
            assert "tool" in info

    def test_categories_sum_to_total(self):
        cats = self.reg.get_categories()
        total = sum(len(v) for v in cats.values())
        assert total == 32


# ---------------------------------------------------------------------------
# ParameterForm
# ---------------------------------------------------------------------------
from jagabot.ui.lab.parameter_form import ParameterForm


class TestParameterForm:
    """ParameterForm widget mapping & defaults."""

    @pytest.fixture(autouse=True)
    def _form(self):
        self.form = ParameterForm()

    def test_widget_type_number(self):
        assert self.form.widget_type_for({"type": "number"}) == "number_input"

    def test_widget_type_integer(self):
        assert self.form.widget_type_for({"type": "integer"}) == "number_input"

    def test_widget_type_string(self):
        assert self.form.widget_type_for({"type": "string"}) == "text_input"

    def test_widget_type_enum(self):
        assert self.form.widget_type_for({"type": "string", "enum": ["a", "b"]}) == "selectbox"

    def test_widget_type_boolean(self):
        assert self.form.widget_type_for({"type": "boolean"}) == "checkbox"

    def test_widget_type_array(self):
        assert self.form.widget_type_for({"type": "array"}) == "text_area"

    def test_widget_type_object(self):
        assert self.form.widget_type_for({"type": "object"}) == "text_area"

    def test_defaults_simple(self):
        schema = {
            "type": "object",
            "properties": {
                "x": {"type": "number", "default": 42.0},
                "y": {"type": "string", "default": "hello"},
            },
        }
        d = self.form.defaults(schema)
        assert d["x"] == 42.0
        assert d["y"] == "hello"

    def test_defaults_with_method(self):
        schema = {
            "type": "object",
            "properties": {"method": {"type": "string"}, "z": {"type": "integer"}},
        }
        d = self.form.defaults(schema, method="test_method")
        assert d["method"] == "test_method"
        assert "z" in d

    def test_defaults_enum_picks_first(self):
        schema = {
            "type": "object",
            "properties": {"kind": {"type": "string", "enum": ["alpha", "beta"]}},
        }
        d = self.form.defaults(schema)
        assert d["kind"] == "alpha"


# ---------------------------------------------------------------------------
# CodeGenerator
# ---------------------------------------------------------------------------
from jagabot.ui.lab.code_generator import CodeGenerator


class TestCodeGenerator:
    """CodeGenerator snippet creation."""

    @pytest.fixture(autouse=True)
    def _gen(self):
        self.gen = CodeGenerator()

    def test_dispatch_tool_code(self):
        code = self.gen.generate("var", {"params": {"portfolio_value": 100000}}, method="parametric_var")
        assert "VaRTool" in code
        assert "parametric_var" in code
        assert "asyncio.run" in code

    def test_simple_tool_code(self):
        code = self.gen.generate("education", {"topic": "VaR"})
        assert "EducationTool" in code
        assert "asyncio.run" in code
        assert "topic" in code

    def test_fallback_code(self):
        code = self.gen.generate("unknown_tool_xyz", {"a": 1})
        assert "unknown_tool_xyz" in code

    def test_import_path_correct(self):
        code = self.gen.generate("stress_test", {"params": {}}, method="position_stress")
        assert "from jagabot.agent.tools.stress_test import StressTestTool" in code

    def test_decision_import(self):
        code = self.gen.generate("decision_engine", {"params": {}}, method="bear_perspective")
        assert "from jagabot.agent.tools.decision import DecisionTool" in code

    def test_alternate_name_code(self):
        code = self.gen.generate("counterfactual_sim", {"scenario": "test"})
        assert "CounterfactualTool" in code


# ---------------------------------------------------------------------------
# GroundTruth
# ---------------------------------------------------------------------------
from jagabot.ui.lab.ground_truth import GroundTruth


class TestGroundTruth:
    """GroundTruth comparison logic."""

    @pytest.fixture(autouse=True)
    def _gt(self):
        self.gt = GroundTruth()

    def test_mc_match(self):
        params = {"current_price": 76.50, "threshold": 70, "vix": 52, "days": 30}
        result = json.dumps({"probability": 34.24})
        comp = self.gt.compare("monte_carlo", params, result)
        assert comp is not None
        assert comp["matches"] is True

    def test_mc_mismatch(self):
        params = {"current_price": 76.50, "threshold": 70, "vix": 52, "days": 30}
        result = json.dumps({"probability": 99.0})
        comp = self.gt.compare("monte_carlo", params, result)
        assert comp is not None
        assert comp["matches"] is False

    def test_unknown_tool_returns_none(self):
        assert self.gt.compare("nonexistent", {}, "{}") is None

    def test_stress_match(self):
        params = {
            "current_equity": 1_109_092,
            "current_price": 76.50,
            "stress_price": 65,
            "units": 21_307,
        }
        result = json.dumps({"stress_equity": 864061, "stress_loss": -245031})
        comp = self.gt.compare("stress_test", params, result, method="position_stress")
        assert comp is not None
        assert comp["matches"] is True

    def test_list_ground_truths(self):
        entries = self.gt.list_ground_truths()
        assert len(entries) >= 5
        assert all("tool" in e for e in entries)

    def test_no_match_different_params(self):
        params = {"current_price": 999, "threshold": 999, "vix": 999, "days": 999}
        assert self.gt.compare("monte_carlo", params, "{}") is None


# ---------------------------------------------------------------------------
# NotebookManager
# ---------------------------------------------------------------------------
from jagabot.ui.lab.notebook_manager import NotebookManager


class TestNotebookManager:
    """NotebookManager save/load/list."""

    @pytest.fixture(autouse=True)
    def _nb(self, tmp_path):
        self.nb = NotebookManager(base_dir=tmp_path)
        self.tmp = tmp_path

    def test_save_and_load(self):
        self.nb.save_cell("test", "var", {"x": 1}, "code1", "result1")
        cells = self.nb.load_notebook("test")
        assert len(cells) == 1
        assert cells[0]["tool"] == "var"
        assert cells[0]["code"] == "code1"

    def test_append_multiple_cells(self):
        self.nb.save_cell("multi", "var", {}, "c1", "r1")
        self.nb.save_cell("multi", "mc", {}, "c2", "r2")
        cells = self.nb.load_notebook("multi")
        assert len(cells) == 2

    def test_load_nonexistent_returns_empty(self):
        assert self.nb.load_notebook("nope") == []

    def test_list_notebooks(self):
        self.nb.save_cell("alpha", "t", {}, "c", "r")
        self.nb.save_cell("beta", "t", {}, "c", "r")
        names = self.nb.list_notebooks()
        assert "alpha" in names
        assert "beta" in names

    def test_new_notebook_creates_empty(self):
        self.nb.new_notebook("fresh")
        assert self.nb.load_notebook("fresh") == []

    def test_delete_notebook(self):
        self.nb.save_cell("todelete", "t", {}, "c", "r")
        assert self.nb.delete_notebook("todelete") is True
        assert self.nb.load_notebook("todelete") == []

    def test_delete_nonexistent_returns_false(self):
        assert self.nb.delete_notebook("nope") is False

    def test_cell_has_timestamp(self):
        self.nb.save_cell("ts", "t", {}, "c", "r")
        cells = self.nb.load_notebook("ts")
        assert "timestamp" in cells[0]
        assert isinstance(cells[0]["timestamp"], float)
