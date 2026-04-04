# AutoJagaMAS — Legacy Notes

Bugs and issues observed in `legacy/jagabot/` during the AutoJagaMAS integration audit.
These are **noted only** — per the constraint, only the 3 specified fixes have been applied.

---

## Fixed in Phase A (3 Specified Fixes)

### Fix 1 — CognitiveStack.process() was never called
**File:** `legacy/jagabot/agent/loop.py`
**Line:** ~766 (after BrierScorer/BeliefEngine block)
**Issue:** `CognitiveStack` was instantiated and wired with BrierScorer, but `.process()`
was never called. All turns fell through to `_run_agent_loop()` regardless of complexity.
**Fix applied:** Inserted `cognitive_stack.process()` call with MAINTENANCE profile bypass
and fallback to `_run_agent_loop()` on exception.

---

### Fix 2 — Ollama had no ProviderSpec in registry
**File:** `legacy/jagabot/providers/registry.py`
**Line:** ~297 (after vLLM entry)
**Issue:** `registry.py` had no entry for Ollama. Any `ollama/` prefixed model would
fall through to the vLLM catch-all or raise an unknown-provider error.
**Fix applied:** Added `ProviderSpec(name="ollama", detect_by_base_keyword="localhost:11434", ...)`
between vLLM and Groq entries.

---

### Fix 3 — Config key mismatch + get_tool_definition missing name field
**File:** `legacy/jagabot/core/model_switchboard.py`
**Lines:** ~416 and ~333
**Issue 1:** `_load_config()` read `modelPresets` (camelCase) but the wiring guide and
`ajm_config.json` write `model_presets` (snake_case). Config-driven preset loading was silently
falling through to `DEFAULT_PRESETS` whenever a real config file was present.
**Fix applied:** Changed to `config.get("model_presets", config.get("modelPresets", DEFAULT_PRESETS))`.
**Issue 2:** `get_tool_definition()` returned a bare `parameters` dict without a `name` field.
Most tool registries (including MASFactory and OpenAI function calling) require `name` as a
top-level key in the tool schema.
**Fix applied:** Added `"name": "switch_model"` and `"description"` as top-level keys, wrapping
the existing properties dict under `"parameters"`.

---

## Additional Bugs Noted (Not Fixed)

### Note 1 — DispatchPackage.tools is a set, not JSON-serialisable
**File:** `legacy/jagabot/core/fluid_dispatcher.py`, `DispatchPackage` dataclass
**Line:** ~196
**Issue:** `tools: set` — Python sets are not directly JSON-serialisable. Any code
that attempts `json.dumps(package.__dict__)` or `json.dumps(asdict(package))` will
raise `TypeError: Object of type set is not JSON serializable`.
**Impact:** The AutoJagaMAS adapter (`jaga_bdi_context_provider.py`) works around this
by explicitly converting `package.tools` to a sorted list. But any direct serialisation
of `DispatchPackage` in `loop.py` metadata would fail.
**Recommended fix:** Change `tools: set` to `tools: set = field(default_factory=set)`
and add a `@property` that returns a sorted list for serialisation. Not applied — out of scope.

---

### Note 2 — 2modelfluid/ directory is dead code
**Path:** `legacy/2modelfluid/`
**Issue:** No Python module in `legacy/jagabot/` imports from `legacy/2modelfluid/`.
The directory contains older reference copies of `fluid_dispatcher.py` and
`model_switchboard.py`. All active imports point to `legacy/jagabot/core/`.
**Impact:** Low. The directory is harmless but adds confusion.
**Recommended fix:** Move to a `legacy/archive/` subdirectory with a README explaining
it is reference-only. Not applied — out of scope.

---

### Note 3 — cognitive_stack.py uses asyncio but has no event loop guard
**File:** `legacy/jagabot/core/cognitive_stack.py`
**Line:** ~222 (`async def process(...)`)
**Issue:** `CognitiveStack.process()` is `async`, which is correct. However, if called
from a context where an event loop is already running (e.g., inside Jupyter or a
FastAPI endpoint), `asyncio.run()` would raise `RuntimeError: This event loop is already running`.
The `loop.py` `_process_message` method is also async and uses `await`, so it handles this
correctly. But the JagaBDIModel adapter uses a thread-pool fallback for this case.
**Recommended fix:** Add `nest_asyncio` to `requirements.txt` as an optional dependency,
or document the limitation in `cognitive_stack.py`. Not applied — out of scope.

---

### Note 4 — PROFILE_MODEL_MAP not exported from model_switchboard
**File:** `legacy/jagabot/core/model_switchboard.py`
**Issue:** `PROFILE_MODEL_MAP` is defined as a module-level dict but is not listed in any
`__all__` export. The `jaga_model_router.py` adapter imports it directly — this works, but
if `model_switchboard.py` is refactored to use `__all__`, the import would break silently.
**Recommended fix:** Add `PROFILE_MODEL_MAP` to `__all__` if `__all__` is ever defined.

---

### Note 5 — loop.py docstring says 6 phases, code has 8+
**File:** `legacy/jagabot/agent/loop.py`
**Line:** ~55 (module docstring)
**Issue:** The docstring lists "Phase 1–6" of message processing. The actual `_process_message`
method now has additional phases (FluidDispatcher, ModelSwitchboard, CognitiveStack, Librarian,
SelfModel, etc.) added incrementally without updating the docstring.
**Impact:** Documentation drift — minor but confusing for new readers.
**Recommended fix:** Update the docstring to reflect the current phase list. Not applied — out of scope.
