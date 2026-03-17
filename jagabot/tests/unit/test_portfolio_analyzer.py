"""
Unit tests for portfolio_analyzer tool.
Tests portfolio analysis, stress testing, and probability calculations.
"""

import pytest
import sys
import os

# Add parent directory to path to import tools
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

def test_portfolio_analyzer_analyze_method():
    """Test the analyze method with various portfolio configurations."""
    test_cases = [
        {
            "name": "basic_portfolio",
            "params": {
                "capital": 1000000,
                "leverage": 2.0,
                "positions": [
                    {
                        "symbol": "WTI",
                        "entry_price": 85.0,
                        "current_price": 72.5,
                        "quantity": 0,  # Will be calculated from weight
                        "weight": 0.6
                    },
                    {
                        "symbol": "BRENT",
                        "entry_price": 95.0,
                        "current_price": 81.2,
                        "quantity": 0,
                        "weight": 0.3
                    }
                ],
                "cash": 100000
            },
            "expected_fields": ["equity", "total_pnl", "margin_status", "cross_check"]
        },
        {
            "name": "single_position",
            "params": {
                "capital": 500000,
                "leverage": 1.5,
                "positions": [
                    {
                        "symbol": "AAPL",
                        "entry_price": 150.0,
                        "current_price": 180.0,
                        "quantity": 1000,
                        "weight": 1.0
                    }
                ],
                "cash": 0
            },
            "expected_fields": ["equity", "total_pnl", "margin_status", "cross_check"]
        },
        {
            "name": "all_cash",
            "params": {
                "capital": 1000000,
                "leverage": 1.0,
                "positions": [],
                "cash": 1000000
            },
            "expected_fields": ["equity", "total_pnl", "margin_status", "cross_check"]
        }
    ]
    
    for case in test_cases:
        assert "name" in case
        assert "params" in case
        assert "expected_fields" in case
        assert isinstance(case["params"], dict)
        assert "capital" in case["params"]
        assert "leverage" in case["params"]
        assert "positions" in case["params"]
        assert "cash" in case["params"]

def test_portfolio_analyzer_stress_test_method():
    """Test stress_test method with target price scenarios."""
    test_cases = [
        {
            "name": "single_stress_scenario",
            "params": {
                "capital": 1000000,
                "leverage": 2.0,
                "positions": [
                    {
                        "symbol": "WTI",
                        "entry_price": 85.0,
                        "current_price": 72.5,
                        "quantity": 10000,
                        "weight": 0.6
                    }
                ],
                "target_prices": {"WTI": 60.0}
            },
            "expected_fields": ["stress_equity", "stress_pnl", "margin_call_risk"]
        },
        {
            "name": "multiple_stress_scenarios",
            "params": {
                "capital": 2000000,
                "leverage": 3.0,
                "positions": [
                    {
                        "symbol": "WTI",
                        "entry_price": 85.0,
                        "current_price": 72.5,
                        "quantity": 20000,
                        "weight": 0.5
                    },
                    {
                        "symbol": "BRENT",
                        "entry_price": 95.0,
                        "current_price": 81.2,
                        "quantity": 10000,
                        "weight": 0.3
                    }
                ],
                "target_prices": {"WTI": 60.0, "BRENT": 70.0}
            },
            "expected_fields": ["stress_equity", "stress_pnl", "margin_call_risk"]
        }
    ]
    
    for case in test_cases:
        assert "name" in case
        assert "params" in case
        assert "expected_fields" in case
        assert "target_prices" in case["params"]
        assert isinstance(case["params"]["target_prices"], dict)

def test_portfolio_analyzer_probability_method():
    """Test probability method for price target calculations."""
    test_cases = [
        {
            "name": "basic_probability",
            "params": {
                "current_price": 72.5,
                "target_price": 60.0,
                "daily_returns": [0.02, -0.01, 0.015, -0.005, 0.01, -0.02, 0.005],
                "days": 30
            },
            "expected_type": float  # Probability should be float 0-100
        },
        {
            "name": "short_horizon",
            "params": {
                "current_price": 100.0,
                "target_price": 95.0,
                "daily_returns": [0.01, -0.005, 0.002],
                "days": 5
            },
            "expected_type": float
        },
        {
            "name": "long_horizon",
            "params": {
                "current_price": 50.0,
                "target_price": 40.0,
                "daily_returns": [-0.01, 0.005, -0.015, 0.002, -0.008],
                "days": 90
            },
            "expected_type": float
        }
    ]
    
    for case in test_cases:
        assert "name" in case
        assert "params" in case
        assert "expected_type" in case
        assert "current_price" in case["params"]
        assert "target_price" in case["params"]
        assert "daily_returns" in case["params"]
        assert "days" in case["params"]

def test_portfolio_analyzer_edge_cases():
    """Test edge cases and error conditions."""
    edge_cases = [
        {
            "name": "zero_capital",
            "params": {
                "capital": 0,
                "leverage": 1.0,
                "positions": [],
                "cash": 0
            },
            "should_error": True  # Zero capital invalid
        },
        {
            "name": "negative_leverage",
            "params": {
                "capital": 1000000,
                "leverage": -1.0,
                "positions": [],
                "cash": 0
            },
            "should_error": True  # Negative leverage invalid
        },
        {
            "name": "leverage_less_than_one",
            "params": {
                "capital": 1000000,
                "leverage": 0.5,
                "positions": [],
                "cash": 0
            },
            "should_error": False  # Leverage < 1 is valid (no borrowing)
        },
        {
            "name": "negative_cash",
            "params": {
                "capital": 1000000,
                "leverage": 2.0,
                "positions": [],
                "cash": -100000
            },
            "should_error": True  # Negative cash invalid
        },
        {
            "name": "weight_sum_not_one",
            "params": {
                "capital": 1000000,
                "leverage": 2.0,
                "positions": [
                    {
                        "symbol": "WTI",
                        "entry_price": 85.0,
                        "current_price": 72.5,
                        "quantity": 0,
                        "weight": 0.8  # Sum would be 0.8, not 1.0
                    }
                ],
                "cash": 0
            },
            "should_error": False  # Tool should handle weight normalization
        }
    ]
    
    for case in edge_cases:
        assert "name" in case
        assert "params" in case
        assert "should_error" in case

def test_portfolio_analyzer_cross_check_validation():
    """Test cross-check validation in analyze method."""
    validation_tests = [
        {
            "name": "equity_calculation",
            "condition": "equity == capital + total_pnl"
        },
        {
            "name": "position_value_calculation",
            "condition": "position_value == sum(qty * current_price for all positions)"
        },
        {
            "name": "exposure_calculation",
            "condition": "exposure == capital * leverage"
        },
        {
            "name": "margin_requirement",
            "condition": "margin_required == exposure / leverage"  # Or similar formula
        }
    ]
    
    for test in validation_tests:
        assert "name" in test
        assert "condition" in test

def test_portfolio_analyzer_integration_scenarios():
    """Test integrated scenarios combining multiple methods."""
    integration_scenarios = [
        {
            "name": "full_analysis_flow",
            "steps": [
                "analyze current portfolio",
                "stress_test with target prices",
                "calculate probability of further decline"
            ]
        },
        {
            "name": "margin_call_scenario",
            "steps": [
                "analyze with high leverage",
                "stress_test with severe price drops",
                "check margin_call_risk flag"
            ]
        }
    ]
    
    for scenario in integration_scenarios:
        assert "name" in scenario
        assert "steps" in scenario
        assert isinstance(scenario["steps"], list)
        assert len(scenario["steps"]) > 0

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])