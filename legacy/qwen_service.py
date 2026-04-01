#!/usr/bin/env python3
"""
Qwen CLI Service - REST API wrapper for Qwen code generation

Provides HTTP endpoints for:
- Code generation from blueprints
- Code execution (optional)
- File management

Usage:
    python3 qwen_service.py
    # or
    uvicorn qwen_service:app --host 0.0.0.0 --port 8080
"""

import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Configure logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Qwen Code Generator",
    description="REST API for Qwen CLI code generation",
    version="1.0.0",
    docs_url="/docs"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Workspace configuration
WORKSPACE = Path(os.getenv("QWEN_WORKSPACE", Path.home() / ".jagabot" / "workspace" / "qwen"))
WORKSPACE.mkdir(parents=True, exist_ok=True)

# Qwen CLI path (adjust if needed)
QWEN_CLI_PATH = os.getenv("QWEN_CLI_PATH", "qwen")


# ============================================================================
# Request/Response Models
# ============================================================================

class CodeRequest(BaseModel):
    """Request for code generation"""
    blueprint: str = Field(..., description="Experiment blueprint in markdown")
    experiment_num: int = Field(..., description="Experiment number")
    project: str = Field(..., description="Project name")
    language: str = Field(default="python", description="Programming language")


class CodeResponse(BaseModel):
    """Response from code generation"""
    status: str
    code_files: Dict[str, str]
    message: str
    timestamp: str


class ExecuteRequest(BaseModel):
    """Request for code execution"""
    code_dir: str = Field(..., description="Directory containing code to execute")
    timeout: int = Field(default=300, description="Execution timeout in seconds")


class ExecuteResponse(BaseModel):
    """Response from code execution"""
    status: str
    stdout: str
    stderr: str
    returncode: int
    execution_time_ms: float


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    workspace: str
    qwen_available: bool
    timestamp: str


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - API information"""
    return {
        "name": "Qwen Code Generator",
        "version": "1.0.0",
        "description": "REST API for Qwen CLI code generation",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint"""
    # Check if Qwen CLI is available
    try:
        result = subprocess.run(
            [QWEN_CLI_PATH, "--version"],
            capture_output=True,
            timeout=5
        )
        qwen_available = result.returncode == 0
    except Exception:
        qwen_available = False
    
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        workspace=str(WORKSPACE),
        qwen_available=qwen_available,
        timestamp=datetime.now().isoformat()
    )


@app.post("/generate", response_model=CodeResponse, tags=["Code"])
async def generate_code(request: CodeRequest):
    """
    Generate code from experiment blueprint.
    
    This endpoint:
    1. Parses the blueprint
    2. Generates appropriate code files
    3. Returns structured code
    
    **Example:**
    ```json
    {
        "blueprint": "# Experiment 1\\n\\nObjective: Improve accuracy...",
        "experiment_num": 1,
        "project": "Logistic_Regression"
    }
    ```
    """
    logger.info(f"Generating code for {request.project} experiment {request.experiment_num}")
    
    try:
        # Try to use Qwen CLI if available
        if _is_qwen_available():
            code_files = await _generate_with_qwen(request)
        else:
            logger.warning("Qwen CLI not available, using template generation")
            code_files = _generate_from_template(request)
        
        logger.info(f"Generated {len(code_files)} files")
        
        return CodeResponse(
            status="success",
            code_files=code_files,
            message=f"Generated {len(code_files)} files for {request.project} experiment {request.experiment_num}",
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Code generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/execute", response_model=ExecuteResponse, tags=["Execution"])
async def execute_code(request: ExecuteRequest):
    """
    Execute generated code.
    
    **Warning:** This executes arbitrary code. Use with caution.
    
    **Example:**
    ```json
    {
        "code_dir": "/path/to/code",
        "timeout": 300
    }
    ```
    """
    import time
    start_time = time.time()
    
    code_dir = Path(request.code_dir)
    
    if not code_dir.exists():
        raise HTTPException(status_code=404, detail=f"Directory {code_dir} not found")
    
    logger.info(f"Executing code in {code_dir}")
    
    try:
        # Find main Python file
        main_file = code_dir / "main.py"
        if not main_file.exists():
            # Try to find any .py file
            py_files = list(code_dir.glob("*.py"))
            if py_files:
                main_file = py_files[0]
            else:
                raise HTTPException(status_code=404, detail="No Python files found")
        
        # Execute
        result = subprocess.run(
            [sys.executable, str(main_file)],
            cwd=str(code_dir),
            capture_output=True,
            text=True,
            timeout=request.timeout
        )
        
        execution_time = (time.time() - start_time) * 1000
        
        return ExecuteResponse(
            status="success" if result.returncode == 0 else "error",
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
            execution_time_ms=execution_time
        )
        
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail=f"Execution timeout after {request.timeout}s")
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/save", tags=["Files"])
async def save_code(request: CodeRequest, background_tasks: BackgroundTasks):
    """
    Generate and save code to workspace.
    
    Code is saved to: `{workspace}/{project}/experiment{num}/`
    """
    project_dir = WORKSPACE / request.project / f"experiment{request.experiment_num}"
    project_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Saving code to {project_dir}")
    
    # Generate code
    code_files = _generate_from_template(request)
    
    # Save files
    saved_files = []
    for filename, content in code_files.items():
        file_path = project_dir / filename
        file_path.write_text(content)
        saved_files.append(str(file_path))
    
    return {
        "status": "success",
        "saved_files": saved_files,
        "directory": str(project_dir)
    }


@app.get("/projects", tags=["Projects"])
async def list_projects():
    """List all projects in workspace"""
    projects = []
    for project_dir in WORKSPACE.iterdir():
        if project_dir.is_dir():
            experiments = [d.name for d in project_dir.iterdir() if d.is_dir()]
            projects.append({
                "name": project_dir.name,
                "experiments": experiments,
                "experiment_count": len(experiments)
            })
    
    return {"status": "success", "projects": projects}


@app.delete("/projects/{project_name}", tags=["Projects"])
async def delete_project(project_name: str):
    """Delete a project and all its experiments"""
    project_dir = WORKSPACE / project_name
    
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project {project_name} not found")
    
    shutil.rmtree(project_dir)
    
    return {"status": "success", "message": f"Project {project_name} deleted"}


# ============================================================================
# Helper Functions
# ============================================================================

def _is_qwen_available() -> bool:
    """Check if Qwen CLI is available"""
    try:
        result = subprocess.run(
            [QWEN_CLI_PATH, "--version"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


async def _generate_with_qwen(request: CodeRequest) -> Dict[str, str]:
    """Generate code using Qwen CLI"""
    # Save blueprint to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(request.blueprint)
        blueprint_path = f.name
    
    try:
        # Run Qwen CLI
        result = subprocess.run(
            [QWEN_CLI_PATH, "generate", blueprint_path, "--output", "json"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            raise Exception(f"Qwen CLI error: {result.stderr}")
        
        # Parse Qwen output
        import json
        qwen_output = json.loads(result.stdout)
        
        return qwen_output.get("code_files", {})
        
    finally:
        # Cleanup
        os.unlink(blueprint_path)


def _generate_from_template(request: CodeRequest) -> Dict[str, str]:
    """Generate code from template (fallback when Qwen unavailable)"""
    
    exp_num = request.experiment_num
    project = request.project
    
    # Parse blueprint for context
    objective = _extract_objective(request.blueprint)
    approach = _extract_approach(request.blueprint)
    
    return {
        f"exp{exp_num}_data_loader.py": _generate_data_loader(project, objective),
        f"exp{exp_num}_model.py": _generate_model(project, approach),
        f"exp{exp_num}_evaluation.py": _generate_evaluation(project),
        f"exp{exp_num}_main.py": _generate_main(project, exp_num),
        "requirements.txt": _generate_requirements(),
        "README.md": _generate_readme(project, exp_num, objective)
    }


def _extract_objective(blueprint: str) -> str:
    """Extract objective from blueprint"""
    import re
    match = re.search(r'## 🎯 Objective\n(.*?)(?:\n\n|\n##|$)', blueprint, re.DOTALL)
    return match.group(1).strip() if match else "Improve model performance"


def _extract_approach(blueprint: str) -> str:
    """Extract approach from blueprint"""
    import re
    match = re.search(r'## 🧠 Proposed Approach\n(.*?)(?:\n\n|\n##|$)', blueprint, re.DOTALL)
    return match.group(1).strip() if match else "Standard ML pipeline"


def _generate_data_loader(project: str, objective: str) -> str:
    """Generate data loader code"""
    return f'''# Data Loader for {project} - Experiment
# Objective: {objective}

import pandas as pd
import numpy as np
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_data():
    """
    Load or generate dataset for {project}
    
    Returns:
        X_train, X_test, y_train, y_test
    """
    logger.info("Loading data...")
    
    # Generate synthetic classification data
    # Replace with actual data loading for production
    X, y = make_classification(
        n_samples=1200,
        n_features=20,
        n_informative=10,
        n_redundant=5,
        n_classes=2,
        random_state=42
    )
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    logger.info(f"Data loaded: {len(X_train)} train, {len(X_test)} test samples")
    
    return X_train, X_test, y_train, y_test


def save_data(X, y, path="data.npz"):
    """Save data to file"""
    np.savez(path, X=X, y=y)
    logger.info(f"Data saved to {path}")


def load_data_from_file(path="data.npz"):
    """Load data from file"""
    data = np.load(path)
    return data['X'], data['y']


if __name__ == "__main__":
    X_train, X_test, y_train, y_test = load_data()
    print(f"Train: {X_train.shape}, Test: {X_test.shape}")
'''


def _generate_model(project: str, approach: str) -> str:
    """Generate model code"""
    return f'''# Model Implementation for {project}
# Approach: {approach}

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.pipeline import Pipeline
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.preprocessing import StandardScaler
import logging
import joblib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_model(model_type="logistic", **kwargs):
    """
    Create ML model pipeline
    
    Args:
        model_type: Type of model (logistic, random_forest, xgboost)
        **kwargs: Model hyperparameters
    
    Returns:
        sklearn Pipeline
    """
    logger.info(f"Creating {model_type} model...")
    
    if model_type == "logistic":
        C = kwargs.get("C", 1.0)
        max_iter = kwargs.get("max_iter", 1000)
        
        model = Pipeline([
            ('feature_selection', SelectKBest(f_classif, k=10)),
            ('scaler', StandardScaler()),
            ('classifier', LogisticRegression(C=C, max_iter=max_iter, random_state=42))
        ])
        
    elif model_type == "random_forest":
        n_estimators = kwargs.get("n_estimators", 100)
        max_depth = kwargs.get("max_depth", 10)
        
        model = Pipeline([
            ('feature_selection', SelectKBest(f_classif, k=10)),
            ('scaler', StandardScaler()),
            ('classifier', RandomForestClassifier(
                n_estimators=n_estimators,
                max_depth=max_depth,
                random_state=42
            ))
        ])
        
    elif model_type == "xgboost":
        try:
            from xgboost import XGBClassifier
            
            n_estimators = kwargs.get("n_estimators", 100)
            max_depth = kwargs.get("max_depth", 6)
            learning_rate = kwargs.get("learning_rate", 0.1)
            
            model = Pipeline([
                ('feature_selection', SelectKBest(f_classif, k=10)),
                ('scaler', StandardScaler()),
                ('classifier', XGBClassifier(
                    n_estimators=n_estimators,
                    max_depth=max_depth,
                    learning_rate=learning_rate,
                    random_state=42
                ))
            ])
        except ImportError:
            logger.warning("XGBoost not available, using Random Forest")
            return create_model("random_forest", **kwargs)
    
    else:
        raise ValueError(f"Unknown model type: {model_type}")
    
    logger.info(f"Model created: {model}")
    
    return model


def save_model(model, path="best_model.pkl"):
    """Save model to file"""
    joblib.dump(model, path)
    logger.info(f"Model saved to {path}")


def load_model(path="best_model.pkl"):
    """Load model from file"""
    return joblib.load(path)


if __name__ == "__main__":
    # Test model creation
    model = create_model("logistic", C=0.1)
    print(model)
'''


def _generate_evaluation(project: str) -> str:
    """Generate evaluation code"""
    return f'''# Evaluation Script for {project}

import numpy as np
import json
import logging
from pathlib import Path
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, confusion_matrix
)
import matplotlib.pyplot as plt
import seaborn as sns

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def evaluate_model(model, X_test, y_test):
    """
    Evaluate model performance
    
    Args:
        model: Trained sklearn model
        X_test: Test features
        y_test: Test labels
    
    Returns:
        dict: Evaluation metrics
    """
    logger.info("Evaluating model...")
    
    # Predictions
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    
    # Metrics
    metrics = {{
        'accuracy': accuracy_score(y_test, y_pred),
        'precision': precision_score(y_test, y_pred),
        'recall': recall_score(y_test, y_pred),
        'f1': f1_score(y_test, y_pred),
        'roc_auc': roc_auc_score(y_test, y_proba)
    }}
    
    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred)
    
    logger.info(f"Accuracy: {{metrics['accuracy']:.4f}}")
    logger.info(f"F1 Score: {{metrics['f1']:.4f}}")
    logger.info(f"ROC AUC: {{metrics['roc_auc']:.4f}}")
    
    return {{
        'metrics': metrics,
        'confusion_matrix': cm.tolist(),
        'y_pred': y_pred.tolist(),
        'y_proba': y_proba.tolist()
    }}


def save_results(results, output_dir="results"):
    """Save evaluation results"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save metrics
    metrics_path = output_dir / "metrics.json"
    with open(metrics_path, 'w') as f:
        json.dump(results['metrics'], f, indent=2)
    logger.info(f"Metrics saved to {{metrics_path}}")
    
    # Save accuracy
    accuracy_path = output_dir / "accuracy.txt"
    with open(accuracy_path, 'w') as f:
        f.write(f"accuracy: {{results['metrics']['accuracy']:.4f}}\\n")
        f.write(f"f1: {{results['metrics']['f1']:.4f}}\\n")
        f.write(f"roc_auc: {{results['metrics']['roc_auc']:.4f}}\\n")
    logger.info(f"Accuracy saved to {{accuracy_path}}")
    
    # Plot confusion matrix
    plt.figure(figsize=(8, 6))
    sns.heatmap(
        results['confusion_matrix'],
        annot=True,
        fmt='d',
        cmap='Blues'
    )
    plt.title('Confusion Matrix')
    plt.ylabel('True Label')
    plt.xlabel('Predicted Label')
    plt.savefig(output_dir / "confusion_matrix.png")
    logger.info("Confusion matrix saved")


if __name__ == "__main__":
    # Test evaluation
    from exp_data_loader import load_data
    from exp_model import create_model
    from sklearn.model_selection import cross_val_score
    
    X_train, X_test, y_train, y_test = load_data()
    model = create_model("logistic", C=0.1)
    
    # Train
    model.fit(X_train, y_train)
    
    # Evaluate
    results = evaluate_model(model, X_test, y_test)
    save_results(results)
'''


def _generate_main(project: str, exp_num: int) -> str:
    """Generate main execution script"""
    return f'''# Main Execution Script for {project} - Experiment {exp_num}

import logging
import json
from pathlib import Path
import joblib

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run complete experiment pipeline"""
    logger.info("=" * 60)
    logger.info(f"Starting {project} - Experiment {exp_num}")
    logger.info("=" * 60)
    
    # Import modules
    from exp{exp_num}_data_loader import load_data
    from exp{exp_num}_model import create_model, save_model
    from exp{exp_num}_evaluation import evaluate_model, save_results
    
    # Step 1: Load data
    logger.info("\\n📊 Step 1: Loading data...")
    X_train, X_test, y_train, y_test = load_data()
    
    # Step 2: Create and train model
    logger.info("\\n🧠 Step 2: Training model...")
    model = create_model("logistic", C=0.1)
    model.fit(X_train, y_train)
    logger.info("Model trained successfully")
    
    # Step 3: Evaluate
    logger.info("\\n📈 Step 3: Evaluating model...")
    results = evaluate_model(model, X_test, y_test)
    
    # Step 4: Save results
    logger.info("\\n💾 Step 4: Saving results...")
    save_model(model, "best_model.pkl")
    save_results(results, "results")
    
    # Step 5: Summary
    logger.info("\\n" + "=" * 60)
    logger.info("✅ Experiment Complete!")
    logger.info(f"Accuracy: {{results['metrics']['accuracy']:.4f}}")
    logger.info(f"F1 Score: {{results['metrics']['f1']:.4f}}")
    logger.info(f"ROC AUC: {{results['metrics']['roc_auc']:.4f}}")
    logger.info("=" * 60)
    
    return results


if __name__ == "__main__":
    results = main()
'''


def _generate_requirements() -> str:
    """Generate requirements.txt"""
    return """scikit-learn==1.4.2
pandas==2.2.0
numpy==1.26.0
matplotlib==3.8.0
seaborn==0.13.0
joblib==1.3.2
"""


def _generate_readme(project: str, exp_num: int, objective: str) -> str:
    """Generate README.md"""
    return f'''# {project} - Experiment {exp_num}

## Objective
{objective}

## Files
- `exp{exp_num}_data_loader.py` - Data loading and preprocessing
- `exp{exp_num}_model.py` - Model definition and training
- `exp{exp_num}_evaluation.py` - Evaluation metrics and visualization
- `exp{exp_num}_main.py` - Main execution script

## Usage

### Install dependencies
```bash
pip install -r requirements.txt
```

### Run experiment
```bash
python exp{exp_num}_main.py
```

### Results
Results will be saved to the `results/` directory:
- `metrics.json` - All evaluation metrics
- `accuracy.txt` - Key metrics in text format
- `confusion_matrix.png` - Confusion matrix visualization
- `best_model.pkl` - Trained model

## Expected Output
```
Accuracy: 0.XXXX
F1 Score: 0.XXXX
ROC AUC: 0.XXXX
```
'''


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Run the Qwen CLI Service"""
    logger.info("Starting Qwen CLI Service...")
    logger.info(f"Workspace: {WORKSPACE}")
    logger.info(f"Qwen CLI: {QWEN_CLI_PATH}")
    logger.info("API docs available at: http://localhost:8081/docs")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8081,  # Changed from 8080 to avoid conflict
        log_level="info"
    )


if __name__ == "__main__":
    main()
