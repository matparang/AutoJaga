# FluidDispatcher — Wiring Guide + QWEN CLI Prompt

---

## Send this to QWEN CLI

```
Implement the Fluid Harness experiment using fluid_dispatcher.py.

AUDIT FIRST — before writing any code, run:

grep -n "def __init__\|self\.librarian\|self\.brier\|self\.curiosity\|
self\.tracker\|self\.belief\|self\.self_model\|self\.interceptor\|
self\.trajectory\|self\.goal_engine" \
/root/nanojaga/jagabot/agent/loop.py | head -40

Show me the output. Then proceed in this order:

---

TASK 1: Install fluid_dispatcher.py
Copy to: /root/nanojaga/jagabot/core/fluid_dispatcher.py

Syntax check:
python3 -m py_compile /root/nanojaga/jagabot/core/fluid_dispatcher.py
echo "Compile: $?"

Import test:
python3 -c "
from jagabot.core.fluid_dispatcher import (
    FluidDispatcher, HarnessManager, HARNESS_PROFILES
)
print('Import: PASS')
print('Profiles:', list(HARNESS_PROFILES.keys()))
"

Do NOT proceed until both pass.

---

TASK 2: Smoke test classify_intent()
python3 -c "
from jagabot.core.fluid_dispatcher import FluidDispatcher
fd = FluidDispatcher()

tests = [
    ('/verify confirmed',  'CALIBRATION'),
    ('/yolo research X',   'AUTONOMOUS'),
    ('/status',            'MAINTENANCE'),
    ('confirmed',          'CALIBRATION'),
    ('research quantum',   'RESEARCH'),
    ('verify this claim',  'VERIFICATION'),
    ('write file X',       'ACTION'),
    ('hello',              'SAFE_DEFAULT'),
]

all_pass = True
for query, expected in tests:
    profile, reason = fd.classify_intent(query)
    status = 'PASS' if profile == expected else 'FAIL'
    if status == 'FAIL':
        all_pass = False
    print(f'{status}: \"{query}\" → {profile} (expected {expected})')

print()
print('ALL PASS' if all_pass else 'SOME FAILED — review above')
"

All 8 tests must pass. Report any failures to me before Task 3.

---

TASK 3: Wire into loop.py __init__

After all existing engine initializations, add:

# ── Fluid Harness ────────────────────────────────────────────────────
try:
    from jagabot.core.fluid_dispatcher import HarnessManager
    self.harness = HarnessManager(
        workspace        = workspace,
        calibration_mode = config.get("calibration_mode", False),
        k1_tool          = getattr(self, 'k1_bayesian_tool', None),
    )
    self.harness.register_all(self)
    logger.info(
        f"FluidHarness: initialized — "
        f"{len(self.harness._registry)} engines registered"
    )
except Exception as _harness_err:
    import traceback
    logger.error(f"FluidHarness init failed: {_harness_err}")
    self.harness = None
    # Write to REPAIR_LOG
    repair_log = Path(workspace) / "memory" / "REPAIR_LOG.md"
    with open(repair_log, "a") as f:
        f.write(f"\n## FluidHarness FAILED {datetime.now()}\n"
                f"```\n{traceback.format_exc()}\n```\n")
# ────────────────────────────────────────────────────────────────────

---

TASK 4: Wire into _process_message START

REPLACE the current engine context loading section with:

# FluidDispatcher replaces manual engine loading
if self.harness:
    is_first = self._first_message
    package  = self.harness.dispatch(
        user_input   = msg.content,
        topic        = detected_topic,
        confidence   = getattr(self, '_last_confidence', 1.0),
        has_pending  = (
            self.tracker.has_overdue_pending()
            if self.tracker else False
        ),
        is_first_msg = is_first,
    )
    # Use harness output
    engine_context  = package.context
    tools_this_turn = package.tools
    logger.debug(
        f"FluidHarness: profile={package.profile} | "
        f"~{package.token_estimate}t | "
        f"engines={package.engines_active} | "
        f"{package.dispatch_ms:.1f}ms"
    )
else:
    # Fallback: full load (harness not initialized)
    engine_context  = ""
    tools_this_turn = set(self.tool_registry.keys())

# Inject engine_context into system_prompt
if engine_context:
    system_prompt = engine_context + "\n\n---\n\n" + system_prompt

---

TASK 5: Add /harness command to command_registry.py

Command(
    name        = "/harness",
    description = "Control and inspect the Fluid Harness",
    usage       = "/harness [status|stats|profiles|force <e>|freeze <e>|clear]",
    handler     = self._handle_harness,
    category    = "system",
),

def _handle_harness(self, args: str, ctx: CommandContext) -> str:
    if not ctx.agent or not hasattr(ctx.agent, 'harness'):
        return "FluidHarness not initialized."
    if not ctx.agent.harness:
        return "FluidHarness failed to initialize. Check REPAIR_LOG.md"
    return ctx.agent.harness.handle_command(args)

---

TASK 6: Verify end-to-end

Restart AutoJaga and check startup logs for:
  FluidHarness: initialized — N engines registered

Then run:
  /harness profiles   → shows 6 profiles
  /harness status     → shows 0 turns (just started)
  /pending            → triggers CALIBRATION profile
  /harness status     → shows 1 turn, CALIBRATION profile, token savings

Show me /harness status output after running /pending.

---

TASK 7: Log to HISTORY.md

After all 6 tasks pass:
{timestamp} | FLUID_HARNESS_INSTALLED
- Profiles: MAINTENANCE, CALIBRATION, ACTION, RESEARCH,
            VERIFICATION, AUTONOMOUS, SAFE_DEFAULT
- Dispatch time: < 50ms guaranteed
- K1 routing: active for ambiguous profiles
- Token savings: TBD after first session
- /harness command: active
```

---

## Expected token profile after wiring

```
Query: "/pending"
  Profile: CALIBRATION
  Engines: librarian(150) + belief_engine(120) +
           brier_scorer(80) + outcome_tracker(50)
  Tools: 6
  Total engine tokens: ~400
  vs current: ~1500 tokens
  Savings: 73%

Query: "hello"
  Profile: SAFE_DEFAULT
  Engines: librarian(150)
  Tools: 4
  Total engine tokens: ~150
  vs current: ~1500 tokens
  Savings: 90%

Query: "/yolo research quantum"
  Profile: AUTONOMOUS
  Engines: librarian(150) + k5_planner(200) +
           goal_engine(100)
  Tools: 9
  Total engine tokens: ~450
  vs current: ~1500 tokens
  Savings: 70%
```

---

## The /harness commands

```
/harness status         → what fired last turn and why
/harness stats          → session firing rates + token savings
/harness profiles       → all 6 profiles and their descriptions
/harness force belief_engine  → force it active all session
/harness freeze curiosity_engine → keep it dormant all session
/harness clear          → reset all forced overrides
```
