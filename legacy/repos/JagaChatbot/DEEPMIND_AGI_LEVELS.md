# DeepMind AGI Levels Framework

This project is structured around the DeepMind AGI Levels framework, which defines progressive capabilities for AI systems.

## The 5 Levels

| Level | Name | Description | Example |
|-------|------|-------------|---------|
| **1** | Chatbot | Natural conversation, no external knowledge | ChatGPT, JagaChatbot |
| **2** | Reasoner | Reasoning over provided knowledge | RAG systems, JagaRAG |
| **3** | Agent | Uses tools, takes actions | Devin, AutoJaga-Base |
| **4** | Innovator | Creates novel solutions | Research assistants |
| **5** | Organization | Coordinates multiple agents | Enterprise AI |

## JagaChatbot — Level 1

**What it does:**
- Holds natural conversations
- Remembers past messages (within session)
- Routes to multiple LLM providers
- Compresses long histories

**What it doesn't do:**
- Retrieve external documents
- Use tools or APIs
- Plan multi-step actions

**Key insight:** Level 1 establishes the foundation. Without reliable conversation handling, higher levels fail.

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
    │  + Multi-agent orchestration
    │  + BDI reasoning
    ▼
AutoJaga-Base (Level 3)
```

## Why This Matters

Framing projects against the DeepMind framework:
1. Shows awareness of AI capability progression
2. Demonstrates intentional architecture decisions
3. Creates a coherent portfolio narrative
4. Aligns with industry-standard benchmarks

## References

- [DeepMind AGI Levels Paper](https://arxiv.org/abs/2311.02462)
- [Levels of AGI: Operationalizing Progress on the Path to AGI](https://deepmind.google/research/publications/levels-of-agi/)
