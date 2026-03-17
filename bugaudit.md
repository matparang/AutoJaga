🎯 SCOPE: Investigate & Fix Debate Tool Wiring

---

📋 SITUATION

AutoJaga cannot run persona debates despite:

· Debate system files exist (/root/nanojaga/autoresearch/)
· Personas defined (Bull/Bear/Buffett)
· Fact library exists (socio_economic_facts.json)
· Error: "Maaf, terdapat masalah dengan alat yang diperlukan untuk menjalankan debat"

---

🔍 PROBLEM STATEMENT

Debate tool is not properly wired into AutoJaga's tool registry. AutoJaga cannot access/execute debate functionality even though the underlying code exists.

---

📂 LOCATIONS TO INVESTIGATE

```
/root/nanojaga/
├── autoresearch/
│   ├── debate_agent.py
│   ├── debate_orchestrator.py
│   ├── debate_tools/
│   ├── fact_retriever.py
│   └── socio_economic_facts.json
│
├── jagabot/
│   ├── tools/
│   │   ├── __init__.py          # Tool registry
│   │   └── [debate_tool?]       # Should exist but doesn't?
│   └── agent/
│       └── loop.py               # Tool loading logic
│
└── .jagabot/
    └── config.json                # Tool configuration
```

---

🧠 SUSPECTED ROOT CAUSES

# Hypothesis Likelihood
1 Debate tool not registered in __init__.py 🔴 High
2 PYTHONPATH missing autoresearch directory 🟡 Medium
3 Debate tool function signature mismatch 🟡 Medium
4 Missing dependencies 🟢 Low
5 Permission issues 🟢 Low

---

📋 TASKS FOR COPILOT

TASK 1: AUDIT TOOL REGISTRY

```bash
# Check if debate tool is registered
cat /root/nanojaga/jagabot/tools/__init__.py | grep -A10 -i "debate"

# List all available tools
python3 -c "
import sys
sys.path.append('/root/nanojaga')
from jagabot.tools import get_all_tools
tools = get_all_tools()
print('Available tools:')
for t in tools:
    print(f'  • {t}')
print(f'\\nTotal: {len(tools)} tools')
"
```

TASK 2: CHECK PYTHONPATH

```python
# Test if autoresearch is importable
python3 -c "
import sys
sys.path.append('/root/nanojaga')
try:
    from autoresearch.debate_orchestrator import PersonaDebateOrchestrator
    print('✅ autoresearch importable')
except ImportError as e:
    print(f'❌ Import failed: {e}')
"
```

TASK 3: CREATE/REGISTER DEBATE TOOL

```python
# /root/nanojaga/jagabot/tools/debate_tool.py
"""
Debate tool for AutoJaga - runs persona debates
"""

import sys
sys.path.append('/root/nanojaga')

from autoresearch.debate_orchestrator import PersonaDebateOrchestrator

class DebateTool:
    """Run persona debates with Bull/Bear/Buffett"""
    
    def execute(self, topic: str, personas: list = None, max_rounds: int = 3):
        """
        Execute a persona debate
        
        Args:
            topic: Debate topic/question
            personas: List of personas (default: bull, bear, buffett)
            max_rounds: Maximum debate rounds
        
        Returns:
            Debate report dictionary
        """
        if personas is None:
            personas = ["bull", "bear", "buffett"]
        
        try:
            debate = PersonaDebateOrchestrator(
                topic=topic,
                personas=personas
            )
            debate.judge.max_rounds = max_rounds
            
            report = debate.run_debate()
            
            # Format for user-friendly output
            return self._format_report(report)
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "message": "Debate failed to run"
            }
    
    def _format_report(self, report: dict) -> str:
        """Format debate report for user"""
        output = f"\n{'='*60}\n"
        output += f"🎯 DEBATE: {report['topic']}\n"
        output += f"{'='*60}\n\n"
        
        output += "📊 FINAL POSITIONS:\n"
        for persona, position in report.get('final_positions', {}).items():
            emoji = "🐂" if persona == "bull" else "🐻" if persona == "bear" else "🧔"
            output += f"  {emoji} {persona.capitalize()}: {position:.1f}\n"
        
        output += f"\n🔄 Rounds completed: {report.get('rounds_completed', 0)}\n"
        output += f"✅ Consensus: {'YES' if report.get('consensus_reached') else 'NO'}\n"
        
        if report.get('tool_usage'):
            output += f"\n🛠️ Tools used: {sum(report['tool_usage'].values())} calls\n"
        
        if report.get('model_usage'):
            cost = report['model_usage'].get('total_cost', 0)
            output += f"💰 Cost: ${cost:.6f}\n"
        
        return output

# Create singleton instance
debate_tool = DebateTool()
```

TASK 4: REGISTER TOOL IN init.py

```python
# Add to /root/nanojaga/jagabot/tools/__init__.py

from .debate_tool import debate_tool

# Add to TOOLS dictionary
TOOLS['run_debate'] = debate_tool.execute
# or
TOOLS['debate'] = debate_tool
```

TASK 5: UPDATE CONFIG (if needed)

```json
// In /root/.jagabot/config.json, ensure tools include debate
{
  "tools": [
    "read_file",
    "write_file",
    "edit_file", 
    "list_dir",
    "shell",
    "spawn",
    "debate",  // ← ADD THIS
    // ... other tools
  ]
}
```

TASK 6: TEST DEBATE TOOL

```python
# test_debate_tool.py
"""
Test the newly registered debate tool
"""

import sys
sys.path.append('/root/nanojaga')

from jagabot.tools import get_tool

def test_debate():
    print("🔍 TESTING DEBATE TOOL")
    print("="*60)
    
    # Get debate tool
    debate = get_tool('debate') or get_tool('run_debate')
    
    if not debate:
        print("❌ Debate tool not found in registry")
        return
    
    print("✅ Debate tool found")
    
    # Run test debate
    result = debate(
        topic="Should governments implement a universal basic income?",
        max_rounds=2  # Short test
    )
    
    print(result)

if __name__ == "__main__":
    test_debate()
```

TASK 7: VERIFY WITH AUTOJAGA

```python
# After fixes, AutoJaga should be able to run:
from jagabot.tools import get_tool

debate = get_tool('debate')
result = debate("Should we tax the rich more?")
print(result)
```

---

✅ SUCCESS CRITERIA

Step Success Looks Like
TASK 1 Clear if debate tool is registered
TASK 2 autoresearch imports without error
TASK 3 debate_tool.py created
TASK 4 Tool registered in init.py
TASK 5 Config updated (if needed)
TASK 6 Test script runs without errors
TASK 7 AutoJaga can run debates via NLP

---

🚀 IMPLEMENTATION ORDER

```yaml
Phase 1: Audit (TASK 1-2) - 5 min
Phase 2: Create/Register (TASK 3-5) - 10 min
Phase 3: Test (TASK 6) - 5 min
Phase 4: Verify (TASK 7) - 5 min
```

---

🏁 READY TO IMPLEMENT

Copilot, investigate and fix debate tool wiring as specified. 🚀
