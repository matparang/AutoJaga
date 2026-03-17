---
name: writing_financial_skills
description: Meta-skill for creating new financial analysis skills with tests and integration
metadata: {"jagabot":{"emoji":"✍️","trigger":"skill_creation"}}
---

# Writing Financial Skills (Meta-Skill)

## TRIGGER
- User requests: "create new analysis type", "new skill", "new workflow", "custom analysis"
- Skill trigger detects: template, custom analysis, new capability

## PURPOSE
Systematically create new financial analysis skills that integrate with JAGABOT's existing toolkit. Every new skill follows the standard anatomy, includes test cases, and wires into the trigger/composition system.

## TEMPLATE

Every new financial skill MUST follow this structure:

```markdown
---
name: [skill_name]
description: [one-line description]
metadata: {"jagabot":{"emoji":"[emoji]","trigger":"[trigger_name]"}}
---

# [Skill Name]

## TRIGGER
[When should this skill activate?]

## PURPOSE
[1-paragraph description of what this skill does and why]

## WORKFLOW
### Step 1: [Name]
[Description + tools used]

### Step 2: [Name]
[Description + tools used]

### Step N: REVIEW
- `review` → Two-stage quality gate

### Step N+1: SAVE
- `memory_fleet` → Store results
- `knowledge_graph` → Link to graph

## TOOLS USED
- [list of tools this skill calls]

## COMPOSABLE
- Called by: [which skills call this one]
- Calls: [which skills this one calls]

## TEST CASES
- Case 1: [input] → [expected output]
- Case 2: [input] → [expected output]
```

## CREATION WORKFLOW

### Step 1: UNDERSTAND
Ask the user:
1. "What financial analysis do you need?"
2. "What inputs will you provide?"
3. "What output format do you expect?"
4. "How often will you use this?"

### Step 2: DESIGN
1. Map user needs to existing JAGABOT tools
2. Define the workflow step sequence
3. Identify which existing skills to compose with
4. Define trigger keywords for auto-detection

### Step 3: WRITE
1. Generate the SKILL.md following the template above
2. Register trigger keywords via `skill_trigger` tool
3. Register workflow steps via SkillComposer if composable

### Step 4: VALIDATE
1. Walk through each workflow step mentally
2. Verify all referenced tools exist
3. Check trigger keywords don't conflict with existing skills
4. `review` → Run spec compliance check

### Step 5: REGISTER
1. Save SKILL.md to `jagabot/skills/financial/`
2. Add trigger to SkillTrigger via register action
3. Add workflow to SkillComposer if multi-step
4. Update KnowledgeGraph with new skill node

## INTEGRATION CHECKLIST
- [ ] SKILL.md has valid frontmatter (name, description, metadata)
- [ ] TRIGGER section lists specific keywords
- [ ] WORKFLOW uses only existing JAGABOT tools
- [ ] REVIEW step included (two-stage gate)
- [ ] SAVE step included (MemoryFleet + KnowledgeGraph)
- [ ] TEST CASES defined (at least 2)
- [ ] COMPOSABLE section documents dependencies
- [ ] Trigger keywords registered in SkillTrigger
