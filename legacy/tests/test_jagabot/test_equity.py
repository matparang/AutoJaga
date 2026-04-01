"""v2.7 — Equity consistency tests against Colab ground truth.

Verifies that ALL equity calculations use the correct formula:
    equity = capital + total_pnl
NOT the wrong formula:
    equity = capital + position_value + cash (double-counts capital for leveraged)
"""

import json
import math

import pytest

from jagabot.agent.tools.portfolio_analyzer import (
    analyze_portfolio,
    stress_test_portfolio,
    analytical_probability,
    PortfolioAnalyzerTool,
)
from jagabot.agent.tools.financial_cv import calculate_equity, check_margin_call
from jagabot.guardian.subagents.billing import billing_agent
from jagabot.swarm.planner import (
    TaskPlanner,
    _crisis_tasks,
    _stock_tasks,
    _risk_tasks,
    _portfolio_tasks,
    _general_tasks,
)


# ── Colab ground truth constants ──────────────────────────────────────

CAPITAL = 1_000_000
LEVERAGE = 3
EXPOSURE = CAPITAL * LEVERAGE  # 3,000,000

WTI_BUY, WTI_NOW = 95.0, 82.50
BRENT_BUY, BRENT_NOW = 98.0, 85.20

WTI_UNITS = EXPOSURE * 0.55 / WTI_BUY   # 17368.42
BRENT_UNITS = EXPOSURE * 0.25 / BRENT_BUY  # 7653.06

WTI_PNL = (WTI_NOW - WTI_BUY) * WTI_UNITS      # -217,105
BRENT_PNL = (BRENT_NOW - BRENT_BUY) * BRENT_UNITS  # -97,959
TOTAL_PNL = WTI_PNL + BRENT_PNL                 # -315,064

CORRECT_EQUITY = CAPITAL + TOTAL_PNL             # 684,935
MARGIN_REQ = EXPOSURE / LEVERAGE                 # 1,000,000
CASH = EXPOSURE * 0.20                           # 600,000

# Forbidden wrong values (from the bug)
WRONG_EQUITY_APPROX = [3_284_935, 3_684_935, 2_284_936]

POSITIONS_WEIGHTED = [
    {"symbol": "WTI", "weight": 0.55, "entry_price": WTI_BUY,
     "current_price": WTI_NOW, "quantity": 0},
    {"symbol": "BRENT", "weight": 0.25, "entry_price": BRENT_BUY,
     "current_price": BRENT_NOW, "quantity": 0},
]

POSITIONS_EXPLICIT = [
    {"symbol": "WTI", "quantity": WTI_UNITS, "entry_price": WTI_BUY,
     "current_price": WTI_NOW},
    {"symbol": "BRENT", "quantity": BRENT_UNITS, "entry_price": BRENT_BUY,
     "current_price": BRENT_NOW},
]


# ── Test: Leveraged Equity (Colab Ground Truth) ──────────────────────

class TestLeveragedEquity:
    """Core equity formula tests against Colab ground truth."""

    def test_equity_matches_colab(self):
        result = analyze_portfolio(
            capital=CAPITAL, leverage=LEVERAGE,
            positions=POSITIONS_WEIGHTED, cash=CASH,
        )
        assert abs(result["current_equity"] - CORRECT_EQUITY) < 1.0

    def test_total_pnl_matches_colab(self):
        result = analyze_portfolio(
            capital=CAPITAL, leverage=LEVERAGE,
            positions=POSITIONS_WEIGHTED, cash=CASH,
        )
        assert abs(result["total_pnl"] - TOTAL_PNL) < 1.0

    def test_cross_check_passes(self):
        result = analyze_portfolio(
            capital=CAPITAL, leverage=LEVERAGE,
            positions=POSITIONS_WEIGHTED, cash=CASH,
        )
        assert result["cross_check"]["passed"] is True
        assert result["cross_check"]["delta"] < 1.0

    def test_loan_in_equity_details(self):
        result = analyze_portfolio(
            capital=CAPITAL, leverage=LEVERAGE,
            positions=POSITIONS_WEIGHTED, cash=CASH,
        )
        assert result["equity_details"]["loan"] == 2_000_000.0

    def test_exposure_correct(self):
        result = analyze_portfolio(
            capital=CAPITAL, leverage=LEVERAGE,
            positions=POSITIONS_WEIGHTED, cash=CASH,
        )
        assert result["total_exposure"] == EXPOSURE


# ── Test: Margin Call Detection ───────────────────────────────────────

class TestMarginCall:
    """Margin call must be triggered when equity < margin requirement."""

    def test_margin_call_triggered(self):
        result = analyze_portfolio(
            capital=CAPITAL, leverage=LEVERAGE,
            positions=POSITIONS_WEIGHTED, cash=CASH,
        )
        assert result["margin"]["active"] is True

    def test_margin_ratio_below_threshold(self):
        result = analyze_portfolio(
            capital=CAPITAL, leverage=LEVERAGE,
            positions=POSITIONS_WEIGHTED, cash=CASH,
        )
        # margin_ratio = equity / exposure = ~684K / 3M = 0.228
        # rate = 1/leverage = 0.333
        assert result["margin"]["margin_ratio"] < (1.0 / LEVERAGE)

    def test_no_margin_call_when_profitable(self):
        """When positions are profitable, equity > capital, no margin call."""
        result = analyze_portfolio(
            capital=100_000, leverage=2,
            positions=[{"symbol": "A", "entry_price": 50, "current_price": 80,
                        "quantity": 2000, "weight": 0}],
            cash=0,
        )
        # pnl = 2000 * 30 = 60,000; equity = 160,000; exposure = 200,000
        # ratio = 160K/200K = 0.8 > 0.5 (1/leverage)
        assert result["margin"]["active"] is False


# ── Test: Stress Test Equity ──────────────────────────────────────────

class TestStressTestEquity:
    """Stress test must use correct base equity."""

    def test_stress_at_75_matches_colab(self):
        result = stress_test_portfolio(
            capital=CAPITAL, leverage=LEVERAGE,
            positions=POSITIONS_WEIGHTED,
            target_prices={"WTI": 75.0},
            cash=CASH,
        )
        # Colab: stress @75: 554,672
        assert abs(result["stressed_equity"] - 554_672) < 200

    def test_stress_at_70(self):
        result = stress_test_portfolio(
            capital=CAPITAL, leverage=LEVERAGE,
            positions=POSITIONS_WEIGHTED,
            target_prices={"WTI": 70.0},
            cash=CASH,
        )
        # Colab: stress @70: 467,830
        assert abs(result["stressed_equity"] - 467_830) < 200

    def test_stress_at_65(self):
        result = stress_test_portfolio(
            capital=CAPITAL, leverage=LEVERAGE,
            positions=POSITIONS_WEIGHTED,
            target_prices={"WTI": 65.0},
            cash=CASH,
        )
        # Colab: stress @65: 380,988
        assert abs(result["stressed_equity"] - 380_988) < 200

    def test_stress_base_equity_correct(self):
        result = stress_test_portfolio(
            capital=CAPITAL, leverage=LEVERAGE,
            positions=POSITIONS_WEIGHTED,
            target_prices={"WTI": 75.0},
            cash=CASH,
        )
        assert abs(result["current_equity"] - CORRECT_EQUITY) < 1.0


# ── Test: Non-Leveraged Equity ────────────────────────────────────────

class TestNonLeveragedEquity:
    """Non-leveraged portfolios: equity = capital + total_pnl."""

    def test_simple_profit(self):
        result = analyze_portfolio(
            capital=100_000, leverage=1,
            positions=[{"symbol": "A", "entry_price": 50, "current_price": 60,
                        "quantity": 100, "weight": 0}],
            cash=0,
        )
        # pnl = 100 * 10 = 1000; equity = 101,000
        assert result["current_equity"] == 101_000.0

    def test_simple_loss(self):
        result = analyze_portfolio(
            capital=100_000, leverage=1,
            positions=[{"symbol": "A", "entry_price": 50, "current_price": 40,
                        "quantity": 100, "weight": 0}],
            cash=0,
        )
        # pnl = 100 * (-10) = -1000; equity = 99,000
        assert result["current_equity"] == 99_000.0

    def test_with_cash(self):
        result = analyze_portfolio(
            capital=100_000, leverage=1,
            positions=[{"symbol": "A", "entry_price": 50, "current_price": 60,
                        "quantity": 100, "weight": 0}],
            cash=5000,
        )
        # equity = capital + pnl = 100,000 + 1,000 = 101,000
        # Cash is part of deployment, not additional to capital
        assert result["current_equity"] == 101_000.0
        assert result["cross_check"]["passed"] is True

    def test_no_positions(self):
        result = analyze_portfolio(
            capital=50_000, leverage=1, positions=[], cash=0,
        )
        assert result["current_equity"] == 50_000.0


# ── Test: Regression — Forbidden Values ───────────────────────────────

class TestEquityRegression:
    """Wrong equity values from old formula must never appear."""

    def test_forbidden_values_not_in_output(self):
        result = analyze_portfolio(
            capital=CAPITAL, leverage=LEVERAGE,
            positions=POSITIONS_WEIGHTED, cash=CASH,
        )
        result_str = str(result)
        for bad_value in WRONG_EQUITY_APPROX:
            assert str(bad_value) not in result_str, \
                f"Forbidden equity value {bad_value} found in output"

    def test_equity_never_exceeds_exposure(self):
        """For a losing portfolio, equity must be less than capital."""
        result = analyze_portfolio(
            capital=CAPITAL, leverage=LEVERAGE,
            positions=POSITIONS_WEIGHTED, cash=CASH,
        )
        assert result["current_equity"] < CAPITAL


# ── Test: Planner Uses Exposure as portfolio_value ────────────────────

class TestPlannerPortfolioValue:
    """Planner must pass exposure (capital × leverage) to VaR/stress tools."""

    def _extract_portfolio_values(self, tasks):
        """Extract all portfolio_value params from task groups."""
        values = []
        for group in tasks:
            for task in group:
                pv = task.params.get("portfolio_value")
                if pv is not None:
                    values.append(pv)
        return values

    def test_crisis_uses_exposure(self):
        tasks = _crisis_tasks({"capital": 1_000_000, "leverage": 3})
        pvs = self._extract_portfolio_values(tasks)
        assert all(pv == 3_000_000 for pv in pvs), f"Expected 3M, got {pvs}"

    def test_stock_uses_exposure(self):
        tasks = _stock_tasks({"capital": 500_000, "leverage": 2})
        pvs = self._extract_portfolio_values(tasks)
        assert all(pv == 1_000_000 for pv in pvs), f"Expected 1M, got {pvs}"

    def test_risk_uses_exposure(self):
        tasks = _risk_tasks({"capital": 200_000, "leverage": 5})
        pvs = self._extract_portfolio_values(tasks)
        assert all(pv == 1_000_000 for pv in pvs), f"Expected 1M, got {pvs}"

    def test_portfolio_uses_exposure(self):
        tasks = _portfolio_tasks({"capital": 100_000, "leverage": 3})
        pvs = self._extract_portfolio_values(tasks)
        assert all(pv == 300_000 for pv in pvs), f"Expected 300K, got {pvs}"

    def test_general_uses_exposure(self):
        tasks = _general_tasks({"capital": 100_000, "leverage": 2})
        pvs = self._extract_portfolio_values(tasks)
        assert all(pv == 200_000 for pv in pvs), f"Expected 200K, got {pvs}"

    def test_default_leverage_1(self):
        """When no leverage, exposure = capital (backward compat)."""
        tasks = _crisis_tasks({"capital": 100_000})
        pvs = self._extract_portfolio_values(tasks)
        assert all(pv == 100_000 for pv in pvs)


# ── Test: Billing Agent Leveraged Equity ──────────────────────────────

class TestBillingLeveragedEquity:
    """Billing agent must use correct equity for leveraged portfolios."""

    @pytest.mark.asyncio
    async def test_billing_leveraged_equity(self):
        portfolio = {
            "capital": CAPITAL,
            "leverage": LEVERAGE,
            "positions": POSITIONS_EXPLICIT,
            "cash": CASH,
            "maintenance_rate": 1.0 / LEVERAGE,
        }
        market_data = {
            "current": {"WTI": WTI_NOW},
            "monte_carlo": {"threshold": 80.0, "n_sims": 1000, "days": 30, "seed": 42},
        }
        support_results = {
            "cv_analysis": {"WTI": {"cv": 0.3, "pattern": "declining"}},
        }

        result = await billing_agent(portfolio, market_data, support_results)
        equity = result["equity"]["current"]
        assert abs(equity - CORRECT_EQUITY) < 1.0, \
            f"Billing equity {equity} != expected {CORRECT_EQUITY}"

    @pytest.mark.asyncio
    async def test_billing_margin_call_leveraged(self):
        portfolio = {
            "capital": CAPITAL,
            "leverage": LEVERAGE,
            "positions": POSITIONS_EXPLICIT,
            "cash": CASH,
        }
        market_data = {
            "current": {"WTI": WTI_NOW},
            "monte_carlo": {"threshold": 80.0, "n_sims": 1000, "days": 30, "seed": 42},
        }
        support_results = {
            "cv_analysis": {"WTI": {"cv": 0.3}},
        }

        result = await billing_agent(portfolio, market_data, support_results)
        assert result["margin_call"]["active"] is True

    @pytest.mark.asyncio
    async def test_billing_non_leveraged_unchanged(self):
        """Non-leveraged billing should still work."""
        portfolio = {
            "capital": 100_000,
            "positions": [
                {"symbol": "A", "quantity": 1000, "current_price": 70, "entry_price": 65},
            ],
            "cash": 20_000,
        }
        market_data = {
            "current": {"price": 70},
            "monte_carlo": {"n_sims": 500, "days": 10, "seed": 42},
        }
        result = await billing_agent(portfolio, market_data)
        assert "equity" in result
        assert result["equity"]["capital"] == 100_000


# ── Test: PortfolioAnalyzerTool integration ───────────────────────────

class TestToolIntegration:
    @pytest.fixture
    def tool(self):
        return PortfolioAnalyzerTool()

    @pytest.mark.asyncio
    async def test_tool_leveraged_equity(self, tool):
        result = await tool.execute(
            method="analyze",
            params={
                "capital": CAPITAL, "leverage": LEVERAGE,
                "positions": [
                    {"symbol": "WTI", "weight": 0.55, "entry_price": WTI_BUY,
                     "current_price": WTI_NOW, "quantity": 0},
                    {"symbol": "BRENT", "weight": 0.25, "entry_price": BRENT_BUY,
                     "current_price": BRENT_NOW, "quantity": 0},
                ],
                "cash": CASH,
            },
        )
        data = json.loads(result)
        assert abs(data["current_equity"] - CORRECT_EQUITY) < 1.0
        assert data["margin"]["active"] is True
        assert data["cross_check"]["passed"] is True
