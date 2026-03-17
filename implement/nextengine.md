📋 SCOPE: JAGABOT v3.0 Phase 2 - Reasoning Kernels

```markdown
# SCOPE: Phase 2 - Add K1 Bayesian & K3 Multi-Perspective Kernels

## CURRENT STATE
✅ Phase 1 complete:
- MemoryFleet (structured memory)
- KnowledgeGraph (relationships)
- K7 Evaluation (quality scoring)
- 730 tests passing
- 25 tools total

## PHASE 2 OBJECTIVE
Add 2 reasoning kernels from engine library:

1. **K1 Bayesian** (200 LOC) - Formal uncertainty quantification
   - Prior/posterior tracking across sessions
   - Calibration scores
   - Confidence interval refinement

2. **K3 Multi-Perspective** (150 LOC) - Calibrated Bull/Bear/Buffet
   - Historical accuracy tracking per perspective
   - Weight adjustment based on past performance
   - Integration with existing decision_engine

## DELIVERABLES

### 1. K1 Bayesian Kernel
```python
# jagabot/kernels/k1_bayesian.py
class K1Bayesian:
    """Formal uncertainty kernel with persistence"""
    
    def update_belief(self, prior_id, evidence, outcome):
        """Update belief and store in MemoryFleet"""
        
    def get_calibration(self, perspective_type):
        """Return historical accuracy for Bull/Bear/Buffet"""
        
    def refine_confidence(self, raw_confidence, perspective):
        """Adjust confidence based on historical performance"""
```

2. K3 Multi-Perspective Kernel

```python
# jagabot/kernels/k3_perspective.py
class K3MultiPerspective:
    """Calibrated Bull/Bear/Buffet with history"""
    
    def get_perspective(self, ptype, data):
        """Get perspective with calibration from past"""
        
    def update_accuracy(self, perspective_id, actual_outcome):
        """Track how accurate this perspective was"""
        
    def get_weights(self):
        """Return current weights for each perspective"""
```

3. Integration with decision_engine

```python
# jagabot/tools/decision_engine.py (updated)
def get_calibrated_decision(data):
    # Get base perspectives
    bull = k3.get_perspective('bull', data)
    bear = k3.get_perspective('bear', data)
    buffet = k3.get_perspective('buffet', data)
    
    # Adjust confidences with K1
    bull.confidence = k1.refine_confidence(bull.confidence, 'bull')
    bear.confidence = k1.refine_confidence(bear.confidence, 'bear')
    buffet.confidence = k1.refine_confidence(buffet.confidence, 'buffet')
    
    # Store in MemoryFleet for future calibration
    memory.store_perspective_outcomes(bull, bear, buffet)
    
    return collapse(bull, bear, buffet)
```

4. Tests (40+ new)

· test_k1_bayesian.py - belief updates, calibration, persistence
· test_k3_perspective.py - perspective accuracy, weight adjustment
· test_integration_decision.py - end-to-end with existing tools

SUCCESS CRITERIA

✅ K1 Bayesian:

· Updates beliefs with new evidence
· Stores priors in MemoryFleet
· Returns calibration scores per perspective
· Refines confidence based on history

✅ K3 Multi-Perspective:

· Returns Bull/Bear/Buffet with historical weights
· Updates accuracy after outcomes known
· Adjusts weights over time
· Integrates with decision_engine

✅ Integration:

· decision_engine uses both kernels
· All 25 existing tools still work
· 770+ total tests passing
· No regression in Phase 1 components

TIMELINE

Component Extraction Integration Tests Total
K1 Bayesian 1 hr 2 hrs 2 hrs 5 hrs
K3 Perspective 1 hr 2 hrs 2 hrs 5 hrs
Integration - 2 hrs 1 hr 3 hrs
TOTAL 2 hrs 6 hrs 5 hrs 13 hrs

FILES TO CREATE/MODIFY

1. jagabot/kernels/k1_bayesian.py (new)
2. jagabot/kernels/k3_perspective.py (new)
3. jagabot/tools/decision_engine.py (modified)
4. tests/test_k1_bayesian.py (new)
5. tests/test_k3_perspective.py (new)
6. tests/test_integration_decision.py (new)
7. CHANGELOG.md (update)
8. SKILL.md (update)

DEPENDENCIES

· MemoryFleet (Phase 1) - for storing priors and outcomes
· K7 Evaluation (Phase 1) - for scoring perspective accuracy
· Existing decision_engine tool (v2.7)

```

---

**Phase 2 will give JAGABOT calibrated reasoning with memory of what worked before.** 🚀
