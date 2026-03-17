🎯 SCOPE PROMPT UNTUK COPILOT - QWEN 2.5 API SETUP

---

```
# 🚀 TASK: Configure Qwen 2.5 Flash API in AutoJaga config.json

## SITUATION
AutoJaga currently uses DeepSeek as the LLM provider. We want to add Qwen 2.5 Flash as an alternative/backup provider.

## REQUIREMENTS

### 1. API CREDENTIALS
Need to obtain from Alibaba Cloud/DashScope:
- API Key
- Endpoint URL
- Model name (qwen2.5-flash)

### 2. CONFIG.JSON STRUCTURE
Current config.json location: `/root/.jagabot/config.json`

Add Qwen configuration alongside existing DeepSeek:

```json
{
  "workspace": "~/.jagabot/workspace",
  "model": "deepseek/deepseek-chat",  // default model
  "providers": {
    "deepseek": {
      "api_key": "${DEEPSEEK_API_KEY}",
      "base_url": "https://api.deepseek.com",
      "models": ["deepseek-chat", "deepseek-coder"]
    },
    "qwen": {
      "api_key": "${QWEN_API_KEY}",
      "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
      "models": ["qwen2.5-flash", "qwen2.5-7b", "qwen2.5-14b", "qwen2.5-72b"],
      "default_model": "qwen2.5-flash"
    }
  },
  "maxTokens": 8192,
  "temperature": 0.7,
  "maxToolIterations": 20,
  "memoryWindow": 50,
  "restrictToWorkspace": true
}
```

3. ENVIRONMENT VARIABLES

Add to /root/.bashrc or AutoJaga's env:

```bash
export QWEN_API_KEY="your-api-key-here"
```

4. TESTING THE CONFIGURATION

Need to verify Qwen works with:

```python
# Test Qwen connection
from jagabot.llm import get_llm

qwen_llm = get_llm(provider="qwen", model="qwen2.5-flash")
response = qwen_llm.chat("Hello, are you working?")
print(response)
```

SPECIFICATIONS

Qwen 2.5 Flash Details

· Provider: Alibaba Cloud / DashScope
· Model: qwen2.5-flash (fast, cost-effective)
· Context Length: 128K tokens (or 1M for some variants)
· API Endpoint: https://dashscope.aliyuncs.com/compatible-mode/v1
· Authentication: Bearer token with API Key
· Pricing: ~$0.14/1M tokens (similar to DeepSeek)

API Format (OpenAI-compatible)

```python
import requests

response = requests.post(
    "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json"
    },
    json={
        "model": "qwen2.5-flash",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 512
    }
)
```

TASKS FOR COPILOT

TASK 1: Update config.json

· Add Qwen provider section
· Maintain existing DeepSeek configuration
· Use environment variables for API keys (never hardcode)

TASK 2: Update LLM router/loader

Check /root/nanojaga/jagabot/llm/__init__.py or similar and ensure it can handle multiple providers.

TASK 3: Add fallback mechanism

If Qwen fails, should fallback to DeepSeek automatically.

TASK 4: Testing script

Provide a test script to verify Qwen works:

```python
# test_qwen.py
import os
import json
from jagabot.llm import LLMRouter

def test_qwen():
    router = LLMRouter()
    
    # Test Qwen
    response = router.chat(
        provider="qwen",
        model="qwen2.5-flash",
        messages=[{"role": "user", "content": "Say 'Qwen is working' in Malay"}]
    )
    
    print(f"Qwen response: {response}")
    
    # Test fallback
    response = router.chat(
        provider="invalid",
        messages=[{"role": "user", "content": "Should use default"}]
    )
    
    print(f"Fallback response: {response}")

if __name__ == "__main__":
    test_qwen()
```

EXPECTED OUTPUT

After implementation:

1. ✅ config.json updated with Qwen configuration
2. ✅ Environment variable QWEN_API_KEY set
3. ✅ LLM router can switch between DeepSeek and Qwen
4. ✅ AutoJaga can use Qwen as primary or fallback

VERIFICATION STEPS

```bash
# 1. Check config.json
cat /root/.jagabot/config.json | grep -A10 qwen

# 2. Test Qwen directly
curl -X POST https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions \
  -H "Authorization: Bearer $QWEN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5-flash",
    "messages": [{"role": "user", "content": "Hello"}]
  }'

# 3. Test through AutoJaga
python3 test_qwen.py
```

URGENCY

MEDIUM - Adding alternative provider untuk redundancy dan cost optimization.

Proceed with Qwen 2.5 Flash configuration.

```
