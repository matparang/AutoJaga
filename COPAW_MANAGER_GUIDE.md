# 🎯 COPAW SERVICE MANAGER

**Unified CLI for managing all CoPaw services**

---

## ⚡ QUICK START

### Interactive Mode (Recommended)

```bash
cd /root/nanojaga
./copaw.sh
# or
python3 copaw_manager.py
```

You'll see:
```
🎯 CoPaw Service Manager - Interactive Mode
Type 'help' for commands, 'quit' to exit

copaw>
```

### Command Line Mode

```bash
# Start all services
./copaw.sh start

# Stop all services
./copaw.sh stop

# Check status
./copaw.sh status

# View logs
./copaw.sh logs

# View specific service logs
./copaw.sh logs qwen_service
```

---

## 📋 INTERACTIVE COMMANDS

| Command | Description |
|---------|-------------|
| `start` | Start all services |
| `stop` | Stop all services |
| `status` | Show detailed status |
| `health` | Quick health check |
| `logs [service]` | Show logs (all or specific) |
| `start <service>` | Start specific service |
| `stop <service>` | Stop specific service |
| `help` | Show help message |
| `quit` / `exit` | Exit interactive mode |

---

## 🧪 EXAMPLE SESSION

```bash
$ ./copaw.sh

🎯 CoPaw Service Manager - Interactive Mode
Type 'help' for commands, 'quit' to exit

copaw> start

🚀 Starting CoPaw Services

✅ Using virtual environment
✅ Started AutoJaga API (PID: 12345)
✅ Started Qwen Service v2 (PID: 12346)
✅ Started Ollama Server (PID: 12347)

⏳ Waiting for services to initialize...

🏥 Service Health Check

✅ autojaga_api         [HEALTHY   ] Port 8000
✅ qwen_service         [HEALTHY   ] Port 8082
✅ ollama               [HEALTHY   ] Port 11434

copaw> status

📊 CoPaw Services Status

Service              Status     Port   PID      Uptime
------------------------------------------------------------
autojaga_api         healthy       8000 12345    2m 15s
qwen_service         healthy       8082 12346    2m 13s
ollama               healthy      11434 12347    2m 11s

copaw> logs qwen_service

📜 qwen_service Logs (last 30 lines)

2026-03-15 02:50:00,123 | INFO | Starting Qwen Code Generator v2...
2026-03-15 02:50:00,456 | INFO | API docs: http://localhost:8082/docs
INFO:     Started server process [12346]
INFO:     127.0.0.1:54321 - "GET /health HTTP/1.1" 200 OK

copaw> health

🏥 Service Health Check

✅ autojaga_api         [HEALTHY   ] Port 8000
✅ qwen_service         [HEALTHY   ] Port 8082
✅ ollama               [HEALTHY   ] Port 11434

copaw> quit
```

---

## 🛠️ FEATURES

### 1. Service Management

- ✅ Start/stop all services with one command
- ✅ Start/stop individual services
- ✅ Automatic PID tracking
- ✅ Graceful shutdown (SIGTERM → SIGKILL)

### 2. Health Monitoring

- ✅ HTTP health checks for each service
- ✅ Real-time status updates
- ✅ Automatic port detection
- ✅ Uptime tracking

### 3. Log Management

- ✅ Centralized log storage (`/root/.jagabot/logs/`)
- ✅ View last N lines from any service
- ✅ Auto-rotating logs
- ✅ Color-coded output

### 4. Virtual Environment

- ✅ Auto-detects `.venv`
- ✅ Activates venv automatically
- ✅ Falls back to system Python if needed

---

## 📁 FILE STRUCTURE

```
/root/nanojaga/
├── copaw_manager.py          # Main manager script
├── copaw.sh                  # Quick start wrapper
└── /root/.jagabot/logs/      # Log directory
    ├── autojaga_api.log
    ├── qwen_service.log
    └── ollama.log
```

---

## 🔧 TROUBLESHOOTING

### Problem: "Permission denied"

```bash
# Make scripts executable
chmod +x copaw_manager.py copaw.sh
```

### Problem: "Service won't start"

```bash
# Check if port is already in use
ss -tlnp | grep 8000  # AutoJaga
ss -tlnp | grep 8082  # Qwen Service
ss -tlnp | grep 11434 # Ollama

# Kill existing process
pkill -f jagabot.api.server
pkill -f qwen_service_v2
pkill -f ollama

# Try starting again
./copaw.sh start
```

### Problem: "Virtual environment not found"

```bash
# Create venv if it doesn't exist
cd /root/nanojaga
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn aiohttp pydantic
```

### Problem: "Ollama not found"

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull model
ollama pull qwen2.5-coder:7b
```

---

## 📊 SERVICE DETAILS

| Service | Port | Purpose | Log File |
|---------|------|---------|----------|
| **AutoJaga API** | 8000 | Planning & Analysis | `autojaga_api.log` |
| **Qwen Service v2** | 8082 | Code Generation | `qwen_service.log` |
| **Ollama Server** | 11434 | Model Server | `ollama.log` |

---

## 🎯 COMMON WORKFLOWS

### Morning Startup

```bash
cd /root/nanojaga
./copaw.sh start
./copaw.sh health
```

### Debugging Issue

```bash
./copaw.sh status
./copaw.sh logs qwen_service
./copaw.sh stop qwen_service
./copaw.sh start qwen_service
```

### Evening Shutdown

```bash
./copaw.sh stop
./copaw.sh status  # Verify all stopped
```

### Quick Check

```bash
# One-liner to check if everything is running
./copaw.sh status | grep healthy
```

---

## 🚀 ADVANCED USAGE

### Start Specific Service

```bash
copaw> start autojaga_api
```

### View All Logs

```bash
copaw> logs
```

### View Specific Service Logs

```bash
copaw> logs ollama
copaw> logs qwen_service
copaw> logs autojaga_api
```

### Script Mode (Non-Interactive)

```bash
# In scripts or cron
/root/nanojaga/copaw.sh start
sleep 10
/root/nanojaga/copaw.sh health
```

---

## 📝 CONFIGURATION

### Change Log Location

Edit `copaw_manager.py`, line ~100:
```python
log_dir = Path("/root/.jagabot/logs")  # Change this
```

### Add New Service

Edit `copaw_manager.py`, `__init__` method:
```python
self.services["new_service"] = Service(
    name="New Service",
    command=["python3", "new_service.py"],
    port=9999,
    health_endpoint="/health"
)
```

### Change Health Check Timeout

Edit `Service.check_health()` method:
```python
with urllib.request.urlopen(url, timeout=5) as resp:  # Change timeout
```

---

## 🏁 BEST PRACTICES

1. **Always use `./copaw.sh`** - Ensures venv is activated
2. **Check status before debugging** - `./copaw.sh status`
3. **View logs before restarting** - `./copaw.sh logs <service>`
4. **Stop services properly** - Use `stop` command, not `kill`
5. **Check health after starting** - Wait 5 seconds, then `./copaw.sh health`

---

## 📚 RELATED DOCUMENTATION

- **Quick Start:** `/root/nanojaga/COPAW_QUICKSTART.md`
- **Ensemble Fix:** `/root/nanojaga/ENSEMBLE_FIX_COMPLETE.md`
- **Model Upgrade:** `/root/nanojaga/INSTALL_QWEN25_CODER.md`
- **Final Status:** `/root/nanojaga/COPAW_FINAL_COMPLETE.md`

---

**Created:** March 15, 2026  
**Version:** 1.0.0  
**Status:** ✅ **READY TO USE**
