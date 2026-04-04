#!/data/data/com.termux/files/usr/bin/bash

echo "🐈 Starting JagaChatbot (Termux / DeepSeek R1 1.5B)"
echo ""

# Check Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "ERROR: Ollama not found."
    echo "Run install.sh first:"
    echo "  bash ~/AutoJaga/Termux_deploy/scripts/install.sh"
    exit 1
fi

# Start Ollama if not running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Starting Ollama server..."
    ollama serve > /tmp/ollama.log 2>&1 &
    OLLAMA_PID=$!
    echo "Waiting for Ollama to start (up to 10 seconds)..."

    ATTEMPTS=0
    until curl -s http://localhost:11434/api/tags > /dev/null 2>&1 || [ $ATTEMPTS -ge 10 ]; do
        sleep 1
        ATTEMPTS=$((ATTEMPTS + 1))
    done

    if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "ERROR: Ollama failed to start after 10 seconds."
        echo "Check the log for details:"
        echo "  cat /tmp/ollama.log"
        exit 1
    fi
    echo "Ollama started (PID: $OLLAMA_PID)"
else
    echo "Ollama already running."
fi

# Check model is available
if ! ollama list 2>/dev/null | grep -q "deepseek-r1:1.5b"; then
    echo "Model not found locally. Pulling deepseek-r1:1.5b..."
    echo "(This requires ~1GB download — connect to Wi-Fi)"
    ollama pull deepseek-r1:1.5b
    echo "Model ready."
fi

# Activate venv
VENV_PATH="/data/data/com.termux/files/home/AutoJaga/JagaChatbot/venv"
if [ ! -d "$VENV_PATH" ]; then
    echo "ERROR: Virtual environment not found at: $VENV_PATH"
    echo "Run install.sh first:"
    echo "  bash ~/AutoJaga/Termux_deploy/scripts/install.sh"
    exit 1
fi
source "$VENV_PATH/bin/activate"

# Set Termux config override and launch
echo "Launching JagaChatbot..."
echo ""

cd /data/data/com.termux/files/home/AutoJaga/JagaChatbot
JAGACHATBOT_CONFIG="/data/data/com.termux/files/home/AutoJaga/Termux_deploy/config/termux_config.json" \
python -m jagachatbot
