"""Tests for v2.4 — Deterministic Finance Agent (PortfolioAnalyzer + Pydantic models)."""

import json
import math
import pytest
from jagabot.agent.tools.portfolio_models import Position, PortfolioInput, MarketData
from jagabot.agent.tools.portfolio_analyzer import (
    PortfolioAnalyzerTool,
    analyze_portfolio,
    stress_test_portfolio,
    analytical_probability,
)
from jagabot.agent.tools.registry import ToolRegistry


# ── Pydantic Model Tests ─────────────────────────────────────────────────


class TestPosition:
    def test_basic_position(self):
        p = Position(symbol="WTI", entry_price=85, current_price=72.5, quantity=100)
        assert p.value == 7250.0
        assert p.pnl == -1250.0
        assert p.pnl_pct == pytest.approx(-14.71, abs=0.01)

    def test_default_weight(self):
        p = Position(symbol="X", entry_price=10, current_price=12, quantity=50)
        assert p.weight == 0.0

    def test_invalid_negative_price(self):
        with pytest.raises(Exception):
            Position(symbol="X", entry_price=-10, current_price=5, quantity=1)

    def test_invalid_zero_quantity(self):
        with pytest.raises(Exception):
            Position(symbol="X", entry_price=10, current_price=5, quantity=0)


class TestPortfolioInput:
    def test_auto_weights(self):
        pi = PortfolioInput(
            capital=100_000,
            positions=[
                Position(symbol="A", entry_price=50, current_price=55, quantity=100),
                Position(symbol="B", entry_price=30, current_price=28, quantity=200),
            ],
        )
        # Auto-assigned equal weights (both were 0)
        assert pi.positions[0].weight == pytest.approx(0.5, abs=0.01)
        assert pi.positions[1].weight == pytest.approx(0.5, abs=0.01)

    def test_leverage(self):
        pi = PortfolioInput(
            capital=100_000,
            leverage=2,
            positions=[Position(symbol="A", entry_price=50, current_price=55, quantity=100)],
        )
        assert pi.total_exposure == 200_000.0

    def test_invalid_zero_capital(self):
        with pytest.raises(Exception):
            PortfolioInput(
                capital=0,
                positions=[Position(symbol="A", entry_price=50, current_price=55, quantity=100)],
            )

    def test_empty_positions(self):
        with pytest.raises(Exception):
            PortfolioInput(capital=100_000, positions=[])


class TestMarketData:
    def test_defaults(self):
        md = MarketData()
        assert md.daily_returns == []
        assert md.vix is None
        assert md.current_prices == {}

    def test_with_data(self):
        md = MarketData(daily_returns=[0.01, -0.02, 0.03], vix=25.5)
        assert len(md.daily_returns) == 3
        assert md.vix == 25.5


# ── Engine Function Tests ────────────────────────────────────────────────


class TestAnalyzePortfolio:
    def test_basic_analysis(self):
        result = analyze_portfolio(
            capital=500_000,
            leverage=1,
            positions=[
                {"symbol": "WTI", "entry_price": 85, "current_price": 72.5,
                 "quantity": 1000, "weight": 0},
            ],
            cash=0,
        )
        assert "positions" in result
        assert result["positions"][0]["pnl"] == -12500.0
        assert result["positions"][0]["units"] == 1000
        assert result["cross_check"]["passed"] is True

    def test_leveraged_analysis(self):
        result = analyze_portfolio(
            capital=500_000,
            leverage=2,
            positions=[
                {"symbol": "WTI", "entry_price": 85, "current_price": 85,
                 "quantity": 1000, "weight": 0},
            ],
            cash=0,
        )
        assert result["leverage"] == 2
        assert result["total_exposure"] == 1_000_000

    def test_weight_derived_units(self):
        result = analyze_portfolio(
            capital=100_000,
            leverage=1,
            positions=[
                {"symbol": "AAPL", "entry_price": 100, "current_price": 110,
                 "quantity": 0, "weight": 0.5},
            ],
        )
        # weight 0.5 * 100k exposure / entry 100 = 500 units
        assert result["positions"][0]["units"] == 500

    def test_cross_check_passes(self):
        result = analyze_portfolio(
            capital=100_000,
            leverage=1,
            positions=[
                {"symbol": "A", "entry_price": 50, "current_price": 60, "quantity": 100, "weight": 0},
            ],
            cash=5000,
        )
        # Equity = capital + total_pnl = 100000 + (100*(60-50)) = 101000
        assert result["cross_check"]["passed"] is True
        assert result["cross_check"]["expected_equity"] == 101_000.0

    def test_margin_data_present(self):
        result = analyze_portfolio(
            capital=500_000, leverage=1,
            positions=[{"symbol": "WTI", "entry_price": 85, "current_price": 72.5,
                        "quantity": 1000, "weight": 0}],
        )
        assert "margin" in result
        assert "active" in result["margin"]


class TestStressTest:
    def test_basic_stress(self):
        positions = [
            {"symbol": "WTI", "entry_price": 85, "current_price": 72.5,
             "quantity": 1000, "weight": 0},
        ]
        result = stress_test_portfolio(
            capital=500_000, leverage=1, positions=positions,
            target_prices={"WTI": 60},
        )
        scenario = result["scenarios"]["WTI"]
        assert scenario["target_price"] == 60
        assert scenario["stress_pnl"] == -25000.0  # 1000 * (60-85)
        assert result["stressed_equity"] < result["current_equity"]

    def test_missing_symbol(self):
        result = stress_test_portfolio(
            capital=100_000, leverage=1,
            positions=[{"symbol": "A", "entry_price": 10, "current_price": 12, "quantity": 100}],
            target_prices={"Z": 5},
        )
        assert "error" in result["scenarios"]["Z"]

    def test_multiple_scenarios(self):
        positions = [
            {"symbol": "A", "entry_price": 100, "current_price": 110, "quantity": 50, "weight": 0},
            {"symbol": "B", "entry_price": 50, "current_price": 48, "quantity": 200, "weight": 0},
        ]
        result = stress_test_portfolio(
            capital=100_000, leverage=1, positions=positions,
            target_prices={"A": 80, "B": 30},
        )
        assert len(result["scenarios"]) == 2
        assert result["total_impact"] < 0  # Both prices dropped


class TestAnalyticalProbability:
    def test_basic_probability(self):
        # Price 100, target 90, mean daily return ~0, vol 2%
        returns = [0.02, -0.02, 0.01, -0.01, 0.015, -0.015, 0.005, -0.005] * 10
        result = analytical_probability(
            current_price=100, target_price=90, daily_returns=returns, days=30,
        )
        assert result["method"] == "analytical_norm_cdf"
        assert 0 < result["probability_below"] < 100
        assert result["probability_above"] == pytest.approx(100 - result["probability_below"], abs=0.01)

    def test_insufficient_returns(self):
        result = analytical_probability(
            current_price=100, target_price=90, daily_returns=[0.01], days=30,
        )
        assert "error" in result

    def test_target_above_current(self):
        returns = [0.01, -0.01, 0.02, -0.02, 0.005, -0.005] * 10
        result = analytical_probability(
            current_price=100, target_price=120, daily_returns=returns, days=30,
        )
        # With mean ~0, probability of going above 120 should be relatively low
        assert result["probability_above"] < 50

    def test_zero_vol(self):
        returns = [0.0] * 20
        result = analytical_probability(
            current_price=100, target_price=90, daily_returns=returns, days=30,
        )
        # Zero vol, price won't move, so P(below 90) = 0
        assert result["probability_below"] == 0.0


# ── Tool Class Tests ─────────────────────────────────────────────────────


class TestPortfolioAnalyzerTool:
    @pytest.fixture
    def tool(self):
        return PortfolioAnalyzerTool()

    def test_name_and_description(self, tool):
        assert tool.name == "portfolio_analyzer"
        assert len(tool.description) >= 50

    def test_description_chain_keywords(self, tool):
        desc = tool.description.lower()
        has_chain = any(kw in desc for kw in ["call this", "chain", "use after", "use before", "feed"])
        has_method = any(kw in desc for kw in ["method", "mode", "pass ", "usage"])
        assert has_chain, "Description must contain chain keyword"
        assert has_method, "Description must contain method keyword"

    @pytest.mark.asyncio
    async def test_analyze_method(self, tool):
        result = await tool.execute(
            method="analyze",
            params={
                "capital": 100_000, "leverage": 1,
                "positions": [{"symbol": "A", "entry_price": 50, "current_price": 55,
                               "quantity": 100, "weight": 0}],
                "cash": 0,
            },
        )
        data = json.loads(result)
        assert "positions" in data
        assert data["cross_check"]["passed"] is True

    @pytest.mark.asyncio
    async def test_stress_test_method(self, tool):
        result = await tool.execute(
            method="stress_test",
            params={
                "capital": 100_000, "leverage": 1,
                "positions": [{"symbol": "A", "entry_price": 50, "current_price": 55,
                               "quantity": 100, "weight": 0}],
                "target_prices": {"A": 40},
            },
        )
        data = json.loads(result)
        assert "scenarios" in data
        assert data["stressed_equity"] < data["current_equity"]

    @pytest.mark.asyncio
    async def test_probability_method(self, tool):
        result = await tool.execute(
            method="probability",
            params={
                "current_price": 100, "target_price": 80,
                "daily_returns": [0.01, -0.01, 0.02, -0.02, 0.005, -0.005] * 10,
                "days": 30,
            },
        )
        data = json.loads(result)
        assert data["method"] == "analytical_norm_cdf"

    @pytest.mark.asyncio
    async def test_unknown_method(self, tool):
        result = await tool.execute(method="nope", params={})
        data = json.loads(result)
        assert "error" in data

    def test_schema(self, tool):
        schema = tool.to_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "portfolio_analyzer"
        props = schema["function"]["parameters"]["properties"]
        assert "method" in props
        assert "params" in props

    def test_parameters_json_schema(self, tool):
        assert "method" in tool.parameters["properties"]
        assert tool.parameters["properties"]["method"]["type"] == "string"


# ── Registration Tests ───────────────────────────────────────────────────


class TestRegistration:
    def test_tool_in_guardian_all_tools(self):
        from jagabot.guardian.tools import ALL_TOOLS
        names = [t().name for t in ALL_TOOLS]
        assert "portfolio_analyzer" in names

    def test_tool_in_exports(self):
        from jagabot.agent.tools import PortfolioAnalyzerTool as PAT
        assert PAT().name == "portfolio_analyzer"

    def test_registry_count(self):
        from jagabot.guardian.tools import ALL_TOOLS
        reg = ToolRegistry()
        for cls in ALL_TOOLS:
            reg.register(cls())
        assert len(reg) == 32

    def test_skill_mentions_tool(self):
        import pathlib
        skill = pathlib.Path(__file__).parent.parent.parent / "jagabot" / "skills" / "financial" / "SKILL.md"
        content = skill.read_text()
        assert "portfolio_analyzer" in content
        assert "Strict Math Protocol" in content
        assert "cross-check" in content.lower() or "cross_check" in content.lower()
