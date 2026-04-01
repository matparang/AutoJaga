---
name: investment_thesis
description: Structured investment thesis workflow — clarify → explore → present → save
metadata: {"jagabot":{"emoji":"💡","trigger":"investment_thesis"}}
---

# Investment Thesis Skill

## TRIGGER
User mentions: new investment idea, should I invest, research opportunity, thesis, undervalued, entry point

## PURPOSE
Generate a structured, evidence-based investment thesis using JAGABOT's full analytical toolkit. Follows a Socratic method to clarify assumptions, explores alternatives, and presents a complete thesis with entry/exit criteria.

## WORKFLOW

### Step 1: CLARIFY (Socratic)
Ask the user:
1. "What sector/asset are you interested in?"
2. "What's your investment horizon? (days / weeks / months / years)"
3. "What's your risk tolerance? (conservative / moderate / aggressive)"
4. "What's your position size budget?"

### Step 2: EXPLORE
Use tools to gather evidence:
- `financial_cv` → Analyse volatility regime of the asset
- `bayesian` → Assess base probability of thesis success
- `multi_perspective` → Get Bull/Bear/Buffet views
- `correlation` → Check correlation with existing portfolio
- `monte_carlo` → Simulate forward returns

### Step 3: PRESENT
Structure the thesis in 4 sections:
- **Section 1: Opportunity** — What's the edge? Why now?
- **Section 2: Risks** — Key risk factors with probabilities
- **Section 3: Entry/Exit Criteria** — Price targets, stop-loss, time limit
- **Section 4: Position Sizing** — Based on risk tolerance and Kelly criterion

### Step 4: REVIEW
- `review` → spec_check (ensure all 4 sections populated)
- `review` → quality_check (score ≥ 0.7)

### Step 5: SAVE
- `memory_fleet` → Store thesis with tags: #thesis, #asset_name
- `knowledge_graph` → Link to related assets and events

## TOOLS USED
- financial_cv, monte_carlo, bayesian, multi_perspective, correlation
- review (two-stage), memory_fleet, knowledge_graph

## COMPOSABLE
- Called by: skill_trigger (when investment_thesis detected)
- Calls: portfolio_review (to check fit with existing holdings)

## TEST CASES
- Case 1: "Should I invest in oil?" → Must produce all 4 thesis sections
- Case 2: "AAPL entry point?" → Must include price targets and stop-loss
