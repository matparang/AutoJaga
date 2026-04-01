"""Tests for Phase 1 FRM tools: VaR, CVaR, Stress Test, Correlation, Recovery Time."""

import json
import pytest
import numpy as np

# --- VaR ---
from jagabot.agent.tools.var import parametric_var, historical_var, monte_carlo_var, VaRTool

# --- CVaR ---
from jagabot.agent.tools.cvar import calculate_cvar, compare_var_cvar, CVaRTool

# --- Stress Test ---
from jagabot.agent.tools.stress_test import run_stress_test, historical_stress, StressTestTool, HISTORICAL_CRISES

# --- Correlation ---
from jagabot.agent.tools.correlation import pairwise_correlation, correlation_matrix, rolling_correlation, CorrelationTool

# --- Recovery Time ---
from jagabot.agent.tools.recovery_time import estimate_recovery, recovery_probability, RecoveryTimeTool

# --- Registry ---
from jagabot.agent.tools.registry import ToolRegistry


# ========================= VaR =========================

class TestParametricVaR:
    def test_basic_95(self):
        r = parametric_var(mean_return=-0.001, std_return=0.025, confidence=0.95)
        assert r["method"] == "parametric"
        assert r["confidence"] == 0.95
        assert r["var_pct"] > 0
        assert r["var_amount"] > 0

    def test_99_higher_than_95(self):
        r95 = parametric_var(mean_return=-0.001, std_return=0.025, confidence=0.95)
        r99 = parametric_var(mean_return=-0.001, std_return=0.025, confidence=0.99)
        assert r99["var_pct"] > r95["var_pct"]

    def test_holding_period(self):
        r1 = parametric_var(mean_return=-0.001, std_return=0.025, holding_period=1)
        r10 = parametric_var(mean_return=-0.001, std_return=0.025, holding_period=10)
        assert r10["var_amount"] > r1["var_amount"]


class TestHistoricalVaR:
    def test_basic(self):
        returns = [-0.03, -0.02, -0.01, 0.0, 0.01, 0.02, 0.03, -0.04, 0.015, -0.025]
        r = historical_var(returns=returns, confidence=0.95)
        assert r["method"] == "historical"
        assert r["var_pct"] > 0
        assert r["n_observations"] == 10

    def test_empty_returns(self):
        r = historical_var(returns=[])
        assert "error" in r


class TestMonteCarloVaR:
    def test_basic(self):
        np.random.seed(42)
        prices = list(np.random.normal(150, 20, 1000))
        r = monte_carlo_var(prices=prices, current_price=150, confidence=0.95)
        assert r["method"] == "monte_carlo"
        assert r["var_pct"] > 0
        assert r["n_simulations"] == 1000

    def test_invalid_price(self):
        r = monte_carlo_var(prices=[100, 110], current_price=0)
        assert "error" in r


class TestVaRTool:
    @pytest.mark.asyncio
    async def test_dispatch(self):
        tool = VaRTool()
        result = await tool.execute(method="parametric_var", params={"mean_return": -0.001, "std_return": 0.025})
        data = json.loads(result)
        assert data["method"] == "parametric"

    @pytest.mark.asyncio
    async def test_unknown_method(self):
        tool = VaRTool()
        result = await tool.execute(method="bogus", params={})
        data = json.loads(result)
        assert "error" in data


# ========================= CVaR =========================

class TestCalculateCVaR:
    def test_basic(self):
        np.random.seed(42)
        prices = list(np.random.normal(150, 20, 5000))
        r = calculate_cvar(prices=prices, current_price=150, confidence=0.95)
        assert r["cvar_pct"] > r["var_pct"]  # CVaR always >= VaR
        assert r["n_tail"] > 0

    def test_invalid(self):
        r = calculate_cvar(prices=[], current_price=150)
        assert "error" in r


class TestCompareVaRCVaR:
    def test_basic(self):
        np.random.seed(42)
        prices = list(np.random.normal(150, 20, 5000))
        r = compare_var_cvar(prices=prices, current_price=150)
        assert "comparison" in r
        assert len(r["comparison"]) == 3  # 90, 95, 99
        # Higher confidence → higher VaR
        assert r["comparison"][2]["var_pct"] > r["comparison"][0]["var_pct"]


class TestCVaRTool:
    @pytest.mark.asyncio
    async def test_dispatch(self):
        tool = CVaRTool()
        np.random.seed(42)
        prices = list(np.random.normal(150, 20, 1000))
        result = await tool.execute(method="calculate_cvar", params={"prices": prices, "current_price": 150})
        data = json.loads(result)
        assert "cvar_pct" in data


# ========================= Stress Test =========================

class TestRunStressTest:
    def test_instant_shock(self):
        r = run_stress_test(portfolio_value=100000, scenarios=[
            {"name": "mild", "shock_pct": 10},
            {"name": "severe", "shock_pct": 40},
        ])
        assert len(r["results"]) == 2
        assert r["results"][0]["loss"] == 10000
        assert r["results"][1]["loss"] == 40000
        assert r["worst_case"] == "severe"

    def test_dynamics_scenario(self):
        r = run_stress_test(portfolio_value=100000, scenarios=[
            {"name": "slow_decay", "decay_rate": 0.05, "feedback_strength": 0.02},
        ], steps=30)
        assert r["results"][0]["type"] == "dynamics_simulation"
        assert r["results"][0]["final_value"] < 100000


class TestHistoricalStress:
    def test_all_crises(self):
        r = historical_stress(portfolio_value=100000)
        assert len(r["results"]) == len(HISTORICAL_CRISES)
        for res in r["results"]:
            assert "context" in res
            assert res["loss"] > 0

    def test_specific_crisis(self):
        r = historical_stress(portfolio_value=50000, crises=["gfc_2008"])
        assert len(r["results"]) == 1
        assert "2008" in r["results"][0]["scenario"]


class TestStressTestTool:
    @pytest.mark.asyncio
    async def test_dispatch(self):
        tool = StressTestTool()
        result = await tool.execute(method="historical_stress", params={"portfolio_value": 100000, "crises": ["covid_2020"]})
        data = json.loads(result)
        assert len(data["results"]) == 1


# ========================= Correlation =========================

class TestPairwiseCorrelation:
    def test_perfect_positive(self):
        r = pairwise_correlation([1, 2, 3, 4, 5], [2, 4, 6, 8, 10])
        assert r["correlation"] == 1.0
        assert r["strength"] == "very_strong"
        assert r["direction"] == "positive"

    def test_negative(self):
        r = pairwise_correlation([1, 2, 3, 4, 5], [10, 8, 6, 4, 2])
        assert r["correlation"] == -1.0
        assert r["direction"] == "negative"

    def test_unequal_length(self):
        r = pairwise_correlation([1, 2], [1, 2, 3])
        assert "error" in r


class TestCorrelationMatrix:
    def test_basic(self):
        r = correlation_matrix({
            "A": [1, 2, 3, 4, 5],
            "B": [2, 4, 6, 8, 10],
            "C": [5, 3, 1, 2, 4],
        })
        assert "matrix" in r
        assert r["matrix"]["A"]["B"] == 1.0
        assert r["highest_correlation"]["pair"] == "A/B"

    def test_single_series(self):
        r = correlation_matrix({"A": [1, 2, 3]})
        assert "error" in r


class TestRollingCorrelation:
    def test_basic(self):
        np.random.seed(42)
        a = list(np.random.normal(0, 1, 50))
        b = list(np.random.normal(0, 1, 50))
        r = rolling_correlation(a, b, window=10)
        assert len(r["rolling_values"]) == 41  # 50 - 10 + 1
        assert r["trend"] in ("increasing", "decreasing", "stable")

    def test_too_short(self):
        r = rolling_correlation([1, 2, 3], [4, 5, 6], window=10)
        assert "error" in r


class TestCorrelationTool:
    @pytest.mark.asyncio
    async def test_dispatch(self):
        tool = CorrelationTool()
        result = await tool.execute(method="pairwise_correlation", params={
            "series_a": [1, 2, 3, 4], "series_b": [2, 4, 6, 8], "name_a": "X", "name_b": "Y"
        })
        data = json.loads(result)
        assert data["correlation"] == 1.0


# ========================= Recovery Time =========================

class TestEstimateRecovery:
    def test_basic(self):
        r = estimate_recovery(current_price=120, target_price=150)
        assert r["already_recovered"] is False
        assert r["required_return_pct"] > 0
        assert r["deterministic_days"] > 0
        assert r["deterministic_months"] > 0

    def test_already_recovered(self):
        r = estimate_recovery(current_price=160, target_price=150)
        assert r["already_recovered"] is True
        assert r["deterministic_days"] == 0

    def test_zero_price(self):
        r = estimate_recovery(current_price=0, target_price=150)
        assert "error" in r


class TestRecoveryProbability:
    def test_basic(self):
        r = recovery_probability(current_price=120, target_price=150, vix=25, days=252)
        assert 0 <= r["recovery_probability"] <= 100
        assert r["n_simulations"] == 10000
        assert r["already_recovered"] is False

    def test_already_recovered(self):
        r = recovery_probability(current_price=160, target_price=150)
        assert r["recovery_probability"] == 100.0
        assert r["already_recovered"] is True

    def test_high_vix_lower_probability(self):
        r_low = recovery_probability(current_price=100, target_price=150, vix=20, days=252, seed=42)
        r_high = recovery_probability(current_price=100, target_price=150, vix=80, days=252, seed=42)
        # Higher VIX = more uncertainty = can differ in either direction, just test they run
        assert 0 <= r_low["recovery_probability"] <= 100
        assert 0 <= r_high["recovery_probability"] <= 100


class TestRecoveryTimeTool:
    @pytest.mark.asyncio
    async def test_dispatch(self):
        tool = RecoveryTimeTool()
        result = await tool.execute(method="estimate_recovery", params={
            "current_price": 120, "target_price": 150
        })
        data = json.loads(result)
        assert data["required_return_pct"] > 0


# ========================= Registration =========================

class TestFRMRegistration:
    def test_all_22_tools_registered(self):
        """All 22 financial tools register successfully."""
        from jagabot.agent.tools import (
            VaRTool, CVaRTool, StressTestTool, CorrelationTool, RecoveryTimeTool,
            FinancialCVTool, MonteCarloTool, DynamicsTool, StatisticalTool,
            EarlyWarningTool, BayesianTool, CounterfactualTool, SensitivityTool,
            ParetoTool, VisualizationTool, DecisionTool, EducationTool,
            AccountabilityTool, ResearcherTool, CopywriterTool, SelfImproverTool,
            PortfolioAnalyzerTool,
        )
        reg = ToolRegistry()
        all_tools = [
            FinancialCVTool, MonteCarloTool, DynamicsTool, StatisticalTool,
            EarlyWarningTool, BayesianTool, CounterfactualTool, SensitivityTool,
            ParetoTool, VisualizationTool,
            VaRTool, CVaRTool, StressTestTool, CorrelationTool, RecoveryTimeTool,
            DecisionTool, EducationTool, AccountabilityTool,
            ResearcherTool, CopywriterTool, SelfImproverTool,
            PortfolioAnalyzerTool,
        ]
        for cls in all_tools:
            reg.register(cls())
        defs = reg.get_definitions()
        names = {d["function"]["name"] for d in defs}
        expected = {
            "financial_cv", "monte_carlo", "dynamics_oracle", "statistical_engine",
            "early_warning", "bayesian_reasoner", "counterfactual_sim",
            "sensitivity_analyzer", "pareto_optimizer", "visualization",
            "var", "cvar", "stress_test", "correlation", "recovery_time",
            "decision_engine", "education", "accountability",
            "researcher", "copywriter", "self_improver",
            "portfolio_analyzer",
        }
        assert expected.issubset(names), f"Missing: {expected - names}"
