---
metadata: {"jagabot":{"emoji":"🔗","always":false}}
version: 1.0
trigger: infer, logical, chain, fact, implies, causes, derive, deduce, reasoning chain, multi-hop
---

# 🔗 Logical Inference Skill v1.0
## Princeton-style Multi-Hop Verifiable Reasoning

> Use the `inference` tool to store facts and derive conclusions through verifiable chains.
> Confidence degrades with each hop: conf(A→C) = conf(A→B) × conf(B→C)

---

## WHEN TO USE

Use logical inference when:
- Building a knowledge base of verified facts
- Deriving conclusions through multi-step reasoning
- Need traceable evidence for each reasoning step
- Comparing confidence across different reasoning paths
- Zero-shot generalization from 1-2 hop training to 3-5 hop queries

---

## TOOL: inference

### Action: add_fact
Store a verified fact triple.

```json
{
  "action": "add_fact",
  "subject": "NVDA",
  "predicate": "has",
  "object_": "high_volatility",
  "confidence": 0.90,
  "evidence": "Q4 2025 earnings report",
  "domain": "financial"
}
```

**Standard predicates:**
- Causal: `causes`, `implies`, `leads_to`, `prevents`
- Properties: `has`, `lacks`, `increases`, `decreases`
- Risk: `amplifies`, `mitigates`, `correlates_with`
- State: `is`, `was`, `requires`, `enables`

### Action: query
Find inference chain between two concepts.

```json
{
  "action": "query",
  "subject": "NVDA",
  "object_": "margin_risk",
  "max_hops": 3
}
```

Returns:
- Full reasoning chain with each hop
- Confidence calculation (multiplicative)
- Evidence for each step
- Human-readable explanation

### Action: infer_all
All conclusions reachable from a concept.

```json
{
  "action": "infer_all",
  "subject": "supply_chain_disruption",
  "max_hops": 2
}
```

Returns ranked list of (conclusion, confidence, path).

### Action: stats
Show inference engine statistics.

```json
{
  "action": "stats"
}
```

Returns: total facts, verified facts, inferences run, avg hops, avg confidence, domains.

---

## EXAMPLE WORKFLOW

### Step 1: Store base facts
```
inference(action="add_fact",
  subject="NVDA", predicate="has", object_="high_volatility",
  confidence=0.90, evidence="historical data", domain="financial")

inference(action="add_fact",
  subject="high_volatility", predicate="implies", object_="margin_risk",
  confidence=0.85, evidence="risk management principles", domain="risk")
```

### Step 2: Query for chain
```
inference(action="query",
  subject="NVDA", object_="margin_risk", max_hops=3)
```

**Expected output:**
```
## Inference Chain (2 hops)
**Query:** nvda → margin_risk
**Confidence:** 76%

**Reasoning chain:**
  1. `nvda` --[**has**]--> `high_volatility` (conf: 90%)
     Evidence: historical data
  2. `high_volatility` --[**implies**]--> `margin_risk` (conf: 85%)
     Evidence: risk management principles

**Verdict:** nvda has (via 2-hop chain) → margin_risk [76% confidence]
```

### Step 3: Infer all conclusions
```
inference(action="infer_all",
  subject="NVDA", max_hops=2)
```

---

## CONFIDENCE CALCULUS

**Multiplicative degradation:**
- 1 hop: conf = 0.90
- 2 hops: conf = 0.90 × 0.85 = 0.765
- 3 hops: conf = 0.90 × 0.85 × 0.80 = 0.612
- 4 hops: conf = 0.90 × 0.85 × 0.80 × 0.75 = 0.459

**Pruning threshold:** Chains below 0.30 confidence are discarded.

**Warning flags:**
- ⚠️ LOW CONFIDENCE — below 50%
- ✂️ PRUNED — below 30% threshold

---

## ANTI-PATTERNS

❌ Storing unverified claims as facts (use confidence < 0.5)
❌ Chaining beyond 5 hops (confidence too degraded)
❌ Using non-standard predicates (breaks formal vocabulary)
❌ Ignoring confidence degradation (overconfident conclusions)
❌ Storing surface patterns instead of logical structure

---

## QUALITY MARKERS

✅ Each fact has explicit evidence source
✅ Confidence reflects evidence quality (not symmetric 80% everywhere)
✅ Chains are traceable — each hop citable
✅ Formal predicates used consistently
✅ Domain tagged for cross-domain analysis

---

## CROSS-DOMAIN ANALOGIES

The inference engine learns logical STRUCTURE not surface content.

Example transfer:
```
Financial: "high_volatility" →[implies]→ "margin_risk"
Risk:      "supply_concentration" →[implies]→ "disruption_risk"
Health:    "immune_suppression" →[implies]→ "infection_risk"
```

Same logical form: `vulnerability →[implies]→ exposure_consequence`

This enables zero-shot generalization across domains.
