# DeepMind AGI Levels Framework

This project is structured around the DeepMind AGI Levels framework.

## The 5 Levels

| Level | Name | Description | Example |
|-------|------|-------------|---------|
| **1** | Chatbot | Natural conversation, no external knowledge | ChatGPT, JagaChatbot |
| **2** | Reasoner | Reasoning over provided knowledge | RAG systems, JagaRAG |
| **3** | Agent | Uses tools, takes actions | Devin, **AutoJaga-Base** |
| **4** | Innovator | Creates novel solutions | Research assistants |
| **5** | Organization | Coordinates multiple agents | Enterprise AI |

## AutoJaga-Base — Level 3

**What it does:**
- Everything Level 2 does (conversation, memory, RAG)
- Executes tools (web search, file operations, shell commands)
- Scores its own autonomy via BDI scorecard
- Detects and prevents fabricated claims
- Orchestrates multiple specialist agents

**What it doesn't do:**
- Generate truly novel research approaches (Level 4)
- Self-organize into specialized teams (Level 5)

**Key insight:** Level 3 is the "action" level. The agent doesn't just retrieve and reason — it acts in the world and observes consequences.

## BDI Framework

AutoJaga uses a **Belief-Desire-Intention** scoring system:

| Dimension | What it measures | Target |
|-----------|------------------|--------|
| **Belief** | Did agent verify assumptions? | 2.5/2.5 |
| **Desire** | Did agent persist through failures? | 2.5/2.5 |
| **Intention** | Did agent use tools effectively? | 2.5/2.5 |
| **Anomaly** | Did agent avoid chaotic behavior? | 2.5/2.5 |

**Scoring:**
- **0-4**: Reactive Script (just follows prompts)
- **4-6**: Emerging Agent (some autonomous behavior)
- **6+**: Autonomous Strategist (truly agentic)

## Anti-Fabrication

Level 3 agents can hallucinate tool results. AutoJaga's harness catches this:

```
Agent: "I created the file report.md"
Harness: "No write_file was called. Fabrication detected."
```

This is critical for trust — an agent that lies about its actions is dangerous.

## Progression Path

```
JagaChatbot (Level 1)
    │
    │  + Vector memory
    │  + Document ingestion
    │  + Retrieval-grounded responses
    ▼
JagaRAG (Level 2)
    │
    │  + Tool binding
    │  + Tool execution loop
    │  + BDI scoring
    │  + Anti-fabrication
    │  + Swarm orchestration
    ▼
AutoJaga-Base (Level 3)  ← YOU ARE HERE
    │
    │  (Future: Self-modifying strategies)
    ▼
??? (Level 4)
```

## References

- [DeepMind AGI Levels Paper](https://arxiv.org/abs/2311.02462)
- [BDI Agent Architecture](https://en.wikipedia.org/wiki/Belief%E2%80%93desire%E2%80%93intention_software_model)
- [Tool Use in LLMs](https://arxiv.org/abs/2305.16291)
