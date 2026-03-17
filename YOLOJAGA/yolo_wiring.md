# YOLO Mode — Wiring Guide

## File location
jagabot/agent/yolo.py   ← paste yolo_mode.py here

---

## Step 1 — Add CLI command to commands.py

```python
@app.command()
def yolo(
    goal: str = typer.Argument(
        ..., 
        help="Research goal e.g. 'research quantum computing in drug discovery'"
    ),
):
    """
    YOLO mode — fully autonomous research.
    AutoJaga runs all steps without asking for confirmation.
    Sandboxed to ~/.jagabot/workspace/ only.
    """
    from jagabot.agent.yolo import run_yolo
    from pathlib import Path
    run_yolo(
        goal      = goal,
        workspace = Path.home() / ".jagabot" / "workspace",
        agent     = None,  # wire to real AgentLoop
    )
```

Users run:
    jagabot yolo "research quantum computing in drug discovery"
    jagabot yolo "generate 5 unconventional ideas for hospital readmission"
    jagabot yolo "verify my pending outcomes and update memory"

---

## Step 2 — Wire real agent into _execute_step()

Replace the stub in YOLORunner._execute_step():

```python
async def _execute_step(self, prompt, step_name, step_num):
    # Run agent fully autonomously
    response = await self.agent.process_message(
        content    = prompt,
        yolo_mode  = True,   # skip all confirmations
        max_tools  = 10,     # cap tool calls per step
    )
    
    # Parse ProactiveWrapper output for structured data
    return {
        "summary":       self._extract_summary(response),
        "findings":      self._count_findings(response),
        "saved_to":      self._extract_saved_path(response),
        "memory_added":  self._count_memory_additions(response),
        "pending_added": self._count_pending_additions(response),
        "details":       response,
    }
```

---

## Step 3 — Add yolo_mode flag to AgentLoop

In loop.py, add yolo_mode parameter:

```python
async def process_message(
    self,
    content:   str,
    yolo_mode: bool = False,
    max_tools: int  = 20,
):
    if yolo_mode:
        # Skip all confirmation prompts
        # Skip human-in-the-loop checks
        # Execute tool calls immediately
        # But enforce workspace sandbox
        self._enforce_workspace_sandbox = True
        self._max_tool_calls = max_tools
```

---

## Step 4 — Add sandbox check to ToolHarness

In tool_harness.py register():

```python
def register(self, tool_id, tool_name, args, ...):
    if self._workspace_only:
        # Check any file paths in args
        for key, val in args.items():
            if isinstance(val, str) and "/" in val:
                check_sandbox(val)  # raises SandboxViolation if outside
    ...
```

---

## What the user sees

```
$ jagabot yolo "research LLM applications in clinical settings"

┌──────────────────────────────────────────────────────┐
│ 🐈 YOLO MODE — Autonomous Research                  │
│ Goal: research LLM applications in clinical settings │
│ Sandboxed to: ~/.jagabot/workspace/                  │
└──────────────────────────────────────────────────────┘

Step 1/6    Decompose goal into research questions...  ✅ 5 questions identified  0.8s
Step 2/6    Search for current information...          ✅ 14 sources saved        12.3s
Step 3/6    Synthesise and cross-check findings...     ✅ 9 claims verified       4.1s
Step 4/6    Extract key conclusions...                 ✅ 4 conclusions (3 pending) 2.2s
Step 5/6    Generate insights and implications...      ✅ 2 actionable insights   1.8s
Step 6/6    Save to memory and produce report...       ✅ Memory updated          0.9s

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 Report:   research_output/20260315_142233_llm_clinical/report.md
🧠 Memory:   4 facts added to MEMORY.md
📌 Pending:  3 conclusions logged for verification
⏱ Time:     22s

┌─────────┬─────────────────────────────────┬────────────────────────────────┐
│ ✅ 1/6  │ Decompose goal                  │ 5 questions identified         │
│ ✅ 2/6  │ Search for current information  │ 14 sources saved               │
│ ✅ 3/6  │ Synthesise and cross-check      │ 9 claims verified              │
│ ✅ 4/6  │ Extract key conclusions         │ 4 conclusions (3 pending)      │
│ ✅ 5/6  │ Generate insights               │ 2 actionable insights          │
│ ✅ 6/6  │ Save to memory and report       │ Memory updated                 │
└─────────┴─────────────────────────────────┴────────────────────────────────┘

→ Run jagabot chat then /pending to verify conclusions 
  and close the learning loop.
```

---

## Safety guarantees

1. Sandboxed — cannot touch files outside ~/.jagabot/workspace/
2. Audited — every action logged to yolo_audit.log
3. Capped — max 10 tool calls per step (prevents runaway)
4. Reversible — all changes are to workspace files, not system
5. Transparent — full details in research_output/ folder

---

## Three YOLO modes (extend later)

```
jagabot yolo "..."              # research mode (default)
jagabot yolo --mode idea "..."  # idea generation mode
jagabot yolo --mode memory      # verify pending outcomes
```

