# 🚀 AUTOJAGA + TOAD INTEGRATION PLAN

**Date:** March 14, 2026  
**TOAD Version:** 0.6.12 (already installed at `~/nanojaga/toad`)  
**Status:** ✅ **TOAD EXISTS** - Integration plan needed

---

## 📊 CURRENT STATE ANALYSIS

### ✅ What Already Exists

**TOAD TUI** (`~/nanojaga/toad/`):
- ✅ Full TUI framework with Textual
- ✅ Persistent shell integration
- ✅ Fuzzy file picker (@ syntax)
- ✅ Session management
- ✅ Markdown rendering
- ✅ Mouse support
- ✅ Syntax highlighting
- ✅ Agent Client Protocol (ACP) support

**AutoJaga/Jagabot** (`~/nanojaga/jagabot/`):
- ✅ 45+ tools (financial analysis, research, etc.)
- ✅ Multi-agent swarms (Tri-agent, Quad-agent)
- ✅ Research skill (4-phase pipeline)
- ✅ Tool harness with verification
- ✅ 100% test coverage (316 tests)

---

## 🎯 INTEGRATION STRATEGY

### Option A: AutoJaga as TOAD Agent ✅ **RECOMMENDED**

**Architecture:**
```
TOAD (UI Layer)
  ↓
Agent Client Protocol (ACP)
  ↓
AutoJaga (Agent Layer)
  ↓
Tools + Swarms (Execution Layer)
```

**Why This Works:**
1. TOAD already has ACP support ✅
2. AutoJaga already has tools ✅
3. Minimal code changes needed ✅
4. Users get both TOAD UI + AutoJaga capabilities ✅

---

## 📋 IMPLEMENTATION PLAN

### Phase 1: ACP Adapter (1 hour)

**File:** `/root/nanojaga/jagabot/toad/acp_adapter.py`

```python
"""
Adapter to expose AutoJaga as ACP-compatible agent
"""

from typing import AsyncIterator, Dict, Any, List
from pathlib import Path

class AutoJagaACP:
    """
    AutoJaga agent compatible with TOAD's ACP
    """
    
    def __init__(self, workspace: Path = None):
        self.workspace = workspace or Path.home() / ".jagabot" / "workspace"
        self.tools = self._load_tools()
        
    def _load_tools(self) -> List[Dict]:
        """Load AutoJaga tools as ACP tools"""
        from jagabot.agent.tools.registry import ToolRegistry
        registry = ToolRegistry()
        # Register all AutoJaga tools
        # ... (register 45+ tools)
        return registry.get_definitions()
    
    async def run(self, prompt: str, attachments: List[Path] = None) -> AsyncIterator[Dict]:
        """
        Run AutoJaga agent with TOAD ACP protocol
        """
        # Yield thinking status
        yield {
            "type": "status",
            "message": "AutoJaga is thinking...",
            "state": "running"
        }
        
        # Execute with AutoJaga agent loop
        from jagabot.agent.loop import AgentLoop
        # ... (integrate with AgentLoop)
        
        # Stream results
        yield {
            "type": "content",
            "format": "markdown",
            "content": result
        }
        
        # Yield completion
        yield {
            "type": "complete",
            "success": True
        }
```

---

### Phase 2: TOAD Configuration (30 min)

**File:** `/root/nanojaga/jagabot/toad/toad_config.yaml`

```yaml
# AutoJaga configuration for TOAD

agent:
  name: "AutoJaga"
  version: "5.0"
  description: "Financial research AI assistant"
  
  # ACP configuration
  acp:
    enabled: true
    tools:
      - financial_cv
      - monte_carlo
      - var
      - cvar
      - stress_test
      - correlation
      - recovery_time
      - portfolio_analyzer
      - decision_engine
      - bayesian_reasoner
      - k1_bayesian
      - k3_perspective
      - evaluate_result
      - memory_fleet
      - knowledge_graph
      - meta_learning
      - evolution
      - debate
      - tri_agent
      - quad_agent
      - offline_swarm
      # ... (all 45+ tools)

workspace:
  root: "/root/.jagabot/workspace"
  research_dir: "/root/.jagabot/workspace/organized/research"
  
research:
  enabled: true
  phases:
    - tri_agent_debate
    - main_agent_planning
    - quad_agent_execution
    - tri_agent_synthesis
```

---

### Phase 3: TOAD CLI Integration (30 min)

**File:** `/root/nanojaga/jagabot/cli/toad.py`

```python
#!/usr/bin/env python3
"""
Launch AutoJaga within TOAD TUI
"""

import sys
import os
from pathlib import Path

def main():
    """Launch AutoJaga in TOAD"""
    # Add AutoJaga to path
    nanojaga_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(nanojaga_root))
    
    # Set environment for TOAD to find AutoJaga
    os.environ["AUTOJAGA_WORKSPACE"] = str(
        Path.home() / ".jagabot" / "workspace"
    )
    os.environ["AUTOJAGA_AGENT"] = "jagabot.toad.acp_adapter:AutoJagaACP"
    
    # Launch TOAD with AutoJaga agent
    from toad.cli import main as toad_main
    sys.argv = ["toad", "--agent", "autojaga"]
    toad_main()

if __name__ == "__main__":
    main()
```

---

### Phase 4: Update pyproject.toml (15 min)

**File:** `/root/nanojaga/pyproject.toml`

```toml
[project.scripts]
jagabot = "jagabot.cli.commands:app"
jagabot-toad = "jagabot.cli.toad:main"  # NEW

[project.optional-dependencies]
toad = [
    "batrachian-toad>=0.6.12",
    "textual>=8.1.1",
]
```

---

### Phase 5: Integration Test (30 min)

**File:** `/root/nanojaga/tests/test_toad_integration.py`

```python
"""
Test AutoJaga + TOAD integration
"""

import pytest
from pathlib import Path

def test_acp_adapter_imports():
    """Test ACP adapter imports correctly"""
    try:
        from jagabot.toad.acp_adapter import AutoJagaACP
        print("✅ ACP adapter imported successfully")
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        pytest.fail(f"ACP adapter import failed: {e}")

def test_acp_adapter_initialization():
    """Test ACP adapter initializes"""
    from jagabot.toad.acp_adapter import AutoJagaACP
    
    adapter = AutoJagaACP()
    assert adapter is not None
    assert adapter.workspace.exists()

def test_tools_loaded():
    """Test AutoJaga tools are loaded"""
    from jagabot.toad.acp_adapter import AutoJagaACP
    
    adapter = AutoJagaACP()
    tools = adapter._load_tools()
    
    assert len(tools) > 0
    assert any(t["function"]["name"] == "financial_cv" for t in tools)

@pytest.mark.asyncio
async def test_agent_run():
    """Test agent runs with ACP protocol"""
    from jagabot.toad.acp_adapter import AutoJagaACP
    
    adapter = AutoJagaACP()
    results = []
    
    async for message in adapter.run("What is VIX?"):
        results.append(message)
        assert "type" in message
    
    # Should have status, content, and complete messages
    types = [m["type"] for m in results]
    assert "status" in types
    assert "content" in types
    assert "complete" in types
```

---

### Phase 6: Installation Script (15 min)

**File:** `/root/nanojaga/jagabot/toad/install.sh`

```bash
#!/bin/bash
# Install AutoJaga + TOAD integration

echo "🔧 Installing AutoJaga + TOAD integration..."

# Navigate to nanojaga root
cd /root/nanojaga

# Install TOAD if not already installed
if ! pip show batrachian-toad > /dev/null 2>&1; then
    echo "📦 Installing TOAD..."
    pip install batrachian-toad
fi

# Install AutoJaga with TOAD extras
echo "📦 Installing AutoJaga with TOAD support..."
pip install -e ".[toad]"

# Create necessary directories
mkdir -p /root/.jagabot/sessions
mkdir -p /root/.jagabot/workspace/organized/research

# Set permissions
chmod +x /root/nanojaga/jagabot/cli/toad.py

echo ""
echo "✅ AutoJaga + TOAD installed successfully!"
echo ""
echo "Usage:"
echo "  jagabot-toad              # Launch AutoJaga in TOAD TUI"
echo "  toad --agent autojaga     # Alternative launch command"
echo ""
```

---

## 📁 DIRECTORY STRUCTURE

```
/root/nanojaga/
├── jagabot/
│   ├── cli/
│   │   ├── toad.py                 # NEW - TOAD launcher
│   │   └── commands.py             # MODIFY - Add toad command
│   ├── toad/                       # NEW directory
│   │   ├── __init__.py
│   │   ├── acp_adapter.py          # NEW - ACP adapter
│   │   ├── toad_config.yaml        # NEW - Configuration
│   │   └── install.sh              # NEW - Installation
│   └── core/
│       └── toad_bridge.py          # NEW - Communication bridge
├── tests/
│   └── test_toad_integration.py    # NEW - Integration tests
├── toad/                           # EXISTING
│   └── src/toad/                   # TOAD source code
└── pyproject.toml                  # MODIFY - Add toad extras
```

---

## 🚀 IMPLEMENTATION ORDER

### Session 1: Core Integration (2 hours)

1. **Create ACP Adapter** (1 hour)
   - `jagabot/toad/acp_adapter.py`
   - Integrate with AgentLoop
   - Test basic communication

2. **TOAD Configuration** (30 min)
   - `jagabot/toad/toad_config.yaml`
   - Configure all 45+ tools
   - Set workspace paths

3. **CLI Integration** (30 min)
   - `jagabot/cli/toad.py`
   - Add `jagabot-toad` command
   - Test launch

---

### Session 2: Testing + Polish (1.5 hours)

4. **Integration Tests** (30 min)
   - `tests/test_toad_integration.py`
   - Test ACP protocol
   - Test tool execution

5. **Installation Script** (15 min)
   - `jagabot/toad/install.sh`
   - Test installation flow

6. **Documentation** (45 min)
   - Update README
   - Add usage examples
   - Create quickstart guide

---

## 🎯 USAGE EXAMPLES

### Launch AutoJaga in TOAD

```bash
# Method 1: Direct command
jagabot-toad

# Method 2: TOAD with agent flag
toad --agent autojaga

# Method 3: From jagabot CLI
jagabot agent --toad
```

### Example Workflow in TOAD

```
┌────────────────────────────────────────────────────────┐
│ AUTOJAGA v5.0 — RESEARCH PARTNER                       │
│ F1:Help  Ctrl+S:Agents  Ctrl+R:Resume  @:File  !:Shell │
└────────────────────────────────────────────────────────┘

📁 /research/ $ _

You: @proposal.md jalankan research tentang renewable energy

╭──────────────────────────────────────────────────────╮
│ 🔍 Phase 1: Tri-Agent Debate                          │
│   🐂 Bull: Opportunities identified                   │
│   🐻 Bear: Risks highlighted                          │
│   🧔 Buffett: Value assessed                          │
│ ✅ Proposal saved to research/proposal_20260314.md    │
╰──────────────────────────────────────────────────────╯

[25%] ⏳ Phase 2: Planning... (2s remaining)
```

---

## ✅ SUCCESS CRITERIA

### Phase 1 Complete When:
- [ ] ACP adapter created
- [ ] TOAD launches with AutoJaga agent
- [ ] Basic tool execution works
- [ ] All tests pass

### Phase 2 Complete When:
- [ ] All 45+ tools configured
- [ ] Research skill integrated
- [ ] Multi-agent swarms work
- [ ] Documentation complete

### Production Ready When:
- [ ] Integration tests pass
- [ ] Installation script works
- [ ] User documentation complete
- [ ] No regressions in existing functionality

---

## 🎓 LESSONS FROM TOAD CODEBASE

### What TOAD Already Has ✅

From `notes.md`:
- ✅ ACP support broadly works
- ✅ Slash commands
- ✅ Tool calls
- ✅ Terminal integration
- ✅ Settings (F2 / ctrl+,)
- ✅ Multiline prompt
- ✅ Shell commands with colors
- ✅ Interactive shell commands

### What Needs Work ⚠️

From `notes.md`:
- ⚠️ File tree doesn't do much (can enhance)
- ⚠️ Chat bots temporarily disabled (may need workaround)

---

## 🏁 RECOMMENDATION

**Start with Phase 1 immediately.** TOAD is already installed and working - we just need to:

1. Create ACP adapter (1 hour)
2. Configure tools (30 min)
3. Test integration (30 min)

**Total Time to MVP:** 2 hours  
**Risk:** LOW - TOAD already exists, minimal code changes  
**Impact:** HIGH - Professional TUI with all AutoJaga capabilities

---

**Ready to implement?**

```bash
cd /root/nanojaga
mkdir -p jagabot/toad
# Start with acp_adapter.py
```

**Status:** ✅ **READY TO IMPLEMENT**
