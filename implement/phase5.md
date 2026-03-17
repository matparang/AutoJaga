📋 SCOPE PROMPT: Phase 5 - Make JAGABOT a Financial Superpowers

```markdown
# SCOPE: Phase 5 - Transform JAGABOT into Financial Superpowers

## CURRENT STATE (v3.1)
✅ 1009 tests passing
✅ 30 tools
✅ Neo4j graph with 76 nodes, 119 relations
✅ Streamlit UI working
✅ All kernels (K1, K3, K7, MemoryFleet, MetaLearning, Evolution)
✅ 4-stage subagent pipeline

⏳ TARGET: JAGABOT as FINANCIAL SUPERPOWERS
- Skills auto-trigger based on context
- Composable workflows
- Two-stage review (spec + quality)
- Test-driven validation
- Self-documenting skills

## WHAT SUPERPOWERS TEACHES US

```yaml
SUPERPOWERS CORE PRINCIPLES:
  1. Skills trigger AUTOMATICALLY based on context
  2. Skills are COMPOSABLE (can call each other)
  3. SUBAGENT-DRIVEN with two-stage review
  4. TEST-DRIVEN (RED-GREEN-REFACTOR)
  5. SYSTEMATIC over ad-hoc
  6. EVIDENCE over claims
  7. COMPLEXITY REDUCTION as primary goal
```

PHASE 5 DELIVERABLES

PART A: Auto-Triggering Skills System

```python
# jagabot/skills/trigger.py
class SkillTrigger:
    """Automatically detect which skill to use based on context"""
    
    def __init__(self):
        self.skills = self.load_skills()
        self.triggers = {
            'crisis_management': ['vix', 'margin call', 'prob_downside', 'crash'],
            'investment_thesis': ['new idea', 'should i invest', 'research'],
            'portfolio_review': ['portfolio', 'holdings', 'positions'],
            'fund_manager_review': ['fund manager', 'advisor said', 'broker'],
            'risk_validation': ['validate', 'check risk', 'verify'],
            'rebalancing': ['rebalance', 'adjust allocation'],
            'skill_creation': ['create new analysis', 'new skill']
        }
    
    def detect(self, query, market_data):
        """Return best matching skill"""
        scores = {}
        for skill, keywords in self.triggers.items():
            score = sum(1 for k in keywords if k in query.lower())
            # Boost based on market conditions
            if skill == 'crisis_management' and market_data.get('vix', 0) > 40:
                score += 5
            scores[skill] = score
        
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else 'default'
```

PART B: Composable Skills (Skills Calling Skills)

```markdown
# SKILL: crisis_management (composable version)
TRIGGER: vix > 40 OR margin_call = true

WORKFLOW:
1. CALL portfolio_review → get current status
2. CALL risk_validation → verify risk metrics
3. CALL fund_manager_review → check if any advice exists
4. RUN Monte Carlo with evolved parameters
5. GENERATE action plan
6. SAVE to KnowledgeGraph

SUB-SKILLS USED:
- portfolio_review
- risk_validation
- fund_manager_review
```

PART C: Two-Stage Review (Spec + Quality)

```python
# jagabot/kernels/review.py
class TwoStageReview:
    """Superpowers-style two-stage review"""
    
    def stage1_spec_compliance(self, task, output):
        """Does output match the spec?"""
        checks = [
            output.get('probability') is not None,
            output.get('confidence_interval') is not None,
            'action' in output,
            'rationale' in output
        ]
        return all(checks)
    
    def stage2_quality(self, task, output):
        """Is the calculation accurate?"""
        # Use K7 evaluation with stricter criteria
        score = K7.evaluate(output)
        return score > 0.8
    
    def review(self, task, output):
        spec_pass = self.stage1_spec_compliance(task, output)
        if not spec_pass:
            return {'pass': False, 'stage': 1, 'reason': 'Missing required fields'}
        
        quality_pass = self.stage2_quality(task, output)
        if not quality_pass:
            return {'pass': False, 'stage': 2, 'reason': 'Quality score too low'}
        
        return {'pass': True, 'stage': 'both'}
```

PART D: Test-Driven Validation (RED-GREEN-REFACTOR)

```markdown
# SKILL: risk_validation (TDD-style)
TRIGGER: before any major decision

WORKFLOW:
1. RED: Write expected risk parameters
   - Expected VaR: $X
   - Expected probability: Y%
   - Expected margin status: Z

2. GREEN: Run actual calculations
   - Call monte_carlo, var, cvar
   - Compare with expectations

3. REFACTOR: If mismatch
   - Log discrepancy
   - Adjust EvolutionEngine weights
   - Update MetaLearning with lesson

4. COMMIT only if tests pass
```

PART E: Systematic Debugging Skill

```markdown
# SKILL: systematic_debugging
TRIGGER: analysis error OR unexpected result

PHASE 1: OBSERVE
- What was expected? (from MetaLearning)
- What actually happened?
- Gather all relevant data

PHASE 2: HYPOTHESIZE
- Generate 3 possible causes
- Rank by probability
- Use Bayesian reasoning

PHASE 3: TEST
- For each hypothesis:
  - Run controlled test
  - Compare with expectation
  - Record result

PHASE 4: VERIFY
- Confirm fix works
- Add test to prevent regression
- Update KnowledgeGraph with lesson
```

PART F: Financial-Specific Skills (Superpowers Style)

```markdown
# SKILL: investment_thesis (was brainstorming)
TRIGGER: user mentions new investment idea

WORKFLOW:
1. CLARIFY via Socratic questions
   - "What sector are you interested in?"
   - "What's your time horizon?"
   - "What's your risk tolerance?"
   
2. EXPLORE alternatives
   - Compare with similar assets
   - Show historical performance
   - Highlight key risks
   
3. PRESENT thesis in sections
   - Section 1: Opportunity
   - Section 2: Risks
   - Section 3: Entry/Exit criteria
   - Section 4: Position sizing
   
4. SAVE to MemoryFleet
   - Tag with #thesis
   - Link to KnowledgeGraph
   - Track with MetaLearning

# SKILL: portfolio_rebalancing (was finishing-branch)
TRIGGER: risk metrics exceed thresholds OR user request

WORKFLOW:
1. VERIFY current allocation
   - Call portfolio_analyzer
   - Compare with target
   
2. PRESENT options
   - Option A: Sell overweights
   - Option B: Buy underweights
   - Option C: Hedge with options
   - Each with tax implications
   
3. EXECUTE selected option
   - Generate trade list
   - Verify with user
   - Execute via broker (if connected)
   
4. UPDATE memory
   - Save new allocation
   - Log trade rationale
   - Track performance
```

PART G: Meta-Skill for Creating New Financial Skills

```markdown
# SKILL: writing_financial_skills (enhanced skill-creator)
TRIGGER: "create new analysis type" OR "new skill"

TEMPLATE:
```markdown
# SKILL: [name]
TRIGGER: [conditions]

## PURPOSE
[1-paragraph description]

## WORKFLOW
1. [Step 1]
2. [Step 2]
3. [Step 3]

## TOOLS USED
- [tool1]
- [tool2]

## TEST CASES
- Case 1: [input] → [expected output]
- Case 2: [input] → [expected output]

## INTEGRATION
- Calls skills: [list]
- Called by skills: [list]
- Updates: MemoryFleet/KnowledgeGraph/MetaLearning

## EVOLUTION
- Mutation targets: [parameters]
- Fitness criteria: [metrics]
```

VALIDATION:

· Test in sandbox with cases
· Verify triggers work
· Check composability
· Register in skill library

```

## NEW FILES TO CREATE

1. `jagabot/skills/trigger.py` - Auto-triggering system
2. `jababot/kernels/review.py` - Two-stage review
3. `skills/investment_thesis.md` - Brainstorming for finance
4. `skills/portfolio_rebalancing.md` - Finishing workflow
5. `skills/risk_validation.md` - TDD for finance
6. `skills/systematic_debugging.md` - Debugging finance
7. `skills/writing_financial_skills.md` - Meta-skill (updated)
8. `tests/test_triggers.py` - 20+ tests
9. `tests/test_two_stage_review.py` - 15+ tests
10. `tests/test_skill_composition.py` - 15+ tests

## FILES TO MODIFY

1. `jagabot/core/agent.py` - Add auto-trigger before task selection
2. `jagabot/kernels/k7_evaluation.py` - Enhance for two-stage
3. `jagabot/evolution/engine.py` - Use TDD for validation
4. `jagabot/subagents/manager.py` - Add review stage
5. `SKILL.md` - Document new capabilities
6. `CHANGELOG.md` - v3.2

## TESTING REQUIREMENTS

### Test 1: Auto-Trigger
```python
def test_skill_trigger():
    trigger = SkillTrigger()
    query = "VIX is 45, should I worry about margin call?"
    market = {'vix': 45}
    skill = trigger.detect(query, market)
    assert skill == 'crisis_management'
```

Test 2: Two-Stage Review

```python
def test_two_stage_review():
    review = TwoStageReview()
    task = {'type': 'monte_carlo', 'params': {...}}
    output = {'probability': 55, 'ci': [50,60]}
    result = review.review(task, output)
    assert result['pass'] is True
```

Test 3: Skill Composition

```python
def test_skill_composition():
    # crisis_management should call portfolio_review
    result = execute_skill('crisis_management', test_data)
    assert 'portfolio_review' in result['called_skills']
```

Test 4: TDD Validation

```python
def test_tdd_validation():
    skill = load_skill('risk_validation')
    result = skill.execute({'expected_var': 100000, 'actual_var': 95000})
    assert result['tests_passed'] is True
    assert 'refactored' in result
```

SUCCESS CRITERIA

✅ Skills auto-trigger based on context (no manual selection)
✅ Skills can call other skills (composable)
✅ Two-stage review (spec + quality) for all outputs
✅ TDD workflow (RED-GREEN-REFACTOR) for validation
✅ Systematic debugging skill operational
✅ 5 new financial skills (investment_thesis, portfolio_rebalancing, etc.)
✅ Meta-skill for creating new skills with tests
✅ 1100+ tests passing
✅ All existing functionality preserved
✅ KnowledgeGraph updated with skill relationships
✅ MetaLearning tracks skill effectiveness

TIMELINE

Part Component Hours
A Auto-triggering system 3
B Composable skills 4
C Two-stage review 3
D TDD validation 3
E Systematic debugging 3
F 5 new financial skills 5
G Meta-skill enhancement 2
 Tests (50+ new) 5
 Documentation 2
TOTAL  30 hours

```

---

**This Phase 5 will transform JAGABOT into a true FINANCIAL SUPERPOWERS system - skills that auto-trigger, compose, review, and validate like the original, but for finance.** 🚀
