# 🚀 INSTALL QWEN2.5-CODER:7B

**Best local model for code generation with instruction following**

---

## ⚡ QUICK INSTALL (5 minutes)

### Step 1: Install Ollama

```bash
# Download and install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Verify installation
ollama --version
```

### Step 2: Pull Qwen2.5-Coder:7B

```bash
# Pull the model (4.7GB download)
ollama pull qwen2.5-coder:7b

# Verify it's installed
ollama list
# Should show: qwen2.5-coder:7b
```

### Step 3: Start Ollama Server

```bash
# Start server (runs in background)
ollama serve &

# Or as a service (systemd)
sudo systemctl start ollama
sudo systemctl enable ollama
```

### Step 4: Test Model

```bash
# Quick test
ollama run qwen2.5-coder:7b "print hello world in python"
```

Expected output:
```python
print("Hello, World!")
```

---

## 🧪 TEST WITH OUR CODE

```bash
cd /root/nanojaga
source .venv/bin/activate

# Make sure Ollama is running
ollama serve &

# Test Qwen2.5-Coder client
python3 qwen25_coder_client.py
```

Expected output:
```
=== GENERATED CODE ===
from sklearn.ensemble import RandomForestClassifier
model = RandomForestClassifier(n_estimators=100)
...

=== VALIDATION ===
Has RandomForest: True ✅
Has LogisticRegression: False ✅

✅ SUCCESS - Model follows instructions!
```

---

## 🔧 INTEGRATION WITH COPAW

### Update orchestrator_v3.py

Replace `QwenClient` with `Qwen25CoderClient`:

```python
# orchestrator_v3.py

from qwen25_coder_client import Qwen25CoderClient

class CoPawOrchestratorV3:
    async def run_experiment(self, topic: str, max_cycles: int = 3):
        async with AutoJagaClient(self.autojaga_url) as autojaga, \
                   Qwen25CoderClient() as qwen:  # ← Changed!
            
            # ... rest of code stays the same
```

### Benefits

| Aspect | Qwen CLI | Qwen2.5-Coder:7B |
|--------|----------|------------------|
| **Instruction Following** | ❌ Poor | ✅ Excellent |
| **Code Quality** | ⚠️ Basic | ✅ High |
| **Local** | ✅ Yes | ✅ Yes |
| **Free** | ✅ Yes | ✅ Yes |
| **RAM Usage** | ~2GB | ~8GB |
| **Speed** | Fast | Medium |

---

## 📊 SYSTEM REQUIREMENTS

### Minimum

- **RAM:** 16GB (8GB for model + 8GB for system)
- **Storage:** 10GB free space
- **CPU:** Any modern x86_64 or ARM64

### Recommended

- **RAM:** 32GB
- **Storage:** 20GB SSD
- **GPU:** Optional (NVIDIA for faster inference)

---

## 🛠️ TROUBLESHOOTING

### Problem: "Model not found"

```bash
# Pull the model again
ollama pull qwen2.5-coder:7b

# Verify
ollama list | grep qwen
```

### Problem: "Connection refused"

```bash
# Check if Ollama is running
ps aux | grep ollama

# Start server
ollama serve

# Or restart service
sudo systemctl restart ollama
```

### Problem: "Out of memory"

```bash
# Use smaller model (3B instead of 7B)
ollama pull qwen2.5-coder:3b

# Update client to use smaller model
client = Qwen25CoderClient(model="qwen2.5-coder:3b")
```

### Problem: Slow generation

```bash
# If you have NVIDIA GPU, enable GPU acceleration
# Ollama auto-detects GPU, but you can force it:

export OLLAMA_NUM_GPU=1
ollama serve
```

---

## 📈 PERFORMANCE EXPECTATIONS

### Generation Speed

| Model | Tokens/sec | Time for 500 tokens |
|-------|------------|---------------------|
| **qwen2.5-coder:7b** (CPU) | ~10 tok/s | ~50s |
| **qwen2.5-coder:7b** (GPU) | ~50 tok/s | ~10s |
| **qwen2.5-coder:3b** (CPU) | ~20 tok/s | ~25s |

### RAM Usage

| Model | RAM Usage |
|-------|-----------|
| qwen2.5-coder:7b | ~8GB |
| qwen2.5-coder:3b | ~4GB |
| qwen2.5-coder:1.5b | ~2GB |

---

## 🎯 ALTERNATIVE MODELS

If Qwen2.5-Coder:7B doesn't work for you:

### Smaller (Less RAM)

```bash
# 1.5B - Fits in 4GB RAM
ollama pull qwen2.5-coder:1.5b

# 3B - Fits in 8GB RAM
ollama pull qwen2.5-coder:3b
```

### Larger (Better Quality)

```bash
# 14B - Needs 32GB RAM
ollama pull qwen2.5-coder:14b

# 32B - Needs 64GB RAM
ollama pull qwen2.5-coder:32b
```

### Other Code Models

```bash
# DeepSeek-Coder (excellent for Python)
ollama pull deepseek-coder:6.7b

# StarCoder2 (good all-rounder)
ollama pull starcoder2:7b

# CodeLlama (Meta's code model)
ollama pull codellama:7b
```

---

## ✅ VERIFICATION CHECKLIST

After installation, verify:

- [ ] Ollama installed: `ollama --version`
- [ ] Model pulled: `ollama list | grep qwen2.5-coder`
- [ ] Server running: `curl http://localhost:11434/api/tags`
- [ ] Model responds: `ollama run qwen2.5-coder:7b "1+1"`
- [ ] Python client works: `python3 qwen25_coder_client.py`

---

## 📚 RESOURCES

- **Ollama Docs:** https://ollama.ai/docs
- **Qwen2.5-Coder:** https://huggingface.co/Qwen/Qwen2.5-Coder-7B
- **Model Card:** https://ollama.ai/library/qwen2.5-coder

---

**Status:** ✅ **READY TO INSTALL**  
**Estimated Time:** 5-10 minutes  
**Download Size:** 4.7GB  
**RAM Required:** 8GB minimum
