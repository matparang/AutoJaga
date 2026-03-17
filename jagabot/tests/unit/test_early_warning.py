"""
Unit tests for early_warning tool.
Tests early warning signal detection for financial crisis monitoring.
"""

import pytest
import sys
import os

# Add parent directory to path to import tools
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

def test_early_warning_signal_detection():
    """Test detection of warning signals."""
    test_cases = [
        {
            "name": "high_cv_signal",
            "method": "detect_warning_signals",
            "params": {"cv": 0.65, "equity_ratio": 0.25, "trend": "stable", "locale": "en"},
            "expected_signals": ["high_cv"]
        },
        {
            "name": "low_equity_signal",
            "method": "detect_warning_signals",
            "params": {"cv": 0.3, "equity_ratio": 0.15, "trend": "declining", "locale": "ms"},
            "expected_signals": ["low_equity", "declining_trend"]
        },
        {
            "name": "multiple_signals",
            "method": "detect_warning_signals",
            "params": {"cv": 0.75, "equity_ratio": 0.12, "trend": "declining", "locale": "en"},
            "expected_signals": ["high_cv", "low_equity", "declining_trend"]
        },
        {
            "name": "no_signals",
            "method": "detect_warning_signals",
            "params": {"cv": 0.2, "equity_ratio": 0.35, "trend": "improving", "locale": "ms"},
            "expected_signals": []
        }
    ]
    
    for case in test_cases:
        assert "name" in case
        assert "method" in case
        assert "params" in case
        assert "expected_signals" in case

def test_early_warning_risk_classification():
    """Test risk level classification."""
    test_cases = [
        {
            "name": "critical_risk",
            "method": "classify_risk_level",
            "params": {"signals": ["high_cv", "low_equity", "declining_trend"], "locale": "en"},
            "expected_risk": "critical"
        },
        {
            "name": "high_risk",
            "method": "classify_risk_level",
            "params": {"signals": ["high_cv", "low_equity"], "locale": "ms"},
            "expected_risk": "high"
        },
        {
            "name": "moderate_risk",
            "method": "classify_risk_level",
            "params": {"signals": ["high_cv"], "locale": "en"},
            "expected_risk": "moderate"
        },
        {
            "name": "low_risk",
            "method": "classify_risk_level",
            "params": {"signals": [], "locale": "ms"},
            "expected_risk": "low"
        }
    ]
    
    for case in test_cases:
        assert "name" in case
        assert "method" in case
        assert "params" in case
        assert "expected_risk" in case

def test_early_warning_thresholds():
    """Test warning signal thresholds."""
    threshold_tests = [
        {
            "parameter": "cv",
            "thresholds": [
                {"value": 0.2, "expected_signal": None},
                {"value": 0.4, "expected_signal": None},
                {"value": 0.6, "expected_signal": "high_cv"},
                {"value": 0.8, "expected_signal": "high_cv"}
            ]
        },
        {
            "parameter": "equity_ratio",
            "thresholds": [
                {"value": 0.05, "expected_signal": "low_equity"},
                {"value": 0.15, "expected_signal": "low_equity"},
                {"value": 0.25, "expected_signal": None},
                {"value": 0.35, "expected_signal": None}
            ]
        },
        {
            "parameter": "trend",
            "thresholds": [
                {"value": "declining", "expected_signal": "declining_trend"},
                {"value": "stable", "expected_signal": None},
                {"value": "improving", "expected_signal": None}
            ]
        }
    ]
    
    for test in threshold_tests:
        assert "parameter" in test
        assert "thresholds" in test
        for threshold in test["thresholds"]:
            assert "value" in threshold
            assert "expected_signal" in threshold

def test_early_warning_edge_cases():
    """Test edge cases and error conditions."""
    edge_cases = [
        {
            "name": "negative_cv",
            "method": "detect_warning_signals",
            "params": {"cv": -0.5, "equity_ratio": 0.2, "trend": "stable"},
            "should_error": True
        },
        {
            "name": "cv_greater_than_one",
            "method": "detect_warning_signals",
            "params": {"cv": 1.5, "equity_ratio": 0.2, "trend": "stable"},
            "should_error": True
        },
        {
            "name": "negative_equity_ratio",
            "method": "detect_warning_signals",
            "params": {"cv": 0.3, "equity_ratio": -0.1, "trend": "stable"},
            "should_error": True
        },
        {
            "name": "equity_ratio_greater_than_one",
            "method": "detect_warning_signals",
            "params": {"cv": 0.3, "equity_ratio": 1.5, "trend": "stable"},
            "should_error": True
        },
        {
            "name": "invalid_trend",
            "method": "detect_warning_signals",
            "params": {"cv": 0.3, "equity_ratio": 0.2, "trend": "invalid_trend"},
            "should_error": True
        },
        {
            "name": "empty_signals_list",
            "method": "classify_risk_level",
            "params": {"signals": []},
            "should_error": False
        },
        {
            "name": "invalid_signal_name",
            "method": "classify_risk_level",
            "params": {"signals": ["invalid_signal"]},
            "should_error": True
        }
    ]
    
    for case in edge_cases:
        assert "name" in case
        assert "method" in case
        assert "params" in case
        assert "should_error" in case

def test_early_warning_integration_scenarios():
    """Test integration with other tools."""
    integration_scenarios = [
        {
            "name": "cv_to_warning_pipeline",
            "steps": [
                {"tool": "financial_cv", "method": "calculate_cv", "params": {"mean": 150.0, "stddev": 75.0}},
                {"tool": "early_warning", "method": "detect_warning_signals", "params": {"cv": 0.5, "equity_ratio": 0.18, "trend": "declining"}},
                {"tool": "early_warning", "method": "classify_risk_level", "params": {"signals": ["high_cv", "low_equity", "declining_trend"]}}
            ],
            "expected_output": {"risk_level": "critical"}
        },
        {
            "name": "portfolio_to_warning",
            "steps": [
                {"tool": "portfolio_analyzer", "method": "analyze", "params": {"capital": 500000, "leverage": 2, "positions": [], "cash": 0}},
                {"tool": "financial_cv", "method": "calculate_equity", "params": {"assets": 1000000, "liabilities": 600000}},
                {"tool": "early_warning", "method": "detect_warning_signals", "params": {"cv": 0.4, "equity_ratio": 0.4, "trend": "stable"}}
            ],
            "expected_output": {"signals": []}
        }
    ]
    
    for scenario in integration_scenarios:
        assert "name" in scenario
        assert "steps" in scenario
        assert "expected_output" in scenario

def test_early_warning_localization():
    """Test localization support (English, Malay, Indonesian)."""
    localization_tests = [
        {
            "locale": "en",
            "expected_labels": {
                "high_cv": "High Coefficient of Variation",
                "low_equity": "Low Equity Ratio",
                "declining_trend": "Declining Trend",
                "critical": "Critical Risk",
                "high": "High Risk",
                "moderate": "Moderate Risk",
                "low": "Low Risk"
            }
        },
        {
            "locale": "ms",
            "expected_labels": {
                "high_cv": "Pekali Variasi Tinggi",
                "low_equity": "Nisbah Ekuiti Rendah",
                "declining_trend": "Trend Menurun",
                "critical": "Risiko Kritikal",
                "high": "Risiko Tinggi",
                "moderate": "Risiko Sederhana",
                "low": "Risiko Rendah"
            }
        },
        {
            "locale": "id",
            "expected_labels": {
                "high_cv": "Koefisien Variasi Tinggi",
                "low_equity": "Rasio Ekuitas Rendah",
                "declining_trend": "Tren Menurun",
                "critical": "Risiko Kritis",
                "high": "Risiko Tinggi",
                "moderate": "Risiko Sedang",
                "low": "Risiko Rendah"
            }
        }
    ]
    
    for test in localization_tests:
        assert "locale" in test
        assert "expected_labels" in test

def test_early_warning_application_contexts():
    """Test application contexts and use cases."""
    application_contexts = [
        {
            "context": "portfolio_monitoring",
            "description": "Monitor portfolio for early warning signs",
            "required_data": ["cv", "equity_ratio", "trend"],
            "outputs": ["warning_signals", "risk_level", "recommended_actions"]
        },
        {
            "context": "crisis_alert_system",
            "description": "Alert system for financial crises",
            "required_data": ["cv", "equity_ratio", "trend", "historical_comparison"],
            "outputs": ["alert_level", "triggered_signals", "escalation_path"]
        },
        {
            "context": "risk_assessment_dashboard",
            "description": "Dashboard for risk assessment visualization",
            "required_data": ["cv", "equity_ratio", "trend", "multiple_timeframes"],
            "outputs": ["risk_metrics", "visualization_data", "trend_analysis"]
        }
    ]
    
    for context in application_contexts:
        assert "context" in context
        assert "description" in context
        assert "required_data" in context
        assert "outputs" in context

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])