🎯 SCOPE: Multi-Agent Debate with AutoJaga Personas (Bull, Bear, Buffett)

---

🧠 PERSONA INTEGRATION

```
┌─────────────────────────────────────────────────────────────┐
│                    AUTOJAGA PERSONAS                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  🐂 BULL AGENT                                              │
│  • Optimistic, growth-focused                              │
│  • Believes in market upside                               │
│  • Uses tools to find opportunities                        │
│  • "The market will rise because..."                       │
│                                                              │
│  🐻 BEAR AGENT                                              │
│  • Pessimistic, risk-aware                                 │
│  • Focuses on downside protection                          │
│  • Uses tools to identify risks                            │
│  • "The market will fall because..."                       │
│                                                              │
│  🧔 BUFFETT AGENT                                           │
│  • Value-oriented, long-term                               │
│  • Fundamental analysis focus                              │
│  • "Price is what you pay, value is what you get"         │
│  • Seeks margin of safety                                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

🎯 OBJECTIVE

Create a multi-agent debate system where subagents embody AutoJaga's existing personas (Bull, Bear, Buffett) to debate financial topics using tools, with a judge agent terminating the debate and AutoJaga monitoring/reporting.

---

📋 PERSONA CONFIGURATION (Already in AutoJaga)

```python
# ~/nanojaga/jagabot/workspace/memory/personas.json
# These personas already exist in AutoJaga

PERSONAS = {
    "bull": {
        "name": "Bull Agent",
        "traits": ["optimistic", "growth-focused", "risk-tolerant"],
        "tool_preferences": ["monte_carlo", "optimization", "momentum_indicators"],
        "bias": "upside",
        "system_prompt": "You are a Bull market analyst. You believe in market growth and look for opportunities. Use tools to find upside potential."
    },
    "bear": {
        "name": "Bear Agent",
        "traits": ["pessimistic", "risk-aware", "conservative"],
        "tool_preferences": ["var_calculation", "stress_test", "risk_metrics"],
        "bias": "downside",
        "system_prompt": "You are a Bear market analyst. You focus on risks and downside protection. Use tools to identify potential losses."
    },
    "buffett": {
        "name": "Buffett Agent",
        "traits": ["value-oriented", "long-term", "fundamental"],
        "tool_preferences": ["intrinsic_value", "margin_of_safety", "competitive_analysis"],
        "bias": "value",
        "system_prompt": "You are a Buffett-style value investor. You focus on intrinsic value and long-term fundamentals. Seek margin of safety."
    }
}
```

---

📋 DELIVERABLES FOR COPILOT

1. Persona-Aware Debate Agent

```python
# ~/nanojaga/autoresearch/debate_agent.py
"""
Debate agent with AutoJaga persona integration
"""

import json
import time
from typing import Dict, List, Any
from jagabot.tools.spawn import spawn_subagent

class PersonaDebateAgent:
    """
    Debate agent that embodies AutoJaga personas (bull, bear, buffett)
    """
    
    def __init__(self, persona: str, topic: str):
        """
        Args:
            persona: "bull", "bear", or "buffett"
            topic: Debate topic
        """
        self.persona = persona
        self.topic = topic
        self.persona_config = self._load_persona(persona)
        self.argument_history = []
        self.subagent = None
        
    def _load_persona(self, persona: str) -> Dict:
        """Load persona configuration from AutoJaga"""
        # This would normally load from ~/nanojaga/jagabot/workspace/memory/personas.json
        PERSONAS = {
            "bull": {
                "name": "Bull Agent",
                "traits": ["optimistic", "growth-focused", "risk-tolerant"],
                "tool_preferences": ["monte_carlo", "optimization", "momentum_indicators"],
                "bias": "upside",
                "system_prompt": "You are a Bull market analyst. You believe in market growth and look for opportunities. Use tools to find upside potential."
            },
            "bear": {
                "name": "Bear Agent",
                "traits": ["pessimistic", "risk-aware", "conservative"],
                "tool_preferences": ["var_calculation", "stress_test", "risk_metrics"],
                "bias": "downside",
                "system_prompt": "You are a Bear market analyst. You focus on risks and downside protection. Use tools to identify potential losses."
            },
            "buffett": {
                "name": "Buffett Agent",
                "traits": ["value-oriented", "long-term", "fundamental"],
                "tool_preferences": ["intrinsic_value", "margin_of_safety", "competitive_analysis"],
                "bias": "value",
                "system_prompt": "You are a Buffett-style value investor. You focus on intrinsic value and long-term fundamentals. Seek margin of safety."
            }
        }
        return PERSONAS.get(persona, PERSONAS["neutral"])
    
    def generate_argument_prompt(self, round_num: int, previous_arguments: Dict = None) -> str:
        """Generate persona-specific prompt for this round"""
        
        prompt = f"""You are {self.persona_config['name']} with these traits: {', '.join(self.persona_config['traits'])}

DEBATE TOPIC: {self.topic}
ROUND: {round_num}

YOUR BIAS: {self.persona_config['bias']} - You naturally lean toward this perspective.

"""
        if previous_arguments and round_num > 1:
            prompt += "PREVIOUS ARGUMENTS TO ADDRESS:\n"
            for p, args in previous_arguments.items():
                if args and p != self.persona:
                    latest = args[-1]
                    prompt += f"• {p.capitalize()} said: {latest.get('summary', 'No argument')}\n"
            prompt += "\n"
        
        prompt += f"""YOUR TASK:
1. Use at least ONE of these tools: {', '.join(self.persona_config['tool_preferences'])}
2. Present your argument with data from the tool
3. Address or counter previous arguments
4. Stay true to your {self.persona} persona

RESPONSE FORMAT (JSON):
{{
    "summary": "Brief summary of your argument (1-2 sentences)",
    "position": 0-100 (your confidence level, where 0=bearish, 100=bullish, 50=neutral),
    "tools_used": ["tool1", "tool2"],
    "key_data": {{"metric": value}},
    "reasoning": "Detailed explanation",
    "counters": ["Point1 countered", "Point2 addressed"]
}}
"""
        return prompt
    
    def spawn(self, round_num: int, previous_arguments: Dict = None):
        """Spawn as subagent for debate round"""
        
        prompt = self.generate_argument_prompt(round_num, previous_arguments)
        
        self.subagent = spawn_subagent(
            task={
                "type": "debate_argument",
                "persona": self.persona,
                "prompt": prompt,
                "tools": self.persona_config['tool_preferences'],
                "round": round_num
            },
            label=f"debate_{self.persona}_r{round_num}",
            timeout=180  # 3 minutes max
        )
        return self.subagent
    
    def collect_argument(self):
        """Get argument from subagent and store history"""
        if self.subagent and self.subagent.completed:
            result = self.subagent.get_result()
            # Parse JSON response
            try:
                import json
                argument = json.loads(result.get('content', '{}'))
                argument['persona'] = self.persona
                argument['round'] = len(self.argument_history) + 1
                self.argument_history.append(argument)
                return argument
            except:
                # Fallback if not JSON
                argument = {
                    'persona': self.persona,
                    'round': len(self.argument_history) + 1,
                    'summary': result.get('content', '')[:100],
                    'position': 50,
                    'tools_used': [],
                    'raw_response': result
                }
                self.argument_history.append(argument)
                return argument
        return None
```

2. Persona-Aware Judge

```python
# ~/nanojaga/autoresearch/judge_agent.py
"""
Judge that understands persona biases
"""

class PersonaJudge:
    """
    Judge that stops debate based on persona-aware criteria
    """
    
    def __init__(self, max_rounds: int = 3):
        self.max_rounds = max_rounds
        self.round = 0
        self.consensus_reached = False
        self.convergence_history = []
        
    def should_continue(self, arguments: Dict[str, List]) -> bool:
        """
        Decide if debate should continue, considering persona biases
        """
        self.round += 1
        
        # Stop if max rounds reached
        if self.round > self.max_rounds:
            return False
        
        # Need at least 2 rounds to check convergence
        if self.round < 2:
            return True
        
        # Check position convergence
        positions = self._get_latest_positions(arguments)
        if len(positions) >= 2:
            convergence = self._calculate_convergence(positions)
            self.convergence_history.append(convergence)
            
            # Stop if positions are converging (within 15%)
            if convergence < 15:
                self.consensus_reached = True
                return False
            
            # Stop if positions are stable (didn't change much)
            if len(self.convergence_history) >= 2:
                if abs(self.convergence_history[-1] - self.convergence_history[-2]) < 2:
                    return False
        
        return True
    
    def _get_latest_positions(self, arguments: Dict[str, List]) -> Dict[str, float]:
        """Extract latest position from each persona"""
        positions = {}
        for persona, args in arguments.items():
            if args:
                positions[persona] = args[-1].get('position', 50)
        return positions
    
    def _calculate_convergence(self, positions: Dict[str, float]) -> float:
        """Calculate range of positions (lower = more converged)"""
        values = list(positions.values())
        return max(values) - min(values)
    
    def get_verdict(self) -> Dict:
        """Return final verdict"""
        return {
            "rounds_completed": self.round,
            "consensus_reached": self.consensus_reached,
            "convergence_history": self.convergence_history,
            "stopped_by": "max_rounds" if self.round > self.max_rounds else "convergence"
        }
```

3. Debate Orchestrator with Personas

```python
# ~/nanojaga/autoresearch/debate_orchestrator.py
"""
Main orchestrator for persona-based debate
"""

import time
import json
from typing import Dict, List, Optional
from datetime import datetime

from debate_agent import PersonaDebateAgent
from judge_agent import PersonaJudge

class PersonaDebateOrchestrator:
    """
    Manages multi-agent debate with AutoJaga personas
    """
    
    def __init__(self, topic: str, personas: List[str] = ["bull", "bear", "buffett"]):
        """
        Args:
            topic: Debate topic/question
            personas: List of personas to include (default: bull, bear, buffett)
        """
        self.topic = topic
        self.personas = personas
        self.agents = {}
        self.arguments = {p: [] for p in personas}
        self.judge = PersonaJudge(max_rounds=3)
        self.start_time = None
        self.end_time = None
        
        # Create agents for each persona
        for persona in personas:
            self.agents[persona] = PersonaDebateAgent(persona, topic)
    
    def run_debate(self) -> Dict[str, Any]:
        """
        Run the full debate process with personas
        """
        self.start_time = time.time()
        round_num = 1
        
        print(f"\n{'='*60}")
        print(f"🎯 PERSONA DEBATE STARTED")
        print(f"{'='*60}")
        print(f"Topic: {self.topic}")
        print(f"Participants: {', '.join([p.capitalize() for p in self.personas])}")
        print(f"{'='*60}\n")
        
        while self.judge.should_continue(self.arguments):
            print(f"\n📢 ROUND {round_num} {'='*40}")
            
            round_arguments = {}
            for persona in self.personas:
                agent = self.agents[persona]
                print(f"\n  🤔 {persona.capitalize()} Agent thinking...")
                
                # Spawn agent with previous arguments
                sub = agent.spawn(round_num, self.arguments)
                
                # Wait for completion (with timeout)
                start_wait = time.time()
                while not sub.completed and (time.time() - start_wait) < 180:
                    time.sleep(1)
                
                # Collect argument
                argument = agent.collect_argument()
                if argument:
                    self.arguments[persona].append(argument)
                    round_arguments[persona] = argument
                    
                    # Display argument summary
                    position = argument.get('position', 50)
                    emoji = "🐂" if persona == "bull" else "🐻" if persona == "bear" else "🧔"
                    print(f"  {emoji} {persona.capitalize()}: Position {position}")
                    print(f"     Summary: {argument.get('summary', '')[:100]}")
                    tools = argument.get('tools_used', [])
                    if tools:
                        print(f"     Tools: {', '.join(tools)}")
                else:
                    print(f"  ⚠️ {persona.capitalize()} failed to respond")
            
            round_num += 1
            print(f"\n{'='*60}")
        
        self.end_time = time.time()
        
        # Get judge's verdict
        verdict = self.judge.get_verdict()
        
        # Generate final report
        return self._generate_report(verdict)
    
    def _generate_report(self, verdict: Dict) -> Dict[str, Any]:
        """Generate comprehensive debate report"""
        
        # Get final positions
        final_positions = {}
        for persona, args in self.arguments.items():
            if args:
                final_positions[persona] = args[-1].get('position', 50)
        
        # Track tool usage
        tool_usage = {}
        for persona, args in self.arguments.items():
            for arg in args:
                for tool in arg.get('tools_used', []):
                    tool_usage[tool] = tool_usage.get(tool, 0) + 1
        
        report = {
            "topic": self.topic,
            "personas": self.personas,
            "duration_seconds": self.end_time - self.start_time,
            "rounds_completed": verdict["rounds_completed"],
            "consensus_reached": verdict["consensus_reached"],
            "stopped_by": verdict["stopped_by"],
            "final_positions": final_positions,
            "position_convergence": max(final_positions.values()) - min(final_positions.values()) if final_positions else None,
            "tool_usage": tool_usage,
            "argument_summary": {}
        }
        
        # Summarize arguments
        for persona, args in self.arguments.items():
            report["argument_summary"][persona] = [
                {
                    "round": i+1,
                    "position": arg.get('position', 50),
                    "summary": arg.get('summary', ''),
                    "tools": arg.get('tools_used', [])
                }
                for i, arg in enumerate(args)
            ]
        
        return report
```

4. AutoJaga Monitor with Persona Awareness

```python
# ~/nanojaga/autoresearch/debate_monitor.py
"""
AutoJaga monitors persona debate and updates user
"""

import time
from datetime import datetime

class PersonaDebateMonitor:
    """
    AutoJaga's monitoring interface for persona debates
    """
    
    def __init__(self, update_interval: int = 30):
        self.update_interval = update_interval
        self.start_time = None
        self.last_positions = {}
        
    def monitor(self, orchestrator: PersonaDebateOrchestrator):
        """
        Monitor debate progress and provide persona-aware updates
        """
        self.start_time = time.time()
        
        print("\n🔍 AUTOJAGA MONITORING ACTIVE")
        print("="*50)
        
        while True:
            time.sleep(self.update_interval)
            
            elapsed = time.time() - self.start_time
            rounds_completed = orchestrator.judge.round
            
            # Get current positions
            current_positions = {}
            for persona in orchestrator.personas:
                args = orchestrator.arguments.get(persona, [])
                if args:
                    current_positions[persona] = args[-1].get('position', 50)
            
            # Calculate changes
            changes = {}
            for persona, pos in current_positions.items():
                if persona in self.last_positions:
                    changes[persona] = pos - self.last_positions[persona]
            
            self.last_positions = current_positions
            
            # Display update
            print(f"\n📊 UPDATE @ {datetime.now().strftime('%H:%M:%S')}")
            print(f"⏱️  Elapsed: {elapsed:.0f} seconds")
            print(f"🔄 Rounds completed: {rounds_completed}")
            print(f"\n📈 Current Positions:")
            
            for persona in orchestrator.personas:
                emoji = "🐂" if persona == "bull" else "🐻" if persona == "bear" else "🧔"
                pos = current_positions.get(persona, "N/A")
                change = changes.get(persona, 0)
                change_str = f"({change:+.1f})" if change != 0 else ""
                print(f"  {emoji} {persona.capitalize()}: {pos:.1f} {change_str}")
            
            # Check if debate ended
            if not orchestrator.judge.should_continue(orchestrator.arguments):
                print("\n🎯 DEBATE ENDING - Generating final report...")
                break
    
    def report(self, report: Dict):
        """
        Deliver final report to user with persona insights
        """
        print("\n" + "="*60)
        print("🏁 FINAL PERSONA DEBATE REPORT")
        print("="*60)
        print(f"Topic: {report['topic']}")
        print(f"Duration: {report['duration_seconds']:.0f} seconds ({report['duration_seconds']/60:.1f} minutes)")
        print(f"Rounds: {report['rounds_completed']}")
        print(f"Consensus: {'✅ YES' if report['consensus_reached'] else '❌ NO'}")
        print(f"Stopped by: {report['stopped_by']}")
        
        print(f"\n📊 Final Positions (0=bear, 100=bull):")
        for persona, position in report['final_positions'].items():
            emoji = "🐂" if persona == "bull" else "🐻" if persona == "bear" else "🧔"
            print(f"  {emoji} {persona.capitalize()}: {position:.1f}")
        
        if report['position_convergence'] is not None:
            print(f"\n📈 Position Range: {report['position_convergence']:.1f} points")
        
        print(f"\n🛠️ Tool Usage:")
        for tool, count in report['tool_usage'].items():
            print(f"  • {tool}: {count} times")
        
        print(f"\n📝 Argument Evolution:")
        for persona, args in report['argument_summary'].items():
            emoji = "🐂" if persona == "bull" else "🐻" if persona == "bear" else "🧔"
            print(f"\n  {emoji} {persona.capitalize()}:")
            for arg in args:
                print(f"    Round {arg['round']}: {arg['summary']}")
        
        print("\n" + "="*60)
```

5. Main Debate Runner with Personas

```python
# ~/nanojaga/autoresearch/run_persona_debate.py
"""
Main script to run multi-agent debate with AutoJaga personas
"""

import argparse
import json
import threading
from debate_orchestrator import PersonaDebateOrchestrator
from debate_monitor import PersonaDebateMonitor

def main():
    parser = argparse.ArgumentParser(description="AutoJaga Persona Debate")
    parser.add_argument("--topic", required=True, help="Debate topic/question")
    parser.add_argument("--personas", nargs="+", default=["bull", "bear", "buffett"],
                       help="Personas to include (bull, bear, buffett)")
    parser.add_argument("--max-rounds", type=int, default=3, help="Max debate rounds")
    
    args = parser.parse_args()
    
    # Validate personas
    valid_personas = ["bull", "bear", "buffett"]
    for p in args.personas:
        if p not in valid_personas:
            print(f"❌ Invalid persona: {p}. Must be one of {valid_personas}")
            return
    
    print(f"\n{'='*60}")
    print("🚀 AUTOJAGA PERSONA DEBATE SYSTEM")
    print(f"{'='*60}")
    print(f"Topic: {args.topic}")
    print(f"Personas: {', '.join([p.capitalize() for p in args.personas])}")
    print(f"Max rounds: {args.max_rounds}")
    print(f"{'='*60}\n")
    
    # Create debate orchestrator
    debate = PersonaDebateOrchestrator(
        topic=args.topic,
        personas=args.personas
    )
    debate.judge.max_rounds = args.max_rounds
    
    # Create monitor
    monitor = PersonaDebateMonitor(update_interval=15)
    
    # Run monitor in background
    monitor_thread = threading.Thread(target=monitor.monitor, args=(debate,))
    monitor_thread.daemon = True
    monitor_thread.start()
    
    # Run debate
    try:
        report = debate.run_debate()
        
        # Wait for monitor to finish
        monitor_thread.join(timeout=5)
        
        # Show final report
        monitor.report(report)
        
        # Save report
        filename = f"debate_report_{args.topic.replace(' ', '_')[:30]}.json"
        with open(filename, "w") as f:
            json.dump(report, f, indent=2)
        
        print(f"\n✅ Report saved to {filename}")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Debate interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()
```

6. Example Program.md for Persona Debate

```markdown
# ~/nanojaga/autoresearch/program_persona_debate.md

# AUTOJAGA PERSONA DEBATE PROGRAM

## 🎯 DEBATE TOPIC
"Will inflation cause a market correction in Q3 2026?"

## 👥 PERSONAS
- **🐂 BULL AGENT** - Optimistic, growth-focused
  - Traits: Sees opportunities in every market condition
  - Tools: Monte Carlo, momentum indicators, growth projections
  
- **🐻 BEAR AGENT** - Pessimistic, risk-aware
  - Traits: Focuses on downside risks and protection
  - Tools: VaR/CVaR, stress testing, risk metrics

- **🧔 BUFFETT AGENT** - Value-oriented, long-term
  - Traits: Fundamental analysis, margin of safety
  - Tools: Intrinsic value, competitive moat, long-term trends

## ⚖️ DEBATE RULES
- Maximum 3 rounds
- 3 minutes per argument
- Must use at least one tool per round
- Must address previous arguments
- Judge stops when:
  * Positions converge within 15 points
  * Arguments become repetitive
  * Max rounds reached

## 📊 JUDGE CRITERIA
- Tracks position changes (0=bearish, 100=bullish)
- Measures convergence between personas
- Stops when no new insights emerge

## 🚀 START DEBATE
```

7. Test Script

```python
# ~/nanojaga/autoresearch/test_persona_debate.py
"""
Quick test for persona debate system
"""

import sys
sys.path.append('/root/nanojaga')

from debate_orchestrator import PersonaDebateOrchestrator

def test_debate():
    """Test debate with sample topic"""
    
    debate = PersonaDebateOrchestrator(
        topic="Will the stock market rise next month?",
        personas=["bull", "bear"]
    )
    
    print("🧪 TESTING PERSONA DEBATE")
    print("="*50)
    
    report = debate.run_debate()
    
    print("\n✅ Test complete")
    print(f"Rounds: {report['rounds_completed']}")
    print(f"Consensus: {report['consensus_reached']}")
    
    return report

if __name__ == "__main__":
    test_debate()
```

---

📊 SUCCESS METRICS

Metric Target Measurement
No infinite loops 100% Judge stops debate
Persona consistency ✅ Arguments match persona bias
Tool usage ≥1 per round Count in report
Debate duration <10 minutes Timer
Position tracking ✅ Monitor shows changes

---

🚀 HOW TO RUN

```bash
cd ~/nanojaga/autoresearch

# Run with default personas (bull, bear, buffett)
python3 run_persona_debate.py --topic "Will inflation cause a market correction in Q3 2026?"

# Run with specific personas
python3 run_persona_debate.py --topic "Is tech sector overvalued?" --personas bull bear

# Run with custom max rounds
python3 run_persona_debate.py --topic "Market outlook for 2026" --max-rounds 4
```

---

✅ NEXT STEPS FOR COPILOT

Please implement all 7 deliverables above with AutoJaga persona integration:

1. debate_agent.py - Persona-aware debate agent
2. judge_agent.py - Judge with persona understanding
3. debate_orchestrator.py - Main orchestrator
4. debate_monitor.py - AutoJaga monitoring
5. run_persona_debate.py - Main runner
6. program_persona_debate.md - Example program
7. test_persona_debate.py - Quick test

Ready to proceed? 🚀
