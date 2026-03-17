📋 SCOPE: Tri-Agent Verification Loop for AutoJaga

---

🎯 OBJECTIVE

Implement a Tri-Agent Verification Loop to elevate AutoJaga from Level 3.8 to true Level 4+ autonomy. This architecture uses three specialized agents that continuously check each other, eliminating hallucinations and ensuring robust task execution.

---

🔍 CURRENT STATE vs TARGET STATE

```
┌─────────────────────────────────────────────────────────────┐
│                    CURRENT ARCHITECTURE                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  🧠 AutoJaga (Single Agent)                                 │
│  ├── Executes task                                          │
│  ├── Self-verifies (passive)                               │
│  └── No active testing                                      │
│                                                              │
│  ⚠️ Limitations:                                            │
│  • Can hallucinate data                                     │
│  • No independent verification                             │
│  • No robustness testing                                   │
│  • Manual repair needed                                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    TARGET ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  👷 WORKER AGENT                                            │
│  ├── Executes tasks                                         │
│  ├── Creates files/datasets                                 │
│  └── Produces reports                                       │
│                                                              │
│  🔍 VERIFIER AGENT                                          │
│  ├── IGNORES worker output                                  │
│  ├── Recomputes from RAW files                              │
│  └── Detects mismatches                                     │
│                                                              │
│  👾 ADVERSARY AGENT                                         │
│  ├── Intentionally breaks things                           │
│  ├── Deletes/corrupts files                                │
│  └── Creates edge cases                                     │
│                                                              │
│  🔄 REPAIR LOOP                                             │
│  ├── Worker fixes based on feedback                         │
│  ├── Verifier rechecks                                      │
│  ├── Adversary retests                                      │
│  └── Loop until robust                                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

📁 FILES TO CREATE

```bash
/root/nanojaga/jagabot/agents/
├── worker_agent.py          # Task executor
├── verifier_agent.py        # Independent recomputation
└── adversary_agent.py       # Active breaker

/root/nanojaga/jagabot/core/
└── tri_agent_loop.py        # Main control loop

/root/nanojaga/tests/
└── test_tri_agent.py        # Unit tests
```

---

📋 TASK 1: Worker Agent (jagabot/agents/worker_agent.py)

```python
"""
Worker Agent - Executes tasks and creates artifacts
"""

import os
import json
from datetime import datetime
from typing import Dict, Any

class WorkerAgent:
    """
    Does the actual work: creates files, computes stats, generates reports
    """
    
    def __init__(self):
        self.name = "Worker"
        self.workspace = "/root/.jagabot/workspace"
    
    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the given task
        Returns: {
            "status": "success/failure",
            "artifacts": {...},
            "report": "...",
            "files_created": [...]
        }
        """
        # Implementation will vary by task type
        pass
    
    def _save_intermediates(self, data: Any, name: str):
        """Save intermediate files for verifier"""
        path = f"{self.workspace}/intermediates/{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        return path
```

---

📋 TASK 2: Verifier Agent (jagabot/agents/verifier_agent.py)

```python
"""
Verifier Agent - Independently recomputes everything from raw files
NEVER trusts worker output
"""

import os
import statistics
from typing import Dict, Any, List

class VerifierAgent:
    """
    Recomputes statistics directly from source files
    Independent verification - no trust
    """
    
    def __init__(self):
        self.name = "Verifier"
        self.workspace = "/root/.jagabot/workspace"
    
    def verify(self, task: Dict[str, Any], worker_claims: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify worker's claims by recomputing from files
        
        Returns: {
            "passed": bool,
            "mismatches": List[Dict],
            "actual_stats": Dict,
            "files_checked": List[str]
        }
        """
        # 1. Identify all source files
        source_files = self._find_source_files(task)
        
        # 2. Read ALL data from files (ignore worker's claims)
        raw_data = self._read_all_files(source_files)
        
        # 3. Recompute statistics from scratch
        recomputed = self._compute_stats(raw_data)
        
        # 4. Compare with worker's claims
        mismatches = self._find_mismatches(worker_claims, recomputed)
        
        return {
            "passed": len(mismatches) == 0,
            "mismatches": mismatches,
            "actual_stats": recomputed,
            "files_checked": source_files
        }
    
    def _find_source_files(self, task: Dict) -> List[str]:
        """Find all files that should contain source data"""
        # Implementation
        pass
    
    def _read_all_files(self, files: List[str]) -> Dict:
        """Read and parse all source files"""
        data = {}
        for f in files:
            if os.path.exists(f):
                with open(f, 'r') as fp:
                    data[f] = fp.readlines()
        return data
    
    def _compute_stats(self, data: Dict) -> Dict:
        """Recompute statistics from raw data"""
        # Extract all numbers
        all_numbers = []
        for lines in data.values():
            for line in lines:
                try:
                    all_numbers.append(int(line.strip()))
                except:
                    pass
        
        if not all_numbers:
            return {"error": "No valid numbers found"}
        
        return {
            "count": len(all_numbers),
            "mean": statistics.mean(all_numbers),
            "median": statistics.median(all_numbers),
            "stdev": statistics.stdev(all_numbers) if len(all_numbers) > 1 else 0,
            "min": min(all_numbers),
            "max": max(all_numbers),
            "divisible_by_7": [n for n in all_numbers if n % 7 == 0]
        }
    
    def _find_mismatches(self, claimed: Dict, actual: Dict) -> List:
        """Find discrepancies between claimed and actual"""
        mismatches = []
        for key, actual_val in actual.items():
            if key in claimed and abs(claimed[key] - actual_val) > 0.01:
                mismatches.append({
                    "metric": key,
                    "claimed": claimed[key],
                    "actual": actual_val
                })
        return mismatches
```

---

📋 TASK 3: Adversary Agent (jagabot/agents/adversary_agent.py)

```python
"""
Adversary Agent - Intentionally breaks things to test robustness
"""

import os
import random
import shutil

class AdversaryAgent:
    """
    Actively tries to break the system
    Tests if worker can recover from failures
    """
    
    def __init__(self):
        self.name = "Adversary"
        self.workspace = "/root/.jagabot/workspace"
        self.attack_history = []
    
    def inject(self, iteration: int) -> Dict[str, Any]:
        """
        Inject a random failure
        Returns: {
            "attack": str,
            "success": bool,
            "details": str,
            "iteration": int
        }
        """
        attacks = [
            self._delete_random_file,
            self._corrupt_random_line,
            self._insert_invalid_data,
            self._duplicate_entries,
            self._rename_files,
            self._change_permissions
        ]
        
        attack = random.choice(attacks)
        result = attack()
        
        self.attack_history.append({
            "iteration": iteration,
            "attack": attack.__name__,
            "result": result
        })
        
        return {
            "attack": attack.__name__,
            "success": result.get("success", False),
            "details": result,
            "iteration": iteration
        }
    
    def _delete_random_file(self) -> Dict:
        """Delete a random file in workspace"""
        files = [f for f in os.listdir(self.workspace) if f.endswith('.txt')]
        if not files:
            return {"success": False, "reason": "No files to delete"}
        
        target = random.choice(files)
        os.remove(os.path.join(self.workspace, target))
        
        return {
            "success": True,
            "action": "deleted",
            "target": target
        }
    
    def _corrupt_random_line(self) -> Dict:
        """Replace a random line with 'ERROR'"""
        files = [f for f in os.listdir(self.workspace) if f.endswith('.txt')]
        if not files:
            return {"success": False, "reason": "No files to corrupt"}
        
        target = random.choice(files)
        path = os.path.join(self.workspace, target)
        
        with open(path, 'r') as f:
            lines = f.readlines()
        
        if not lines:
            return {"success": False, "reason": "Empty file"}
        
        line_num = random.randint(0, len(lines)-1)
        original = lines[line_num]
        lines[line_num] = "ERROR\n"
        
        with open(path, 'w') as f:
            f.writelines(lines)
        
        return {
            "success": True,
            "action": "corrupted",
            "target": target,
            "line": line_num,
            "original": original.strip()
        }
    
    def _insert_invalid_data(self) -> Dict:
        """Insert NaN or invalid number"""
        files = [f for f in os.listdir(self.workspace) if f.endswith('.txt')]
        if not files:
            return {"success": False}
        
        target = random.choice(files)
        path = os.path.join(self.workspace, target)
        
        with open(path, 'a') as f:
            f.write("NaN\n")
        
        return {
            "success": True,
            "action": "inserted NaN",
            "target": target
        }
    
    def _duplicate_entries(self) -> Dict:
        """Duplicate some entries"""
        files = [f for f in os.listdir(self.workspace) if f.endswith('.txt')]
        if not files:
            return {"success": False}
        
        target = random.choice(files)
        path = os.path.join(self.workspace, target)
        
        with open(path, 'r') as f:
            lines = f.readlines()
        
        if len(lines) < 2:
            return {"success": False}
        
        # Duplicate a random line
        line_num = random.randint(0, len(lines)-1)
        lines.insert(line_num, lines[line_num])
        
        with open(path, 'w') as f:
            f.writelines(lines)
        
        return {
            "success": True,
            "action": "duplicated",
            "target": target,
            "line": line_num
        }
```

---

📋 TASK 4: Tri-Agent Loop (jagabot/core/tri_agent_loop.py)

```python
"""
Tri-Agent Verification Loop - Main control logic
"""

import time
from typing import Dict, Any
from ..agents.worker_agent import WorkerAgent
from ..agents.verifier_agent import VerifierAgent
from ..agents.adversary_agent import AdversaryAgent
from ..core.auditor import auditor
from ..core.tool_harness import harness

class TriAgentLoop:
    """
    Orchestrates the three agents in a verification loop
    Worker → Verifier → Adversary → Repair → Repeat
    """
    
    def __init__(self, max_iterations: int = 5):
        self.worker = WorkerAgent()
        self.verifier = VerifierAgent()
        self.adversary = AdversaryAgent()
        self.max_iterations = max_iterations
        self.cycle_log = []
    
    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a task with full tri-agent verification
        
        Returns: {
            "status": "SUCCESS/FAILURE/PARTIAL",
            "result": {...},
            "cycles": int,
            "robustness": str,
            "log": [...]
        }
        """
        print(f"\n{'='*60}")
        print("🚀 TRI-AGENT VERIFICATION LOOP STARTED")
        print(f"{'='*60}")
        
        for cycle in range(self.max_iterations):
            print(f"\n🔄 CYCLE {cycle+1}/{self.max_iterations}")
            cycle_log = {"cycle": cycle+1, "events": []}
            
            # 1. Worker executes
            print("  👷 Worker: executing task...")
            worker_result = self.worker.execute(task)
            cycle_log["worker"] = worker_result
            
            # 2. Verifier checks (independent)
            print("  🔍 Verifier: recomputing from files...")
            verification = self.verifier.verify(task, worker_result)
            cycle_log["verification"] = verification
            
            if not verification["passed"]:
                print(f"  ❌ Verification failed: {len(verification['mismatches'])} mismatches")
                print("  🔧 Worker must fix in next cycle")
                
                # Log to auditor
                auditor.audit_log.append({
                    "cycle": cycle+1,
                    "type": "verification_failure",
                    "mismatches": verification["mismatches"]
                })
                
                # Continue to next cycle (worker will fix)
                continue
            
            print(f"  ✅ Verification passed")
            
            # 3. Adversary attacks
            print("  👾 Adversary: attempting to break...")
            attack = self.adversary.inject(cycle)
            cycle_log["adversary"] = attack
            
            if attack["success"]:
                print(f"  ⚠️ Attack succeeded: {attack['attack']}")
                print(f"     {attack['details']}")
                print("  🔧 Worker must repair in next cycle")
                
                # Log attack
                auditor.audit_log.append({
                    "cycle": cycle+1,
                    "type": "attack",
                    "attack": attack
                })
                
                continue
            else:
                print(f"  ✅ Attack failed: system robust")
                
                # All checks passed - SUCCESS
                self.cycle_log.append(cycle_log)
                
                # Final audit
                auditor.audit_log.append({
                    "cycle": cycle+1,
                    "type": "success",
                    "robustness": "verified"
                })
                
                return {
                    "status": "SUCCESS",
                    "result": worker_result,
                    "cycles": cycle+1,
                    "robustness": "verified",
                    "log": self.cycle_log
                }
        
        # Max iterations reached without full success
        return {
            "status": "PARTIAL",
            "message": f"Max cycles ({self.max_iterations}) reached",
            "cycles": self.max_iterations,
            "log": self.cycle_log
        }
```

---

📋 TASK 5: Integration with Existing Systems

```python
# In jagabot/agent/loop.py - modify main processing

from ..core.tri_agent_loop import TriAgentLoop

def _process_message(self, message):
    """Process message with tri-agent verification for complex tasks"""
    
    # Check if task is complex enough for tri-agent
    if self._requires_tri_agent(message):
        loop = TriAgentLoop(max_iterations=5)
        result = loop.execute_task({
            "type": "complex",
            "instruction": message
        })
        return self._format_response(result)
    
    # Simple tasks use existing flow
    return self._process_simple(message)
```

---

📋 TASK 6: Test Suite (tests/test_tri_agent.py)

```python
"""
Unit tests for tri-agent verification loop
"""

import sys
sys.path.append('/root/nanojaga')

from jagabot.core.tri_agent_loop import TriAgentLoop

def test_worker():
    """Test worker agent independently"""
    from jagabot.agents.worker_agent import WorkerAgent
    worker = WorkerAgent()
    result = worker.execute({"type": "test", "data": "create 50 numbers"})
    assert result["status"] == "success"
    print("✅ Worker test passed")

def test_verifier():
    """Test verifier agent independently"""
    from jagabot.agents.verifier_agent import VerifierAgent
    verifier = VerifierAgent()
    # Test with known data
    result = verifier.verify({"type": "test"}, {"mean": 100})
    assert isinstance(result, dict)
    print("✅ Verifier test passed")

def test_adversary():
    """Test adversary agent independently"""
    from jagabot.agents.adversary_agent import AdversaryAgent
    adversary = AdversaryAgent()
    attack = adversary.inject(0)
    assert "attack" in attack
    print("✅ Adversary test passed")

def test_tri_agent_loop():
    """Test full tri-agent loop"""
    loop = TriAgentLoop(max_iterations=3)
    result = loop.execute_task({
        "type": "test_pools",
        "instruction": "Create 3 pools of 50 numbers, compute stats, verify"
    })
    assert result["status"] in ["SUCCESS", "PARTIAL"]
    print(f"✅ Tri-agent loop test passed: {result['status']}")

if __name__ == "__main__":
    test_worker()
    test_verifier()
    test_adversary()
    test_tri_agent_loop()
    print("\n🎉 All tests passed!")
```

---

📋 TASK 7: Configuration Updates

```json
// Add to /root/.jagabot/config.json
{
  "tri_agent": {
    "enabled": true,
    "max_iterations": 5,
    "adversary_attacks": ["delete", "corrupt", "invalid", "duplicate"],
    "verification_level": "strict"
  }
}
```

---

✅ SUCCESS CRITERIA

Test Expected Result
Worker creates files Files exist with correct data
Verifier catches mismatches Detects any discrepancy
Adversary breaks things Successfully injects failures
Worker repairs Fixes after attack
Loop terminates Returns SUCCESS or PARTIAL
Audit log Complete history of all cycles

---

🚀 IMPLEMENTATION ORDER

```yaml
Phase 1 (20 min): Create agent files (worker, verifier, adversary)
Phase 2 (15 min): Implement tri-agent loop
Phase 3 (10 min): Write tests
Phase 4 (10 min): Integrate with existing systems
Phase 5 (5 min): Test and debug
```

---

🏁 SCOPE SUMMARY

```
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🎯 TRI-AGENT VERIFICATION LOOP - SCOPE COMPLETE          ║
║                                                              ║
║   Deliverables:                                             ║
║   ├── worker_agent.py                                      ║
║   ├── verifier_agent.py                                    ║
║   ├── adversary_agent.py                                   ║
║   ├── tri_agent_loop.py                                    ║
║   ├── test_tri_agent.py                                    ║
║   └── config updates                                        ║
║                                                              ║
║   Timeline: 1 hour                                         ║
║   Level target: 4.2+                                        ║
║                                                              ║
║   "Three agents, one truth: independent verification."    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

Copilot, implement the tri-agent verification loop as specified. 🚀
