from typing import Dict, Any
import json


def run_tri_agent_debate(topic: str, domain: str = "finance") -> Dict[str, Any]:
    """
    Execute tri-agent debate for idea exploration
    
    Args:
        topic: Research topic
        domain: Research domain (finance, technology, science)
        
    Returns:
        Dictionary containing debate results
    """
    # In production, this would call the tri_agent tool
    # For now, return a structured placeholder
    return {
        "topic": topic,
        "domain": domain,
        "bull_perspective": [
            f"Opportunity in {topic}: High growth potential",
            f"Market opportunity for {topic} is significant"
        ],
        "bear_perspective": [
            f"Risk in {topic}: Market volatility",
            f"Regulatory challenges for {topic}"
        ],
        "buffett_perspective": [
            f"Long-term value in {topic}: Sustainable advantages",
            f"Fundamentals support investment in {topic}"
        ],
        "consensus_focus": f"Balanced approach to {topic} considering opportunities and risks"
    }


def generate_research_proposal(debate_results: Dict[str, Any]) -> str:
    """
    Generate research proposal markdown from debate results
    """
    return f"""# Research Proposal: {debate_results['topic']}

## Bull Perspective\n- {debate_results['bull_perspective'][0]}\n- {debate_results['bull_perspective'][1]}

## Bear Perspective\n- {debate_results['bear_perspective'][0]}\n- {debate_results['bear_perspective'][1]}

## Buffett Perspective\n- {debate_results['buffett_perspective'][0]}\n- {debate_results['buffett_perspective'][1]}

## Recommended Focus\n{debate_results['consensus_focus']}"""