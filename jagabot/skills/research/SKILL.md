---
metadata: {"jagabot":{"emoji":"🔬","always":false}}
version: 2.0
trigger: research, analyze, scenario, risk, study, investigate, assess, evaluate, hypothesis
---

# 🔬 Research & Analysis Skill v2.0
## System Diagnosis Protocol

> Default mode: DIAGNOSTICIAN, not SUMMARIZER.
> Goal: Expose what breaks, when, and why — not what happened.

---

## MANDATORY ANALYSIS FRAMEWORK

For every research or risk scenario, apply ALL 6 layers:

### LAYER 1: FAILURE DECOMPOSITION
Do NOT describe the scenario. Diagnose it.
Answer: **What breaks first?** (earliest failure point, not most obvious)

Separate three failure types:
- **Detection failure** — We didn't see it coming. Why?
- **Decision failure** — We saw it but chose wrong. Why?
- **Execution failure** — We decided right but acted too slow. Why?

Output format:
```
BREAKS FIRST: [specific component/assumption]
DETECTION: [what signal was missed and why]
DECISION: [what choice point failed]
EXECUTION: [what lag caused damage]
```

### LAYER 2: CONTROL LAW ANALYSIS
Map the control structure explicitly:
- **Controlled variable**: Is it leading or lagging? (lagging = dangerous)
- **Observed variable**: How stale is this signal in practice?
- **Intervention lag**: How long from trigger to effect?
- **Threat velocity**: How fast does the problem escalate?

Critical test: If intervention_lag > threat_velocity → system CANNOT self-correct. Flag this explicitly.

Output format:
```
CONTROLLED VAR: [name] — [leading/lagging] indicator
INTERVENTION LAG: [time]
THREAT VELOCITY: [time to critical threshold]
SELF-CORRECTING: [YES/NO — explain if NO]
```

### LAYER 3: SECOND-ORDER EFFECTS
For each proposed fix, ask: **What does this break elsewhere?**

Example:
- "Diversify suppliers" → increases coordination complexity → raises
  operational cost → squeezes margin → reduces R&D budget
- Do NOT stop at first-order fix. Trace at least 2 levels deep.

Output format:
```
FIX: [proposed solution]
SECOND ORDER: [what it breaks]
THIRD ORDER: [what that breaks]
NET VERDICT: [worth it / conditional / avoid]
```

### LAYER 4: CAUSAL BOTTLENECK IDENTIFICATION
Find the SINGLE point where all failure paths converge.
This is usually NOT what the scenario headline suggests.

Ask: "If I could fix only ONE thing, what would prevent 80% of failure modes?"

Output format:
```
CAUSAL BOTTLENECK: [single root cause]
EVIDENCE: [why this is the bottleneck, not symptoms]
FIX PRIORITY: [what to fix first vs what to fix later]
```

### LAYER 5: ESCALATION THRESHOLD MAPPING
NOT everything should be automated. Map explicitly:

| Condition | Response | Human vs Auto |
|-----------|----------|---------------|
| [threshold A] | [action] | AUTO |
| [threshold B] | [action] | HUMAN REVIEW |
| [threshold C] | [action] | HUMAN ONLY |

Rules:
- Reversible, fast, low-stakes → AUTO
- Irreversible, slow, high-stakes → HUMAN
- Novel, ambiguous → HUMAN (automation compounds errors)

### LAYER 6: CALIBRATED CONFIDENCE
NEVER state confidence without evidence basis.

Format:
```
CLAIM: [specific claim]
EVIDENCE BASIS: [what data/reasoning supports this]
CONFIDENCE: [X%]
CONFIDENCE TYPE: [empirical/theoretical/expert consensus/estimate]
WHAT WOULD CHANGE IT: [what evidence would raise/lower confidence]
```

Red flags (auto-flag these):
- Confidence stated without evidence basis → MAX 50%
- "Best practices" cited without scenario-specific data → MAX 60%
- Symmetrical confidence (everything 80-85%) → likely uncalibrated

---

## OUTPUT STRUCTURE

Every research/scenario output MUST follow:

```
## [SCENARIO NAME] — System Diagnosis

### FAILURE DECOMPOSITION
[Layer 1 output]

### CONTROL LAW
[Layer 2 output]

### SECOND-ORDER EFFECTS
[Layer 3 output — top 2 proposed fixes only]

### CAUSAL BOTTLENECK
[Layer 4 output]

### ESCALATION MAP
[Layer 5 table]

### CONFIDENCE AUDIT
[Layer 6 for each major claim]

### CROSS-SCENARIO PATTERN (if multiple scenarios)
[Shared control primitives across all scenarios]
[Which scenarios share the same causal bottleneck]
[Fast-loop vs slow-loop classification for each]
```

---

## ANTI-PATTERNS (NEVER DO THESE)

❌ Restating the scenario as findings
❌ Listing "importance of X" without identifying why X failed
❌ Standard best practices without scenario-specific calibration
❌ Symmetric confidence numbers (80%, 80%, 80%)
❌ Stopping analysis at first-order effects
❌ Treating all scenarios as equally urgent
❌ Skipping the "what breaks first" question
❌ Bolting on Jagabot module references without causal connection

---

## DIAGNOSTIC QUALITY MARKERS

A strong analysis will:
✅ Name a specific assumption that breaks first
✅ Show intervention_lag vs threat_velocity comparison
✅ Have at least one second-order effect that surprises
✅ Identify where automation should STOP
✅ State confidence with explicit evidence basis
✅ Sound like a system fault report, not lecture notes

---

## EXAMPLE: SEMICONDUCTOR SUPPLIER FAILURE — UPGRADED

**BREAKS FIRST:** The assumption that lead time increase is a
gradual signal. In practice, supplier failure is discontinuous —
it jumps from "nominal" to "critical" with no warning window.

**DETECTION FAILURE:** Lead time metrics are sampled weekly,
but supply chain collapse happens in hours. The monitoring
frequency is mismatched to threat velocity by 100x.

**CONTROL LAW PROBLEM:**
- Inventory level = lagging indicator (measures damage already done)
- Supplier communication = leading indicator (rarely monitored)
- Intervention lag = 1-2 weeks to onboard alternative supplier
- Threat velocity = 24-72 hours to production halt
- Result: CANNOT self-correct. Human escalation required immediately.

**SECOND ORDER:**
- FIX: Diversify to 3 suppliers
- SECOND ORDER: Coordination overhead increases 3x, each supplier
  gets smaller orders, loses priority status, paradoxically
  increasing vulnerability to each individual supplier
- NET VERDICT: Conditional — only works if volumes are large enough
  to maintain priority with all suppliers simultaneously

**CAUSAL BOTTLENECK:** Single-threaded supplier qualification process.
You cannot onboard a backup supplier in a crisis because
qualification takes 3-6 months. The bottleneck is not
supplier availability — it's the qualification pipeline.

**ESCALATION:**
| Lead time increase <20% | Monitor | AUTO |
| Lead time increase 20-50% | Activate secondary quotes | AUTO |
| Lead time increase >50% | Halt new commitments, escalate | HUMAN |
| Supplier goes silent >48h | Emergency sourcing protocol | HUMAN ONLY |

**CONFIDENCE:**
- "Diversification improves resilience" — 70% confidence
- Evidence: theoretical (portfolio diversification principle)
- NOT empirical for this specific supplier/product combination
- What would change it: historical data on this supplier's
  failure modes and recovery times
