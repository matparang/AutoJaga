# Confidence Awareness Skill

**Tool:** `confidence_awareness`  
**Engine:** ConfidenceEngine  
**Status:** ✅ Installed and Wired

---

## What It Does

Makes the agent explicitly aware of uncertainty calibration — distinguishing aleatory vs epistemic uncertainty, detecting overconfidence, and annotating responses with structured confidence notes.

---

## Actions

### **1. claim_confidence**
Check confidence level for a specific claim.

```python
confidence_awareness({
    "action": "claim_confidence",
    "claim": "CVaR warns 2 days before breach",
    "domain": "financial"
})
```

**Returns:**
```
🟡 Claim Confidence: LOW

Claim: CVaR warns 2 days before breach
Domain: financial

Uncertainty Type: EPISTEMIC
Evidence Strength: insufficient

Note: Domain 'financial' calibration check needed
Suggested Hedge: Consider hedging: 'preliminary analysis suggests'
```

---

### **2. response_annotation**
Get structured uncertainty annotations for response.

```python
confidence_awareness({
    "action": "response_annotation",
    "response": "Based on my analysis, the market will rise",
    "domain": "financial",
    "tools_used": ["web_search", "monte_carlo"]
})
```

**Returns:**
```
**Response Annotation** (2 annotations)

"Based on my analysis, the market will rise"
⚠️ LOW confidence in financial domain (trust=0.38)
🔵 EPISTEMIC uncertainty — no real-world outcomes verified

Suggested: "Based on my limited track record, preliminary analysis suggests..."
```

---

### **3. overconfidence_check**
Identify overconfident language in text.

```python
confidence_awareness({
    "action": "overconfidence_check",
    "text": "I'm certain the market will definitely rise"
})
```

**Returns:**
```
⚠️ Overconfidence Detected (2 phrases)

- "certain..."
  → Suggested: Consider: 'suggests' instead of 'certain'
- "definitely..."
  → Suggested: Consider: 'likely' instead of 'definitely'

Domain Warning: financial domain has poor calibration (trust=0.38)
```

---

### **4. uncertainty_type**
Distinguish aleatory vs epistemic uncertainty.

```python
confidence_awareness({
    "action": "uncertainty_type",
    "claim": "CVaR timing accuracy needs more measurements"
})
```

**Returns:**
```
📚 Uncertainty Type: EPISTEMIC

Claim: CVaR timing accuracy needs more measurements

Meaning: Knowledge gap — CAN be reduced with more data.
Action: Run simulations, gather real data, verify claims.
Example: "CVaR timing accuracy needs more measurements (epistemic)"
```

---

### **5. calibration_history**
Review past claim verification outcomes.

```python
confidence_awareness({
    "action": "calibration_history",
    "domain": "financial",
    "limit": 10
})
```

**Returns:**
```
**Calibration History** (5 claims)

❌ "CVaR warns 2 days before breach..."
   Original Confidence: high
   Outcome: wrong
   Domain: financial

✅ "Monte Carlo shows 40% probability..."
   Original Confidence: moderate
   Outcome: verified
   Domain: financial

**Calibration Rate:** 40% (2/5)
Higher rate = better confidence calibration
```

---

## When To Use

**BEFORE making strong claims:**
```
confidence_awareness({
    "action": "claim_confidence",
    "claim": "market will rise",
    "domain": "financial"
})
→ If low confidence: hedge language
→ If high confidence: proceed with appropriate certainty
```

**To self-edit before responding:**
```
confidence_awareness({
    "action": "overconfidence_check",
    "text": response_draft
})
→ Identifies overconfident phrases
→ Suggests appropriate hedges
```

**To distinguish uncertainty types:**
```
confidence_awareness({
    "action": "uncertainty_type",
    "claim": "WTI price next month is uncertain"
})
→ Aleatory: Use probability ranges
→ Epistemic: Get more data
```

**For calibration review:**
```
confidence_awareness({
    "action": "calibration_history",
    "domain": "financial"
})
→ Shows past claim verification outcomes
→ Helps calibrate future confidence
```

---

## Installation Status

```
✅ Tool file: /root/nanojaga/jagabot/agent/tools/confidence_awareness.py
✅ Skill file: /root/nanojaga/jagabot/skills/confidence-awareness/SKILL.md
✅ Wired in loop.py: YES
✅ Engine reference: ConfidenceEngine
✅ Registered: YES (in AgentLoop __init__)
```

---

## Example Usage

```python
# Check claim confidence before responding
confidence = confidence_awareness({
    "action": "claim_confidence",
    "claim": "CVaR warns 2 days before breach",
    "domain": "financial"
})

# Returns:
# 🟡 Claim Confidence: LOW
# Uncertainty Type: EPISTEMIC

# Agent response shaped by this knowledge:
"Based on my analysis, I should express low confidence here. This is an
EPISTEMIC uncertainty — we can reduce it by running more simulations.
Preliminary findings suggest CVaR may provide timing signals, but this
needs verification with real data before being treated as reliable."
```

---

## Related Tools

- **self_model_awareness** — Query self-model (domain reliability)
- **curiosity_awareness** — Query curiosity opportunities
- **k1_bayesian** — Bayesian calibration tracking
- **outcome_tracker** — Record verdicts for calibration history

---

## Uncertainty Types Reference

| Type | Meaning | Action | Example |
|------|---------|--------|---------|
| **Aleatory** | Inherent randomness | Use probability ranges | "WTI price is inherently uncertain" |
| **Epistemic** | Knowledge gap | Get more data | "CVaR timing needs more measurements" |
| **Conflicting** | Contradictory evidence | Reconcile sources | "Studies show conflicting results" |
| **Outdated** | Stale information | Refresh data | "This data is 90 days old" |
| **None** | No significant uncertainty | Proceed with confidence | "Verified by actual execution" |

---

**Last Updated:** 2026-03-16  
**Version:** 1.0  
**Status:** ✅ Production Ready
