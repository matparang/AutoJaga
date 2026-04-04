# JagaChatbot — Termux Install Guide

Run JagaChatbot locally on your Android phone using DeepSeek R1 1.5B.  
No API keys. No internet required after setup. Fully offline.

---

## Prerequisites

Before running `install.sh`, make sure you have:

1. **Termux** installed from F-Droid (not the Play Store version)
2. **Storage access** granted: run `termux-setup-storage` in Termux
3. **Ollama** installed:
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```
4. **AutoJaga repo** cloned to your Termux home:
   ```bash
   cd ~ && git clone https://github.com/matparang/AutoJaga.git
   ```

---

## Quick Install (3 commands)

```bash
cd ~/AutoJaga
bash Termux_deploy/scripts/install.sh
bash Termux_deploy/scripts/check_health.sh
```

If all health checks pass, launch with:

```bash
bash Termux_deploy/scripts/start.sh
```

---

## Manual Install (step by step)

Follow this if `install.sh` fails at any step.

### Step 1 — Update Termux packages

```bash
pkg update -y && pkg upgrade -y
pkg install -y python git curl
```

### Step 2 — Install binary packages via pkg

These packages **cannot** be installed via pip on Android because they require Rust or C compilation. The Termux package manager provides pre-compiled binaries:

```bash
pkg install -y python-aiohttp
pkg install -y python-cryptography
```

### Step 3 — Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Verify:

```bash
ollama --version
```

### Step 4 — Pull the model

This downloads approximately 1 GB. Use Wi-Fi.

```bash
ollama pull deepseek-r1:1.5b
```

Verify:

```bash
ollama list
# Should show: deepseek-r1:1.5b
```

### Step 5 — Create virtual environment

```bash
cd ~/AutoJaga/JagaChatbot
python -m venv venv --without-pip
curl -sS https://bootstrap.pypa.io/get-pip.py | venv/bin/python
source venv/bin/activate
pip install --upgrade pip
```

### Step 6 — Install Python dependencies

```bash
pip install -r ~/AutoJaga/Termux_deploy/requirements-termux.txt
```

### Step 7 — Run health check

```bash
bash ~/AutoJaga/Termux_deploy/scripts/check_health.sh
```

---

## Troubleshooting

### ❌ `pip install litellm` fails with Rust/cargo errors

**Fix:** Pin litellm to a version before `fastuuid` was introduced:
```bash
pip install "litellm>=1.40.0,<1.82.7"
```

`fastuuid` only exists in the compromised litellm 1.82.7/1.82.8 releases (supply chain attack). Versions below 1.82.7 never require it. Do NOT use `--no-deps` — that strips litellm's required runtime dependencies and causes import errors.

---

### ❌ `import aiohttp` fails

**Fix:** Install via pkg, not pip:
```bash
pkg install python-aiohttp
```

---

### ❌ Ollama fails to start / "port already in use"

Ollama is already running. Check:
```bash
curl http://localhost:11434/api/tags
```

If that returns JSON, Ollama is running fine. `start.sh` already handles this case and won't double-start.

If the port is blocked by something else:
```bash
pkill ollama
ollama serve &
```

---

### ❌ "No API key configured" error

This means the `JAGACHATBOT_CONFIG` environment variable is not set, so JagaChatbot loaded its default config which has no API keys.

**Fix:** Always launch via `start.sh`, which sets `JAGACHATBOT_CONFIG` automatically:
```bash
bash ~/AutoJaga/Termux_deploy/scripts/start.sh
```

Do **not** run `python -m jagachatbot` directly without the env var.

---

### ❌ Model responses are very slow

DeepSeek R1 1.5B on a phone CPU is slow by design — expect 5–30 seconds per response depending on your phone. This is normal. The model runs entirely on-device.

Tips:
- Close other apps to free RAM
- Keep the phone plugged in (prevents thermal throttling)
- Shorter prompts get faster responses

---

## FAQ

### Can I use a different model?

Yes. Pull any Ollama-compatible model:

```bash
ollama pull llama3.2:1b      # Even smaller, faster
ollama pull phi3:mini         # Microsoft's small model
```

Then edit `Termux_deploy/config/termux_config.json`:
```json
"model": "ollama/llama3.2:1b"
```

### What if Ollama crashes mid-conversation?

`start.sh` will automatically restart it on next launch. Your conversation history is preserved in `~/.jagachatbot/`. Just re-run `start.sh`.

### Can I use a cloud API key instead of Ollama?

Yes — JagaChatbot is model-agnostic. Create a different config file or set env vars:

```bash
OPENAI_API_KEY=sk-... python -m jagachatbot
```

Or edit `termux_config.json` to use `openai/gpt-4o-mini` and add your key.

### Does this use any data or phone plan?

After the initial setup (model download), JagaChatbot runs 100% offline. No data is sent anywhere. All inference runs on your device.

### How much RAM does it need?

DeepSeek R1 1.5B uses approximately 1.5–2 GB of RAM during inference. Phones with 4 GB+ RAM should be fine. Close other apps if you experience crashes.
