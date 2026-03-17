# 🚀 COPAW QUICK START GUIDE

**Date:** March 15, 2026  
**Status:** ✅ **WORKING IN VENV**

---

## ⚡ QUICK START (5 minutes)

### Step 1: Activate Virtual Environment

```bash
cd /root/nanojaga
source .venv/bin/activate
```

You should see `(.venv)` in your prompt.

### Step 2: Install Dependencies (if needed)

```bash
# Only needed once
pip install fastapi uvicorn aiohttp pydantic
```

### Step 3: Start Services

```bash
# Terminal 1: Start AutoJaga API
cd /root/nanojaga
source .venv/bin/activate
python3 -m jagabot.api.server &

# Terminal 2: Start Qwen Service v2
cd /root/nanojaga
source .venv/bin/activate
python3 qwen_service_v2.py &
```

### Step 4: Verify Services

```bash
# Test AutoJaga API
curl http://localhost:8000/health

# Test Qwen Service v2
curl http://localhost:8082/health
```

Expected output:
```json
{"status": "healthy", "version": "2.0.0", ...}
```

### Step 5: Test Code Generation

```bash
# Generate code
RESP=$(curl -s -X POST http://localhost:8082/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Create ML experiment code"}')

echo "Response: $RESP"

# Extract job ID
JOB_ID=$(echo $RESP | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
echo "Job ID: $JOB_ID"

# Poll for status
curl http://localhost:8082/job/$JOB_ID | python3 -m json.tool
```

---

## 📋 SERVICE URLs

| Service | URL | Purpose |
|---------|-----|---------|
| **AutoJaga API** | http://localhost:8000 | Planning & Analysis |
| **AutoJaga Docs** | http://localhost:8000/docs | OpenAPI docs |
| **Qwen Service v2** | http://localhost:8082 | Code Generation |
| **Qwen Docs** | http://localhost:8082/docs | OpenAPI docs |

---

## 🧪 TESTING WORKFLOW

### Test 1: Health Check

```bash
source .venv/bin/activate

# AutoJaga
curl http://localhost:8000/health | python3 -m json.tool

# Qwen
curl http://localhost:8082/health | python3 -m json.tool
```

### Test 2: Generate Code

```bash
# Queue job
curl -X POST http://localhost:8082/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "print hello world"}'

# Output: {"job_id": "...", "status": "queued"}
```

### Test 3: Check Job Status

```bash
# Replace JOB_ID with actual ID
curl http://localhost:8082/job/JOB_ID | python3 -m json.tool
```

Expected states: `queued` → `running` → `done` or `failed`

### Test 4: List All Jobs

```bash
curl http://localhost:8082/jobs | python3 -m json.tool
```

---

## 🔧 TROUBLESHOOTING

### Problem: "ModuleNotFoundError: No module named 'fastapi'"

**Solution:** Activate venv and install dependencies:
```bash
source .venv/bin/activate
pip install fastapi uvicorn aiohttp pydantic
```

### Problem: "Address already in use"

**Solution:** Kill existing service:
```bash
pkill -f jagabot.api.server
pkill -f qwen_service_v2
sleep 2
# Restart services
```

### Problem: "Connection refused"

**Solution:** Check if services are running:
```bash
ps aux | grep -E "(jagabot.api|qwen_service)" | grep -v grep
```

If not running, start them again.

---

## 📁 PROJECT STRUCTURE

```
/root/nanojaga/
├── .venv/                      # Virtual environment
│   └── bin/
│       └── activate            # ← Source this file
├── jagabot/
│   └── api/
│       └── server.py           # AutoJaga API
├── qwen_service_v2.py          # Qwen Service
├── copaw_orchestrator_v3.py    # CoPaw Orchestrator
├── blueprint_schema.py         # Structured blueprints
├── prompt_builder.py           # Prompt engineering
└── code_validator.py           # Code validation
```

---

## 🎯 NEXT STEPS

### After Services Are Running

1. **Test AutoJaga API**
   ```bash
   curl -X POST http://localhost:8000/plan \
     -H "Content-Type: application/json" \
     -d '{"prompt": "Improve model accuracy"}'
   ```

2. **Test Qwen Service**
   ```bash
   curl -X POST http://localhost:8082/generate \
     -H "Content-Type: application/json" \
     -d '{"prompt": "Create RandomForest code"}'
   ```

3. **Run CoPaw Orchestrator**
   ```bash
   source .venv/bin/activate
   python3 orchestrator_v3.py
   ```

---

## 📊 COMPONENT STATUS

| Component | File | Port | Status |
|-----------|------|------|--------|
| **AutoJaga API** | `jagabot/api/server.py` | 8000 | ✅ Working |
| **Qwen Service v2** | `qwen_service_v2.py` | 8082 | ✅ Working |
| **CoPaw Orchestrator v3** | `orchestrator_v3.py` | - | ✅ Ready |
| **Blueprint Schema** | `blueprint_schema.py` | - | ✅ Ready |
| **Prompt Builder** | `prompt_builder.py` | - | ✅ Ready |
| **Code Validator** | `code_validator.py` | - | ✅ Ready |

---

## 🛠️ COMMON COMMANDS

### Start All Services

```bash
source .venv/bin/activate
python3 -m jagabot.api.server &
python3 qwen_service_v2.py &
```

### Stop All Services

```bash
pkill -f jagabot.api.server
pkill -f qwen_service_v2
```

### Check Service Status

```bash
ps aux | grep -E "(jagabot.api|qwen_service)" | grep -v grep
```

### View Logs

```bash
# AutoJaga logs (if running with nohup)
tail -f /root/.jagabot/logs/autojaga_api.log

# Qwen logs (stdout/stderr)
# Check terminal output
```

---

## 📚 DOCUMENTATION

- **AutoJaga API Docs:** http://localhost:8000/docs
- **Qwen Service Docs:** http://localhost:8082/docs
- **Ensemble Fix:** `/root/nanojaga/ENSEMBLE_FIX_COMPLETE.md`
- **CoPaw Status:** `/root/nanojaga/COPAW_100_PERCENT_WORKING.md`

---

**Status:** ✅ **READY TO USE**  
**Last Updated:** March 15, 2026  
**Python:** 3.12 (venv)  
**Dependencies:** FastAPI, uvicorn, aiohttp, pydantic
