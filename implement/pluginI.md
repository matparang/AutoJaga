📋 SCOPE PROMPT: Integrate Anthropic Financial Plugins into JAGABOT

```markdown
# SCOPE: Integrate Anthropic Financial Services Plugins into JAGABOT Skill Library

## CURRENT STATE
✅ JAGABOT v3.7.2 complete (1300+ tests)
✅ Skill system exists at `~/.jagabot/workspace/skills/`
✅ EvolutionEngine can create/update skills
✅ Anthropic plugins downloaded to `~/nanojaga/financial-services-plugins/`

## ANTHROPIC PLUGINS AVAILABLE
```

financial-services-plugins/
├── financial-analysis/           # Core plugin with 41 skills, 38 commands
│   ├── skills/                   # Domain expertise files
│   ├── commands/                  # Slash commands
│   └── .mcp.json                  # Data connectors
├── equity-research/               # Add-on for research
├── investment-banking/            # Add-on for IB workflows
├── private-equity/                # Add-on for PE analysis
├── wealth-management/             # Add-on for wealth clients
└── partner-built/                 # LSEG, S&P Global integrations

```

## OBJECTIVE
Integrate all Anthropic financial plugins into JAGABOT's skill system:

1. **COPY** all skill files to `~/.jagabot/workspace/skills/`
2. **CONVERT** Anthropic format to JAGABOT SKILL.md format
3. **REGISTER** new skills with SkillRegistry
4. **UPDATE** trigger keywords for auto-activation
5. **MAKE JAGABOT AWARE** of new capabilities

## INTEGRATION TASKS

### TASK 1: Copy & Convert Skills (41 files)
```bash
# Source: ~/nanojaga/financial-services-plugins/*/skills/*.md
# Target: ~/.jagabot/workspace/skills/

# For each skill file, need to:
1. Copy content
2. Add JAGABOT header with trigger keywords
3. Map to appropriate tools
4. Save as SKILL_[name].md
```

TASK 2: Skill Conversion Template

```markdown
# SKILL: [Name from Anthropic]

## TRIGGER KEYWORDS
[Extract from content + add finance terms]

## PURPOSE
[Original description]

## WORKFLOW
[Convert Anthropic steps to JAGABOT workflow]

## TOOLS REQUIRED
[List JAGABOT tools that map to this skill]

## INTEGRATION WITH JAGABOT
- Uses: [tool1, tool2, ...]
- Calls subagents: [yes/no]
- Requires sandbox: [yes/no]

## EXAMPLE QUERY
[Sample user query that triggers this skill]

## VERSION
v1.0 - Imported from Anthropic Financial Plugins
```

TASK 3: Register New Skills

```python
# Update jagabot/skills/__init__.py
# Auto-discover all SKILL_*.md files
# Add to SkillRegistry
# Update trigger keyword database
```

TASK 4: Update System Prompt

```markdown
# Add to JAGABOT system prompt:
"New skills available from Anthropic Financial Plugins:
- comparable_analysis (equity research)
- dcf_modeling (valuation)
- earnings_update (post-earnings)
- ic_memo (investment committee)
- client_review (wealth management)
- ... (41 total)"
```

TASK 5: Test Integration

```python
# Test queries for each major plugin:
test_queries = [
    "Run comparable analysis for TSLA",
    "Build DCF model for AAPL",
    "Draft earnings update for MSFT",
    "Create IC memo for acquisition target",
    "Generate client review for retirement portfolio"
]

# Verify:
1. Correct skill triggered
2. Tools called appropriately
3. Output format correct
4. Response within limits
```

NEW FILES TO CREATE

1. scripts/import_anthropic_skills.py - Automation script
2. tests/test_anthropic_skills.py - 20+ new tests
3. docs/anthropic_integration.md - Documentation

FILES TO MODIFY

1. jagabot/skills/__init__.py - Auto-register new skills
2. jagabot/core/prompts/system_prompt.md - Announce new skills
3. jagabot/skills/trigger_keywords.json - Update database
4. CHANGELOG.md - v3.8 entry

SUCCESS CRITERIA

✅ All 41 Anthropic skills copied to ~/.jagabot/workspace/skills/
✅ Each skill converted to JAGABOT SKILL.md format
✅ Skills auto-registered and discoverable
✅ Trigger keywords updated for each skill
✅ Test queries execute correct skills
✅ 20+ new tests passing
✅ JAGABOT aware of new capabilities
✅ No regression in existing 1300+ tests
✅ Target: 1320+ tests

TIMELINE

Task Hours
Create import script 3
Convert 41 skills 8
Update registry 2
Update system prompt 1
Write tests (20+) 4
Documentation 1
TOTAL 19 hours

```

---

**This integration will give JAGABOT 41 professional financial skills from Anthropic!** 🚀
