# Enhanced CLI — Wiring Guide

## File location
jagabot/cli/interactive.py   ← paste jagabot_cli.py here

## Step 1 — Add CLI command to commands.py

```python
@app.command()
def chat(
    stream: bool = typer.Option(True, help="Stream output word by word"),
    model:  str  = typer.Option("Qwen-Plus", help="LLM model name"),
):
    """Launch enhanced interactive CLI (Claude Code style)."""
    from jagabot.cli.interactive import run_interactive
    from pathlib import Path
    run_interactive(
        workspace  = Path.home() / ".jagabot",
        model_name = model,
        stream     = stream,
    )
```

Now users can run:
    jagabot chat          # enhanced CLI
    jagabot chat --no-stream  # no streaming (faster on slow terminals)

## Step 2 — Wire real agent into _call_agent()

Replace the stub in EnhancedCLI._call_agent():

```python
async def _call_agent(self, query: str) -> str:
    # Wire ToolHarness callbacks for live display
    def on_tool_start(tool_name: str):
        print_tool_start(tool_name)
    
    def on_tool_done(tool_name: str, elapsed: float, status: str):
        print_tool_done(tool_name, elapsed, status)
    
    self.agent.harness.set_callbacks(
        on_start=on_tool_start,
        on_done=on_tool_done,
    )
    
    # Process message through real agent
    response = await self.agent.process_message(query)
    self._last_tools_used = self.agent.harness.last_tools_used
    return response
```

## Step 3 — Add callbacks to ToolHarness

In jagabot/core/tool_harness.py, add:

```python
def set_callbacks(self, on_start=None, on_done=None):
    self._on_start_cb = on_start
    self._on_done_cb  = on_done

def register(self, tool_id: str, ...):
    ...
    if self._on_start_cb:
        self._on_start_cb(tool_name)  # fires immediately

def complete(self, tool_id: str, ...):
    ...
    if self._on_done_cb:
        self._on_done_cb(tool_name, elapsed, "ok")
```

## What it looks like after wiring

```
› /research quantum computing in drug discovery

  ⚙ web_search...
  ✅ web_search (1.2s)
  ⚙ researcher...
  ✅ researcher (0.8s)
  ⚙ memory_fleet...
  ✅ memory_fleet (0.1s)

13:42 🐈 jagabot:

Quantum simulation of molecular interactions is
production-ready for small molecules as of 2025...

[streams word by word]

**What this means:** IBM and Google have demonstrated
protein folding applications in production settings.
The "hype" is mostly around fault-tolerant quantum
computers — still 5-10 years away.

**Next:** Want me to research specific drug targets
where quantum simulation shows the most promise?
```

## Slash command experience

```
› /help

Slash Commands

  /research    Deep research on any topic
               e.g. /research quantum computing in healthcare

  /idea        Generate ideas with tri-agent isolation
               e.g. /idea ways to reduce hospital readmission

  /memory      Show memory and verification status
  /pending     Show pending research outcomes
  /sessions    List past research sessions
  /status      Show agent and kernel health
  /verify      Verify a past conclusion
  /clear       Clear current session context
  /help        Show all slash commands
```

## ProactiveWrapper integration (already wired)

The CLI calls ProactiveWrapper automatically after every response:

```python
response = self.pro_wrapper.enhance(
    content=response,
    query=query,
    tools_used=tools_used,
)
```

This means every response automatically gets:
- Plain language interpretation (if missing)
- Specific next step (if response ends passively)
- Never "just say the word" endings

