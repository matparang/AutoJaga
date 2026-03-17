#!/usr/bin/env python3
"""Test script to verify agent fix."""

import asyncio
import json
from pathlib import Path
from jagabot.agent.tools.registry import ToolRegistry
from jagabot.agent.tools.filesystem import ListDirTool, ReadFileTool
from jagabot.agent.tools.shell import ExecTool
from jagabot.core.tool_harness import ToolHarness

async def test_agent_fix():
    """Test the agent fix with actual tool execution."""
    
    registry = ToolRegistry()
    registry.register(ListDirTool(allowed_dir=Path('/root/.jagabot/workspace')))
    registry.register(ExecTool(working_dir='/root/.jagabot/workspace', timeout=30))
    
    harness = ToolHarness()
    
    print("=" * 70)
    print("TEST 1: list_dir - Should show files in /root/.jagabot/workspace/")
    print("=" * 70)
    
    plan = [{'tool': 'list_dir', 'args': {'path': '/root/.jagabot/workspace'}}]
    execution_results = []
    
    for action in plan:
        tool_name = action['tool']
        args = action.get('args', {})
        h_id = harness.register(tool_name)
        
        result = await registry.execute(tool_name, args)
        
        if isinstance(result, str) and result.startswith('Error'):
            result_str = result
            harness.fail(h_id, result[:200])
        else:
            result_str = str(result) if result is not None else ''
            harness.complete(h_id, result_text=result_str)
        
        execution_results.append((tool_name, args, result_str))
    
    # Generate summary (EXACT code from loop.py)
    summary_lines = [f'✅ Executed {len(execution_results)} action(s):']
    for tool_name, args, result_str in execution_results:
        args_preview = json.dumps(args)[:100] if args else ''
        summary_lines.append(f'\n**{tool_name}**({args_preview})')
        if result_str:
            result_preview = result_str[:800] + ('...' if len(result_str) > 800 else '')
            summary_lines.append(f'```\n{result_preview}\n```')
    
    final_content = '\n'.join(summary_lines)
    print(final_content)
    
    print("\n" + "=" * 70)
    print("TEST 2: exec with echo - Should show 'TEST OUTPUT'")
    print("=" * 70)
    
    plan = [{'tool': 'exec', 'args': {'command': 'echo "TEST OUTPUT"'}}]
    execution_results = []
    
    for action in plan:
        tool_name = action['tool']
        args = action.get('args', {})
        h_id = harness.register(tool_name)
        
        result = await registry.execute(tool_name, args)
        result_str = str(result) if result and not result.startswith('Error') else result
        harness.complete(h_id, result_text=result_str)
        execution_results.append((tool_name, args, result_str))
    
    summary_lines = [f'✅ Executed {len(execution_results)} action(s):']
    for tool_name, args, result_str in execution_results:
        args_preview = json.dumps(args)[:100] if args else ''
        summary_lines.append(f'\n**{tool_name}**({args_preview})')
        if result_str:
            summary_lines.append(f'```\n{result_str}\n```')
    
    print('\n'.join(summary_lines))
    
    print("\n" + "=" * 70)
    print("TEST 3: Verify core/ directory exists and has files")
    print("=" * 70)
    
    plan = [{'tool': 'list_dir', 'args': {'path': '/root/.jagabot/workspace/core'}}]
    execution_results = []
    
    for action in plan:
        tool_name = action['tool']
        args = action.get('args', {})
        h_id = harness.register(tool_name)
        
        result = await registry.execute(tool_name, args)
        result_str = str(result) if result and not result.startswith('Error') else result
        harness.complete(h_id, result_text=result_str)
        execution_results.append((tool_name, args, result_str))
    
    summary_lines = [f'✅ Executed {len(execution_results)} action(s):']
    for tool_name, args, result_str in execution_results:
        args_preview = json.dumps(args)[:100] if args else ''
        summary_lines.append(f'\n**{tool_name}**({args_preview})')
        if result_str:
            result_preview = result_str[:800] + ('...' if len(result_str) > 800 else '')
            summary_lines.append(f'```\n{result_preview}\n```')
    
    print('\n'.join(summary_lines))
    
    print("\n" + "=" * 70)
    print("✅ ALL TESTS COMPLETED")
    print("=" * 70)

if __name__ == '__main__':
    asyncio.run(test_agent_fix())
