Good input from GPT. The key upgrade is making **mini the default thinker** that decides complexity, not just the executor. Let me build this:

Two files. Here's what changed from the original ModelSwitchboard and why.

## The Key Insight GPT Added

The original ModelSwitchboard was still sending full answers through Model 2. GPT identified the smarter pattern:

```
Before: User asks complex question
         → Model 2 produces 3000 token full answer
         Cost: ~$0.0075

After: User asks complex question
         → Model 2 produces 400 token PLAN (JSON steps)
         → Model 1 executes each step (~500 tokens each)
         → Model 1 synthesizes final answer
         Cost: ~$0.0015 (80% cheaper per complex turn)
```

Model 2 now only thinks. Model 1 does all the work.

## The Complete Architecture

```
FluidDispatcher → which engines and tools load (no LLM, < 50ms)
CognitiveStack → which model handles each step (M1 classifies first)

Together they answer two questions before every LLM call:
  1. What context does the agent need? → FluidDispatcher
  2. Which model should handle this? → CognitiveStack
```

## The Self-Repair Loop (GPT's Point 4)

```
Model 1 executes step 3
       ↓
Step fails with error
       ↓
Model 2 diagnoses: "missing data — try web_search first"
       ↓
Model 2 produces repair plan: ["search X", "then calculate"]
       ↓
Model 1 executes repair steps
       ↓
Output recovered
```

This is the cognitive escalation system GPT described — and it's now built directly into `CognitiveStack._model2_repair()`.
