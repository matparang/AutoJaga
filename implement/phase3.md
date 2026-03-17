📋 SCOPE PROMPT: JAGABOT v3.0 Phase 3 - MetaLearningEngine

```markdown
# SCOPE: Phase 3 - Add MetaLearningEngine for Outcome Learning

## CURRENT STATE
✅ Phase 1 & 2 complete:
- MemoryFleet (structured memory)
- KnowledgeGraph (relationships)
- K7 Evaluation (quality scoring)
- K1 Bayesian (uncertainty)
- K3 Multi-Perspective (calibrated reasoning)
- 770+ tests passing
- 25 tools total

⏳ Phase 3 target: MetaLearningEngine (661 LOC from engine library)

## WHAT META LEARNING ENGINE DOES
Tracks every prediction vs actual outcome to improve future accuracy:

```yaml
capabilities:
  - Store prediction outcomes (what JAGABOT said vs what happened)
  - Calculate accuracy metrics per perspective (Bull/Bear/Buffet)
  - Auto-adjust weights in decision_engine
  - Update K1 Bayesian priors based on historical performance
  - Detect which signals work in which market conditions
  - Generate "lessons learned" reports
  - Feed patterns into KnowledgeGraph
```

DEPENDENCIES

· MemoryFleet (stores prediction outcomes)
· K7 Evaluation (scores prediction quality)
· K1 Bayesian (updates priors)
· K3 Multi-Perspective (adjusts weights)
· decision_engine (uses calibrated weights)

INTEGRATION POINTS

1. Prediction Tracking Hook

```python
# jagabot/core/meta_learning.py
class MetaLearningEngine:
    def __init__(self):
        self.memory = MemoryFleet()
        self.k7 = K7Evaluation()
        self.k1 = K1Bayesian()
        self.k3 = K3MultiPerspective()
    
    def track_prediction(self, analysis_id, prediction_data, actual_outcome):
        """
        Store prediction vs actual for learning
        Called after outcome is known (user feedback / market data)
        """
        # 1. Store in MemoryFleet
        self.memory.store_outcome(analysis_id, {
            'prediction': prediction_data,
            'actual': actual_outcome,
            'timestamp': now()
        })
        
        # 2. Calculate accuracy score
        accuracy = self.k7.evaluate_prediction(prediction_data, actual_outcome)
        
        # 3. Update K1 priors
        self.k1.update_calibration(
            perspective=prediction_data['perspective'],
            confidence=prediction_data['confidence'],
            was_correct=accuracy > 0.7
        )
        
        # 4. Adjust K3 weights
        self.k3.adjust_weight(
            perspective=prediction_data['perspective'],
            delta=accuracy - 0.5  # Positive if better than random
        )
        
        # 5. Store pattern in KnowledgeGraph
        self.graph.add_relationship(
            from_node=f"signal_{prediction_data['signal_type']}",
            to_node=f"outcome_{actual_outcome}",
            weight=accuracy
        )
```

2. Decision Engine Integration

```python
# jagabot/tools/decision_engine.py (updated)
def get_calibrated_decision(data):
    # Get base perspectives with current weights
    bull = k3.get_perspective('bull', data)
    bear = k3.get_perspective('bear', data)
    buffet = k3.get_perspective('buffet', data)
    
    # Adjust confidences based on historical accuracy
    bull.confidence = k1.calibrate(bull.confidence, 'bull')
    bear.confidence = k1.calibrate(bear.confidence, 'bear')
    buffet.confidence = k1.calibrate(buffet.confidence, 'buffet')
    
    # Store prediction for future learning
    analysis_id = generate_id()
    meta.track_prediction(analysis_id, {
        'perspective': 'bull',
        'confidence': bull.confidence,
        'signal_type': data.signal_type
    }, pending=True)  # Mark as pending outcome
    
    return collapse(bull, bear, buffet)
```

3. Outcome Collection

```python
# jagabot/cli/feedback.py
@cli.command()
@click.argument('analysis_id')
@click.option('--outcome', type=click.Choice(['correct', 'wrong', 'partial']))
def feedback(analysis_id, outcome):
    """Provide actual outcome for past prediction"""
    meta.record_outcome(analysis_id, outcome)
    click.echo(f"✅ Outcome recorded. MetaLearningEngine will adjust weights.")
```

4. Automated Market Data Integration

```python
# jagabot/cron/outcome_checker.py
class OutcomeChecker:
    """Cron job to check actual outcomes against predictions"""
    
    def __init__(self):
        self.yahoo = YahooFinance()
        self.meta = MetaLearningEngine()
    
    def check_pending_predictions(self):
        """Run daily to check predictions against actual market data"""
        pending = self.meta.get_pending_predictions(days_old=30)
        
        for pred in pending:
            if pred['type'] == 'price_direction':
                actual = self.yahoo.get_price(pred['symbol'], pred['date'] + 30)
                was_correct = (actual > pred['target']) == pred['predicted_direction']
                
                self.meta.record_outcome(
                    pred['id'],
                    'correct' if was_correct else 'wrong'
                )
```

METRICS TO TRACK

Metric Purpose Stored In
Accuracy per perspective Weight adjustment K3 weights
Confidence calibration K1 prior updates K1 priors
Signal effectiveness Pattern detection KnowledgeGraph
Win rate by market condition Strategy refinement MemoryFleet
Learning curve Overall improvement MetaLearning DB

LEARNING VISUALIZATION

```python
# jagabot/cli/learning.py
@cli.command()
def learning_report():
    """Show how JAGABOT has improved over time"""
    
    report = meta.get_learning_curve()
    
    print(f"""
📈 JAGABOT LEARNING REPORT

Overall Accuracy: {report.overall_accuracy}% (was {report.baseline_accuracy}%)
Improvement: +{report.improvement_pct}%

Per Perspective:
🐂 Bull: {report.bull_accuracy}% (weight {report.bull_weight})
🐻 Bear: {report.bear_accuracy}% (weight {report.bear_weight})
🦉 Buffet: {report.buffet_accuracy}% (weight {report.buffet_weight})

Top Performing Signals:
{report.top_signals}

Lessons Learned:
{report.lessons}
    """)
```

TESTING REQUIREMENTS

Test 1: Prediction Tracking

```python
def test_track_prediction():
    meta = MetaLearningEngine()
    analysis_id = "test_123"
    pred = {'perspective': 'bull', 'confidence': 0.7}
    
    meta.track_prediction(analysis_id, pred, pending=True)
    assert meta.get_pending(analysis_id) is not None
```

Test 2: Outcome Recording

```python
def test_outcome_recording():
    meta = MetaLearningEngine()
    analysis_id = "test_123"
    
    meta.record_outcome(analysis_id, 'correct')
    stats = meta.get_stats('bull')
    assert stats['correct'] == 1
```

Test 3: Weight Adjustment

```python
def test_weight_adjustment():
    meta = MetaLearningEngine()
    
    # Simulate 10 correct predictions for bear
    for _ in range(10):
        meta.record_outcome('bear', 'correct')
    
    weights = meta.k3.get_weights()
    assert weights['bear'] > weights['bull']
```

Test 4: Full Integration

```python
def test_end_to_end_learning():
    # Run analysis
    result = jagabot.analyze(test_query)
    analysis_id = result.id
    
    # Simulate 30 days later
    time_travel(days=30)
    
    # Auto-check outcome
    checker = OutcomeChecker()
    checker.check_pending_predictions()
    
    # Verify learning occurred
    report = meta.get_learning_report()
    assert report.improvement_pct > 0
```

NEW FILES TO CREATE

1. jagabot/core/meta_learning.py (main engine)
2. jagabot/cli/feedback.py (user feedback commands)
3. jagabot/cron/outcome_checker.py (automated outcome checking)
4. jagabot/cli/learning.py (learning visualization)
5. tests/test_meta_learning.py (30+ tests)
6. tests/test_outcome_checker.py (10+ tests)

FILES TO MODIFY

1. jagabot/tools/decision_engine.py - add prediction tracking
2. jagabot/swarm/planner.py - generate analysis IDs
3. jagabot/cron/__init__.py - register outcome checker
4. SKILL.md - document new learning capabilities
5. CHANGELOG.md - v3.0 Phase 3

SUCCESS CRITERIA

✅ MetaLearningEngine extracts from engine library (661 LOC)
✅ Predictions tracked for all analyses
✅ Outcomes recorded (user feedback + auto-check)
✅ Weights auto-adjust in decision_engine
✅ K1 priors update based on calibration
✅ KnowledgeGraph shows signal-outcome relationships
✅ Learning report shows improvement over time
✅ 850+ tests passing
✅ All Phase 1 & 2 features still work

TIMELINE

Task Hours
Extract MetaLearningEngine from library 2
Implement prediction tracking hooks 3
Implement outcome recording 2
Integrate with decision_engine 2
Add cron-based auto-checker 2
Add CLI feedback commands 1
Add learning visualization 2
Write tests (40+) 3
Documentation 1
TOTAL 18 hours

```

---

**Phase 3 will make JAGABOT self-improving. Ready to build?** 🚀
