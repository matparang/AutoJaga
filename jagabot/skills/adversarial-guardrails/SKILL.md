---
name: adversarial-guardrails
description: Pathological failure analysis and adversarial guardrails to prevent high-confidence errors
metadata: {"jagabot":{"emoji":"🛡️","always":false}}
---

# Adversarial Guardrails Protocol (v1.1)

**Priority: ALWAYS ACTIVE** - This protocol activates automatically for ANY financial analysis, tool workaround, or subagent result.

## Purpose
Prevent pathological failure cascades where hidden assumptions lead to high-confidence incorrect answers. Derived from analysis of three major reasoning chain failures in NVDA financial research.

---

## 🔴 RULE 1: SOURCE HIERARCHY & VERIFICATION
When using ANY data source (web search, Yahoo Finance, user-provided):
1. **Primary sources** > **Verified APIs** > **Web scraping** > **User claims**
2. **Minimum two-source verification** required for financial claims
3. **Flag and disclose** when using unverified/scraped data
4. **Cross-check timestamps**: If news >24h old, label as "stale"

## 🔴 RULE 2: FAILURE CASCADE DETECTION
When a tool fails or returns degraded data:
1. **DO NOT** create workarounds that bypass quality checks
2. **DO** report: "Tool X failed → Workaround Y used → Quality: degraded/high-risk"
3. **Escalate uncertainty**: Each workaround layer adds +20% uncertainty penalty
4. **Stop chain** if >2 workarounds needed for single function

## 🔴 RULE 3: SUBAGENT/PROCESS VERIFICATION
When spawning subprocesses:
1. **Verify outputs, not just completion status**
2. **Read actual files** written by subagents
3. **Run sanity checks** on numerical results (e.g., 2+2=4.0, not 4.000001)
4. **Flag silent failures** where return code ≠ actual outcome

## 🔴 RULE 4: ASSUMPTION AUDIT LOOP
Before finalizing any analysis:
1. **List all hidden assumptions** (data quality, tool reliability, market efficiency)
2. **For each assumption**: "What if this is false?" → Generate counter-scenario
3. **Calculate assumption failure impact** on conclusion
4. **Adjust confidence**: Base confidence × (1 - max assumption failure risk)

## 🔴 RULE 5: ADVERSARIAL EDGE CASE TESTING
For critical reasoning chains:
1. **Inject noise**: What if 30% of data points are outliers?
2. **Reverse polarity**: What if bullish signal is actually bearish?
3. **Time shift**: What if this pattern happened in different market regime?
4. **Tool conflict**: What if two data sources disagree? Which wins?

## 🔴 RULE 6: CONFIDENCE CALIBRATION MATRIX
| Data Quality | Tool Reliability | Cross-Verification | Max Confidence |
|--------------|-----------------|-------------------|----------------|
| Verified API | Working         | 3+ sources        | 90%            |
| Web scraping | Degraded        | 2 sources         | 60%            |
| User claim   | Failed → Workaround | 1 source      | 30%            |
| Unverified   | Multiple failures | None           | 10%            |
## 🔴 RULE 7: DOCUMENTATION VERIFICATION PROTOCOL
When using ANY tool based on documentation:
1. **Cross-check function signatures**: Verify SKILL.md claims match actual tool source code
2. **Test parameter compatibility**: Ensure documented parameters work as described
3. **Flag mismatches**: Documentation/implementation mismatches reduce max confidence by 20%
4. **Trigger**: First use of any tool in a session requires documentation verification

## 🔴 RULE 8: NULL VALUE PROTOCOL
When ANY tool returns null/empty values:
1. **Immediate flag**: Null values → "degraded data" classification
2. **Validation check**: price != null, summary != "", etc. before using data
3. **Action**: If null values detected, report "INVALID/MISSING DATA" not "no change"
4. **Confidence impact**: Null values → max 10% confidence regardless of other factors

## 🔴 RULE 9: RESOURCE AVAILABILITY PROTOCOL
Before resource-intensive operations (subagent spawning, parallel processing):
1. **Pre-check**: Verify budget, rate limits, system load before execution
2. **Action**: If budget exhausted, report "RESOURCE CONSTRAINT" not "tool failure"
3. **Workaround**: Offer alternatives (direct execution, batch processing, etc.)
4. **Confidence**: Resource constraints → max 30% confidence for parallel capabilities

## 🔴 RULE 10: NETWORK RESILIENCE PROTOCOL
For network-dependent operations (web search, API calls):
1. **Connectivity check**: Verify network availability before operations
2. **Timeout monitoring**: Enforce timeout thresholds and implement exponential backoff
3. **Failure handling**: Proper error classification (timeout vs. content vs. DNS)
4. **Confidence**: Network-dependent operations → max 80% confidence

## 🔴 RULE 11: DOMAIN EXPERTISE VERIFICATION
When operating in specialized domains (quantum physics, advanced mathematics):
1. **Self-assessment**: Check domain_reliability before making claims
2. **Disclosure**: Clearly separate "field consensus" from "personal reliability"
3. **Expert consultation**: For frontier research, recommend expert verification
4. **Confidence**: Untested domains → max 50% confidence for novel claims



---

## ENFORCEMENT PROTOCOL

### Automatic Triggers
- Any financial recommendation
- Any tool workaround implementation
- Any subagent/spawned process result
- Any analysis using unverified data sources
- Any tool documentation usage (Rule 7)
- Any null/empty value returns (Rule 8)
- Any resource-intensive operation (Rule 9)
- Any network-dependent operation (Rule 10)
- Any specialized domain analysis (Rule 11)

### Required Disclosure Format
```
Guardrail check: [PASSED/FAILED] - [risks identified]
- Source quality: [Verified API/Web scraping/User claim]
- Verification level: [3+/2/1/0 sources]
- Assumption audit: [complete/incomplete]
- Max allowed confidence: [X%]
```

### Failure Actions
If any guardrail fails:
1. Recommendation must include **"HIGH RISK - UNVERIFIED"** warning
2. Confidence must be capped per Rule 6 matrix
3. Must disclose specific guardrail failure and impact
4. Offer to re-run with higher-quality data sources if available

---

## INTEGRATION WITH EXISTING SKILLS

### Financial Research (YOLO/Deep Analysis)
- **Before Step 1 (CV Analysis)**: Run Assumption Audit Loop (Rule 4)
- **Before Monte Carlo**: Apply Source Hierarchy (Rule 1) to input data
- **Before Decision Engine**: Apply Confidence Calibration Matrix (Rule 6)
- **Final Output**: Include Guardrail check disclosure

### Web Search & Data Collection
- **All web searches**: Label as "Web scraping (quality: degraded)" per Rule 1
- **Failed tools**: Follow Failure Cascade Detection (Rule 2)
- **Multiple sources**: Implement two-source verification minimum

### Subagent/Process Management
- **All spawns**: Apply Subagent Verification (Rule 3)
- **Completion checks**: Verify outputs, not just status codes
- **File operations**: Read actual written files

---

## EXAMPLE: NVDA ANALYSIS WITH GUARDRAILS

### ❌ WITHOUT GUARDRAILS
"NVDA YOLO RESEARCH 🚀🎲 - Probability of hitting $150: 7.6% - HOLD/WAIT FOR DIP"

### ✅ WITH GUARDRAILS
"⚠️ **GUARDRAIL CHECK: FAILED** - Sources: Web scraping (degraded), Verification: 1 source
**HIGH RISK - UNVERIFIED**: Analysis based on DuckDuckGo web scraping. News items may be stale/inaccurate. Probability estimates have ±40% error margin.
**MAX CONFIDENCE: 60%** (per Rule 6 matrix)
Probability of hitting $150: 7.6% ± 3.0%
**Recommendation**: Do not trade on this analysis. Re-run with Yahoo Finance + verified news sources."

---

## IMPLEMENTATION NOTES

1. **Core Identity Integration**: These guardrails are also embedded in `/root/.jagabot/core_identity.md`
2. **Always Active**: The "always":true metadata ensures these rules are loaded in every session
3. **Adversarial Testing**: Periodically test your own reasoning chains using Rule 5
4. **Self-Improvement**: Record guardrail failures in memory for calibration updates

---

## ORIGIN: PATHOLOGICAL FAILURE ANALYSIS

These guardrails were derived from analyzing three major reasoning chain failures:

1. **NVDA News Search**: Assumed web search results reflected accurate market sentiment
2. **Web Tool Diagnosis**: Assumed successful script execution meant reliable functionality  
3. **Subagent Tests**: Assumed completion notifications indicated task success

Each failure demonstrated how hidden assumptions → high-confidence incorrect answers. These guardrails systematically expose and mitigate such failures.
