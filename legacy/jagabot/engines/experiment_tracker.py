"""
ExperimentTracker — structured hypothesis lifecycle management.

Adapted from nanobot/soul/meta_learning_engine.py (ExperimentTracker class).
Storage path: ~/.jagabot/workspace/experiments.json
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger

_DEFAULT_DIR = Path.home() / ".jagabot" / "workspace"


@dataclass
class Experiment:
    """A single structured experiment record."""
    experiment_id: str
    hypothesis: str
    method: str
    variables: dict[str, Any]
    result: Optional[dict[str, Any]] = None
    conclusion: str = ""
    falsified: bool = False
    status: str = "planned"  # planned → running → completed → reviewed
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "hypothesis": self.hypothesis,
            "method": self.method,
            "variables": self.variables,
            "result": self.result,
            "conclusion": self.conclusion,
            "falsified": self.falsified,
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Experiment:
        return cls(
            experiment_id=d["experiment_id"],
            hypothesis=d["hypothesis"],
            method=d["method"],
            variables=d.get("variables", {}),
            result=d.get("result"),
            conclusion=d.get("conclusion", ""),
            falsified=d.get("falsified", False),
            status=d.get("status", "planned"),
            created_at=d.get("created_at", datetime.now().isoformat()),
            completed_at=d.get("completed_at"),
        )


class ExperimentTracker:
    """Structured experiment logging with hypothesis tracking.

    Lifecycle: planned → running → completed → reviewed
    Max 200 experiments persisted.
    """

    MAX_EXPERIMENTS = 200

    def __init__(self, workspace: str | Path | None = None) -> None:
        ws = Path(workspace) if workspace else _DEFAULT_DIR
        ws.mkdir(parents=True, exist_ok=True)
        self._path = ws / "experiments.json"
        self._experiments: list[Experiment] = []
        self._load()

    def create(
        self,
        hypothesis: str,
        method: str,
        variables: dict[str, Any] | None = None,
    ) -> Experiment:
        """Register a new experiment."""
        exp = Experiment(
            experiment_id=f"exp-{random.randint(1000, 9999)}-{datetime.now().strftime('%H%M%S')}",
            hypothesis=hypothesis,
            method=method,
            variables=variables or {},
            status="planned",
        )
        self._experiments.append(exp)
        self._save()
        return exp

    def start(self, experiment_id: str) -> Experiment | None:
        """Mark an experiment as running."""
        exp = self._find(experiment_id)
        if exp:
            exp.status = "running"
            self._save()
        return exp

    def complete(
        self,
        experiment_id: str,
        result: dict[str, Any],
        conclusion: str,
        falsified: bool = False,
    ) -> Experiment | None:
        """Record experiment results and conclusion."""
        exp = self._find(experiment_id)
        if exp:
            exp.result = result
            exp.conclusion = conclusion
            exp.falsified = falsified
            exp.status = "completed"
            exp.completed_at = datetime.now().isoformat()
            self._save()
        return exp

    def review(self, experiment_id: str) -> Experiment | None:
        """Mark a completed experiment as reviewed."""
        exp = self._find(experiment_id)
        if exp and exp.status == "completed":
            exp.status = "reviewed"
            self._save()
        return exp

    def get(self, experiment_id: str) -> dict | None:
        exp = self._find(experiment_id)
        return exp.to_dict() if exp else None

    def list_experiments(
        self,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """List experiments, optionally filtered by status."""
        exps = self._experiments
        if status:
            exps = [e for e in exps if e.status == status]
        return [e.to_dict() for e in exps[-limit:]]

    def summary(self) -> dict[str, Any]:
        """Summary statistics of all experiments."""
        total = len(self._experiments)
        completed = [e for e in self._experiments if e.status in ("completed", "reviewed")]
        falsified = [e for e in completed if e.falsified]
        return {
            "total": total,
            "planned": sum(1 for e in self._experiments if e.status == "planned"),
            "running": sum(1 for e in self._experiments if e.status == "running"),
            "completed": len(completed),
            "reviewed": sum(1 for e in self._experiments if e.status == "reviewed"),
            "falsified": len(falsified),
            "supported": len(completed) - len(falsified),
            "falsification_rate": round(len(falsified) / len(completed), 4) if completed else 0.0,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _find(self, experiment_id: str) -> Experiment | None:
        for exp in self._experiments:
            if exp.experiment_id == experiment_id:
                return exp
        return None

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = [e.to_dict() for e in self._experiments[-self.MAX_EXPERIMENTS:]]
            self._path.write_text(json.dumps(data, indent=2))
        except Exception as exc:
            logger.warning("ExperimentTracker: save failed: {}", exc)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            self._experiments = [Experiment.from_dict(d) for d in data]
        except Exception as exc:
            logger.warning("ExperimentTracker: load failed: {}", exc)
