"""Tests for v3.2.2 — VaR Formula Correction & K3 Weight Calibration.

Validates bear/buffet confidence, K3 weights, portfolio_var, and full decision
chain against Colab ground truth.
"""

import json
import math
import asyncio
import tempfile
import pytest

from jagabot.agent.tools.decision import (
    bear_perspective, buffet_perspective, bull_perspective, collapse_perspectives,
)
from jagabot.agent.tools.var import parametric_var, portfolio_var, VaRTool


# ── Bear Perspective Calibration ─────────────────────────────────────────


class TestBearCalibration:
    def test_colab_ground_truth(self):
        """Bear with prob=33.85%, var_pct=14.4% → confidence ≈ 25%."""
        r = bear_perspective(
            probability_below_target=33.85,
            current_price=76.50, target_price=70,
            var_pct=14.4,
        )
        assert r["verdict"] == "HEDGE"
        assert 20 < r["confidence"] < 30, f"Got {r['confidence']}, expected ~25"

    def test_margin_call_escalates_to_sell(self):
        """With margin_call=True, bear should escalate to SELL."""
        r = bear_perspective(
            probability_below_target=33.85,
            current_price=76.50, target_price=70,
            var_pct=14.4, margin_call=True,
        )
        assert r["verdict"] == "SELL"
        assert 35 < r["confidence"] < 50

    def test_no_var_lower_confidence(self):
        """Without var_pct, bear confidence should be lower."""
        r_with = bear_perspective(
            probability_below_target=33.85,
            current_price=76.50, target_price=70,
            var_pct=14.4,
        )
        r_without = bear_perspective(
            probability_below_target=33.85,
            current_price=76.50, target_price=70,
        )
        assert r_without["confidence"] < r_with["confidence"]

    def test_high_risk_still_sell(self):
        """60%+ downside risk → SELL with high confidence."""
        r = bear_perspective(
            probability_below_target=65,
            current_price=76.50, target_price=70,
        )
        assert r["verdict"] == "SELL"
        assert r["confidence"] == 65.0

    def test_low_risk_hold(self):
        """<25% downside → HOLD with inverted confidence."""
        r = bear_perspective(
            probability_below_target=15,
            current_price=76.50, target_price=70,
        )
        assert r["verdict"] == "HOLD"
        assert r["confidence"] == 85.0


# ── Buffet Perspective Calibration ───────────────────────────────────────


class TestBuffetCalibration:
    def test_margin_call_100_confidence(self):
        """With margin_call=True, buffet confidence must be 100%."""
        r = buffet_perspective(
            probability_below_target=33.85,
            current_price=76.50, target_price=70,
            margin_call=True,
        )
        assert r["confidence"] == 100.0
        assert r["verdict"] == "SELL — Rule #1 Violated"

    def test_margin_call_rationale(self):
        """Margin call should produce Rule #1 rationale."""
        r = buffet_perspective(
            probability_below_target=33.85,
            current_price=76.50, target_price=70,
            margin_call=True,
        )
        assert any("MARGIN CALL" in s for s in r["rationale"])

    def test_no_margin_call_uses_composite(self):
        """Without margin_call, buffet uses composite scoring."""
        r = buffet_perspective(
            probability_below_target=33.85,
            current_price=76.50, target_price=70,
        )
        assert r["confidence"] != 100.0
        assert "composite_score" in r
        assert r["composite_score"] > 0


# ── K3 Weights ───────────────────────────────────────────────────────────


class TestK3Weights:
    def test_collapse_default_weights(self):
        """collapse_perspectives default weights should be 0.20/0.45/0.35."""
        bull = bull_perspective(33.85, 76.50, 70)
        bear = bear_perspective(33.85, 76.50, 70)
        buffet = buffet_perspective(33.85, 76.50, 70)
        r = collapse_perspectives(bull, bear, buffet)
        assert r["weights"]["bull"] == 0.20
        assert r["weights"]["bear"] == 0.45
        assert r["weights"]["buffet"] == 0.35

    def test_calibrated_collapse_with_margin_call(self):
        """K3 calibrated_collapse should pass margin_call through."""
        from jagabot.kernels.k3_perspective import K3MultiPerspective
        tmp = tempfile.mkdtemp()
        k3 = K3MultiPerspective(workspace=tmp)
        result = k3.calibrated_collapse({
            "probability_below_target": 33.85,
            "current_price": 76.50,
            "target_price": 70,
            "var_pct": 14.4,
            "margin_call": True,
        })
        assert "final_verdict" in result
        assert result["final_verdict"] == "SELL"


# ── Portfolio VaR ────────────────────────────────────────────────────────


class TestPortfolioVaR:
    def test_basic(self):
        """portfolio_var should sum position_value + cash."""
        r = portfolio_var(
            position_value=2_609_093, cash=300_000,
            annual_vol=0.52,
        )
        assert r["holding_period_days"] == 10
        assert r["position_value"] == 2_609_093
        assert r["cash"] == 300_000
        assert r["var_amount"] > 0

    def test_result_fields(self):
        """portfolio_var result should include extra fields."""
        r = portfolio_var(position_value=1_000_000, cash=100_000, annual_vol=0.30)
        assert "annual_vol" in r
        assert "position_value" in r
        assert "cash" in r

    def test_tool_dispatch(self):
        """VaRTool should dispatch portfolio_var."""
        tool = VaRTool()
        raw = asyncio.run(tool.execute(
            method="portfolio_var",
            params={"position_value": 1_000_000, "cash": 100_000, "annual_vol": 0.30},
        ))
        data = json.loads(raw)
        assert data["holding_period_days"] == 10
        assert data["var_amount"] > 0


# ── Full Decision Chain Integration ──────────────────────────────────────


class TestDecisionChain:
    def test_colab_full_chain_sell(self):
        """Full chain with margin_call should produce SELL."""
        bull = bull_perspective(
            probability_below_target=33.85,
            current_price=76.50, target_price=70,
        )
        bear = bear_perspective(
            probability_below_target=33.85,
            current_price=76.50, target_price=70,
            var_pct=14.4, margin_call=True,
        )
        buffet = buffet_perspective(
            probability_below_target=33.85,
            current_price=76.50, target_price=70,
            margin_call=True,
        )
        collapsed = collapse_perspectives(bull, bear, buffet)
        assert collapsed["final_verdict"] == "SELL"
        assert 55 < collapsed["confidence"] < 70

    def test_no_margin_call_not_sell(self):
        """Without margin_call, moderate risk should NOT produce SELL."""
        bull = bull_perspective(33.85, 76.50, 70)
        bear = bear_perspective(33.85, 76.50, 70, var_pct=14.4)
        buffet = buffet_perspective(33.85, 76.50, 70)
        collapsed = collapse_perspectives(bull, bear, buffet)
        assert collapsed["final_verdict"] != "SELL"
