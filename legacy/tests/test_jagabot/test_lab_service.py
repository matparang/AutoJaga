"""Tests for JAGABOT v3.4 — LabService centralized tool execution.

Tests cover: LabService core, parameter validation, logging,
BaseSubagent integration, and parallel execution.
"""

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from jagabot.lab.service import LabService
from jagabot.subagents.base import BaseSubagent


# ---------------------------------------------------------------------------
# LabService — Core Execution
# ---------------------------------------------------------------------------

class TestLabServiceExecution:
    """LabService.execute() for various tools."""

    @pytest.fixture(autouse=True)
    def _lab(self, tmp_path):
        self.lab = LabService(log_dir=tmp_path)
        self.log_dir = tmp_path

    @pytest.mark.asyncio
    async def test_monte_carlo_execution(self):
        r = await self.lab.execute("monte_carlo", {
            "current_price": 76.50,
            "target_price": 70,
            "vix": 52,
            "days": 30,
        })
        assert r["success"] is True
        assert r["tool"] == "monte_carlo"
        assert "output" in r
        assert isinstance(r["output"], dict)
        prob = r["output"].get("probability", 0)
        assert 30.0 < prob < 38.0, f"Probability {prob} outside expected range"

    @pytest.mark.asyncio
    async def test_var_execution(self):
        r = await self.lab.execute("var", {
            "method": "parametric_var",
            "params": {
                "portfolio_value": 1_000_000,
                "annual_vol": 0.82,
                "holding_period": 10,
                "confidence": 0.95,
            },
        })
        assert r["success"] is True
        assert r["tool"] == "var"
        assert isinstance(r["output"], dict)

    @pytest.mark.asyncio
    async def test_stress_test_execution(self):
        r = await self.lab.execute("stress_test", {
            "method": "position_stress",
            "params": {
                "current_equity": 1_109_092,
                "current_price": 76.50,
                "stress_price": 65,
                "units": 21_307,
            },
        })
        assert r["success"] is True
        stress_eq = r["output"].get("stress_equity", 0)
        assert 860_000 < stress_eq < 870_000

    @pytest.mark.asyncio
    async def test_execution_has_id_and_time(self):
        r = await self.lab.execute("monte_carlo", {
            "current_price": 100, "target_price": 90, "vix": 30,
        })
        assert "execution_id" in r
        assert r["execution_id"].startswith("monte_carlo_")
        assert "execution_time" in r
        assert r["execution_time"] >= 0

    @pytest.mark.asyncio
    async def test_sandbox_flag_recorded(self):
        r = await self.lab.execute("monte_carlo", {
            "current_price": 100, "target_price": 90, "vix": 30,
        })
        assert r["sandbox_used"] is False


# ---------------------------------------------------------------------------
# LabService — Validation
# ---------------------------------------------------------------------------

class TestLabServiceValidation:
    """Parameter validation via LabService."""

    @pytest.fixture(autouse=True)
    def _lab(self, tmp_path):
        self.lab = LabService(log_dir=tmp_path)

    def test_validate_valid_params(self):
        v = self.lab.validate_params("monte_carlo", {
            "current_price": 76.50, "target_price": 70, "vix": 52,
        })
        assert v["valid"] is True

    def test_validate_missing_required(self):
        v = self.lab.validate_params("monte_carlo", {"current_price": 76.50})
        assert v["valid"] is False
        assert len(v["errors"]) > 0

    def test_validate_unknown_tool(self):
        v = self.lab.validate_params("nonexistent_tool", {})
        assert v["valid"] is False

    @pytest.mark.asyncio
    async def test_execute_unknown_tool_fails(self):
        r = await self.lab.execute("nonexistent_tool", {})
        assert r["success"] is False
        assert "Unknown tool" in str(r.get("error", ""))

    @pytest.mark.asyncio
    async def test_execute_bad_params_fails(self):
        r = await self.lab.execute("monte_carlo", {"bad_param": "xyz"})
        assert r["success"] is False


# ---------------------------------------------------------------------------
# LabService — Logging
# ---------------------------------------------------------------------------

class TestLabServiceLogging:
    """Execution logging to lab_logs directory."""

    @pytest.fixture(autouse=True)
    def _lab(self, tmp_path):
        self.lab = LabService(log_dir=tmp_path)
        self.log_dir = tmp_path

    @pytest.mark.asyncio
    async def test_log_file_created(self):
        r = await self.lab.execute("monte_carlo", {
            "current_price": 100, "target_price": 90, "vix": 30,
        })
        log_files = list(self.log_dir.glob("*.json"))
        assert len(log_files) >= 1

    @pytest.mark.asyncio
    async def test_log_contains_metadata(self):
        r = await self.lab.execute("monte_carlo", {
            "current_price": 100, "target_price": 90, "vix": 30,
        })
        log_files = list(self.log_dir.glob("*.json"))
        log = json.loads(log_files[0].read_text())
        assert log["tool"] == "monte_carlo"
        assert log["success"] is True
        assert "timestamp" in log
        assert "execution_id" in log

    @pytest.mark.asyncio
    async def test_failed_execution_logged(self):
        r = await self.lab.execute("nonexistent", {})
        log_files = list(self.log_dir.glob("*.json"))
        assert len(log_files) >= 1
        log = json.loads(log_files[0].read_text())
        assert log["success"] is False


# ---------------------------------------------------------------------------
# LabService — Parallel Execution
# ---------------------------------------------------------------------------

class TestLabServiceParallel:
    """Parallel tool execution."""

    @pytest.fixture(autouse=True)
    def _lab(self, tmp_path):
        self.lab = LabService(log_dir=tmp_path)

    @pytest.mark.asyncio
    async def test_parallel_execution(self):
        tasks = [
            {"tool": "monte_carlo", "params": {
                "current_price": 76.50, "target_price": 70, "vix": 52,
            }},
            {"tool": "monte_carlo", "params": {
                "current_price": 100, "target_price": 80, "vix": 30,
            }},
        ]
        results = await self.lab.execute_parallel(tasks)
        assert len(results) == 2
        assert all(r["success"] for r in results)

    @pytest.mark.asyncio
    async def test_parallel_mixed_success(self):
        tasks = [
            {"tool": "monte_carlo", "params": {
                "current_price": 100, "target_price": 90, "vix": 30,
            }},
            {"tool": "nonexistent", "params": {}},
        ]
        results = await self.lab.execute_parallel(tasks)
        assert len(results) == 2
        assert results[0]["success"] is True
        assert results[1]["success"] is False


# ---------------------------------------------------------------------------
# LabService — Tool listing
# ---------------------------------------------------------------------------

class TestLabServiceListing:
    """Tool listing convenience methods."""

    @pytest.fixture(autouse=True)
    def _lab(self, tmp_path):
        self.lab = LabService(log_dir=tmp_path)

    def test_list_tools(self):
        tools = self.lab.list_tools()
        assert "monte_carlo" in tools
        assert "var" in tools
        assert len(tools) == 32

    def test_tool_count(self):
        assert self.lab.tool_count() == 32


# ---------------------------------------------------------------------------
# BaseSubagent
# ---------------------------------------------------------------------------

class TestBaseSubagent:
    """BaseSubagent with LabService integration."""

    @pytest.fixture(autouse=True)
    def _agent(self, tmp_path):
        self.agent = BaseSubagent(lab=LabService(log_dir=tmp_path))

    @pytest.mark.asyncio
    async def test_execute_tool(self):
        r = await self.agent.execute_tool("monte_carlo", {
            "current_price": 76.50, "target_price": 70, "vix": 52,
        })
        assert r["success"] is True
        assert "output" in r

    @pytest.mark.asyncio
    async def test_execute_tool_failure(self):
        r = await self.agent.execute_tool("nonexistent", {})
        assert r["success"] is False

    @pytest.mark.asyncio
    async def test_parallel_tools(self):
        results = await self.agent.execute_tools_parallel([
            {"tool": "monte_carlo", "params": {
                "current_price": 100, "target_price": 90, "vix": 30,
            }},
        ])
        assert len(results) == 1
        assert results[0]["success"] is True
