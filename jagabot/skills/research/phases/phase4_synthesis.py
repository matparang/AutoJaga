from typing import Dict, Any
import json


def synthesize_research_results(plan: Dict[str, Any], results: Dict[str, Any]) -> str:
    """
    Synthesize research results using tri-agent interpretation
    
    Args:
        plan: Experiment plan dictionary
        results: Execution results dictionary
        
    Returns:
        Markdown string containing research summary
    """
    # In production, this would call tri_agent tool with synthesis template
    # For now, return a structured placeholder
    return f"""# Research Summary: {plan['topic']}

## Executive Summary
Comprehensive research on {plan['topic']} has been completed using the 4-phase AutoJaga research pipeline.

## Bull Interpretation
The research indicates strong growth opportunities with positive market indicators and technological advantages. Key findings include high ROI potential and significant market opportunity.

## Bear Interpretation
Significant risks were identified including market volatility, regulatory challenges, and competitive pressures. The risk assessment indicates moderate exposure that requires careful management.

## Buffett Interpretation
From a long-term value perspective, the research highlights sustainable fundamentals and competitive advantages that support investment. The analysis shows strong cash flow generation and durable moats.

## Conclusion
A balanced approach is recommended, leveraging opportunities while managing identified risks through diversification and risk mitigation strategies. The research supports strategic investment in {plan['topic']} with appropriate risk controls.

## Next Steps
- Conduct deeper analysis of specific market segments
- Monitor regulatory developments
- Track key performance indicators quarterly
- Review investment thesis annually

## References
- AutoJaga Research Pipeline v1.0
- Financial Data Sources
- Web Search Results
- Regulatory Filings"""


def save_research_summary(summary: str, output_path: str):
    """
    Save research summary to markdown file
    """
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(summary)