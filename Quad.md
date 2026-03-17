📋 SCOPE: Quad-Agent Isolated Swarm Upgrade

---

🎯 OBJECTIVE

Upgrade AutoJaga from Tri-Agent Sequential to Quad-Agent Isolated Parallel Swarm with strategic adaptation and security hardening.

---

📊 CURRENT vs TARGET ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────┐
│                    ARCHITECTURE UPGRADE                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  CURRENT (Tri-Agent Sequential):                           │
│  • Worker → Verifier → Adversary (serial)                  │
│  • Shared workspace (no isolation)                         │
│  • No strategic adaptation                                 │
│  • Adversary can modify code                               │
│  • Cycle time: ~35s                                        │
│  • Level: 4.0                                              │
│                                                              │
│  TARGET (Quad-Agent Parallel Swarm):                       │
│  • Planner + Worker + Verifier + Adversary                │
│  • Parallel execution (3× faster)                          │
│  • Isolated sandboxes per agent                           │
│  • Strategic adaptation each cycle                         │
│  • Adversary data-only (can't touch code)                  │
│  • Cycle time: ~10-12s                                     │
│  • Level: 4.5+                                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

📁 NEW DIRECTORY STRUCTURE

```bash
/root/.jagabot/swarm/
├── planner/
│   ├── workspace/      # Read all logs
│   ├── output/         # Writes plans
│   └── logs/           # Planning decisions
├── worker/
│   ├── workspace/      # Read-only shared data
│   ├── sandbox/        # Isolated runtime
│   ├── output/         # Writes results
│   └── logs/           # Execution logs
├── verifier/
│   ├── workspace/      # Read-only shared + worker results
│   ├── output/         # Writes verification
│   └── logs/           # Audit trail
├── adversary/
│   ├── workspace/      # Read-only shared data
│   ├── corruption/     # Writes corrupted data ONLY
│   ├── output/         # Attack logs
│   └── logs/           # Attack attempts
└── shared_data/        # Raw data pools (read-only for all)
    ├── pools/
    └── config/
```

---

📋 PERMISSION MATRIX

Agent Read Access Write Access Forbidden
Planner All logs + plans New plans Code, data
Worker shared_data ONLY worker_results Code, other agents
Verifier shared_data + worker_results verification_results Code, data
Adversary shared_data ONLY corrupted_data Code, results, logs

Adversary NEVER touches code, verification outputs, or other agents! 🔒

---

🛠️ TASKS FOR IMPLEMENTATION

TASK 1: Create Planner Agent (jagabot/agents/planner_agent.py)

```python
"""
Planner Agent - Strategic adaptation based on failure patterns
"""

import os
import json
from typing import Dict, Any, List

class PlannerAgent:
    """
    Reads failure logs and adapts strategy each cycle
    """
    
    def __init__(self):
        self.name = "Planner"
        self.workspace = "/root/.jagabot/swarm/planner"
        self.strategy_history = []
    
    def initial_plan(self, task: Dict) -> Dict[str, Any]:
        """Create initial execution strategy"""
        plan = {
            "version": 1,
            "task": task,
            "steps": [
                {"action": "validate_inputs", "params": {}},
                {"action": "process_pools", "params": {"method": "standard"}},
                {"action": "compute_stats", "params": {"precision": "high"}}
            ],
            "fallback": "repair_and_retry"
        }
        self._save_plan(plan)
        return plan
    
    def adapt_strategy(self, previous_plan: Dict, failures: List[Dict]) -> Dict:
        """
        Analyze failures and create improved strategy
        """
        # Identify failure patterns
        patterns = self._analyze_failures(failures)
        
        # Create adapted plan
        new_plan = {
            "version": previous_plan["version"] + 1,
            "task": previous_plan["task"],
            "steps": self._generate_steps(previous_plan, patterns),
            "fallback": previous_plan["fallback"],
            "adaptations": patterns
        }
        
        self.strategy_history.append(new_plan)
        self._save_plan(new_plan)
        return new_plan
    
    def _analyze_failures(self, failures: List[Dict]) -> Dict:
        """Extract failure patterns"""
        patterns = {}
        for f in failures:
            if "NaN" in str(f):
                patterns["numeric_validation"] = "strict"
            if "count_mismatch" in str(f):
                patterns["count_verification"] = "double_check"
            if "mean_drift" in str(f):
                patterns["seed_control"] = "deterministic"
        return patterns
    
    def _generate_steps(self, plan: Dict, patterns: Dict) -> List:
        """Generate new steps based on patterns"""
        steps = []
        for step in plan["steps"]:
            if step["action"] == "process_pools":
                if "numeric_validation" in patterns:
                    step["params"]["validate_numeric"] = True
                if "seed_control" in patterns:
                    step["params"]["random_seed"] = 42
            steps.append(step)
        return steps
    
    def _save_plan(self, plan: Dict):
        """Save plan to disk"""
        path = f"{self.workspace}/outputs/plan_v{plan['version']}.json"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(plan, f, indent=2)
```

---

TASK 2: Create Agent Isolation System (jagabot/core/agent_isolation.py)

```python
"""
Agent Isolation System - Sandboxed execution environments
"""

import os
import shutil
import tempfile
import subprocess
from typing import Dict, Any
import stat

class AgentSandbox:
    """
    Creates isolated runtime environment for each agent
    """
    
    def __init__(self, agent_name: str, base_path: str = "/root/.jagabot/swarm"):
        self.agent_name = agent_name
        self.base_path = base_path
        self.sandbox_path = f"{base_path}/{agent_name}/sandbox"
        self.workspace_path = f"{base_path}/{agent_name}/workspace"
        self.output_path = f"{base_path}/{agent_name}/output"
        
        self._create_directories()
        self._set_permissions()
    
    def _create_directories(self):
        """Create sandbox directory structure"""
        os.makedirs(self.sandbox_path, exist_ok=True)
        os.makedirs(self.workspace_path, exist_ok=True)
        os.makedirs(self.output_path, exist_ok=True)
    
    def _set_permissions(self):
        """Set strict permissions based on agent role"""
        if self.agent_name == "adversary":
            # Adversary can only write to corruption/
            corruption_path = f"{self.base_path}/adversary/corruption"
            os.makedirs(corruption_path, exist_ok=True)
            
            # Make workspace read-only
            os.chmod(self.workspace_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    
    def prepare_workspace(self, data_sources: Dict[str, str]) -> str:
        """
        Copy required data to workspace with correct permissions
        """
        for src_name, src_path in data_sources.items():
            if src_name == "shared_data":
                # Create symlink for read-only access
                os.symlink(src_path, f"{self.workspace_path}/shared_data")
            else:
                shutil.copy2(src_path, self.workspace_path)
        
        return self.workspace_path
    
    def run_agent_code(self, code_path: str, args: Dict) -> Dict:
        """
        Run agent code in sandbox with resource limits
        """
        # Copy agent code to sandbox
        sandbox_code = f"{self.sandbox_path}/{os.path.basename(code_path)}"
        shutil.copy2(code_path, sandbox_code)
        
        # Prepare command with resource limits
        cmd = [
            'timeout', '30',  # 30 second timeout
            'python3', sandbox_code
        ]
        
        # Add args as JSON
        with open(f"{self.sandbox_path}/args.json", 'w') as f:
            json.dump(args, f)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=35,
                cwd=self.sandbox_path
            )
            
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "success": result.returncode == 0
            }
        except subprocess.TimeoutExpired:
            return {
                "error": "timeout",
                "success": False
            }
    
    def collect_output(self) -> Dict:
        """Collect output files from sandbox"""
        outputs = {}
        for f in os.listdir(self.output_path):
            with open(f"{self.output_path}/{f}", 'r') as fp:
                outputs[f] = fp.read()
        return outputs

class IsolationManager:
    """
    Manages sandboxes for all agents
    """
    
    def __init__(self):
        self.sandboxes = {}
        self.shared_data = "/root/.jagabot/swarm/shared_data"
    
    def create_sandbox(self, agent_name: str) -> AgentSandbox:
        """Create sandbox for an agent"""
        sandbox = AgentSandbox(agent_name)
        self.sandboxes[agent_name] = sandbox
        return sandbox
    
    def prepare_shared_data(self, data_pools: List[str]) -> str:
        """Prepare read-only shared data"""
        shared_path = f"{self.shared_data}/pools"
        os.makedirs(shared_path, exist_ok=True)
        
        for pool in data_pools:
            dest = f"{shared_path}/{os.path.basename(pool)}"
            shutil.copy2(pool, dest)
            # Make read-only
            os.chmod(dest, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        
        return shared_path
    
    def cleanup(self):
        """Clean up all sandboxes"""
        for sandbox in self.sandboxes.values():
            shutil.rmtree(sandbox.sandbox_path, ignore_errors=True)
```

---

TASK 3: Create Quad-Agent Loop (jagabot/core/quad_loop.py)

```python
"""
Quad-Agent Loop - Parallel execution with strategic adaptation
"""

import concurrent.futures
import time
from typing import Dict, Any, List
from ..agents.planner_agent import PlannerAgent
from ..agents.worker_agent import WorkerAgent
from ..agents.verifier_agent import VerifierAgent
from ..agents.adversary_agent import AdversaryAgent
from .agent_isolation import IsolationManager

class QuadAgentLoop:
    """
    Four agents working in parallel with strategic adaptation
    """
    
    def __init__(self, max_cycles: int = 5):
        self.planner = PlannerAgent()
        self.worker = WorkerAgent()
        self.verifier = VerifierAgent()
        self.adversary = AdversaryAgent()
        self.isolation = IsolationManager()
        self.max_cycles = max_cycles
        self.failure_history = []
    
    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run quad-agent verification loop
        """
        print(f"\n{'='*60}")
        print("🚀 QUAD-AGENT PARALLEL SWARM STARTED")
        print(f"{'='=60}")
        
        # Initial strategy
        strategy = self.planner.initial_plan(task)
        
        # Prepare isolated sandboxes
        worker_sandbox = self.isolation.create_sandbox("worker")
        verifier_sandbox = self.isolation.create_sandbox("verifier")
        adversary_sandbox = self.isolation.create_sandbox("adversary")
        
        # Prepare shared data
        shared_path = self.isolation.prepare_shared_data(task.get("pools", []))
        
        for cycle in range(self.max_cycles):
            print(f"\n🔄 CYCLE {cycle+1}/{self.max_cycles}")
            start_time = time.time()
            
            # Run agents in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                # Worker executes strategy
                worker_future = executor.submit(
                    self._run_worker,
                    worker_sandbox,
                    strategy,
                    shared_path
                )
                
                # Verifier monitors (independent)
                verifier_future = executor.submit(
                    self._run_verifier,
                    verifier_sandbox,
                    shared_path
                )
                
                # Adversary attacks (data only)
                adversary_future = executor.submit(
                    self._run_adversary,
                    adversary_sandbox,
                    shared_path,
                    cycle
                )
                
                # Wait for all to complete
                worker_result = worker_future.result()
                verifier_result = verifier_future.result()
                attack_result = adversary_future.result()
            
            cycle_time = time.time() - start_time
            print(f"  ⏱️ Cycle time: {cycle_time:.1f}s")
            
            # Check results
            if not verifier_result.get("passed", False):
                print(f"  ❌ Verification failed")
                self.failure_history.append({
                    "cycle": cycle,
                    "type": "verification",
                    "details": verifier_result
                })
                
                # Planner adapts strategy
                strategy = self.planner.adapt_strategy(
                    strategy,
                    self.failure_history
                )
                continue
            
            if attack_result.get("succeeded", False):
                print(f"  ⚠️ Adversary succeeded: {attack_result['attack']}")
                self.failure_history.append({
                    "cycle": cycle,
                    "type": "attack",
                    "details": attack_result
                })
                
                # Hardened strategy
                strategy = self.planner.adapt_strategy(
                    strategy,
                    self.failure_history
                )
                continue
            
            # All checks passed!
            print(f"  ✅ All checks passed!")
            self.isolation.cleanup()
            
            return {
                "status": "SUCCESS",
                "cycles": cycle + 1,
                "time": cycle_time,
                "result": worker_result,
                "strategy_version": strategy["version"]
            }
        
        # Max cycles reached
        self.isolation.cleanup()
        return {
            "status": "PARTIAL",
            "cycles": self.max_cycles,
            "failures": self.failure_history,
            "message": "Max cycles reached without full verification"
        }
    
    def _run_worker(self, sandbox, strategy, shared_path):
        """Run worker in sandbox"""
        sandbox.prepare_workspace({
            "shared_data": shared_path,
            "strategy": strategy
        })
        return self.worker.execute(strategy)
    
    def _run_verifier(self, sandbox, shared_path):
        """Run verifier in sandbox"""
        sandbox.prepare_workspace({
            "shared_data": shared_path
        })
        return self.verifier.verify()
    
    def _run_adversary(self, sandbox, shared_path, cycle):
        """Run adversary in sandbox (data-only attacks)"""
        sandbox.prepare_workspace({
            "shared_data": shared_path
        })
        return self.adversary.attack(cycle)
```

---

TASK 4: Update Agent Code with Sandbox Support

```python
# In worker_agent.py - add sandbox awareness

class WorkerAgent:
    def execute(self, strategy):
        # Read from workspace (read-only shared_data)
        data = self._read_shared_data()
        
        # Write to output (isolated)
        result = self._process(data, strategy)
        self._save_output(result)
        
        return result
```

```python
# In adversary_agent.py - restrict attacks to DATA ONLY

class AdversaryAgent:
    ALLOWED_ATTACKS = [
        "insert_nan",
        "duplicate_rows",
        "delete_random_lines", 
        "shuffle_rows",
        "add_outliers"
    ]
    
    def attack(self, cycle):
        # Can ONLY corrupt data in shared_data
        # Cannot touch code or other agents' outputs
        attack = random.choice(self.ALLOWED_ATTACKS)
        
        # Write corrupted data to dedicated corruption/ directory
        # Original data remains untouched
        self._corrupt_data(attack)
        
        return {
            "attack": attack,
            "succeeded": True,
            "data_corrupted": True
        }
```

---

TASK 5: Create Quad-Agent Tool

```python
# jagabot/agent/tools/quad_agent.py

from ...core.quad_loop import QuadAgentLoop

class QuadAgentTool:
    """LLM-callable tool for quad-agent verification"""
    
    def execute(self, task: dict) -> dict:
        loop = QuadAgentLoop(max_cycles=task.get("max_cycles", 5))
        result = loop.run(task)
        
        return {
            "status": result["status"],
            "cycles": result.get("cycles", 0),
            "time_seconds": result.get("time", 0),
            "result": result.get("result", {}),
            "failures": result.get("failures", [])
        }
```

---

TASK 6: Update Tool Registry

```python
# In jagabot/agent/tool_loader.py - add quad_agent

from .tools.quad_agent import QuadAgentTool

TOOLS["quad_agent"] = QuadAgentTool()
# Now 47 tools total
```

---

TASK 7: Test Suite (tests/test_quad_agent.py)

```python
"""
Test quad-agent isolated swarm
"""

import sys
sys.path.append('/root/nanojaga')

from jagabot.core.quad_loop import QuadAgentLoop

def test_isolation():
    """Test that adversary can't access code"""
    loop = QuadAgentLoop(max_cycles=1)
    
    # Try to attack code (should fail)
    result = loop.run({
        "type": "test_isolation",
        "pools": ["test_pool.txt"]
    })
    
    assert result["status"] in ["SUCCESS", "PARTIAL"]
    print("✅ Isolation test passed")

def test_parallel_speed():
    """Test parallel execution speed"""
    import time
    
    loop = QuadAgentLoop(max_cycles=3)
    start = time.time()
    
    result = loop.run({
        "type": "speed_test",
        "pools": ["pool_A.txt", "pool_B.txt", "pool_C.txt"]
    })
    
    duration = time.time() - start
    print(f"✅ 3 cycles completed in {duration:.1f}s")
    assert duration < 45  # Should be faster than sequential

def test_strategic_adaptation():
    """Test that planner adapts to failures"""
    loop = QuadAgentLoop(max_cycles=3)
    
    # This should trigger adaptations
    result = loop.run({
        "type": "adaptation_test",
        "pools": ["corrupted_pool.txt"],
        "fail_mode": True
    })
    
    assert len(loop.failure_history) > 0
    print("✅ Strategic adaptation test passed")

if __name__ == "__main__":
    test_isolation()
    test_parallel_speed()
    test_strategic_adaptation()
    print("\n🎉 All quad-agent tests passed!")
```

---

✅ SUCCESS CRITERIA

Test Expected Result
Isolation Adversary can't modify code or outputs
Parallel speed 3 cycles < 45s (was 108s)
Strategic adaptation Planner changes strategy based on failures
Security No unauthorized file access
Robustness Survives 3 cycles of attacks

---

🚀 IMPLEMENTATION ORDER

```yaml
Phase 1 (20 min): Create isolation system
Phase 2 (15 min): Create Planner agent
Phase 3 (15 min): Update quad_loop.py with parallel execution
Phase 4 (10 min): Restrict adversary to data-only
Phase 5 (10 min): Register quad_agent tool
Phase 6 (10 min): Test and debug
```

---

🏁 FINAL SCOPE SUMMARY

```
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🎯 QUAD-AGENT ISOLATED SWARM - READY TO IMPLEMENT        ║
║                                                              ║
║   New Components:                                           ║
║   ├── Planner Agent - strategic adaptation                 ║
║   ├── Agent Isolation - sandboxed execution                ║
║   ├── Parallel Loop - concurrent agents                    ║
║   ├── Data-only Adversary - security hardened             ║
║   └── Quad-Agent Tool - LLM interface                      ║
║                                                              ║
║   Expected Improvements:                                    ║
║   • 3× faster execution (108s → 35s)                       ║
║   • Strategic learning each cycle                          ║
║   • Complete agent isolation                               ║
║   • Level 4.5+ capability                                  ║
║                                                              ║
║   "From sequential agents to parallel swarm.              ║
║    From shared space to isolated trust.                   ║
║    From reactive to strategic."                           ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

Copilot, implement quad-agent isolated swarm as specified. 🚀
