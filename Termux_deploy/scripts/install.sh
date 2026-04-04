#!/data/data/com.termux/files/usr/bin/bash
# Fix 1: Removed global set -e — each step handles its own errors

echo "================================================"
echo "  JagaChatbot Termux Installer"
echo "  Local AI on your Android phone"
echo "================================================"
echo ""

# ── Helper: binary-first pip install with source fallback ─────────────────────
# Fix 4: pip_install_safe() tries --only-binary=:all: first; falls back to
#         source build only when a binary wheel is unavailable.
pip_install_safe() {
    local pkg="$1"
    shift
    local extra_args=("$@")
    echo "  Installing $pkg (binary-first)..."
    if pip install "$pkg" "${extra_args[@]}" --only-binary=:all: --quiet 2>/dev/null; then
        echo "    ✅ $pkg installed (binary wheel)"
    else
        echo "    ⚠️  Binary wheel not found for $pkg, trying source install..."
        if pip install "$pkg" "${extra_args[@]}"; then
            echo "    ✅ $pkg installed (source)"
        else
            echo "    ❌ FAILED to install $pkg — skipping"
        fi
    fi
}

# ── Step 1 — Termux packages ───────────────────────────────────────────────────
echo "[1/6] Installing Termux packages..."
if ! { pkg update -y && pkg upgrade -y; }; then
    echo "WARNING: pkg update/upgrade encountered errors — continuing anyway."
fi

if ! pkg install -y python git curl; then
    echo "ERROR: Failed to install core packages (python git curl). Cannot continue."
    exit 1
fi

# Fix 2: Graceful pkg install with pip fallback for aiohttp and cryptography
NEED_PIP_AIOHTTP=0
NEED_PIP_CRYPTOGRAPHY=0

if pkg install -y python-aiohttp; then
    echo "  python-aiohttp installed via pkg."
else
    echo "  WARNING: pkg install python-aiohttp failed — will install via pip after venv is ready."
    NEED_PIP_AIOHTTP=1
fi

if pkg install -y python-cryptography; then
    echo "  python-cryptography installed via pkg."
else
    echo "  WARNING: pkg install python-cryptography failed — will install via pip after venv is ready."
    NEED_PIP_CRYPTOGRAPHY=1
fi

echo "Termux packages step complete."

# ── Step 2 — Ollama check ─────────────────────────────────────────────────────
echo ""
echo "[2/6] Checking Ollama..."
if ! command -v ollama &> /dev/null; then
    echo "ERROR: Ollama not found."
    echo ""
    echo "Install Ollama for Linux/aarch64:"
    echo "  curl -fsSL https://ollama.com/install.sh | sh"
    echo ""
    echo "Then pull the model:"
    echo "  ollama pull deepseek-r1:1.5b"
    echo ""
    echo "Then re-run this script."
    exit 1
fi
echo "Ollama found: $(ollama --version 2>/dev/null || echo 'version unknown')"

# ── Step 3 — Model check ──────────────────────────────────────────────────────
echo ""
echo "[3/6] Checking DeepSeek R1 1.5B model..."
if ! ollama list 2>/dev/null | grep -q "deepseek-r1:1.5b"; then
    echo "Model not found. Pulling deepseek-r1:1.5b..."
    echo "(This downloads ~1GB — connect to Wi-Fi first)"
    if ! ollama pull deepseek-r1:1.5b; then
        echo "WARNING: Failed to pull model — you can pull it later with:"
        echo "  ollama pull deepseek-r1:1.5b"
    else
        echo "Model pulled successfully."
    fi
else
    echo "Model already pulled."
fi

# ── Step 4 — Virtual environment ──────────────────────────────────────────────
echo ""
echo "[4/6] Setting up virtual environment..."
JAGACHATBOT_DIR="/data/data/com.termux/files/home/AutoJaga/JagaChatbot"

if [ ! -d "$JAGACHATBOT_DIR" ]; then
    echo "ERROR: JagaChatbot directory not found at: $JAGACHATBOT_DIR"
    echo "Make sure you cloned AutoJaga to your Termux home directory:"
    echo "  cd ~ && git clone https://github.com/matparang/AutoJaga.git"
    exit 1
fi

cd "$JAGACHATBOT_DIR"

# Fix 3: Repair mode — healthy venv requires both activate and a working python
if [ -d "venv" ]; then
    if [ -f "venv/bin/activate" ] && [ -x "venv/bin/python" ]; then
        echo "  Virtual environment is healthy — skipping creation."
    else
        echo "  WARNING: venv/ exists but is broken (missing activate or python)."
        echo "  Removing broken venv and recreating..."
        rm -rf venv
        python -m venv venv --without-pip
        curl -sS https://bootstrap.pypa.io/get-pip.py | venv/bin/python
        echo "  Virtual environment recreated."
    fi
else
    echo "  No venv found — creating fresh virtual environment..."
    python -m venv venv --without-pip
    curl -sS https://bootstrap.pypa.io/get-pip.py | venv/bin/python
    echo "  Virtual environment created."
fi

# ── Step 5 — Install dependencies ─────────────────────────────────────────────
echo ""
echo "[5/6] Installing Python dependencies..."
# shellcheck source=/dev/null
source venv/bin/activate

if ! pip install --upgrade pip --quiet; then
    echo "WARNING: pip upgrade failed — continuing with existing pip version."
fi

# Fix 4: Use pip_install_safe() for every package
# litellm always installed with --no-deps to avoid Rust dependency pulls
echo "  Installing litellm (no-deps to avoid Rust failures)..."
pip_install_safe litellm --no-deps

pip_install_safe openai
pip_install_safe httpx
pip_install_safe pydantic
pip_install_safe python-dotenv
pip_install_safe typing-extensions
pip_install_safe anyio
pip_install_safe rich
pip_install_safe typer
pip_install_safe anthropic

# Fix 2 (continued): pip fallback for pkg packages that failed earlier
if [ "$NEED_PIP_AIOHTTP" -eq 1 ]; then
    echo "  Installing aiohttp via pip (pkg fallback)..."
    pip_install_safe aiohttp
fi

if [ "$NEED_PIP_CRYPTOGRAPHY" -eq 1 ]; then
    echo "  Installing cryptography via pip (pkg fallback)..."
    pip_install_safe cryptography
fi

echo "Dependencies installed."

# ── Step 6 — Config ───────────────────────────────────────────────────────────
echo ""
echo "[6/6] Setting up config..."
TERMUX_DEPLOY_DIR="/data/data/com.termux/files/home/AutoJaga/Termux_deploy"

if [ ! -f "$TERMUX_DEPLOY_DIR/.env.termux" ]; then
    echo "ERROR: .env.termux not found at: $TERMUX_DEPLOY_DIR/.env.termux"
    echo "Make sure you have the full AutoJaga repo including Termux_deploy/"
    exit 1
fi

mkdir -p ~/.jagachatbot
cp "$TERMUX_DEPLOY_DIR/.env.termux" ~/.jagachatbot/.env
echo "Config files set up."

echo ""
echo "================================================"
echo "  Installation complete!"
echo ""
echo "  Next steps:"
echo "  1. Run health check:"
echo "     bash ~/AutoJaga/Termux_deploy/scripts/check_health.sh"
echo ""
echo "  2. Start JagaChatbot:"
echo "     bash ~/AutoJaga/Termux_deploy/scripts/start.sh"
echo ""
echo "================================================"
echo "  REPAIR (if venv is broken later):"
echo "  cd ~/AutoJaga/JagaChatbot && rm -rf venv && bash ~/AutoJaga/Termux_deploy/scripts/install.sh"
echo "================================================"
