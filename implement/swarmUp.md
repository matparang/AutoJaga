📋 SCOPE PROMPT: JAGABOT v3.4 Phase 1 - LabService for Monte Carlo

```markdown
# SCOPE: JAGABOT v3.4 Phase 1 - LabService MVP for Monte Carlo

## CURRENT STATE
✅ JAGABOT v3.3 complete (1147 tests, 32 tools, Lab UI)
✅ Subagents can spawn and execute tools directly
✅ Parallel execution possible with multiple subagents
✅ Docker sandbox for secure execution

⏳ TARGET: Centralized LabService for tool execution starting with monte_carlo

## OBJECTIVE
Build a minimal LabService that:

1. Provides centralized tool execution (subagents call Lab instead of direct tools)
2. Validates parameters before execution
3. Executes in sandbox
4. Returns standardized results
5. Logs all executions
6. Works with monte_carlo tool first (expand later)

## NEW COMPONENTS

### 1. LabService Core
```python
# jagabot/lab/service.py

import asyncio
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

from jagabot.tools import get_tool
from jagabot.sandbox.executor import SafePythonExecutor
from jagabot.ui.lab.tool_registry import LabToolRegistry

class LabService:
    """
    Centralized tool execution service for subagents
    Phase 1: Monte Carlo only
    """
    
    def __init__(self):
        self.sandbox = SafePythonExecutor()
        self.registry = LabToolRegistry()
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.log_dir = Path.home() / '.jagabot' / 'lab_logs'
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    async def execute(self, tool_name: str, params: Dict[str, Any], 
                     timeout: int = 30) -> Dict[str, Any]:
        """
        Execute a tool with parameters
        
        Args:
            tool_name: Name of tool (e.g., 'monte_carlo')
            params: Tool parameters
            timeout: Execution timeout in seconds
        
        Returns:
            Standardized result dict
        """
        start_time = time.time()
        execution_id = f"{tool_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Step 1: Validate tool exists
            if tool_name != 'monte_carlo':
                return {
                    'success': False,
                    'error': f'Tool {tool_name} not supported in Phase 1',
                    'execution_id': execution_id
                }
            
            # Step 2: Validate parameters against registry
            validation = self.validate_params(tool_name, params)
            if not validation['valid']:
                return {
                    'success': False,
                    'error': validation['error'],
                    'execution_id': execution_id
                }
            
            # Step 3: Execute in sandbox
            code = self.generate_code(tool_name, params)
            result = await self.sandbox.execute(code, timeout=timeout)
            
            # Step 4: Parse and validate output
            if result['success']:
                try:
                    output = json.loads(result['stdout'])
                except:
                    output = {'raw': result['stdout']}
            else:
                output = {'error': result['stderr']}
            
            # Step 5: Log execution
            self.log_execution(execution_id, tool_name, params, result, time.time() - start_time)
            
            return {
                'success': result['success'],
                'tool': tool_name,
                'output': output,
                'execution_id': execution_id,
                'execution_time': round(time.time() - start_time, 2),
                'sandbox_used': True
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'execution_id': execution_id,
                'execution_time': round(time.time() - start_time, 2)
            }
    
    def validate_params(self, tool_name: str, params: Dict) -> Dict:
        """Validate parameters against tool metadata"""
        metadata = self.registry.get_tool_metadata(tool_name)
        
        required = ['current_price', 'vix', 'target']
        for param in required:
            if param not in params:
                return {
                    'valid': False,
                    'error': f'Missing required parameter: {param}'
                }
        
        # Type validation
        try:
            float(params['current_price'])
            float(params['vix'])
            float(params['target'])
        except:
            return {
                'valid': False,
                'error': 'Parameters must be numbers'
            }
        
        # Range validation
        if params['vix'] < 0 or params['vix'] > 100:
            return {
                'valid': False,
                'error': 'VIX must be between 0 and 100'
            }
        
        return {'valid': True}
    
    def generate_code(self, tool_name: str, params: Dict) -> str:
        """Generate Python code for execution"""
        if tool_name == 'monte_carlo':
            return f"""
import json
from jagabot.tools import monte_carlo

result = monte_carlo(
    current_price={params['current_price']},
    vix={params['vix']},
    target={params['target']},
    days={params.get('days', 30)},
    simulations={params.get('simulations', 100000)}
)

# Ensure JSON serializable
print(json.dumps({{
    'probability': result['probability'],
    'ci_95': result['ci_95'],
    'mean': result['mean'],
    'median': result['median'],
    'p5': result['p5'],
    'p95': result['p95']
}}))
"""
        raise ValueError(f"Code generation not implemented for {tool_name}")
    
    def log_execution(self, exec_id: str, tool: str, params: Dict, 
                      result: Dict, duration: float):
        """Log execution to file"""
        log_entry = {
            'execution_id': exec_id,
            'tool': tool,
            'params': params,
            'success': result.get('success', False),
            'duration': duration,
            'timestamp': datetime.now().isoformat()
        }
        
        log_file = self.log_dir / f"{exec_id}.json"
        with open(log_file, 'w') as f:
            json.dump(log_entry, f, indent=2)
    
    async def execute_parallel(self, tasks: list) -> list:
        """
        Execute multiple tools in parallel
        Phase 2 feature - placeholder for now
        """
        # Will implement in Phase 2
        results = []
        for task in tasks:
            result = await self.execute(task['tool'], task['params'])
            results.append(result)
        return results
```

2. Updated Subagent Base

```python
# jagabot/subagents/base.py (updated)

from jagabot.lab.service import LabService

class Subagent:
    """Base class for all subagents with Lab integration"""
    
    def __init__(self):
        self.lab = LabService()  # Use Lab instead of direct tools
    
    async def execute_tool(self, tool_name: str, params: dict):
        """Execute tool via LabService"""
        return await self.lab.execute(tool_name, params)
```

3. Example: Updated Monte Carlo Subagent

```python
# jagabot/subagents/monte_carlo.py (updated)

class MonteCarloSubagent(Subagent):
    async def run(self, data):
        # Instead of calling tool directly:
        # result = monte_carlo(...)
        
        # Now call via Lab:
        result = await self.execute_tool('monte_carlo', {
            'current_price': data['price'],
            'vix': data['vix'],
            'target': data['target'],
            'days': data.get('days', 30)
        })
        
        return result
```

4. Test Script

```python
# tests/test_lab_service.py

import pytest
from jagabot.lab.service import LabService

@pytest.mark.asyncio
async def test_lab_service_monte_carlo():
    lab = LabService()
    
    result = await lab.execute('monte_carlo', {
        'current_price': 76.50,
        'vix': 52,
        'target': 70,
        'days': 30,
        'simulations': 100000
    })
    
    assert result['success'] is True
    assert 'probability' in result['output']
    assert 33.0 < result['output']['probability'] < 35.0
    assert result['execution_time'] < 5.0

@pytest.mark.asyncio
async def test_lab_service_validation():
    lab = LabService()
    
    # Missing parameter
    result = await lab.execute('monte_carlo', {
        'current_price': 76.50
        # missing vix and target
    })
    assert result['success'] is False
    assert 'Missing required parameter' in result['error']
    
    # Invalid VIX
    result = await lab.execute('monte_carlo', {
        'current_price': 76.50,
        'vix': 200,
        'target': 70
    })
    assert result['success'] is False
    assert 'VIX must be between 0 and 100' in result['error']

@pytest.mark.asyncio
async def test_lab_service_unsupported_tool():
    lab = LabService()
    
    result = await lab.execute('var', {'portfolio': 1000000})
    assert result['success'] is False
    assert 'not supported in Phase 1' in result['error']
```

NEW FILES TO CREATE

1. jagabot/lab/service.py - LabService core
2. jagabot/lab/__init__.py - Package init
3. jagabot/subagents/base.py - Updated with Lab integration
4. jagabot/subagents/monte_carlo.py - Updated example
5. tests/test_lab_service.py - 10+ tests

FILES TO MODIFY

1. jagabot/subagents/__init__.py - Update imports
2. jagabot/subagents/manager.py - Use Lab for tool execution
3. CHANGELOG.md - v3.4 Phase 1

SUCCESS CRITERIA

✅ LabService executes monte_carlo correctly (34.24% ±0.5%)
✅ Parameter validation works (missing params, invalid ranges)
✅ Logs created in ~/.jagabot/lab_logs/
✅ Subagents can call Lab instead of direct tools
✅ 10+ new tests passing
✅ All existing 1147 tests still pass
✅ No regression in other tools

TIMELINE

Task Hours
LabService core 3
Parameter validation 2
Code generation 2
Logging 1
Update subagent base 2
Update monte_carlo subagent 1
Tests (10+) 3
Integration 2
TOTAL 16 hours

```

---

**This SCOPE will give JAGABOT a centralized LabService for tool execution, starting with monte_carlo. Perfect for Phase 1 MVP.** 🚀
