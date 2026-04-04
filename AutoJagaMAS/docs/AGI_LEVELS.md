# AGI Levels — Where AutoJagaMAS Sits

## The DeepMind AGI Levels Framework

DeepMind's 2023 framework defines AGI maturity across six levels (0–5),
assessed on two axes: **breadth** (narrow vs. general) and **performance**
(compared to unskilled humans, skilled humans, and experts).

| Level | Name | Description |
|-------|------|-------------|
| 0 | No AI | Rule-based, no learned model |
| 1 | Emerging | Matches or exceeds unskilled humans on some tasks |
| 2 | Competent | Matches or exceeds 50th-percentile skilled adults |
| 3 | Expert | Matches or exceeds 90th-percentile domain experts |
| 4 | Virtuoso | Matches or exceeds top-0.1% experts |
| 5 | Superhuman | Exceeds all humans on all cognitive tasks |

---

## AutoJaga Product Line — Level Positioning

### JagaChatbot — Level 0 (Narrow)

**Repository:** `JagaChatbot/`

- Single LLM call per turn, no tools, no memory
- Outputs text only — no actions in the world
- Cannot access external data, cannot update its own state
- **Classification:** Level 0 Narrow — no tools, no reasoning, pure language I/O

```
Breadth: Narrow (single task: chat)
Performance: Emerging (matches casual conversation, not expert domain tasks)
```

---

### JagaRAG — Level 0 (Narrow, Retrieval-Augmented)

**Repository:** `JagaRAG/`

- Retrieval-augmented generation: searches document index before answering
- Grounded in documents, reduces hallucination
- Still single-turn, still no tool use beyond retrieval
- **Classification:** Level 0 Narrow — retrieval improves accuracy but not capability breadth

```
Breadth: Narrow (single task: document-grounded Q&A)
Performance: Emerging (matches a research assistant reading a specific document set)
```

---

### AutoJaga — Level 1 (Emerging, Agentic)

**Repository:** `AutoJaga/`

- Multi-turn agent loop with tool use (web search, file read/write, exec, memory)
- BDI cognitive stack: fluid dispatching, belief engine, brier scorer
- Calibrated confidence, self-model awareness
- Two-tier model routing: fast local model for routine, cloud model for complex
- **Classification:** Level 1 Emerging — multi-step tool use with calibrated reasoning

```
Breadth: Narrow-to-emerging (works across several task types: research, code, analysis)
Performance: Emerging (matches a skilled research assistant on structured tasks)
```

What's missing for Level 2:
- Persistent self-improvement (learning from verified outcomes — partially implemented via BrierScorer)
- Generalisation across unseen domains without prompt engineering
- Calibrated uncertainty across all domains (not just trained profiles)

---

### AutoJagaMAS — Level 1→2 Bridge (Multi-Agent Graph Orchestration)

**Repository:** `AutoJagaMAS/` (this folder)

- 5-agent swarm with cognitive BDI at each node
- Conductor orchestrates specialist agents (botanist, chemist, pathologist)
- Synthesiser combines findings into calibrated research brief
- BDI state flows through graph edges — agents can read each other's confidence
- Model routing per node: local for retrieval, cloud for synthesis
- **Classification:** Level 1→2 Bridge — multi-agent orchestration with cross-agent belief sharing

```
Breadth: Emerging (multiple specialist domains in a single research task)
Performance: Competent (approaches expert-level for well-defined research synthesis tasks)
```

### What makes this a Level 1→2 Bridge (not full Level 2)?

| Criterion for Level 2 | AutoJagaMAS Status |
|------------------------|-------------------|
| Persistent memory across sessions | ✅ BrierScorer + memory fleet |
| Self-improvement from verified outcomes | 🔶 Partial — BrierScorer records, but loop not yet closed |
| Calibrated confidence across all domains | 🔶 Partial — works for configured profiles |
| Multi-agent coordination | ✅ Full graph orchestration |
| Tool use across domains | ✅ Web search, file ops, exec, memory |
| Generalisation to unseen tasks | ❌ Still requires persona engineering |

---

## What's Needed for Full Level 2 (Competent AGI)

1. **Closed self-improvement loop** — BrierScorer records outcomes, CognitiveStack reads trust
   history and adjusts tier thresholds without human prompt changes.

2. **Cross-domain calibration** — BeliefEngine must generalise confidence calibration
   across all domains, not just configured profiles (RESEARCH, CALIBRATION, etc.).

3. **Persistent swarm memory** — Agents share a vector memory store so findings from
   one research session inform the next without re-running the full swarm.

4. **Verifiable reasoning chains** — Each claim in the synthesiser output is annotated
   with provenance (which specialist, which source, what confidence level).

5. **NemoClaw integration** — JagaShellResult feeds into NemoClaw's reasoning pipeline
   for adversarial cross-examination of swarm outputs.
   (See: `contracts/jagashell_contract.py` — `# TODO: wire to NemoClaw when v0.3 stable`)

---

## Summary

```
Level 0  ──  JagaChatbot (chat only)
Level 0  ──  JagaRAG (retrieval + chat)
Level 1  ──  AutoJaga (tool-using agent)
Level 1→2 ─  AutoJagaMAS (multi-agent swarm)    ← WE ARE HERE
Level 2  ──  (requires closed self-improvement loop)
Level 3  ──  (expert-level across all domains)
```
