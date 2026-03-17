# Anthropic Financial Plugins Integration: Jagabot Infrastructure Report

## 1. PLUGINS SOURCE EXISTS ✅

### Location
`/root/nanojaga/financial-services-plugins/`

### Full Directory Tree (69 directories, 52 files)

```
financial-services-plugins/
├── README.md                          (Main plugin documentation)
├── LICENSE
├── CLAUDE.md                          (Claude configuration)
├── equity-research/
│   ├── README.md
│   ├── commands/                      (9 markdown command specs)
│   │   ├── catalysts.md
│   │   ├── earnings.md
│   │   ├── earnings-preview.md
│   │   ├── initiate.md
│   │   ├── model-update.md
│   │   ├── morning-note.md
│   │   ├── screen.md
│   │   ├── sector.md
│   │   └── thesis.md
│   ├── hooks/
│   │   └── hooks.json
│   └── skills/                        (9 SKILL.md files)
│       ├── catalyst-calendar/
│       ├── earnings-analysis/
│       ├── earnings-preview/
│       ├── idea-generation/
│       ├── initiating-coverage/
│       ├── model-update/
│       ├── morning-note/
│       ├── sector-overview/
│       └── thesis-tracker/
├── financial-analysis/
│   ├── commands/                      (8 command specs)
│   │   ├── 3-statements.md
│   │   ├── check-deck.md
│   │   ├── competitive-analysis.md
│   │   ├── comps.md
│   │   ├── dcf.md
│   │   ├── debug-model.md
│   │   ├── lbo.md
│   │   └── ppt-template.md
│   ├── hooks/
│   │   └── hooks.json
│   └── skills/                        (9 SKILL.md files)
│       ├── 3-statements/
│       ├── check-deck/
│       ├── check-model/
│       ├── competitive-analysis/
│       ├── comps-analysis/
│       ├── dcf-model/
│       ├── lbo-model/
│       ├── ppt-template-creator/
│       └── skill-creator/
├── investment-banking/
│   ├── README.md
│   ├── commands/                      (7 command specs)
│   ├── hooks/
│   │   └── hooks.json
│   └── skills/                        (9 SKILL.md files)
│       ├── buyer-list/
│       ├── cim-builder/
│       ├── datapack-builder/
│       ├── deal-tracker/
│       ├── merger-model/
│       ├── pitch-deck/
│       ├── process-letter/
│       ├── strip-profile/
│       └── teaser/
├── private-equity/
│   ├── commands/                      (9 command specs)
│   ├── hooks/
│   │   └── hooks.json
│   └── skills/                        (9 SKILL.md files)
│       ├── dd-checklist/
│       ├── dd-meeting-prep/
│       ├── deal-screening/
│       ├── deal-sourcing/
│       ├── ic-memo/
│       ├── portfolio-monitoring/
│       ├── returns-analysis/
│       ├── unit-economics/
│       └── value-creation-plan/
├── wealth-management/
│   ├── commands/                      (6 command specs)
│   ├── hooks/
│   │   └── hooks.json
│   └── skills/                        (6 SKILL.md files)
│       ├── client-report/
│       ├── client-review/
│       ├── financial-plan/
│       ├── investment-proposal/
│       ├── portfolio-rebalance/
│       └── tax-loss-harvesting/
├── partner-built/
│   ├── lseg/
│   │   ├── README.md
│   │   ├── CONNECTORS.md
│   │   ├── commands/
│   │   └── skills/                    (8 SKILL.md files)
│   │       ├── bond-futures-basis/
│   │       ├── bond-relative-value/
│   │       ├── equity-research/
│   │       ├── fixed-income-portfolio/
│   │       ├── fx-carry-trade/
│   │       ├── macro-rates-monitor/
│   │       ├── option-vol-analysis/
│   │       └── swap-curve-strategy/
│   └── spglobal/
│       ├── README.md
│       ├── LICENSE
│       └── skills/                    (3 SKILL.md files)
│           ├── earnings-preview-beta/
│           ├── funding-digest/
│           └── tear-sheet/
```

**Total: 53 SKILL.md files across 5 major plugins + 2 partner plugins**

---

## 2. JAGABOT SKILLS SYSTEM

### File: `/root/nanojaga/jagabot/agent/skills.py` — Complete SkillsLoader Class

**Key Classes:**
- `SkillsLoader` — loads and manages SKILL.md files

**Default Builtin Skills Directory:** 
- Relative path: `jagabot/skills/`
- Absolute: `/root/nanojaga/jagabot/skills/`

**Core Methods:**

| Method | Purpose | Returns |
|--------|---------|---------|
| `list_skills(filter_unavailable=True)` | List available skills | `list[dict]` with `name`, `path`, `source` |
| `load_skill(name)` | Load a skill by name | `str` (SKILL.md content) or `None` |
| `load_skills_for_context(skill_names)` | Load multiple skills for agent context | `str` (formatted markdown) |
| `build_skills_summary()` | Build XML summary of all skills (name, desc, location, availability) | XML-formatted `str` |
| `get_always_skills()` | Get skills marked `always=true` that meet requirements | `list[str]` (skill names) |
| `get_skill_metadata(name)` | Extract metadata from SKILL.md frontmatter | `dict` or `None` |

**Skill Location Priority (hierarchical):**
1. **Workspace skills** (highest): `~/.jagabot/workspace/skills/{skill-name}/SKILL.md`
2. **Built-in skills** (fallback): `/root/nanojaga/jagabot/skills/{skill-name}/SKILL.md`

**Requirement Checking:**
- Checks YAML frontmatter `requires` field for:
  - `bins` — CLI tools (checked with `shutil.which()`)
  - `env` — environment variables

---

### File: `/root/nanojaga/jagabot/skills/` — Builtin Skills

**Existing Built-in Skills (8 skills):**
1. `financial/` — Financial crisis analysis protocol (📊 emoji, `always=true`)
2. `skill-creator/` — Dynamic skill creation workflow
3. `summarize/` — Content summarization
4. `tmux/` — Terminal multiplexer management
5. `memory/` — Long-term memory management
6. `github/` — GitHub integration
7. `weather/` — Weather data
8. `cron/` — Scheduled tasks

**Key Skill File Structure:**
```
skill-name/
├── SKILL.md                # Main skill definition with frontmatter
├── trigger.py              # Optional: Python trigger rules
└── assets/                 # Optional: templates, data files
```

**SKILL.md Frontmatter Format (YAML):**
```yaml
---
name: financial
description: Financial crisis analysis protocol — 13-step tool-calling workflow
metadata: {"jagabot":{"emoji":"📊","always":true}}
---
```

**Metadata Fields:**
- `name` — Skill identifier
- `description` — Human-readable description
- `metadata` — JSON object with:
  - `always` — boolean (include always in system prompt)
  - `emoji` — optional display emoji
  - `requires.bins[]` — required CLI tools
  - `requires.env[]` — required environment variables

---

### Files: Trigger System

**File 1:** `/root/nanojaga/jagabot/skills/trigger.py`
**File 2:** `/root/nanojaga/jagabot/agent/tools/skill_trigger.py`

**SkillTrigger Class:**
- Detects best skill for a query + market conditions
- Uses keyword matching + condition boosts
- Returns: `{skill, score, confidence, triggers_matched, condition_boosts}`

**Default Financial Triggers:**
- `crisis_management` — keywords: vix, margin call, crash, liquidation
- `investment_thesis` — keywords: new idea, research, opportunity, buy
- `portfolio_review` — keywords: portfolio, holdings, allocation
- `fund_manager_review` — keywords: fund manager, advisor, recommendation
- `risk_validation` — keywords: validate, backtest, stress test
- `rebalancing` — keywords: rebalance, trim, rotate, overweight
- `skill_creation` — keywords: create new analysis, custom skill

---

## 3. EXISTING SKILLS IN JAGABOT

### Builtin Skills (in `/root/nanojaga/jagabot/skills/`)
```
8 builtin SKILL.md files:
  • financial/SKILL.md — 32 financial tools, 15-step protocol (always loaded)
  • skill-creator/SKILL.md
  • summarize/SKILL.md
  • tmux/SKILL.md
  • memory/SKILL.md
  • github/SKILL.md
  • weather/SKILL.md
  • cron/SKILL.md
```

### Workspace Skills (in `~/.jagabot/workspace/skills/`)
```
1 custom skill:
  • financial_analysis.md (8.4 KB)
```

### Financial Services Plugin Skills (53 SKILL.md files)
**Equity Research (9 skills)**
- sector-overview, idea-generation, model-update, thesis-tracker, morning-note,
- initiating-coverage, earnings-preview, catalyst-calendar, earnings-analysis

**Financial Analysis (9 skills)**
- 3-statements, check-deck, check-model, competitive-analysis, comps-analysis,
- dcf-model, lbo-model, ppt-template-creator, skill-creator

**Investment Banking (9 skills)**
- buyer-list, cim-builder, datapack-builder, deal-tracker, merger-model,
- pitch-deck, process-letter, strip-profile, teaser

**Private Equity (9 skills)**
- dd-checklist, dd-meeting-prep, deal-screening, deal-sourcing, ic-memo,
- portfolio-monitoring, returns-analysis, unit-economics, value-creation-plan

**Wealth Management (6 skills)**
- client-report, client-review, financial-plan, investment-proposal,
- portfolio-rebalance, tax-loss-harvesting

**Partner-Built Skills (11 skills)**
- LSEG (8): equity-research, bond-futures-basis, bond-relative-value, etc.
- S&P Global (3): earnings-preview-beta, funding-digest, tear-sheet

---

## 4. CONTEXTBUILDER SKILLS INTEGRATION

### File: `/root/nanojaga/jagabot/agent/context.py` — ContextBuilder Class

**Skills Integration Methods:**

#### `get_always_skills() → list[str]`
- **Purpose:** Return skills marked as `always=true` that meet requirements
- **Logic:**
  1. Iterate through all available skills (with filter for unavailable)
  2. Check skill metadata for `always` flag in frontmatter
  3. Return list of skill names that qualify
- **Used in:** `build_system_prompt()` for full content inclusion

**Code Snippet:**
```python
def get_always_skills(self) -> list[str]:
    result = []
    for s in self.list_skills(filter_unavailable=True):
        meta = self.get_skill_metadata(s["name"]) or {}
        skill_meta = self._parse_jagabot_metadata(meta.get("metadata", ""))
        if skill_meta.get("always") or meta.get("always"):
            result.append(s["name"])
    return result
```

#### `build_skills_summary() → str` (XML Format)
- **Purpose:** Create summary of ALL skills (name, desc, location, availability)
- **Output Format:** XML with structure:
```xml
<skills>
  <skill available="true|false">
    <name>skill-name</name>
    <description>One-line description</description>
    <location>/path/to/SKILL.md</location>
    <requires>CLI: missing_tool, ENV: missing_var</requires>  <!-- if unavailable -->
  </skill>
  ...
</skills>
```
- **Availability:** Checked by verifying `requires.bins` and `requires.env`
- **Used in:** System prompt to show agent available skills

**Code Snippet:**
```python
def build_skills_summary(self) -> str:
    all_skills = self.list_skills(filter_unavailable=False)
    # ... XML construction with availability checks ...
    return "\n".join(lines)
```

#### System Prompt Structure (in `build_system_prompt()`)
```
1. Identity section (jagabot core identity)
2. Bootstrap files (AGENTS.md, SOUL.md, USER.md, TOOLS.md, IDENTITY.md)
3. Memory context
4. Active Skills (full content of always=true skills)
5. Skills Summary (XML of all available skills)
```

**Skills are included in two ways:**
1. **Full content** (always-loaded): Appended directly to system prompt
2. **Progressive loading** (summary): Agent reads full SKILL.md via `read_file` tool when needed

---

## 5. EVOLUTIONENGINE

### File: `/root/nanojaga/jagabot/evolution/engine.py` — EvolutionEngine

**Purpose:** Safe self-evolution of financial analysis parameters through mutation testing

**4-Layer Safety Protocol:**
1. **Factor Clamping** — mutations only ×0.90–×1.10
2. **Sandbox Testing** — 50 evaluation cycles before decision
3. **Fitness Validation** — accept only if fitness improves
4. **Auto-Rollback** — revert parameter immediately on rejection

**Key Classes:**

| Class | Purpose |
|-------|---------|
| `Mutation` | One parameter mutation record |
| `MutationResult` | Result of sandbox testing and acceptance |
| `EvolutionEngine` | Main orchestrator |

**Safety Constants:**
- `MIN_MUTATION_FACTOR = 0.90`
- `MAX_MUTATION_FACTOR = 1.10`
- `SANDBOX_CYCLES = 50`
- `MIN_CYCLES_BETWEEN = 100` (governor: wait 100 cycles before next mutation)

**Tunable Parameters (from `/root/nanojaga/jagabot/evolution/targets.py`):**

| Target | Default Value | Description |
|--------|---------------|-------------|
| `RISK_THRESHOLD` | 0.95 | VaR confidence level (0.90–0.99) |
| `VOLATILITY_WEIGHT` | 0.30 | CV pattern classification weight |
| `CORRELATION_THRESHOLD` | 0.60 | Minimum correlation to trigger alerts |
| `PERSPECTIVE_WEIGHT` | 0.35 | K3 bear/buffet weight balance |
| `LEARNING_RATE` | 0.40 | MetaLearning problem-detection threshold |

**State Persistence:**
- Location: `~/.jagabot/workspace/evolution_state.json`
- Tracks all mutations, fitness history, and acceptance/rejection records

---

## INTEGRATION POINTS: SKILLS ↔ FINANCIAL-SERVICES-PLUGINS

### How to Connect Plugins to Jagabot

**Step 1: Copy Skills to Workspace or Builtin**

Option A (Recommended — Workspace):
```bash
mkdir -p ~/.jagabot/workspace/skills/{plugin-name}
cp /root/nanojaga/financial-services-plugins/{plugin}/* \
   ~/.jagabot/workspace/skills/{plugin-name}/
```

Option B (Global Builtin):
```bash
cp -r /root/nanojaga/financial-services-plugins/{plugin}/skills/* \
   /root/nanojaga/jagabot/skills/
```

**Step 2: SkillsLoader Discovery**
- Automatically scans both workspace and builtin locations
- Discovers any SKILL.md file (no registration needed)
- Filters by requirement availability

**Step 3: Trigger Registration**
Add to SkillTrigger triggers (in skills/trigger.py):
```python
TriggerRule(
    skill="cim-builder",
    keywords=["cim", "confidential information memo", "deal materials"],
)
```

**Step 4: System Prompt Integration**
- Set `always: true` in frontmatter for always-loaded skills:
  ```yaml
  metadata: {"jagabot": {"always": true}}
  ```
- Or let agent discover via XML summary and load via `read_file` tool

### Skills XML Summary Format

Agent sees in system prompt:
```xml
<skill available="true">
  <name>cim-builder</name>
  <description>Draft CIMs, teasers, and process letters...</description>
  <location>/root/nanojaga/financial-services-plugins/investment-banking/skills/cim-builder/SKILL.md</location>
</skill>
```

Agent can then call:
```
read_file(path="/root/nanojaga/financial-services-plugins/investment-banking/skills/cim-builder/SKILL.md")
```

---

## SUMMARY: INFRASTRUCTURE READY FOR INTEGRATION ✅

| Component | Status | Details |
|-----------|--------|---------|
| **Plugin Source** | ✅ EXISTS | 53 skills across 5 plugins + 2 partners |
| **SkillsLoader** | ✅ ACTIVE | Loads from workspace & builtin, filters requirements |
| **System Prompt** | ✅ ACTIVE | Includes always-skills + XML summary of all skills |
| **Progressive Loading** | ✅ ACTIVE | Agent can read SKILL.md files on demand |
| **Trigger System** | ✅ ACTIVE | Auto-detects best skill for financial queries |
| **EvolutionEngine** | ✅ ACTIVE | Safe mutation of 5 financial parameters |
| **Workspace Skills** | ✅ ACTIVE | ~/.jagabot/workspace/skills/ monitored |

**Next Steps for Integration:**
1. Copy financial-services-plugins skills to appropriate location
2. Add trigger keywords for new skills (optional — SkillTrigger.register_trigger())
3. Set `always: true` for frequently-used skills (optional)
4. Restart agent loop to load new skills
