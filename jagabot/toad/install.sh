#!/bin/bash
# Install AutoJaga + TOAD integration

set -e

echo "🔧 Installing AutoJaga + TOAD integration..."
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
echo "🐍 Python version: $PYTHON_VERSION"

# Navigate to nanojaga root
cd /root/nanojaga

# Check if TOAD can be installed
echo "📦 Checking TOAD compatibility..."
if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 14) else 1)" 2>/dev/null; then
    # Python 3.14+ - can install TOAD
    if pip show batrachian-toad > /dev/null 2>&1; then
        echo "✅ TOAD already installed"
        TOAD_VERSION=$(pip show batrachian-toad | grep Version | cut -d' ' -f2)
        echo "   Version: $TOAD_VERSION"
    else
        echo "📦 Installing TOAD..."
        pip install batrachian-toad && echo "✅ TOAD installed" || {
            echo "⚠️  TOAD installation failed (requires Python 3.14+)"
            echo "   Your Python version: $PYTHON_VERSION"
            echo ""
            echo "📝 TOAD integration code is installed but TOAD TUI is not available."
            echo "   You can still use AutoJaga CLI and API."
            echo ""
            echo "   To use TOAD in the future:"
            echo "   1. Upgrade to Python 3.14+"
            echo "   2. Run: pip install batrachian-toad"
        }
    fi
else
    echo "⚠️  TOAD requires Python 3.14+ (you have $PYTHON_VERSION)"
    echo ""
    echo "📝 TOAD integration code is installed but TOAD TUI is not available."
    echo "   You can still use AutoJaga CLI and API."
    echo ""
    echo "   To use TOAD in the future:"
    echo "   1. Upgrade to Python 3.14+"
    echo "   2. Run: pip install batrachian-toad"
fi

# Install AutoJaga dependencies
echo ""
echo "📦 Installing AutoJaga dependencies..."
pip install -e ".[dev]" > /dev/null 2>&1 || pip install -e "."

# Install TOAD integration dependencies (these work with Python 3.12)
echo "📦 Installing TOAD integration dependencies..."
pip install pyyaml thefuzz prompt_toolkit > /dev/null 2>&1 || true

# Create necessary directories
echo ""
echo "📁 Creating directories..."
mkdir -p /root/.jagabot/sessions
mkdir -p /root/.jagabot/workspace/organized/research
mkdir -p /root/.jagabot/logs

# Set permissions
echo "🔐 Setting permissions..."
chmod +x /root/nanojaga/jagabot/cli/toad.py 2>/dev/null || true

# Verify installation
echo ""
echo "🧪 Verifying installation..."
python3 -c "
import sys
sys.path.insert(0, '/root/nanojaga')
from jagabot.toad.acp_adapter import AutoJagaACP
from pathlib import Path
adapter = AutoJagaACP(workspace=Path.home() / '.jagabot' / 'workspace')
print(f'✅ AutoJaga ACP adapter initialized')
print(f'   Workspace: {adapter.workspace}')
print(f'   Tools loaded: {len(adapter.tools)}')
"

echo ""
echo "✅ AutoJaga + TOAD integration code installed successfully!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 14) else 1)" 2>/dev/null && pip show batrachian-toad > /dev/null 2>&1; then
    echo "Usage:"
    echo "  jagabot-toad              # Launch AutoJaga in TOAD TUI"
    echo "  toad --agent autojaga     # Alternative launch command"
else
    echo "⚠️  TOAD TUI not available (requires Python 3.14+)"
    echo ""
    echo "You can still use AutoJaga:"
    echo "  jagabot agent             # CLI mode"
    echo "  jagabot agent --tui       # Basic TUI mode"
fi
echo ""
echo "Features:"
echo "  📊 45+ financial analysis tools"
echo "  🤖 Multi-agent swarms (Tri/Quad)"
echo "  🔍 4-phase research pipeline"
echo "  ✅ Epistemic verification"
echo ""
if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 14) else 1)" 2>/dev/null; then
    echo "Note: TOAD TUI features (file picker, persistent shell)"
    echo "      will be available when you upgrade to Python 3.14+"
fi
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
