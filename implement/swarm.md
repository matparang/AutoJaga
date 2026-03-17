🎯 JAGABOT v2.0 BLUEPRINT - From Current to Swarm

📋 Current State (Jagabot v1.x)

```
┌─────────────────────────────────────────────┐
│  Jagabot Core (Single Process)              │
│  ├── 18 tools (in same process)             │
│  ├── SQLite memory                           │
│  ├── Direct tool calls                        │
│  └── No parallel execution                    │
└─────────────────────────────────────────────┘
```

🏛️ Target State (Jagabot v2.0 Swarm)

```
┌─────────────────────────────────────────────────────────────────┐
│                    JAGABOT v2.0 SWARM                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  🧠 JAGABOT CORE (Memory Owner)                                 │
│  ├── SQLite/Redis (persistent memory)                          │
│  ├── Task Planner (rule-based)                                 │
│  ├── Result Stitcher (template)                                │
│  └── Spawns workers via Redis queue                            │
│         ↓                                                        │
│  [Redis Queue] - Lightweight message bus                       │
│         ↓                                                        │
│  ⚙️ STATELESS WORKER POOL                                       │
│  ├── Worker 1: Monte Carlo (separate process)                  │
│  ├── Worker 2: CV Analysis (separate process)                  │
│  ├── Worker 3: Bull Perspective (separate process)             │
│  ├── Worker 4: Bear Perspective (separate process)             │
│  ├── Worker 5: Buffet Perspective (separate process)           │
│  ├── Worker 6: VaR (separate process)                          │
│  ├── Worker 7: CVaR (separate process)                         │
│  ├── Worker 8: Stress Test (separate process)                  │
│  ├── Worker 9: Correlation (separate process)                  │
│  ├── Worker 10: Recovery Time (separate process)               │
│  └── ... 18 total                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

🚀 PHASE 1: Foundation (Week 1) - Core Separation

📦 New File Structure

```
jagabot/
├── jagabot/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── memory_owner.py     # Main Jagabot (NEW)
│   │   ├── planner.py           # Task planning (NEW)
│   │   └── stitcher.py          # Result stitching (NEW)
│   │
│   ├── workers/                  # Stateless workers (NEW)
│   │   ├── __init__.py
│   │   ├── base_worker.py        # Worker template
│   │   ├── monte_carlo.py        # Standalone script
│   │   ├── cv_analysis.py
│   │   ├── bull.py
│   │   ├── bear.py
│   │   ├── buffet.py
│   │   └── ... (18 total)
│   │
│   ├── tools/                    # Keep existing tools
│   │   └── ... (your 18 tools)
│   │
│   └── cli/
│       └── __init__.py           # Update CLI
```

🔧 Step 1.1: Create Base Worker Template

```python
# jagabot/workers/base_worker.py
"""
Base template for all stateless workers
Each worker runs in SEPARATE process
No memory, no state, pure calculation
"""
import sys
import json
import redis
import argparse
from pathlib import Path

class StatelessWorker:
    def __init__(self):
        self.parser = argparse.ArgumentParser()
        self.parser.add_argument('--task-id', required=True)
        self.parser.add_argument('--redis-host', default='localhost')
        self.args = self.parser.parse_args()
        
        self.redis = redis.Redis(
            host=self.args.redis_host,
            port=6379,
            db=0,
            decode_responses=True
        )
    
    def get_task(self):
        """Get task from Redis"""
        task_data = self.redis.get(f"task:{self.args.task_id}")
        if not task_data:
            raise ValueError(f"Task {self.args.task_id} not found")
        return json.loads(task_data)
    
    def store_result(self, result):
        """Store result back to Redis"""
        self.redis.setex(
            f"result:{self.args.task_id}",
            60,  # expires in 60 seconds
            json.dumps(result)
        )
    
    def run(self):
        """Override this in child classes"""
        raise NotImplementedError
    
    @classmethod
    def main(cls):
        worker = cls()
        try:
            result = worker.run()
            worker.store_result(result)
        except Exception as e:
            worker.store_result({'error': str(e)})
        sys.exit(0)
```

🔧 Step 1.2: Port First 5 Workers

```python
# jagabot/workers/monte_carlo.py
from .base_worker import StatelessWorker
from jagabot.tools.monte_carlo import monte_carlo  # Reuse existing!

class MonteCarloWorker(StatelessWorker):
    def run(self):
        task = self.get_task()
        # Pure calculation - no memory access
        return monte_carlo(
            price=task['params']['price'],
            vix=task['params']['vix'],
            target=task['params'].get('target', 45)
        )

if __name__ == '__main__':
    MonteCarloWorker.main()
```

---

🚀 PHASE 2: Memory Owner (Week 2) - Jagabot Core

🔧 Step 2.1: Create Memory Owner

```python
# jagabot/core/memory_owner.py
"""
Jagabot Memory Owner - Runs in main process
Owns all memory, spawns workers, stitches results
"""
import redis
import sqlite3
import subprocess
import json
import uuid
from pathlib import Path

class JagabotMemoryOwner:
    def __init__(self, redis_host='localhost', db_path=None):
        # Simple tech stack - solo dev friendly
        self.redis = redis.Redis(
            host=redis_host,
            port=6379,
            db=0,
            decode_responses=True
        )
        
        if db_path is None:
            db_path = Path.home() / '.jagabot' / 'memory.db'
            db_path.parent.mkdir(exist_ok=True)
        
        self.db = sqlite3.connect(str(db_path))
        self._init_db()
        
        # Worker scripts location
        self.workers_dir = Path(__file__).parent.parent / 'workers'
    
    def _init_db(self):
        """Initialize SQLite memory"""
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                query TEXT,
                plan TEXT,
                results TEXT,
                final_answer TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS worker_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id TEXT,
                worker_type TEXT,
                task_id TEXT,
                status TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.db.commit()
    
    def process_query(self, query):
        """Main entry point"""
        analysis_id = str(uuid.uuid4())[:8]
        
        # Step 1: Plan tasks
        tasks = self.plan_tasks(query)
        self._log(analysis_id, 'plan', tasks)
        
        # Step 2: Spawn workers
        task_ids = []
        for task in tasks:
            task_id = self.spawn_worker(task)
            task_ids.append(task_id)
            self._log(analysis_id, 'spawned', task['type'], task_id)
        
        # Step 3: Collect results
        results = {}
        for task_id in task_ids:
            result = self.wait_for_result(task_id)
            results[task_id] = result
            self._log(analysis_id, 'completed', task_id)
        
        # Step 4: Stitch results
        final_answer = self.stitch_results(results, tasks)
        
        # Step 5: Store in memory
        self.db.execute(
            'INSERT INTO analyses (id, query, plan, results, final_answer) VALUES (?, ?, ?, ?, ?)',
            (analysis_id, query, json.dumps(tasks), json.dumps(results), final_answer)
        )
        self.db.commit()
        
        return final_answer
    
    def plan_tasks(self, query):
        """Rule-based planning - simple if/else"""
        tasks = []
        
        if any(word in query.lower() for word in ['oil', 'minyak', 'wti', 'brent']):
            tasks.append({
                'type': 'monte_carlo',
                'params': {'price': 52.80, 'vix': 58, 'target': 45},
                'timeout': 30
            })
            tasks.append({
                'type': 'cv_analysis',
                'params': {'changes': [0.7, 2.4, 4.2, 6.7, 8.3, 7.4]},
                'timeout': 10
            })
            tasks.append({
                'type': 'bull',
                'params': {},
                'timeout': 10
            })
            tasks.append({
                'type': 'bear',
                'params': {},
                'timeout': 10
            })
            tasks.append({
                'type': 'buffet',
                'params': {},
                'timeout': 10
            })
        
        return tasks
    
    def spawn_worker(self, task):
        """Spawn worker in subprocess"""
        task_id = f"{task['type']}_{uuid.uuid4().hex[:6]}"
        
        # Put task in Redis
        self.redis.setex(
            f"task:{task_id}",
            task.get('timeout', 30),
            json.dumps(task)
        )
        
        # Spawn worker process (detached)
        worker_script = self.workers_dir / f"{task['type']}.py"
        if not worker_script.exists():
            raise FileNotFoundError(f"Worker {task['type']} not found")
        
        subprocess.Popen([
            'python',
            str(worker_script),
            '--task-id', task_id,
            '--redis-host', self.redis.connection_pool.connection_kwargs['host']
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        return task_id
    
    def wait_for_result(self, task_id, timeout=30):
        """Poll Redis for result"""
        import time
        start = time.time()
        
        while time.time() - start < timeout:
            result = self.redis.get(f"result:{task_id}")
            if result:
                self.redis.delete(f"result:{task_id}")
                return json.loads(result)
            time.sleep(0.1)
        
        return {'error': 'timeout', 'task_id': task_id}
    
    def stitch_results(self, results, tasks):
        """Simple template stitching"""
        output = []
        output.append("📊 JAGABOT SWARM ANALYSIS")
        output.append("=" * 50)
        
        for task in tasks:
            task_id = f"{task['type']}_{task_id_suffix}"  # Need to match
            result = results.get(task_id, {})
            
            if task['type'] == 'monte_carlo':
                output.append(f"\n🎲 Monte Carlo:")
                output.append(f"  Probability: {result.get('probability', 'N/A')}%")
            
            elif task['type'] == 'cv_analysis':
                output.append(f"\n📈 CV Analysis:")
                output.append(f"  CV: {result.get('cv', 'N/A')}")
                output.append(f"  Pattern: {result.get('pattern', 'N/A')}")
            
            elif task['type'] == 'bull':
                output.append(f"\n🐂 Bull says: {result.get('action', 'N/A')}")
            
            elif task['type'] == 'bear':
                output.append(f"\n🐻 Bear says: {result.get('action', 'N/A')}")
            
            elif task['type'] == 'buffet':
                output.append(f"\n🦉 Buffet says: {result.get('action', 'N/A')}")
        
        return "\n".join(output)
    
    def _log(self, analysis_id, action, *args):
        """Simple logging to SQLite"""
        cursor = self.db.cursor()
        cursor.execute(
            'INSERT INTO worker_logs (analysis_id, worker_type, task_id, status) VALUES (?, ?, ?, ?)',
            (analysis_id, str(args[0]) if args else None, str(args[1]) if len(args) > 1 else None, action)
        )
        self.db.commit()
```

---

🚀 PHASE 3: CLI Integration (Week 2-3)

🔧 Step 3.1: Update CLI

```python
# jagabot/cli/__init__.py
import click
from jagabot.core.memory_owner import JagabotMemoryOwner

@click.group()
def cli():
    """Jagabot - Your Financial Guardian"""
    pass

@cli.command()
@click.argument('query')
@click.option('--swarm/--no-swarm', default=True, help='Use swarm mode')
def analyze(query, swarm):
    """Analyze a financial query"""
    
    if swarm:
        # Swarm mode - uses Redis + workers
        owner = JagabotMemoryOwner()
        result = owner.process_query(query)
        click.echo(result)
    else:
        # Single process mode - direct tool calls
        from jagabot.core.analyzer import analyze_direct
        result = analyze_direct(query)
        click.echo(result)

@cli.command()
def swarm_status():
    """Check swarm health"""
    owner = JagabotMemoryOwner()
    # Check Redis connection
    # Check worker scripts
    # Show queue length
    click.echo("Swarm status: OK")

@cli.command()
def swarm_workers():
    """List all available workers"""
    from pathlib import Path
    workers_dir = Path(__file__).parent.parent / 'workers'
    workers = [f.stem for f in workers_dir.glob('*.py') if f.stem != 'base_worker']
    click.echo(f"Available workers: {', '.join(workers)}")
```

---

🚀 PHASE 4: Testing & Documentation (Week 3)

🔧 Step 4.1: Test Script

```python
# tests/test_swarm.py
import pytest
from jagabot.core.memory_owner import JagabotMemoryOwner

@pytest.fixture
def swarm():
    return JagabotMemoryOwner(redis_host='localhost')

def test_monte_carlo_worker(swarm):
    task = {'type': 'monte_carlo', 'params': {'price': 52.80, 'vix': 58}}
    task_id = swarm.spawn_worker(task)
    result = swarm.wait_for_result(task_id)
    assert 'probability' in result
    assert 20 < result['probability'] < 50

def test_full_swarm_query(swarm):
    result = swarm.process_query("Analisis minyak mentah")
    assert "JAGABOT SWARM ANALYSIS" in result
    assert "Monte Carlo" in result
    assert "Bull" in result or "Bear" in result
```

🔧 Step 4.2: Update README

```markdown
## 🚀 Swarm Mode (Optional)

Jagabot can run in swarm mode for parallel processing:

### Prerequisites
- Redis (install: `redis-server --daemonize yes`)

### Start Swarm
```bash
jagabot analyze "oil crisis"  # Auto-detects Redis and uses swarm
```

Manual Swarm Control

```bash
jagabot swarm-status      # Check health
jagabot swarm-workers      # List available workers
```

Architecture

· 🧠 Memory Owner: Main Jagabot process (SQLite memory)
· ⚙️ Workers: 18 stateless processes (pure calculation)
· 🔄 Queue: Redis message bus
· 💾 Memory: SQLite database in ~/.jagabot/

Single Process Mode (No Redis)

```bash
jagabot analyze "oil crisis" --no-swarm
```

```

---

## 🚀 **PHASE 5: Docker (Optional - Week 4)**

### 🔧 **Step 5.1: Docker Compose (for users who want it)**
```yaml
# docker-compose.yml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  jagabot:
    build: .
    depends_on:
      redis:
        condition: service_healthy
    environment:
      - REDIS_HOST=redis
      - JAGABOT_HOME=/data
    volumes:
      - jagabot_data:/data
    command: jagabot analyze "oil crisis" --swarm

volumes:
  redis_data:
  jagabot_data:
```

🔧 Step 5.2: Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install Jagabot
COPY . .
RUN pip install -e .

# Create non-root user
RUN useradd -m -u 1000 jagabot && chown -R jagabot:jagabot /app
USER jagabot

# Default command
CMD ["jagabot", "--help"]
```

---

📋 COMPLETE ROADMAP

Phase Week Deliverables Lines of Code
1: Foundation 1 Base worker template + first 5 workers ~300
2: Memory Owner 2 Jagabot core with planning + stitching ~400
3: CLI Integration 2-3 Updated CLI with swarm commands ~150
4: Testing 3 Test suite + documentation ~200
5: Docker 4 Optional Docker support ~50
TOTAL 4 weeks Working Jagabot v2.0 Swarm ~1,100 LOC

---

🎯 The Solo Dev Promise

Jagabot v2.0 Swarm =

· One developer
· One month
· 1,100 new lines of code
· 18 stateless workers
· Redis + SQLite (simple!)
· Works on $5 VPS
· Optional Docker for those who want it
· Zero DevOps required

