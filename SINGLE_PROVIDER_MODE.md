# Single Provider Mode — RESTORED ✅

**Date:** March 17, 2026  
**Status:** Fallback REMOVED — Single provider only

---

## What Changed

### **Removed: 3-Way Fallback System**

**Before (Complex):**
```python
FallbackProvider(
    primary=OpenAI,
    fallback=DeepSeek  # ← Caused "Insufficient Balance" errors
)
```

**After (Simple):**
```python
# Single provider only — NO FALLBACK
return LiteLLMProvider(...)
```

---

## How It Works Now

### **Single Provider Mode**

```
config.json has ONE provider with API key
       ↓
_make_provider() creates that provider ONLY
       ↓
If provider fails → See REAL error message
       ↓
NO automatic fallback to different provider
```

**Benefits:**
- ✅ No confusing fallback errors
- ✅ What you configure is what you get
- ✅ If it fails, you see the actual error

---

## How To Change Models

### **Method 1: Edit config.json (Recommended)**

**File:** `~/.jagabot/config.json`

**Find this section:**
```json
{
  "agents": {
    "defaults": {
      "model": "openai/gpt-4o"
    }
  }
}
```

**Change to:**
```json
{
  "agents": {
    "defaults": {
      "model": "openai/gpt-4o-mini"
    }
  }
}
```

**Available OpenAI Models:**
- `openai/gpt-4o-mini` (fast, cheap)
- `openai/gpt-4o` (balanced)
- `openai/o1-preview` (reasoning)
- `openai/gpt-4-turbo` (previous gen)

**Save and restart jagabot:**
```bash
jagabot chat
```

---

### **Method 2: Use jagabot configure Command**

```bash
jagabot configure
# Follow prompts to select model
```

---

## Current Configuration

**Your Settings:**
```
Model: openai/gpt-4o
Provider: openai
API Key: SET (sk-proj-CQ...)
Fallback: ❌ DISABLED
```

**To switch to gpt-4o-mini:**
```bash
nano ~/.jagabot/config.json
# Change: "model": "openai/gpt-4o"
# To:     "model": "openai/gpt-4o-mini"
# Save (Ctrl+O, Enter, Ctrl+X)
```

---

## Troubleshooting

### **Error: "No API key configured"**

**Fix:**
```bash
nano ~/.jagabot/config.json
# Make sure you have:
{
  "providers": {
    "openai": {
      "apiKey": "sk-proj-..."
    }
  }
}
```

### **Error: "Invalid API key"**

Your OpenAI API key is expired or invalid.

**Fix:**
1. Go to https://platform.openai.com/api-keys
2. Create new API key
3. Update config.json with new key

### **Want to switch providers (e.g., OpenAI → DashScope)**

**Edit config.json:**
```json
{
  "agents": {
    "defaults": {
      "model": "qwen-plus"  ← DashScope model
    }
  },
  "providers": {
    "dashscope": {
      "apiKey": "sk-..."  ← Your DashScope key
    }
  }
}
```

---

## Summary

**Removed:** FallbackProvider system  
**Restored:** Single provider mode  
**Result:** Simple, predictable, no confusing fallback errors

**To change model:** Edit `~/.jagabot/config.json` → Change `"model"` field → Restart jagabot

---

**Status:** March 17, 2026  
**Mode:** ✅ Single Provider  
**Fallback:** ❌ DISABLED  
**Config:** ✅ Edit config.json to change model

**Your agent now uses ONLY the provider specified in config.json — no automatic fallbacks, no confusing errors.**
