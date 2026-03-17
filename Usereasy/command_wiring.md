# Command Registry — Wiring Guide
# Works across CLI, TUI, and Telegram

---

## File location
jagabot/cli/command_registry.py

---

## Step 1 — Wire into CLI (interactive.py)

In EnhancedCLI.__init__():
```python
from jagabot.cli.command_registry import (
    CommandRegistry, CLICommandDispatcher
)
registry       = CommandRegistry(workspace)
self.cmd_dispatcher = CLICommandDispatcher(
    registry  = registry,
    workspace = workspace,
    agent     = self.agent,
)
```

In EnhancedCLI._process_turn():
```python
# Replace the existing slash command handler with:
if user_input.startswith("/"):
    response = self.cmd_dispatcher.handle(
        user_input,
        session_key=self._session_key,
    )
    if response:
        print_agent_streaming(response, stream=self.stream)
    return
```

---

## Step 2 — Wire into TUI (tui.py)

In JagabotTUI.on_mount():
```python
from jagabot.cli.command_registry import (
    CommandRegistry, CLICommandDispatcher
)
registry       = CommandRegistry(self.workspace)
self.cmd_dispatcher = CLICommandDispatcher(registry, self.workspace)
```

In JagabotTUI._process_query():
```python
if query.startswith("/"):
    response = self.cmd_dispatcher.handle(query)
    if response:
        chat.add_agent(response)
    return
```

---

## Step 3 — Wire into Telegram channel

In jagabot/channels/telegram.py message handler:
```python
from jagabot.cli.command_registry import (
    CommandRegistry, TelegramCommandDispatcher
)

registry    = CommandRegistry(workspace)
tg_dispatch = TelegramCommandDispatcher(
    registry  = registry,
    workspace = workspace,
    agent     = agent,
)

# In message handler:
async def handle_message(update, context):
    text = update.message.text or ""
    
    if text.startswith("/"):
        response = tg_dispatch.handle(
            text    = text,
            user_id = str(update.message.from_user.id),
            chat_id = str(update.message.chat_id),
        )
        if response:
            await update.message.reply_text(
                response,
                parse_mode="Markdown",
            )
            return
    
    # Normal message handling...
```

---

## Step 4 — Register with BotFather (Telegram)

Run this to get the command list:
```python
from jagabot.cli.command_registry import get_telegram_botfather_commands
print(get_telegram_botfather_commands())
```

Then:
1. Open Telegram, message @BotFather
2. Send /setcommands
3. Select your bot
4. Paste the output

Users will then see autocomplete when they type / in your bot.

---

## Full command reference

```
CONTEXT
  /compress      Compress context + flush to memory
  /context       Show context window usage
  /export        Export session to markdown file
  /sessions      List recent research sessions

AGENT
  /spawn <task>  Spawn background subagent
  /kill [id]     Kill subagent or current run
  /stop          Stop current task
  /restart       Restart agent, fresh context
  /subagents     List/manage subagents

RESEARCH
  /research <t>  Deep research on topic
  /idea <topic>  Idea generation (tri-agent)
  /yolo <goal>   Fully autonomous research
  /verify <...>  Verify past conclusion
  /pending       Show unverified conclusions

MEMORY
  /memory        Show/search/flush memory
  /skills        List available skills

SYSTEM
  /status        Full kernel + memory status
  /think <level> Set reasoning depth
  /model [name]  Show/switch LLM model
  /usage         Token usage + cost
  /config        Show/get/set config values
  /clear         Clear session context
  /btw <q>       Quick side question
  /help          Show all commands
```

---

## What works immediately vs needs wiring

Works immediately (no agent needed):
  /help, /pending (reads file), /sessions,
  /skills, /memory show, /config show,
  /think, /btw, /research, /idea, /verify

Needs agent wiring:
  /compress (needs agent.get_session_text())
  /spawn (needs subagent tool)
  /kill, /stop (needs agent._running)
  /restart (needs agent.restart())
  /status (needs tool calls)
  /usage (needs token tracking)
  /yolo (already wired from yolo.py)

