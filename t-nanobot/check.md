## 🎯 **SCOPE PROMPTING UNTUK COPILOT - FIX V2 MCP INTEGRATION**

```markdown
# SCOPE: V2 Chess MCP Tools Integration

## Situation Context
TanyalahD currently has:
- ✅ Working V2 modules (cache_v2.py, fensync.py, filter.py, classifier.py, confidence.py)
- ✅ Working chess MCP tools (get_board_state_enhanced, analyse_with_commentary)
- ❌ V2 modules NOT registered as MCP tools - TanyalahD cannot call them directly
- ❌ Import path confusion (double nanobot folder structure)
- ❌ No separation between V1 and V2 tools

## Objective
Create a separate V2 MCP toolset that TanyalahD can control, independent from existing chess MCP functions.

## Architecture

### 1. New V2 MCP Wrapper File
Create: `/root/t-nanobot/nanobot/nanobot/mcp/chess_v2_wrapper.py`

```python
"""
V2 Chess MCP Wrapper - exposes V2 reasoning modules as MCP tools
Separate from existing chess_wrapper.py to avoid conflicts
"""

from nanobot.nanobot.chess.cache_v2 import ChessRelationalCacheV2
from nanobot.nanobot.chess.fensync import FENSyncEngine
from nanobot.nanobot.chess.filter import StockfishFilter
from nanobot.nanobot.chess.classifier import ChessTaskClassifier
from nanobot.nanobot.chess.confidence import DynamicConfidenceV2
import chess
import json

class ChessV2MCPServer:
    """
    MCP server for V2 chess reasoning modules
    Each method = one MCP tool
    """
    
    def __init__(self):
        self.cache = ChessRelationalCacheV2()
        self.fensync = FENSyncEngine()
        self.filter = StockfishFilter()
        self.classifier = ChessTaskClassifier()
        self.confidence = DynamicConfidenceV2()
        self.current_fen = None
    
    def tool_update_position(self, fen: str) -> dict:
        """
        Update cache with new position
        Returns board snapshot
        """
        pass
    
    def tool_get_threats(self, square: str = None) -> dict:
        """
        Get threat analysis for specific square or whole board
        Uses cache.get_threats()
        """
        pass
    
    def tool_check_filter(self, position_fen: str) -> dict:
        """
        Check if position qualifies for Stockfish filter
        Returns FilterDecision with filtered flag + reason
        """
        pass
    
    def tool_classify_query(self, query: str) -> dict:
        """
        Classify user query using regex fast-path
        Returns ClassifyResult with intent + confidence
        """
        pass
    
    def tool_get_confidence_threshold(self, position_fen: str) -> dict:
        """
        Get adaptive confidence threshold based on position complexity
        Returns threshold + allow_creativity flag
        """
        pass
    
    def tool_differential_update(self, move_uci: str, new_fen: str) -> dict:
        """
        Update cache with differential method (only changed squares)
        Returns list of updated squares + performance metrics
        """
        pass
```

### 2. Register V2 Tools in MCP Config
Update: `/root/.nanobot/config.json`

Add new MCP server entry:
```json
{
  "tools": {
    "mcpServers": {
      "chess_v2": {
        "command": "/root/t-nanobot/venv/bin/python3",
        "args": ["-m", "nanobot.nanobot.mcp.chess_v2_wrapper"],
        "env": {
          "PYTHONPATH": "/root/t-nanobot",
          "PYTHONUNBUFFERED": "1"
        }
      }
    }
  }
}
```

### 3. Test Script for V2 Tools
Create: `/root/t-nanobot/scripts/test_v2_mcp.py`

```python
"""
Test script for V2 MCP tools
Run: python scripts/test_v2_mcp.py
"""

import json
import subprocess
import sys
sys.path.insert(0, '/root/t-nanobot')

def test_v2_tools():
    """Test all V2 MCP tools"""
    print("🧪 Testing V2 MCP Tools")
    print("=" * 50)
    
    # Test 1: Update position
    # Test 2: Get threats
    # Test 3: Check filter
    # Test 4: Classify query
    # Test 5: Get confidence
    # Test 6: Differential update
    
    pass

if __name__ == "__main__":
    test_v2_tools()
```

### 4. Fix Import Paths (Critical!)
Ensure all V2 modules use correct imports:

**In each V2 file** (`cache_v2.py`, `fensync.py`, `filter.py`, `classifier.py`, `confidence.py`):
```python
# Use THIS pattern (depends on actual structure)
from nanobot.nanobot.chess.xxx import YYY
# OR
from nanobot.chess.xxx import YYY  # Whichever works
```

## Success Criteria
- [ ] `nanobot tools list` shows new `chess_v2` tools (5-6 tools)
- [ ] TanyalahD can call `mcp_chess_v2_update_position()`
- [ ] V2 tools work independently from existing chess MCP
- [ ] No import errors when loading V2 modules
- [ ] Test script passes all 6 tests
- [ ] Existing chess MCP tools still work (get_board_state_enhanced, etc.)

## Important Notes
- Keep V2 tools SEPARATE from existing chess MCP (don't modify chess_wrapper.py)
- Use the same double-nanobot import pattern that currently works
- Add debug logging to track V2 tool usage
- Include performance metrics (update time, filter rate)

## TanyalahD Commands (After Implementation)
```
TanyalahD, update position to rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR
TanyalahD, what threats at e4?
TanyalahD, check if this position needs LLM: [FEN]
TanyalahD, classify: "best move in Dragon?"
TanyalahD, get confidence threshold for current position
```
```

## 🚀 **PASTE INI KE COPILOT!**

Copilot akan generate:
- ✅ chess_v2_wrapper.py dengan semua tools
- ✅ Config update
- ✅ Test script
- ✅ Fix import paths

**V2 tools akan jadi MCP tools yang boleh TanyalahD panggil terus!** 🧠
