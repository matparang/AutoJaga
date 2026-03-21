"""
Latent Reasoning Engine — Information-theoretic uncertainty tracking.

Tracks reasoning state across multiple hypotheses/perspectives using:
  - Entropy calculation (disagreement measure)
  - Curiosity gap scoring (knowledge gap detection)
  - Confidence calibration via BrierScorer
  - Belief updates via BeliefEngine

Flow:
  1. Collect hypotheses/perspectives from upstream engines
  2. Compute entropy across confidence distribution
  3. Score curiosity gaps (what don't we know?)
  4. Calibrate confidence via BrierScorer.trust_score()
  5. Update beliefs via BeliefEngine.update_belief()
  6. Output: reasoning state + uncertainty annotation

Wire into:
  - k3_perspective: entropy across bull/bear/buffet
  - CognitiveStack: latent state as planning context
  - session_writer: latent quality scoring
  - FluidDispatcher: RESEARCH profile engine
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger


# ── Data structures ────────────────────────────────────────────────

@dataclass
class Hypothesis:
    """A single hypothesis with confidence weight."""
    text: str = ""
    confidence: float = 0.5  # 0-1
    source: str = ""  # "bull", "bear", "buffet", "hypothesis_engine", etc.
    evidence_for: list[str] = field(default_factory=list)
    evidence_against: list[str] = field(default_factory=list)


@dataclass
class ReasoningState:
    """Complete latent reasoning state."""
    entropy: float = 0.0  # 0-1, higher = more uncertainty
    depth_reached: int = 0
    converged: bool = False
    best: Optional[Hypothesis] = None
    alternatives: list[Hypothesis] = field(default_factory=list)
    curiosity_gap: float = 0.0  # 0-1, higher = more unknown
    clarify_question: str = ""
    hypotheses: list[Hypothesis] = field(default_factory=list)
    computed_at: str = field(default_factory=lambda: datetime.now().isoformat())


# ── Entropy calculation ────────────────────────────────────────────

def _normalize_confidences(hypotheses: list[Hypothesis]) -> list[float]:
    """Normalize confidences to sum to 1.0 for entropy calculation."""
    if not hypotheses:
        return []
    
    total = sum(h.confidence for h in hypotheses)
    if total == 0:
        return [1.0 / len(hypotheses)] * len(hypotheses)
    
    return [h.confidence / total for h in hypotheses]


def _calculate_entropy(hypotheses: list[Hypothesis]) -> float:
    """
    Calculate Shannon entropy across hypothesis confidence distribution.
    
    Returns:
        0.0 = complete certainty (one hypothesis has 100% confidence)
        1.0 = maximum uncertainty (all hypotheses equally likely)
    """
    if not hypotheses:
        return 0.0
    
    probs = _normalize_confidences(hypotheses)
    
    # Shannon entropy: H = -sum(p * log2(p))
    entropy = 0.0
    for p in probs:
        if p > 0:
            entropy -= p * math.log2(p)
    
    # Normalize to 0-1 range (max entropy = log2(n) for n hypotheses)
    n = len(hypotheses)
    max_entropy = math.log2(n) if n > 1 else 1.0
    
    return entropy / max_entropy if max_entropy > 0 else 0.0


# ── Curiosity gap scoring ─────────────────────────────────────────

def _score_curiosity_gap(
    hypotheses: list[Hypothesis],
    context: str = "",
) -> float:
    """
    Score how much we don't know (curiosity gap).
    
    High gap when:
    - Low total confidence across all hypotheses
    - High entropy (disagreement)
    - Missing key information in context
    
    Returns:
        0.0 = we know enough
        1.0 = significant knowledge gap
    """
    if not hypotheses:
        return 1.0  # Complete gap
    
    # Factor 1: Average confidence (lower = more gap)
    avg_conf = sum(h.confidence for h in hypotheses) / len(hypotheses)
    confidence_gap = 1.0 - avg_conf
    
    # Factor 2: Entropy (higher = more gap)
    entropy = _calculate_entropy(hypotheses)
    
    # Factor 3: Context length (shorter = potentially more gap)
    context_factor = min(1.0, 100 / max(len(context), 1))
    
    # Weighted combination
    gap = (0.5 * confidence_gap) + (0.3 * entropy) + (0.2 * context_factor)
    
    return min(1.0, max(0.0, gap))


# ── Main engine ───────────────────────────────────────────────────

class LatentReasoning:
    """
    Latent Reasoning Engine for uncertainty-aware reasoning.
    
    Usage:
        lr = LatentReasoning(workspace=Path('/root/.jagabot/workspace'))
        state = await lr.reason(query="Should I invest in NVDA?", context=...)
        
        if state.entropy > 0.7:
            # High uncertainty — hedge response
            return f"There is significant disagreement... (entropy={state.entropy:.2f})"
        else:
            # Low uncertainty — confident response
            return f"Based on analysis... (confidence={state.best.confidence:.0%})"
    """
    
    def __init__(
        self,
        workspace: Path,
        hypothesis_engine: Optional[object] = None,
        brier_scorer: Optional[object] = None,
        belief_engine: Optional[object] = None,
        curiosity: Optional[object] = None,
        config: Optional[dict] = None,
    ) -> None:
        self.workspace = Path(workspace)
        self.hypothesis_engine = hypothesis_engine
        self.brier = brier_scorer
        self.belief_engine = belief_engine
        self.curiosity = curiosity
        self.config = config or {}
        
        # Thresholds
        self.HIGH_ENTROPY = self.config.get("high_entropy_threshold", 0.6)
        self.MAX_DEPTH = self.config.get("max_depth", 3)
        self.CONVERGENCE_DELTA = self.config.get("convergence_delta", 0.05)
        
        logger.debug("LatentReasoning initialized")
    
    async def reason(
        self,
        query: str,
        context: str = "",
        runner: Optional[object] = None,
        force_depth: Optional[int] = None,
    ) -> ReasoningState:
        """
        Main reasoning entry point.
        
        Args:
            query: The question or task
            context: Additional context
            runner: Agent runner for tool access
            force_depth: Override max depth for quick passes
            
        Returns:
            ReasoningState with entropy, confidence, and uncertainty annotation
        """
        depth_limit = force_depth if force_depth is not None else self.MAX_DEPTH
        
        logger.debug(f"LatentReasoning [{id(self):04x}]: starting (depth_limit={depth_limit})")
        
        # Enrich context with curiosity gaps
        if self.curiosity:
            try:
                gaps = self.curiosity.get_top_targets(n=3)
                if gaps:
                    gap_context = "\n".join(
                        f"- Known gap: {getattr(g, 'gap_description', str(g))[:80]}"
                        for g in gaps
                        if getattr(g, 'curiosity_score', 0) > 0.5
                    )
                    if gap_context:
                        context = context + "\n\nKnown knowledge gaps:\n" + gap_context
                        logger.debug(f"Added {len(gaps)} curiosity gaps to context")
            except Exception as e:
                logger.debug(f"Curiosity enrichment failed: {e}")
        
        # Phase 1: Instinct pass — generate initial hypotheses
        hypotheses = await self._instinct_pass(query, context, runner)
        logger.debug(f"instinct → {len(hypotheses)} hypotheses")
        
        if not hypotheses:
            # Fallback: create single hypothesis from query
            hypotheses = [Hypothesis(text=query, confidence=0.5, source="fallback")]
        
        # Phase 2: Compute entropy
        entropy = _calculate_entropy(hypotheses)
        logger.debug(f"entropy = {entropy:.3f}")
        
        # Phase 3: Iterative refinement (if high entropy)
        depth = 1
        prev_entropy = entropy
        
        while entropy > self.HIGH_ENTROPY and depth < depth_limit:
            depth += 1
            logger.debug(f"depth {depth} → refining...")
            
            # Refine hypotheses
            hypotheses = await self._refine_pass(
                query, context, hypotheses, runner
            )
            
            new_entropy = _calculate_entropy(hypotheses)
            logger.debug(f"depth {depth} → {len(hypotheses)} hypotheses, entropy={new_entropy:.3f}")
            
            # Check convergence
            if abs(new_entropy - prev_entropy) < self.CONVERGENCE_DELTA:
                logger.debug(f"converged at depth {depth}")
                entropy = new_entropy
                break
            
            prev_entropy = entropy
            entropy = new_entropy
        
        # Phase 4: Build reasoning state
        best = max(hypotheses, key=lambda h: h.confidence) if hypotheses else None
        alternatives = [h for h in hypotheses if h != best]
        
        # Curiosity gap scoring
        curiosity_gap = _score_curiosity_gap(hypotheses, context)
        
        # Generate clarifying question if high uncertainty
        clarify_question = ""
        if entropy > self.HIGH_ENTROPY:
            clarify_question = self._generate_clarifying_question(
                query, hypotheses, curiosity_gap
            )
        
        # Calibrate confidence via BrierScorer if available
        if self.brier and best:
            try:
                trust = self.brier.trust_score("general", "reasoning")
                if trust:
                    best.confidence = best.confidence * trust
                    logger.debug(f"confidence calibrated via BrierScorer: {best.confidence:.2f}")
            except Exception as e:
                logger.debug(f"Brier calibration failed: {e}")
        
        # Update belief engine if available
        if self.belief_engine and best:
            try:
                self.belief_engine.update_belief(
                    domain="reasoning",
                    confidence=best.confidence,
                    entropy=entropy,
                )
            except Exception as e:
                logger.debug(f"Belief update failed: {e}")
        
        state = ReasoningState(
            entropy=entropy,
            depth_reached=depth,
            converged=depth < depth_limit or entropy <= self.HIGH_ENTROPY,
            best=best,
            alternatives=alternatives,
            curiosity_gap=curiosity_gap,
            clarify_question=clarify_question,
            hypotheses=hypotheses,
        )
        
        logger.debug(
            f"LatentReasoning [{id(self):04x}]: complete — "
            f"entropy={entropy:.3f}, converged={state.converged}, depth={depth}"
        )
        
        return state
    
    async def _instinct_pass(
        self,
        query: str,
        context: str,
        runner: Optional[object],
    ) -> list[Hypothesis]:
        """
        Generate initial hypotheses from instinct/retrieval.
        
        Uses HypothesisEngine if available, otherwise falls back to retrieval.
        """
        hypotheses = []
        
        # Try HypothesisEngine first
        if self.hypothesis_engine:
            try:
                generated = self.hypothesis_engine.generate(
                    domain="all",
                    topic=query[:50],
                )
                for h in generated:
                    hypotheses.append(Hypothesis(
                        text=h.statement if hasattr(h, 'statement') else str(h),
                        confidence=h.confidence if hasattr(h, 'confidence') else 0.5,
                        source="hypothesis_engine",
                    ))
                logger.debug(f"HypothesisEngine generated {len(generated)} hypotheses")
            except Exception as e:
                logger.debug(f"HypothesisEngine instinct pass failed: {e}")
        
        # Fallback: try to get from k3_perspective via runner
        if not hypotheses and runner:
            try:
                # Check if runner has k3 attribute
                k3 = getattr(runner, 'k3', None)
                if k3 and hasattr(k3, 'get_all_perspectives'):
                    perspectives = k3.get_all_perspectives({"query": query})
                    for name, result in perspectives.items():
                        if isinstance(result, dict) and "verdict" in result:
                            hypotheses.append(Hypothesis(
                                text=f"{name}: {result.get('verdict', '')}",
                                confidence=float(result.get('confidence', 0.5)),
                                source=name,
                            ))
                    logger.debug(f"k3_perspective generated {len(hypotheses)} hypotheses")
            except Exception as e:
                logger.debug(f"k3_perspective instinct pass failed: {e}")
        
        return hypotheses
    
    async def _refine_pass(
        self,
        query: str,
        context: str,
        hypotheses: list[Hypothesis],
        runner: Optional[object],
    ) -> list[Hypothesis]:
        """
        Refine hypotheses through deeper reasoning.
        
        In future: use web search, additional data sources, or adversarial testing.
        For now: adjust confidences based on context match.
        """
        # Simple refinement: boost hypotheses that match context better
        context_lower = context.lower()
        
        for h in hypotheses:
            text_lower = h.text.lower()
            # Boost if hypothesis terms appear in context
            matches = sum(1 for word in text_lower.split() if len(word) > 4 and word in context_lower)
            if matches > 0:
                h.confidence = min(1.0, h.confidence * (1.0 + 0.1 * matches))
        
        # Normalize confidences after refinement
        total = sum(h.confidence for h in hypotheses)
        if total > 0:
            for h in hypotheses:
                h.confidence = h.confidence / total
        
        return hypotheses
    
    def _generate_clarifying_question(
        self,
        query: str,
        hypotheses: list[Hypothesis],
        curiosity_gap: float,
    ) -> str:
        """Generate a clarifying question when uncertainty is high."""
        if curiosity_gap > 0.7:
            return "What specific aspect would you like me to focus on?"
        elif len(hypotheses) >= 2:
            h1, h2 = hypotheses[0], hypotheses[1]
            return f"Should I prioritize {h1.source} or {h2.source} perspective?"
        else:
            return "Could you provide more context about your goals?"
    
    def _calculate_entropy(self, hypotheses: list[Hypothesis]) -> float:
        """Wrapper for entropy calculation (for external calls)."""
        return _calculate_entropy(hypotheses)


# ── Convenience functions ─────────────────────────────────────────

def compute_disagreement(perspectives: dict[str, dict]) -> str:
    """
    Compute disagreement level from k3_perspective output.
    
    Args:
        perspectives: {"bull": {...}, "bear": {...}, "buffet": {...}}
        
    Returns:
        "LOW", "MEDIUM", or "HIGH"
    """
    if not perspectives:
        return "LOW"
    
    # Extract confidences
    confidences = []
    for name, result in perspectives.items():
        if isinstance(result, dict) and "confidence" in result:
            confidences.append(float(result["confidence"]))
    
    if len(confidences) < 2:
        return "LOW"
    
    # Compute entropy
    hypotheses = [Hypothesis(text=name, confidence=c) for name, c in zip(perspectives.keys(), confidences)]
    entropy = _calculate_entropy(hypotheses)
    
    if entropy > 0.7:
        return "HIGH"
    elif entropy > 0.4:
        return "MEDIUM"
    else:
        return "LOW"
