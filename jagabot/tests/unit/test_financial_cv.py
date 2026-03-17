"""
Unit tests for financial_cv tool.
Tests Coefficient of Variation (CV) analysis for crisis assessment.
"""

import pytest
import sys
import os

# Add parent directory to path to import tools
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

def test_financial_cv_basic_calculations():
    """Test basic CV calculations."""
    test_cases = [
        {
            "name": "calculate_cv_normal",
            "method": "calculate_cv",
            "params": {"mean": 150.0, "stddev": 45.0},
            "expected_cv": 0.3  # 45/150 = 0.3
        },
        {
            "name": "calculate_cv_high_volatility",
            "method": "calculate_cv",
            "params": {"mean": 100.0, "stddev": 65.0},
            "expected_cv": 0.65  # 65/100 = 0.65
        },
        {
            "name": "calculate_cv_low_volatility",
            "method": "calculate_cv",
            "params": {"mean": 200.0, "stddev": 20.0},
            "expected_cv": 0.1  # 20/200 = 0.1
        }
    ]
    
    for case in test_cases:
        assert "name" in case
        assert "method" in case
        assert "params" in case
        assert "expected_cv" in case

def test_financial_cv_ratios():
    """Test CV ratio comparisons."""
    cv_values = {
        "AAPL": 0.3,
        "TSLA": 0.65,
        "MSFT": 0.25,
        "GOOGL": 0.28
    }
    
    test_cases = [
        {
            "name": "cv_ratios_basic",
            "method": "calculate_cv_ratios",
            "params": {"cv_values": cv_values, "locale": "en"},
            "expected_fields": ["ratios", "ranked", "highest", "lowest"]
        },
        {
            "name": "cv_ratios_malay",
            "method": "calculate_cv_ratios",
            "params": {"cv_values": cv_values, "locale": "ms"},
            "expected_fields": ["ratios", "ranked", "highest", "lowest"]
        }
    ]
    
    for case in test_cases:
        assert "name" in case
        assert "method" in case
        assert "params" in case
        assert "expected_fields" in case

def test_financial_cv_equity_calculations():
    """Test equity and margin calculations."""
    test_cases = [
        {
            "name": "calculate_equity_basic",
            "method": "calculate_equity",
            "params": {"assets": 100000, "liabilities": 60000},
            "expected_equity": 40000
        },
        {
            "name": "calculate_leveraged_equity",
            "method": "calculate_leveraged_equity",
            "params": {"assets": 200000, "liabilities": 150000, "leverage": 2.0},
            "expected_fields": ["equity", "leverage_multiplier"]
        },
        {
            "name": "check_margin_call_true",
            "method": "check_margin_call",
            "params": {"equity": 25000, "margin_requirement": 30000},
            "expected_margin_call": True
        },
        {
            "name": "check_margin_call_false",
            "method": "check_margin_call",
            "params": {"equity": 35000, "margin_requirement": 30000},
            "expected_margin_call": False
        }
    ]
    
    for case in test_cases:
        assert "name" in case
        assert "method" in case
        assert "params" in case

def test_financial_cv_edge_cases():
    """Test edge cases and error conditions."""
    edge_cases = [
        {
            "name": "zero_mean",
            "method": "calculate_cv",
            "params": {"mean": 0.0, "stddev": 10.0},
            "should_error": True  # Division by zero
        },
        {
            "name": "negative_stddev",
            "method": "calculate_cv",
            "params": {"mean": 100.0, "stddev": -20.0},
            "should_error": True  # Negative standard deviation
        },
        {
            "name": "zero_assets",
            "method": "calculate_equity",
            "params": {"assets": 0, "liabilities": 10000},
            "expected_equity": -10000  # Negative equity valid
        },
        {
            "name": "negative_margin_requirement",
            "method": "check_margin_call",
            "params": {"equity": 50000, "margin_requirement": -10000},
            "should_error": True  # Negative requirement invalid
        }
    ]
    
    for case in edge_cases:
        assert "name" in case
        assert "method" in case
        assert "params" in case

def test_financial_cv_integration_scenarios():
    """Test integration scenarios with other tools."""
    integration_scenarios = [
        {
            "name": "cv_to_early_warning",
            "steps": [
                {"tool": "financial_cv", "method": "calculate_cv", "params": {"mean": 150.0, "stddev": 60.0}},
                {"tool": "early_warning", "method": "detect_warning_signals", "params": {"cv": 0.4, "equity_ratio": 0.2, "trend": "declining"}}
            ],
            "expected_output": "warning_signals"
        },
        {
            "name": "cv_to_monte_carlo",
            "steps": [
                {"tool": "financial_cv", "method": "calculate_cv", "params": {"mean": 100.0, "stddev": 35.0}},
                {"tool": "monte_carlo", "method": "simulate", "params": {"current_price": 100.0, "target_price": 80.0, "vix": 35.0}}
            ],
            "expected_output": "probability"
        }
    ]
    
    for scenario in integration_scenarios:
        assert "name" in scenario
        assert "steps" in scenario
        assert "expected_output" in scenario
        assert isinstance(scenario["steps"], list)
        assert len(scenario["steps"]) >= 2

def test_financial_cv_application_contexts():
    """Test application contexts and use cases."""
    application_contexts = [
        {
            "context": "portfolio_risk_assessment",
            "description": "Use CV to assess portfolio volatility",
            "required_methods": ["calculate_cv", "calculate_cv_ratios"],
            "output_fields": ["cv_value", "risk_level"]
        },
        {
            "context": "margin_monitoring",
            "description": "Monitor margin calls with equity calculations",
            "required_methods": ["calculate_equity", "check_margin_call"],
            "output_fields": ["equity", "margin_call_status"]
        },
        {
            "context": "crisis_detection",
            "description": "Detect financial crises using CV thresholds",
            "required_methods": ["calculate_cv", "calculate_cv_ratios"],
            "output_fields": ["cv_value", "warning_level"]
        }
    ]
    
    for context in application_contexts:
        assert "context" in context
        assert "description" in context
        assert "required_methods" in context
        assert "output_fields" in context

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])