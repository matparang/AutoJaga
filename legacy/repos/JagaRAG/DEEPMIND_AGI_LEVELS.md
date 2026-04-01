# DeepMind AGI Levels Framework

This project is structured around the DeepMind AGI Levels framework.

## The 5 Levels

| Level | Name | Description | Example |
|-------|------|-------------|---------|
| **1** | Chatbot | Natural conversation, no external knowledge | ChatGPT, JagaChatbot |
| **2** | Reasoner | Reasoning over provided knowledge | RAG systems, **JagaRAG** |
| **3** | Agent | Uses tools, takes actions | Devin, AutoJaga-Base |
| **4** | Innovator | Creates novel solutions | Research assistants |
| **5** | Organization | Coordinates multiple agents | Enterprise AI |

## JagaRAG — Level 2

**What it does:**
- Everything Level 1 does (conversation, memory, compression)
- Ingests documents into vector memory
- Retrieves relevant chunks for each query
- Grounds responses in retrieved knowledge
- Cites sources naturally

**What it doesn't do:**
- Use external tools or APIs
- Take actions in the world
- Plan multi-step strategies

**Key insight:** Level 2 is the "show your work" level. Instead of generating answers from training data alone, the system explicitly retrieves and cites relevant documents.

## Progression Path

```
JagaChatbot (Level 1)
    │
    │  + Vector memory
    │  + Document ingestion
    │  + Retrieval-grounded responses
    ▼
JagaRAG (Level 2)  ← YOU ARE HERE
    │
    │  + Tool binding
    │  + Multi-agent orchestration
    │  + BDI reasoning
    ▼
AutoJaga-Base (Level 3)
```

## Why RAG Matters

1. **Reduces hallucination**: Responses grounded in actual documents
2. **Auditable**: Can trace claims back to sources
3. **Updatable**: Add new knowledge without retraining
4. **Domain-specific**: Excel in narrow domains with targeted data

## The Mangliwood Demo

JagaRAG includes a unique demo dataset from real botanical research:
- Mangliwood specimen notes
- SCOPE analysis results
- Styrax compound data

This demonstrates RAG on **novel data** — information the LLM was never trained on, proving retrieval is actually working.

## References

- [DeepMind AGI Levels Paper](https://arxiv.org/abs/2311.02462)
- [RAG vs Fine-tuning](https://www.anyscale.com/blog/a-comprehensive-guide-for-building-rag-based-llm-applications-part-1)
