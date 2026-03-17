"""Tests for v3.2.1 — Tool Calibration (Monte Carlo, VaR, Stress Test).

Validates all 3 fixes against Colab ground truth values.
"""

import json
import math
import pytest
import numpy as np

from jagabot.agent.tools.monte_carlo import standard_monte_carlo, MonteCarloTool
from jagabot.agent.tools.var import parametric_var, VaRTool
from jagabot.agent.tools.stress_test import position_stress, StressTestTool
from jagabot.agent.tools.cvar import calculate_cvar


# ── Monte Carlo Calibration ─────────────────────────────────────────────


class TestMonteCarloCalibration:
    def test_colab_ground_truth(self):
        """MC with Colab params: P(<$70) should be ~34.24%, not 40.26%."""
        r = standard_monte_carlo(
            current_price=76.50, target_price=70, vix=52,
            days=30, n_simulations=100_000, seed=42,
        )
        assert 33.0 < r["probability"] < 36.0, f"Got {r['probability']}, expected ~34.24"

    def test_default_mu_is_zero(self):
        """Default mu should be 0.0 (risk-neutral)."""
        import inspect
        sig = inspect.signature(standard_monte_carlo)
        assert sig.parameters["mu"].default == 0.0

    def test_risk_neutral_drift(self):
        """With mu=0, drift should be purely -0.5*sigma^2 (risk-neutral)."""
        r = standard_monte_carlo(
            current_price=100, target_price=100, vix=20,
            days=252, n_simulations=50_000, seed=42,
        )
        # Risk-neutral: mean should be close to initial (slight downward from vol drag)
        # With vol=20%, vol_drag = -0.5*0.04 = -2% annual → mean ≈ 98
        assert 95 < r["mean_price"] < 103

    def test_bearish_mu_increases_probability(self):
        """Negative mu should increase probability of falling below target."""
        r_neutral = standard_monte_carlo(
            current_price=76.50, target_price=70, vix=52,
            days=30, n_simulations=10_000, mu=0.0, seed=42,
        )
        r_bearish = standard_monte_carlo(
            current_price=76.50, target_price=70, vix=52,
            days=30, n_simulations=10_000, mu=-0.001, seed=42,
        )
        assert r_bearish["probability"] > r_neutral["probability"]

    def test_ci_contains_probability(self):
        """95% CI should bracket the probability estimate."""
        r = standard_monte_carlo(
            current_price=76.50, target_price=70, vix=52,
            days=30, n_simulations=100_000, seed=42,
        )
        assert r["ci_95"][0] < r["probability"] < r["ci_95"][1]

    def test_high_vix_high_probability(self):
        """VIX=80 should give higher probability of breach than VIX=20."""
        r_low = standard_monte_carlo(
            current_price=76.50, target_price=70, vix=20,
            days=30, n_simulations=10_000, seed=42,
        )
        r_high = standard_monte_carlo(
            current_price=76.50, target_price=70, vix=80,
            days=30, n_simulations=10_000, seed=42,
        )
        assert r_high["probability"] > r_low["probability"]

    def test_tool_uses_risk_neutral(self):
        """MonteCarloTool should produce risk-neutral results by default."""
        import asyncio
        tool = MonteCarloTool()
        raw = asyncio.run(tool.execute(
            current_price=76.50, target_price=70, vix=52,
            days=30, n_simulations=100_000, seed=42,
        ))
        data = json.loads(raw)
        assert 33.0 < data["probability"] < 36.0


# ── VaR Calibration ─────────────────────────────────────────────────────


class TestVaRCalibration:
    def test_default_holding_period_10(self):
        """Default holding period should be 10 days (Basel III)."""
        r = parametric_var(mean_return=-0.001, std_return=0.025)
        assert r["holding_period_days"] == 10

    def test_default_10_via_inspect(self):
        """Verify default via signature inspection."""
        import inspect
        sig = inspect.signature(parametric_var)
        assert sig.parameters["holding_period"].default == 10

    def test_10day_larger_than_1day(self):
        """10-day VaR should be larger than 1-day VaR."""
        r1 = parametric_var(mean_return=-0.001, std_return=0.025, holding_period=1)
        r10 = parametric_var(mean_return=-0.001, std_return=0.025, holding_period=10)
        assert r10["var_amount"] > r1["var_amount"]

    def test_colab_var_range(self):
        """VaR with Colab portfolio params should be in expected range."""
        daily_std = 0.52 / math.sqrt(252)  # VIX=52 → daily vol
        r = parametric_var(
            mean_return=0.0, std_return=daily_std,
            portfolio_value=1_630_786, holding_period=10, confidence=0.95,
        )
        # 10-day parametric VaR for this portfolio
        assert r["var_amount"] > 50_000
        assert r["var_amount"] < 500_000

    def test_tool_default_10day(self):
        """VaRTool should default to 10-day holding period."""
        import asyncio
        tool = VaRTool()
        raw = asyncio.run(tool.execute(
            method="parametric_var",
            params={"mean_return": -0.001, "std_return": 0.025},
        ))
        data = json.loads(raw)
        assert data["holding_period_days"] == 10


# ── Stress Test Position-Level Calibration ───────────────────────────────


class TestPositionStress:
    def test_colab_ground_truth(self):
        """Position stress with Colab params: equity should be ~$864,064."""
        r = position_stress(
            current_equity=1_109_092,
            current_price=76.50,
            stress_price=65,
            units=21_307,
        )
        assert abs(r["stress_equity"] - 864_061.5) < 1000, f"Got {r['stress_equity']}"

    def test_change_percent(self):
        """Change percent should be ~-22.09%."""
        r = position_stress(
            current_equity=1_109_092,
            current_price=76.50,
            stress_price=65,
            units=21_307,
        )
        assert abs(r["change_percent"] - (-22.09)) < 0.5

    def test_stress_loss_positive(self):
        """stress_loss should be absolute value (always positive)."""
        r = position_stress(
            current_equity=100_000,
            current_price=50,
            stress_price=40,
            units=1_000,
        )
        assert r["stress_loss"] == 10_000
        assert r["stress_equity"] == 90_000

    def test_stress_price_above_current(self):
        """If stress_price > current_price, equity should increase."""
        r = position_stress(
            current_equity=100_000,
            current_price=50,
            stress_price=60,
            units=1_000,
        )
        assert r["stress_equity"] == 110_000
        assert r["change_percent"] == 10.0

    def test_type_field(self):
        """Result should have type='position_stress'."""
        r = position_stress(
            current_equity=100_000,
            current_price=50,
            stress_price=40,
            units=100,
        )
        assert r["type"] == "position_stress"

    def test_tool_dispatch(self):
        """StressTestTool should dispatch position_stress."""
        import asyncio
        tool = StressTestTool()
        raw = asyncio.run(tool.execute(
            method="position_stress",
            params={
                "current_equity": 1_109_092,
                "current_price": 76.50,
                "stress_price": 65,
                "units": 21_307,
            },
        ))
        data = json.loads(raw)
        assert abs(data["stress_equity"] - 864_061.5) < 1000


# ── Integration: Tool Chain ──────────────────────────────────────────────


class TestToolChainIntegration:
    def test_mc_to_var_chain(self):
        """Monte Carlo prices → MC VaR should produce reasonable VaR."""
        from jagabot.agent.tools.var import monte_carlo_var
        mc = standard_monte_carlo(
            current_price=76.50, target_price=70, vix=52,
            days=30, n_simulations=10_000, seed=42,
        )
        var_r = monte_carlo_var(
            prices=mc["all_prices"],
            current_price=76.50,
            portfolio_value=1_630_786,
            confidence=0.95,
        )
        assert var_r["var_amount"] > 0
        assert var_r["method"] == "monte_carlo"

    def test_mc_to_cvar_chain(self):
        """Monte Carlo prices → CVaR should be >= VaR."""
        mc = standard_monte_carlo(
            current_price=76.50, target_price=70, vix=52,
            days=30, n_simulations=10_000, seed=42,
        )
        cvar_r = calculate_cvar(
            prices=mc["all_prices"],
            current_price=76.50,
            portfolio_value=1_630_786,
            confidence=0.95,
        )
        assert cvar_r["cvar_amount"] >= cvar_r["var_amount"]
