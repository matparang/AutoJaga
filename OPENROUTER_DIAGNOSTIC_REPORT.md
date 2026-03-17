# OpenRouter Integration Diagnostic Report

**Date:** 2026-03-17  
**Status:** BLOCKED - Cannot make OpenRouter API calls work  
**Severity:** CRITICAL - Agent cannot function

---

## EXECUTIVE SUMMARY

AutoJaga agent is configured to use OpenRouter as the LLM provider, but ALL API calls fail. Multiple fix attempts have been made without success. Need fresh eyes on this problem.

---

## ENVIRONMENT

```
Project: AutoJaga (autonomous research agent)
Location: /root/nanojaga
Python: 3.12
LLM Router: LiteLLM v1.x (via litellm.acompletion)
Provider: OpenRouter (https://openrouter.ai)
Model: gpt-4o-mini (via OpenRouter)
Config: ~/.jagabot/config.json
```

---

## CONFIGURATION

### API Key Location
```bash
# Confirmed present in config.json:
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-proj-..."  # ✅ Present and valid
    }
  }
}

# Also set as environment variable:
export OPENROUTER_API_KEY="sk-proj-..."  # ✅ Set
```

### Model Configuration
```json
{
  "agents": {
    "defaults": {
      "model": "openai/gpt-4o-mini"
    }
  },
  "model_presets": {
    "1": {
      "model_id": "openai/gpt-4o-mini",
      "provider": "openai"
    }
  }
}
```

---

## ERROR HISTORY

### Error #1: Unexpected 'usage' Parameter
**Symptom:**
```
litellm.APIError: APIError: OpenrouterException -
AsyncCompletions.create() got an unexpected keyword argument 'usage'
```

**Attempts Made:**
1. ✅ Set `litellm.drop_params = True`
2. ✅ Set `LITELLM_DROP_PARAMS=True` env var
3. ✅ Manually stripped `usage` from kwargs before call
4. ✅ Created wrapper function to strip params
5. ✅ Added multi-factor OpenRouter detection

**Result:** ❌ FAILED - LiteLLM internally adds `usage` param after our cleanup

---

### Error #2: Missing Authentication Header
**Symptom:**
```
Error code: 401 - {'error': {'message': 'Missing Authentication header', 'code': 401}}
```

**Context:**
- Occurred when bypassing LiteLLM and using raw OpenAI client
- API key exists in config and env var
- Using correct OpenRouter endpoint: `https://openrouter.ai/api/v1`

**Attempted Fix:**
```python
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    default_headers={
        "HTTP-Referer": "https://github.com/jagabot",
        "X-Title": "jagabot",
    }
)
```

**Result:** ❌ FAILED - Still getting 401

---

## CODE ANALYSIS

### Current Implementation (jagabot/providers/litellm_provider.py)

**LiteLLM Provider Class:**
```python
class LiteLLMProvider(LLMProvider):
    def __init__(self, api_key, api_base, ...):
        self._gateway = find_gateway(provider_name, api_key, api_base)
        # ... setup env vars ...
    
    async def chat(self, messages, tools, model, ...):
        model = self._resolve_model(model)
        
        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        # OpenRouter detection
        is_openrouter = (
            "openrouter" in model.lower() or
            "openrouter" in (self.api_base or "").lower() or
            os.getenv("OPENROUTER_API_KEY")  # ← This triggers
        )
        
        if is_openrouter:
            # Strip params
            kwargs.pop("usage", None)
            kwargs.pop("stream_options", None)
            # ... more stripping ...
            
            # BYPASS LiteLLM - use direct OpenAI client
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=os.getenv("OPENROUTER_API_KEY"),
                default_headers={...}
            )
            response = await client.chat.completions.create(
                model=kwargs["model"].replace("openrouter/", ""),
                messages=kwargs["messages"],
                max_tokens=kwargs.get("max_tokens"),
                temperature=kwargs.get("temperature"),
                tools=kwargs.get("tools"),
            )
        else:
            response = await acompletion(**kwargs)
```

### Debug Logs Observed

**Good News:**
```
DEBUG | OpenRouter detected via OPENROUTER_API_KEY env var
DEBUG | OpenRouter mode: stripping usage params from kwargs
DEBUG | Using direct OpenAI client for OpenRouter (bypassing LiteLLM)
DEBUG | wrapped_acompletion: stripped params, calling with ['model', 'messages', 'max_tokens', 'temperature', 'api_key', 'api_base', 'tools', 'tool_choice']
```

**Bad News:**
```
ERROR | LLM call failed: litellm.APIError: APIError: OpenrouterException -
        AsyncCompletions.create() got an unexpected keyword argument 'usage'

ERROR | LLM call failed: Error code: 401 - {'error': {'message': 'Missing Authentication header', 'code': 401}}
```

---

## HYPOTHESIS

### Why 'usage' Parameter Error Persists

**Theory:** LiteLLM's `acompletion()` function has OpenRouter-specific logic that ADDS the `usage` parameter internally, regardless of what we pass to it.

**Evidence:**
- We strip `usage` from kwargs → still gets error
- We wrap `acompletion` to strip again → still gets error
- Error comes from INSIDE LiteLLM's OpenRouter handler

**Conclusion:** LiteLLM v1.x has a bug or "feature" where it forces `usage` param for OpenRouter calls.

---

### Why 401 Authentication Error

**Theory:** The direct OpenAI client approach is correct, but the API key isn't being passed correctly.

**Possible Causes:**
1. `os.getenv("OPENROUTER_API_KEY")` returns `None` in that scope
2. OpenAI client doesn't use `api_key` param correctly for non-OpenAI endpoints
3. Need to pass auth via headers instead of `api_key` param
4. OpenRouter requires different auth header format

**Evidence:**
- API key exists in config.json ✅
- API key set as env var ✅
- Using correct base_url ✅
- Still getting 401 ❌

---

## WHAT WE NEED

### Option A: Fix LiteLLM Integration
Find a way to make LiteLLM NOT add the `usage` parameter for OpenRouter calls.

**Possible approaches:**
1. Patch LiteLLM's OpenRouter handler
2. Use older LiteLLM version without this "feature"
3. Set specific LiteLLM config to disable usage tracking
4. Use LiteLLM's `force_timeout` or other params to bypass

---

### Option B: Fix Direct OpenAI Client
Make the direct OpenAI client approach work with proper authentication.

**Possible approaches:**
1. Pass API key via `Authorization` header explicitly
2. Use OpenRouter's specific client library (if exists)
3. Use `httpx` client directly instead of OpenAI SDK
4. Check if OpenRouter needs different auth format

---

### Option C: Alternative Router
Use a different routing library that doesn't have this issue.

**Candidates:**
- Direct OpenAI SDK (no router)
- httpx with manual endpoint handling
- requests library
- OpenRouter's official Python client (if exists)

---

## REQUESTED OUTPUT

Please provide:

1. **Root Cause Analysis** - Why is this happening?
2. **Recommended Solution** - Which option (A/B/C) is best?
3. **Implementation Plan** - Step-by-step code changes needed
4. **Code Example** - Working code snippet for OpenRouter calls
5. **Testing Strategy** - How to verify the fix works

---

## FILES TO REVIEW

```
/root/nanojaga/jagabot/providers/litellm_provider.py  ← Main provider code
/root/nanojaga/jagabot/providers/registry.py          ← Provider detection
/root/nanojaga/jagabot/agent/loop.py                  ← Where provider is called
/root/.jagabot/config.json                             ← API key config
```

---

## CONTACT

**Project:** AutoJaga - Autonomous Research Agent  
**Repository:** /root/nanojaga  
**Urgency:** CRITICAL (agent is completely blocked)

---

**End of Diagnostic Report**
