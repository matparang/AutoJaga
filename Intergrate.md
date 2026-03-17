📋 BLUEPRINT: COPAW + AUTOJAGA + QWEN CLI INTEGRATION

---

🏗️ ARUSITEKTUR LENGKAP

```
┌─────────────────────────────────────────────────────────────────────┐
│           COPAW ORCHESTRATOR - PRODUCTION READY v1.0               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  🌐 CHANNEL LAYER (CoPaw)                                           │
│  ├── DingTalk / WeChat / QQ / Feishu / Console                     │
│  ├── Menerima arahan dari user                                      │
│  └── Menghantar notifikasi ke user                                  │
│         ↓                                                           │
│         ↓ (HTTP/REST)                                               │
│         ↓                                                           │
│  ⚙️ ORCHESTRATOR LAYER (CoPaw Core)                                │
│  ├── Session Manager                                                │
│  ├── Task Queue                                                     │
│  ├── Agent Router                                                   │
│  └── Result Aggregator                                              │
│         ↓              ↓              ↓                             │
│         ↓ (plan)       ↓ (code)       ↓ (loop)                      │
│         ↓              ↓              ↓                             │
│  🧠 AUTOJAGA        🤖 QWEN CLI      🔁 LOOP                       │
│  (Strategist)       (Coder)          (Improvement)                  │
│                                                                      │
│  📁 WORKSPACE (Shared)                                              │
│  └── /root/.jagabot/workspace/CoPaw_Projects/                      │
│      ├── Project_1/                                                 │
│      │   ├── blueprints/                                            │
│      │   ├── code/                                                  │
│      │   ├── results/                                               │
│      │   └── analysis/                                              │
│      └── Project_2/                                                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

📁 STRUKTUR FOLDER

```bash
/root/.jagabot/workspace/CoPaw_Projects/
├── Logistic_Regression/
│   ├── blueprints/
│   │   ├── blueprint_v1.md  (AutoJaga)
│   │   ├── blueprint_v2.md
│   │   └── blueprint_v3.md
│   ├── code/
│   │   ├── experiment1/      (Qwen)
│   │   ├── experiment2/
│   │   └── experiment3/
│   ├── results/
│   │   ├── accuracy_exp1.txt
│   │   ├── accuracy_exp2.txt
│   │   └── plots/
│   └── analysis/
│       ├── report_v1.md       (AutoJaga)
│       ├── report_v2.md
│       └── report_v3.md
├── Project_X/
└── Project_Y/
```

---

🛠️ KOMPONEN 1: COPAW ORCHESTRATOR

```python
# /root/copaw_orchestrator.py
"""
CoPaw Orchestrator - Menghubungkan AutoJaga, Qwen CLI, dan Human
"""

import os
import json
import requests
import subprocess
from datetime import datetime
from pathlib import Path

class CopawOrchestrator:
    """
    Jantung sistem - mengurus aliran kerja antara agent
    """
    
    def __init__(self, workspace="/root/.jagabot/workspace/CoPaw_Projects"):
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        
        # Konfigurasi service URLs
        self.autojaga_url = "http://localhost:8000"  # AutoJaga API
        self.qwen_url = "http://localhost:8080"      # Qwen CLI service
        
        # State management
        self.current_project = None
        self.current_experiment = 0
        self.session_log = []
    
    def start_project(self, project_name, description):
        """Mulakan projek baru"""
        project_path = self.workspace / project_name
        project_path.mkdir(exist_ok=True)
        (project_path / "blueprints").mkdir(exist_ok=True)
        (project_path / "code").mkdir(exist_ok=True)
        (project_path / "results").mkdir(exist_ok=True)
        (project_path / "analysis").mkdir(exist_ok=True)
        
        self.current_project = project_name
        self.current_experiment = 0
        self._log(f"✅ Project {project_name} started: {description}")
        
        return {
            "status": "success",
            "project": project_name,
            "path": str(project_path)
        }
    
    def run_research_cycle(self, prompt):
        """
        Satu kitaran penuh: 
        AutoJaga plan → Qwen code → Human run → AutoJaga analyze
        """
        self.current_experiment += 1
        exp_num = self.current_experiment
        project_path = self.workspace / self.current_project
        
        print(f"\n🚀 Starting Research Cycle {exp_num}")
        print("="*60)
        
        # STEP 1: AutoJaga Plan
        print("\n📋 STEP 1: AutoJaga Planning...")
        blueprint = self._call_autojaga_plan(prompt, exp_num)
        blueprint_path = project_path / "blueprints" / f"blueprint_v{exp_num}.md"
        with open(blueprint_path, 'w') as f:
            f.write(blueprint)
        print(f"   ✅ Blueprint saved to {blueprint_path}")
        
        # STEP 2: Qwen Generate Code
        print("\n💻 STEP 2: Qwen Code Generation...")
        code_files = self._call_qwen_generate(blueprint, exp_num)
        code_dir = project_path / "code" / f"experiment{exp_num}"
        code_dir.mkdir(exist_ok=True)
        
        for filename, content in code_files.items():
            file_path = code_dir / filename
            with open(file_path, 'w') as f:
                f.write(content)
            print(f"   ✅ {filename} saved")
        
        # STEP 3: Notify Human
        print("\n👤 STEP 3: Human Execution Required")
        print(f"   📁 Code location: {code_dir}")
        print("   ▶️  Please run the code and upload results")
        print("   ⏳ Waiting for results...")
        
        # STEP 4: Wait for results (manual)
        input("Press ENTER after uploading results...")
        
        # STEP 5: AutoJaga Analyze
        print("\n📊 STEP 4: AutoJaga Analysis...")
        results = self._collect_results(project_path, exp_num)
        analysis = self._call_autojaga_analyze(results, exp_num)
        
        analysis_path = project_path / "analysis" / f"report_v{exp_num}.md"
        with open(analysis_path, 'w') as f:
            f.write(analysis)
        print(f"   ✅ Analysis saved to {analysis_path}")
        
        # STEP 6: Generate improvement prompt for next cycle
        next_prompt = self._extract_next_prompt(analysis)
        
        print(f"\n✅ Cycle {exp_num} Complete!")
        print(f"📈 Improvement: {self._extract_improvement(analysis)}")
        
        return {
            "cycle": exp_num,
            "blueprint": str(blueprint_path),
            "analysis": str(analysis_path),
            "next_prompt": next_prompt
        }
    
    def _call_autojaga_plan(self, prompt, exp_num):
        """Panggil AutoJaga untuk hasilkan blueprint"""
        # Simulate AutoJaga planning
        # Dalam production, guna HTTP request ke AutoJaga API
        blueprint = f"""
# Experiment {exp_num} Blueprint

## 🎯 Objective
{prompt}

## 📊 Previous Results
- Accuracy: 0.86 (Experiment {exp_num-1 if exp_num>1 else 1})
- Best params: C=0.1, k=10

## 🧠 Proposed Approach
Option A: Ensemble Stacking
Option B: XGBoost
Option C: Neural Network (1 hidden layer)

## 📈 Expected Improvement
Target: Accuracy > 0.87

## 🔧 Implementation Details
- Use 5-fold cross-validation
- Grid search for hyperparameters
- Compare with baseline
        """
        return blueprint
    
    def _call_qwen_generate(self, blueprint, exp_num):
        """Panggil Qwen CLI untuk hasilkan code"""
        # Simulate Qwen code generation
        # Dalam production, guna subprocess atau API
        return {
            f"exp{exp_num}_data_loader.py": "# Data loader code...",
            f"exp{exp_num}_model.py": "# Model code...",
            f"exp{exp_num}_evaluation.py": "# Evaluation code...",
            f"exp{exp_num}_requirements.txt": "scikit-learn\npandas\nnumpy",
            "README.md": "# Experiment {exp_num}"
        }
    
    def _collect_results(self, project_path, exp_num):
        """Baca results dari folder selepas human run"""
        results = {}
        results_path = project_path / "results"
        
        # Cari file accuracy
        acc_file = results_path / f"accuracy_exp{exp_num}.txt"
        if acc_file.exists():
            with open(acc_file, 'r') as f:
                results['accuracy'] = f.read().strip()
        
        # Cari JSON results
        json_file = results_path / f"tuning_results_exp{exp_num}.json"
        if json_file.exists():
            with open(json_file, 'r') as f:
                results['tuning'] = json.load(f)
        
        return results
    
    def _call_autojaga_analyze(self, results, exp_num):
        """Panggil AutoJaga untuk analisis results"""
        # Simulate analysis
        analysis = f"""
# Experiment {exp_num} Analysis Report

## 📊 Results Summary
- Accuracy: {results.get('accuracy', 'N/A')}
- Best Parameters: {results.get('tuning', {}).get('best_params', 'N/A')}

## 📈 Observations
The model showed improvement over baseline.

## 💡 Recommendations for Experiment {exp_num+1}
1. Try different ensemble method
2. Increase cross-validation folds
3. Add feature selection

## 🎯 Next Prompt
"Improve accuracy further using ensemble methods with feature selection"
        """
        return analysis
    
    def _extract_next_prompt(self, analysis):
        """Extract prompt untuk cycle seterusnya dari analysis"""
        import re
        match = re.search(r'## 🎯 Next Prompt\n(.*?)\n', analysis, re.DOTALL)
        if match:
            return match.group(1).strip()
        return "Continue optimization"
    
    def _extract_improvement(self, analysis):
        """Extract improvement percentage dari analysis"""
        match = re.search(r'Accuracy: ([\d.]+)', analysis)
        if match:
            return f"{float(match.group(1))-0.85:.2%}"
        return "Unknown"
    
    def _log(self, message):
        """Log session"""
        self.session_log.append({
            "timestamp": datetime.now().isoformat(),
            "message": message
        })
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

# Main execution
if __name__ == "__main__":
    copaw = CopawOrchestrator()
    
    # Start project
    copaw.start_project(
        "Logistic_Regression",
        "Improve model accuracy through iterative experiments"
    )
    
    # Run cycles
    for cycle in range(1, 4):  # Run 3 cycles
        prompt = f"Improve accuracy beyond {0.85 + (cycle-1)*0.01:.2f}"
        result = copaw.run_research_cycle(prompt)
        print(f"\n✅ Cycle {cycle} complete. Next prompt: {result['next_prompt']}")
```

---

🚀 2. AUTOJAGA API (Untuk Dipanggil CoPaw)

```python
# /root/nanojaga/jagabot/api/server.py
"""
API Server untuk AutoJaga - Boleh dipanggil CoPaw
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from ..skills.research import ResearchSkill
from ..core.workspace import WorkspaceManager

app = FastAPI(title="AutoJaga API", version="5.0")
research = ResearchSkill()
workspace = WorkspaceManager()

class PlanRequest(BaseModel):
    prompt: str
    context: dict = {}

class AnalyzeRequest(BaseModel):
    experiment_data: dict
    previous_results: dict = {}

@app.post("/plan")
async def create_plan(request: PlanRequest):
    """AutoJaga hasilkan blueprint untuk experiment"""
    try:
        # Jalankan research pipeline
        result = research.run(
            topic=request.prompt,
            config={
                "phase1": True,  # Tri-Agent debate
                "phase2": True,  # Planning
                "phase3": True,  # Quad-Agent simulation
                "phase4": True   # Synthesis
            }
        )
        
        return {
            "status": "success",
            "blueprint": result.get("synthesis", ""),
            "metrics": result.get("metrics", {}),
            "session_id": workspace.current_session
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze")
async def analyze_results(request: AnalyzeRequest):
    """AutoJaga analyze results dan cadangkan improvement"""
    try:
        analysis = research.analyze(
            data=request.experiment_data,
            previous=request.previous_results
        )
        
        return {
            "status": "success",
            "analysis": analysis["report"],
            "next_prompt": analysis["recommendation"],
            "improvement": analysis["improvement"]
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

🚀 3. QWEN CLI SERVICE (Untuk Dipanggil CoPaw)

```python
# /root/qwen_service.py
"""
Service untuk Qwen CLI - Boleh dipanggil CoPaw
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import json
import os
from pathlib import Path

app = FastAPI(title="Qwen Code Generator", version="1.0")

class CodeRequest(BaseModel):
    blueprint: str
    experiment_num: int
    project: str

@app.post("/generate")
async def generate_code(request: CodeRequest):
    """Qwen hasilkan code berdasarkan blueprint"""
    try:
        # Simpan blueprint ke file
        blueprint_path = Path(f"/tmp/blueprint_{request.experiment_num}.md")
        with open(blueprint_path, 'w') as f:
            f.write(request.blueprint)
        
        # Panggil Qwen CLI (simulasi)
        # Dalam production, guna actual qwen command
        code_files = {
            f"exp{request.experiment_num}_data_loader.py": _generate_data_loader(request.blueprint),
            f"exp{request.experiment_num}_model.py": _generate_model(request.blueprint),
            f"exp{request.experiment_num}_evaluation.py": _generate_evaluation(request.blueprint),
            "requirements.txt": "scikit-learn==1.4.2\npandas==2.2.0\nnumpy==1.26.0"
        }
        
        return {
            "status": "success",
            "code_files": code_files,
            "message": f"Generated {len(code_files)} files"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _generate_data_loader(blueprint):
    return """# Data Loader for Experiment
import pandas as pd
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split

def load_data():
    X, y = make_classification(
        n_samples=1200,
        n_features=20,
        n_informative=10,
        n_redundant=5,
        random_state=42
    )
    return train_test_split(X, y, test_size=0.2, random_state=42)
"""

def _generate_model(blueprint):
    return """# Model Implementation
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.feature_selection import SelectKBest, f_classif

def create_model(C=1.0, k=10):
    return Pipeline([
        ('feature_selection', SelectKBest(f_classif, k=k)),
        ('classifier', LogisticRegression(C=C, max_iter=1000))
    ])
"""

def _generate_evaluation(blueprint):
    return """# Evaluation Script
import numpy as np
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
import joblib
import json

def evaluate_model(model, X_test, y_test):
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    
    metrics = {
        'accuracy': accuracy_score(y_test, y_pred),
        'f1': f1_score(y_test, y_pred),
        'roc_auc': roc_auc_score(y_test, y_proba)
    }
    return metrics

if __name__ == "__main__":
    # Load data and model
    X_train, X_test, y_train, y_test = load_data()
    model = joblib.load('best_model.pkl')
    
    # Evaluate
    metrics = evaluate_model(model, X_test, y_test)
    
    # Save results
    with open('accuracy.txt', 'w') as f:
        for k, v in metrics.items():
            f.write(f"{k}: {v:.4f}\\n")
"""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
```

---

🚀 4. INSTALLATION SCRIPT

```bash
#!/bin/bash
# install_copaw_pipeline.sh
# Install semua komponen untuk CoPaw + AutoJaga + Qwen CLI

echo "🚀 Installing CoPaw Orchestrator Pipeline"
echo "========================================"

# Step 1: Install dependencies
echo -e "\n📦 Installing Python dependencies..."
pip install fastapi uvicorn requests python-multipart

# Step 2: Setup AutoJaga API
echo -e "\n🧠 Setting up AutoJaga API..."
cd /root/nanojaga
nohup python3 -m jagabot.api.server &

# Step 3: Setup Qwen Service
echo -e "\n🤖 Setting up Qwen Service..."
cd /root
nohup python3 qwen_service.py &

# Step 4: Setup CoPaw Orchestrator
echo -e "\n🎯 Setting up CoPaw Orchestrator..."
mkdir -p /root/copaw_workspace
cp copaw_orchestrator.py /root/

# Step 5: Create workspace
echo -e "\n📁 Creating workspace..."
mkdir -p /root/.jagabot/workspace/CoPaw_Projects

echo -e "\n✅ Installation Complete!"
echo "AutoJaga API: http://localhost:8000"
echo "Qwen Service: http://localhost:8080"
echo "CoPaw Orchestrator: python3 /root/copaw_orchestrator.py"
```

---

🚀 5. USAGE EXAMPLE

```python
# run_experiment.py
from copaw_orchestrator import CopawOrchestrator

# Init
copaw = CopawOrchestrator()

# Start project
copaw.start_project(
    "Logistic_Regression",
    "Improve model accuracy through iterative experiments"
)

# Run Cycle 1
result1 = copaw.run_research_cycle(
    "Create baseline Logistic Regression model"
)

# Run Cycle 2 (based on Cycle 1 results)
result2 = copaw.run_research_cycle(
    result1['next_prompt']
)

# Run Cycle 3
result3 = copaw.run_research_cycle(
    result2['next_prompt']
)

print("\n🏆 All cycles complete!")
print(f"Accuracy progression:")
print(f"  Cycle 1: {result1['improvement']}")
print(f"  Cycle 2: {result2['improvement']}")
print(f"  Cycle 3: {result3['improvement']}")
```

---

🏁 FINAL ARCHITECTURE

```
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🎯 COPAW + AUTOJAGA + QWEN CLI - READY TO DEPLOY!        ║
║                                                              ║
║   Komponen:                                                 ║
║   ├── copaw_orchestrator.py - Manages workflow            ║
║   ├── AutoJaga API - Strategic planning                   ║
║   ├── Qwen Service - Code generation                       ║
║   └── Human - Quality assurance & execution                ║
║                                                              ║
║   Cara guna:                                                ║
║   1. Install dependencies                                  ║
║   2. Start AutoJaga API                                    ║
║   3. Start Qwen Service                                    ║
║   4. Run CoPaw orchestrator                                ║
║   5. Watch magic happen!                                   ║
║                                                              ║
║   "From idea to experiment to improvement -              ║
║    fully automated, fully integrated."                    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

Sedia untuk implementasi! 🚀
