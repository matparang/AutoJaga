"""Entry point for python -m jagaragbot."""

import asyncio
import sys
from pathlib import Path

from jagaragbot.cli.interactive import run_interactive


def main() -> int:
    """Run JagaRAG in interactive CLI mode."""
    workspace = Path.home() / ".jagaragbot"
    workspace.mkdir(parents=True, exist_ok=True)
    
    try:
        asyncio.run(run_interactive(workspace))
        return 0
    except KeyboardInterrupt:
        print("\nGoodbye!")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
