"""Tests for all 8 Jagabot engine tools."""

import json
import math
import pytest

# === Financial Engine Tests ===
from jagabot.agent.tools.financial_cv import (
    calculate_cv,
    calculate_cv_ratios,
    calculate_equity,
    calculate_leveraged_equity,
    check_margin_call,
    FinancialCVTool,
)
from jagabot.agent.tools.monte_carlo import monte_carlo_gbm, MonteCarloTool


class TestCalculateCV:
    def test_basic(self):
        changes = [0.7, 2.4, 4.2, 6.7, 8.3, 7.4]
        cv = calculate_cv(changes)
        assert cv > 0
        assert isinstance(cv, float)

    def test_empty(self):
        assert calculate_cv([]) == 0.0

    def test_single(self):
        assert calculate_cv([5.0]) == 0.0

    def test_identical_values(self):
        assert calculate_cv([3.0, 3.0, 3.0]) == 0.0

    def test_zero_mean(self):
        assert calculate_cv([-1.0, 1.0]) == 0.0  # mean=0 → returns 0


class TestCalculateCVRatios:
    def test_basic(self):
        changes = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        result = calculate_cv_ratios(changes)
        assert "overall_cv" in result
        assert "windows" in result
        assert "pattern" in result
        assert result["pattern"] in ("stable", "increasing_volatility", "decreasing_volatility")

    def test_insufficient_data(self):
        result = calculate_cv_ratios([1.0])
        assert result["pattern"] == "insufficient_data"


class TestCalculateEquity:
    def test_basic(self):
        positions = [
            {"symbol": "AAPL", "quantity": 100, "current_price": 150.0, "entry_price": 140.0},
            {"symbol": "GOOG", "quantity": 50, "current_price": 100.0, "entry_price": 110.0},
        ]
        result = calculate_equity(capital=50000, positions=positions, cash=10000)
        assert result["capital"] == 50000
        assert result["cash"] == 10000
        assert result["total_position"] == 100 * 150 + 50 * 100
        assert result["current"] == 50000 + 20000 + 10000
        assert len(result["positions"]) == 2

    def test_empty_positions(self):
        result = calculate_equity(capital=10000, positions=[], cash=5000)
        assert result["current"] == 15000
        assert result["total_position"] == 0


class TestCalculateLeveragedEquity:
    def test_basic(self):
        result = calculate_leveraged_equity({"equity": 100000, "borrowed": 50000})
        assert result["leverage_ratio"] == 1.5
        assert result["total_assets"] == 150000

    def test_zero_equity(self):
        result = calculate_leveraged_equity({"equity": 0, "borrowed": 50000})
        assert result["leverage_ratio"] == float("inf")


class TestCheckMarginCall:
    def test_no_margin_call(self):
        result = check_margin_call(equity=50000, pos_value=100000, rate=0.25)
        assert result["active"] is False
        assert result["excess"] > 0

    def test_margin_call_active(self):
        result = check_margin_call(equity=10000, pos_value=100000, rate=0.25)
        assert result["active"] is True
        assert result["shortfall"] > 0

    def test_zero_positions(self):
        result = check_margin_call(equity=50000, pos_value=0)
        assert result["active"] is False


class TestMonteCarlo:
    def test_deterministic_with_seed(self):
        r1 = monte_carlo_gbm(100, 0.3, 30, n_sims=1000, seed=42)
        r2 = monte_carlo_gbm(100, 0.3, 30, n_sims=1000, seed=42)
        assert r1["mean"] == r2["mean"]
        assert r1["median"] == r2["median"]

    def test_with_threshold(self):
        result = monte_carlo_gbm(100, 0.3, 30, n_sims=1000, threshold=90, seed=42)
        assert "prob_below" in result
        assert "prob_above" in result
        assert abs(result["prob_below"] + result["prob_above"] - 100) < 0.01

    def test_percentiles(self):
        result = monte_carlo_gbm(100, 0.3, 30, n_sims=1000, seed=42)
        assert "percentiles" in result
        assert result["percentiles"]["p5"] <= result["percentiles"]["p95"]

    def test_structure(self):
        result = monte_carlo_gbm(100, 0.3, 30, n_sims=100, seed=1)
        assert result["initial_price"] == 100
        assert result["days"] == 30
        assert result["simulations"] == 100


class TestFinancialCVTool:
    @pytest.mark.asyncio
    async def test_dispatch(self):
        tool = FinancialCVTool()
        result = await tool.execute(method="calculate_cv", params={"changes": [1, 2, 3, 4, 5]})
        data = json.loads(result)
        assert isinstance(data, float)

    @pytest.mark.asyncio
    async def test_unknown_method(self):
        tool = FinancialCVTool()
        result = await tool.execute(method="nonexistent", params={})
        data = json.loads(result)
        assert "error" in data


class TestMonteCarloTool:
    @pytest.mark.asyncio
    async def test_dispatch(self):
        tool = MonteCarloTool()
        result = await tool.execute(price=100, vol=0.3, days=30, n_sims=100, seed=42)
        data = json.loads(result)
        assert data["simulations"] == 100
        assert data["days"] == 30


# === Dynamics Oracle Tests ===
from jagabot.agent.tools.dynamics import simulate, forecast_convergence, DynamicsTool


class TestDynamicsSimulate:
    def test_basic(self):
        states = simulate(energy=0.5, stability=0.7, steps=10)
        assert len(states) == 10
        assert all("energy" in s and "stability" in s for s in states)
        assert states[0]["step"] == 1

    def test_growth_models(self):
        for model in ["exponential", "logistic", "linear", "decay"]:
            states = simulate(energy=0.5, stability=0.5, steps=5, growth_model=model)
            assert len(states) == 5

    def test_defense(self):
        no_def = simulate(energy=0.5, stability=0.5, steps=10, defense=0.0)
        with_def = simulate(energy=0.5, stability=0.5, steps=10, defense=0.8)
        # Defense should generally preserve stability better
        assert with_def[-1]["stability"] >= no_def[-1]["stability"] - 0.5

    def test_risk_levels(self):
        states = simulate(energy=0.5, stability=0.1, steps=5)
        assert all(s["risk_level"] in ("low", "moderate", "high", "critical") for s in states)


class TestForecastConvergence:
    def test_convergence(self):
        result = forecast_convergence(energy=0.5, stability=0.7, target_energy=0.9, max_steps=200)
        assert "converged" in result
        assert "steps_needed" in result


# === Statistical Engine Tests ===
from jagabot.agent.tools.statistical import (
    confidence_interval,
    hypothesis_test,
    distribution_analysis,
    StatisticalTool,
)


class TestConfidenceInterval:
    def test_basic(self):
        data = [10, 12, 14, 11, 13, 15, 12, 14, 13, 11]
        result = confidence_interval(data)
        assert result["lower"] < result["mean"] < result["upper"]
        assert result["n"] == 10
        assert result["confidence"] == 0.95

    def test_empty(self):
        result = confidence_interval([])
        assert "error" in result

    def test_single_value(self):
        result = confidence_interval([5.0])
        assert result["mean"] == 5.0
        assert result["lower"] == result["upper"]


class TestHypothesisTest:
    def test_reject(self):
        data = [10, 11, 12, 10, 11, 12, 10, 11, 12, 11]
        result = hypothesis_test(data, mu0=0.0)
        assert result["reject"] is True

    def test_fail_to_reject(self):
        data = [0.1, -0.1, 0.05, -0.05, 0.02, -0.02]
        result = hypothesis_test(data, mu0=0.0)
        assert result["reject"] is False


class TestDistributionAnalysis:
    def test_basic(self):
        data = list(range(1, 101))
        result = distribution_analysis(data)
        assert result["n"] == 100
        assert "skewness" in result
        assert "kurtosis" in result
        assert result["shape"] in ("normal-like", "skewed", "heavy-tailed")


# === Early Warning Tests ===
from jagabot.agent.tools.early_warning import (
    detect_warning_signals,
    classify_risk_level,
    EarlyWarningTool,
)


class TestDetectWarningSignals:
    def test_normal(self):
        result = detect_warning_signals({"volatility": 0.1, "drawdown": 0.02})
        assert result["level"] == "normal"
        assert result["signal_count"] == 0

    def test_critical(self):
        result = detect_warning_signals({
            "volatility": 0.8, "drawdown": 0.3, "correlation_shift": 0.5
        })
        assert result["level"] in ("warning", "critical")
        assert result["signal_count"] >= 3


class TestClassifyRiskLevel:
    def test_low(self):
        result = classify_risk_level([])
        assert result["classification"] == "low"

    def test_high(self):
        signals = [
            {"severity": "high"}, {"severity": "high"}, {"severity": "medium"}
        ]
        result = classify_risk_level(signals)
        assert result["classification"] in ("high", "critical")


# === Bayesian Reasoner Tests ===
from jagabot.agent.tools.bayesian import (
    update_belief,
    sequential_update,
    bayesian_network_inference,
    BayesianTool,
)


class TestUpdateBelief:
    def test_basic(self):
        result = update_belief(prior=0.5, likelihood=0.8)
        assert 0 < result["posterior"] <= 1
        assert result["direction"] == "strengthened"

    def test_weakened(self):
        result = update_belief(prior=0.8, likelihood=0.2)
        assert result["posterior"] < 0.8
        assert result["direction"] == "weakened"

    def test_boundary(self):
        result = update_belief(prior=0.0, likelihood=0.9)
        assert result["posterior"] == 0.0


class TestSequentialUpdate:
    def test_basic(self):
        result = sequential_update(prior=0.5, observations=[
            {"likelihood": 0.7}, {"likelihood": 0.8}, {"likelihood": 0.6}
        ])
        assert result["n_updates"] == 3
        assert len(result["history"]) == 4  # initial + 3 updates


class TestBayesianNetwork:
    def test_basic(self):
        nodes = {
            "market_crash": {"prior": 0.1, "parents": {}},
            "oil_drop": {"prior": 0.3, "parents": {"market_crash": 0.5}},
        }
        result = bayesian_network_inference(nodes, evidence={"market_crash": 0.9})
        assert "posteriors" in result
        assert "market_crash" in result["posteriors"]


# === Counterfactual Simulator Tests ===
from jagabot.agent.tools.counterfactual import (
    simulate_counterfactual,
    compare_scenarios,
    CounterfactualTool,
)


class TestSimulateCounterfactual:
    def test_basic(self):
        baseline = {"energy": 0.5, "stability": 0.7}
        changes = {"defense": 0.5}
        result = simulate_counterfactual(baseline, changes, steps=5)
        assert "baseline_final" in result
        assert "counterfactual_final" in result
        assert "energy_impact" in result


class TestCompareScenarios:
    def test_basic(self):
        scenarios = [
            {"name": "optimistic", "energy": 0.8, "stability": 0.9},
            {"name": "pessimistic", "energy": 0.2, "stability": 0.3},
            {"name": "neutral", "energy": 0.5, "stability": 0.5},
        ]
        result = compare_scenarios(scenarios, steps=5)
        assert result["scenarios_compared"] == 3
        assert result["best"] is not None
        assert all(r.get("rank") for r in result["results"])


# === Sensitivity Analyzer Tests ===
from jagabot.agent.tools.sensitivity import (
    analyze_sensitivity,
    tornado_analysis,
    SensitivityTool,
)


class TestAnalyzeSensitivity:
    def test_basic(self):
        base = {"energy": 0.5, "stability": 0.5, "params": {"growth_rate": 0.05}}
        vary = {
            "energy": [0.2, 0.8],
            "params.growth_rate": [0.01, 0.10],
        }
        result = analyze_sensitivity(base, vary, steps=5)
        assert "sensitivities" in result
        assert "most_sensitive" in result


class TestTornadoAnalysis:
    def test_basic(self):
        base = {"energy": 0.5, "stability": 0.5}
        params = {"energy": [0.2, 0.8], "stability": [0.2, 0.8]}
        result = tornado_analysis(base, params, steps=5)
        assert "bars" in result
        assert len(result["bars"]) == 2


# === Pareto Optimizer Tests ===
from jagabot.agent.tools.pareto import (
    find_pareto_optimal,
    rank_strategies,
    optimize_portfolio_allocation,
    ParetoTool,
)


class TestFindParetoOptimal:
    def test_basic(self):
        solutions = [
            {"name": "A", "return": 10, "risk": 5},
            {"name": "B", "return": 8, "risk": 3},
            {"name": "C", "return": 6, "risk": 8},
            {"name": "D", "return": 12, "risk": 7},
        ]
        result = find_pareto_optimal(solutions, objectives=["return", "risk"], maximize=[True, False])
        assert result["pareto_count"] >= 1
        assert result["total_solutions"] == 4

    def test_empty(self):
        result = find_pareto_optimal([], objectives=["x"])
        assert len(result["pareto_front"]) == 0


class TestRankStrategies:
    def test_basic(self):
        strategies = [
            {"name": "hold", "expected_return": 5, "risk": 8, "cost": 0},
            {"name": "hedge", "expected_return": 3, "risk": 3, "cost": 100},
            {"name": "exit", "expected_return": 0, "risk": 0, "cost": 50},
        ]
        criteria = {
            "expected_return": {"weight": 0.5, "maximize": True},
            "risk": {"weight": 0.3, "maximize": False},
            "cost": {"weight": 0.2, "maximize": False},
        }
        result = rank_strategies(strategies, criteria)
        assert result["best"] is not None
        assert result["ranked"][0]["_rank"] == 1


class TestOptimizePortfolio:
    def test_basic(self):
        assets = [
            {"name": "stocks", "expected_return": 0.10, "risk": 0.20},
            {"name": "bonds", "expected_return": 0.04, "risk": 0.05},
            {"name": "gold", "expected_return": 0.06, "risk": 0.12},
        ]
        result = optimize_portfolio_allocation(assets, total_capital=100000, risk_tolerance=0.5)
        assert len(result["allocations"]) == 3
        total_alloc = sum(a["amount"] for a in result["allocations"])
        assert abs(total_alloc - 100000) < 1.0  # within rounding


# === Tool Registration Tests ===
from jagabot.guardian.tools import register_jagabot_tools, ALL_TOOLS
from jagabot.agent.tools.registry import ToolRegistry


class TestToolRegistration:
    def test_register_all(self):
        registry = ToolRegistry()
        register_jagabot_tools(registry)
        assert len(registry) == 32

    def test_all_tools_have_schema(self):
        for tool_cls in ALL_TOOLS:
            tool = tool_cls()
            schema = tool.to_schema()
            assert schema["type"] == "function"
            assert "name" in schema["function"]
            assert "description" in schema["function"]
            assert "parameters" in schema["function"]


# === Standardized Monte Carlo Tests ===
from jagabot.agent.tools.monte_carlo import standard_monte_carlo, MonteCarloTool


class TestStandardMonteCarlo:
    def test_deterministic_with_seed(self):
        r1 = standard_monte_carlo(current_price=52.80, target_price=45, vix=58, seed=42)
        r2 = standard_monte_carlo(current_price=52.80, target_price=45, vix=58, seed=42)
        assert r1["probability"] == r2["probability"]
        assert r1["mean_price"] == r2["mean_price"]

    def test_vix_58_probability_range(self):
        """VIX=58 should give probability in ~15-30% range per MCedit.md."""
        result = standard_monte_carlo(current_price=52.80, target_price=45, vix=58, seed=42)
        assert 10 <= result["probability"] <= 35, f"Got {result['probability']}%"

    def test_daily_vol_conversion(self):
        result = standard_monte_carlo(current_price=100, target_price=80, vix=58)
        assert result["annual_vol"] == 0.58
        expected_daily = 0.58 / (252 ** 0.5)
        assert abs(result["daily_vol"] - expected_daily) < 0.0001

    def test_has_confidence_interval(self):
        result = standard_monte_carlo(current_price=52.80, target_price=45, vix=58)
        assert "ci_95" in result
        assert len(result["ci_95"]) == 2
        assert result["ci_95"][0] < result["probability"] < result["ci_95"][1]

    def test_all_prices_returned(self):
        result = standard_monte_carlo(current_price=100, target_price=80, vix=30, n_simulations=500)
        assert "all_prices" in result
        assert len(result["all_prices"]) == 500

    def test_percentiles_present(self):
        result = standard_monte_carlo(current_price=100, target_price=80, vix=30)
        for key in ["p5", "p10", "p25", "p50", "p75", "p90", "p95"]:
            assert key in result["percentiles"]

    def test_expected_value_if_below(self):
        result = standard_monte_carlo(current_price=100, target_price=80, vix=50, seed=42)
        if result["probability"] > 0:
            assert result["expected_value_if_below"] is not None
            assert result["expected_value_if_below"] < 80


class TestMonteCarloToolNew:
    @pytest.mark.asyncio
    async def test_standard_call(self):
        tool = MonteCarloTool()
        result = await tool.execute(current_price=52.80, target_price=45, vix=58, seed=42, n_simulations=1000)
        data = json.loads(result)
        assert "probability" in data
        assert "ci_95" in data
        assert "all_prices" not in data  # stripped from tool output

    @pytest.mark.asyncio
    async def test_legacy_call(self):
        tool = MonteCarloTool()
        result = await tool.execute(price=100, vol=0.3, days=30, threshold=80, seed=42)
        data = json.loads(result)
        assert "prob_below" in data
        assert data["volatility"] == 0.3


# === Visualization Tool Tests ===
from jagabot.agent.tools.visualization import (
    generate_ascii_dashboard,
    generate_markdown_dashboard,
    generate_dashboard_base64,
    VisualizationTool,
)


class TestASCIIDashboard:
    def test_generates_string(self):
        prices = list(range(40, 70)) * 100
        result = generate_ascii_dashboard(prices, 52.80, 45, 17.2)
        assert isinstance(result, str)
        assert "JAGABOT CRISIS DASHBOARD" in result
        assert "17.20%" in result

    def test_risk_levels(self):
        prices = list(range(40, 70)) * 100
        assert "CRITICAL" in generate_ascii_dashboard(prices, 52.80, 45, 35)
        assert "HIGH" in generate_ascii_dashboard(prices, 52.80, 45, 20)
        assert "MODERATE" in generate_ascii_dashboard(prices, 52.80, 45, 10)


class TestMarkdownDashboard:
    def test_generates_markdown(self):
        result = generate_markdown_dashboard(
            probability=17.2, equity=50000, loss=-2670000,
            current_price=52.80, target_price=45,
        )
        assert "# JAGABOT CRISIS ANALYSIS" in result
        assert "17.2%" in result

    def test_with_scenarios(self):
        scenarios = {"Cut Loss": {"loss_mm": 2.67, "prob": 100, "risk": 1}}
        result = generate_markdown_dashboard(
            probability=17.2, equity=50000, loss=-2670000,
            current_price=52.80, target_price=45, scenarios=scenarios,
        )
        assert "Cut Loss" in result
        assert "Loss Scenarios" in result

    def test_with_ci(self):
        result = generate_markdown_dashboard(
            probability=17.2, equity=50000, loss=0,
            current_price=52.80, target_price=45, ci_95=[15.0, 19.5],
        )
        assert "15.00%" in result
        assert "19.50%" in result


class TestBase64Dashboard:
    def test_generates_base64(self):
        import numpy as np
        np.random.seed(42)
        prices = (np.random.normal(52, 5, 1000)).tolist()
        result = generate_dashboard_base64(prices, 52.80, 45, 17.2)
        assert isinstance(result, str)
        assert len(result) > 100  # non-trivial base64 string

    def test_with_loss_scenarios(self):
        import numpy as np
        np.random.seed(42)
        prices = (np.random.normal(52, 5, 500)).tolist()
        scenarios = {
            "Cut Loss": {"loss_mm": 2.67, "ev": -2.1, "risk": 1},
            "Do Nothing": {"loss_mm": 4.0, "ev": -3.0, "risk": 5},
        }
        result = generate_dashboard_base64(prices, 52.80, 45, 17.2, scenarios)
        assert isinstance(result, str)
        assert len(result) > 100


class TestVisualizationTool:
    @pytest.mark.asyncio
    async def test_ascii_mode(self):
        tool = VisualizationTool()
        prices = list(range(40, 70)) * 100
        result = await tool.execute(
            mode="ascii", prices=prices,
            current_price=52.80, target_price=45, probability=17.2,
        )
        data = json.loads(result)
        assert data["format"] == "ascii"
        assert "JAGABOT" in data["chart"]

    @pytest.mark.asyncio
    async def test_markdown_mode(self):
        tool = VisualizationTool()
        result = await tool.execute(
            mode="markdown", current_price=52.80, target_price=45,
            probability=17.2, equity=50000, loss=-2670000,
        )
        data = json.loads(result)
        assert data["format"] == "markdown"
        assert "JAGABOT" in data["dashboard"]

    @pytest.mark.asyncio
    async def test_base64_mode(self):
        import numpy as np
        np.random.seed(42)
        tool = VisualizationTool()
        prices = (np.random.normal(52, 5, 500)).tolist()
        result = await tool.execute(
            mode="base64", prices=prices,
            current_price=52.80, target_price=45, probability=17.2,
        )
        data = json.loads(result)
        assert data["format"] == "base64_png"
        assert len(data["data"]) > 100

    @pytest.mark.asyncio
    async def test_base64_requires_prices(self):
        tool = VisualizationTool()
        result = await tool.execute(
            mode="base64", current_price=52.80, target_price=45, probability=17.2,
        )
        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_unknown_mode(self):
        tool = VisualizationTool()
        result = await tool.execute(
            mode="unknown", current_price=52.80, target_price=45, probability=17.2,
        )
        data = json.loads(result)
        assert "error" in data


# === Locale-aware Label Tests ===
from jagabot.agent.tools.financial_cv import calculate_cv_ratios
from jagabot.agent.tools.early_warning import detect_warning_signals, classify_risk_level


class TestLocalePatternLabels:
    def test_cv_ratios_english_default(self):
        changes = [0.7, 2.4, 4.2, 6.7, 8.3, 7.4, 5.1, 3.2]
        result = calculate_cv_ratios(changes)
        assert result["pattern"] in ("stable", "increasing_volatility", "decreasing_volatility")

    def test_cv_ratios_malay(self):
        changes = [0.7, 2.4, 4.2, 6.7, 8.3, 7.4, 5.1, 3.2]
        result = calculate_cv_ratios(changes, locale="ms")
        assert result["pattern"] in ("STABIL", "TIDAK STABIL", "STABIL MENURUN")

    def test_cv_ratios_indonesian(self):
        changes = [0.7, 2.4, 4.2, 6.7, 8.3, 7.4, 5.1, 3.2]
        result = calculate_cv_ratios(changes, locale="id")
        assert result["pattern"] in ("STABIL", "TIDAK STABIL", "STABIL MENURUN")

    def test_cv_ratios_insufficient_data_malay(self):
        result = calculate_cv_ratios([1.0], locale="ms")
        assert result["pattern"] == "DATA TIDAK CUKUP"

    def test_cv_ratios_unknown_locale_falls_back_to_english(self):
        changes = [0.7, 2.4, 4.2, 6.7, 8.3, 7.4, 5.1, 3.2]
        result = calculate_cv_ratios(changes, locale="xx")
        assert result["pattern"] in ("stable", "increasing_volatility", "decreasing_volatility")


class TestLocaleWarningLabels:
    def test_detect_warnings_english(self):
        result = detect_warning_signals({"volatility": 0.6, "drawdown": 0.25})
        assert result["level"] == "critical"

    def test_detect_warnings_malay(self):
        result = detect_warning_signals({"volatility": 0.6, "drawdown": 0.25}, locale="ms")
        assert result["level"] == "KRITIKAL"

    def test_detect_warnings_normal_malay(self):
        result = detect_warning_signals({"volatility": 0.1}, locale="ms")
        assert result["level"] == "NORMAL"

    def test_classify_risk_english(self):
        signals = [{"severity": "high"}, {"severity": "high"}, {"severity": "high"}, {"severity": "critical"}]
        result = classify_risk_level(signals)
        assert result["classification"] == "critical"

    def test_classify_risk_malay(self):
        signals = [{"severity": "high"}, {"severity": "high"}, {"severity": "high"}, {"severity": "critical"}]
        result = classify_risk_level(signals, locale="ms")
        assert result["classification"] == "KRITIKAL"
        assert result["recommended_action"] == "TINDAKAN SEGERA DIPERLUKAN"

    def test_classify_risk_low_indonesian(self):
        signals = [{"severity": "low"}]
        result = classify_risk_level(signals, locale="id")
        assert result["classification"] == "RENDAH"
        assert result["recommended_action"] == "LANJUTKAN PEMANTAUAN"
