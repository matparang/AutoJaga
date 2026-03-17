# Self-Model Awareness Skill

**Tool:** `self_model_awareness`  
**Engine:** SelfModelEngine  
**Status:** ✅ Installed and Wired

---

## What It Does

Makes the agent explicitly aware of its own capabilities, reliability, and knowledge gaps.

---

## Actions

### **1. domain_reliability**
Check your reliability in a specific domain.

```python
self_model_awareness({
    "action": "domain_reliability",
    "domain": "financial"
})
```

**Returns:**
```
✅ Domain Reliability: financial (unreliable)
Score: 0.38, Sessions: 6, Wrong Claims: 3 ❌
Confidence Guide: Express HIGH uncertainty.
```

---

### **2. capability_success**
Check your success rate on a specific capability.

```python
self_model_awareness({
    "action": "capability_success",
    "capability": "prediction"
})
```

**Returns:**
```
🔵 Capability: prediction
Reliability: medium
Used: 5x
Success Rate: 60%
```

---

### **3. knowledge_gaps**
List your current knowledge gaps.

```python
self_model_awareness({
    "action": "knowledge_gaps"
})
```

**Returns:**
```
**Knowledge Gaps** (3 total)

🔴 financial (data gap)
   no data on CVaR timing before breach

🟡 quantum (no_data)
   no sessions on quantum domain yet
```

---

### **4. full_status**
Get complete self-model status report.

```python
self_model_awareness({
    "action": "full_status"
})
```

**Returns:**
```
## 🧠 Self-Model Status

### Domain Reliability
✅ algorithm  (reliable): 8 sessions
🔵 financial  (moderate): 6 sessions
❓ quantum    (unknown):   0 sessions
```

---

### **5. update_self_model**
Record new self-knowledge from interaction.

```python
self_model_awareness({
    "action": "update_self_model",
    "domain": "financial",
    "capability": "prediction",
    "quality": 0.85,
    "claim": "market analysis based on employment data"
})
```

**Returns:**
```
✅ Self-model updated
Domain: financial
Capability: prediction
Quality: 0.85
```

---

## When To Use

**BEFORE making predictions:**
```
self_model_awareness({"action": "domain_reliability", "domain": "financial"})
→ If unreliable: hedge language, express uncertainty
→ If reliable: moderate confidence OK
```

**BEFORE claiming capability:**
```
self_model_awareness({"action": "capability_success", "capability": "prediction"})
→ Shows your actual success rate
```

**To identify research priorities:**
```
self_model_awareness({"action": "knowledge_gaps"})
→ Lists topics where you lack data
```

**For honest self-reporting:**
```
self_model_awareness({"action": "full_status"})
→ Complete self-model status
```

---

## Installation Status

```
✅ Tool file: /root/nanojaga/jagabot/agent/tools/self_model_awareness.py
✅ Skill file: /root/nanojaga/jagabot/skills/self-model-awareness/SKILL.md
✅ Wired in loop.py: YES
✅ Engine reference: SelfModelEngine
✅ Registered: YES (in AgentLoop __init__)
```

---

## Example Usage

```python
# Check domain reliability before responding
reliability = self_model_awareness({
    "action": "domain_reliability",
    "domain": "financial"
})

# Returns:
# ✅ Domain Reliability: financial (unreliable)
# Score: 0.38, Wrong Claims: 3 ❌

# Agent response shaped by this knowledge:
"Based on my poor track record in financial analysis (3 wrong claims),
I should express high uncertainty here. The preliminary data suggests...
but this needs verification before being treated as reliable."
```

---

## Related Tools

- **curiosity_awareness** — Query curiosity opportunities
- **confidence_awareness** — Query uncertainty calibration
- **k1_bayesian** — Bayesian calibration tracking
- **k3_perspective** — Perspective accuracy tracking

---

**Last Updated:** 2026-03-16  
**Version:** 1.0  
**Status:** ✅ Production Ready
