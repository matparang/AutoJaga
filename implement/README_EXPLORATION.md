# JAGABOT CODEBASE EXPLORATION — README

This directory contains a complete analysis of the jagabot codebase infrastructure.

## 📋 Documents in This Folder

### 1. **CODEBASE_EXPLORATION.md** (15 KB) — Detailed Technical Analysis
Comprehensive breakdown of:
- ✅ Existing MCP client & server infrastructure
- ✅ Two tool registry implementations (Swarm vs Agent)
- ✅ Evolution engine with 4-layer safety
- ✅ CLI structure with Typer
- ✅ Configuration system with Pydantic
- ✅ 32 built-in tools catalog

**Best for:** Understanding the full architecture in detail

### 2. **QUICK_REFERENCE.md** (8.5 KB) — Cheat Sheet
Quick lookup guide with:
- 🔍 Key facts table (versions, paths)
- 🛠️ Registry API comparison
- 🚀 MCP integration summary
- 🧬 Evolution engine quick methods
- ⚙️ Config system overview
- 🔗 Copy-paste code examples
- 🎯 Key implementation insights

**Best for:** Quick lookup during development

### 3. **FILE_REFERENCE_MAP.md** (6 KB) — File Navigation
- 📍 All key files with sizes and purposes
- 📦 Complete directory tree
- 🗂️ Tool files catalog (32 tools)
- 📄 MCP-related files list
- 🔎 Quick navigation guide

**Best for:** Finding specific files quickly

---

## 🎯 Quick Start by Use Case

### "I need to understand the tool system"
1. Read: QUICK_REFERENCE.md → "Tool Registry Quick Comparison"
2. Read: CODEBASE_EXPLORATION.md → "Section 2: Tool Registry"
3. View: `/root/nanojaga/jagabot/agent/tools/base.py`
4. View: `/root/nanojaga/jagabot/agent/tools/registry.py`

### "I need to integrate MCP servers"
1. Read: QUICK_REFERENCE.md → "MCP Integration"
2. Read: CODEBASE_EXPLORATION.md → "Section 1: MCP"
3. View: `/root/nanojaga/nanobot/nanobot/agent/tools/mcp.py`
4. Copy example from QUICK_REFERENCE.md → "Example 3: Connect MCP Server"

### "I need to understand the evolution engine"
1. Read: QUICK_REFERENCE.md → "Evolution Engine"
2. Read: CODEBASE_EXPLORATION.md → "Section 3: Evolution Engine"
3. View: `/root/nanojaga/jagabot/evolution/engine.py`
4. Study: `/root/nanojaga/jagabot/evolution/targets.py`

### "I need to modify configuration"
1. Read: QUICK_REFERENCE.md → "Config System"
2. View: `/root/nanojaga/jagabot/config/schema.py`
3. View: `/root/nanojaga/jagabot/config/loader.py`
4. Edit: `~/.jagabot/config.json`

### "I need to add a new tool"
1. Read: CODEBASE_EXPLORATION.md → "Section 2.C: Base Tool Class"
2. View: `/root/nanojaga/jagabot/agent/tools/base.py`
3. Copy example tool from any file in `/root/nanojaga/jagabot/agent/tools/`
4. Add to: `/root/nanojaga/jagabot/guardian/tools/__init__.py` (ALL_TOOLS list)

---

## 📊 Key Statistics

| Metric | Value |
|--------|-------|
| **Jagabot Version** | 0.1.0 |
| **Total Tool Registries** | 2 (Swarm + Agent) |
| **Built-in Tools** | 32 |
| **MCP Servers** | 1 (DeepSeek, v0.4.0) |
| **LLM Providers** | 14 |
| **Config Sections** | 5 (agents, channels, providers, gateway, tools) |
| **Evolution Layers** | 4 (safety) |
| **Tunable Parameters** | 5 |

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      JAGABOT 0.1.0                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐         ┌──────────────┐                 │
│  │  CLI (Typer) │────────→│ ToolRegistry │←──────┐         │
│  └──────────────┘         └──────────────┘       │         │
│        ↓                        ↓                 │         │
│   [prompt_toolkit]        [Validation]      [Execute]      │
│   [history]               [Async]                │         │
│   [multiline]                                    │         │
│                                                  ↓         │
│  ┌──────────────┐         ┌──────────────┐  ┌────────┐    │
│  │Config System │         │   32 Tools   │  │  MCP   │    │
│  │ (Pydantic)   │         │  (Financial/ │  │Wrapper │    │
│  └──────────────┘         │   Analysis)  │  └────────┘    │
│    JSON + ENV              └──────────────┘      ↓         │
│                                                   │         │
│  ┌──────────────┐         ┌──────────────┐      │         │
│  │   Evolution  │         │   Swarm      │  [MCP Servers] │
│  │   Engine     │         │  Registry    │  [stdio/HTTP]  │
│  │(4-layer)     │         │(class map)   │                │
│  └──────────────┘         └──────────────┘                │
│   [Mutation]                                               │
│   [Sandbox]                                                │
│   [Fitness]                                                │
│   [Rollback]                                               │
│                                                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔍 File Lookup Quick Index

**Core Framework:**
- Version & branding → `jagabot/__init__.py`
- Tool base class → `jagabot/agent/tools/base.py` (103 LOC)
- Full registry → `jagabot/agent/tools/registry.py` (74 LOC)
- Lightweight registry → `jagabot/swarm/tool_registry.py` (40 LOC)

**Evolution:**
- Main engine → `jagabot/evolution/engine.py` (499 LOC)
- Parameters → `jagabot/evolution/targets.py` (38 LOC)

**Configuration:**
- Schema → `jagabot/config/schema.py` (310 LOC)
- Loader → `jagabot/config/loader.py` (107 LOC)

**CLI:**
- Commands → `jagabot/cli/commands.py`
- Lab → `jagabot/cli/lab_commands.py`

**Tools:**
- All tools → `jagabot/agent/tools/__init__.py`
- Master list → `jagabot/guardian/tools/__init__.py`
- Tool files → `jagabot/agent/tools/` (32 files)

**MCP:**
- Server (TS) → `deepseek-mcp-server/src/mcp-server.ts`
- Client (Py) → `nanobot/nanobot/agent/tools/mcp.py`

---

## 💡 Key Insights

1. **Dual Registry Pattern**
   - Swarm: lightweight, class-based, read-only (40 LOC)
   - Agent: full-featured, instance-based, async (74 LOC)
   - Both exist for different use cases

2. **MCP Already Integrated**
   - Standalone DeepSeek MCP server exists (TypeScript)
   - Generic MCP client wrapper in Nanobot
   - Can connect any MCP server to any ToolRegistry

3. **Configuration is First-Class**
   - Pydantic-based schema with validation
   - JSON file + environment variable support
   - 14 LLM providers pre-configured
   - 9 communication channels

4. **Evolution is Conservative**
   - 4-layer safety prevents runaway mutations
   - 100-cycle governor prevents rapid changes
   - All state persisted to JSON
   - Fitness-driven acceptance

5. **Tools are Async-First**
   - All tools use `async def execute()`
   - Registry.execute() is async
   - Validation happens before execution
   - 32 built-in tools covering financial analysis, ML, and meta-learning

---

## 🚀 Getting Started

### Step 1: Read the Overview
```bash
cat QUICK_REFERENCE.md  # 2 min read
```

### Step 2: Understand Tool System
```bash
head -200 CODEBASE_EXPLORATION.md  # Section 1 & 2
view jagabot/agent/tools/base.py
```

### Step 3: Explore Your Use Case
Use the "Quick Start by Use Case" section above to dive deeper into specific areas.

### Step 4: Reference as Needed
- Need a file? → FILE_REFERENCE_MAP.md
- Need quick API? → QUICK_REFERENCE.md
- Need details? → CODEBASE_EXPLORATION.md

---

## 📁 File Locations (Absolute Paths)

All files referenced are under `/root/nanojaga/`:

```
/root/nanojaga/
├── jagabot/                    # Main framework
├── deepseek-mcp-server/        # MCP Server (TS)
├── nanobot/                    # Nanobot (MCP client)
├── implement/                  # This directory
└── [other directories]
```

---

## 🔗 Cross-References

| Term | Found In |
|------|----------|
| ToolRegistry | CODEBASE, QUICK_REFERENCE, base.py, registry.py |
| EvolutionEngine | CODEBASE, QUICK_REFERENCE, engine.py |
| MCP | CODEBASE, QUICK_REFERENCE, mcp.py, mcp-server.ts |
| Config | CODEBASE, QUICK_REFERENCE, schema.py, loader.py |
| Tool (base) | CODEBASE, base.py, registry.py |
| 32 Tools | QUICK_REFERENCE, ALL_TOOLS, guardian/tools/ |

---

## 📞 Need Help?

1. **Understanding architecture?** → CODEBASE_EXPLORATION.md
2. **Looking for quick answer?** → QUICK_REFERENCE.md
3. **Finding a specific file?** → FILE_REFERENCE_MAP.md
4. **Want to see actual code?** → View the referenced file paths

---

## ✅ Exploration Completeness

This exploration covers:
- ✅ MCP client implementation (nanobot)
- ✅ MCP server (deepseek-mcp-server)
- ✅ Tool registry (dual implementations)
- ✅ Evolution engine (complete)
- ✅ CLI structure
- ✅ Configuration system
- ✅ All 32 built-in tools
- ✅ File mappings and navigation

**Last Updated:** March 9, 2025
**Jagabot Version Analyzed:** 0.1.0

---

Generated by: Codebase Exploration Agent
Purpose: Understand jagabot infrastructure for MCP integration and tool management
