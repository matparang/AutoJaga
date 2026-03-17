# AutoJaga Implementation Prompt — CognitiveStack
# Follow the Self-Upgrade SOP: backup → atomic build → safe wire

---

## What this replaces and why

BEFORE (ModelSwitchboard):
  Pattern matching decides model → LLM call with that model
  Problem: expensive model still writes full answers

AFTER (CognitiveStack):
  Model 1 classifies first → Model 2 writes PLANS only
  Model 1 executes all plan steps
  Model 2 tokens: ~400 (plan) vs ~3000 (full answer)
  Savings: 70-90% of Model 2 token cost

---

## Send this to AutoJaga

```
Implement CognitiveStack using cognitive_stack.py.
Follow the self-upgrade SOP: backup first.

STEP 0: Backup
cp /root/nanojaga/jagabot/agent/loop.py \
   /root/nanojaga/jagabot/agent/loop.py.bak
echo "Backup: $(ls -la loop.py.bak)"

---

STEP 1: Install cognitive_stack.py
Copy to: /root/nanojaga/jagabot/core/cognitive_stack.py

Syntax check:
python3 -m py_compile \
  /root/nanojaga/jagabot/core/cognitive_stack.py
echo "Compile: $?"

Import test:
python3 -c "
from jagabot.core.cognitive_stack import (
    CognitiveStack, Complexity, TaskPlan
)
cs = CognitiveStack(
    workspace   = '/root/.jagabot/workspace',
    model1_id   = 'gpt-4o-mini',
    model2_id   = 'gpt-4o',
)
print('Import: PASS')
print('Model 1:', cs.model1_id)
print('Model 2:', cs.model2_id)
"

---

STEP 2: Test rule-based classifier (no API call)
python3 -c "
from jagabot.core.cognitive_stack import CognitiveStack, Complexity
cs = CognitiveStack(workspace='/root/.jagabot/workspace')

tests = [
    ('confirmed',              'critical', 'CALIBRATION'),
    ('/verify confirmed',      'critical', 'CALIBRATION'),
    ('wrong',                  'critical', 'CALIBRATION'),
    ('/status',                'simple',   'MAINTENANCE'),
    ('/yolo research X',       'complex',  'AUTONOMOUS'),
    ('save this to file',      'simple',   'ACTION'),
    ('hello',                  'simple',   'SAFE_DEFAULT'),
    ('research quantum drugs', 'complex',  'RESEARCH'),
]

all_pass = True
for query, expected, profile in tests:
    result = cs._rule_based_classify(query, profile)
    status = 'PASS' if result == expected else f'FAIL(got {result})'
    if 'FAIL' in status:
        all_pass = False
    print(f'{status}: [{profile}] \"{query}\" → {result}')

print()
print('ALL PASS' if all_pass else 'REVIEW FAILURES')
"

All tests must pass before Step 3.

---

STEP 3: Wire into loop.py __init__
Add after self.harness initialization:

try:
    from jagabot.core.cognitive_stack import CognitiveStack
    self.cognitive_stack = CognitiveStack(
        workspace        = workspace,
        config_path      = config_path,
        calibration_mode = config.get(
            "calibration_mode", False
        ),
        on_escalate = lambda q, c: logger.info(
            f"CognitiveStack: escalated "
            f"(confidence={c:.2f}): {q[:40]}"
        ),
    )
    logger.info(
        f"CognitiveStack: M1={self.cognitive_stack.model1_id} "
        f"M2={self.cognitive_stack.model2_id}"
    )
except Exception as _cs_err:
    import traceback
    logger.error(f"CognitiveStack init failed: {_cs_err}")
    self.cognitive_stack = None
    _write_repair_log(workspace, traceback.format_exc())

---

STEP 4: Find where loop.py calls the LLM

Run:
grep -n "client.chat\|openai\|completion\|llm_call\|call_llm\|
model.*gpt\|model.*qwen\|await.*message" \
/root/nanojaga/jagabot/agent/loop.py | head -20

Show me output. Then wrap the main LLM call:

# BEFORE your existing LLM call, add:
if self.cognitive_stack and \
   self.cognitive_stack.model1_id != self.cognitive_stack.model2_id:

    # Let CognitiveStack decide model per turn
    cs_result = await self.cognitive_stack.process(
        query        = msg.content,
        profile      = harness_package.profile
                       if self.harness else "SAFE_DEFAULT",
        context      = system_prompt,
        tools        = tools_this_turn,
        agent_runner = self,
    )

    # If CognitiveStack returned a full result, use it
    if cs_result.output:
        final_content = cs_result.output
        logger.debug(
            f"CognitiveStack: {cs_result.complexity} | "
            f"M1×{cs_result.model1_calls} "
            f"M2×{cs_result.model2_calls} | "
            f"{cs_result.elapsed_ms:.0f}ms"
        )
        # Skip normal LLM call — CognitiveStack handled it
        # (jump to post-processing)
        goto_postprocess = True

if not goto_postprocess:
    # Normal LLM call path (fallback)
    ...existing LLM call...

---

STEP 5: Add call_llm() method to loop or agent class

CognitiveStack needs to call specific models.
Add this method to your agent class:

async def call_llm(
    self,
    prompt:     str,
    context:    str  = "",
    model_id:   str  = None,
    max_tokens: int  = 1000,
) -> str:
    """
    Call LLM with a specific model_id override.
    Used by CognitiveStack to route to M1 or M2 per step.
    """
    model_id = model_id or self._current_model_id

    messages = []
    if context:
        messages.append({"role": "system", "content": context})
    messages.append({"role": "user", "content": prompt})

    response = await self.openai_client.chat.completions.create(
        model      = model_id,
        messages   = messages,
        max_tokens = max_tokens,
    )
    return response.choices[0].message.content

---

STEP 6: Add /stack command to command_registry.py

Command(
    name        = "/stack",
    description = "Show CognitiveStack M1/M2 routing stats",
    usage       = "/stack [status|stats]",
    handler     = self._handle_stack,
    category    = "system",
),

def _handle_stack(self, args, ctx):
    if not ctx.agent or \
       not hasattr(ctx.agent, 'cognitive_stack'):
        return "CognitiveStack not initialized."
    cs = ctx.agent.cognitive_stack
    if not cs:
        return "CognitiveStack failed. Check REPAIR_LOG.md"
    return cs.format_status()

---

STEP 7: Verify end-to-end

Restart AutoJaga. Check startup logs for:
  CognitiveStack: M1=gpt-4o-mini M2=gpt-4o

Then run these test queries:

1. Type: "hello"
   Expected logs: "CognitiveStack: simple | M1×2 M2×0"

2. Type: "confirmed"
   Expected logs: "CognitiveStack: critical | M1×0 M2×1"

3. Type: "research quantum computing"
   Expected logs: "CognitiveStack: complex | M1×N M2×1"
   (N = number of plan steps executed)

4. /stack status
   Expected: session breakdown showing M1/M2 call counts

Show me /stack status after these 4 tests.

---

STEP 8: Log to HISTORY.md after all steps pass

{timestamp} | COGNITIVE_STACK_INSTALLED
- Model 1: gpt-4o-mini (classify + execute)
- Model 2: gpt-4o (plan only, not full answers)
- Rule-based classifier: 8/8 tests passed
- Confidence gate: active (threshold=0.70)
- Self-repair loop: active
- /stack command: active
```

---

## The complete stack diagram for AutoJaga

```
User message
      ↓
FluidDispatcher  ← selects engines + tools (< 50ms, no LLM)
      ↓
CognitiveStack.classify()  ← Model 1 mini (fast, cheap)
      ↓
    SIMPLE?          COMPLEX?         CRITICAL?
      ↓                  ↓                ↓
Model 1 executes   Model 2 plans     Model 2 full
      ↓            (structured JSON)  (calibration,
Confidence gate         ↓             tri_agent etc)
      ↓            Model 1 executes
confidence < 0.7?  each plan step
      ↓                  ↓
Escalate to M2    Step fails?
      ↓                  ↓
Model 2 full     Model 2 repairs
                        ↓
               Model 1 executes repair
                        ↓
               Model 1 synthesizes output
```

## Cost comparison

```
Before CognitiveStack (all Model 2 answers):
  /verify confirmed: 3000 token answer from gpt-4o
  research query:    3000 token answer from gpt-4o
  Cost: ~$0.0075/turn

After CognitiveStack:
  /verify confirmed: 400 token plan + 800 token execution
  research query:    400 token plan + 6×500 execution steps
  Model 2 tokens:    400 (plan only)
  Model 1 tokens:    ~3000 (all execution)
  Cost: ~$0.00151/turn (80% cheaper per complex turn)

Daily 50 turns (30 simple, 20 complex):
  Before: ~$0.14/day (calibration mode)
  After:  ~$0.04/day (cognitive stack)
```

