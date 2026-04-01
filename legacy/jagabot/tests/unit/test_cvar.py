#!/usr/bin/env python3
"""
Unit tests for CVaR (Conditional Value at Risk) tool.
Tests both calculate_cvar and compare_var_cvar functions.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

import pytest
import numpy as np
from jagabot.agent.tools.cvar import calculate_cvar, compare_var_cvar


class TestCalculateCVaR:
    """Test calculate_cvar function"""
    
    def test_basic_cvar_calculation(self):
        """Test basic CVaR calculation with simulated prices"""
        # Simulated prices from monte_carlo (normal distribution around 150)
        prices = [145.2, 148.5, 152.3, 147.8, 149.6, 151.2, 146.7, 153.1, 150.5, 148.9]
        current_price = 150.0
        portfolio_value = 100000
        
        result = calculate_cvar(
            prices=prices,
            current_price=current_price,
            confidence=0.95,
            portfolio_value=portfolio_value
        )
        
        # Verify result structure
        assert "cvar_pct" in result
        assert "cvar_amount" in result
        assert "var_pct" in result
        assert "var_amount" in result
        assert "confidence" in result
        assert "n_tail" in result
        assert "n_simulations" in result
        assert "method" in result
        
        # Verify data types
        assert isinstance(result["cvar_pct"], float)
        assert isinstance(result["cvar_amount"], float)
        assert isinstance(result["var_pct"], float)
        assert isinstance(result["var_amount"], float)
        assert result["confidence"] == 0.95
        assert result["n_simulations"] == len(prices)
        assert result["method"] == "monte_carlo_cvar"
        
        # Verify CVaR > VaR (CVaR is more conservative)
        assert result["cvar_pct"] >= result["var_pct"]
        assert result["cvar_amount"] >= result["var_amount"]
        
        # Verify calculations are reasonable
        assert 0 <= result["cvar_pct"] <= 100  # Percentage between 0-100%
        assert 0 <= result["var_pct"] <= 100
        
        print(f"✅ Basic CVaR test passed: CVaR={result['cvar_pct']}%, VaR={result['var_pct']}%")
    
    def test_cvar_with_different_confidence(self):
        """Test CVaR with different confidence levels"""
        prices = [140, 145, 150, 155, 160] * 100  # 500 prices for better statistics
        current_price = 150.0
        
        # Test 90% confidence
        result_90 = calculate_cvar(prices, current_price, confidence=0.90)
        
        # Test 99% confidence
        result_99 = calculate_cvar(prices, current_price, confidence=0.99)
        
        # Higher confidence should give higher CVaR (more conservative)
        assert result_99["cvar_pct"] >= result_90["cvar_pct"]
        assert result_99["var_pct"] >= result_90["var_pct"]
        
        print(f"✅ Confidence level test: 90% CVaR={result_90['cvar_pct']}%, 99% CVaR={result_99['cvar_pct']}%")
    
    def test_cvar_portfolio_value_scaling(self):
        """Test that CVaR amount scales correctly with portfolio value"""
        prices = [145, 147, 149, 151, 153] * 50
        current_price = 150.0
        
        # Test with 100k portfolio
        result_100k = calculate_cvar(prices, current_price, portfolio_value=100000)
        
        # Test with 500k portfolio
        result_500k = calculate_cvar(prices, current_price, portfolio_value=500000)
        
        # CVaR percentage should be same
        assert abs(result_100k["cvar_pct"] - result_500k["cvar_pct"]) < 0.01
        
        # CVaR amount should scale 5x
        expected_ratio = 5.0
        actual_ratio = result_500k["cvar_amount"] / result_100k["cvar_amount"]
        assert abs(actual_ratio - expected_ratio) < 0.01
        
        print(f"✅ Portfolio scaling test: 100k=${result_100k['cvar_amount']:.2f}, 500k=${result_500k['cvar_amount']:.2f}")
    
    def test_cvar_error_handling(self):
        """Test error handling for invalid inputs"""
        # Empty prices
        result = calculate_cvar([], 150.0)
        assert "error" in result
        
        # Zero current price
        result = calculate_cvar([150, 155, 160], 0.0)
        assert "error" in result
        
        # Negative current price
        result = calculate_cvar([150, 155, 160], -10.0)
        assert "error" in result
        
        print("✅ Error handling test passed")


class TestCompareVarCvar:
    """Test compare_var_cvar function"""
    
    def test_compare_multiple_confidence_levels(self):
        """Test comparison across multiple confidence levels"""
        # Generate more prices for better statistics
        np.random.seed(42)
        prices = np.random.normal(loc=150, scale=10, size=1000).tolist()
        current_price = 150.0
        
        result = compare_var_cvar(
            prices=prices,
            current_price=current_price,
            confidence_levels=[0.90, 0.95, 0.99],
            portfolio_value=100000
        )
        
        # Verify structure
        assert "comparison" in result
        assert "portfolio_value" in result
        assert len(result["comparison"]) == 3
        
        # Verify each confidence level
        confidences = [0.90, 0.95, 0.99]
        for i, conf in enumerate(confidences):
            item = result["comparison"][i]
            assert item["confidence"] == conf
            assert "var_pct" in item
            assert "var_amount" in item
            assert "cvar_pct" in item
            assert "cvar_amount" in item
            assert "excess_loss" in item
            
            # CVaR should be greater than VaR
            assert item["cvar_pct"] >= item["var_pct"]
            assert item["cvar_amount"] >= item["var_amount"]
            assert item["excess_loss"] >= 0
        
        # Higher confidence should have higher risk measures
        comp = result["comparison"]
        assert comp[2]["var_pct"] >= comp[1]["var_pct"] >= comp[0]["var_pct"]  # 99% >= 95% >= 90%
        assert comp[2]["cvar_pct"] >= comp[1]["cvar_pct"] >= comp[0]["cvar_pct"]
        
        print("✅ Multiple confidence level comparison test passed")
    
    def test_compare_default_confidence_levels(self):
        """Test with default confidence levels"""
        prices = [140, 145, 150, 155, 160] * 200
        current_price = 150.0
        
        result = compare_var_cvar(prices, current_price)
        
        # Default should be [0.90, 0.95, 0.99]
        assert len(result["comparison"]) == 3
        assert result["comparison"][0]["confidence"] == 0.90
        assert result["comparison"][1]["confidence"] == 0.95
        assert result["comparison"][2]["confidence"] == 0.99
        
        print("✅ Default confidence levels test passed")
    
    def test_compare_custom_confidence_levels(self):
        """Test with custom confidence levels"""
        prices = [140, 145, 150, 155, 160] * 200
        current_price = 150.0
        
        result = compare_var_cvar(
            prices=prices,
            current_price=current_price,
            confidence_levels=[0.80, 0.85, 0.90, 0.95]
        )
        
        assert len(result["comparison"]) == 4
        assert result["comparison"][0]["confidence"] == 0.80
        assert result["comparison"][3]["confidence"] == 0.95
        
        print("✅ Custom confidence levels test passed")


class TestCVaRIntegration:
    """Integration tests for CVaR tool"""
    
    def test_integration_with_monte_carlo_prices(self):
        """Test CVaR using prices generated by monte_carlo tool"""
        # Simulate monte_carlo output (in real test, would import monte_carlo)
        # For now, create realistic price distribution
        np.random.seed(123)
        n_simulations = 10000
        current_price = 150.0
        annual_vol = 0.25  # 25% annual volatility
        daily_vol = annual_vol / np.sqrt(252)
        drift = 0.0
        
        # Generate GBM prices
        daily_returns = np.random.normal(drift, daily_vol, n_simulations)
        prices = current_price * np.exp(daily_returns * 30)  # 30-day horizon
        
        # Calculate CVaR
        result = calculate_cvar(
            prices=prices.tolist(),
            current_price=current_price,
            confidence=0.95,
            portfolio_value=100000
        )
        
        # Verify reasonable values for 25% vol
        # With 25% annualized vol and 30-day horizon, CVaR can be 5-70%
        assert 5 <= result["cvar_pct"] <= 70  # CVaR between 5-70% for 25% vol
        assert 5 <= result["var_pct"] <= 70   # VaR similar range
        
        print(f"✅ Integration test: CVaR={result['cvar_pct']:.2f}%, VaR={result['var_pct']:.2f}%")
    
    def test_cvar_tail_count(self):
        """Verify tail count matches confidence level"""
        n_simulations = 10000
        confidence = 0.95
        
        # Generate prices
        np.random.seed(456)
        prices = np.random.normal(loc=100, scale=10, size=n_simulations).tolist()
        current_price = 100.0
        
        result = calculate_cvar(prices, current_price, confidence=confidence)
        
        # Expected tail size: (1-confidence) * n_simulations
        expected_tail = int((1 - confidence) * n_simulations)
        actual_tail = result["n_tail"]
        
        # Allow some variation due to percentile calculation
        tolerance = 0.1 * expected_tail  # 10% tolerance
        assert abs(actual_tail - expected_tail) <= tolerance
        
        print(f"✅ Tail count test: expected={expected_tail}, actual={actual_tail}")


def run_all_tests():
    """Run all CVaR tests and report results"""
    print("=" * 60)
    print("RUNNING CVAR TOOL TESTS")
    print("=" * 60)
    
    test_classes = [
        TestCalculateCVaR(),
        TestCompareVarCvar(),
        TestCVaRIntegration()
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = []
    
    for test_class in test_classes:
        class_name = test_class.__class__.__name__
        print(f"\n📋 {class_name}")
        
        # Get all test methods
        test_methods = [method for method in dir(test_class) 
                       if method.startswith('test_') and callable(getattr(test_class, method))]
        
        for method_name in test_methods:
            total_tests += 1
            try:
                getattr(test_class, method_name)()
                print(f"  ✅ {method_name}")
                passed_tests += 1
            except AssertionError as e:
                print(f"  ❌ {method_name} - AssertionError: {e}")
                failed_tests.append(f"{class_name}.{method_name}: {e}")
            except Exception as e:
                print(f"  ❌ {method_name} - Error: {e}")
                failed_tests.append(f"{class_name}.{method_name}: {e}")
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {len(failed_tests)}")
    
    if failed_tests:
        print("\nFailed tests:")
        for failure in failed_tests:
            print(f"  • {failure}")
        return False
    else:
        print("\n✅ All tests passed!")
        return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)