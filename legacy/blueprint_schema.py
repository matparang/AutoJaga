#!/usr/bin/env python3
"""
Blueprint Schema - Structured format for ML experiment specifications

This ensures AutoJaga outputs machine-readable blueprints that Qwen can follow.
"""

import random
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class AlgorithmSpec:
    """Algorithm specification with constraints"""
    name: str
    import_statement: str
    forbidden: List[str]


@dataclass
class Hyperparameters:
    """Model hyperparameters - use as dict instead"""
    pass


@dataclass
class SuccessMetric:
    """Success criteria for experiment"""
    metric: str
    target: str
    minimum: float


@dataclass
class Blueprint:
    """Complete experiment blueprint"""
    experiment_id: str
    algorithm: AlgorithmSpec
    hyperparameters: Dict[str, Any]
    rationale: str
    success_metric: SuccessMetric
    dataset: str
    validation_strategy: str
    created_at: str


# Algorithm import mapping
ALGORITHM_IMPORTS = {
    "RandomForestClassifier": "from sklearn.ensemble import RandomForestClassifier",
    "GradientBoostingClassifier": "from sklearn.ensemble import GradientBoostingClassifier",
    "XGBClassifier": "from xgboost import XGBClassifier",
    "AdaBoostClassifier": "from sklearn.ensemble import AdaBoostClassifier",
    "ExtraTreesClassifier": "from sklearn.ensemble import ExtraTreesClassifier",
    "LogisticRegression": "from sklearn.linear_model import LogisticRegression",
    "SGDClassifier": "from sklearn.linear_model import SGDClassifier",
    "KNeighborsClassifier": "from sklearn.neighbors import KNeighborsClassifier",
    "SVC": "from sklearn.svm import SVC",
    "GaussianNB": "from sklearn.naive_bayes import GaussianNB",
    "DecisionTreeClassifier": "from sklearn.tree import DecisionTreeClassifier",
}


def get_import_statement(algorithm_name: str) -> str:
    """Get correct import statement for algorithm"""
    return ALGORITHM_IMPORTS.get(
        algorithm_name,
        f"from sklearn.ensemble import {algorithm_name}"
    )


def create_blueprint(
    algorithm_name: str,
    forbidden_algorithms: List[str],
    hyperparameters: Dict[str, Any],
    rationale: str,
    target_accuracy: float = 0.825,
    dataset: str = "iris",
    experiment_id: str = None
) -> Blueprint:
    """
    Create a structured experiment blueprint.
    
    Args:
        algorithm_name: Exact algorithm class name (e.g., "RandomForestClassifier")
        forbidden_algorithms: List of algorithms to avoid
        hyperparameters: Dict of hyperparameter name → value
        rationale: Why this algorithm was chosen
        target_accuracy: Target accuracy to beat
        dataset: Dataset to use (default: iris)
        experiment_id: Optional custom ID
    
    Returns:
        Complete Blueprint object
    """
    if experiment_id is None:
        experiment_id = f"EXP-{random.randint(100, 999)}"
    
    return Blueprint(
        experiment_id=experiment_id,
        algorithm=AlgorithmSpec(
            name=algorithm_name,
            import_statement=get_import_statement(algorithm_name),
            forbidden=forbidden_algorithms
        ),
        hyperparameters=hyperparameters,
        rationale=rationale,
        success_metric=SuccessMetric(
            metric="accuracy",
            target=f"> {target_accuracy:.4f}",
            minimum=target_accuracy
        ),
        dataset=dataset,
        validation_strategy="train_test_split",
        created_at=datetime.now().isoformat()
    )


def blueprint_to_dict(blueprint: Blueprint) -> Dict[str, Any]:
    """Convert blueprint to dictionary for JSON serialization"""
    return {
        "experiment_id": blueprint.experiment_id,
        "algorithm": {
            "name": blueprint.algorithm.name,
            "import": blueprint.algorithm.import_statement,
            "forbidden": blueprint.algorithm.forbidden
        },
        "hyperparameters": blueprint.hyperparameters,
        "rationale": blueprint.rationale,
        "success_metric": {
            "metric": blueprint.success_metric.metric,
            "target": blueprint.success_metric.target,
            "minimum": blueprint.success_metric.minimum
        },
        "dataset": blueprint.dataset,
        "validation_strategy": blueprint.validation_strategy,
        "created_at": blueprint.created_at
    }


def dict_to_blueprint(data: Dict[str, Any]) -> Blueprint:
    """Convert dictionary back to Blueprint object"""
    return Blueprint(
        experiment_id=data["experiment_id"],
        algorithm=AlgorithmSpec(
            name=data["algorithm"]["name"],
            import_statement=data["algorithm"]["import"],
            forbidden=data["algorithm"]["forbidden"]
        ),
        hyperparameters=data["hyperparameters"],
        rationale=data["rationale"],
        success_metric=SuccessMetric(
            metric=data["success_metric"]["metric"],
            target=data["success_metric"]["target"],
            minimum=data["success_metric"]["minimum"]
        ),
        dataset=data["dataset"],
        validation_strategy=data["validation_strategy"],
        created_at=data["created_at"]
    )


# Pre-defined blueprints for common scenarios
BLUEPRINTS = {
    "random_forest": lambda: create_blueprint(
        algorithm_name="RandomForestClassifier",
        forbidden_algorithms=["LogisticRegression", "LinearRegression", "SGDClassifier"],
        hyperparameters={
            "n_estimators": 100,
            "max_depth": 10,
            "random_state": 42
        },
        rationale="Previous LR stuck at local optimum, need non-linear boundary"
    ),
    
    "gradient_boosting": lambda: create_blueprint(
        algorithm_name="GradientBoostingClassifier",
        forbidden_algorithms=["LogisticRegression"],
        hyperparameters={
            "n_estimators": 100,
            "learning_rate": 0.1,
            "max_depth": 3,
            "random_state": 42
        },
        rationale="Ensemble method with better generalization"
    ),
    
    "xgboost": lambda: create_blueprint(
        algorithm_name="XGBClassifier",
        forbidden_algorithms=["LogisticRegression"],
        hyperparameters={
            "n_estimators": 100,
            "max_depth": 6,
            "learning_rate": 0.1,
            "random_state": 42
        },
        rationale="XGBoost typically outperforms sklearn RF"
    ),
    
    "extra_trees": lambda: create_blueprint(
        algorithm_name="ExtraTreesClassifier",
        forbidden_algorithms=["LogisticRegression"],
        hyperparameters={
            "n_estimators": 100,
            "max_depth": 10,
            "random_state": 42
        },
        rationale="More randomization than RF, may find better solution"
    ),
}


def get_blueprint_for_scenario(scenario: str) -> Blueprint:
    """Get pre-defined blueprint for common scenarios"""
    if scenario not in BLUEPRINTS:
        raise ValueError(f"Unknown scenario: {scenario}. Available: {list(BLUEPRINTS.keys())}")
    return BLUEPRINTS[scenario]()


if __name__ == "__main__":
    # Test blueprint creation
    bp = create_blueprint(
        algorithm_name="RandomForestClassifier",
        forbidden_algorithms=["LogisticRegression"],
        hyperparameters={"n_estimators": 100, "max_depth": 10},
        rationale="Testing blueprint creation"
    )
    
    print("Blueprint created:")
    print(f"  ID: {bp.experiment_id}")
    print(f"  Algorithm: {bp.algorithm.name}")
    print(f"  Import: {bp.algorithm.import_statement}")
    print(f"  Forbidden: {bp.algorithm.forbidden}")
    print(f"  Hyperparams: {bp.hyperparameters}")
    print(f"  Rationale: {bp.rationale}")
    
    # Test serialization
    bp_dict = blueprint_to_dict(bp)
    print(f"\nSerialized: {len(str(bp_dict))} chars")
    
    # Test deserialization
    bp2 = dict_to_blueprint(bp_dict)
    print(f"\nDeserialized algorithm: {bp2.algorithm.name}")
    print(f"Match: {bp.algorithm.name == bp2.algorithm.name}")
