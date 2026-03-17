# JAGABOT SKILLS INTEGRATION ARCHITECTURE

## System Overview Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                   JAGABOT AGENT LOOP                            │
│  (loop.py: Receives messages → builds context → calls LLM)     │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
         ┌─────────────────────────────┐
         │   CONTEXT BUILDER           │
         │  (context.py)               │
         └──────────────┬──────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
   Bootstrap      Memory Context   SKILLS LOADER
   Files          (MEMORY.md)       (skills.py)
  (AGENTS.md,                       │
   SOUL.md,                         ├─ Workspace Skills (priority 1)
   etc.)                            │  ~/.jagabot/workspace/skills/
                                    │  • financial_analysis.md
                                    │
                                    └─ Builtin Skills (priority 2)
                                       /root/nanojaga/jagabot/skills/
                                       • financial/
                                       • skill-creator/
                                       • github/
                                       • memory/
                                       • weather/
                                       • cron/
                                       • tmux/
                                       • summarize/

┌─────────────────────────────────────────────────────────────────┐
│                  SYSTEM PROMPT ASSEMBLY                          │
├─────────────────────────────────────────────────────────────────┤
│ 1. Identity (jagabot core info)                                 │
│ 2. Bootstrap files (AGENTS, SOUL, etc.)                         │
│ 3. Memory context                                               │
│ 4. ACTIVE SKILLS (always=true, full markdown content)           │
│    └─ Example: financial/ skill (32 tools, 15-step protocol)   │
│ 5. SKILLS SUMMARY (XML index of ALL available skills)           │
│    └─ Agent can read full SKILL.md via read_file() tool        │
└─────────────────────────────────────────────────────────────────┘

                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              SKILL DISCOVERY & EXECUTION FLOW                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User Query → SkillTrigger.detect() → Best skill + confidence   │
│              (keyword + condition matching)                      │
│                                                                  │
│  OR                                                             │
│                                                                  │
│  Agent reads XML summary → Agent calls read_file() →           │
│  Agent loads SKILL.md → Agent executes tool calls based on skill│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│        FINANCIAL-SERVICES-PLUGINS INTEGRATION POINT             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  /root/nanojaga/financial-services-plugins/                     │
│  ├─ equity-research/ (9 skills)                                │
│  ├─ financial-analysis/ (9 skills)                             │
│  ├─ investment-banking/ (9 skills)                             │
│  ├─ private-equity/ (9 skills)                                 │
│  ├─ wealth-management/ (6 skills)                              │
│  └─ partner-built/                                              │
│     ├─ lseg/ (8 skills)                                        │
│     └─ spglobal/ (3 skills)                                    │
│                                                                  │
│  TOTAL: 53 SKILL.md files (structured, ready to integrate)     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

              ┌──────────────────┐
              │  EVOLUTION ENGINE  │
              │  (evolution/)      │
              │                    │
              │ Mutates 5 params:  │
              │ • risk_threshold   │
              │ • volatility_weight│
              │ • correlation_*    │
              │ • perspective_*    │
              │ • learning_rate    │
              │                    │
              │ Safety: 4-layer    │
              │ • Clamping ×0.9-1.1│
              │ • Sandbox 50 cycles│
              │ • Fitness validation│
              │ • Auto-rollback    │
              └──────────────────┘
```

---

## SKILL.md Format & Integration

### Example: Builtin Financial Skill

**File:** `/root/nanojaga/jagabot/skills/financial/SKILL.md`
```yaml
---
name: financial
description: Financial crisis analysis protocol — 13-step tool-calling workflow
metadata: {"jagabot":{"emoji":"📊","always":true}}
---

# Financial Analysis Protocol

You have 32 specialised financial analysis tools...

## Tool Calling Order (15-Step Protocol)

When a user asks about stocks, risk, crisis...
```

**Key properties:**
- `name` → Unique identifier
- `description` → One-liner shown in XML summary
- `metadata.always` → Include full content in system prompt (not just summary)
- `metadata.emoji` → Optional UI indicator
- Full markdown content → Tool-calling protocols, workflows, examples

---

### Example: Plugin Equity Research Skill

**File:** `/root/nanojaga/financial-services-plugins/equity-research/skills/initiating-coverage/SKILL.md`

```yaml
---
name: initiating-coverage
description: Create institutional-quality equity research initiation reports 
  through a 5-task workflow...
---

# Initiating Coverage

Create institutional-quality equity research reports...

## ⚠️ CRITICAL: One Task at a Time

If User Requests Full Pipeline...
```

**Key properties:**
- Structured workflow guidance (5 tasks, dependencies)
- Example outputs and expected formats
- Prerequisite verification rules
- Tool-calling patterns specific to financial analysis

---

## SkillsLoader: How It Works

### Discovery Algorithm (list_skills)
```
FOR each skill directory in workspace_skills/:
    IF SKILL.md exists:
        ADD to skills list with source="workspace"

FOR each skill directory in builtin_skills/:
    IF SKILL.md exists AND skill not in workspace:
        ADD to skills list with source="builtin"

IF filter_unavailable:
    FILTER OUT skills with unmet requires.bins or requires.env
```

### Progressive Loading Strategy

```
SYSTEM PROMPT contains:

1. Always-loaded skills (full markdown):
   ┌─────────────────────────────────┐
   │ # Active Skills                 │
   │                                 │
   │ ### Skill: financial            │
   │ [FULL SKILL.MD CONTENT]        │
   └─────────────────────────────────┘

2. Summary of all other skills (XML index):
   ┌─────────────────────────────────┐
   │ # Skills                        │
   │                                 │
   │ <skills>                        │
   │   <skill available="true">      │
   │     <name>cim-builder</name>   │
   │     <description>...</description>
   │     <location>/path/to/SKILL.md</location>
   │   </skill>                      │
   │   ...                           │
   │ </skills>                       │
   └─────────────────────────────────┘

AGENT can then:
  - Use built-in always-loaded skills directly
  - Call read_file("/path/to/SKILL.md") for other skills
  - Skill content loaded on-demand to save token space
```

---

## Integration Checklist for Financial Plugins

### Phase 1: Copy Skills to Workspace ✓

```bash
# Create workspace structure
mkdir -p ~/.jagabot/workspace/skills/

# Copy each plugin (OR select skills)
cp -r /root/nanojaga/financial-services-plugins/equity-research/skills/* \
  ~/.jagabot/workspace/skills/
cp -r /root/nanojaga/financial-services-plugins/investment-banking/skills/* \
  ~/.jagabot/workspace/skills/
# ... repeat for other plugins
```

### Phase 2: SkillsLoader Discovers Them ✓

No registration needed. SkillsLoader automatically:
- Scans `~/.jagabot/workspace/skills/`
- Finds all SKILL.md files
- Extracts metadata from frontmatter
- Tests requirement availability
- Includes in XML summary

### Phase 3: Optional - Register Triggers 

```python
# In jagabot/skills/trigger.py or at runtime:
trigger_tool.register_trigger(
    skill_name="cim-builder",
    keywords=["cim", "confidential information memo", "deal structure"],
    conditions={}
)
```

### Phase 4: Optional - Mark Always-Loaded

Add to SKILL.md frontmatter to include full content in system prompt:
```yaml
metadata: {"jagabot": {"always": true}}
```

### Phase 5: Restart Agent

```bash
# Agent loop will reload all skills on startup
python -m jagabot
```

---

## Skills Requirement System

### Frontmatter Example (with Requirements)

```yaml
---
name: dcf-model
description: Build DCF financial models
requires:
  bins: ["python", "openpyxl"]
  env: ["FINANCIAL_DATA_API_KEY"]
metadata: {"jagabot": {"emoji": "📊"}}
---
```

### Availability Logic

```python
# SkillsLoader._check_requirements(skill_meta)

available = True
FOR each required binary in requires.bins:
    IF not shutil.which(binary):
        available = False

FOR each required env var in requires.env:
    IF not os.environ.get(env_var):
        available = False

RETURN available

# In XML summary:
<skill available="false">
  <name>dcf-model</name>
  <description>...</description>
  <requires>ENV: FINANCIAL_DATA_API_KEY</requires>
</skill>
```

---

## Context Builder Integration Flow

```python
# In context.py:

def build_system_prompt(self, skill_names=None):
    parts = []
    
    # 1. Core identity
    parts.append(self._get_identity())
    
    # 2. Bootstrap files
    parts.append(self._load_bootstrap_files())
    
    # 3. Memory context
    parts.append(self.memory.get_memory_context())
    
    # 4. Always-loaded skills (full content)
    always_skills = self.skills.get_always_skills()  # ← Returns ["financial", ...]
    if always_skills:
        content = self.skills.load_skills_for_context(always_skills)
        parts.append(f"# Active Skills\n\n{content}")
    
    # 5. Skills summary (XML index)
    summary = self.skills.build_skills_summary()  # ← Returns XML
    if summary:
        parts.append(f"""# Skills
        
The following skills extend your capabilities. To use a skill, 
read its SKILL.md file using the read_file tool.

{summary}""")
    
    return "\n\n---\n\n".join(parts)
```

---

## Expected Token Usage

### System Prompt Composition

| Section | Tokens (est.) |
|---------|---------------|
| Identity (jagabot core) | 150 |
| Bootstrap files (AGENTS, SOUL, etc.) | 500 |
| Memory context | 100 |
| Active Skills (financial/ full content) | 3,000 |
| Skills Summary (XML index, 53 skills) | 2,000 |
| **TOTAL SYSTEM PROMPT** | **~5,750** |

### Message Exchange

| Component | Tokens |
|-----------|--------|
| User message | Variable |
| Tool calls (skill reading, execution) | Variable |
| Tool results (analysis output) | Variable |

**Strategy:** Always-loaded skill + XML summary keeps base prompt lean while enabling full feature access on-demand.

---

## What Happens When User Asks About Financial Topics

### Example: "Create an equity research initiation report for Tesla"

1. **Message arrives** → AgentLoop receives query
2. **Context built** → ContextBuilder includes:
   - System prompt with financial/ skill (32 tools)
   - XML index showing all 53 available skills
3. **Agent reads prompt** → Sees skills summary, identifies best skill:
   - SkillTrigger suggests: `initiating-coverage` (equity-research plugin)
4. **Agent loads skill** → Calls `read_file("/root/.../initiating-coverage/SKILL.md")`
5. **Skill execution** → Follows 5-task workflow from SKILL.md
6. **Tool calling** → Uses financial analysis tools from always-loaded skill
7. **Output** → Delivers institutional-quality report

---

## Security & Safety

### Requirement Filtering
- **Unavailable skills** marked as `available="false"` in XML
- **Reasons shown** (e.g., "ENV: API_KEY_MISSING")
- **Agent notified** in system prompt that dependencies needed

### Evolution Safety
- **Mutations clamped** to ×0.90–×1.10 range
- **Sandbox testing** before acceptance (50 cycles)
- **Fitness validation** required for commitment
- **Auto-rollback** on any rejection

### Skill Isolation
- **No execution permission** in SKILL.md (markdown only)
- **Tool calling** required for actual operations
- **Agent decides** which tools to call based on skill content
- **Tool registry** controls what operations are allowed

