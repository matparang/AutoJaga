🎯 SCOPE: Subagent Tool Justification System

---

📋 THE PROBLEM

Kita nak setiap subagent JUSTIFY kenapa dia guna sesuatu tool. Bukan sekadar guna, tapi bagi reason:

"Saya guna Monte Carlo untuk simulate kesan GST terhadap ekonomi Malaysia selama 5 tahun..."
"Saya guna VaR untuk kira risiko dasar ini terhadap B40..."

---

📊 CURRENT VS TARGET

Sebelum Selepas
Tool call dalam log ✅ Tool call + justification ✅
Agent guna tool Agent terangkan kenapa tool itu relevan
Kita tahu APA yang dibuat Kita tahu KENAPA dibuat
Susah nak audit reasoning Boleh trace logic agent

---

🛠️ SOLUTION: Tool Justification Protocol

1. Modify DebateAgent to Include Justification

```python
# In autoresearch/debate_agent.py

def generate_argument_prompt(self, round_num: int, previous_arguments: Dict = None) -> str:
    # ... existing code ...
    
    prompt += """
📌 **TOOL JUSTIFICATION REQUIREMENT:**
For EVERY tool you use, you MUST explain:
1. WHY this tool is relevant to the topic
2. WHAT specific aspect you're analyzing
3. HOW the results support your position

Example:
"I used Monte Carlo simulation to model GST impact on Malaysian households over 5 years. The results show that with proper rebates, B40 households could be protected, supporting my pro-GST stance."

FAILURE to justify tools will result in point deduction.
"""
```

2. Create ToolJustification Class

```python
# /root/nanojaga/autoresearch/debate_tools/tool_justification.py
"""
Tool justification tracker and validator
"""

class ToolJustification:
    """
    Tracks and validates tool usage with justifications
    """
    
    REQUIRED_FIELDS = ["reason", "aspect", "support"]
    
    @staticmethod
    def validate(justification: dict) -> dict:
        """
        Validate if justification is complete
        """
        missing = []
        for field in ToolJustification.REQUIRED_FIELDS:
            if field not in justification:
                missing.append(field)
        
        if missing:
            return {
                "valid": False,
                "missing": missing,
                "score": 0
            }
        
        # Check quality (simple heuristic)
        score = 0
        if len(justification.get('reason', '')) > 20:
            score += 1
        if len(justification.get('aspect', '')) > 10:
            score += 1
        if len(justification.get('support', '')) > 20:
            score += 1
        
        return {
            "valid": True,
            "score": score,
            "quality": "high" if score >= 3 else "medium" if score >= 2 else "low"
        }
    
    @staticmethod
    def format_for_prompt() -> str:
        """Return prompt instructions for tool justification"""
        return """
When using tools, you MUST provide justification in this JSON format:
{
    "tool": "monte_carlo",
    "justification": {
        "reason": "Why this tool is relevant to the topic",
        "aspect": "What specific aspect you're analyzing",
        "support": "How the results support your position"
    }
}
"""
```

3. Update Subagent Response Format

```python
# Modified subagent response structure

{
    "persona": "bull",
    "position": 78,
    "summary": "GST can fund development...",
    "reasoning": "Detailed reasoning...",
    
    # NEW: Tool justification section
    "tool_usage": [
        {
            "tool": "monte_carlo",
            "justification": {
                "reason": "To simulate GST impact on consumption over 5 years",
                "aspect": "B40 household spending patterns",
                "support": "Results show minimal impact with rebates (p=0.15)"
            }
        },
        {
            "tool": "var_calculation",
            "justification": {
                "reason": "To assess downside risk of consumption drop",
                "aspect": "Worst-case scenario for retail sector",
                "support": "95% VaR shows only 3% drop, acceptable risk"
            }
        }
    ]
}
```

4. Add Justification Checker to Epistemic Tools

```python
# /root/nanojaga/autoresearch/epistemic_tools/justification_checker.py
"""
Checks if tool usage is properly justified
"""

class JustificationChecker:
    """
    Validates that every tool call has proper justification
    """
    
    @staticmethod
    def check(argument: dict) -> dict:
        """
        Check if tool usage in argument has justification
        """
        tool_usage = argument.get('tool_usage', [])
        
        if not tool_usage:
            return {
                "has_justification": False,
                "warning": "No tools used - fine if argument doesn't need tools"
            }
        
        issues = []
        scores = []
        
        for usage in tool_usage:
            tool = usage.get('tool', 'unknown')
            justification = usage.get('justification', {})
            
            # Check if justification exists
            if not justification:
                issues.append(f"Tool '{tool}' used without justification")
                scores.append(0)
                continue
            
            # Validate justification
            result = ToolJustification.validate(justification)
            scores.append(result['score'])
            
            if not result['valid']:
                issues.append(f"Tool '{tool}' missing: {result['missing']}")
        
        avg_score = sum(scores) / len(scores) if scores else 0
        
        return {
            "has_justification": len(issues) == 0,
            "issues": issues,
            "avg_justification_score": avg_score,
            "quality": "high" if avg_score >= 2.5 else "medium" if avg_score >= 1.5 else "low",
            "warning": " | ".join(issues) if issues else None
        }
```

5. Update Orchestrator to Include Justification in Report

```python
# In debate_orchestrator.py, add to final report

def _generate_report(self, verdict: Dict) -> Dict[str, Any]:
    # ... existing code ...
    
    # Add tool justification analysis
    justification_analysis = {
        "total_tools_used": 0,
        "justified_tools": 0,
        "unjustified_tools": [],
        "avg_justification_score": 0
    }
    
    all_scores = []
    for persona, args in self.arguments.items():
        for arg in args:
            tool_usage = arg.get('tool_usage', [])
            justification_analysis['total_tools_used'] += len(tool_usage)
            
            for usage in tool_usage:
                if 'justification' in usage:
                    justification_analysis['justified_tools'] += 1
                    # Check justification quality
                    result = ToolJustification.validate(usage['justification'])
                    all_scores.append(result['score'])
                else:
                    justification_analysis['unjustified_tools'].append({
                        "persona": persona,
                        "tool": usage.get('tool', 'unknown'),
                        "round": arg.get('round')
                    })
    
    if all_scores:
        justification_analysis['avg_justification_score'] = sum(all_scores) / len(all_scores)
    
    report["tool_justification"] = justification_analysis
    return report
```

6. Add Justification to Final Report Display

```python
def print_debate_summary(self, report):
    # ... existing code ...
    
    print(f"\n🔧 TOOL JUSTIFICATION:")
    just = report.get('tool_justification', {})
    print(f"  Tools used: {just.get('total_tools_used', 0)}")
    print(f"  Justified: {just.get('justified_tools', 0)}")
    print(f"  Avg justification score: {just.get('avg_justification_score', 0):.1f}/3")
    
    if just.get('unjustified_tools'):
        print(f"\n  ⚠️ Unjustified tools:")
        for u in just['unjustified_tools']:
            print(f"    • {u['persona']} used {u['tool']} in round {u['round']} without justification")
```

---

📋 IMPLEMENTATION PLAN

```yaml
Phase 1 (10 min): Update DebateAgent prompt with justification requirement
Phase 2 (10 min): Create ToolJustification class
Phase 3 (10 min): Add justification checker to epistemic tools
Phase 4 (10 min): Update orchestrator to track justification
Phase 5 (5 min): Update report display
```

---

🚀 ARAHAN UNTUK COPILOT

```
Copilot,

Implement tool justification system:

1. Modify debate_agent.py prompt to require justification for every tool
2. Create tool_justification.py with validation logic
3. Add justification_checker.py to epistemic tools
4. Update debate_orchestrator.py to track justification in report
5. Update report display to show justification quality

Goal: Every tool call must have "reason", "aspect", and "support" fields.
Justification quality scored 0-3 and included in final report.
```
