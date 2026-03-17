#!/usr/bin/env python3
"""
Safe Agent Bridge Installer
This script adds the agent bridge to server.py safely.
It creates backups and validates at each step.
"""

import shutil
import sys
from pathlib import Path

SERVER_FILE = Path("/root/nanojaga/jagabot/api/server.py")
BACKUP_FILE = Path("/root/nanojaga/jagabot/api/server.py.prebridge")

BRIDGE_CODE = '''

# ============================================================================
# AGENT BRIDGE - Starts Jagabot AgentLoop for /execute endpoint
# ============================================================================

# Global state for agent
_agent_bus: MessageBus = None
_agent_loop_task: asyncio.Task = None
_agent_instance: AgentLoop = None

async def get_or_start_agent() -> MessageBus:
    """Lazy-start AgentLoop when first request arrives."""
    global _agent_bus, _agent_loop_task, _agent_instance

    if _agent_bus is not None and _agent_loop_task and not _agent_loop_task.done():
        return _agent_bus

    logger.info("Starting Jagabot AgentLoop for the first time...")
    _agent_bus = MessageBus()

    config_path = Path.home() / ".jagabot" / "config.json"
    model = "dashscope/qwen-plus"
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
        model = config.get("agents", {}).get("defaults", {}).get("model", "dashscope/qwen-plus")

    logger.info(f"Using model: {model}")

    _agent_instance = AgentLoop(
        bus=_agent_bus,
        provider=LiteLLMProvider(
            api_key=config.get("providers", {}).get("dashscope", {}).get("apiKey", ""),
            api_base=config.get("providers", {}).get("dashscope", {}).get("apiBase"),
            default_model=model,
            provider_name="dashscope"
        ),
        workspace=Path("/root/.jagabot/workspace"),
        model=model,
        max_iterations=20,
    )

    # THIS is the missing line - START THE AGENT!
    _agent_loop_task = asyncio.create_task(_agent_instance.run())
    await asyncio.sleep(2)
    logger.info("✅ Jagabot AgentLoop started and ready")
    return _agent_bus


@app.post("/execute")
async def execute_task(request: PlanRequest):
    """Full agent execution — tools, memory, subagents, everything."""
    session_id = f"api_{int(asyncio.get_event_loop().time())}"

    try:
        logger.info(f"Executing task: {request.prompt[:100]}...")
        bus = await get_or_start_agent()

        msg = InboundMessage(
            channel="api",
            chat_id=session_id,
            content=request.prompt,
            sender_id="copaw_cli"
        )
        await bus.publish_inbound(msg)
        logger.info(f"Message published to agent (session: {session_id})")

        logger.info(f"Waiting for agent response (timeout: 300s)...")
        response = await asyncio.wait_for(
            bus.consume_outbound(chat_id=session_id),
            timeout=300
        )
        logger.info(f"Agent completed task (session: {session_id})")

        return {
            "status": "success",
            "session_id": session_id,
            "response": response.content,
            "tools_used": getattr(response, "tools_used", []),
        }

    except asyncio.TimeoutError:
        logger.error(f"Agent timeout (session: {session_id})")
        return {
            "status": "timeout",
            "session_id": session_id,
            "message": "Agent exceeded 5 minute limit"
        }
    except Exception as e:
        logger.error(f"Agent execution error: {e}")
        return {
            "status": "error",
            "message": str(e)
        }
'''

def main():
    print("="*60)
    print("SAFE AGENT BRIDGE INSTALLER")
    print("="*60)
    print()
    
    # Step 1: Check file exists
    print("Step 1: Checking server.py exists...")
    if not SERVER_FILE.exists():
        print(f"❌ ERROR: {SERVER_FILE} not found!")
        return False
    print(f"✅ Found: {SERVER_FILE}")
    print()
    
    # Step 2: Create backup
    print("Step 2: Creating backup...")
    try:
        shutil.copy2(SERVER_FILE, BACKUP_FILE)
        print(f"✅ Backup created: {BACKUP_FILE}")
    except Exception as e:
        print(f"❌ ERROR creating backup: {e}")
        return False
    print()
    
    # Step 3: Read current file
    print("Step 3: Reading current file...")
    try:
        with open(SERVER_FILE, 'r') as f:
            content = f.read()
        print(f"✅ File read ({len(content)} bytes)")
    except Exception as e:
        print(f"❌ ERROR reading file: {e}")
        return False
    print()
    
    # Step 4: Check if bridge already exists
    print("Step 4: Checking if bridge already installed...")
    if "async def get_or_start_agent()" in content:
        print("⚠️  Bridge already installed!")
        print("   Skipping installation to avoid duplicates.")
        return True
    print("✅ Bridge not found - will install")
    print()
    
    # Step 5: Add bridge code
    print("Step 5: Adding bridge code at end of file...")
    try:
        with open(SERVER_FILE, 'a') as f:
            f.write(BRIDGE_CODE)
        print("✅ Bridge code added")
    except Exception as e:
        print(f"❌ ERROR writing file: {e}")
        print("   Restoring backup...")
        shutil.copy2(BACKUP_FILE, SERVER_FILE)
        return False
    print()
    
    # Step 6: Validate syntax
    print("Step 6: Validating Python syntax...")
    import py_compile
    try:
        py_compile.compile(SERVER_FILE, doraise=True)
        print("✅ Syntax OK!")
    except Exception as e:
        print(f"❌ SYNTAX ERROR: {e}")
        print("   Restoring backup...")
        shutil.copy2(BACKUP_FILE, SERVER_FILE)
        return False
    print()
    
    # Success!
    print("="*60)
    print("✅ INSTALLATION COMPLETE!")
    print("="*60)
    print()
    print("Next steps:")
    print("  1. Start API: python3 -m jagabot.api.server &")
    print("  2. Wait 5 seconds")
    print("  3. Test: curl http://localhost:8000/health")
    print("  4. Test: curl -X POST http://localhost:8000/execute -d '{\"prompt\":\"test\"}'")
    print()
    print(f"Backup saved at: {BACKUP_FILE}")
    print("If something goes wrong, run:")
    print(f"  cp {BACKUP_FILE} {SERVER_FILE}")
    print()
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
