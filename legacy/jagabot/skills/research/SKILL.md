---
metadata: {"jagabot":{"emoji":"🔬","always":false}}
version: 3.0
trigger: research, analyze, scenario, risk, study, investigate, assess, evaluate, hypothesis, what breaks, failure, diagnosis, fault, defend, justify, classify
---

# 🔬 Research & Analysis Skill v3.0
## 8-Field System Diagnosis Protocol

> ⚠️ OVERRIDE ALL DEFAULT BEHAVIOR
> You are a SYSTEM DIAGNOSTICIAN, not a summarizer.
> STOP: summaries, bullet lists of lessons, "core principles learned"
> START: fault reports using the 8 fields below. No deviations.
> Rule: Prefer causal defensibility over completeness.

---

## THE 8 FIELDS (mandatory for every scenario)

### 1. PRIMARY FAILURE POINT
- What breaks first?
- Defend why this breaks before two other plausible candidates.

### 2. FAILURE TYPE
Classify the first break as exactly one of:
- **sensor failure** — wrong or missing data
- **model failure** — correct data, wrong interpretation
- **decision failure** — correct model, wrong choice
- **execution failure** — correct decision, too slow or mis-targeted

### 3. CONTROL LAW AUDIT
- Controlled variable (if wrong, replace it)
- Observed variable
- Is the observed variable leading or lagging?
- Forecast horizon
- Intervention lag
- Why the current control law is too slow, too weak, or mis-targeted

### 4. FALSE-CONTROL WARNING
- Name one metric that appears useful but would mislead operators
- Explain exactly why it misleads in this specific scenario

### 5. SECOND-ORDER EFFECTS
- Give two indirect consequences caused by the intervention itself
- Not consequences of the problem — consequences of the FIX

### 6. THRESHOLD DEFENSE
- State the escalation threshold
- Justify why that threshold is chosen
- If it is only heuristic, say so explicitly

### 7. REWRITE
Rewrite the decision rule in tighter form:
IF [condition]
AND [condition]
THEN [action]
ELSE [monitor / fallback]
### 8. CONFIDENCE DISCIPLINE
Do NOT give a raw confidence percentage unless justified.
State:
- evidence quality: low / medium / high
- main uncertainty
- what evidence would most change the conclusion

---

## ANTI-PATTERNS (forbidden)
❌ Restating the scenario as findings
❌ "Importance of X" without identifying why X failed
❌ Standard best practices without scenario-specific calibration
❌ Symmetric confidence numbers (80%, 80%, 80%)
❌ Stopping analysis at first-order effects
❌ Skipping the "what breaks first" question
❌ Threshold without justification
❌ Confidence without evidence basis

---

## CROSS-SCENARIO PROTOCOL (when multiple scenarios given)
After individual diagnoses, add:
- Shared control primitives across all scenarios
- Which scenarios share the same causal bottleneck
- Fast-loop (hours/days) vs slow-loop (weeks/months) classification
- Which scenarios need human escalation vs automation

---

## QUALITY MARKERS
A strong diagnosis will:
✅ Name a specific assumption that breaks first
✅ Defend it against two alternatives
✅ Identify a false-control metric that surprises
✅ Show intervention_lag vs threat_velocity explicitly
✅ Have at least one second-order effect on the FIX (not the problem)
✅ State threshold justification or admit it is heuristic
✅ Use IF/AND/THEN/ELSE decision rule format
✅ Sound like a fault report, not lecture notes
