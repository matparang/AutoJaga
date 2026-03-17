# MODEL CONFIG FIX — NO MORE CONFUSION ✅

**Date:** March 17, 2026  
**Status:** RESOLVED — Clear separation between fallback and dynamic model

---

## PROBLEM IDENTIFIED

**Confusing Config:**
```json
{
  "agents": {
    "defaults": {
      "model": "modelPresets"  ← ❌ CONFUSING! Not a real model ID
    }
  }
}
```

**Issues:**
1. `"modelPresets"` is not a valid LiteLLM model ID
2. Conflicts with `model_presets` section
3. Unclear what it does

---

## SOLUTION

### **Clear Separation of Concerns**

**`agents.defaults.model`** → **Fallback only** (when auto-switch disabled)
```json
{
  "agents": {
    "defaults": {
      "model": "openai/gpt-4o-mini"  ← ✅ Valid model ID, fallback only
    }
  }
}
```

**`model_presets`** → **Dynamic model selection** (when auto-switch enabled)
```json
{
  "model_presets": {
    "1": {"model_id": "openai/gpt-4o-mini", ...},
    "2": {"model_id": "openai/gpt-4o", ...}
  },
  "current_model": "1",
  "auto_switch": true
}
```

---

## HOW IT WORKS NOW

### **With Auto-Switch Enabled (Default)**

```
ModelSwitchboard selects model based on profile:
  MAINTENANCE → Model 1 (openai/gpt-4o-mini)
  CALIBRATION → Model 2 (openai/gpt-4o)
  
agents.defaults.model is IGNORED (fallback only)
```

### **With Auto-Switch Disabled**

```
User runs: jagabot model 2
→ Sets current_model = "2"
→ Uses model_presets["2"].model_id = "openai/gpt-4o"

agents.defaults.model is IGNORED (uses preset instead)
```

### **If model_presets Missing (Fresh Install)**

```
Schema defaults provide model_presets
→ Model 1: openai/gpt-4o-mini
→ Model 2: openai/gpt-4o

agents.defaults.model = "openai/gpt-4o-mini" (matches Model 1)
```

---

## MIGRATION FIX

### **What Was Changed**

**1. Schema Defaults (schema.py):**
```python
class AgentDefaults(BaseModel):
    workspace: str = "~/.jagabot/workspace"
    model: str = "openai/gpt-4o-mini"  # Fallback only
    # ... other fields
```

**Before:** `model: str = "anthropic/claude-opus-4-5"`  
**After:** `model: str = "openai/gpt-4o-mini"` (matches Model 1)

---

**2. Config Migration (loader.py):**
```python
def _migrate_config(data: dict) -> dict:
    # Fix confusing model values
    if "agents" in data and "defaults" in data["agents"]:
        old_model = data["agents"]["defaults"].get("model", "")
        if old_model in ["modelPresets", "model_presets", "auto", "switching"]:
            data["agents"]["defaults"]["model"] = "openai/gpt-4o-mini"
            print("ℹ️ Fixed agents.defaults.model → openai/gpt-4o-mini")
    
    return data
```

**Detects and fixes:**
- `"modelPresets"` → `"openai/gpt-4o-mini"`
- `"model_presets"` → `"openai/gpt-4o-mini"`
- `"auto"` → `"openai/gpt-4o-mini"`
- `"switching"` → `"openai/gpt-4o-mini"`

---

## TEST RESULTS

**Before Migration:**
```json
{
  "agents": {
    "defaults": {
      "model": "modelPresets"  ← Confusing!
    }
  }
}
```

**After Migration:**
```
✅ Added model_presets to config (model switching enabled)
ℹ️ Fixed agents.defaults.model → openai/gpt-4o-mini (fallback only)
```

```json
{
  "agents": {
    "defaults": {
      "model": "openai/gpt-4o-mini"  ← Clear!
    }
  },
  "model_presets": {
    "1": {...},
    "2": {...}
  },
  "current_model": "1",
  "auto_switch": true
}
```

---

## FILES MODIFIED

| File | Changes | Purpose |
|------|---------|---------|
| `jagabot/config/schema.py` | 1 line | Changed default model to match Model 1 |
| `jagabot/config/loader.py` | +10 lines | Migration fixes confusing model values |

---

## VERIFICATION

### **Test 1: Confusing Model Value**
```bash
python3 -c "
from jagabot.config.loader import _migrate_config

config = {'agents': {'defaults': {'model': 'modelPresets'}}}
migrated = _migrate_config(config)
print(migrated['agents']['defaults']['model'])
"
```

**Expected:** `openai/gpt-4o-mini`

---

### **Test 2: Schema Defaults**
```bash
python3 -c "
from jagabot.config.schema import AgentDefaults

defaults = AgentDefaults()
print(defaults.model)
"
```

**Expected:** `openai/gpt-4o-mini`

---

### **Test 3: Load Current Config**
```bash
cat ~/.jagabot/config.json | python3 -c "
import json, sys
c = json.load(sys.stdin)
print('agents.defaults.model:', c['agents']['defaults']['model'])
print('model_presets present:', 'model_presets' in c)
print('auto_switch:', c.get('auto_switch'))
"
```

**Expected:**
```
agents.defaults.model: openai/gpt-4o-mini
model_presets present: True
auto_switch: True
```

---

## SUMMARY

**Problem:** `agents.defaults.model = "modelPresets"` was confusing  
**Solution:** Migrate to `"openai/gpt-4o-mini"` + add comment explaining it's fallback only  
**Status:** ✅ RESOLVED

**Now:**
- ✅ `agents.defaults.model` = valid LiteLLM model ID
- ✅ `model_presets` = dynamic model selection
- ✅ Clear separation of concerns
- ✅ Auto-migration fixes old confusing configs

**No more confusion between fallback model and dynamic model switching!** 🎉

---

**Fix Complete:** March 17, 2026  
**Migration:** ✅ AUTOMATIC  
**Schema Defaults:** ✅ CLEAR  
**Confusion Eliminated:** ✅ YES

**Your config is now crystal clear — `agents.defaults.model` is just a fallback, while `model_presets` handles dynamic switching!**
