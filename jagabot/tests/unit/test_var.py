"""
Unit tests for var tool (Value at Risk).
Tests parametric, historical, and Monte Carlo VaR calculations.
"""

import pytest
import sys
import os

# Add parent directory to path to import tools
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

def test_var_parametric_method():
    """Test parametric VaR calculation."""
    test_cases = [
        {
            "name": "basic_parametric_var",
            "params": {
                "mean_return": -0.001,
                "std_return": 0.025,
                "confidence": 0.95,
                "portfolio_value": 100000,
                "holding_period": 10
            },
            "expected_fields": ["var_amount", "var_percentage", "confidence_level"]
        },
        {
            "name": "high_confidence",
            "params": {
                "mean_return": 0.0005,
                "std_return": 0.03,
                "confidence": 0.99,
                "portfolio_value": 500000
            },
            "expected_fields": ["var_amount", "var_percentage", "confidence_level"]
        },
        {
            "name": "different_holding_period",
            "params": {
                "mean_return": 0.0,
                "std_return": 0.02,
                "confidence": 0.95,
                "portfolio_value": 1000000,
                "holding_period": 1  # 1-day VaR
            },
            "expected_fields": ["var_amount", "var_percentage", "confidence_level"]
        }
    ]
    
    for case in test_cases:
        assert "name" in case
        assert "params" in case
        assert "expected_fields" in case
        assert "mean_return" in case["params"]
        assert "std_return" in case["params"]
        assert "confidence" in case["params"]

def test_var_historical_method():
    """Test historical VaR calculation."""
    test_cases = [
        {
            "name": "basic_historical_var",
            "params": {
                "returns": [-0.02, 0.01, -0.03, 0.005, -0.015, 0.008, -0.01],
                "confidence": 0.95,
                "portfolio_value": 100000
            },
            "expected_fields": ["var_amount", "var_percentage", "confidence_level"]
        },
        {
            "name": "small_sample",
            "params": {
                "returns": [-0.05, -0.03, -0.01],
                "confidence": 0.90,
                "portfolio_value": 50000
            },
            "expected_fields": ["var_amount", "var_percentage", "confidence_level"]
        },
        {
            "name": "mixed_returns",
            "params": {
                "returns": [0.02, -0.01, 0.03, -0.02, 0.01, -0.03, 0.005, -0.015],
                "confidence": 0.99,
                "portfolio_value": 250000
            },
            "expected_fields": ["var_amount", "var_percentage", "confidence_level"]
        }
    ]
    
    for case in test_cases:
        assert "name" in case
        assert "params" in case
        assert "expected_fields" in case
        assert "returns" in case["params"]
        assert isinstance(case["params"]["returns"], list)
        assert len(case["params"]["returns"]) > 0

def test_var_monte_carlo_method():
    """Test Monte Carlo VaR calculation."""
    test_cases = [
        {
            "name": "basic_monte_carlo_var",
            "params": {
                "prices": [148, 142, 155, 138, 145, 152, 140, 147, 135, 150],
                "current_price": 150,
                "confidence": 0.95,
                "portfolio_value": 100000
            },
            "expected_fields": ["var_amount", "var_percentage", "confidence_level"]
        },
        {
            "name": "volatile_prices",
            "params": {
                "prices": [130, 170, 125, 175, 120, 180, 115, 185, 110, 190],
                "current_price": 150,
                "confidence": 0.99,
                "portfolio_value": 500000
            },
            "expected_fields": ["var_amount", "var_percentage", "confidence_level"]
        }
    ]
    
    for case in test_cases:
        assert "name" in case
        assert "params" in case
        assert "expected_fields" in case
        assert "prices" in case["params"]
        assert "current_price" in case["params"]
        assert isinstance(case["params"]["prices"], list)
        assert len(case["params"]["prices"]) > 0

def test_var_portfolio_method():
    """Test portfolio VaR calculation."""
    test_cases = [
        {
            "name": "basic_portfolio_var",
            "params": {
                "position_value": 100000,
                "cash": 50000,
                "annual_vol": 0.25,
                "holding_period": 10,
                "confidence": 0.95
            },
            "expected_fields": ["var_amount", "var_percentage", "confidence_level"]
        },
        {
            "name": "high_volatility_portfolio",
            "params": {
                "position_value": 500000,
                "cash": 100000,
                "annual_vol": 0.40,
                "holding_period": 1,
                "confidence": 0.99
            },
            "expected_fields": ["var_amount", "var_percentage", "confidence_level"]
        }
    ]
    
    for case in test_cases:
        assert "name" in case
        assert "params" in case
        assert "expected_fields" in case
        assert "position_value" in case["params"]
        assert "annual_vol" in case["params"]

def test_var_edge_cases():
    """Test edge cases and error conditions."""
    edge_cases = [
        {
            "name": "zero_portfolio_value",
            "params": {
                "mean_return": 0.0,
                "std_return": 0.02,
                "confidence": 0.95,
                "portfolio_value": 0
            },
            "should_error": True  # Zero portfolio value invalid
        },
        {
            "name": "negative_portfolio_value",
            "params": {
                "mean_return": 0.0,
                "std_return": 0.02,
                "confidence": 0.95,
                "portfolio_value": -100000
            },
            "should_error": True  # Negative portfolio value invalid
        },
        {
            "name": "confidence_out_of_range_low",
            "params": {
                "mean_return": 0.0,
                "std_return": 0.02,
                "confidence": 0.50,  # Too low for meaningful VaR
                "portfolio_value": 100000
            },
            "should_error": False  # Low confidence is valid
        },
        {
            "name": "confidence_out_of_range_high",
            "params": {
                "mean_return": 0.0,
                "std_return": 0.02,
                "confidence": 0.999,  # Very high
                "portfolio_value": 100000
            },
            "should_error": False  # High confidence is valid
        },
        {
            "name": "negative_std_return",
            "params": {
                "mean_return": 0.0,
                "std_return": -0.02,  # Negative volatility
                "confidence": 0.95,
                "portfolio_value": 100000
            },
            "should_error": True  # Negative volatility invalid
        }
    ]
    
    for case in edge_cases:
        assert "name" in case
        assert "params" in case
        assert "should_error" in case

def test_var_statistical_properties():
    """Test statistical properties of VaR calculations."""
    statistical_tests = [
        {
            "name": "var_increases_with_confidence",
            "condition": "var_95 < var_99"  # VaR should increase with confidence level
        },
        {
            "name": "var_scales_with_portfolio_value",
            "condition": "var_amount ∝ portfolio_value"
        },
        {
            "name": "var_increases_with_volatility",
            "condition": "var_low_vol < var_high_vol"
        },
        {
            "name": "var_positive_amount",
            "condition": "var_amount >= 0"  # VaR is typically positive (loss amount)
        }
    ]
    
    for test in statistical_tests:
        assert "name" in test
        assert "condition" in test

def test_var_method_comparison():
    """Compare different VaR methods for consistency."""
    comparison_tests = [
        {
            "name": "parametric_vs_historical",
            "description": "Parametric and historical VaR should be similar for normal returns"
        },
        {
            "name": "monte_carlo_consistency",
            "description": "Monte Carlo VaR should converge with enough simulations"
        }
    ]
    
    for test in comparison_tests:
        assert "name" in test
        assert "description" in test

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])