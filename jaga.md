✅ GOT IT. nanobot → jagabot + 8 tools.

📋 The FINAL SCOPE Prompt

```
# SCOPE: Convert nanobot to jagabot with 8 financial tools

## CONTEXT
I have a fresh nanobot installation. I want to:
1. Rename it from "nanobot" to "jagabot"
2. Add 8 financial tools

## TASK PART 1: RENAME EVERYTHING
Change ALL occurrences of "nanobot" to "jagabot":

- Package name in pyproject.toml/setup.py
- Import statements: `nanobot.xxx` → `jagabot.xxx`
- CLI command: `nanobot` → `jagabot`
- Config directory: `~/.nanobot/` → `~/.jagabot/`
- All internal variable/class names
- Documentation strings
- File/folder names (nanobot/ → jagabot/)

## TASK PART 2: ADD 8 FINANCIAL TOOLS
Add these tool files to `jagabot/agent/tools/`:

1. `financial_cv.py` - CV calculation, ratios, pattern classification
2. `monte_carlo.py` - GBM simulation, probability forecasts  
3. `statistical.py` - t-tests, confidence intervals
4. `early_warning.py` - instability detection, RED/YELLOW/GREEN
5. `bayesian.py` - prior/posterior updates
6. `counterfactual.py` - what-if scenarios
7. `sensitivity.py` - parameter importance analysis
8. `pareto.py` - multi-strategy optimization

## REQUIREMENTS
- Each tool must follow nanobot's existing tool pattern
- Register them in the tool registry
- Make them available to `jagabot agent`
- Keep ALL existing functionality working

## OUTPUT
Provide the complete jagabot codebase with:
- All files renamed (nanobot → jagabot)
- 8 new tool files
- Updated tool registry
- Working `jagabot agent` command

## CONSTRAINTS
- DO NOT change nanobot's architecture
- DO NOT add features beyond rename + tools
- Just rename + add tools
```

---

That's it. Rename + 8 tools. Nothing else.
