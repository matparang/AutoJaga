"""Integration tests for Jagabot subagents and orchestrator pipeline."""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from jagabot.guardian.subagents.support import support_agent
from jagabot.guardian.subagents.billing import billing_agent
from jagabot.guardian.subagents.supervisor import supervisor_agent
from jagabot.guardian.core import Jagabot


# === Support Subagent Tests ===
class TestSupportAgent:
    @pytest.mark.asyncio
    async def test_basic_flow(self):
        market_data = {
            "historical_changes": {
                "WTI": [0.7, 2.4, 4.2, 6.7, 8.3, 7.4, 5.1, 3.2],
                "BRENT": [1.1, 2.0, 3.5, 5.0, 6.2, 4.8],
            },
            "current": {
                "volatility": 0.4,
                "drawdown": 0.15,
                "volume_change": 1.5,
            },
        }
        web_results = {
            "query": "oil prices",
            "news": [{"title": "Oil up 2%", "url": "http://example.com"}],
            "result_count": 1,
        }

        result = await support_agent(market_data, web_results)

        assert "cv_analysis" in result
        assert "WTI" in result["cv_analysis"]
        assert "warnings" in result
        assert "risk_classification" in result
        assert result["cv_analysis"]["WTI"]["cv"] > 0

    @pytest.mark.asyncio
    async def test_empty_market_data(self):
        result = await support_agent(market_data={}, web_results={"query": "", "news": [], "result_count": 0})
        assert result["cv_analysis"] == {}
        assert result["warnings"]["level"] == "normal"


# === Billing Subagent Tests ===
class TestBillingAgent:
    @pytest.mark.asyncio
    async def test_basic_flow(self):
        portfolio = {
            "capital": 100000,
            "positions": [
                {"symbol": "WTI", "quantity": 1000, "current_price": 70.0, "entry_price": 65.0},
            ],
            "cash": 20000,
            "maintenance_rate": 0.25,
        }
        market_data = {
            "current": {"WTI": 70.0},
            "monte_carlo": {"threshold": 60.0, "n_sims": 1000, "days": 30, "seed": 42},
        }
        support_results = {
            "cv_analysis": {"WTI": {"cv": 0.3, "pattern": "stable"}},
        }

        result = await billing_agent(portfolio, market_data, support_results)

        assert "probability" in result
        assert "equity" in result
        assert "margin_call" in result
        assert "confidence_interval" in result
        assert result["equity"]["capital"] == 100000
        assert result["primary_asset"] == "WTI"

    @pytest.mark.asyncio
    async def test_deterministic(self):
        """Same seed should give same results."""
        portfolio = {"capital": 50000, "positions": [], "cash": 10000}
        market_data = {
            "current": {"price": 100},
            "monte_carlo": {"n_sims": 500, "days": 10, "seed": 99},
        }

        r1 = await billing_agent(portfolio, market_data)
        r2 = await billing_agent(portfolio, market_data)
        assert r1["probability"]["mean"] == r2["probability"]["mean"]


# === Supervisor Subagent Tests ===
class TestSupervisorAgent:
    @pytest.mark.asyncio
    async def test_basic_flow(self):
        web_results = {
            "query": "oil market analysis",
            "news": [{"title": "Oil prices rise"}, {"title": "OPEC meeting"}],
        }
        support_results = {
            "warnings": {
                "level": "elevated",
                "risk_score": 3.0,
                "signals": [{"type": "elevated_vol", "severity": "medium"}],
            },
        }
        billing_results = {
            "probability": {
                "mean": 95.0, "initial_price": 100, "min": 70, "max": 130,
                "prob_below": 35.0, "percentiles": {},
            },
            "equity": {"current": 120000, "total_position": 100000},
            "margin_call": {"active": False, "shortfall": 0},
            "derived_volatility": 0.3,
        }

        result = await supervisor_agent(web_results, support_results, billing_results)

        assert "report" in result
        assert "JAGABOT GUARDIAN REPORT" in result["report"]
        assert "bayesian_analysis" in result
        assert "strategies" in result
        assert result["risk_level"] == "elevated"

    @pytest.mark.asyncio
    async def test_critical_report(self):
        web_results = {"query": "crash", "news": []}
        support_results = {
            "warnings": {
                "level": "critical",
                "risk_score": 8.0,
                "signals": [
                    {"type": "vol_spike", "severity": "high"},
                    {"type": "drawdown", "severity": "high"},
                    {"type": "correlation", "severity": "critical"},
                ],
            },
        }
        billing_results = {
            "probability": {"mean": 80, "initial_price": 100, "prob_below": 70.0},
            "equity": {"current": 50000},
            "margin_call": {"active": True, "shortfall": 15000},
            "derived_volatility": 0.6,
        }

        result = await supervisor_agent(web_results, support_results, billing_results)
        assert "ACTIVE" in result["report"]
        assert result["margin_call_active"] is True


# === Orchestrator Tests ===
class TestJagabot:
    def test_init(self, tmp_path):
        jaga = Jagabot(workspace=tmp_path)
        assert len(jaga.tools) == 32
        assert "financial_cv" in jaga.tools
        assert "monte_carlo" in jaga.tools
        assert "dynamics_oracle" in jaga.tools

    def test_registered_tools(self, tmp_path):
        jaga = Jagabot(workspace=tmp_path)
        tools = jaga.get_registered_tools()
        expected = [
            "financial_cv", "monte_carlo", "dynamics_oracle", "statistical_engine",
            "early_warning", "bayesian_reasoner", "counterfactual_sim",
            "sensitivity_analyzer", "pareto_optimizer",
        ]
        for name in expected:
            assert name in tools

    @pytest.mark.asyncio
    async def test_full_pipeline(self, tmp_path):
        """Full pipeline test with mocked web search."""
        jaga = Jagabot(workspace=tmp_path)

        mock_web_result = {
            "query": "oil prices WTI",
            "news": [{"title": "Oil rises", "url": "http://ex.com"}],
            "raw_results": "Results for: oil prices WTI\n1. Oil rises\n   http://ex.com",
            "result_count": 1,
            "timestamp": "2026-03-07T04:00:00",
        }

        with patch("jagabot.guardian.subagents.websearch.websearch_agent",
                    new_callable=AsyncMock, return_value=mock_web_result):
            from jagabot.guardian.subagents import websearch as ws_mod
            original = ws_mod.websearch_agent
            ws_mod.websearch_agent = AsyncMock(return_value=mock_web_result)

            # Patch the import in core.py
            with patch("jagabot.guardian.core.websearch_agent",
                        new_callable=AsyncMock, return_value=mock_web_result):

                result = await jaga.handle_query(
                    user_query="oil prices WTI analysis",
                    portfolio={
                        "capital": 100000,
                        "positions": [
                            {"symbol": "WTI", "quantity": 500, "current_price": 70.0, "entry_price": 65.0},
                        ],
                        "cash": 20000,
                        "maintenance_rate": 0.25,
                    },
                    market_data={
                        "historical_changes": {
                            "WTI": [0.7, 2.4, 4.2, 6.7, 8.3, 7.4, 5.1, 3.2],
                        },
                        "current": {
                            "WTI": 70.0,
                            "volatility": 0.35,
                            "drawdown": 0.08,
                        },
                        "monte_carlo": {"threshold": 60.0, "n_sims": 500, "days": 30, "seed": 42},
                    },
                )

            ws_mod.websearch_agent = original

        assert "report" in result
        assert "JAGABOT GUARDIAN REPORT" in result["report"]
        assert "session_id" in result
        assert result["web"] == mock_web_result
        assert "support" in result
        assert "billing" in result
        assert "supervisor" in result

        # Verify memory was stored
        history = (tmp_path / "memory" / "HISTORY.md").read_text()
        assert "analysis_" in history

    @pytest.mark.asyncio
    async def test_memory_persistence(self, tmp_path):
        """Verify results are stored in memory files."""
        jaga = Jagabot(workspace=tmp_path)

        mock_web = {
            "query": "test", "news": [], "raw_results": "", "result_count": 0,
            "timestamp": "2026-01-01",
        }

        with patch("jagabot.guardian.core.websearch_agent",
                    new_callable=AsyncMock, return_value=mock_web):
            await jaga.handle_query(
                user_query="test query",
                portfolio={"capital": 10000, "positions": [], "cash": 0},
                market_data={"current": {}, "historical_changes": {}},
            )

        assert (tmp_path / "memory" / "HISTORY.md").exists()
        assert (tmp_path / "memory" / "MEMORY.md").exists()
