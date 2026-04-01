# JagaRAG Architecture

## Component Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INPUT                                │
│                     (CLI / Channel)                              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                        RAGLoop                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   VectorMemory.search()                  │    │
│  │  • Encode query as embedding                             │    │
│  │  • Calculate cosine similarity                           │    │
│  │  • Return top-k relevant chunks                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                             │                                    │
│                             ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    ContextBuilder                        │    │
│  │  • Build system prompt                                   │    │
│  │  • Inject retrieved documents                            │    │
│  │  • Add conversation history                              │    │
│  └─────────────────────────────────────────────────────────┘    │
│                             │                                    │
│                             ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    LLMProvider                           │    │
│  │  • Call API with grounded context                        │    │
│  │  • Generate response                                     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                             │                                    │
│                             ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    MemoryStore                           │    │
│  │  • Log query + sources + response                        │    │
│  │  • Update history                                        │    │
│  └─────────────────────────────────────────────────────────┘    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    GROUNDED RESPONSE                             │
│                  (with source citations)                         │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### RAGLoop (`agent/loop.py`)
The main orchestrator. Extends ChatLoop with retrieval:
1. Search vector memory for relevant chunks
2. Inject retrieved context into prompt
3. Call LLM
4. Return response with source attribution

### VectorMemory (`memory/vector_memory.py`)
Semantic search over ingested documents:
- Uses sentence-transformers for embeddings (all-MiniLM-L6-v2)
- Cosine similarity for ranking
- Falls back to keyword search if no embeddings available

### DocumentIngester (`ingestion/pipeline.py`)
Document processing pipeline:
- Reads txt, md, pdf files
- Chunks into ~500 character segments with overlap
- Stores in vector memory with metadata

### ContextBuilder (`agent/context.py`)
Assembles the full prompt:
- Core identity
- Retrieved document context (injected here)
- Long-term memory
- Conversation history

## Ingestion Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                      DOCUMENT INPUT                              │
│                (file.txt, file.md, file.pdf)                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      read_file()                                 │
│  • txt/md: read as text                                          │
│  • pdf: extract with pypdf                                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      chunk_text()                                │
│  • Split by paragraphs                                           │
│  • Target 500 chars per chunk                                    │
│  • 50 char overlap between chunks                                │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   VectorMemory.add_document()                    │
│  • Encode chunk as embedding                                     │
│  • Store with source metadata                                    │
│  • Save to disk                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## File Locations

```
~/.jagaragbot/
├── config.json              # User configuration
├── workspace/
│   └── memory/
│       ├── MEMORY.md        # Long-term facts
│       ├── HISTORY.md       # Conversation log
│       ├── vectors.npy      # Embeddings (numpy)
│       └── vector_metadata.json  # Document chunks + metadata
└── .env                     # Environment variables
```

## Retrieval Algorithm

1. **Query encoding**: Convert user query to embedding vector
2. **Similarity search**: Calculate cosine similarity with all stored vectors
3. **Ranking**: Sort by similarity descending
4. **Top-k selection**: Return k most relevant chunks (default k=3)
5. **Context injection**: Format chunks into system prompt

## Fallback Behavior

When `sentence-transformers` is not installed:
- VectorMemory falls back to keyword matching
- Still functional, but less semantic
- Install for full capability: `pip install sentence-transformers`
