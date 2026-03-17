# 🎯 COPAW MANAGER V2 - ENHANCED CLI

**Now with direct service communication, experiment running, and API calls!**

---

## 🚀 NEW COMMANDS

### Communication Commands 💬

```bash
copaw> talk autojaga "What is VIX?"
📤 Sending to AutoJaga: What is VIX?
✅ Response: { ... }

copaw> talk qwen "Generate hello world in Python"
📤 Sending to Qwen: Generate hello world in Python
✅ Job queued: abc123
⏳ Waiting for result...
✅ Done!
print("Hello, World!")

copaw> talk copaw "Run experiment"
⚠️  CoPaw orchestrator command: Run experiment
   (Full orchestrator integration coming soon)
```

### Experiment Commands 🧪

```bash
copaw> experiment 1 RandomForestClassifier
🧪 Running 1 experiment cycle(s) with RandomForestClassifier
✅ Blueprint created:
{
  "experiment_id": "EXP-456",
  "algorithm": {
    "name": "RandomForestClassifier",
    "import": "from sklearn.ensemble import RandomForestClassifier",
    "forbidden": ["LogisticRegression"]
  },
  ...
}

copaw> plan Improve model accuracy with ensemble methods
📤 Sending to AutoJaga: Improve model accuracy...
✅ Blueprint:
{
  "status": "success",
  "blueprint": "...",
  ...
}

copaw> code Generate RandomForest code with n_estimators=100
📤 Sending to Qwen: Generate RandomForest code...
✅ Job queued: xyz789
⏳ Generating code...
✅ Code generated!
from sklearn.ensemble import RandomForestClassifier
model = RandomForestClassifier(n_estimators=100)
...

copaw> validate /path/to/code.py
📄 Validating: /path/to/code.py
✅ Validation PASSED

# Or if validation fails:
❌ Validation FAILED
  ❌ Required algorithm 'RandomForestClassifier' NOT found
  ❌ Forbidden algorithm 'LogisticRegression' FOUND
```

### API Commands 🔌

```bash
copaw> services

📋 Available Services

AutoJaga API
  URL: http://localhost:8000
  Endpoints:
    GET  /health          - Health check
    POST /plan            - Create experiment blueprint
    POST /analyze         - Analyze results
    POST /tools/execute   - Execute tool
    GET  /tools           - List tools

Qwen Service v2
  URL: http://localhost:8082
  Endpoints:
    GET  /health          - Health check
    POST /generate        - Generate code (async)
    GET  /job/{id}        - Get job status
    GET  /jobs            - List all jobs
    DELETE /job/{id}      - Delete job

Ollama Server
  URL: http://localhost:11434
  Endpoints:
    GET  /api/tags        - List models
    POST /api/generate    - Generate with model
    POST /api/chat        - Chat with model

copaw> api autojaga /health ''
📤 Calling autojaga /health
✅ Response:
{
  "status": "healthy",
  "version": "5.0.0",
  ...
}

copaw> api qwen /jobs ''
📤 Calling qwen /jobs
✅ Response:
{
  "jobs": [...],
  "count": 5,
  ...
}
```

---

## 📋 ALL COMMANDS

### Basic Service Management

| Command | Description |
|---------|-------------|
| `start` | Start all services |
| `stop` | Stop all services |
| `status` | Show detailed status |
| `health` | Quick health check |
| `logs [service]` | Show logs |
| `start <service>` | Start specific service |
| `stop <service>` | Stop specific service |

### Communication (NEW!)

| Command | Description |
|---------|-------------|
| `talk autojaga "<msg>"` | Send message to AutoJaga |
| `talk qwen "<msg>"` | Send prompt to Qwen |
| `talk copaw "<msg>"` | Send command to CoPaw |

### Experiments (NEW!)

| Command | Description |
|---------|-------------|
| `experiment <n> [algo]` | Run experiment cycle |
| `plan <prompt>` | Get blueprint from AutoJaga |
| `code <blueprint>` | Generate code from Qwen |
| `validate <file>` | Validate code |

### API Access (NEW!)

| Command | Description |
|---------|-------------|
| `services` | List all services & APIs |
| `api <svc> <endpoint> <data>` | Direct API call |

---

## 🧪 EXAMPLE SESSION

```bash
$ ./copaw.sh

🎯 CoPaw Service Manager - Interactive Mode
Type 'help' for commands, 'quit' to exit

copaw> status

📊 CoPaw Services Status

Service              Status     Port   PID      Uptime
------------------------------------------------------------
autojaga_api         healthy       8000 12345    2m 15s
qwen_service         healthy       8082 12346    2m 13s
ollama               healthy      11434 12347    2m 11s

copaw> talk autojaga "What is VIX?"

📤 Sending to AutoJaga: What is VIX?
✅ Response:
{
  "status": "success",
  "blueprint": "VIX (Volatility Index) is...",
  "session_id": "session_123"
}

copaw> plan Improve logistic regression accuracy

📤 Sending to AutoJaga: Improve logistic regression accuracy
✅ Blueprint:
{
  "status": "success",
  "blueprint": "Try ensemble methods...",
  ...
}

copaw> code Generate RandomForest code

📤 Sending to Qwen: Generate RandomForest code
✅ Job queued: abc123
⏳ Generating code...
✅ Code generated!
from sklearn.ensemble import RandomForestClassifier
model = RandomForestClassifier(n_estimators=100)
...

copaw> validate /tmp/test.py

📄 Validating: /tmp/test.py
✅ Validation PASSED

copaw> services

📋 Available Services

AutoJaga API
  URL: http://localhost:8000
  Endpoints:
    GET  /health          - Health check
    POST /plan            - Create experiment blueprint
    ...

copaw> api autojaga /tools ''

📤 Calling autojaga /tools
✅ Response:
{
  "tools": [...],
  "count": 45
}

copaw> quit
```

---

## 🔧 QUICK REFERENCE

### Talk to Services

```bash
# Ask AutoJaga a question
talk autojaga "Explain Monte Carlo simulation"

# Ask Qwen to generate code
talk qwen "Create ML model with RandomForest"

# Test CoPaw orchestrator
talk copaw "Run experiment cycle"
```

### Run Experiments

```bash
# Run 1 cycle with default algorithm
experiment 1

# Run 3 cycles with specific algorithm
experiment 3 XGBClassifier

# Get blueprint only
plan Improve model accuracy

# Generate code only
code Create RandomForest with n_estimators=100

# Validate generated code
validate /path/to/code.py
```

### Direct API Access

```bash
# List services
services

# Call AutoJaga health endpoint
api autojaga /health ''

# Call Qwen jobs endpoint
api qwen /jobs ''

# Call with POST data
api autojaga /plan '{"prompt": "test"}'
```

---

## 📊 WORKFLOWS

### Morning Startup + Quick Test

```bash
copaw> start
copaw> health
copaw> talk autojaga "Good morning! What's the market outlook?"
```

### Debug Code Generation Issue

```bash
copaw> logs qwen_service
copaw> code Generate RandomForest code
copaw> validate /tmp/generated.py
copaw> api qwen /jobs ''
```

### Run Full Experiment

```bash
copaw> start
copaw> health
copaw> experiment 3 RandomForestClassifier
copaw> plan Improve accuracy beyond 0.85
copaw> code Use the blueprint
copaw> validate /path/to/code.py
```

### API Exploration

```bash
copaw> services
copaw> api autojaga /tools ''
copaw> api autojaga /health ''
copaw> api qwen /health ''
```

---

## 🎯 BEST PRACTICES

1. **Use `talk` for quick tests** - Faster than full experiment
2. **Validate before running** - Always `validate` generated code
3. **Check services first** - `services` shows available endpoints
4. **Use `api` for debugging** - Direct API access for troubleshooting
5. **Start with `plan`** - Get blueprint before generating code

---

## 📚 RELATED DOCUMENTATION

| Document | Purpose |
|----------|---------|
| `COPAW_MANAGER_GUIDE.md` | Original guide |
| `COPAW_MANAGER_COMPLETE.md` | V1 summary |
| `ENSEMBLE_FIX_COMPLETE.md` | 3-layer solution |
| `INSTALL_QWEN25_CODER.md` | Model installation |

---

## 🏁 CONCLUSION

**CoPaw Manager V2** now includes:
- ✅ Service management (start/stop/status)
- ✅ Health monitoring
- ✅ Log viewing
- ✅ **Direct service communication** (talk)
- ✅ **Experiment running** (experiment, plan, code, validate)
- ✅ **Direct API access** (services, api)

**All in one unified CLI!**

---

**Updated:** March 15, 2026  
**Version:** 2.0.0  
**Status:** ✅ **READY TO USE**
