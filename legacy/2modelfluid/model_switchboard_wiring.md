# ModelSwitchboard — Wiring Guide + AutoJaga Prompt

---

## Step 1 — Update config.json first

Ask AutoJaga:
```
Update config.json to add model_presets section.
Add this structure (keep all existing keys, just add these):

"model_presets": {
  "1": {
    "name": "GPT-4o-mini (Fast)",
    "model_id": "gpt-4o-mini",
    "provider": "openai",
    "purpose": "routine",
    "max_tokens": 2000,
    "token_cost_per_1k_input": 0.00015,
    "token_cost_per_1k_output": 0.00060
  },
  "2": {
    "name": "GPT-4o (Smart)",
    "model_id": "gpt-4o",
    "provider": "openai",
    "purpose": "reasoning",
    "max_tokens": 4000,
    "token_cost_per_1k_input": 0.00250,
    "token_cost_per_1k_output": 0.01000
  }
},
"current_model": "1",
"auto_switch": true

Show me config.json after update.
```

---

## Step 2 — Install and wire

Send this full prompt to AutoJaga:

```
Install the ModelSwitchboard for dynamic model switching.

TASK 1: Install
Copy model_switchboard.py to:
/root/nanojaga/jagabot/core/model_switchboard.py

Syntax check:
python3 -m py_compile \
  /root/nanojaga/jagabot/core/model_switchboard.py
echo "Compile: $?"

Import test:
python3 -c "
from jagabot.core.model_switchboard import ModelSwitchboard
ms = ModelSwitchboard()
print('Import: PASS')
print('Presets:', list(ms._presets.keys()))
"

---

TASK 2: Wire into loop.py __init__
After self.harness initialization, add:

try:
    from jagabot.core.model_switchboard import ModelSwitchboard
    self.switchboard = ModelSwitchboard(
        config_path = config_path,
        workspace   = workspace,
    )
    logger.info(
        f"ModelSwitchboard: initialized — "
        f"current=Model {self.switchboard._current}"
    )
except Exception as e:
    logger.warning(f"ModelSwitchboard init failed: {e}")
    self.switchboard = None

---

TASK 3: Wire into _process_message — AFTER FluidDispatcher

# Resolve model for this turn
if self.switchboard:
    model_cfg = self.switchboard.resolve_model(
        profile          = harness_package.profile
                           if self.harness else "SAFE_DEFAULT",
        confidence       = getattr(self, '_last_confidence', 1.0),
        query            = msg.content,
        calibration_mode = getattr(
            self, 'calibration_mode',
            type('', (), {'enabled': False})()
        ).enabled,
        manual_override  = getattr(self, '_manual_model', None),
    )
    # Store for LLM call
    self._current_model_id    = model_cfg.model_id
    self._current_model_name  = model_cfg.name
    self._current_max_tokens  = model_cfg.max_tokens
else:
    # Fallback to config model
    self._current_model_id   = config.get("model", "gpt-4o-mini")
    self._current_max_tokens = 2000

# Log model selection
logger.debug(
    f"Model: {self._current_model_id} "
    f"({model_cfg.reason if self.switchboard else 'config'})"
)

---

TASK 4: Wire _current_model_id into actual LLM call

Find where your loop makes the OpenAI/LiteLLM API call.
Replace the hardcoded model string with:

response = await client.chat.completions.create(
    model      = self._current_model_id,  # ← dynamic
    max_tokens = self._current_max_tokens,
    messages   = messages,
    tools      = tool_definitions,
)

# Record turn for cost tracking
if self.switchboard:
    usage = response.usage
    self.switchboard.record_turn(
        preset_id     = model_cfg.preset_id,
        input_tokens  = usage.prompt_tokens,
        output_tokens = usage.completion_tokens,
        reason        = model_cfg.reason,
        auto          = model_cfg.auto_selected,
    )

---

TASK 5: Add /model command to command_registry.py

Command(
    name        = "/model",
    description = "Switch or view active LLM model",
    usage       = "/model [1|2|auto|status]",
    handler     = self._handle_model,
    category    = "system",
),

def _handle_model(self, args: str, ctx: CommandContext) -> str:
    if not ctx.agent or not hasattr(ctx.agent, 'switchboard'):
        return "ModelSwitchboard not initialized."

    sb = ctx.agent.switchboard
    if not sb:
        return "ModelSwitchboard failed to initialize."

    args = args.strip().lower()

    if args == "auto":
        return sb.set_auto()

    if args in ("1", "2"):
        # Manual switch — store on agent for this session
        ctx.agent._manual_model = args
        return sb.manual_switch(args)

    if args == "status" or not args:
        return sb.get_status()

    return (
        "Usage: /model [1|2|auto|status]\n"
        "  /model 1      → switch to fast model (routine)\n"
        "  /model 2      → switch to smart model (reasoning)\n"
        "  /model auto   → restore automatic switching\n"
        "  /model status → show current model and session stats"
    )

---

TASK 6: Add switch_model tool to tool registry

The agent can self-switch when it detects a complex task:

# In tool_registry or tools/__init__.py:
switchboard = self.switchboard  # reference

def tool_switch_model(preset_id: str, reason: str) -> str:
    if not switchboard:
        return "ModelSwitchboard not available"
    result = switchboard.manual_switch(preset_id)
    logger.info(f"Agent self-switched to Model {preset_id}: {reason}")
    return result

# Register as a tool:
self.tool_registry["switch_model"] = tool_switch_model

---

TASK 7: Wire into Telegram channel (if active)

In telegram.py message handler, add /model support:

async def handle_model_command(update, context):
    sb = agent.switchboard
    if not sb:
        await update.message.reply_text("Switchboard not available")
        return

    # Show inline keyboard
    keyboard = sb.get_telegram_keyboard()
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(btn["text"],
                              callback_data=btn["callback_data"])]
        for row in keyboard for btn in row
    ])
    await update.message.reply_text(
        "Select model:", reply_markup=reply_markup
    )

async def handle_model_callback(update, context):
    query = update.callback_query
    await query.answer()
    result = agent.switchboard.handle_telegram_callback(
        query.data
    )
    await query.edit_message_text(result)

---

TASK 8: Verify end-to-end

Restart AutoJaga and run:

/model status
→ shows Model 1 active (auto), Model 2 available

/model 2
→ "✅ Switched to Model 2: GPT-4o (Smart)"

Then send a normal message
→ check logs: "Model: gpt-4o (manual_command)"

/model auto
→ "✅ Auto model switching restored"

Then run /verify confirmed
→ check logs: "Model: gpt-4o (calibration_mode or CALIBRATION profile)"

/model status
→ shows session breakdown: X turns Model 1, Y turns Model 2

Show me /model status output.
```

---

## How auto-switching works with FluidDispatcher

```
Turn: "hello"
  FluidDispatcher: SAFE_DEFAULT profile
  ModelSwitchboard: SAFE_DEFAULT → Model 1 (fast)
  Model used: gpt-4o-mini
  Cost: ~$0.00005/turn

Turn: "/verify confirmed"
  FluidDispatcher: CALIBRATION profile
  ModelSwitchboard: CALIBRATION → always Model 2
  Model used: gpt-4o
  Cost: ~$0.005/turn

Turn: "research quantum computing"
  FluidDispatcher: RESEARCH profile
  ModelSwitchboard: RESEARCH → Model 2
  Model used: gpt-4o
  Cost: ~$0.005/turn

Turn: "save this to file"
  FluidDispatcher: ACTION profile
  ModelSwitchboard: ACTION → Model 1
  Model used: gpt-4o-mini
  Cost: ~$0.00005/turn
```

## Daily cost estimate (50 turns)

```
Typical session mix:
  30 turns Model 1 (SAFE_DEFAULT, ACTION, MAINTENANCE)
  20 turns Model 2 (RESEARCH, CALIBRATION, VERIFICATION)

Cost:
  Model 1: 30 × ~1100 tokens × $0.00015/1k = $0.005
  Model 2: 20 × ~1100 tokens × $0.00250/1k = $0.055
  Total:   ~$0.06/day

vs full GPT-4o for all 50 turns:
  50 × ~5000 tokens × $0.00250/1k = $0.625/day

Savings: ~90% cost reduction
Quality: zero degradation on reasoning turns
         (always Model 2 when it matters)
```

---

## Agent self-switching (advanced)

When agent detects it's outclassed, it can call switch_model:

```
User: "analyze the causal graph and compute IPW weights
       then verify with adversarial tri-agent"

Agent reasoning:
  → complex multi-step
  → tri_agent involved
  → verification required
  → calls: switch_model(preset_id="2",
             reason="complex causal analysis + tri_agent")
  → switches to gpt-4o for this turn
  → proceeds with full capability
```

Add to AGENTS.md:
```
## Model Switching Rule

If a task requires:
- Multi-step causal reasoning
- Calibration or outcome recording
- tri_agent or quad_agent calls
- Complex financial analysis
- Cross-domain synthesis

Call switch_model(preset_id="2", reason="<why>")
BEFORE starting the task.

If a task is routine:
- File read/write
- Status check
- Simple memory retrieval
- Acknowledge/confirm messages

Stay on current model (likely Model 1).
Only switch when genuinely needed — Model 2 costs 16x more.
```

