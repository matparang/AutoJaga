# JagaRAG

> **DeepMind AGI Level 2 — Retrieval-Augmented Reasoner**

A RAG-enhanced chatbot that retrieves relevant documents before answering, reducing hallucinations and grounding responses in real knowledge.

![Level 2](https://img.shields.io/badge/DeepMind%20AGI-Level%202%20Reasoner-purple)
![Python](https://img.shields.io/badge/Python-3.11+-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## What is JagaRAG?

JagaRAG extends [JagaChatbot](https://github.com/matparang/JagaChatbot) (Level 1) with retrieval-augmented generation:

- **Everything in JagaChatbot** — Multi-provider LLM routing, memory, compression
- **Vector memory** — Semantic search with sentence-transformers
- **Document ingestion** — Ingest txt, md, pdf files into searchable chunks
- **Grounded responses** — Automatically retrieves relevant context before answering
- **Source citations** — Responses reference the documents they drew from

This is **Level 2** in the [DeepMind AGI Levels framework](DEEPMIND_AGI_LEVELS.md): a reasoner that can draw on external knowledge to answer questions more accurately.

---

## 5-Minute Quickstart

### 1. Install

```bash
git clone https://github.com/matparang/JagaRAG.git
cd JagaRAG
pip install -e .
```

### 2. Configure

```bash
# Option A: Environment variable
export OPENAI_API_KEY="sk-..."

# Option B: Config file
cp .env.example ~/.jagaragbot/.env
```

### 3. Ingest Documents

```bash
# In the CLI
python -m jagaragbot

> /ingest ~/Documents/research_notes.md
Ingested research_notes.md: 12 chunks

> /ingest ~/Documents/papers/
Ingested 5 files
```

### 4. Ask Questions

```bash
> What does the research say about Styrax compounds?

🐈 JagaRAG:
Based on the retrieved documents [1][2], the research indicates that
Styrax compounds show promising antimicrobial properties...

[1] research_notes.md (relevance: 0.87)
[2] styrax_analysis.md (relevance: 0.72)
```

---

## Demo: Mangliwood Research Data

JagaRAG includes a demo dataset based on real botanical research:

```bash
# Ingest the demo data
python -m jagaragbot
> /ingest demo_data/

# Ask about the research
> What are the key findings from the Mangliwood specimens?
> What compounds were identified in the SCOPE analysis?
```

The demo data contains:
- Mangliwood specimen notes
- SCOPE (Secondary Compound Profiling for Endangered species) research summaries
- Styrax benzoin chemical analysis

This is **your unique demo story** — no other developer has this data.

---

## Architecture

```
jagaragbot/
├── __main__.py              # Entry point
├── agent/
│   ├── loop.py              # RAG-enhanced chat loop
│   ├── context.py           # System prompt builder
│   ├── memory.py            # Long-term memory
│   └── compressor.py        # Token compression
├── memory/
│   └── vector_memory.py     # Semantic search with embeddings
├── ingestion/
│   └── pipeline.py          # Document chunking and indexing
├── providers/
│   └── litellm_provider.py  # Multi-provider LLM routing
├── config/
│   └── schema.py            # Configuration
└── cli/
    └── interactive.py       # Rich terminal interface
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed component flow.

---

## How RAG Works

```
┌──────────────────────────────────────────────────────────────────┐
│                        USER QUERY                                 │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                     VECTOR MEMORY SEARCH                          │
│  • Encode query as embedding                                      │
│  • Find top-k similar document chunks                             │
│  • Return with similarity scores                                  │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                     CONTEXT INJECTION                             │
│  • Format retrieved chunks                                        │
│  • Add to system prompt                                           │
│  • Include source references                                      │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                        LLM GENERATION                             │
│  • Answer grounded in retrieved context                           │
│  • Cite sources naturally                                         │
│  • Acknowledge when info not found                                │
└──────────────────────────────────────────────────────────────────┘
```

---

## Configuration

Configuration at `~/.jagaragbot/config.json`:

```json
{
  "providers": {
    "openai": {"api_key": "sk-..."}
  },
  "defaults": {
    "model": "openai/gpt-4o-mini",
    "retrieval_k": 3
  }
}
```

---

## Smoke Test

```bash
python -m pytest tests/test_smoke.py -v
```

---

## Related Projects

| Repo | Level | Description |
|------|-------|-------------|
| [JagaChatbot](https://github.com/matparang/JagaChatbot) | Level 1 | Conversational chatbot |
| **JagaRAG** (this) | Level 2 | Retrieval-augmented reasoning |
| [AutoJaga-Base](https://github.com/matparang/AutoJaga-Base) | Level 3 | Autonomous multi-agent system |

---

## License

MIT — see [LICENSE](LICENSE)

---

## Author

Built by [@matparang](https://github.com/matparang)
