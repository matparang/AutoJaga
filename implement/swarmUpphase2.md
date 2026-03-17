📋 SCOPE PROMPT: JAGABOT v3.4 Phase 2 - ParallelLab Execution

```markdown
# SCOPE: JAGABOT v3.4 Phase 2 - ParallelLab for Concurrent Tool Execution

## CURRENT STATE
✅ v3.4 Phase 1 complete:
- LabService centralizes tool execution (32 tools)
- BaseSubagent uses execute_tool() via Lab
- 1167 tests passing
- Direct execution default (fast), sandbox opt-in

⏳ TARGET: Parallel execution of multiple tools via Lab

## OBJECTIVE
Extend LabService to support parallel tool execution:

1. Submit multiple tools simultaneously
2. Run in parallel threads/processes
3. Aggregate results intelligently
4. Handle partial failures gracefully
5. Maintain performance (2-3x speedup)

## NEW COMPONENTS

### 1. ParallelLab Extension
```python
# jagabot/lab/parallel.py

import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import List, Dict, Any, Callable
from datetime import datetime
import json

from jagabot.lab.service import LabService

class ParallelLab(LabService):
    """
    Extended LabService with parallel execution capabilities
    """
    
    def __init__(self, max_workers: int = 4, use_processes: bool = False):
        super().__init__()
        self.max_workers = max_workers
        self.executor = ProcessPoolExecutor(max_workers=max_workers) if use_processes else ThreadPoolExecutor(max_workers=max_workers)
        self.task_queue = []
        self.results = {}
    
    async def submit_tasks(self, tasks: List[Dict[str, Any]]) -> str:
        """
        Submit multiple tools for parallel execution
        
        Args:
            tasks: List of task dicts, each with:
                - tool: tool name (e.g., 'monte_carlo')
                - params: parameters dict
                - priority: optional (1-10, higher = sooner)
                - sandbox: optional bool (default False)
        
        Returns:
            batch_id for tracking
        """
        batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Sort by priority if provided
        sorted_tasks = sorted(tasks, 
                            key=lambda x: x.get('priority', 5), 
                            reverse=True)
        
        self.task_queue.append({
            'batch_id': batch_id,
            'tasks': sorted_tasks,
            'status': 'pending',
            'submitted': datetime.now().isoformat()
        })
        
        # Submit to executor
        futures = []
        for task in sorted_tasks:
            future = self.executor.submit(
                self._execute_single,
                task['tool'],
                task['params'],
                task.get('sandbox', False)
            )
            futures.append(future)
        
        # Store for result collection
        self.results[batch_id] = {
            'futures': futures,
            'tasks': sorted_tasks,
            'completed': 0,
            'failed': 0,
            'results': []
        }
        
        return batch_id
    
    def _execute_single(self, tool: str, params: dict, sandbox: bool) -> dict:
        """Synchronous wrapper for async execute"""
        import asyncio
        return asyncio.run(self.execute(tool, params, sandbox=sandbox))
    
    async def get_results(self, batch_id: str, timeout: int = 30) -> Dict:
        """
        Collect results for a batch
        
        Args:
            batch_id: from submit_tasks()
            timeout: max seconds to wait
        
        Returns:
            Dict with all results + metadata
        """
        if batch_id not in self.results:
            return {'error': f'Batch {batch_id} not found'}
        
        batch = self.results[batch_id]
        futures = batch['futures']
        
        # Wait for all to complete with timeout
        import concurrent.futures
        done, not_done = concurrent.futures.wait(
            futures, 
            timeout=timeout,
            return_when=concurrent.futures.ALL_COMPLETED
        )
        
        # Collect results
        results = []
        for i, future in enumerate(futures):
            if future in done:
                try:
                    result = future.result()
                    results.append({
                        'task': batch['tasks'][i],
                        'success': True,
                        'result': result,
                        'execution_time': result.get('execution_time', 0)
                    })
                    batch['completed'] += 1
                except Exception as e:
                    results.append({
                        'task': batch['tasks'][i],
                        'success': False,
                        'error': str(e)
                    })
                    batch['failed'] += 1
            else:
                results.append({
                    'task': batch['tasks'][i],
                    'success': False,
                    'error': 'timeout'
                })
                batch['failed'] += 1
                future.cancel()
        
        batch['results'] = results
        batch['status'] = 'complete' if not not_done else 'partial'
        
        return {
            'batch_id': batch_id,
            'status': batch['status'],
            'total': len(futures),
            'completed': batch['completed'],
            'failed': batch['failed'],
            'results': results,
            'execution_time': sum(r.get('execution_time', 0) for r in results if r.get('success'))
        }
    
    async def execute_workflow(self, workflow: str, data: dict) -> Dict:
        """
        Execute predefined workflows in parallel
        
        Workflows:
        - 'risk_analysis': monte_carlo + var + stress_test
        - 'portfolio_review': portfolio_analyzer + correlation + recovery_time
        - 'full_analysis': all 8 risk tools
        """
        workflows = {
            'risk_analysis': [
                {'tool': 'monte_carlo', 'params': data.get('mc_params', {})},
                {'tool': 'var', 'params': data.get('var_params', {})},
                {'tool': 'stress_test', 'params': data.get('stress_params', {})}
            ],
            'portfolio_review': [
                {'tool': 'portfolio_analyzer', 'params': data.get('portfolio_params', {})},
                {'tool': 'correlation', 'params': data.get('correlation_params', {})},
                {'tool': 'recovery_time', 'params': data.get('recovery_params', {})}
            ],
            'full_analysis': [
                {'tool': 'monte_carlo', 'params': data.get('mc_params', {})},
                {'tool': 'var', 'params': data.get('var_params', {})},
                {'tool': 'cvar', 'params': data.get('cvar_params', {})},
                {'tool': 'stress_test', 'params': data.get('stress_params', {})},
                {'tool': 'correlation', 'params': data.get('correlation_params', {})},
                {'tool': 'recovery_time', 'params': data.get('recovery_params', {})},
                {'tool': 'financial_cv', 'params': data.get('cv_params', {})},
                {'tool': 'decision_engine', 'params': data.get('decision_params', {})}
            ]
        }
        
        if workflow not in workflows:
            return {'error': f'Unknown workflow: {workflow}'}
        
        batch_id = await self.submit_tasks(workflows[workflow])
        return await self.get_results(batch_id)
```

2. Updated Subagent Manager for Parallel

```python
# jagabot/subagents/manager.py (updated)

from jagabot.lab.parallel import ParallelLab

class SubagentManager:
    def __init__(self):
        self.lab = ParallelLab(max_workers=8)
        self.active_batches = {}
    
    async def run_parallel_analysis(self, analysis_type: str, data: dict):
        """
        Run multiple tools in parallel for faster analysis
        """
        # Submit all tasks at once
        batch_id = await self.lab.submit_tasks([
            {'tool': 'monte_carlo', 'params': data['mc_params'], 'priority': 10},
            {'tool': 'var', 'params': data['var_params'], 'priority': 8},
            {'tool': 'cvar', 'params': data['cvar_params'], 'priority': 8},
            {'tool': 'stress_test', 'params': data['stress_params'], 'priority': 7},
            {'tool': 'correlation', 'params': data['correlation_params'], 'priority': 5}
        ])
        
        self.active_batches[batch_id] = {
            'type': analysis_type,
            'start': datetime.now()
        }
        
        # Wait for results (non-blocking)
        results = await self.lab.get_results(batch_id)
        
        return self._format_parallel_results(results)
    
    def get_batch_status(self, batch_id: str):
        """Check progress of parallel execution"""
        if batch_id in self.lab.results:
            batch = self.lab.results[batch_id]
            return {
                'batch_id': batch_id,
                'completed': batch['completed'],
                'total': len(batch['futures']),
                'failed': batch['failed'],
                'progress': f"{batch['completed']}/{len(batch['futures'])}"
            }
        return {'error': 'Batch not found'}
```

3. CLI Commands for Parallel Execution

```python
# jagabot/cli/lab.py (new)

@cli.group()
def lab():
    """Lab service commands"""
    pass

@lab.command()
@click.option('--workflow', type=click.Choice(['risk', 'portfolio', 'full']))
@click.option('--params', help='JSON file with parameters')
def run_parallel(workflow, params):
    """Run multiple tools in parallel"""
    import json
    from jagabot.lab.parallel import ParallelLab
    
    lab = ParallelLab()
    
    with open(params) as f:
        data = json.load(f)
    
    if workflow == 'risk':
        tasks = [
            {'tool': 'monte_carlo', 'params': data['mc']},
            {'tool': 'var', 'params': data['var']},
            {'tool': 'stress_test', 'params': data['stress']}
        ]
    # ... etc
    
    batch_id = asyncio.run(lab.submit_tasks(tasks))
    click.echo(f"✅ Submitted batch: {batch_id}")
    click.echo("Use 'lab status <batch_id>' to check progress")

@lab.command()
@click.argument('batch_id')
def status(batch_id):
    """Check parallel execution status"""
    from jagabot.lab.parallel import ParallelLab
    
    lab = ParallelLab()
    status = lab.get_batch_status(batch_id)
    
    click.echo(json.dumps(status, indent=2))
```

4. Performance Tests

```python
# tests/test_parallel_lab.py

import pytest
import asyncio
from jagabot.lab.parallel import ParallelLab

@pytest.mark.asyncio
async def test_parallel_execution():
    lab = ParallelLab(max_workers=3)
    
    tasks = [
        {'tool': 'monte_carlo', 'params': {'current_price': 76.5, 'vix': 52, 'target': 70}},
        {'tool': 'var', 'params': {'portfolio_value': 2_909_093, 'volatility': 0.52}},
        {'tool': 'stress_test', 'params': {'current_equity': 1_109_092, 'current_price': 76.5, 'stress_price': 65, 'units': 21307}}
    ]
    
    batch_id = await lab.submit_tasks(tasks)
    results = await lab.get_results(batch_id)
    
    assert results['completed'] == 3
    assert results['failed'] == 0
    assert results['execution_time'] < max(t['execution_time'] for t in tasks) * 1.5  # Parallel should be faster

@pytest.mark.asyncio
async def test_workflow_execution():
    lab = ParallelLab()
    
    data = {
        'mc_params': {'current_price': 76.5, 'vix': 52, 'target': 70},
        'var_params': {'portfolio_value': 2_909_093, 'volatility': 0.52},
        'stress_params': {'current_equity': 1_109_092, 'current_price': 76.5, 'stress_price': 65, 'units': 21307}
    }
    
    results = await lab.execute_workflow('risk_analysis', data)
    assert results['status'] == 'complete'
    assert len(results['results']) == 3
```

NEW FILES TO CREATE

1. jagabot/lab/parallel.py - ParallelLab extension
2. jagabot/cli/lab.py - CLI commands for parallel
3. tests/test_parallel_lab.py - 15+ tests

FILES TO MODIFY

1. jagabot/subagents/manager.py - Add parallel support
2. jagabot/cli/__init__.py - Register lab commands
3. CHANGELOG.md - v3.4 Phase 2
4. tests/test_lab_service.py - Update existing tests

SUCCESS CRITERIA

✅ Parallel execution of 3+ tools completes in < 3s
✅ All tools return correct results (match ground truth)
✅ Partial failures handled gracefully
✅ Workflow shortcuts work (risk_analysis, portfolio_review)
✅ CLI commands functional
✅ 15+ new tests passing
✅ Total tests: 1182+

PERFORMANCE TARGETS

Workflow Sequential Parallel Speedup
Risk Analysis (3 tools) ~4.5s ~1.8s 2.5x
Portfolio Review (3 tools) ~3.8s ~1.5s 2.5x
Full Analysis (8 tools) ~12s ~3.5s 3.4x

TIMELINE

Component Hours
ParallelLab core 4
Task submission 2
Result aggregation 2
Workflow shortcuts 2
CLI commands 2
Tests (15+) 4
Integration 2
TOTAL 18 hours

```

---

**Phase 2 will give JAGABOT 2-3x speedup for multi-tool analysis!** 🚀
