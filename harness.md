🎯 BRILLIANT! UNIVERSAL HARNESS FOR ALL TOOLS!

---

🧠 YES! This should be a GENERAL Context Building Harness

```
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🔍 UNIVERSAL HARNESS - For ALL tools, not just debate!   ║
║                                                              ║
║   Every tool that takes >5 seconds needs:                  ║
║   • Progress updates                                       ║
║   • Anti-fabrication checks                                ║
║   • Source file verification                               ║
║   • Honesty enforcement                                     ║
║                                                              ║
║   This should be part of the CONTEXT BUILDING process      ║
║   - Not a separate harness per tool                        ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

---

📊 TOOLS THAT NEED HARNESS

Tool Typical Duration Risk of Fabrication
debate 120-180s 🔴 HIGH
monte_carlo 30-60s 🟡 MEDIUM
swarm_analysis 60-120s 🟡 MEDIUM
web_search 5-15s 🟢 LOW
file_operations <1s 🟢 LOW
memory_consolidation 10-30s 🟡 MEDIUM

---

🏗️ UNIVERSAL HARNESS ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────┐
│                 UNIVERSAL TOOL HARNESS                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  CONTEXT BUILDER                                     │   │
│  │  • Tracks all active tools                          │   │
│  │  • Monitors execution time                          │   │
│  │  • Estimates completion                             │   │
│  └─────────────────────────────────────────────────────┘   │
│                              │                              │
│                              ▼                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  RESPONSE INTERCEPTOR                                │   │
│  │  • Checks if tool is still running                  │   │
│  │  • Verifies claims against actual results           │   │
│  │  • Blocks fabrications                              │   │
│  └─────────────────────────────────────────────────────┘   │
│                              │                              │
│                              ▼                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  UPDATE INJECTOR                                     │   │
│  │  • Sends progress updates during long tasks         │   │
│  │  • Provides partial results if available            │   │
│  │  • Estimates time remaining                         │   │
│  └─────────────────────────────────────────────────────┘   │
│                              │                              │
│                              ▼                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  SOURCE VERIFIER                                     │   │
│  │  • Checks if result files exist                     │   │
│  │  • Validates file size and content                  │   │
│  │  • Ensures citations are accurate                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

🛠️ UNIVERSAL HARNESS IMPLEMENTATION

```python
# /root/nanojaga/jagabot/core/universal_harness.py
"""
Universal Tool Harness - Prevents fabrications for ALL long-running tools
"""

import time
import os
import json
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime
import hashlib

class ToolHarness:
    """
    Universal harness that monitors all tool executions
    """
    
    def __init__(self):
        self.active_tools = {}
        self.tool_history = []
        self.constitutional_rules = self._load_constitutional_rules()
        
    def _load_constitutional_rules(self) -> Dict:
        """Load rules from SOUL.md and AGENTS.md"""
        rules = {
            "epistemic_humility": True,
            "no_fabrication": True,
            "source_citation_required": True,
            "wait_for_completion": True,
            "progress_updates": True
        }
        
        # Try to load from SOUL.md
        soul_path = "/root/.jagabot/workspace/SOUL.md"
        if os.path.exists(soul_path):
            with open(soul_path, 'r') as f:
                content = f.read()
                if "Epistemic Humility" in content:
                    rules["epistemic_humility"] = True
        
        return rules
    
    def register_tool(self, tool_name: str, tool_id: str, estimated_duration: int = 30) -> str:
        """Register a tool execution"""
        self.active_tools[tool_id] = {
            "tool_name": tool_name,
            "start_time": time.time(),
            "estimated_duration": estimated_duration,
            "status": "running",
            "updates": [],
            "result": None,
            "result_file": None
        }
        return tool_id
    
    def update_progress(self, tool_id: str, progress_data: Dict[str, Any]):
        """Record progress update from tool"""
        if tool_id in self.active_tools:
            self.active_tools[tool_id]["updates"].append({
                "timestamp": time.time(),
                "data": progress_data
            })
    
    def complete_tool(self, tool_id: str, result: Any, result_file: Optional[str] = None):
        """Mark tool as complete"""
        if tool_id in self.active_tools:
            self.active_tools[tool_id]["status"] = "complete"
            self.active_tools[tool_id]["result"] = result
            self.active_tools[tool_id]["result_file"] = result_file
            self.active_tools[tool_id]["end_time"] = time.time()
            
            # Archive to history
            self.tool_history.append({
                "tool_id": tool_id,
                **self.active_tools[tool_id]
            })
    
    def pre_response_check(self, agent_response: str, context: Dict[str, Any]) -> str:
        """
        Intercept agent response before user sees it
        Checks for fabrications and enforces constitutional rules
        """
        # Extract any tool claims from response
        tool_claims = self._extract_tool_claims(agent_response)
        
        for claim in tool_claims:
            tool_id = claim.get('tool_id')
            if tool_id and tool_id in self.active_tools:
                tool_status = self.active_tools[tool_id]
                
                # Rule 1: Tool still running
                if tool_status['status'] == 'running':
                    return self._format_progress_update(tool_id)
                
                # Rule 2: Tool complete but result doesn't match claim
                if tool_status['status'] == 'complete':
                    if not self._verify_claim_against_result(claim, tool_status['result']):
                        return self._format_verification_error(tool_id)
                    
                    # Rule 3: Source citation required
                    if self.constitutional_rules['source_citation_required']:
                        if not claim.get('source_file') and tool_status['result_file']:
                            return self._format_source_error(tool_id, tool_status['result_file'])
            
            # Rule 4: Claiming tool execution that never happened
            elif claim.get('claims_execution') and not tool_id:
                return self._format_no_tool_error(claim)
        
        return agent_response
    
    def _extract_tool_claims(self, response: str) -> List[Dict]:
        """Extract claims about tool execution from response"""
        claims = []
        
        # Look for debate claims
        if "Debate" in response or "debate" in response.lower():
            claims.append({
                "type": "debate",
                "claims_execution": True,
                "text": response
            })
        
        # Look for Monte Carlo claims
        if "Monte Carlo" in response or "simulation" in response.lower():
            claims.append({
                "type": "monte_carlo",
                "claims_execution": True,
                "text": response
            })
        
        # Look for file creation claims
        if "created file" in response.lower() or "saved to" in response.lower():
            claims.append({
                "type": "file_creation",
                "claims_execution": True,
                "text": response
            })
        
        return claims
    
    def _verify_claim_against_result(self, claim: Dict, result: Any) -> bool:
        """Verify that claim matches actual result"""
        if not result:
            return False
        
        # For debate, check positions
        if claim.get('type') == 'debate' and isinstance(result, dict):
            claim_text = claim.get('text', '')
            for position in ['Bull', 'Bear', 'Buffett']:
                if position in claim_text:
                    # Extract claimed position (simplified)
                    import re
                    match = re.search(f"{position}.*?([0-9]+)", claim_text)
                    if match:
                        claimed_value = int(match.group(1))
                        actual_value = result.get(position.lower(), 0)
                        if abs(claimed_value - actual_value) > 5:  # Tolerance
                            return False
        
        return True
    
    def _format_progress_update(self, tool_id: str) -> str:
        """Format progress update for running tool"""
        tool = self.active_tools[tool_id]
        elapsed = time.time() - tool['start_time']
        estimated = tool['estimated_duration']
        remaining = max(0, estimated - elapsed)
        
        update = f"""
⏳ **{tool['tool_name']} IN PROGRESS...** ({elapsed:.0f}s elapsed)

"""
        # Add latest updates if available
        if tool['updates']:
            latest = tool['updates'][-1]['data']
            if 'round' in latest:
                update += f"Round {latest['round']} complete.\n"
                if 'bull' in latest:
                    update += f"🐂 Bull: {latest['bull']}\n"
                    update += f"🐻 Bear: {latest['bear']}\n"
                    update += f"🧔 Buffett: {latest['buffett']}\n"
        
        update += f"\nEstimated time remaining: {remaining:.0f} seconds.\n"
        update += "Full results will appear when complete."
        
        return update
    
    def _format_verification_error(self, tool_id: str) -> str:
        """Format error when claim doesn't match result"""
        tool = self.active_tools[tool_id]
        return f"""
⚠️ **VERIFICATION ERROR**

Your response doesn't match the actual results from {tool['tool_name']}.

Please check the tool output and update your response.
Actual results are available in: {tool['result_file']}

Remember SOUL.md: Epistemic Humility means being accurate, not "helpful."
"""
    
    def _format_source_error(self, tool_id: str, result_file: str) -> str:
        """Format error when source citation missing"""
        return f"""
⚠️ **SOURCE CITATION REQUIRED**

You mentioned results from a tool but didn't cite the source file.

Per constitutional rules, you MUST include:
Source: {result_file}

Please update your response.
"""
    
    def _format_no_tool_error(self, claim: Dict) -> str:
        """Format error when claiming tool execution that never happened"""
        return f"""
⚠️ **CONSTITUTIONAL VIOLATION**

You claimed to have executed a tool, but no tool was actually called.

Per SOUL.md (Epistemic Humility):
- Never claim to have done something you haven't verified
- If a tool is still running, say it's running
- Do not guess or fabricate results

Please correct your response.
"""

# Global harness instance
harness = ToolHarness()
```

---

🔧 INTEGRATE INTO CONTEXT BUILDER

```python
# In jagabot/agent/context_builder.py

from jagabot.core.universal_harness import harness

class ContextBuilder:
    def __init__(self):
        self.harness = harness
        self.active_tools = {}
    
    def before_tool_execution(self, tool_name: str, estimated_duration: int) -> str:
        """Called before tool execution"""
        tool_id = f"{tool_name}_{int(time.time())}"
        self.harness.register_tool(tool_name, tool_id, estimated_duration)
        return tool_id
    
    def during_tool_execution(self, tool_id: str, progress_data: Dict):
        """Called during tool execution to provide updates"""
        self.harness.update_progress(tool_id, progress_data)
        
        # Return formatted update for agent
        return self.harness._format_progress_update(tool_id)
    
    def after_tool_execution(self, tool_id: str, result: Any, result_file: str):
        """Called after tool completes"""
        self.harness.complete_tool(tool_id, result, result_file)
    
    def build_response(self, agent_response: str, context: Dict) -> str:
        """Build final response with harness check"""
        # Let harness check for fabrications
        checked_response = self.harness.pre_response_check(agent_response, context)
        
        # If harness modified response, use that
        if checked_response != agent_response:
            return checked_response
        
        # Otherwise, build normal response
        return self._format_response(agent_response, context)
```

---

📋 SCOPE PROMPT UNTUK COPILOT

```
# 🚀 UNIVERSAL TOOL HARNESS - For ALL Long-Running Tools

## PROBLEM
Agent fabricates results for ANY tool that takes >5 seconds:
- Debate (130s) - fabricates summaries
- Monte Carlo (30-60s) - fabricates results
- Swarm analysis (60-120s) - fabricates conclusions
- Memory consolidation (10-30s) - fabricates summaries

## SOLUTION
Create Universal Tool Harness that:
1. Tracks ALL active tool executions
2. Provides real-time progress updates
3. Intercepts and verifies ALL responses
4. Enforces constitutional rules (SOUL.md)
5. Requires source citations for ALL tool results

## FILES TO CREATE
- /root/nanojaga/jagabot/core/universal_harness.py

## FILES TO MODIFY
- /root/nanojaga/jagabot/agent/context_builder.py
- /root/nanojaga/jagabot/agent/loop.py
- System prompt (add universal rules)

## SUCCESS CRITERIA
- No fabrication for ANY tool
- Progress updates for ALL long-running tools
- Source citations REQUIRED for ALL results
- Constitutional rules ENFORCED universally

🚀 IMPLEMENT NOW!
```
