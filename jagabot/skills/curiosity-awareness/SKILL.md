# Curiosity Awareness Skill

**Tool:** `curiosity_awareness`  
**Engine:** CuriosityEngine  
**Status:** ✅ Installed and Wired

---

## What It Does

Makes the agent explicitly aware of curiosity opportunities — knowledge gaps, bridge connections, and underexplored topics worth investigating.

---

## Actions

### **1. session_suggestions**
Get curiosity suggestions for current session.

```python
curiosity_awareness({
    "action": "session_suggestions",
    "current_query": "research quantum computing",
    "session_key": "cli:direct"
})
```

**Returns:**
```
💡 Curiosity Opportunities (3 found)

1. healthcare (score: 0.92)
   Gap: No data on quantum healthcare applications
   Suggested: Research quantum simulation in drug discovery
   Bridge: Quantum simulation could accelerate drug discovery
```

---

### **2. knowledge_gaps**
List all knowledge gaps ranked by curiosity score.

```python
curiosity_awareness({
    "action": "knowledge_gaps",
    "domain": "financial",
    "limit": 10
})
```

**Returns:**
```
**Knowledge Gaps** (5 total)

🔴 financial (score: 0.88)
   No data on CVaR timing before breach
   Type: data_gap
   Suggested: Run CVaR simulations with timing measurements
```

---

### **3. bridge_opportunities**
List cross-domain connection opportunities.

```python
curiosity_awareness({
    "action": "bridge_opportunities",
    "domain1": "quantum",
    "domain2": "healthcare"
})
```

**Returns:**
```
🌉 Bridge Opportunities (2 found)

**quantum ↔ healthcare**
   Insight: Quantum simulation could accelerate drug discovery
   Curiosity Score: 0.92
   Suggested: Research quantum computing in pharmaceutical applications
```

---

### **4. pending_outcomes**
List overdue outcomes awaiting verification.

```python
curiosity_awareness({
    "action": "pending_outcomes",
    "overdue_days": 3
})
```

**Returns:**
```
⏳ Pending Outcomes (2 overdue by 3+ days)

**CVaR timing accuracy needs measurement...**
   Days Pending: 5
   Domain: financial
   Priority: 🔴 High
```

---

### **5. exploration_history**
Review which curiosity explorations paid off.

```python
curiosity_awareness({
    "action": "exploration_history",
    "limit": 10
})
```

**Returns:**
```
**Exploration History** (8 explorations)

✅ quantum (2026-03-15)
   Curiosity Score: 0.88
   Outcome: success
   Quality: 0.85
   Findings: 4

**Success Rate:** 75% (6/8)
Higher success rate = better curiosity calibration
```

---

## When To Use

**At session start:**
```
curiosity_awareness({
    "action": "session_suggestions",
    "current_query": msg.content
})
→ Surfaces relevant knowledge gaps proactively
```

**When user asks about cross-domain topics:**
```
curiosity_awareness({
    "action": "bridge_opportunities",
    "domain1": "quantum",
    "domain2": "healthcare"
})
→ Identifies connection opportunities
```

**To identify verification priorities:**
```
curiosity_awareness({
    "action": "pending_outcomes",
    "overdue_days": 3
})
→ Shows which outcomes need verification
```

**For curiosity calibration:**
```
curiosity_awareness({
    "action": "exploration_history"
})
→ Shows which curiosity-driven explorations paid off
```

---

## Installation Status

```
✅ Tool file: /root/nanojaga/jagabot/agent/tools/curiosity_awareness.py
✅ Skill file: /root/nanojaga/jagabot/skills/curiosity-awareness/SKILL.md
✅ Wired in loop.py: YES
✅ Engine reference: CuriosityEngine
✅ Registered: YES (in AgentLoop __init__)
```

---

## Example Usage

```python
# Check curiosity opportunities at session start
suggestions = curiosity_awareness({
    "action": "session_suggestions",
    "current_query": "research CVaR timing"
})

# Returns:
# 💡 Curiosity Opportunities (2 found)
# 1. financial (score: 0.88)
#    Gap: No data on CVaR timing before breach

# Agent response shaped by this knowledge:
"I notice there's a significant knowledge gap here — we have no verified
data on CVaR timing before breach. This is actually a high-priority
curiosity opportunity (score: 0.88). Would you like me to run simulations
to fill this gap?"
```

---

## Related Tools

- **self_model_awareness** — Query self-model (domain reliability, gaps)
- **confidence_awareness** — Query uncertainty calibration
- **outcome_tracker** — Record verdicts on pending outcomes
- **session_index** — Track session history

---

**Last Updated:** 2026-03-16  
**Version:** 1.0  
**Status:** ✅ Production Ready
