# 🚀 COPAW + AUTOJAGA + QWEN CLI INTEGRATION PLAN

**Date:** March 14, 2026  
**Status:** 📋 **PLANNING PHASE**  
**Blueprint:** `/root/nanojaga/Intergrate.md`

---

## 📊 EXECUTIVE SUMMARY

The blueprint proposes an **autonomous research pipeline** where:
1. **AutoJaga** plans experiments (Strategist)
2. **Qwen CLI** generates code (Coder)
3. **Human** executes and uploads results (Quality Assurance)
4. **CoPaw Orchestrator** manages the workflow

**Goal:** Fully automated ML experiment iteration with human-in-the-loop.

---

## 🏗️ ARCHITECTURE ANALYSIS

### Current State vs Target

| Component | Current | Target | Gap |
|-----------|---------|--------|-----|
| **AutoJaga** | ✅ 45+ tools, 4-phase research | ✅ API endpoint | 🟡 Need FastAPI server |
| **Qwen CLI** | ✅ Code generation | ✅ Service endpoint | 🟡 Need wrapper service |
| **CoPaw Orchestrator** | ❌ Not exists | ✅ Python orchestrator | 🔴 Need to build |
| **Workspace** | ✅ `/root/.jagabot/workspace` | ✅ CoPaw_Projects structure | 🟡 Need folder structure |
| **Human Interface** | ✅ CLI, TUI | ✅ Upload results | 🟡 Need upload mechanism |

---

## 📋 IMPLEMENTATION PHASES

### Phase 1: Foundation (2 hours) 🔴

#### 1.1 Create Workspace Structure
**File:** `/root/.jagabot/workspace/CoPaw_Projects/`

```bash
mkdir -p /root/.jagabot/workspace/CoPaw_Projects
cd /root/.jagabot/workspace/CoPaw_Projects
mkdir -p Logistic_Regression/{blueprints,code,results,analysis}
```

#### 1.2 AutoJaga API Server
**File:** `/root/nanojaga/jagabot/api/server.py`

**Dependencies:**
- FastAPI
- Uvicorn
- Pydantic

**Endpoints:**
- `POST /plan` - Create experiment blueprint
- `POST /analyze` - Analyze results
- `GET /health` - Health check

**Implementation Priority:** 🔴 **CRITICAL**

#### 1.3 Qwen CLI Service
**File:** `/root/qwen_service.py`

**Dependencies:**
- FastAPI
- Uvicorn
- Subprocess (for Qwen CLI calls)

**Endpoints:**
- `POST /generate` - Generate code from blueprint
- `POST /execute` - Run code (optional)
- `GET /health` - Health check

**Implementation Priority:** 🔴 **CRITICAL**

---

### Phase 2: Orchestrator (3 hours) 🟡

#### 2.1 CoPaw Orchestrator Core
**File:** `/root/copaw_orchestrator.py`

**Features:**
- Project management
- Research cycle orchestration
- Agent coordination
- Result aggregation

**Methods:**
- `start_project(name, description)`
- `run_research_cycle(prompt)`
- `_call_autojaga_plan(prompt, exp_num)`
- `_call_qwen_generate(blueprint, exp_num)`
- `_collect_results(project_path, exp_num)`
- `_call_autojaga_analyze(results, exp_num)`

**Implementation Priority:** 🟡 **HIGH**

#### 2.2 Human Upload Interface
**Options:**
1. **Simple:** File upload via HTTP POST
2. **Medium:** Web interface with drag-drop
3. **Advanced:** Desktop app with auto-detection

**Recommended:** Option 1 (simple HTTP POST)

**File:** `/root/copaw_upload.py`

**Implementation Priority:** 🟡 **HIGH**

---

### Phase 3: Integration (2 hours) 🟢

#### 3.1 Service Communication
**Tasks:**
- Configure AutoJaga API URL
- Configure Qwen Service URL
- Test HTTP communication
- Add retry logic

#### 3.2 Error Handling
**Scenarios:**
- AutoJaga API down
- Qwen Service timeout
- Human doesn't upload results
- Invalid results format

**Implementation Priority:** 🟢 **MEDIUM**

---

### Phase 4: Testing (2 hours) 🔵

#### 4.1 End-to-End Test
**Scenario:** Logistic Regression improvement

**Steps:**
1. Start project
2. Run cycle 1 (baseline)
3. Upload results
4. Run cycle 2 (improvement)
5. Upload results
6. Run cycle 3 (final)
7. Verify accuracy improvement

#### 4.2 Integration Tests
**Tests:**
- AutoJaga API responds
- Qwen Service generates code
- Orchestrator coordinates correctly
- Results are collected properly

**Implementation Priority:** 🔵 **LOW** (but important)

---

## 📁 FILE STRUCTURE

```
/root/
├── nanojaga/
│   └── jagabot/
│       └── api/
│           └── server.py              # NEW - AutoJaga API
├── copaw_orchestrator.py              # NEW - Main orchestrator
├── copaw_upload.py                    # NEW - Human upload interface
├── qwen_service.py                    # NEW - Qwen CLI wrapper
└── .jagabot/
    └── workspace/
        └── CoPaw_Projects/            # NEW - Project folder
            ├── Logistic_Regression/
            │   ├── blueprints/
            │   ├── code/
            │   ├── results/
            │   └── analysis/
            └── Project_X/
```

---

## 🔧 IMPLEMENTATION DETAILS

### 1. AutoJaga API Server

```python
# /root/nanojaga/jagabot/api/server.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from pathlib import Path

app = FastAPI(title="AutoJaga API", version="5.0")

class PlanRequest(BaseModel):
    prompt: str
    context: dict = {}
    previous_results: dict = {}

class AnalyzeRequest(BaseModel):
    experiment_data: dict
    previous_results: dict = {}

@app.post("/plan")
async def create_plan(request: PlanRequest):
    """AutoJaga creates experiment blueprint"""
    try:
        from jagabot.skills.research.core import ResearchSkill
        
        research = ResearchSkill()
        result = research.run(
            topic=request.prompt,
            config=request.context
        )
        
        return {
            "status": "success",
            "blueprint": result.get("synthesis", ""),
            "metrics": result.get("metrics", {}),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze")
async def analyze_results(request: AnalyzeRequest):
    """AutoJaga analyzes results"""
    try:
        # Use AutoJaga analysis tools
        from jagabot.agent.tools.evaluation import EvaluationKernel
        
        evaluator = EvaluationKernel()
        analysis = evaluator.full_evaluate(
            expected=request.previous_results,
            actual=request.experiment_data,
            history=[],
            execution_log=[]
        )
        
        return {
            "status": "success",
            "analysis": analysis.to_dict(),
            "recommendation": "Try ensemble methods",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "5.0"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

### 2. Qwen CLI Service

```python
# /root/qwen_service.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import json
from pathlib import Path

app = FastAPI(title="Qwen Code Generator", version="1.0")

class CodeRequest(BaseModel):
    blueprint: str
    experiment_num: int
    project: str

@app.post("/generate")
async def generate_code(request: CodeRequest):
    """Qwen generates code from blueprint"""
    try:
        # Save blueprint to temp file
        blueprint_path = Path(f"/tmp/blueprint_{request.experiment_num}.md")
        blueprint_path.write_text(request.blueprint)
        
        # Call Qwen CLI
        # In production: subprocess.run(["qwen", "generate", str(blueprint_path)])
        
        # For now, generate template code
        code_files = {
            f"exp{request.experiment_num}_data_loader.py": _generate_data_loader(),
            f"exp{request.experiment_num}_model.py": _generate_model(),
            f"exp{request.experiment_num}_evaluation.py": _generate_evaluation(),
            "requirements.txt": "scikit-learn==1.4.2\npandas==2.2.0\nnumpy==1.26.0"
        }
        
        return {
            "status": "success",
            "code_files": code_files,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _generate_data_loader():
    return """# Data Loader
import pandas as pd
from sklearn.datasets import make_classification

def load_data():
    X, y = make_classification(n_samples=1200, n_features=20, random_state=42)
    return X, y
"""

def _generate_model():
    return """# Model
from sklearn.linear_model import LogisticRegression

def create_model(C=1.0):
    return LogisticRegression(C=C, max_iter=1000)
"""

def _generate_evaluation():
    return """# Evaluation
from sklearn.metrics import accuracy_score
import json

def evaluate(model, X_test, y_test):
    y_pred = model.predict(X_test)
    return {"accuracy": accuracy_score(y_test, y_pred)}
"""

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
```

---

### 3. CoPaw Orchestrator

```python
# /root/copaw_orchestrator.py

import os
import json
import requests
from datetime import datetime
from pathlib import Path

class CopawOrchestrator:
    """CoPaw Orchestrator - Manages AutoJaga + Qwen workflow"""

    def __init__(self, workspace="/root/.jagabot/workspace/CoPaw_Projects"):
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        
        # Service URLs
        self.autojaga_url = "http://localhost:8000"
        self.qwen_url = "http://localhost:8080"
        
        # State
        self.current_project = None
        self.current_experiment = 0
        self.session_log = []

    def start_project(self, project_name, description):
        """Start new project"""
        project_path = self.workspace / project_name
        project_path.mkdir(exist_ok=True)
        
        for subdir in ["blueprints", "code", "results", "analysis"]:
            (project_path / subdir).mkdir(exist_ok=True)
        
        self.current_project = project_name
        self.current_experiment = 0
        self._log(f"✅ Project {project_name} started: {description}")
        
        return {"status": "success", "project": project_name, "path": str(project_path)}

    def run_research_cycle(self, prompt):
        """Run full research cycle"""
        self.current_experiment += 1
        exp_num = self.current_experiment
        project_path = self.workspace / self.current_project
        
        print(f"\n🚀 Starting Research Cycle {exp_num}")
        print("="*60)
        
        # STEP 1: AutoJaga Plan
        print("\n📋 STEP 1: AutoJaga Planning...")
        blueprint = self._call_autojaga_plan(prompt, exp_num)
        blueprint_path = project_path / "blueprints" / f"blueprint_v{exp_num}.md"
        blueprint_path.write_text(blueprint)
        print(f"   ✅ Blueprint saved")
        
        # STEP 2: Qwen Generate Code
        print("\n💻 STEP 2: Qwen Code Generation...")
        code_files = self._call_qwen_generate(blueprint, exp_num)
        code_dir = project_path / "code" / f"experiment{exp_num}"
        code_dir.mkdir(exist_ok=True)
        
        for filename, content in code_files.items():
            (code_dir / filename).write_text(content)
        print(f"   ✅ Code generated ({len(code_files)} files)")
        
        # STEP 3: Human Execution
        print("\n👤 STEP 3: Human Execution Required")
        print(f"   📁 Code: {code_dir}")
        print("   ▶️  Run code and upload results")
        
        # Wait for results
        input("\nPress ENTER after uploading results...")
        
        # STEP 4: AutoJaga Analyze
        print("\n📊 STEP 4: AutoJaga Analysis...")
        results = self._collect_results(project_path, exp_num)
        analysis = self._call_autojaga_analyze(results, exp_num)
        
        analysis_path = project_path / "analysis" / f"report_v{exp_num}.md"
        analysis_path.write_text(analysis)
        print(f"   ✅ Analysis saved")
        
        # Extract next prompt
        next_prompt = self._extract_next_prompt(analysis)
        
        print(f"\n✅ Cycle {exp_num} Complete!")
        
        return {
            "cycle": exp_num,
            "blueprint": str(blueprint_path),
            "analysis": str(analysis_path),
            "next_prompt": next_prompt
        }

    def _call_autojaga_plan(self, prompt, exp_num):
        """Call AutoJaga API for planning"""
        try:
            response = requests.post(
                f"{self.autojaga_url}/plan",
                json={"prompt": prompt, "context": {"experiment_num": exp_num}}
            )
            response.raise_for_status()
            return response.json()["blueprint"]
        except Exception as e:
            return f"# AutoJaga API error: {e}\n# Manual blueprint needed"

    def _call_qwen_generate(self, blueprint, exp_num):
        """Call Qwen Service for code generation"""
        try:
            response = requests.post(
                f"{self.qwen_url}/generate",
                json={
                    "blueprint": blueprint,
                    "experiment_num": exp_num,
                    "project": self.current_project
                }
            )
            response.raise_for_status()
            return response.json()["code_files"]
        except Exception as e:
            return {"error.py": f"# Qwen error: {e}"}

    def _collect_results(self, project_path, exp_num):
        """Collect results from human upload"""
        results = {}
        results_path = project_path / "results"
        
        # Read accuracy file
        acc_file = results_path / f"accuracy_exp{exp_num}.txt"
        if acc_file.exists():
            results['accuracy'] = acc_file.read_text().strip()
        
        # Read JSON results
        json_file = results_path / f"tuning_results_exp{exp_num}.json"
        if json_file.exists():
            results['tuning'] = json.loads(json_file.read_text())
        
        return results

    def _call_autojaga_analyze(self, results, exp_num):
        """Call AutoJaga API for analysis"""
        try:
            response = requests.post(
                f"{self.autojaga_url}/analyze",
                json={"experiment_data": results, "previous_results": {}}
            )
            response.raise_for_status()
            return response.json()["analysis"]
        except Exception as e:
            return f"# Analysis error: {e}"

    def _extract_next_prompt(self, analysis):
        """Extract next prompt from analysis"""
        import re
        match = re.search(r'## 🎯 Next Prompt\n(.*?)\n', analysis, re.DOTALL)
        return match.group(1).strip() if match else "Continue optimization"

    def _log(self, message):
        """Log session"""
        self.session_log.append({
            "timestamp": datetime.now().isoformat(),
            "message": message
        })
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")


if __name__ == "__main__":
    copaw = CopawOrchestrator()
    
    copaw.start_project(
        "Logistic_Regression",
        "Improve model accuracy through iterative experiments"
    )
    
    for cycle in range(1, 4):
        prompt = f"Improve accuracy beyond {0.85 + (cycle-1)*0.01:.2f}"
        result = copaw.run_research_cycle(prompt)
        print(f"\n✅ Cycle {cycle} complete. Next: {result['next_prompt']}")
```

---

## 🚀 INSTALLATION

### Quick Install Script

```bash
#!/bin/bash
# install_copaw.sh

echo "🚀 Installing CoPaw Pipeline..."

# Install dependencies
pip install fastapi uvicorn requests python-multipart

# Create workspace
mkdir -p /root/.jagabot/workspace/CoPaw_Projects

# Start AutoJaga API
cd /root/nanojaga
nohup python3 -m jagabot.api.server > /tmp/autojaga.log 2>&1 &
echo "✅ AutoJaga API started (port 8000)"

# Start Qwen Service
cd /root
nohup python3 qwen_service.py > /tmp/qwen.log 2>&1 &
echo "✅ Qwen Service started (port 8080)"

# Wait for services
sleep 3

# Test health endpoints
curl -s http://localhost:8000/health && echo " - AutoJaga OK"
curl -s http://localhost:8080/health && echo " - Qwen OK"

echo ""
echo "✅ Installation Complete!"
echo "Run: python3 /root/copaw_orchestrator.py"
```

---

## 📊 TESTING STRATEGY

### Test Scenario: Logistic Regression

**Initial State:**
- Baseline accuracy: 0.86
- Goal: > 0.88

**Cycle 1:**
- AutoJaga: Plan baseline model
- Qwen: Generate LogisticRegression code
- Human: Run, get 0.86 accuracy
- AutoJaga: Analyze, suggest ensemble

**Cycle 2:**
- AutoJaga: Plan Random Forest
- Qwen: Generate RandomForest code
- Human: Run, get 0.87 accuracy
- AutoJaga: Analyze, suggest XGBoost

**Cycle 3:**
- AutoJaga: Plan XGBoost
- Qwen: Generate XGBoost code
- Human: Run, get 0.88 accuracy
- AutoJaga: Analyze, goal achieved!

---

## ⚠️ RISKS & MITIGATIONS

| Risk | Impact | Mitigation |
|------|--------|------------|
| AutoJaga API down | High | Fallback to manual planning |
| Qwen Service timeout | Medium | Retry logic, cache responses |
| Human doesn't upload | Medium | Reminder notifications |
| Invalid results format | Low | Validation on upload |

---

## 🏁 SUCCESS CRITERIA

### Phase 1 Complete When:
- [ ] AutoJaga API responds to `/plan` and `/analyze`
- [ ] Qwen Service responds to `/generate`
- [ ] Workspace structure created
- [ ] Health endpoints work

### Phase 2 Complete When:
- [ ] CoPaw Orchestrator runs full cycle
- [ ] Human can upload results
- [ ] Results are collected properly
- [ ] Analysis is generated

### Phase 3 Complete When:
- [ ] 3 full cycles run successfully
- [ ] Accuracy improves each cycle
- [ ] All error cases handled
- [ ] Documentation complete

---

## 🎯 RECOMMENDATION

**Start with Phase 1 (AutoJaga API + Qwen Service)**

**Estimated Time:** 4 hours total
**Risk:** LOW (both services are wrappers around existing functionality)
**Impact:** HIGH (enables full automation)

**Next Steps:**
1. Create AutoJaga API server (2 hours)
2. Create Qwen Service (1 hour)
3. Test both services (1 hour)

**Ready to implement?**

```bash
cd /root/nanojaga
mkdir -p jagabot/api
# Start with AutoJaga API server
```

---

**Status:** 📋 **READY FOR IMPLEMENTATION**  
**Priority:** 🔴 **HIGH** (core automation pipeline)  
**Estimated Time:** 4-6 hours for full implementation
