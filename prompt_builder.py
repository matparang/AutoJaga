#!/usr/bin/env python3
"""
Prompt Builder - Convert structured blueprints to ironclad Qwen prompts

This ensures Qwen generates EXACTLY the algorithm specified in the blueprint.
"""

from typing import Dict, Any, List
from blueprint_schema import Blueprint, blueprint_to_dict


def build_qwen_prompt(blueprint: Dict[str, Any]) -> str:
    """
    Transform structured blueprint into ironclad Qwen prompt.
    
    Keys:
    - Explicit algorithm requirements
    - Negative constraints (forbidden algorithms)
    - Exact hyperparameters
    - Required code structure
    - Output format specification
    
    Args:
        blueprint: Dictionary from blueprint_schema
    
    Returns:
        Formatted prompt string
    """
    algorithm = blueprint["algorithm"]["name"]
    import_line = blueprint["algorithm"]["import"]
    forbidden = blueprint["algorithm"]["forbidden"]
    hyperparams = blueprint["hyperparameters"]
    dataset = blueprint.get("dataset", "iris")
    
    # Build hyperparameter lines
    hyperparam_lines = "\n".join(
        f"  - {k}: {repr(v)}" for k, v in hyperparams.items()
    )
    
    # Build forbidden list
    forbidden_str = ", ".join(forbidden)
    
    # Build required model instantiation
    model_args = ", ".join(f"{k}={repr(v)}" for k, v in hyperparams.items())
    
    prompt = f"""
You are a Python ML engineer. Generate COMPLETE, RUNNABLE code.

============================================================
TASK: Classification experiment
============================================================

REQUIRED ALGORITHM: {algorithm}
REQUIRED IMPORT: {import_line}

HYPERPARAMETERS (use EXACTLY these):
{hyperparam_lines}

============================================================
STRICT CONSTRAINTS (NEVER violate these):
============================================================
FORBIDDEN algorithms: {forbidden_str}
DO NOT use LogisticRegression under any circumstance
DO NOT simplify to a different algorithm
DO NOT add comments suggesting alternative approaches
DO NOT include any code after the accuracy print statement

============================================================
REQUIRED in your code:
============================================================
1. `{import_line}`
2. `model = {algorithm}({model_args})`
3. `X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)`
4. `model.fit(X_train, y_train)`
5. `y_pred = model.predict(X_test)`
6. `accuracy = accuracy_score(y_test, y_pred)`
7. `print(f"ACCURACY: {{accuracy:.4f}}")`  <- EXACT this format

============================================================
DATASET: Use {dataset} dataset (sklearn.datasets.load_{dataset})
OUTPUT: Only Python code, no explanations
============================================================

Generate the complete Python code now:
```python
"""
    
    return prompt


def build_escalated_prompt(
    blueprint: Dict[str, Any],
    attempt: int,
    previous_error: str = None
) -> str:
    """
    Build increasingly forceful prompt with each failed attempt.
    
    Args:
        blueprint: Original blueprint
        attempt: Which attempt this is (2, 3, etc.)
        previous_error: Error from validator
    
    Returns:
        Escalated prompt string
    """
    base_prompt = build_qwen_prompt(blueprint)
    
    algorithm = blueprint["algorithm"]["name"]
    import_line = blueprint["algorithm"]["import"]
    forbidden = blueprint["algorithm"]["forbidden"]
    hyperparams = blueprint["hyperparameters"]
    model_args = ", ".join(f"{k}={repr(v)}" for k, v in hyperparams.items())
    
    if attempt == 2:
        escalation = f"""

🚨 CRITICAL FEEDBACK:
Previous attempt used WRONG algorithm.
You MUST use {algorithm}. This is non-negotiable.

ERROR: {previous_error or "Wrong algorithm detected"}

REMEMBER:
- FORBIDDEN: {', '.join(forbidden)}
- REQUIRED: {algorithm} ONLY
"""
    
    elif attempt >= 3:
        escalation = f"""

🚨🚨 FINAL WARNING - MANDATORY REQUIREMENTS:

You MUST start your code with EXACTLY these lines:
```python
{import_line}
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

model = {algorithm}({model_args})
```

ANY OTHER ALGORITHM = WRONG ANSWER = FAILURE
DO NOT use: {', '.join(forbidden)}
ONLY use: {algorithm}

This is your final attempt. Get it right.
"""
    
    else:
        escalation = ""
    
    return base_prompt + escalation


def build_quick_fix_prompt(
    algorithm_name: str,
    forbidden: List[str],
    hyperparams: Dict[str, Any]
) -> str:
    """
    Quick fix prompt for immediate testing without full blueprint.
    
    This is the "10-minute fix" from Emsamble.md
    """
    import_line = f"from sklearn.ensemble import {algorithm_name}" if "Forest" in algorithm_name or "Boost" in algorithm_name else f"from sklearn.linear_model import {algorithm_name}"
    model_args = ", ".join(f"{k}={repr(v)}" for k, v in hyperparams.items())
    
    return f"""
Generate Python ML classification code using ONLY {algorithm_name}.

REQUIRED:
1. First line: {import_line}
2. Model: model = {algorithm_name}({model_args})
3. Train: model.fit(X_train, y_train)
4. Predict: y_pred = model.predict(X_test)
5. Accuracy: print(f"ACCURACY: {{accuracy:.4f}}")

FORBIDDEN (NEVER use): {', '.join(forbidden)}

DO NOT simplify to LogisticRegression.
DO NOT use any other algorithm.
ONLY use {algorithm_name}.

Generate code now:
```python
"""


if __name__ == "__main__":
    # Test prompt building
    test_blueprint = {
        "experiment_id": "EXP-003",
        "algorithm": {
            "name": "RandomForestClassifier",
            "import": "from sklearn.ensemble import RandomForestClassifier",
            "forbidden": ["LogisticRegression", "LinearRegression"]
        },
        "hyperparameters": {
            "n_estimators": 100,
            "max_depth": 10,
            "random_state": 42
        },
        "rationale": "Previous LR stuck at 0.825",
        "success_metric": {
            "metric": "accuracy",
            "target": "> 0.8250",
            "minimum": 0.83
        },
        "dataset": "iris",
        "validation_strategy": "train_test_split"
    }
    
    prompt = build_qwen_prompt(test_blueprint)
    print("=== BASE PROMPT ===")
    print(prompt[:500], "...")
    print("\n=== PROMPT LENGTH ===")
    print(f"{len(prompt)} characters")
    
    # Test escalation
    escalated = build_escalated_prompt(test_blueprint, attempt=2, previous_error="Found LogisticRegression")
    print("\n=== ESCALATED PROMPT ===")
    print(escalated[500:1000], "...")
