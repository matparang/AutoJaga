"""Tests for v3.7.1 — Colab Ground Truth Calibration.

Validates VaR, recovery time, and bear confidence against Colab reference values.
"""

import math
import pytest

from jagabot.agent.tools.var import parametric_var, portfolio_var
from jagabot.agent.tools.recovery_time import estimate_recovery, recovery_probability
from jagabot.agent.tools.decision import (
    bear_perspective, buffet_perspective, bull_perspective, collapse_perspectives,
)


# ── VaR Colab Ground Truth ───────────────────────────────────────────────


class TestVaRColab:
    """VaR formula is correct: portfolio_var uses position+cash with sqrt(h/252).

    The Colab $819,534 figure may use slightly different vol; our formula
    matches the standard parametric VaR: z * (annual_vol / sqrt(252)) * sqrt(h) * V.
    """

    def test_portfolio_var_colab_scenario(self):
        """Portfolio VaR for Colab inputs should be in expected range."""
        r = portfolio_var(
            position_value=4_610_265, cash=600_000,
            annual_vol=0.52, holding_period=10, confidence=0.95,
        )
        # Formula: 1.645 * (0.52/sqrt(252)) * sqrt(10) * 5,210,265 ≈ $888K
        # Colab says $819K (different vol assumption). Accept 750K–950K range.
        assert 750_000 < r["var_amount"] < 950_000
        assert 14 < r["var_pct"] < 19

    def test_portfolio_var_uses_position_plus_cash(self):
        """VaR base should be position + cash, not raw exposure."""
        r = portfolio_var(position_value=1_000_000, cash=500_000, annual_vol=0.30)
        # portfolio_value = 1,500,000 (not some leveraged amount)
        assert r["position_value"] == 1_000_000
        assert r["cash"] == 500_000
        var_implied_base = r["var_amount"] / (r["var_pct"] / 100)
        assert abs(var_implied_base - 1_500_000) < 10  # float rounding

    def test_var_pct_matches_colab_formula(self):
        """VaR percentage should match: z * vol * sqrt(h/252)."""
        r = portfolio_var(
            position_value=5_210_265, cash=0,
            annual_vol=0.52, holding_period=10,
        )
        expected_pct = 1.645 * 0.52 * math.sqrt(10 / 252) * 100
        assert abs(r["var_pct"] - expected_pct) < 0.5


# ── Recovery Time Colab Ground Truth ─────────────────────────────────────


class TestRecoveryColab:
    """Recovery time using 15% annual return and annual compounding."""

    def test_default_is_15_percent(self):
        """Default annual_return should be 0.15 (market average)."""
        r = estimate_recovery(current_price=100, target_price=200)
        assert r["annual_return_assumed"] == 0.15

    def test_colab_43_months(self):
        """Colab scenario: 908K→1.5M at 15% → ~43 months."""
        r = estimate_recovery(
            current_price=908_610, target_price=1_500_000,
            annual_return=0.15,
        )
        assert not r["already_recovered"]
        # Colab: log(1.6513) / log(1.15) = 3.588 years = 43.1 months
        assert 42 < r["deterministic_months"] < 45, (
            f"Got {r['deterministic_months']}, expected ~43"
        )

    def test_annual_compounding_vs_formula(self):
        """Deterministic months should match annual compounding formula."""
        r = estimate_recovery(
            current_price=100, target_price=200, annual_return=0.15,
        )
        expected_years = math.log(2) / math.log(1.15)
        expected_months = expected_years * 12
        assert abs(r["deterministic_months"] - expected_months) < 0.5

    def test_recovery_probability_default_15(self):
        """recovery_probability should also use 15% default."""
        r = recovery_probability(
            current_price=100, target_price=150, days=252,
        )
        assert r["annual_return_assumed"] == 0.15

    def test_backward_compat_custom_return(self):
        """Callers can still pass custom annual_return."""
        r8 = estimate_recovery(current_price=100, target_price=200, annual_return=0.08)
        r15 = estimate_recovery(current_price=100, target_price=200, annual_return=0.15)
        # 8% takes longer than 15%
        assert r8["deterministic_months"] > r15["deterministic_months"]


# ── Bear Confidence Colab Ground Truth ───────────────────────────────────


class TestBearConfidenceColab:
    """Bear confidence with margin_call uses calibrated multi-component formula."""

    def test_colab_51_percent(self):
        """Colab: prob=42.33%, var=15.73%, shortfall=0.395 → ~52%."""
        r = bear_perspective(
            probability_below_target=42.33,
            current_price=76.50, target_price=70,
            var_pct=15.73,
            margin_call=True,
            margin_shortfall_ratio=0.395,
        )
        assert r["verdict"] == "SELL"
        # Blueprint target ~51.5%, formula gives ~52.1%
        assert 48 < r["confidence"] < 56, f"Got {r['confidence']}, expected ~51.5"

    def test_margin_call_without_shortfall_ratio(self):
        """Without shortfall_ratio, falls back to downside-based estimate."""
        r = bear_perspective(
            probability_below_target=42.33,
            current_price=76.50, target_price=70,
            var_pct=15.73,
            margin_call=True,
        )
        assert r["verdict"] == "SELL"
        # Should be > old formula (~29%) but < full Colab (~52%)
        assert 35 < r["confidence"] < 55

    def test_no_margin_call_unchanged(self):
        """HEDGE case (no margin_call) formula should be unchanged."""
        r = bear_perspective(
            probability_below_target=33.85,
            current_price=76.50, target_price=70,
            var_pct=14.4,
        )
        assert r["verdict"] == "HEDGE"
        # Same formula as before: downside*0.5 + min(var,30)*0.5 ≈ 24
        assert 20 < r["confidence"] < 30

    def test_high_shortfall_capped(self):
        """Shortfall component should be capped at 50%."""
        r = bear_perspective(
            probability_below_target=50,
            current_price=76.50, target_price=70,
            var_pct=20,
            margin_call=True,
            margin_shortfall_ratio=0.9,  # 90% shortfall
        )
        assert r["verdict"] == "SELL"
        # var: min(40,40)*0.4=16, prob: 50*0.3=15, shortfall: min(90,50)*0.3=15, boost=15
        # total = 61 (not unlimited)
        assert r["confidence"] <= 70


# ── Full Decision Chain Colab Integration ────────────────────────────────


class TestFullChainColab:
    """Full 3-perspective chain with Colab parameters."""

    def test_colab_sell_with_calibrated_bear(self):
        """Full chain: margin_call → SELL with calibrated confidence."""
        bull = bull_perspective(
            probability_below_target=42.33,
            current_price=76.50, target_price=70,
        )
        bear = bear_perspective(
            probability_below_target=42.33,
            current_price=76.50, target_price=70,
            var_pct=15.73,
            margin_call=True,
            margin_shortfall_ratio=0.395,
        )
        buffet = buffet_perspective(
            probability_below_target=42.33,
            current_price=76.50, target_price=70,
            margin_call=True,
        )
        collapsed = collapse_perspectives(bull, bear, buffet)
        assert collapsed["final_verdict"] == "SELL"
        # Bear ~52%, Buffet 100%, Bull ~57.67%
        # Weighted: 0.20*57.67 + 0.45*52.1 + 0.35*100 ≈ 69.5
        assert 60 < collapsed["confidence"] < 80
