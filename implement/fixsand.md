📋 SCOPE PROMPT: Fix Jagabot Sandbox Integration & Add Sandbox CLI

```markdown
# SCOPE: Jagabot Sandbox Integration & CLI Tools

## SITUATION
Jagabot v2.2 has Docker sandbox implemented but:
1. ❌ No `jagabot sandbox` CLI command to test/check status
2. ❌ Subagents not consistently using sandbox for ALL calculations
3. ❌ Basic math (equity, loss) still hallucinated (not using sandbox)
4. ❌ No way to verify sandbox is actually being used
5. ❌ Docker permission issues cause hanging (already fixed manually)

## OBJECTIVE
Create complete sandbox integration with:
1. **Sandbox CLI** - Commands to test, check status, configure
2. **Force ALL subagents** to use sandbox for EVERY calculation
3. **Verification layer** - Confirm sandbox execution in logs
4. **Fallback handling** - Graceful degradation if Docker unavailable
5. **Timeout management** - Prevent hanging (like the 10min stuck)

## REQUIRED COMPONENTS

### PART 1: Sandbox CLI (New)
Create `jagabot/cli/sandbox.py` with these commands:

```python
# jagabot/cli/sandbox.py
"""
Sandbox CLI commands for Jagabot
"""

@cli.group()
def sandbox():
    """Manage Docker sandbox for secure code execution"""
    pass

@sandbox.command()
def status():
    """Check sandbox status and configuration"""
    # Check Docker installed?
    # Check user in docker group?
    # Check permissions?
    # Show current timeout/memory settings
    # Output formatted table

@sandbox.command()
@click.option('--timeout', default=5, help='Timeout in seconds')
def test(timeout):
    """Test sandbox with simple Python execution"""
    # Run "print(2+2)" in sandbox
    # Measure response time
    # Return success/failure with details

@sandbox.command()
def config():
    """Show current sandbox configuration"""
    # Show timeout, memory limit, CPU limit
    # Show fallback settings
    # Show Docker image used

@sandbox.command()
@click.option('--timeout', type=int, help='Set timeout in seconds')
@click.option('--memory', help='Set memory limit (e.g., "128m")')
@click.option('--cpus', type=float, help='Set CPU limit')
def set(timeout, memory, cpus):
    """Configure sandbox settings"""
    # Update config file with new settings

@sandbox.command()
def logs():
    """Show recent sandbox execution logs"""
    # Tail last 50 sandbox executions
    # Show which subagents used sandbox
    # Show any errors

@sandbox.command()
def force_fallback():
    """Temporarily force fallback mode (no Docker)"""
    # Switch to subprocess mode for testing
```

PART 2: Force ALL Subagents to Use Sandbox

Update ALL subagent prompts to MANDATE sandbox usage:

```python
# jagabot/guardian/subagents/financial.py - UPDATED PROMPT
SUBAGENT_FINANCIAL_PROMPT = """
You are a FINANCIAL CALCULATION expert.

🚫 **STRICT RULES - NO EXCEPTIONS:**
1. **EVERY** calculation - including basic math - MUST use the sandbox
2. NEVER output a number without sandbox execution proof
3. Equity calculation MUST be step-by-step in Python
4. Loss calculation MUST use exact formulas
5. If sandbox fails 3 times, report "UNABLE TO CALCULATE"

✅ **CORRECT BEHAVIOR:**
[I will calculate equity in sandbox...]
```python
units_wti = 600000 / 85
current_value = units_wti * 72.50
equity = current_value + ...  # step by step
print(f"Equity: ${equity:.0f}")
```

[Sandbox output: Equity: $368,128]

❌ INCORRECT BEHAVIOR:
"Equity = $275,000" (no sandbox proof)

```

### PART 3: Sandbox Execution Tracker

```python
# jagabot/sandbox/tracker.py
"""
Track sandbox usage across all subagents
"""

class SandboxTracker:
    """Verify every calculation uses sandbox"""
    
    def __init__(self):
        self.executions = []
        self.db = sqlite3.connect('~/.jagabot/sandbox.db')
        self._init_db()
    
    def _init_db(self):
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS sandbox_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subagent TEXT,
                calculation_type TEXT,
                code_hash TEXT,
                success BOOLEAN,
                execution_time REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    
    def log_execution(self, subagent, calc_type, code, success, exec_time):
        """Log every sandbox execution"""
        code_hash = hashlib.md5(code.encode()).hexdigest()
        self.db.execute('''
            INSERT INTO sandbox_executions 
            (subagent, calculation_type, code_hash, success, execution_time)
            VALUES (?, ?, ?, ?, ?)
        ''', (subagent, calc_type, code_hash, success, exec_time))
        self.db.commit()
    
    def verify_all_calculations_used_sandbox(self, analysis_id):
        """Check if every calculation in an analysis used sandbox"""
        # Query to ensure no calculations were done outside sandbox
        pass
    
    def get_sandbox_usage_report(self):
        """Generate report of sandbox usage by subagent"""
        cursor = self.db.execute('''
            SELECT subagent, COUNT(*) as total, 
                   SUM(success) as successes,
                   AVG(execution_time) as avg_time
            FROM sandbox_executions
            GROUP BY subagent
        ''')
        return cursor.fetchall()
```

PART 4: Enhanced SafePythonExecutor

```python
# jagabot/sandbox/executor.py - ENHANCED
class SafePythonExecutor:
    """Enhanced with better timeout handling and verification"""
    
    def __init__(self, config):
        self.timeout = config.get('sandbox_timeout', 10)
        self.memory_limit = config.get('sandbox_memory', '128m')
        self.cpu_limit = config.get('sandbox_cpus', 0.5)
        self.tracker = SandboxTracker()
    
    async def execute(self, code, subagent=None, calc_type=None):
        """Execute with timeout and tracking"""
        
        start_time = time.time()
        
        try:
            # Run with timeout
            result = await asyncio.wait_for(
                self._run_in_docker(code),
                timeout=self.timeout
            )
            
            success = result['returncode'] == 0
            exec_time = time.time() - start_time
            
            # Track execution
            self.tracker.log_execution(
                subagent=subagent,
                calc_type=calc_type,
                code=code,
                success=success,
                exec_time=exec_time
            )
            
            return result
            
        except asyncio.TimeoutError:
            self.tracker.log_execution(
                subagent=subagent,
                calc_type=calc_type,
                code=code,
                success=False,
                exec_time=self.timeout
            )
            return {
                'success': False,
                'error': f'Execution timeout after {self.timeout}s'
            }
    
    async def _run_in_docker(self, code):
        """Run code in Docker with resource limits"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py') as f:
            f.write(code)
            f.flush()
            
            # Docker run with strict limits
            cmd = [
                "docker", "run", "--rm",
                "--network", "none",
                "--memory", self.memory_limit,
                "--cpus", str(self.cpu_limit),
                "--read-only",  # Read-only filesystem
                "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
                "-v", f"{f.name}:/script.py:ro",
                "python:3.10-slim",
                "python", "/script.py"
            ]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await proc.communicate()
            
            return {
                'success': proc.returncode == 0,
                'stdout': stdout.decode(),
                'stderr': stderr.decode(),
                'returncode': proc.returncode
            }
```

PART 5: Subagent Resilience with Sandbox

```python
# jagabot/guardian/subagents/resilience.py - UPDATED
class ResilientSubagent:
    """Subagent that ALWAYS uses sandbox with retry"""
    
    async def run_with_sandbox(self, task):
        """Run task with mandatory sandbox usage"""
        
        for attempt in range(3):
            # Generate code for this calculation
            code = await self.generate_code(task, attempt)
            
            # Execute in sandbox
            result = await self.sandbox.execute(
                code=code,
                subagent=self.name,
                calc_type=task['type']
            )
            
            if result['success']:
                # Parse and return
                return self.parse_output(result['stdout'])
            else:
                # Log error and retry
                error = result['stderr']
                task['last_error'] = error
        
        return {'error': f'Failed after 3 attempts. Last error: {error}'}
```

PART 6: Verification System

```python
# jagabot/sandbox/verifier.py
class SandboxVerifier:
    """Verify that ALL calculations used sandbox"""
    
    def verify_analysis(self, analysis_id):
        """Check if analysis used sandbox for every calculation"""
        
        # Get all expected calculations for this analysis
        expected = self.get_expected_calculations(analysis_id)
        
        # Get actual sandbox executions
        actual = self.tracker.get_executions_for_analysis(analysis_id)
        
        # Verify coverage
        missing = set(expected) - set(actual)
        
        if missing:
            return {
                'verified': False,
                'missing_calculations': list(missing),
                'message': f"❌ {len(missing)} calculations didn't use sandbox"
            }
        
        return {
            'verified': True,
            'total_calculations': len(expected),
            'message': "✅ ALL calculations used sandbox"
        }
```

PART 7: Configuration Updates

```yaml
# ~/.jagabot/config.yaml - ADD THESE SETTINGS

sandbox:
  enabled: true
  backend: docker  # or 'subprocess' for fallback
  timeout: 10  # seconds
  memory_limit: "128m"
  cpu_limit: 0.5
  docker_image: "python:3.10-slim"
  
  # Verification
  require_all_calculations: true
  log_all_executions: true
  fail_on_missing_sandbox: false  # Set to true for strict mode
  
  # Retry settings
  max_retries: 3
  retry_backoff: 1.5  # exponential backoff multiplier
```

PART 8: Tests

```python
# tests/test_sandbox/test_cli.py
def test_sandbox_status_command():
    """Test sandbox status CLI"""
    result = runner.invoke(sandbox, ['status'])
    assert 'Docker' in result.output
    assert 'running' in result.output.lower()

def test_sandbox_test_command():
    """Test sandbox test execution"""
    result = runner.invoke(sandbox, ['test', '--timeout', '5'])
    assert '4' in result.output  # 2+2 should be 4
    assert '✅' in result.output

# tests/test_sandbox/test_subagent_sandbox.py
def test_financial_subagent_uses_sandbox():
    """Verify financial subagent always uses sandbox"""
    analysis = run_analysis("Kira equity untuk modal 500k")
    verifier = SandboxVerifier()
    report = verifier.verify_analysis(analysis.id)
    assert report['verified'] is True
    assert 'equity' in [c['type'] for c in report['calculations']]
```

DELIVERABLES

1. ✅ Sandbox CLI - Complete with 6 commands (status, test, config, set, logs, force_fallback)
2. ✅ Updated Subagent Prompts - Force ALL calculations use sandbox
3. ✅ Sandbox Tracker - Log every execution for verification
4. ✅ Enhanced Executor - Better timeout, resource limits, read-only FS
5. ✅ Resilient Subagents - 3 retry attempts with error feedback
6. ✅ Verification System - Confirm every calculation used sandbox
7. ✅ Config Updates - All sandbox settings in YAML
8. ✅ Tests - 20+ new tests for sandbox functionality

SUCCESS CRITERIA

After implementation:

· jagabot sandbox status shows Docker running ✅
· jagabot sandbox test returns "4" in <2 seconds ✅
· Financial subagent equity calculation uses sandbox (check logs) ✅
· Risk subagent Monte Carlo uses sandbox (check logs) ✅
· All 4 subagents show sandbox usage in tracker ✅
· Verification report shows 100% sandbox usage ✅
· No more math hallucinations (equity = $368,128 not $275,000) ✅
· 10min hanging issue resolved (timeout at 10s) ✅

TIMELINE

Phase Component Est. Time
1 Sandbox CLI 2 days
2 Subagent Prompt Updates 1 day
3 Sandbox Tracker 1 day
4 Enhanced Executor 1 day
5 Resilience + Retry 1 day
6 Verification System 1 day
7 Tests 1 day
TOTAL  8 days

```

---

This SCOPE prompt gives Copilot everything needed to:
1. **Create sandbox CLI** commands
2. **Force ALL subagents** to use sandbox for every calculation
3. **Track and verify** sandbox usage
4. **Prevent hanging** with proper timeouts
5. **Add tests** for all new functionality

**Ready to fix the sandbox integration!** 🚀
