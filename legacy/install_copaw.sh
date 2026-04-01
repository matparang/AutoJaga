#!/bin/bash
# install_copaw.sh - Install CoPaw Pipeline (AutoJaga API + Qwen Service)
#
# This script installs all components needed for CoPaw integration:
# - AutoJaga API server (port 8000)
# - Qwen CLI service (port 8080)
# - Workspace structure
#
# Usage:
#   bash install_copaw.sh

set -e

echo "🚀 Installing CoPaw Pipeline..."
echo "================================"
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
echo "🐍 Python version: $PYTHON_VERSION"

# Navigate to nanojaga root
cd /root/nanojaga

# Step 1: Install Python dependencies
echo ""
echo "📦 Installing Python dependencies..."
pip install fastapi uvicorn requests python-multipart pydantic loguru 2>&1 | grep -E "(Successfully|Requirement|already)" || true
echo "✅ Dependencies installed"

# Step 2: Create workspace structure
echo ""
echo "📁 Creating workspace structure..."
mkdir -p /root/.jagabot/workspace/CoPaw_Projects/Logistic_Regression/{blueprints,code,results,analysis}
mkdir -p /root/.jagabot/logs
mkdir -p /root/.jagabot/sessions
mkdir -p /root/.jagabot/workspace/qwen
echo "✅ Workspace created at /root/.jagabot/workspace/CoPaw_Projects/"

# Step 3: Start AutoJaga API
echo ""
echo "🧠 Starting AutoJaga API server..."
if pgrep -f "jagabot.api.server" > /dev/null; then
    echo "⚠️  AutoJaga API already running"
else
    cd /root/nanojaga
    nohup python3 -m jagabot.api.server > /root/.jagabot/logs/autojaga_api.log 2>&1 &
    sleep 2
    if pgrep -f "jagabot.api.server" > /dev/null; then
        echo "✅ AutoJaga API started (PID: $(pgrep -f jagabot.api.server))"
    else
        echo "❌ Failed to start AutoJaga API"
        echo "   Check logs: /root/.jagabot/logs/autojaga_api.log"
    fi
fi

# Step 4: Start Qwen Service
echo ""
echo "🤖 Starting Qwen CLI Service..."
if pgrep -f "qwen_service" > /dev/null; then
    echo "⚠️  Qwen Service already running"
else
    cd /root/nanojaga
    nohup python3 qwen_service.py > /root/.jagabot/logs/qwen_service.log 2>&1 &
    sleep 2
    if pgrep -f "qwen_service" > /dev/null; then
        echo "✅ Qwen Service started (PID: $(pgrep -f qwen_service))"
    else
        echo "❌ Failed to start Qwen Service"
        echo "   Check logs: /root/.jagabot/logs/qwen_service.log"
    fi
fi

# Step 5: Wait for services and test health endpoints
echo ""
echo "🧪 Testing service health..."
sleep 3

# Test AutoJaga API
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ AutoJaga API: http://localhost:8000/health"
    curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || true
else
    echo "⚠️  AutoJaga API not responding (may need more time to start)"
fi

# Test Qwen Service
if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo "✅ Qwen Service: http://localhost:8080/health"
    curl -s http://localhost:8080/health | python3 -m json.tool 2>/dev/null || true
else
    echo "⚠️  Qwen Service not responding (may need more time to start)"
fi

# Step 6: Display usage information
echo ""
echo "✅ CoPaw Pipeline installation complete!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📍 Service URLs:"
echo "   AutoJaga API:    http://localhost:8000"
echo "   Qwen Service:    http://localhost:8081"
echo "   API Docs:        http://localhost:8000/docs"
echo "   Qwen Docs:       http://localhost:8081/docs"
echo ""
echo "📁 Workspace:"
echo "   /root/.jagabot/workspace/CoPaw_Projects/"
echo ""
echo "📋 Logs:"
echo "   AutoJaga: /root/.jagabot/logs/autojaga_api.log"
echo "   Qwen:     /root/.jagabot/logs/qwen_service.log"
echo ""
echo "🚀 Usage:"
echo "   # Test AutoJaga API"
echo "   curl http://localhost:8000/health"
echo ""
echo "   # Test Qwen Service"
echo "   curl http://localhost:8080/health"
echo ""
echo "   # Create experiment plan"
echo "   curl -X POST http://localhost:8000/plan \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"prompt\": \"Improve logistic regression accuracy\"}'"
echo ""
echo "   # Generate code"
echo "   curl -X POST http://localhost:8080/generate \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"blueprint\": \"# Experiment 1\", \"experiment_num\": 1, \"project\": \"Test\"}'"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🛑 To stop services:"
echo "   pkill -f jagabot.api.server"
echo "   pkill -f qwen_service"
echo ""
