# Termux Deploy — JagaChatbot on Android

> Run the same JagaChatbot architecture entirely on your Android phone  
> using a free local AI model. No subscription. No internet after setup.

---

## What This Folder Is

`Termux_deploy/` is a self-contained deployment package that lets you run JagaChatbot on Android using [Termux](https://termux.dev) and [Ollama](https://ollama.com).

It does **not** modify the main `JagaChatbot/` codebase. It overrides only the model configuration via the `JAGACHATBOT_CONFIG` environment variable — the only integration point between this folder and JagaChatbot.

---

## Why It Exists Separately

JagaChatbot's main codebase targets cloud APIs (OpenAI, Anthropic, DeepSeek Cloud). Android/Termux has specific constraints:

- Some Python packages with Rust dependencies can't be compiled on aarch64
- `uvloop` doesn't work on the Android kernel
- `aiohttp` and `cryptography` need pre-compiled Termux binaries
- Cloud APIs require internet and API keys

This folder solves all of that without touching the core code.

---

## The Teaching Narrative

> This demonstrates that AI architecture is **model-agnostic**.
>
> JagaChatbot was designed to route through LiteLLM, which supports dozens of providers through a unified interface. Swap the model string and the same conversation engine — the same memory system, the same context builder, the same compression logic — works whether you're calling a RM500/month cloud API or running a free local model on your phone in Termux.
>
> ```
> Cloud:  "model": "openai/gpt-4o"              → RM500+/month
> Phone:  "model": "ollama/deepseek-r1:1.5b"    → RM0/month, offline
> ```
>
> Same architecture. Same code. Different model string.

---

## Folder Structure

```
Termux_deploy/
├── config/
│   └── termux_config.json       ← Ollama model config (overrides default)
├── scripts/
│   ├── install.sh               ← Full installer (run once)
│   ├── start.sh                 ← One-tap launcher
│   └── check_health.sh          ← Verify everything is working
├── requirements-termux.txt      ← Termux-safe pip dependencies
├── .env.termux                  ← Environment variable template
├── TERMUX_INSTALL.md            ← Step-by-step install guide
└── README.md                    ← This file
```

---

## Quick Start

```bash
# 1. Clone the repo (if you haven't already)
cd ~ && git clone https://github.com/matparang/AutoJaga.git

# 2. Run the installer
bash ~/AutoJaga/Termux_deploy/scripts/install.sh

# 3. Verify everything works
bash ~/AutoJaga/Termux_deploy/scripts/check_health.sh

# 4. Launch
bash ~/AutoJaga/Termux_deploy/scripts/start.sh
```

For detailed instructions and troubleshooting, see [TERMUX_INSTALL.md](./TERMUX_INSTALL.md).

---

## How the Config Override Works

JagaChatbot reads `~/.jagachatbot/config.json` by default. This deployment sets:

```bash
JAGACHATBOT_CONFIG=/path/to/Termux_deploy/config/termux_config.json
```

That single env var redirects config loading to the Termux-specific config which points at local Ollama instead of cloud APIs. No code changes in JagaChatbot needed — just an environment variable.

---

## Model: DeepSeek R1 1.5B via Ollama

| Property | Value |
|---|---|
| Model | `deepseek-r1:1.5b` |
| Size | ~1 GB download |
| RAM usage | ~1.5–2 GB |
| Inference speed | 5–30 sec/response (CPU-only) |
| Internet required | Only for initial download |
| Cost | Free |

---

## Links

- [JagaChatbot README](../JagaChatbot/README.md)
- [TERMUX_INSTALL.md](./TERMUX_INSTALL.md) — full install guide
- [Termux](https://termux.dev)
- [Ollama](https://ollama.com)
