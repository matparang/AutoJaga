🎯 ENHANCED BLUEPRINT: Debate Tool Library + Epistemic Tools

---

🏗️ THE "LIBRARY FIRST" STRATEGY

```
┌─────────────────────────────────────────────────────────────┐
│                 DEBATE TOOL LIBRARY (PHASE 2)               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  📊 SOCIO-ECONOMIC METRICS (NEW)                           │
│  ├── gini_calculator.py     - Wealth distribution         │
│  ├── gdp_calculator.py      - Economic output             │
│  ├── cpi_analyzer.py        - Inflation / purchasing power│
│  └── mobility_index.py      - Social mobility             │
│                                                              │
│  🔍 EPISTEMIC TOOLS (NEW)                                  │
│  ├── bias_detector.py       - Scans for loaded language   │
│  ├── evidence_requester.py  - Forces citations            │
│  ├── consistency_penalty.py - Prevents wild position swings│
│  └── logic_checker.py       - Detects circular reasoning  │
│                                                              │
│  📈 FINANCIAL TOOLS (EXISTING)                             │
│  ├── monte_carlo.py         - Simulations                 │
│  ├── var_calculation.py     - Risk metrics                │
│  └── portfolio_optimization.py - Allocation               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

🧠 EPISTEMIC TOOLS - Make Debates Smarter Without API Cost

---

1. Bias Detector Tool

```python
# ~/nanojaga/autoresearch/debate_tools/bias_detector.py
"""
Detects loaded language and bias in agent arguments
"""

import re
from typing import Dict, List, Any
from .base_tool import DebateTool

class BiasDetector(DebateTool):
    """
    Scans agent arguments for biased or loaded language
    Returns bias score and suggestions for neutral alternatives
    """
    
    LOADED_WORDS = {
        "clearly": 0.3,
        "obviously": 0.4,
        "everyone knows": 0.5,
        "without doubt": 0.4,
        "absolutely": 0.3,
        "totally": 0.2,
        "always": 0.4,
        "never": 0.4,
        "disastrous": 0.5,
        "perfect": 0.4,
        "flawless": 0.5,
        "catastrophic": 0.5,
        "unquestionably": 0.5,
        "undeniably": 0.4,
        "radical": 0.3,
        "extreme": 0.3,
        "common sense": 0.2,
        "obviously wrong": 0.5
    }
    
    CIRCULAR_PATTERNS = [
        r".*because.*is what it is.*",
        r".*the reason is because of the reason.*",
        r".*it is true because it is true.*",
        r".*they are that way because that's how they are.*"
    ]
    
    def __init__(self):
        super().__init__("bias_detector", "epistemic")
    
    def calculate(self, text: str, **kwargs) -> Dict[str, Any]:
        """
        Analyze text for bias and loaded language
        """
        text_lower = text.lower()
        
        # Detect loaded words
        loaded_words_found = []
        bias_score = 0.0
        
        for word, weight in self.LOADED_WORDS.items():
            if word in text_lower:
                count = text_lower.count(word)
                loaded_words_found.append({
                    "word": word,
                    "count": count,
                    "weight": weight,
                    "contribution": count * weight
                })
                bias_score += count * weight
        
        # Detect circular reasoning
        circular_matches = []
        for pattern in self.CIRCULAR_PATTERNS:
            if re.search(pattern, text_lower):
                circular_matches.append(pattern)
                bias_score += 0.5  # Heavy penalty for circular logic
        
        # Sentiment skew (simple ratio of positive/negative words)
        positive_words = ["good", "great", "excellent", "beneficial", "advantage"]
        negative_words = ["bad", "terrible", "harmful", "destructive", "dangerous"]
        
        pos_count = sum(text_lower.count(w) for w in positive_words)
        neg_count = sum(text_lower.count(w) for w in negative_words)
        
        if pos_count + neg_count > 0:
            sentiment_ratio = pos_count / (pos_count + neg_count)
            if sentiment_ratio > 0.8 or sentiment_ratio < 0.2:
                bias_score += 0.3  # Extreme sentiment bias
        
        # Generate suggestions
        suggestions = []
        if loaded_words_found:
            suggestions.append(f"Replace loaded words: {', '.join([w['word'] for w in loaded_words_found[:3]])}")
        if circular_matches:
            suggestions.append("Avoid circular reasoning. State evidence-based logic.")
        if bias_score > 2.0:
            suggestions.append("Argument appears highly biased. Consider more neutral language.")
        
        return {
            "bias_score": round(bias_score, 2),
            "bias_level": "low" if bias_score < 1 else "medium" if bias_score < 3 else "high",
            "loaded_words_found": loaded_words_found,
            "circular_reasoning_detected": len(circular_matches) > 0,
            "sentiment_ratio": round(sentiment_ratio, 2) if pos_count + neg_count > 0 else None,
            "suggestions": suggestions,
            "text_length": len(text),
            "word_count": len(text.split())
        }
```

---

2. Evidence Requester Tool

```python
# ~/nanojaga/autoresearch/debate_tools/evidence_requester.py
"""
Forces agents to provide evidence for position changes
"""

import re
from datetime import datetime
from typing import Dict, Any, List
from .base_tool import DebateTool

class EvidenceRequester(DebateTool):
    """
    Validates that position changes > threshold have supporting evidence
    """
    
    HISTORICAL_EVENTS = {
        "great_depression": 1929,
        "new_deal": 1933,
        "post_ww2_boom": 1945,
        "oil_crisis": 1973,
        "stagflation": 1970,
        "reagan_era": 1980,
        "dot_com_bubble": 2000,
        "2008_crisis": 2008,
        "covid_pandemic": 2020,
        "great_recession": 2008
    }
    
    def __init__(self):
        super().__init__("evidence_requester", "epistemic")
    
    def calculate(self, previous_position: float, new_position: float, 
                  argument: str, persona: str, **kwargs) -> Dict[str, Any]:
        """
        Check if position change is justified with evidence
        """
        position_change = abs(new_position - previous_position)
        
        # Extract potential evidence from argument
        found_evidence = []
        missing_evidence = []
        
        # Look for historical references
        for event, year in self.HISTORICAL_EVENTS.items():
            if event in argument.lower() or str(year) in argument:
                found_evidence.append({
                    "type": "historical",
                    "reference": event,
                    "year": year
                })
        
        # Look for data/citations
        if re.search(r'\d+%|\d+ percent', argument):
            found_evidence.append({"type": "statistical", "description": "Contains percentage data"})
        
        if re.search(r'data|study|research|according to|source', argument.lower()):
            found_evidence.append({"type": "citation", "description": "References external source"})
        
        if re.search(r'gini|coefficient|index|metric', argument.lower()):
            found_evidence.append({"type": "metric", "description": "References economic metric"})
        
        # Determine if evidence is sufficient
        if position_change > 30:
            required_evidence = 2
        elif position_change > 15:
            required_evidence = 1
        else:
            required_evidence = 0
        
        sufficient = len(found_evidence) >= required_evidence
        
        # Generate feedback if insufficient
        feedback = None
        if position_change > 0 and not sufficient:
            if position_change > 30:
                feedback = f"⚠️ Large position change ({position_change:.0f} points) requires at least 2 pieces of evidence. Found: {len(found_evidence)}."
            elif position_change > 15:
                feedback = f"⚠️ Position change ({position_change:.0f} points) requires at least 1 piece of evidence. Found: {len(found_evidence)}."
        
        return {
            "position_change": position_change,
            "change_magnitude": "small" if position_change < 10 else "medium" if position_change < 20 else "large",
            "found_evidence": found_evidence,
            "evidence_count": len(found_evidence),
            "evidence_sufficient": sufficient,
            "required_evidence_count": required_evidence,
            "feedback": feedback,
            "needs_revision": not sufficient and required_evidence > 0
        }
```

---

3. Consistency Penalty Tool

```python
# ~/nanojaga/autoresearch/debate_tools/consistency_penalty.py
"""
Prevents wild swings in agent positions
"""

from typing import Dict, Any, List
from datetime import datetime
from .base_tool import DebateTool

class ConsistencyPenalty(DebateTool):
    """
    Tracks position history and flags inconsistent swings
    """
    
    def __init__(self):
        super().__init__("consistency_penalty", "epistemic")
        self.position_history = {}  # persona -> list of (round, position)
    
    def calculate(self, persona: str, round_num: int, new_position: float, 
                  previous_positions: List[Dict] = None, **kwargs) -> Dict[str, Any]:
        """
        Check if new position is consistent with history
        """
        if persona not in self.position_history:
            self.position_history[persona] = []
        
        # Get history for this persona
        history = self.position_history[persona]
        
        if not history:
            # First position, no penalty
            self.position_history[persona].append((round_num, new_position))
            return {
                "consistent": True,
                "swing_detected": False,
                "penalty": 0,
                "message": "First position recorded"
            }
        
        # Calculate changes
        last_round, last_position = history[-1]
        rounds_gap = round_num - last_round
        position_change = abs(new_position - last_position)
        
        # Calculate average change if enough history
        avg_change = 0
        if len(history) >= 3:
            changes = [abs(history[i][1] - history[i-1][1]) for i in range(1, len(history))]
            avg_change = sum(changes) / len(changes)
        
        # Detect swings
        swing_threshold = avg_change * 2.5 if avg_change > 0 else 20
        swing_detected = position_change > swing_threshold
        
        # Calculate penalty
        penalty = 0
        if swing_detected:
            # Penalty proportional to how much over threshold
            excess = position_change - swing_threshold
            penalty = min(excess / 10, 1.0)  # Cap at 1.0
        
        # Store new position
        self.position_history[persona].append((round_num, new_position))
        
        # Keep only last 5 positions to prevent memory bloat
        if len(self.position_history[persona]) > 5:
            self.position_history[persona] = self.position_history[persona][-5:]
        
        return {
            "consistent": not swing_detected,
            "swing_detected": swing_detected,
            "position_change": round(position_change, 1),
            "average_change": round(avg_change, 1),
            "swing_threshold": round(swing_threshold, 1),
            "penalty": round(penalty, 2),
            "message": f"Swing detected!" if swing_detected else "Consistent with history",
            "history": [(r, p) for r, p in self.position_history[persona]]
        }
```

---

4. Logic Checker Tool

```python
# ~/nanojaga/autoresearch/debate_tools/logic_checker.py
"""
Detects logical fallacies in arguments
"""

import re
from typing import Dict, Any, List
from .base_tool import DebateTool

class LogicChecker(DebateTool):
    """
    Identifies common logical fallacies in debate arguments
    """
    
    FALLACY_PATTERNS = {
        "straw_man": [
            r"opponent.*says.*but actually.*",
            r"they want.*but that's not true",
            r"misrepresenting.*position"
        ],
        "ad_hominem": [
            r"you can't trust.*because.*is",
            r"opponent is .* (stupid|naive|biased|ignorant)",
            r"clearly doesn't understand"
        ],
        "false_dilemma": [
            r"either.*or.*no other",
            r"only two options",
            r"must choose between"
        ],
        "slippery_slope": [
            r"if.*then eventually",
            r"first.*then.*inevitably",
            r"will lead to"
        ],
        "appeal_to_authority": [
            r"because .* (expert|professor|economist) says",
            r"according to (studies|research)",
            r"as everyone knows"
        ],
        "circular_reasoning": [
            r"is true because.*is true",
            r"proves itself",
            r"by definition"
        ]
    }
    
    def __init__(self):
        super().__init__("logic_checker", "epistemic")
    
    def calculate(self, text: str, **kwargs) -> Dict[str, Any]:
        """
        Analyze argument for logical fallacies
        """
        text_lower = text.lower()
        
        fallacies_found = []
        for fallacy, patterns in self.FALLACY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    fallacies_found.append({
                        "fallacy": fallacy,
                        "pattern_matched": pattern,
                        "severity": self._get_severity(fallacy)
                    })
                    break  # Only count each fallacy once
        
        # Calculate logic score (0-100)
        base_score = 100
        deduction = sum(f["severity"] for f in fallacies_found) * 10
        logic_score = max(0, base_score - deduction)
        
        # Generate feedback
        feedback = []
        if fallacies_found:
            fallacy_names = [f["fallacy"].replace("_", " ") for f in fallacies_found]
            feedback.append(f"Logical fallacies detected: {', '.join(fallacy_names)}")
            
            for f in fallacies_found:
                if f["fallacy"] == "straw_man":
                    feedback.append("  • Straw man: Addressing a distorted version of opponent's argument")
                elif f["fallacy"] == "ad_hominem":
                    feedback.append("  • Ad hominem: Attacking the person, not the argument")
                elif f["fallacy"] == "false_dilemma":
                    feedback.append("  • False dilemma: Presenting limited options when more exist")
        
        return {
            "logic_score": logic_score,
            "logic_quality": "excellent" if logic_score > 90 else "good" if logic_score > 70 else "fair" if logic_score > 50 else "poor",
            "fallacies_found": fallacies_found,
            "fallacy_count": len(fallacies_found),
            "feedback": feedback,
            "argument_length": len(text),
            "recommendation": self._get_recommendation(fallacies_found)
        }
    
    def _get_severity(self, fallacy: str) -> float:
        """Return severity weight for fallacy"""
        severity_map = {
            "straw_man": 2,
            "ad_hominem": 3,
            "false_dilemma": 1.5,
            "slippery_slope": 2,
            "appeal_to_authority": 1,
            "circular_reasoning": 3
        }
        return severity_map.get(fallacy, 2)
    
    def _get_recommendation(self, fallacies: List) -> str:
        """Generate recommendation based on fallacies found"""
        if not fallacies:
            return "Argument is logically sound"
        
        fallacy_types = [f["fallacy"] for f in fallacies]
        
        if "ad_hominem" in fallacy_types:
            return "Focus on the argument, not the person making it"
        elif "straw_man" in fallacy_types:
            return "Address the actual position, not a distorted version"
        elif "false_dilemma" in fallacy_types:
            return "Consider that more than two options may exist"
        elif "slippery_slope" in fallacy_types:
            return "Provide evidence for each step of the chain, not just the first"
        else:
            return "Strengthen your argument with evidence and logic"
```

---

5. Updated Tool Registry

```python
# ~/nanojaga/autoresearch/debate_tools/__init__.py
"""
Enhanced tool registry with epistemic tools
"""

from .inequality_tools import GiniCalculator, SocialMobilityIndex, ExternalityAnalyzer
from .historical_tools import HistoricalRegimeAnalyzer, CrisisComparator
from .bias_detector import BiasDetector
from .evidence_requester import EvidenceRequester
from .consistency_penalty import ConsistencyPenalty
from .logic_checker import LogicChecker

# Registry of all available debate tools
DEBATE_TOOLS = {
    # Socio-economic metrics
    "gini_calculator": GiniCalculator(),
    "mobility_index": SocialMobilityIndex(),
    "externality_analyzer": ExternalityAnalyzer(),
    
    # Historical analysis
    "historical_regime": HistoricalRegimeAnalyzer(),
    "crisis_comparator": CrisisComparator(),
    
    # Epistemic tools (NEW)
    "bias_detector": BiasDetector(),
    "evidence_requester": EvidenceRequester(),
    "consistency_penalty": ConsistencyPenalty(),
    "logic_checker": LogicChecker()
}

def get_tool(tool_name: str):
    """Get a tool by name"""
    return DEBATE_TOOLS.get(tool_name)

def list_tools(category: str = None) -> List[str]:
    """List all tools, optionally filtered by category"""
    if category:
        return [name for name, tool in DEBATE_TOOLS.items() if tool.category == category]
    return list(DEBATE_TOOLS.keys())

def get_tool_descriptions() -> Dict[str, str]:
    """Get descriptions of all tools for agent prompts"""
    return {name: tool.get_description() for name, tool in DEBATE_TOOLS.items()}
```

---

🛤️ UPDATED DEVELOPMENT ROADMAP

Phase Goal Tools Complexity
Phase 1 Static personas + Basic finance tools Monte Carlo, VaR, Portfolio Low
Phase 2 (NOW) Socio-economic metrics Gini, GDP, CPI, Mobility Medium
Phase 3 (NEW) Epistemic tools Bias Detector, Evidence Requester, Consistency Penalty, Logic Checker Medium
Phase 4 Structured feedback Agents review each other's tool outputs Medium
Phase 5 Self-correction Agents suggest which tool they need next High

---

🚀 IMPLEMENTATION ORDER

```yaml
Week 1 (Current): Phase 2 - Socio-economic metrics
  - GiniCalculator
  - SocialMobilityIndex
  - HistoricalRegimeAnalyzer

Week 2: Phase 3 - Epistemic tools
  - BiasDetector
  - EvidenceRequester  
  - ConsistencyPenalty
  - LogicChecker

Week 3: Integration
  - Connect tools to debate system
  - Add tool usage to argument prompts
  - Test with simple debates

Week 4: Refinement
  - Adjust thresholds based on testing
  - Add more historical data
  - Document tool usage patterns
```

---

🧪 TESTING THE EPISTEMIC TOOLS

```python
# ~/nanojaga/autoresearch/test_epistemic_tools.py
"""
Test script for epistemic tools
"""

import sys
sys.path.append('/root/nanojaga')

from debate_tools import get_tool

def test_bias_detector():
    print("\n🔍 Testing Bias Detector")
    tool = get_tool("bias_detector")
    
    biased_text = "It's clearly obvious that everyone knows the disastrous policy will obviously fail. The reason is because of the reason itself."
    result = tool.execute(biased_text)
    print(f"Bias score: {result['bias_score']}")
    print(f"Level: {result['bias_level']}")
    print(f"Loaded words: {result['loaded_words_found']}")
    print(f"Suggestions: {result['suggestions']}")

def test_evidence_requester():
    print("\n📚 Testing Evidence Requester")
    tool = get_tool("evidence_requester")
    
    # Large position change without evidence
    result = tool.execute(
        previous_position=50,
        new_position=90,
        argument="The economy will definitely improve!",
        persona="bull"
    )
    print(f"Position change: {result['position_change']}")
    print(f"Evidence sufficient: {result['evidence_sufficient']}")
    print(f"Feedback: {result['feedback']}")

def test_logic_checker():
    print("\n🧠 Testing Logic Checker")
    tool = get_tool("logic_checker")
    
    fallacy_text = "Either we accept free markets or we become communists. My opponent clearly doesn't understand economics, so their argument is invalid."
    result = tool.execute(fallacy_text)
    print(f"Logic score: {result['logic_score']}")
    print(f"Fallacies: {result['fallacies_found']}")
    print(f"Feedback: {result['feedback']}")

if __name__ == "__main__":
    test_bias_detector()
    test_evidence_requester()
    test_logic_checker()
```

---

✅ BENEFITS OF THIS APPROACH

Benefit Why It Matters
No API Cost Epistemic tools run locally, zero tokens
Forced Balance Bias detector prevents loaded language
Evidence-Based Evidence requester stops baseless swings
Logical Soundness Logic checker identifies fallacies
Gradual Learning AutoJaga learns by seeing which arguments pass checks

---


5. Update __init__.py and create test script

Start with BiasDetector - it's the most impactful for immediate debate quality improvement. 🚀	
