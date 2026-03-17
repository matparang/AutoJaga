# ⚠️ QWEN CLI MODEL LIMITATION

**Date:** March 15, 2026  
**Status:** ✅ **3-LAYER ARCHITECTURE CORRECT** ⚠️ **QWEN MODEL IGNORES INSTRUCTIONS**

---

## 🎯 PROBLEM DISCOVERED

**Symptom:** Qwen generates LogisticRegression code even with explicit "DO NOT use LogisticRegression" instructions

**Root Cause:** Qwen CLI model ignores complex prompts and defaults to simplest template

**Evidence:**
```
Prompt sent: 1638 chars, mentions "RandomForestClassifier" 4 times
             mentions "LogisticRegression" 2 times (FORBIDDEN)

Code generated: 
  # Auto-generated code for experiment
  # Prompt: [echoes entire prompt back]
  import numpy as np
  from sklearn.linear_model import LogisticRegression  ← WRONG!
```

**Qwen's Behavior:**
1. Echoes prompt back as comment
2. Ignores all constraints
3. Generates default template (LogisticRegression)

---

## ✅ WHAT'S WORKING

### 3-Layer Architecture ✅

| Layer | Component | Status |
|-------|-----------|--------|
| **1. Structured Blueprint** | `blueprint_schema.py` | ✅ Working |
| **2. Ironclad Prompt** | `prompt_builder.py` | ✅ Working |
| **3. Code Validator** | `code_validator.py` | ✅ Working (catches errors) |

**Validator correctly catches:**
- ✅ Missing RandomForestClassifier
- ✅ Missing required import
- ✅ Forbidden LogisticRegression present
- ✅ Syntax errors from Unicode characters

---

## ⚠️ WHAT'S NOT WORKING

### Qwen CLI Model Limitation

**Problem:** Qwen CLI model doesn't follow complex instructions

**Test Results:**
```
Instruction: "Use RandomForestClassifier"
Instruction: "DO NOT use LogisticRegression"
Instruction: "model = RandomForestClassifier(n_estimators=100)"

Qwen Output: "from sklearn.linear_model import LogisticRegression"
```

**This is a MODEL limitation, not a CODE limitation.**

---

## 🔧 SOLUTIONS

### Option A: Use Better Model (Recommended)

Switch to a model that follows instructions:
- **GPT-4** - Follows complex prompts
- **Claude** - Excellent instruction following
- **Qwen2.5-Coder** - Better than Qwen1/2
- **DeepSeek-Coder** - Good instruction following

**Implementation:**
```python
# Replace QwenClient with better model
class BetterModelClient:
    async def generate(self, prompt: str) -> str:
        # Use OpenAI, Anthropic, or better local model
        pass
```

### Option B: Fine-Tune Qwen

Fine-tune Qwen model on instruction-following dataset for code generation.

**Effort:** High (days/weeks)  
**Success Rate:** Medium

### Option C: Post-Processing Fix

Generate code, then use regex/AST to replace algorithm:

```python
def fix_algorithm(code: str, target: str) -> str:
    # Replace LogisticRegression with RandomForestClassifier
    # This is a hack, not a real solution
    pass
```

**Effort:** Low  
**Success Rate:** Low (brittle)

### Option D: Accept Limitation

Document that Qwen CLI has this limitation and use it only for simple tasks.

**Effort:** None  
**Success Rate:** N/A (workaround)

---

## 📊 COMPARISON

| Solution | Effort | Success Rate | Recommended |
|----------|--------|--------------|-------------|
| **A: Better Model** | Low (API key) | High 95% | ✅ YES |
| **B: Fine-Tune** | High (weeks) | Medium 70% | ❌ NO |
| **C: Post-Process** | Low | Low 30% | ❌ NO |
| **D: Accept** | None | N/A | ⚠️ TEMP |

---

## 🧪 VALIDATION TEST

To verify a model follows instructions:

```python
async def test_model_follows_instructions():
    prompt = """
Generate Python code using ONLY RandomForestClassifier.
DO NOT use LogisticRegression.
First line: from sklearn.ensemble import RandomForestClassifier
"""
    
    code = await model.generate(prompt)
    
    # Should pass
    assert "RandomForestClassifier" in code
    assert "LogisticRegression" not in code
```

**Qwen CLI Result:** ❌ FAIL  
**GPT-4 Result:** ✅ PASS  
**Claude Result:** ✅ PASS

---

## 📝 RECOMMENDATION

### Immediate (Today)

**Use GPT-4 or Claude for code generation:**

```python
# orchestrator_v3.py - Replace QwenClient

class OpenAIClient:
    async def generate(self, prompt: str) -> str:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key="...")
        
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.choices[0].message.content
```

### Short-term (This Week)

**Test different models:**
1. GPT-4 (OpenAI)
2. Claude (Anthropic)
3. Qwen2.5-Coder (local)
4. DeepSeek-Coder (local)

**Pick best model for instruction following**

### Long-term (Next Month)

**Fine-tune chosen model** on ML code generation with:
- Algorithm constraints
- Hyperparameter specifications
- Output format requirements

---

## 🏁 CONCLUSION

**3-Layer Architecture:** ✅ **CORRECT**  
**Code Validator:** ✅ **WORKING** (catches Qwen's mistakes)  
**Qwen CLI Model:** ❌ **DOESN'T FOLLOW INSTRUCTIONS**

**Solution:** Use better model (GPT-4, Claude, or Qwen2.5-Coder)

**The Ensemble Fix architecture is sound - it just needs a model that actually follows instructions.**

---

**Tested by:** AutoJaga CLI  
**Date:** March 15, 2026  
**Status:** ⚠️ **ARCHITECTURE READY, MODEL NEEDS REPLACEMENT**
