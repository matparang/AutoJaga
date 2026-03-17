from typing import Dict, Any
import json


def create_experiment_plan(topic: str, debate_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create detailed experiment plan from research proposal
    
    Args:
        topic: Research topic
        debate_results: Results from tri-agent debate
        
    Returns:
        Dictionary containing experiment plan
    """
    # In production, this would use LLM planning with templates
    # For now, return a structured placeholder
    return {
        "methodology": "comparative analysis",
        "topic": topic,
        "research_questions": [
            f"What are the key opportunities in {topic}?")
            f"What are the main risks associated with {topic}?")
            f"What is the long-term value proposition of {topic}?"
        ],
        "data_requirements": [
            "Market data",
            "Financial metrics",
            "Regulatory information",
            "Competitive landscape"
        ],
        "steps": [
            {
                "action": "collect_data",
                "sources": ["web_search", "financial_data", "regulatory_filings"]
            },
            {
                "action": "analyze",
                "metrics": ["volatility", "roi", "risk_assessment"]
            },
            {
                "action": "validate",
                "method": "cross_check_with_multiple_sources"
            }
        ],
        "success_criteria": [
            "accuracy > 0.95",
            "all_required_files_exist",
            "validation_passed"
        ],
        "timeline": {
            "planning": "1 day",
            "execution": "3 days",
            "synthesis": "1 day"
        }
    }


def save_experiment_plan(plan: Dict[str, Any], output_path: str):
    """
    Save experiment plan to JSON file
    """
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(plan, f, indent=2)