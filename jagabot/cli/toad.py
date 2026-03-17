#!/usr/bin/env python3
"""
Launch AutoJaga within TOAD TUI

This script sets up the environment and launches TOAD with AutoJaga as the agent.
"""

import sys
import os
from pathlib import Path


def main():
    """Launch AutoJaga in TOAD TUI"""
    
    # Get nanojaga root directory
    nanojaga_root = Path(__file__).parent.parent.parent
    
    # Add AutoJaga to Python path
    sys.path.insert(0, str(nanojaga_root))
    
    # Set environment variables for TOAD
    workspace = Path.home() / ".jagabot" / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    
    os.environ["AUTOJAGA_WORKSPACE"] = str(workspace)
    os.environ["AUTOJAGA_AGENT"] = "jagabot.toad.acp_adapter:AutoJagaACP"
    
    # Set TOAD agent configuration
    os.environ["TOAD_AGENT"] = "autojaga"
    os.environ["TOAD_AGENT_CONFIG"] = str(
        nanojaga_root / "jagabot" / "toad" / "toad_config.yaml"
    )
    
    try:
        # Try to launch TOAD with AutoJaga agent
        from toad.cli import main as toad_main
        
        # Set command line arguments for TOAD
        sys.argv = [
            "toad",
            "--agent", "autojaga",
            "--workspace", str(workspace)
        ]
        
        print("🚀 Launching AutoJaga in TOAD TUI...")
        print(f"📁 Workspace: {workspace}")
        print("Press Ctrl+Q to quit\n")
        
        toad_main()
        
    except ImportError as e:
        print(f"❌ TOAD not installed: {e}")
        print("\nTo install TOAD, run:")
        print("  pip install batrachian-toad")
        print("\nOr use the installation script:")
        print("  bash jagabot/toad/install.sh")
        sys.exit(1)
        
    except Exception as e:
        print(f"❌ Failed to launch TOAD: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
