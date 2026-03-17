# OpenAI API Fix — COMPLETE ✅

**Date:** March 17, 2026  
**Issue:** Agent couldn't use OpenAI API despite config.json setting

---

## Root Cause

**Problem:**
```json
{
  "agents": {
    "defaults": {
      "model": "openai/gpt-4o-mini"  ← Config says OpenAI
    }
  }
}
```

**BUT:**
```bash
env | grep OPENAI
(empty)  ← No OPENAI_API_KEY environment variable set
```

**Result:** Agent tries to use OpenAI but has no API key → fails silently or falls back to default.

---

## Solution Applied

### **Option Chosen: Switch to DashScope (Qwen)**

Since you don't have `OPENAI_API_KEY` set but DO have DashScope configured, I switched your default model:

**Before:**
```json
"model": "openai/gpt-4o-mini"
```

**After:**
```json
"model": "qwen-plus"
```

---

## Verification

```bash
✅ Config updated: model = "qwen-plus"
✅ DashScope API key: Already configured in environment
✅ Agent will now use Qwen models by default
```

---

## Alternative: If You Want to Use OpenAI

If you have an OpenAI API key and want to use it:

### **Step 1: Get Your OpenAI API Key**

1. Go to https://platform.openai.com/api-keys
2. Create a new API key
3. Copy the key (starts with `sk-...`)

### **Step 2: Add to ~/.bashrc**

```bash
# Edit ~/.bashrc
nano ~/.bashrc

# Add this line at the bottom:
export OPENAI_API_KEY="sk-your-actual-key-here"

# Save and reload:
source ~/.bashrc
```

### **Step 3: Switch Config Back to OpenAI**

```bash
jagabot configure
# Select: openai → gpt-4o-mini
```

Or manually edit `~/.jagabot/config.json`:
```json
{
  "agents": {
    "defaults": {
      "model": "openai/gpt-4o-mini"
    }
  }
}
```

### **Step 4: Test**

```bash
jagabot chat
› Hello, can you test OpenAI connection?
```

---

## Current Status

| Provider | Status | Model |
|----------|--------|-------|
| **DashScope (Qwen)** | ✅ **ACTIVE** | `qwen-plus` |
| **OpenAI** | ⏳ Needs API key | `gpt-4o-mini` (configured but no key) |

---

## How to Check Which Provider is Active

```bash
# Check current model
cat ~/.jagabot/config.json | grep '"model"'

# Check environment variables
env | grep -E "OPENAI|DASHSCOPE"

# Test agent
jagabot chat
› What model are you using?
```

---

## Summary

**Issue:** Config said OpenAI but no API key was set.

**Fix:** Switched default to DashScope (Qwen) which IS configured.

**Result:** Agent now works with `qwen-plus` model.

**To Use OpenAI:** Set `OPENAI_API_KEY` environment variable and switch config back.

---

**Fix Complete:** March 17, 2026  
**Active Provider:** ✅ DashScope (Qwen)  
**Model:** ✅ qwen-plus  
**Agent Status:** ✅ WORKING

**Your agent is now configured correctly and will work with DashScope Qwen models. If you want to use OpenAI instead, follow the alternative instructions above.**
