# Repository Restructuring Decisions

This document records key decisions made during the AutoJaga → 3 Repos restructuring.

## Repo Structure Decisions

### 1. Package Naming
- **JagaChatbot** → `jagachatbot` (clean, distinct from original)
- **JagaRAG** → `jagaragbot` (indicates RAG extension)
- **AutoJaga-Base** → `autojaga` (inherits original name for Level 3)

### 2. Duplicate File Resolution

| Duplicate Pair | Winner | Reason |
|----------------|--------|--------|
| `context.py` vs `context_builder.py` | `context.py` for L1/L2, `context_builder.py` for L3 | context.py is simpler, context_builder.py has dynamic tool relevance |
| `history_compressor.py` vs `context_compressor.py` | `compressor.py` (from agent/) for L1/L2 | 3-layer micro-compact is production-ready |
| `history_compressor.py` vs `context_compressor.py` | Both for L3 | Advanced turn tracking needed |

### 3. Financial Domain Decision
- **Excluded from all 3 repos** — financial tools (FinancialCV, MonteCarlo, VaR, CVaR, Yahoo Finance) are domain-specific
- Demo will use Mangliwood botanical research data instead (unique, compelling, non-financial)

### 4. MCP WebSearch Binding
- **JagaChatbot/JagaRAG**: Use `WebSearchTool` with Brave API (simple, proven)
- **AutoJaga-Base**: Include both `WebSearchTool` and `WebSearchMcpTool` (DuckDuckGo bridge)
- Tool is passed as object at spawn in `subagent.py:116` ✓

### 5. loop.py Split Strategy (AutoJaga-Base only)
Conservative extraction approach:
1. Keep `loop.py` as main orchestrator (~1000 lines)
2. Extract `loop_components.py` — all __init__ component wiring
3. Extract `tool_executor.py` — tool call execution
4. Use existing `fluid_dispatcher.py` for BDI routing

### 6. Files Excluded (All Repos)
- All `.bak`, `.backup`, `.prebridge` files
- Dead directories: A2A/, 2engine/, 2modelfluid/, ContextENG/, Selfmodel/, ProactiveCLI/, REPGuard/, Usereasy/, YOLOJAGA/
- BAK1/ directory
- case/ directory (31MB GIFs → replaced with video link)
- Empty tool stubs (<40 bytes)

### 7. Inheritance Strategy
- **JagaRAG** copies JagaChatbot code (not imports) — enables standalone deployment
- **AutoJaga-Base** copies JagaRAG code — same reason
- Each repo is fully self-contained, no cross-repo dependencies

---

## DeepMind AGI Level Mapping

| Repo | Level | Description | Key Capability |
|------|-------|-------------|----------------|
| JagaChatbot | 1 | Chatbot | Multi-provider LLM routing, conversation memory |
| JagaRAG | 2 | Reasoner | Vector retrieval, grounded responses |
| AutoJaga-Base | 3 | Agent | Tool use, multi-agent orchestration, BDI reasoning |

---

## Open Questions (Resolved)
1. ✅ Where to create repos? → `/repos/` in this branch
2. ✅ Demo data? → Mangliwood botanical research (unique)
3. ✅ Financial tools? → Excluded (domain-specific)
