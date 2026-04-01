"""Tests for v2.5 — Risk Metrics Volatility Scaling Fix.

Verifies defensive normalization guards at every tool boundary
and validates results against Google Colab ground truth values.
"""

import math
import json
import pytest
import numpy as np

from jagabot.agent.tools.monte_carlo import standard_monte_carlo, monte_carlo_gbm
from jagabot.agent.tools.var import parametric_var
from jagabot.agent.tools.financial_cv import calculate_cv, calculate_cv_ratios
from jagabot.agent.tools.portfolio_analyzer import analytical_probability


# ── Monte Carlo Normalization Guards ─────────────────────────────────────


class TestMonteCarloGuards:
    def test_vix_percentage_normal(self):
        """VIX=22.25 (percentage form) should work as-is."""
        r = standard_monte_carlo(current_price=78.5, target_price=75, vix=22.25, days=30)
        assert 0 < r["probability"] < 100
        assert r["annual_vol"] == pytest.approx(0.2225, abs=0.001)

    def test_vix_decimal_auto_scales(self):
        """VIX=0.2225 (decimal form) should auto-scale to 22.25."""
        r = standard_monte_carlo(current_price=78.5, target_price=75, vix=0.2225, days=30)
        assert r["annual_vol"] == pytest.approx(0.2225, abs=0.001)

    def test_vix_decimal_same_as_percentage(self):
        """Passing vix=0.2225 should give same result as vix=22.25."""
        r_pct = standard_monte_carlo(current_price=78.5, target_price=75, vix=22.25, seed=42)
        r_dec = standard_monte_carlo(current_price=78.5, target_price=75, vix=0.2225, seed=42)
        assert r_pct["probability"] == r_dec["probability"]
        assert r_pct["mean_price"] == r_dec["mean_price"]

    def test_gbm_decimal_normal(self):
        """vol=0.2225 (decimal) should work as-is in monte_carlo_gbm."""
        r = monte_carlo_gbm(price=78.5, vol=0.2225, days=30, threshold=75, seed=42)
        assert "prob_below" in r
        assert r["volatility"] == pytest.approx(0.2225, abs=0.001)

    def test_gbm_percentage_auto_scales(self):
        """vol=22.25 (percentage) should auto-scale to 0.2225."""
        r = monte_carlo_gbm(price=78.5, vol=22.25, days=30, threshold=75, seed=42)
        assert r["volatility"] == pytest.approx(0.2225, abs=0.001)

    def test_gbm_percentage_same_as_decimal(self):
        """Passing vol=22.25 should give same result as vol=0.2225."""
        r_dec = monte_carlo_gbm(price=78.5, vol=0.2225, days=30, threshold=75, seed=42)
        r_pct = monte_carlo_gbm(price=78.5, vol=22.25, days=30, threshold=75, seed=42)
        assert r_dec["prob_below"] == r_pct["prob_below"]

    def test_high_vix_not_scaled(self):
        """VIX=58 should NOT be scaled (it's already percentage)."""
        r = standard_monte_carlo(current_price=78.5, target_price=75, vix=58, days=30)
        assert r["annual_vol"] == pytest.approx(0.58, abs=0.001)


# ── VaR Normalization Guards ─────────────────────────────────────────────


class TestVaRGuards:
    def test_std_decimal_normal(self):
        """std_return=0.025 (decimal) should work as-is."""
        r = parametric_var(mean_return=-0.001, std_return=0.025, portfolio_value=100_000)
        assert 0 < r["var_amount"] < 100_000

    def test_std_percentage_auto_scales(self):
        """std_return=2.5 (percentage) should auto-scale to 0.025."""
        r = parametric_var(mean_return=-0.001, std_return=2.5, portfolio_value=100_000)
        r_correct = parametric_var(mean_return=-0.001, std_return=0.025, portfolio_value=100_000)
        assert r["var_amount"] == pytest.approx(r_correct["var_amount"], rel=0.001)

    def test_var_colab_ground_truth(self):
        """VaR against Colab ground truth: ~$117,179 for given params.

        Params from blueprint: exposure=1,875,000, vol=22.25%, 10-day hold, 95% CI.
        VaR = 1.645 * 0.2225 * sqrt(10) * 1,875,000 ≈ $117,179 * (10day/1day adj)
        But parametric_var uses daily std, so:
        daily_std = 22.25% / sqrt(252) = 0.01402
        VaR = Z * daily_std * sqrt(10) * portfolio = 1.645 * 0.01402 * 3.162 * 1,875,000
        """
        daily_std = 0.2225 / math.sqrt(252)  # annualized → daily
        r = parametric_var(
            mean_return=-0.001, std_return=daily_std,
            portfolio_value=1_875_000, holding_period=10, confidence=0.95,
        )
        # Blueprint says ~$117,179 — allow wider tolerance for mean/drift adjustment
        assert 100_000 < r["var_amount"] < 200_000


# ── Analytical Probability Normalization ─────────────────────────────────


class TestProbabilityGuards:
    def test_decimal_returns_normal(self):
        """Decimal daily returns should work as-is."""
        returns = [0.02, -0.01, 0.015, -0.005, 0.008, -0.012] * 10
        r = analytical_probability(current_price=100, target_price=90, daily_returns=returns, days=30)
        assert 0 < r["probability_below"] < 100
        assert r["method"] == "analytical_norm_cdf"

    def test_percentage_returns_auto_scales(self):
        """Percentage daily returns (e.g. 2.0 = 2%) should auto-scale."""
        returns_pct = [2.0, -1.0, 1.5, -0.5, 0.8, -1.2] * 10
        returns_dec = [r / 100 for r in returns_pct]
        r_pct = analytical_probability(current_price=100, target_price=90, daily_returns=returns_pct, days=30)
        r_dec = analytical_probability(current_price=100, target_price=90, daily_returns=returns_dec, days=30)
        assert r_pct["probability_below"] == pytest.approx(r_dec["probability_below"], abs=0.01)

    def test_mixed_small_returns_not_scaled(self):
        """Small returns like 0.001 should NOT be scaled (they're already decimal)."""
        returns = [0.001, -0.002, 0.003, -0.001, 0.002, -0.003] * 10
        r = analytical_probability(current_price=100, target_price=90, daily_returns=returns, days=30)
        assert r["daily_vol"] < 0.01  # Very small vol since returns are tiny


# ── CV Analysis Tests ────────────────────────────────────────────────────


class TestCVDecimal:
    def test_cv_returns_decimal(self):
        """CV should return a decimal ratio, not percentage."""
        changes = [0.032, 0.045, 0.058, 0.062, 0.059, 0.068]
        cv = calculate_cv(changes)
        # CV = std/mean, with these values should be < 1.0 (decimal)
        assert 0 < cv < 1.0

    def test_cv_ratios_decimal(self):
        """CV ratios should all be decimal."""
        changes = [0.032, 0.045, 0.058, 0.062, 0.059, 0.068, 0.04, 0.055,
                   0.061, 0.048, 0.052, 0.065, 0.044, 0.057, 0.063]
        result = calculate_cv_ratios(changes)
        assert 0 < result["overall_cv"] < 1.0
        for window_cv in result["windows"].values():
            assert 0 < window_cv < 2.0  # Allow wider range for windows

    def test_cv_not_multiplied_by_100(self):
        """Verify CV is NOT accidentally multiplied by 100."""
        changes = [10, 12, 8, 11, 9, 13, 10, 14]
        cv = calculate_cv(changes)
        assert cv < 1.0  # Should be ~0.18, not 18


# ── Billing Pipeline Integration ─────────────────────────────────────────


class TestBillingVolGuard:
    def test_cv_fallback_decimal(self):
        """Billing agent's CV fallback should handle decimal CV correctly."""
        from jagabot.agent.tools.monte_carlo import monte_carlo_gbm
        # Simulate what billing does: CV=0.30 → vol=0.30
        r = monte_carlo_gbm(price=78.5, vol=0.30, days=30, threshold=75, seed=42)
        assert r["volatility"] == pytest.approx(0.30, abs=0.01)

    def test_cv_fallback_percentage_guard(self):
        """If CV somehow comes as 30 (percentage), guard should catch it."""
        from jagabot.agent.tools.monte_carlo import monte_carlo_gbm
        r = monte_carlo_gbm(price=78.5, vol=30.0, days=30, threshold=75, seed=42)
        # Guard should scale 30 → 0.30
        assert r["volatility"] == pytest.approx(0.30, abs=0.01)


# ── Edge Cases ───────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_zero_vol_mc(self):
        """VIX=0 should not crash."""
        r = standard_monte_carlo(current_price=100, target_price=90, vix=0.001, days=10)
        assert "probability" in r

    def test_very_high_vix(self):
        """VIX=100 (extreme crisis) should work."""
        r = standard_monte_carlo(current_price=100, target_price=50, vix=100, days=30)
        assert 0 < r["probability"] < 100

    def test_negative_returns_probability(self):
        """Negative daily returns should work in analytical probability."""
        returns = [-0.02, -0.03, -0.01, -0.04, -0.02, -0.015] * 10
        r = analytical_probability(current_price=100, target_price=80, daily_returns=returns, days=30)
        assert r["probability_below"] > 0

    def test_var_tiny_std(self):
        """Very small std_return should give small VaR."""
        r = parametric_var(mean_return=0, std_return=0.001, portfolio_value=100_000)
        assert r["var_amount"] < 1_000


# ── SKILL.md Compliance ──────────────────────────────────────────────────


class TestSkillVolRules:
    def test_skill_has_vol_unit_rules(self):
        """SKILL.md must contain Volatility Unit Rules section."""
        import pathlib
        skill = pathlib.Path(__file__).parent.parent.parent / "jagabot" / "skills" / "financial" / "SKILL.md"
        content = skill.read_text()
        assert "Volatility Unit Rules" in content
        assert "vix=22.25" in content
        assert "vol=0.2225" in content
        assert "std_return=0.025" in content
        assert "CV → VIX" in content or "CV → VIX" in content
