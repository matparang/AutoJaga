📋 SCOPE: Implementing Autoresearch Framework for AutoJaga

---

🎯 OBJECTIVE

Integrate Andrej Karpathy's autoresearch framework into AutoJaga to enable autonomous overnight experimentation and optimization of financial tools.

---

📂 REFERENCE LOCATION

```
Repository: ~/nanojaga/autoresearch
Original: https://github.com/karpathy/autoresearch
```

---

🔍 PROBLEM STATEMENT

AutoJaga currently requires manual tuning of financial tools (Monte Carlo, risk metrics, portfolio optimization). We need an autonomous system that can:

· Run overnight experiments without human intervention
· Systematically test variations of financial algorithms
· Track and compare results
· Keep improvements that work, revert those that don't
· Log all experiments for analysis

---

🏗️ AUTORESEARCH CORE ARCHITECTURE (Reference)

```
┌─────────────────────────────────────────────────────────────┐
│                    AUTORESEARCH STRUCTURE                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  📄 program.md (Human Edits)                                │
│  ├── Research objectives                                    │
│  ├── Experiment parameters                                  │
│  └── Constraints                                            │
│                                                              │
│         ↓ (Agent reads)                                     │
│                                                              │
│  🤖 AI AGENT                                                │
│  ├── Reads program.md                                       │
│  ├── Modifies train.py                                      │
│  ├── Runs experiment (5 min fixed)                         │
│  ├── Evaluates result (val_bpb metric)                     │
│  └── Keeps/reverts changes                                  │
│                                                              │
│         ↓ (Edits & runs)                                    │
│                                                              │
│  🐍 train.py (Agent Edits)                                  │
│  ├── Model architecture                                     │
│  ├── Hyperparameters                                        │
│  ├── Optimizer settings                                     │
│  └── Training loop                                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

✅ KEY DESIGN PRINCIPLES TO ADAPT

Autoresearch Principle AutoJaga Adaptation
Single file to modify Financial tools: monte_carlo.py, risk_metrics.py, portfolio_opt.py
Fixed time budget 2-5 minute experiments per iteration
Single metric Combined score: accuracy_weight × error_pct + speed_weight × time_ms
Human edits strategy program.md defines research goals
Agent edits tactics AutoJaga modifies tool parameters/code
Keep/revert based on metric Auto-decision with rollback capability

---

📋 DELIVERABLES

1. Autoresearch Financial Adapter

Create bridge between autoresearch and AutoJaga tools:

```python
# ~/nanojaga/autoresearch/financial_adapter.py
"""
Bridge connecting autoresearch framework to AutoJaga financial tools
"""

import os
import sys
import time
import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Add AutoJaga to path
sys.path.append('/root/nanojaga')

class FinancialResearchAgent:
    """
    Autoresearch-style agent for optimizing financial tools
    """
    
    def __init__(self, tool_name: str, program_path: str = "program.md"):
        self.tool_name = tool_name
        self.tool_path = f"/root/nanojaga/jagabot/tools/{tool_name}.py"
        self.program_path = program_path
        self.backup_path = f"/tmp/{tool_name}_backup.py"
        self.experiment_log = "experiments_log.tsv"
        self.best_score = float('inf')
        self.best_code = None
        
    def read_program(self) -> str:
        """Read research objectives from program.md"""
        with open(self.program_path, 'r') as f:
            return f.read()
    
    def backup_current(self):
        """Create backup before modification"""
        shutil.copy2(self.tool_path, self.backup_path)
    
    def restore_backup(self):
        """Restore from backup (revert)"""
        shutil.copy2(self.backup_path, self.tool_path)
    
    def propose_modification(self, program: str) -> str:
        """
        Use LLM to propose a code modification based on program.md
        This is where AutoJaga's intelligence comes in
        """
        # This will be implemented using Qwen/DeepSeek
        # Returns modified code as string
        pass
    
    def run_experiment(self, time_budget: int = 300) -> Dict[str, Any]:
        """
        Run the modified tool with time budget
        Returns results and metrics
        """
        start_time = time.time()
        
        # Import and run the modified tool
        # This depends on the specific tool being tested
        
        elapsed = time.time() - start_time
        return {
            "computation_time": elapsed,
            "success": True,
            # Tool-specific metrics will be added here
        }
    
    def evaluate_result(self, result: Dict[str, Any], baseline: Dict[str, Any]) -> float:
        """
        Calculate combined score based on program.md criteria
        Lower is better
        """
        # This will be customized per tool
        pass
    
    def log_experiment(self, modification: str, score: float, kept: bool):
        """Log experiment results to TSV file"""
        with open(self.experiment_log, 'a') as f:
            f.write(f"{datetime.now()}\t{modification}\t{score}\t{kept}\n")
    
    def run_experiment_cycle(self) -> bool:
        """
        One complete experiment cycle:
        1. Read program
        2. Backup current code
        3. Propose modification
        4. Apply modification
        5. Run experiment
        6. Evaluate result
        7. Keep or revert
        8. Log result
        """
        program = self.read_program()
        self.backup_current()
        
        modified_code = self.propose_modification(program)
        
        # Apply modification
        with open(self.tool_path, 'w') as f:
            f.write(modified_code)
        
        # Run experiment
        result = self.run_experiment()
        
        # Evaluate
        score = self.evaluate_result(result, {})  # Need baseline
        
        if score < self.best_score:
            self.best_score = score
            self.best_code = modified_code
            self.log_experiment("modification", score, kept=True)
            return True  # Kept
        else:
            self.restore_backup()
            self.log_experiment("modification", score, kept=False)
            return False  # Reverted
    
    def run_overnight(self, hours: int = 8):
        """
        Run experiments autonomously for specified hours
        Each cycle takes ~5 minutes → ~12 experiments/hour
        """
        cycles = (hours * 60) // 5
        print(f"🎯 Target: {cycles} experiments overnight")
        
        for i in range(cycles):
            kept = self.run_experiment_cycle()
            status = "✅ KEPT" if kept else "↩️ REVERTED"
            print(f"Cycle {i+1}/{cycles}: {status}")
```

2. Tool-Specific Experiment Definitions

```python
# ~/nanojaga/autoresearch/experiments/monte_carlo_experiment.py
"""
Monte Carlo simulation optimization experiments
"""

import numpy as np
from financial_adapter import FinancialResearchAgent

class MonteCarloExperiment(FinancialResearchAgent):
    def __init__(self):
        super().__init__("monte_carlo")
        self.baseline_results = self.run_baseline()
    
    def run_baseline(self) -> Dict[str, Any]:
        """Run with original code to get baseline"""
        # Implementation
        pass
    
    def run_experiment(self) -> Dict[str, Any]:
        """Run Monte Carlo with modified code"""
        from jagabot.tools.monte_carlo import monte_carlo
        
        # Test with standard parameters
        result = monte_carlo(
            initial_capital=1000000,
            simulations=5000,
            days=252,
            mean_return=0.001,
            volatility=0.02
        )
        
        # Calculate metrics
        return {
            "mean_final": result.get("mean_final"),
            "var_95": result.get("var_95"),
            "cvar_95": result.get("cvar_95"),
            "computation_time": result.get("time_ms", 0)
        }
    
    def evaluate_result(self, result: Dict[str, Any], baseline: Dict[str, Any]) -> float:
        """
        Combined score = error_pct + (time_ms / 100)
        Lower is better
        """
        # Calculate error vs baseline
        error_pct = abs(result["mean_final"] - baseline["mean_final"]) / baseline["mean_final"] * 100
        time_penalty = result["computation_time"] / 100  # Normalize
        
        return error_pct + time_penalty
```

3. Program.md Templates

```markdown
# ~/nanojaga/autoresearch/program_monte_carlo.md

# AUTOJAGA FINANCIAL RESEARCH PROGRAM

## 🎯 RESEARCH OBJECTIVE
Optimize Monte Carlo simulation for speed/accuracy tradeoff.

## 📊 EVALUATION METRIC
Combined Score = error_pct + (computation_time_ms / 100)
Lower is better. Baseline score ~ 5.0.

## ⏱️ EXPERIMENT BUDGET
Each experiment runs for exactly 3 minutes wall-clock time.

## 🔧 TARGET FILE
`/root/nanojaga/jagabot/tools/monte_carlo.py`

## 🧪 ALLOWED MODIFICATIONS
You may modify:
- Number of simulations (keep between 1000-10000)
- Random number generator seed/method
- Variance reduction techniques
- Parallelization approach
- Data structures for efficiency

## 🚫 CONSTRAINTS
- Never change function signature
- Must accept same parameters: initial_capital, simulations, days, mean_return, volatility
- Must return dict with at least: mean_final, var_95, cvar_95
- Must include error handling
- Must complete within 3 minutes

## 📝 LOGGING
All experiments automatically logged to experiments_log.tsv
```

4. Main Orchestration Script

```python
# ~/nanojaga/autoresearch/run_financial_research.py
"""
Main orchestrator for AutoJaga financial research
"""

import argparse
import importlib
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="AutoJaga Financial Research")
    parser.add_argument("--tool", choices=["monte_carlo", "risk_metrics", "portfolio_opt"], required=True)
    parser.add_argument("--hours", type=int, default=8, help="Hours to run")
    parser.add_argument("--program", default="program.md", help="Program file")
    
    args = parser.parse_args()
    
    # Dynamically import appropriate experiment class
    module = importlib.import_module(f"experiments.{args.tool}_experiment")
    experiment_class = getattr(module, f"{args.tool.title().replace('_', '')}Experiment")
    
    # Initialize and run
    experiment = experiment_class(program_path=args.program)
    print(f"🚀 Starting {args.tool} research for {args.hours} hours")
    experiment.run_overnight(hours=args.hours)
    
    print(f"\n✅ Complete! Check experiments_log.tsv for results")
    print(f"🏆 Best score: {experiment.best_score}")

if __name__ == "__main__":
    main()
```

5. Analysis Notebook

```python
# ~/nanojaga/autoresearch/analyze_results.ipynb
"""
Jupyter notebook to analyze experiment results
"""

import pandas as pd
import matplotlib.pyplot as plt

# Load experiments
df = pd.read_csv('experiments_log.tsv', sep='\t', 
                 names=['timestamp', 'modification', 'score', 'kept'])

# Basic stats
print(f"Total experiments: {len(df)}")
print(f"Improvements kept: {df['kept'].sum()}")
print(f"Best score: {df['score'].min()}")

# Plot progress
plt.figure(figsize=(12, 6))
plt.plot(df.index, df['score'], 'b-', alpha=0.5, label='All experiments')
plt.plot(df[df['kept']].index, df[df['kept']]['score'], 'g.', label='Kept improvements')
plt.axhline(y=df['score'].min(), color='r', linestyle='--', label='Best score')
plt.xlabel('Experiment Number')
plt.ylabel('Combined Score (lower is better)')
plt.title('Financial Tool Optimization Progress')
plt.legend()
plt.grid(True, alpha=0.3)
plt.show()
```

---

📊 SUCCESS METRICS

Metric Target Measurement
Experiments per night 50-100 (8-12/hour) Count log entries
Improvement rate ≥20% score reduction (best_score - baseline)/baseline
Autonomy 100% No manual intervention
Tool compatibility All 3 tools Monte Carlo, Risk, Portfolio

---

🚀 IMPLEMENTATION ROADMAP

```yaml
Phase 1 (2 hours): Setup & Adapter
  - Create financial_adapter.py
  - Test with monte_carlo.py
  - Verify backup/restore works

Phase 2 (2 hours): Experiment Definitions
  - Create monte_carlo_experiment.py
  - Create risk_metrics_experiment.py
  - Create portfolio_opt_experiment.py
  - Define metrics for each

Phase 3 (1 hour): Program.md Templates
  - Write research programs for each tool
  - Test with single cycle

Phase 4 (1 hour): Orchestration
  - Create run_financial_research.py
  - Test overnight simulation (1 hour test)

Phase 5 (1 hour): Analysis
  - Set up analysis notebook
  - Create visualization
  - Document findings
```

---

✅ NEXT STEPS FOR COPILOT

Please provide:

1. Complete implementation of financial_adapter.py with all methods
2. One complete experiment class (e.g., monte_carlo_experiment.py)
3. A sample program.md for Monte Carlo optimization
4. The main orchestration script
5. Testing instructions to verify the system works

Ready to proceed? 🚀
