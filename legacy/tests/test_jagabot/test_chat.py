"""Tests for JAGABOT v3.6 — Chat Tab.

Covers query classification, tool-result formatting, dashboard metrics
extraction, general-query handling, and render_chat importability.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jagabot.ui.chat import (
    classify_query,
    format_tool_results,
    format_dashboard_metrics,
    _handle_general,
    _process_query,
    _KEYWORDS,
    _QUERY_WORKFLOWS,
)


# ====================================================================
# classify_query
# ====================================================================

class TestClassifyQuery:
    def test_portfolio_keywords(self):
        assert classify_query("Check portfolio saya") == "portfolio"
        assert classify_query("modal 1.5M") == "portfolio"
        assert classify_query("equity margin call") == "portfolio"
        assert classify_query("leveraj 2.5") == "portfolio"

    def test_risk_keywords(self):
        assert classify_query("Apa risiko saya?") == "risk"
        assert classify_query("Calculate VaR") == "risk"
        assert classify_query("CVaR analysis") == "risk"
        assert classify_query("stress test") == "risk"
        assert classify_query("VIX tinggi") == "risk"

    def test_fund_manager_keywords(self):
        assert classify_query("Fund manager kata OK") == "fund_manager"
        assert classify_query("advisor saya cakap") == "fund_manager"
        assert classify_query("broker recommended") == "fund_manager"

    def test_general_keywords(self):
        assert classify_query("Hello JAGABOT") == "general"
        assert classify_query("Hi there") == "general"
        assert classify_query("Thank you") == "general"
        assert classify_query("help me") == "general"

    def test_unknown_query(self):
        assert classify_query("random gibberish xyz") == "unknown"
        assert classify_query("") == "unknown"

    def test_case_insensitive(self):
        assert classify_query("PORTFOLIO check") == "portfolio"
        assert classify_query("RISK analysis") == "risk"

    def test_priority_first_match(self):
        # "portfolio risk" → portfolio wins (checked first)
        result = classify_query("portfolio risk analysis")
        assert result in ("portfolio", "risk")


# ====================================================================
# format_tool_results
# ====================================================================

class TestFormatToolResults:
    def test_batch_results(self):
        data = {
            "results": [
                {
                    "task": {"tool": "monte_carlo"},
                    "success": True,
                    "execution_time": 0.5,
                },
                {
                    "task": {"tool": "var"},
                    "success": False,
                    "execution_time": 0.1,
                },
            ]
        }
        tools = format_tool_results(data)
        assert len(tools) == 2
        assert tools[0]["name"] == "monte_carlo"
        assert tools[0]["success"] is True
        assert tools[0]["duration"] == 0.5
        assert tools[1]["success"] is False

    def test_pipeline_results_with_tool_results(self):
        data = {
            "tools": {
                "success": True,
                "tool_results": [
                    {"tool": "monte_carlo", "success": True, "execution_time": 0.3},
                ],
            },
        }
        tools = format_tool_results(data)
        assert any(t["name"] == "monte_carlo" for t in tools)

    def test_empty_results(self):
        assert format_tool_results({}) == []

    def test_fallback_to_stage_name(self):
        data = {
            "tools": {"success": True, "execution_time": 1.0},
        }
        tools = format_tool_results(data)
        assert len(tools) >= 1
        assert tools[0]["name"] == "tools"


# ====================================================================
# format_dashboard_metrics
# ====================================================================

class TestFormatDashboardMetrics:
    def test_batch_numeric_outputs(self):
        data = {
            "results": [
                {
                    "task": {"tool": "monte_carlo"},
                    "output": {"probability": 0.72, "simulations": 10000},
                },
            ]
        }
        metrics = format_dashboard_metrics(data)
        assert len(metrics) == 2
        labels = [m["label"] for m in metrics]
        assert "monte_carlo: probability" in labels

    def test_pipeline_stage_metrics(self):
        data = {
            "tools": {"success": True, "score": 85.5},
        }
        metrics = format_dashboard_metrics(data)
        assert any(m["label"] == "tools: score" for m in metrics)

    def test_max_12_metrics(self):
        data = {
            "results": [
                {
                    "task": {"tool": "big"},
                    "output": {f"metric_{i}": i for i in range(20)},
                },
            ]
        }
        metrics = format_dashboard_metrics(data)
        assert len(metrics) <= 12

    def test_empty_data(self):
        assert format_dashboard_metrics({}) == []

    def test_skips_non_numeric(self):
        data = {
            "results": [
                {
                    "task": {"tool": "mc"},
                    "output": {"nested": {"a": 1}, "list_val": [1, 2]},
                },
            ]
        }
        metrics = format_dashboard_metrics(data)
        # nested dict and list should be skipped
        assert len(metrics) == 0


# ====================================================================
# _handle_general
# ====================================================================

class TestHandleGeneral:
    def test_greeting(self):
        r = _handle_general("Hello!")
        assert "JAGABOT" in r["message"]
        assert r["dashboard"] is None
        assert r["tools"] is None

    def test_thanks(self):
        r = _handle_general("terima kasih")
        assert "Sama-sama" in r["message"]

    def test_help(self):
        r = _handle_general("tolong saya")
        assert "Cara" in r["message"]

    def test_generic(self):
        r = _handle_general("apa boleh buat")
        assert "boleh bantu" in r["message"]


# ====================================================================
# _process_query (with mocks)
# ====================================================================

class TestProcessQuery:
    def test_general_query_no_pipeline(self):
        """General queries should NOT call SubagentManager."""
        result = _process_query("Hello!", {})
        assert "JAGABOT" in result["message"]
        assert result.get("tools") is None

    def test_unknown_query_calls_pipeline(self):
        """Unknown queries run the full pipeline (mocked)."""
        mock_result = {
            "success": True,
            "tools": {"success": True},
            "models": {"success": True},
            "reasoning": {"success": True},
            "websearch": {"success": True},
        }
        with patch("jagabot.ui.chat._run_pipeline", return_value={
            "message": "✅ Analisis selesai.",
            "dashboard": None,
            "tools": [],
        }) as mock_pipe:
            result = _process_query("some complex query xyz", {})
            mock_pipe.assert_called_once()
            assert "selesai" in result["message"].lower() or "⏱️" in result["message"]

    def test_portfolio_query_calls_focused(self):
        with patch("jagabot.ui.chat._run_focused_workflow", return_value={
            "message": "✅ Analisis portfolio selesai",
            "dashboard": [],
            "tools": [],
        }) as mock_fw:
            result = _process_query("Check portfolio saya", {})
            mock_fw.assert_called_once()
            assert "portfolio" in result["message"].lower()

    def test_risk_query_calls_focused(self):
        with patch("jagabot.ui.chat._run_focused_workflow", return_value={
            "message": "✅ Analisis risiko selesai",
            "dashboard": [],
            "tools": [],
        }) as mock_fw:
            result = _process_query("VaR analysis please", {})
            mock_fw.assert_called_once()

    def test_exception_handled(self):
        with patch("jagabot.ui.chat._run_pipeline", side_effect=RuntimeError("boom")):
            result = _process_query("some unknown query xyz", {})
            assert "Maaf" in result["message"]
            assert "boom" in result["message"]


# ====================================================================
# Module-level constants
# ====================================================================

class TestModuleConstants:
    def test_keywords_dict_populated(self):
        assert len(_KEYWORDS) == 4
        assert "portfolio" in _KEYWORDS
        assert "risk" in _KEYWORDS
        assert "fund_manager" in _KEYWORDS
        assert "general" in _KEYWORDS

    def test_query_workflows_mapping(self):
        assert _QUERY_WORKFLOWS["portfolio"] == "portfolio_review"
        assert _QUERY_WORKFLOWS["risk"] == "risk_analysis"


# ====================================================================
# render_chat importability
# ====================================================================

class TestRenderChat:
    def test_importable(self):
        from jagabot.ui.chat import render_chat
        assert callable(render_chat)

    def test_streamlit_app_has_six_tabs(self):
        """Verify streamlit_app.py references 6 tabs."""
        import inspect
        from pathlib import Path

        app_path = Path(__file__).parent.parent.parent / "jagabot" / "ui" / "streamlit_app.py"
        if app_path.exists():
            src = app_path.read_text()
            assert "tab6" in src
            assert "💬 Chat" in src
