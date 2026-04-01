"""
Session Checkpoint — Save and restore conversation state.

Prevents memory loss when session crashes or budget exceeded.

Usage:
    from jagabot.core.session_checkpoint import save_checkpoint, load_latest_checkpoint
    
    # Save every N turns
    save_checkpoint(messages, iteration, workspace)
    
    # Load on resume
    checkpoint = load_latest_checkpoint(workspace)
    if checkpoint:
        messages = checkpoint["messages"]
"""

import json
from pathlib import Path
from datetime import datetime
from loguru import logger


def save_checkpoint(messages: list, turn_number: int, workspace: Path) -> Path:
    """
    Save conversation state to checkpoint file.
    
    Args:
        messages: Current conversation messages
        turn_number: Current turn number
        workspace: Workspace directory
    
    Returns:
        Path to saved checkpoint file
    """
    checkpoint_dir = workspace / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    # Calculate token estimate
    token_estimate = sum(len(m.get("content", "")) // 4 for m in messages)
    
    checkpoint = {
        "timestamp": datetime.now().isoformat(),
        "turn": turn_number,
        "message_count": len(messages),
        "token_estimate": token_estimate,
        "messages": messages,
    }
    
    path = checkpoint_dir / f"checkpoint_turn_{turn_number}.json"
    path.write_text(json.dumps(checkpoint, indent=2))
    
    logger.info(f"Checkpoint saved: turn {turn_number}, {len(messages)} messages, ~{token_estimate:,} tokens")
    return path


def load_latest_checkpoint(workspace: Path) -> dict | None:
    """
    Load most recent checkpoint.
    
    Args:
        workspace: Workspace directory
    
    Returns:
        Checkpoint dict or None if no checkpoint found
    """
    checkpoint_dir = workspace / "checkpoints"
    if not checkpoint_dir.exists():
        return None
    
    checkpoints = list(checkpoint_dir.glob("checkpoint_turn_*.json"))
    if not checkpoints:
        return None
    
    latest = max(checkpoints)
    checkpoint = json.loads(latest.read_text())
    
    logger.info(f"Checkpoint loaded: turn {checkpoint['turn']}, {checkpoint['message_count']} messages")
    return checkpoint


def list_checkpoints(workspace: Path) -> list[dict]:
    """List all available checkpoints."""
    checkpoint_dir = workspace / "checkpoints"
    if not checkpoint_dir.exists():
        return []
    
    checkpoints = []
    for path in sorted(checkpoint_dir.glob("checkpoint_turn_*.json")):
        data = json.loads(path.read_text())
        checkpoints.append({
            "path": str(path),
            "turn": data["turn"],
            "timestamp": data["timestamp"],
            "messages": data["message_count"],
            "tokens": data["token_estimate"],
        })
    
    return checkpoints


def cleanup_old_checkpoints(workspace: Path, keep_last: int = 5):
    """Remove old checkpoints, keeping only the last N."""
    checkpoint_dir = workspace / "checkpoints"
    if not checkpoint_dir.exists():
        return
    
    checkpoints = sorted(checkpoint_dir.glob("checkpoint_turn_*.json"))
    if len(checkpoints) <= keep_last:
        return
    
    # Remove oldest checkpoints
    for path in checkpoints[:-keep_last]:
        path.unlink()
        logger.debug(f"Removed old checkpoint: {path.name}")
