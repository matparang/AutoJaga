#!/data/data/com.termux/files/usr/bin/bash

echo "=== JagaChatbot Termux Health Check ==="
echo ""

PASS=0
FAIL=0

check() {
    local label="$1"
    local cmd="$2"
    if eval "$cmd" > /dev/null 2>&1; then
        echo "✅ $label"
        PASS=$((PASS + 1))
    else
        echo "❌ $label"
        FAIL=$((FAIL + 1))
    fi
}

# System checks
check "Python 3.x installed"         "python --version"
check "Git installed"                 "command -v git"
check "curl installed"                "command -v curl"

# Ollama checks
check "Ollama installed"              "command -v ollama"
check "Ollama server running"         "curl -s http://localhost:11434/api/tags"
check "DeepSeek R1 1.5B pulled"       "ollama list | grep deepseek-r1:1.5b"

# Python environment checks
check "Virtual environment exists" \
    "test -d /data/data/com.termux/files/home/AutoJaga/JagaChatbot/venv"
check "LiteLLM installed" \
    "/data/data/com.termux/files/home/AutoJaga/JagaChatbot/venv/bin/python -c 'import litellm'"
check "Rich installed" \
    "/data/data/com.termux/files/home/AutoJaga/JagaChatbot/venv/bin/python -c 'import rich'"
check "Pydantic installed" \
    "/data/data/com.termux/files/home/AutoJaga/JagaChatbot/venv/bin/python -c 'import pydantic'"
check "httpx installed" \
    "/data/data/com.termux/files/home/AutoJaga/JagaChatbot/venv/bin/python -c 'import httpx'"

# Config and project checks
check "Termux config file exists" \
    "test -f /data/data/com.termux/files/home/AutoJaga/Termux_deploy/config/termux_config.json"
check ".env.termux file exists" \
    "test -f /data/data/com.termux/files/home/AutoJaga/Termux_deploy/.env.termux"
check "JagaChatbot __main__.py found" \
    "test -f /data/data/com.termux/files/home/AutoJaga/JagaChatbot/jagachatbot/__main__.py"
check "start.sh is executable" \
    "test -x /data/data/com.termux/files/home/AutoJaga/Termux_deploy/scripts/start.sh"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
echo ""

if [ $FAIL -eq 0 ]; then
    echo "All checks passed! Run start.sh to launch:"
    echo "  bash ~/AutoJaga/Termux_deploy/scripts/start.sh"
else
    echo "Fix the failed checks, then run this script again."
    echo "See TERMUX_INSTALL.md for troubleshooting help."
fi
