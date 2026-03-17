"""Tests for v2.6 — Query Parsing & Tool Coverage Fix.

Verifies that _detect_params() extracts all structured data from queries
and that builder functions use extracted params instead of hardcoded defaults.
"""

import pytest
from jagabot.swarm.planner import _detect_params, _classify_query, TaskPlanner
from jagabot.swarm.worker_pool import TaskSpec


# ── Extractor Tests ──────────────────────────────────────────────────────


class TestDetectParams:
    def test_price_usd(self):
        assert _detect_params("USD 78.50")["price"] == 78.5

    def test_price_rm(self):
        assert _detect_params("RM 4.50")["price"] == 4.5

    def test_price_dollar(self):
        assert _detect_params("$100.25")["price"] == 100.25

    def test_price_comma(self):
        assert _detect_params("USD 1,875,000")["price"] == 1875000

    def test_vix(self):
        assert _detect_params("VIX: 35")["vix"] == 35.0

    def test_vix_equals(self):
        assert _detect_params("vix=58")["vix"] == 58.0

    def test_target_colon(self):
        assert _detect_params("TARGET: 80")["target"] == 80.0

    def test_target_price(self):
        assert _detect_params("target price: 75.50")["target"] == 75.5

    def test_threshold(self):
        assert _detect_params("threshold: 60")["target"] == 60.0

    def test_target_malay(self):
        assert _detect_params("sasaran: 90")["target"] == 90.0

    def test_changes_array(self):
        result = _detect_params("CHANGES: [4.2, 5.1, 6.3, 6.8]")
        assert result["changes"] == [4.2, 5.1, 6.3, 6.8]

    def test_changes_with_spaces(self):
        result = _detect_params("changes = [1.0, 2.0, 3.0]")
        assert result["changes"] == [1.0, 2.0, 3.0]

    def test_stress_prices(self):
        result = _detect_params("STRESS: [75,70,65]")
        assert result["stress_prices"] == [75.0, 70.0, 65.0]

    def test_stress_scenarios(self):
        result = _detect_params("stress scenarios: [80, 75, 70]")
        assert result["stress_prices"] == [80.0, 75.0, 70.0]

    def test_usd_index(self):
        assert _detect_params("USD Index: 110.5")["usd_index"] == 110.5

    def test_dxy(self):
        assert _detect_params("DXY: 105.2")["usd_index"] == 105.2

    def test_capital(self):
        assert _detect_params("capital: 500000")["capital"] == 500000.0

    def test_capital_malay(self):
        assert _detect_params("modal: 100,000")["capital"] == 100000.0

    def test_leverage(self):
        assert _detect_params("leverage: 2")["leverage"] == 2.0

    def test_leverage_malay(self):
        assert _detect_params("leveraj: 3")["leverage"] == 3.0

    def test_exposure(self):
        assert _detect_params("exposure: 1,875,000")["exposure"] == 1875000.0

    def test_confidence_decimal(self):
        assert _detect_params("confidence: 0.95")["confidence"] == 0.95

    def test_confidence_percentage(self):
        assert _detect_params("confidence: 95%")["confidence"] == 0.95

    def test_days(self):
        assert _detect_params("days: 30")["days"] == 30

    def test_horizon(self):
        assert _detect_params("horizon: 10")["days"] == 10

    def test_no_match(self):
        result = _detect_params("hello world")
        assert result == {}


class TestFullExtraction:
    """Test extraction of a complete structured query."""

    QUERY = (
        "Analyze USD 78.50 with VIX: 35, TARGET: 80, "
        "CHANGES: [4.2, 5.1, 6.3, 6.8, 6.5, 7.2], "
        "STRESS: [75,70,65], USD Index: 110.5, "
        "capital: 500,000, leverage: 2"
    )

    def test_all_params_extracted(self):
        p = _detect_params(self.QUERY)
        assert p["price"] == 78.5
        assert p["vix"] == 35.0
        assert p["target"] == 80.0
        assert p["changes"] == [4.2, 5.1, 6.3, 6.8, 6.5, 7.2]
        assert p["stress_prices"] == [75.0, 70.0, 65.0]
        assert p["usd_index"] == 110.5
        assert p["capital"] == 500000.0
        assert p["leverage"] == 2.0


# ── Builder Integration Tests ────────────────────────────────────────────


class TestCrisisBuilderUsesExtractedParams:
    def test_target_from_query(self):
        from jagabot.swarm.planner import _crisis_tasks
        params = {"price": 78.5, "target": 80.0, "vix": 35}
        groups = _crisis_tasks(params)
        mc_task = next(t for g in groups for t in g if t.tool_name == "monte_carlo")
        assert mc_task.params["target_price"] == 80.0

    def test_target_default_fallback(self):
        from jagabot.swarm.planner import _crisis_tasks
        params = {"price": 100}
        groups = _crisis_tasks(params)
        mc_task = next(t for g in groups for t in g if t.tool_name == "monte_carlo")
        assert mc_task.params["target_price"] == 85.0  # 100 * 0.85

    def test_changes_from_query(self):
        from jagabot.swarm.planner import _crisis_tasks
        params = {"changes": [1.1, 2.2, 3.3]}
        groups = _crisis_tasks(params)
        cv_task = next(t for g in groups for t in g if t.tool_name == "financial_cv")
        assert cv_task.params["changes"] == [1.1, 2.2, 3.3]

    def test_capital_flows_to_var(self):
        from jagabot.swarm.planner import _crisis_tasks
        params = {"capital": 500_000}
        groups = _crisis_tasks(params)
        var_task = next(t for g in groups for t in g if t.tool_name == "var")
        assert var_task.params["portfolio_value"] == 500_000

    def test_stress_prices_generate_tasks(self):
        from jagabot.swarm.planner import _crisis_tasks
        params = {"price": 80, "stress_prices": [75, 70, 65]}
        groups = _crisis_tasks(params)
        stress_tasks = [t for g in groups for t in g if t.tool_name == "stress_test"]
        assert len(stress_tasks) == 3


class TestStockBuilderUsesExtractedParams:
    def test_target_from_query(self):
        from jagabot.swarm.planner import _stock_tasks
        params = {"price": 4.50, "target": 3.80}
        groups = _stock_tasks(params)
        mc_task = next(t for g in groups for t in g if t.tool_name == "monte_carlo")
        assert mc_task.params["target_price"] == 3.80

    def test_changes_from_query(self):
        from jagabot.swarm.planner import _stock_tasks
        params = {"changes": [0.1, -0.2, 0.3]}
        groups = _stock_tasks(params)
        cv_task = next(t for g in groups for t in g if t.tool_name == "financial_cv")
        assert cv_task.params["changes"] == [0.1, -0.2, 0.3]


class TestRiskBuilderUsesExtractedParams:
    def test_capital_flows_to_var(self):
        from jagabot.swarm.planner import _risk_tasks
        params = {"capital": 1_000_000}
        groups = _risk_tasks(params)
        var_task = next(t for g in groups for t in g if t.tool_name == "var")
        assert var_task.params["portfolio_value"] == 1_000_000

    def test_usd_index_in_correlation(self):
        from jagabot.swarm.planner import _risk_tasks
        params = {"usd_index": 110.5}
        groups = _risk_tasks(params)
        corr_task = next(t for g in groups for t in g if t.tool_name == "correlation")
        assert "USD Index" in corr_task.params["labels"]

    def test_stress_prices_added(self):
        from jagabot.swarm.planner import _risk_tasks
        params = {"price": 100, "stress_prices": [90, 80]}
        groups = _risk_tasks(params)
        stress_tasks = [t for g in groups for t in g if t.tool_name == "stress_test"]
        assert len(stress_tasks) >= 3  # 1 historical + 2 scenario


class TestPortfolioBuilderUsesExtractedParams:
    def test_capital_flows(self):
        from jagabot.swarm.planner import _portfolio_tasks
        params = {"capital": 250_000}
        groups = _portfolio_tasks(params)
        pa_task = next(t for g in groups for t in g if t.tool_name == "portfolio_analyzer")
        assert pa_task.params["capital"] == 250_000

    def test_leverage_flows(self):
        from jagabot.swarm.planner import _portfolio_tasks
        params = {"leverage": 3}
        groups = _portfolio_tasks(params)
        pa_task = next(t for g in groups for t in g if t.tool_name == "portfolio_analyzer")
        assert pa_task.params["leverage"] == 3


class TestGeneralBuilderUsesExtractedParams:
    def test_target_from_query(self):
        from jagabot.swarm.planner import _general_tasks
        params = {"price": 100, "target": 80}
        groups = _general_tasks(params)
        mc_task = next(t for g in groups for t in g if t.tool_name == "monte_carlo")
        assert mc_task.params["target_price"] == 80


# ── Planner E2E Tests ────────────────────────────────────────────────────


class TestPlannerE2E:
    def test_full_structured_query(self):
        """Full structured query should use extracted params."""
        planner = TaskPlanner()
        query = (
            "I'm worried about a crisis with USD 78.50, VIX: 35, "
            "TARGET: 80, CHANGES: [4.2, 5.1, 6.3]"
        )
        groups = planner.plan(query)
        all_tasks = [t for g in groups for t in g]

        # MC should use target=80
        mc = next((t for t in all_tasks if t.tool_name == "monte_carlo"), None)
        assert mc is not None
        assert mc.params["target_price"] == 80.0

        # CV should use extracted changes
        cv = next((t for t in all_tasks if t.tool_name == "financial_cv"), None)
        assert cv is not None
        assert cv.params["changes"] == [4.2, 5.1, 6.3]

    def test_backward_compat_no_structured_data(self):
        """Queries without structured data should still work with defaults."""
        planner = TaskPlanner()
        groups = planner.plan("what is the risk?")
        all_tasks = [t for g in groups for t in g]
        assert len(all_tasks) > 0
        # VaR should still use default capital
        var = next((t for t in all_tasks if t.tool_name == "var"), None)
        assert var is not None
        assert var.params["portfolio_value"] == 100_000

    def test_context_override(self):
        """Context dict should override extracted params."""
        planner = TaskPlanner()
        groups = planner.plan("risk analysis", context={"capital": 999_999})
        all_tasks = [t for g in groups for t in g]
        var = next((t for t in all_tasks if t.tool_name == "var"), None)
        assert var is not None
        assert var.params["portfolio_value"] == 999_999


# ── SKILL.md Compliance ──────────────────────────────────────────────────


class TestSkillParsingRules:
    def test_skill_has_parsing_rules(self):
        import pathlib
        skill = pathlib.Path(__file__).parent.parent.parent / "jagabot" / "skills" / "financial" / "SKILL.md"
        content = skill.read_text()
        assert "Query Parsing Rules" in content
        assert "TARGET:" in content
        assert "CHANGES:" in content
        assert "STRESS:" in content
        assert "USD Index" in content
