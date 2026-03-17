"""
Kernel Composition Pipeline — K1 → K3 → K7 chaining.

Orchestrates the three reasoning kernels in sequence:
1. K1 Bayesian: Uncertainty quantification with calibration
2. K3 Multi-Perspective: Bull/Bear/Buffet analysis with adaptive weights
3. K7 Evaluation: Result scoring and anomaly detection

Usage:
    from jagabot.kernels.composition import KernelPipeline
    
    pipeline = KernelPipeline(workspace=Path.home() / ".jagabot" / "workspace")
    
    result = pipeline.analyze(
        data={
            "topic": "AAPL analysis",
            "probability_below_target": 0.35,
            "current_price": 150,
            "target_price": 180
        },
        context={"market_sentiment": "positive"}
    )
    
    print(f"Confidence: {result['confidence']}%")
    print(f"Recommendation: {result['recommendation']}")
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


@dataclass
class PipelineResult:
    """Result of a kernel pipeline execution."""
    topic: str
    k1_beliefs: Dict[str, Any]
    k3_perspectives: Dict[str, Any]
    k7_evaluation: Dict[str, Any]
    confidence: float
    recommendation: str
    execution_time_ms: float
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "k1_beliefs": self.k1_beliefs,
            "k3_perspectives": self.k3_perspectives,
            "k7_evaluation": self.k7_evaluation,
            "confidence": round(self.confidence, 2),
            "recommendation": self.recommendation,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "timestamp": self.timestamp.isoformat()
        }


class KernelPipeline:
    """
    Automatic chaining of reasoning kernels: K1 → K3 → K7.
    
    This pipeline orchestrates the three v3.0 reasoning kernels:
    1. K1 Bayesian: Probabilistic reasoning with calibration
    2. K3 Multi-Perspective: Bull/Bear/Buffet analysis
    3. K7 Evaluation: Result quality assessment
    
    The pipeline:
    - Runs kernels in sequence with data passing
    - Calculates combined confidence score
    - Generates actionable recommendations
    - Tracks execution history for learning
    """
    
    def __init__(self, workspace: Path | str | None = None):
        self.workspace = Path(workspace) if workspace else Path.home() / ".jagabot" / "workspace"
        
        # Initialize kernels
        self.k1 = self._init_k1()
        self.k3 = self._init_k3()
        self.k7 = self._init_k7()
        
        # Execution history
        self.history: List[PipelineResult] = []
        self.max_history = 100
    
    def _init_k1(self):
        """Initialize K1 Bayesian kernel."""
        try:
            from jagabot.kernels.k1_bayesian import K1Bayesian
            return K1Bayesian(workspace=self.workspace)
        except ImportError as e:
            logger.warning(f"KernelPipeline: K1Bayesian not available: {e}")
            return None
    
    def _init_k3(self):
        """Initialize K3 Multi-Perspective kernel."""
        try:
            from jagabot.kernels.k3_perspective import K3MultiPerspective
            return K3MultiPerspective(workspace=self.workspace)
        except ImportError as e:
            logger.warning(f"KernelPipeline: K3MultiPerspective not available: {e}")
            return None
    
    def _init_k7(self):
        """Initialize K7 Evaluation kernel."""
        try:
            from jagabot.agent.tools.evaluation import EvaluationKernel
            return EvaluationKernel()
        except ImportError as e:
            logger.warning(f"KernelPipeline: EvaluationKernel not available: {e}")
            return None
    
    def analyze(
        self,
        data: Dict[str, Any],
        context: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """
        Run full K1 → K3 → K7 pipeline.
        
        Args:
            data: Input data for analysis
            context: Optional context (similar memories, entities, etc.)
        
        Returns:
            Combined result dict with confidence and recommendation
        """
        start_time = time.time()
        
        # Run K1: Bayesian reasoning
        k1_result = self._run_k1(data, context or {})
        
        # Run K3: Multi-perspective analysis
        k3_result = self._run_k3(k1_result, data, context or {})
        
        # Run K7: Evaluation
        k7_result = self._run_k7(k1_result, k3_result, data)
        
        # Calculate combined confidence
        confidence = self._calculate_confidence(k1_result, k3_result, k7_result)
        
        # Generate recommendation
        recommendation = self._generate_recommendation(k1_result, k3_result, k7_result, confidence)
        
        # Create result
        result = PipelineResult(
            topic=data.get("topic", "analysis"),
            k1_beliefs=k1_result,
            k3_perspectives=k3_result,
            k7_evaluation=k7_result,
            confidence=confidence,
            recommendation=recommendation,
            execution_time_ms=(time.time() - start_time) * 1000,
            timestamp=datetime.now()
        )
        
        # Store in history
        self.history.append(result)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        
        logger.info(f"KernelPipeline: analysis complete - {recommendation} ({confidence}%)")
        return result.to_dict()
    
    def _run_k1(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Run K1 Bayesian reasoning."""
        if self.k1 is None:
            return {"error": "K1 unavailable", "fallback": True}
        
        topic = data.get("topic", "analysis")
        evidence = data.get("evidence", {k: v for k, v in data.items() if k != "topic"})
        
        # Bayesian update
        result = self.k1.update(topic, evidence)
        
        # Add confidence interval
        posterior = result.get("posterior", 0.5)
        ci = self.k1.ci(posterior, n=100)
        result["confidence_interval"] = {
            "lower": ci[0],
            "upper": ci[1]
        }
        
        # Assess uncertainty if problem specified
        if "problem" in data or "question" in data:
            problem = data.get("problem") or data.get("question")
            assessment = self.k1.assess(problem)
            result["uncertainty_assessment"] = assessment
        
        return result
    
    def _run_k3(
        self,
        k1_result: Dict[str, Any],
        data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run K3 Multi-Perspective analysis."""
        if self.k3 is None:
            return {"error": "K3 unavailable", "fallback": True}
        
        # Prepare data for perspectives
        perspective_data = {
            "probability_below_target": data.get("probability_below_target", 0.5),
            "current_price": data.get("current_price", 100),
            "target_price": data.get("target_price", 100)
        }
        
        # Add optional fields
        for key in ["var_pct", "cvar_pct", "warnings", "risk_level", "intrinsic_value"]:
            if key in data:
                perspective_data[key] = data[key]
        
        # Get calibrated decision
        result = self.k3.calibrated_collapse(perspective_data)
        
        # Add K1 calibration if available
        if "posterior" in k1_result and not k1_result.get("error"):
            result["k1_posterior"] = k1_result["posterior"]
        
        return result
    
    def _run_k7(
        self,
        k1_result: Dict[str, Any],
        k3_result: Dict[str, Any],
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run K7 Evaluation."""
        if self.k7 is None:
            return {"error": "K7 unavailable", "fallback": True}
        
        # Define expected outcomes
        expected = {
            "has_beliefs": True,
            "has_perspectives": True,
            "has_recommendation": True,
            "confidence_in_range": True
        }
        
        # Define actual outcomes
        actual = {
            "has_beliefs": "posterior" in k1_result or not k1_result.get("error"),
            "has_perspectives": "verdict" in k3_result or not k3_result.get("error"),
            "has_recommendation": "recommendation" in k3_result,
            "confidence_in_range": 0 <= k3_result.get("confidence", 50) <= 100
        }
        
        # Evaluate result quality
        evaluation = self.k7.evaluate_result(expected, actual)
        
        # Add anomaly detection
        history_data = [h.to_dict() for h in self.history[-10:]]
        if history_data:
            anomaly = self.k7.detect_anomaly(
                {"confidence": k3_result.get("confidence", 50)},
                [{"k3_perspectives": {"confidence": h.get("confidence", 50)}} for h in history_data]
            )
            evaluation["anomaly"] = anomaly
        
        return evaluation
    
    def _calculate_confidence(
        self,
        k1_result: Dict[str, Any],
        k3_result: Dict[str, Any],
        k7_result: Dict[str, Any]
    ) -> float:
        """
        Calculate combined confidence score.
        
        Weights:
        - K1: 30% (Bayesian confidence)
        - K3: 40% (Perspective agreement)
        - K7: 30% (Evaluation score)
        """
        # Weight factors
        k1_weight = 0.30
        k3_weight = 0.40
        k7_weight = 0.30
        
        # Extract individual confidences
        k1_conf = 0.5  # Default
        if not k1_result.get("error"):
            posterior = k1_result.get("posterior", 0.5)
            # Convert posterior to confidence (0-100)
            k1_conf = abs(posterior - 0.5) * 2  # 0.5→0, 0/1→100
        
        k3_conf = k3_result.get("confidence", 50) / 100.0 if not k3_result.get("error") else 0.5
        
        k7_conf = k7_result.get("score", 0.5) if not k7_result.get("error") else 0.5
        
        # Weighted average
        combined = (k1_weight * k1_conf + k3_weight * k3_conf + k7_weight * k7_conf)
        
        return round(combined * 100, 2)
    
    def _generate_recommendation(
        self,
        k1_result: Dict[str, Any],
        k3_result: Dict[str, Any],
        k7_result: Dict[str, Any],
        confidence: float
    ) -> str:
        """Generate actionable recommendation."""
        # Get verdict from K3
        verdict = k3_result.get("verdict", "HOLD") if not k3_result.get("error") else "HOLD"
        
        # Determine strength based on confidence
        if confidence >= 80:
            strength = "STRONG"
        elif confidence >= 60:
            strength = "MODERATE"
        elif confidence >= 40:
            strength = "WEAK"
        else:
            strength = "VERY WEAK"
        
        # Add evaluation quality note
        quality = k7_result.get("score", 0.5) if not k7_result.get("error") else 0.5
        quality_note = ""
        if quality < 0.5:
            quality_note = " (low quality - verify inputs)"
        
        return f"{strength} {verdict}{quality_note} (confidence: {confidence}%)"
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline execution statistics."""
        if not self.history:
            return {"runs": 0}
        
        avg_confidence = sum(r.confidence for r in self.history) / len(self.history)
        avg_time = sum(r.execution_time_ms for r in self.history) / len(self.history)
        
        # Count by recommendation strength
        strength_counts = {}
        for r in self.history:
            strength = r.recommendation.split()[0] if r.recommendation else "UNKNOWN"
            strength_counts[strength] = strength_counts.get(strength, 0) + 1
        
        return {
            "runs": len(self.history),
            "avg_confidence": round(avg_confidence, 2),
            "avg_execution_time_ms": round(avg_time, 2),
            "recommendation_distribution": strength_counts,
            "last_recommendation": self.history[-1].recommendation if self.history else None
        }
    
    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent pipeline execution history."""
        return [r.to_dict() for r in self.history[-limit:]]
    
    def clear_history(self):
        """Clear execution history."""
        self.history.clear()


class KernelPipelineTool:
    """
    Tool wrapper for KernelPipeline.
    Can be used as a jagabot tool for kernel composition.
    """
    
    def __init__(self, workspace: Path | str | None = None):
        self.pipeline = KernelPipeline(workspace)
    
    async def execute(self, action: str, **kwargs) -> str:
        """
        Execute kernel pipeline action.
        
        Args:
            action: One of: analyze, stats, history, clear
            **kwargs: Action-specific parameters
        
        Returns:
            JSON string result
        """
        import json
        
        if action == "analyze":
            data = kwargs.get("data", {})
            context = kwargs.get("context", {})
            result = self.pipeline.analyze(data, context)
            return json.dumps(result)
        
        elif action == "stats":
            result = self.pipeline.get_stats()
            return json.dumps(result)
        
        elif action == "history":
            limit = kwargs.get("limit", 10)
            result = self.pipeline.get_history(limit)
            return json.dumps({"history": result, "count": len(result)})
        
        elif action == "clear":
            self.pipeline.clear_history()
            return json.dumps({"cleared": True})
        
        else:
            return json.dumps({"error": f"Unknown action: {action}. Use analyze|stats|history|clear."})
