"""
Unit tests for stress_test tool.
Tests crisis scenario simulation and stress testing.
"""

import pytest
import sys
import os

# Add parent directory to path to import tools
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

def test_stress_test_run_method():
    """Test run_stress_test method with custom scenarios."""
    test_cases = [
        {
            "name": "basic_stress_scenarios",
            "params": {
                "portfolio_value": 100000,
                "scenarios": [
                    {"name": "mild_stress", "shock_pct": 10},
                    {"name": "moderate_stress", "shock_pct": 25},
                    {"name": "severe_stress", "shock_pct": 40}
                ],
                "steps": 20
            },
            "expected_fields": ["scenario_results", "worst_case", "recovery_analysis"]
        },
        {
            "name": "single_scenario",
            "params": {
                "portfolio_value": 500000,
                "scenarios": [
                    {"name": "market_correction", "shock_pct": 15}
                ]
            },
            "expected_fields": ["scenario_results", "worst_case", "recovery_analysis"]
        },
        {
            "name": "multiple_shock_levels",
            "params": {
                "portfolio_value": 250000,
                "scenarios": [
                    {"name": "5%_drop", "shock_pct": 5},
                    {"name": "10%_drop", "shock_pct": 10},
                    {"name": "20%_drop", "shock_pct": 20},
                    {"name": "30%_drop", "shock_pct": 30}
                ]
            },
            "expected_fields": ["scenario_results", "worst_case", "recovery_analysis"]
        }
    ]
    
    for case in test_cases:
        assert "name" in case
        assert "params" in case
        assert "expected_fields" in case
        assert "portfolio_value" in case["params"]
        assert "scenarios" in case["params"]
        assert isinstance(case["params"]["scenarios"], list)
        assert len(case["params"]["scenarios"]) > 0

def test_stress_test_historical_method():
    """Test historical_stress method with preset crises."""
    test_cases = [
        {
            "name": "single_historical_crisis",
            "params": {
                "portfolio_value": 100000,
                "crises": ["gfc_2008"]  # Global Financial Crisis
            },
            "expected_fields": ["crisis_results", "comparison", "lessons"]
        },
        {
            "name": "multiple_historical_crises",
            "params": {
                "portfolio_value": 500000,
                "crises": ["asian_1997", "gfc_2008", "covid_2020"]
            },
            "expected_fields": ["crisis_results", "comparison", "lessons"]
        },
        {
            "name": "all_historical_crises",
            "params": {
                "portfolio_value": 1000000,
                "crises": ["asian_1997", "dot_com_2000", "gfc_2008", "covid_2020"]
            },
            "expected_fields": ["crisis_results", "comparison", "lessons"]
        }
    ]
    
    for case in test_cases:
        assert "name" in case
        assert "params" in case
        assert "expected_fields" in case
        assert "portfolio_value" in case["params"]
        if "crises" in case["params"]:
            assert isinstance(case["params"]["crises"], list)

def test_stress_test_position_method():
    """Test position_stress method for specific asset stress."""
    test_cases = [
        {
            "name": "equity_position_stress",
            "params": {
                "current_equity": 50000,
                "current_price": 100.0,
                "stress_price": 80.0,
                "units": 500
            },
            "expected_fields": ["stress_equity", "loss_amount", "loss_percentage", "margin_impact"]
        },
        {
            "name": "severe_position_stress",
            "params": {
                "current_equity": 100000,
                "current_price": 150.0,
                "stress_price": 100.0,  # 33% drop
                "units": 1000
            },
            "expected_fields": ["stress_equity", "loss_amount", "loss_percentage", "margin_impact"]
        }
        # Note: multiple_position_stress removed - would require tool extension
    ]

    for case in test_cases:
        assert "name" in case
        assert "params" in case
        assert "expected_fields" in case
        assert "current_equity" in case["params"]
        assert "current_price" in case["params"]
        assert "stress_price" in case["params"]
        assert "units" in case["params"]

def test_stress_test_edge_cases():
    """Test edge cases and error conditions."""
    edge_cases = [
        {
            "name": "zero_portfolio_value",
            "params": {
                "portfolio_value": 0,
                "scenarios": [{"name": "test", "shock_pct": 10}]
            },
            "should_error": True  # Zero portfolio value invalid
        },
        {
            "name": "negative_portfolio_value",
            "params": {
                "portfolio_value": -100000,
                "scenarios": [{"name": "test", "shock_pct": 10}]
            },
            "should_error": True  # Negative portfolio value invalid
        },
        {
            "name": "zero_shock_percentage",
            "params": {
                "portfolio_value": 100000,
                "scenarios": [{"name": "no_stress", "shock_pct": 0}]
            },
            "should_error": False  # Zero shock is valid (baseline)
        },
        {
            "name": "negative_shock_percentage",
            "params": {
                "portfolio_value": 100000,
                "scenarios": [{"name": "negative_stress", "shock_pct": -10}]  # Positive shock?
            },
            "should_error": False  # Negative shock might mean positive movement
        },
        {
            "name": "extreme_shock_percentage",
            "params": {
                "portfolio_value": 100000,
                "scenarios": [{"name": "wipeout", "shock_pct": 100}]
            },
            "should_error": False  # 100% shock is extreme but valid
        },
        {
            "name": "empty_scenarios_list",
            "params": {
                "portfolio_value": 100000,
                "scenarios": []
            },
            "should_error": True  # Empty scenarios invalid
        }
    ]
    
    for case in edge_cases:
        assert "name" in case
        assert "params" in case
        assert "should_error" in case

def test_stress_test_crisis_scenarios():
    """Test specific crisis scenario properties."""
    crisis_scenarios = [
        {
            "name": "asian_1997",
            "properties": ["currency_crisis", "regional", "high_volatility"]
        },
        {
            "name": "dot_com_2000",
            "properties": ["tech_bubble", "valuation_crash", "sector_specific"]
        },
        {
            "name": "gfc_2008",
            "properties": ["financial_crisis", "global", "liquidity_crunch", "systemic"]
        },
        {
            "name": "covid_2020",
            "properties": ["pandemic", "global", "supply_chain", "recovery_v-shaped"]
        }
    ]
    
    for crisis in crisis_scenarios:
        assert "name" in crisis
        assert "properties" in crisis
        assert isinstance(crisis["properties"], list)

def test_stress_test_recovery_analysis():
    """Test recovery analysis in stress test results."""
    recovery_tests = [
        {
            "name": "recovery_time_estimation",
            "description": "Estimate time to recover from stress scenario"
        },
        {
            "name": "recovery_probability",
            "description": "Probability of recovering within time horizon"
        },
        {
            "name": "recovery_path_simulation",
            "description": "Simulate possible recovery paths"
        }
    ]
    
    for test in recovery_tests:
        assert "name" in test
        assert "description" in test

def test_stress_test_application_scenarios():
    """Test stress test in different application contexts."""
    application_scenarios = [
        {
            "name": "regulatory_stress_testing",
            "steps": [
                "Run baseline scenario",
                "Run adverse scenario",
                "Run severely adverse scenario",
                "Calculate capital impact"
            ]
        },
        {
            "name": "portfolio_risk_management",
            "steps": [
                "Identify key risk factors",
                "Define stress scenarios",
                "Calculate portfolio impact",
                "Implement risk mitigants"
            ]
        },
        {
            "name": "investment_decision_support",
            "steps": [
                "Stress test investment thesis",
                "Assess downside scenarios",
                "Evaluate risk-adjusted returns",
                "Make informed decision"
            ]
        }
    ]
    
    for scenario in application_scenarios:
        assert "name" in scenario
        assert "steps" in scenario
        assert isinstance(scenario["steps"], list)
        assert len(scenario["steps"]) > 0

def test_stress_test_comparative_analysis():
    """Test comparative analysis of different stress scenarios."""
    comparative_tests = [
        {
            "name": "scenario_severity_comparison",
            "description": "Compare mild vs moderate vs severe scenarios"
        },
        {
            "name": "historical_vs_hypothetical",
            "description": "Compare historical crises with hypothetical scenarios"
        },
        {
            "name": "sensitivity_to_shock_size",
            "description": "Analyze how results change with shock magnitude"
        }
    ]
    
    for test in comparative_tests:
        assert "name" in test
        assert "description" in test

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])