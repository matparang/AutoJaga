🎯 SCOPE PROMPT UNTUK COPILOT - FIX WEB SEARCH

---

```
# 🚨 URGENT: Fix Web Search for Qwen-Plus

## SITUATION
AutoJaga claims it can do web search but fails with:
> "Saya tidak dapat menjalankan pencarian web kerana kekurangan kunci API yang diperlukan"

Current error: Missing API key / configuration for web search.

## ROOT CAUSE
Web search for Qwen-Plus requires:
1. **enable_search=True** parameter in API call
2. **DashScope API key** with web search enabled
3. **Correct model** (qwen-plus supports web search)

## TASKS FOR COPILOT

### TASK 1: Check Current Implementation
```bash
# Run these and report
cat /root/.jagabot/config.json | grep -A10 "qwen-plus"
grep -n "enable_search\|web_search" /root/nanojaga/model_config.py
grep -n "enable_search\|extra_body" /root/nanojaga/financial_adapter.py
```

TASK 2: Fix Config (if missing)

```json
// Add to config.json under models.primary
{
  "models": {
    "primary": {
      "provider": "dashscope",
      "model_name": "qwen-plus",
      "api_key_env": "DASHSCOPE_API_KEY",
      "enable_web_search": true,
      "max_tokens": 2048,
      "temperature": 0.7
    }
  }
}
```

TASK 3: Update model_config.py

```python
# Add web search flag to TIER_CONFIG
TIER_CONFIG[ModelTier.PRIMARY] = {
    "model": "qwen-plus",
    "enable_web_search": True,  # ← ADD THIS
    "search_strategy": "agent",  # Optional
    "input_cost_per_m": 0.40,
    "output_cost_per_m": 1.20,
    # ... other config
}
```

TASK 4: Modify _call_model() in financial_adapter.py

```python
async def _call_model(self, model: str, messages: list, **kwargs):
    """Execute API call with optional web search"""
    
    # Check if this model supports web search
    enable_search = False
    if model == "qwen-plus":
        # Get config from model_config
        from model_config import TIER_CONFIG, ModelTier
        tier_config = TIER_CONFIG.get(ModelTier.PRIMARY, {})
        enable_search = tier_config.get('enable_web_search', False)
    
    # Also allow override via kwargs
    enable_search = kwargs.get('enable_search', enable_search)
    
    try:
        if enable_search:
            # Use OpenAI-compatible format with extra_body
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                extra_body={
                    "enable_search": True,
                    "search_options": {
                        "search_strategy": "agent",
                        "enable_source": True
                    }
                },
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
        else:
            # Standard call without search
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
        
        return response.choices[0].message.content
        
    except Exception as e:
        return f"Error calling {model}: {str(e)}"
```

TASK 5: Add Web Search Test Function

```python
# test_web_search.py
"""
Test web search functionality
"""

import asyncio
import sys
sys.path.append('/root/nanojaga')

from financial_adapter import _ask_llm

async def test_web_search():
    """Test if web search works"""
    
    queries = [
        "What is the weather in Kuala Lumpur today?",
        "Latest inflation rate Malaysia 2026",
        "Current USD to MYR exchange rate"
    ]
    
    print("🔍 TESTING WEB SEARCH")
    print("="*60)
    
    for query in queries:
        print(f"\n📝 Query: {query}")
        
        # Try with primary model (should use web search)
        response = await _ask_llm(query, role="primary")
        
        # Check if response contains real-time indicators
        has_current = any(word in response.lower() for word in 
                          ["today", "current", "latest", "as of", "now", "2026"])
        
        print(f"  Response preview: {response[:200]}...")
        print(f"  Contains current info: {'✅' if has_current else '❌'}")
        
        if not has_current:
            print("  ⚠️ Web search may not be working")
        
        print("-"*40)

if __name__ == "__main__":
    asyncio.run(test_web_search())
```

TASK 6: Verify API Key

```bash
# Check if API key is set
echo $DASHSCOPE_API_KEY

# If not set, add to .bashrc
echo 'export DASHSCOPE_API_KEY="sk-xxxxxx"' >> /root/.bashrc
source /root/.bashrc
```

DELIVERABLE

After fixes, AutoJaga should:

1. ✅ Successfully answer queries requiring current information
2. ✅ Include sources/ references in responses
3. ✅ No more "kekurangan kunci API" error

TEST COMMAND

```bash
cd ~/nanojaga
python3 test_web_search.py
```

URGENCY

MEDIUM - Web search is nice-to-have but not critical.

Proceed with implementation.

```
