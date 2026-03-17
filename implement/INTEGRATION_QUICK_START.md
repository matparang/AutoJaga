# Integration Quick Start: Financial Plugins → Jagabot

## TL;DR - What You Have

✅ **Plugin Source Ready**
- 53 SKILL.md files in `/root/nanojaga/financial-services-plugins/`
- 5 domain plugins: equity-research, financial-analysis, investment-banking, private-equity, wealth-management
- 2 partner plugins: LSEG (8 skills), S&P Global (3 skills)
- Each skill is a complete workflow guide with tool-calling protocols

✅ **SkillsLoader Active**
- Automatically discovers SKILL.md files from two locations:
  1. Workspace: `~/.jagabot/workspace/skills/` (priority)
  2. Builtin: `/root/nanojaga/jagabot/skills/` (fallback)
- Filters by requirement availability (CLI tools, env vars)
- Loads full content or provides XML summary for progressive loading

✅ **System Prompt Integration Active**
- ContextBuilder assembles system prompt with:
  1. Always-loaded skills (full markdown)
  2. XML index of all available skills
- Agent can read skill files on-demand via `read_file()` tool
- No manual registration needed

✅ **EvolutionEngine Ready**
- Self-tunes 5 financial parameters
- 4-layer safety: clamping, sandbox, validation, rollback
- Persists state in `~/.jagabot/workspace/evolution_state.json`

---

## Three Integration Strategies

### Strategy 1: Simple Copy (Recommended for testing)

**Step 1: Create workspace directory**
```bash
mkdir -p ~/.jagabot/workspace/skills
```

**Step 2: Copy plugins you want**
```bash
# Copy all equity research skills
cp -r /root/nanojaga/financial-services-plugins/equity-research/skills/* \
  ~/.jagabot/workspace/skills/

# Or copy specific skills
cp -r /root/nanojaga/financial-services-plugins/equity-research/skills/initiating-coverage \
  ~/.jagabot/workspace/skills/
```

**Step 3: Verify discovery**
```bash
python3 -c "
from pathlib import Path
from jagabot.agent.skills import SkillsLoader

loader = SkillsLoader(Path.home() / '.jagabot' / 'workspace')
skills = loader.list_skills(filter_unavailable=False)
for s in skills:
    print(f'{s[\"name\"]}: {s[\"source\"]}')
"
```

**Step 4: Restart agent**
- Agent automatically discovers new skills on startup
- Skills appear in system prompt XML summary

---

### Strategy 2: Symlink (Recommended for development)

**Step 1: Create workspace structure**
```bash
mkdir -p ~/.jagabot/workspace/skills
```

**Step 2: Symlink plugin directories**
```bash
# Symlink entire plugins
ln -s /root/nanojaga/financial-services-plugins/equity-research/skills/* \
  ~/.jagabot/workspace/skills/

# Or symlink specific plugins
ln -s /root/nanojaga/financial-services-plugins/investment-banking/skills/* \
  ~/.jagabot/workspace/skills/
```

**Advantages:**
- Changes to SKILL.md files immediately reflected
- No duplication of files
- Easy to switch between plugins

---

### Strategy 3: Custom Wrapper Skill (Advanced)

Create a meta-skill that coordinates multiple plugin skills:

**File:** `~/.jagabot/workspace/skills/financial-services-coordinator/SKILL.md`

```yaml
---
name: financial-services-coordinator
description: Route financial services requests to specialized plugins
metadata: {"jagabot": {"always": true}}
---

# Financial Services Coordinator

Route user requests to the best financial services skill based on domain.

## Domain Routing

### Equity Research
When user asks about: sector analysis, company research, earnings, theses
→ Use skills from equity-research plugin:
  • sector-overview
  • idea-generation
  • initiating-coverage
  • earnings-analysis
  • catalyst-calendar

### Investment Banking
When user asks about: M&A, deals, CIMs, pitches, buyer lists
→ Use skills from investment-banking plugin:
  • cim-builder
  • deal-tracker
  • merger-model
  • pitch-deck
  • teaser

[... repeat for other domains ...]

## Workflow

1. Identify user's domain (equity research, PE, wealth, etc.)
2. Call read_file() for the specific skill
3. Execute tool-calling workflow from that skill
```

---

## How Skills Are Used in System Prompt

### System Prompt Structure (After Integration)

```
# jagabot 🐈

You are jagabot, a helpful AI assistant...

[... identity, bootstrap, memory sections ...]

# Active Skills

### Skill: financial

You have 32 specialised financial analysis tools...

[FULL CONTENT OF financial/SKILL.md]

# Skills

The following skills extend your capabilities. To use a skill, 
read its SKILL.md file using the read_file tool.

<skills>
  <skill available="true">
    <name>initiating-coverage</name>
    <description>Create institutional-quality equity research initiation reports...</description>
    <location>/root/.../equity-research/skills/initiating-coverage/SKILL.md</location>
  </skill>
  <skill available="true">
    <name>cim-builder</name>
    <description>Draft CIMs, teasers, and process letters</description>
    <location>/root/.../investment-banking/skills/cim-builder/SKILL.md</location>
  </skill>
  [... 51 more skills ...]
</skills>
```

### When Agent Encounters Request

**Example 1: Builtin financial skill (always loaded)**
```
User: "Check if my portfolio has a margin call risk"

Agent: (Already has financial/ skill in context)
  • Calls financial_cv to analyze positions
  • Calls early_warning to detect danger signals
  • Responds with analysis
```

**Example 2: Plugin skill (progressive loading)**
```
User: "Create a coverage initiation report for Tesla"

Agent: (Reads system prompt XML summary)
  • Identifies initiating-coverage skill as best match
  • Calls: read_file("/root/.../initiating-coverage/SKILL.md")
  • Follows 5-task workflow from skill content
  • Executes financial tools for research/modeling/valuation
  • Delivers report
```

---

## Metadata Customization

### Make a Skill Always-Loaded

Edit SKILL.md frontmatter to include full content in system prompt:

```yaml
---
name: my-skill
description: Does something important
metadata: {"jagabot": {"always": true, "emoji": "��"}}
---
```

**Use case:** Skills your agent uses frequently (reduces latency, no file read needed)

### Specify Requirements

```yaml
---
name: dcf-model
description: Build DCF financial models
requires:
  bins: ["python", "openpyxl", "pandas"]
  env: ["FINANCIAL_API_KEY"]
---
```

**Behavior:**
- SkillsLoader checks for `python`, `openpyxl`, `pandas` in PATH
- Checks for `FINANCIAL_API_KEY` env var
- If any missing: `available="false"` in XML, shows what's missing

---

## Testing Integration

### 1. Verify Skills Are Discovered

```python
from pathlib import Path
from jagabot.agent.skills import SkillsLoader

workspace = Path.home() / ".jagabot" / "workspace"
loader = SkillsLoader(workspace)

# List all skills
skills = loader.list_skills(filter_unavailable=False)
print(f"Found {len(skills)} skills:")
for s in skills:
    print(f"  • {s['name']} ({s['source']})")

# Get always-loaded skills
always = loader.get_always_skills()
print(f"\nAlways-loaded: {always}")

# Get summary (what appears in system prompt)
summary = loader.build_skills_summary()
print(f"\nSystem prompt will include: {len(summary)} chars of XML summary")
```

### 2. Test System Prompt Building

```python
from pathlib import Path
from jagabot.agent.context import ContextBuilder

workspace = Path.home() / ".jagabot" / "workspace"
builder = ContextBuilder(workspace)

# Build complete system prompt
prompt = builder.build_system_prompt()
print(f"System prompt: {len(prompt)} chars")
print(f"Contains {prompt.count('<skill')} skills in summary")
```

### 3. Test Skill Loading

```python
from pathlib import Path
from jagabot.agent.skills import SkillsLoader

loader = SkillsLoader(Path.home() / ".jagabot" / "workspace")

# Load specific skill
content = loader.load_skill("initiating-coverage")
if content:
    print(f"Loaded initiating-coverage skill: {len(content)} chars")
    # Parse frontmatter
    meta = loader.get_skill_metadata("initiating-coverage")
    print(f"Metadata: {meta}")
else:
    print("Skill not found!")
```

---

## Troubleshooting

### Skills Not Appearing

**Problem:** Skills copied but not showing in XML summary

**Solution:**
1. Verify file path: `~/.jagabot/workspace/skills/{skill-name}/SKILL.md`
2. Check frontmatter: File must start with `---`
3. Test discovery: Run verification script above
4. Restart agent (clears caches)

### Skill Shows as Unavailable

**Problem:** Skill in summary but marked `available="false"`

**Solution:**
1. Check what's missing: Look at `<requires>` field in XML
2. Install dependencies: Run `apt-get install` or `pip install`
3. Or set environment variables: `export REQUIRED_VAR=value`
4. Restart agent

### Frontmatter Parsing Failed

**Problem:** Skill loads but metadata is empty

**Solution:**
1. Check YAML syntax: Frontmatter must be valid YAML
2. Verify delimiters: Must have `---` at start and end
3. Example valid frontmatter:
   ```yaml
   ---
   name: my-skill
   description: Does something
   ---
   ```

---

## Next Steps After Integration

### 1. Add Trigger Keywords (Optional)

Register custom triggers for automatic skill detection:

```python
# In a script or agent initialization:
from jagabot.skills.trigger import SkillTrigger

trigger = SkillTrigger()
trigger.register_trigger(
    skill_name="initiating-coverage",
    keywords=["initiate coverage", "write research", "equity research initiation"],
)
trigger.register_trigger(
    skill_name="cim-builder",
    keywords=["cim", "confidential information memo", "deal materials"],
)
```

### 2. Customize Skill Content

Edit SKILL.md files to add your firm's:
- Specific templates
- Data sources
- Workflow variations
- Output formats

### 3. Monitor Evolution Engine

Check adaptation over time:

```python
from pathlib import Path
from jagabot.evolution.engine import EvolutionEngine

engine = EvolutionEngine()
state = engine.load_state()
print(f"Mutations attempted: {len(state.mutations)}")
print(f"Accepted: {len([m for m in state.mutations if m.success])}")
```

### 4. Create Composite Skills

Wrap multiple skills in a single meta-skill for complex workflows:

```markdown
# Equity Research Pipeline

Complete workflow: company research → financial modeling → valuation → charts → report

## Step 1: Company Research
→ Read skill: sector-overview
→ Read skill: idea-generation
→ Gather business info, competitive landscape

## Step 2: Financial Modeling
→ Read skill: dcf-model
→ Build projection model with assumptions

## Step 3: Valuation & Charts
→ Read skill: initiating-coverage (Task 3-4)
→ Generate charts and valuation multiples
```

---

## File Reference

| Path | Purpose |
|------|---------|
| `/root/nanojaga/jagabot/agent/skills.py` | SkillsLoader class (discovery, loading, summary) |
| `/root/nanojaga/jagabot/agent/context.py` | ContextBuilder (system prompt assembly) |
| `/root/nanojaga/jagabot/skills/trigger.py` | SkillTrigger (automatic skill detection) |
| `/root/nanojaga/jagabot/evolution/` | EvolutionEngine (self-tuning) |
| `/root/nanojaga/financial-services-plugins/` | 53 plugin skills (ready to integrate) |
| `~/.jagabot/workspace/skills/` | Workspace skills (agent's custom skills) |

---

## One-Line Test

```bash
python3 -c "from pathlib import Path; from jagabot.agent.skills import SkillsLoader; l=SkillsLoader(Path.home()/.jagabot/workspace'); print(f'Found {len(l.list_skills())} skills')"
```

If you see "Found N skills" (N > 8), integration is working! ✅

