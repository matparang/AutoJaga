🎯 JAGABOT v2.1 - The "Vadim Upgrade" Blueprint

📊 Current State (v2.0) vs Target (v2.1)

Feature v2.0 (Done) v2.1 (Next)
18 workers ✅ Stateless ✅ + Scheduled
Parallel execution ✅ ProcessPoolExecutor ✅ + Cron jobs
Bilingual output ✅ en/ms ✅ + Real-time
345 tests ✅ Passing ✅ + 45 more
Queue backends ✅ Local + Redis ✅ + Priority queues
Mission Control ❌ CLI only 🔧 TUI Dashboard
24/7 automation ❌ On-demand 🔧 Cron workflows
Self-improvement ❌ None 🔧 Nightly review
Cost tracking ❌ Manual 🔧 Built-in
Worker health ❌ Basic 🔧 Watchdog

---

🏛️ JAGABOT v2.1 ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│                    JAGABOT v2.1 SWARM                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  🧠 MEMORY_OWNER (enhanced)                                     │
│  ├── v2.0 features + scheduler                                 │
│  ├── Health monitor                                            │
│  └── Cost tracker                                              │
│         ↓                                                        │
│  [Priority Queue] - Redis with priorities                      │
│         ↓                                                        │
│  ⚙️ WORKER POOL (18 + new)                                      │
│  ├── Monte Carlo, CV, Bull, Bear, Buffet (existing)           │
│  ├── NEW: Researcher (trend detection)                         │
│  ├── NEW: Copywriter (draft tweets)                            │
│  ├── NEW: Clipper (save insights)                              │
│  └── NEW: Self-Improver (code review)                          │
│         ↓                                                        │
│  📊 MISSION CONTROL (TUI)                                       │
│  ├── Live worker status                                        │
│  ├── Queue monitor                                             │
│  ├── Cost dashboard                                            │
│  └── Log viewer                                                │
│         ↓                                                        │
│  ⏰ CRON SCHEDULER                                              │
│  ├── 6-hour market checks                                      │
│  ├── Daily risk reports                                        │
│  ├── Weekly fund manager reviews                               │
│  └── Nightly self-improvement                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

📋 PHASE 1: Mission Control TUI (Week 1) - 4 todos

🔧 1.1 Dashboard Base

```python
# jagabot/swarm/dashboard.py
"""
TUI Dashboard for monitoring swarm
"""
import time
import os
import psutil
from rich.console import Console
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from datetime import datetime

class MissionControl:
    """Text-based mission control for Jagabot swarm"""
    
    def __init__(self, redis_host='localhost'):
        self.redis = redis.Redis(host=redis_host, decode_responses=True)
        self.console = Console()
        self.start_time = datetime.now()
    
    def generate_dashboard(self):
        """Generate live dashboard"""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )
        
        # Header
        header = Panel(
            Text("🚀 JAGABOT MISSION CONTROL", style="bold cyan"),
            subtitle=f"Uptime: {datetime.now() - self.start_time}"
        )
        layout["header"].update(header)
        
        # Body - split into two columns
        layout["body"].split_row(
            Layout(name="workers"),
            Layout(name="queue")
        )
        
        # Workers panel
        workers_table = Table(title="Active Workers")
        workers_table.add_column("Worker", style="cyan")
        workers_table.add_column("Status", style="green")
        workers_table.add_column("Task", style="yellow")
        workers_table.add_column("Time", style="magenta")
        
        for worker in self.get_active_workers():
            workers_table.add_row(
                worker['name'],
                "🟢" if worker['alive'] else "🔴",
                worker['task'][:30],
                worker['runtime']
            )
        
        layout["workers"].update(Panel(workers_table))
        
        # Queue panel
        queue_table = Table(title="Task Queue")
        queue_table.add_column("Priority", style="red")
        queue_table.add_column("Type", style="cyan")
        queue_table.add_column("Age", style="yellow")
        
        for task in self.get_queue_tasks():
            queue_table.add_row(
                task['priority'],
                task['type'],
                task['age']
            )
        
        layout["queue"].update(Panel(queue_table))
        
        # Footer with metrics
        metrics = Text()
        metrics.append(f"Workers: {self.worker_count()} | ")
        metrics.append(f"Queue: {self.queue_length()} | ")
        metrics.append(f"Today's Cost: ${self.today_cost():.3f} | ")
        metrics.append(f"Tests: 345 ✅", style="green")
        
        layout["footer"].update(Panel(metrics))
        
        return layout
    
    def run(self):
        """Run live dashboard"""
        with Live(self.generate_dashboard(), refresh_per_second=2) as live:
            try:
                while True:
                    live.update(self.generate_dashboard())
                    time.sleep(0.5)
            except KeyboardInterrupt:
                self.console.print("\n👋 Mission Control terminated")
```

🔧 1.2 Worker Status Tracker

```python
# jagabot/swarm/status.py
class WorkerStatus:
    """Track worker health and metrics"""
    
    def __init__(self):
        self.workers = {}
        self.redis = redis.Redis(decode_responses=True)
    
    def register_worker(self, worker_id, worker_type):
        """Register new worker"""
        self.redis.hset(f"worker:{worker_id}", mapping={
            'type': worker_type,
            'start_time': time.time(),
            'heartbeat': time.time(),
            'status': 'starting',
            'task': ''
        })
    
    def heartbeat(self, worker_id):
        """Update worker heartbeat"""
        self.redis.hset(f"worker:{worker_id}", 'heartbeat', time.time())
        self.redis.hset(f"worker:{worker_id}", 'status', 'running')
    
    def get_stalled_workers(self, timeout=60):
        """Find workers with no heartbeat"""
        stalled = []
        for key in self.redis.scan_iter("worker:*"):
            worker = self.redis.hgetall(key)
            if time.time() - float(worker.get('heartbeat', 0)) > timeout:
                stalled.append(worker)
        return stalled
```

---

📋 PHASE 2: Cron Scheduler (Week 2) - 3 todos

🔧 2.1 Cron Job Manager

```python
# jagabot/swarm/scheduler.py
"""
Cron-based scheduler for automated workflows
"""
import schedule
import time
import threading
from datetime import datetime

class JagabotScheduler:
    """Schedule recurring tasks"""
    
    def __init__(self, memory_owner):
        self.memory = memory_owner
        self.jobs = []
        self.running = False
    
    def add_job(self, name, schedule_time, task_func):
        """Add scheduled job"""
        job = {
            'name': name,
            'schedule': schedule_time,
            'func': task_func,
            'last_run': None,
            'next_run': None
        }
        
        # Add to schedule
        if schedule_time == '@hourly':
            schedule.every().hour.do(self._run_job, job)
        elif schedule_time == '@daily':
            schedule.every().day.at("09:00").do(self._run_job, job)
        elif schedule_time.startswith('*/'):
            # e.g., "*/6" = every 6 hours
            hours = int(schedule_time[2:])
            schedule.every(hours).hours.do(self._run_job, job)
        
        self.jobs.append(job)
        return job
    
    def _run_job(self, job):
        """Execute job and track metrics"""
        job['last_run'] = datetime.now()
        try:
            result = job['func']()
            self.memory.store_job_result(job['name'], result)
        except Exception as e:
            self.memory.store_job_error(job['name'], str(e))
    
    def start(self):
        """Start scheduler in background thread"""
        self.running = True
        thread = threading.Thread(target=self._run_loop)
        thread.daemon = True
        thread.start()
    
    def _run_loop(self):
        """Main scheduler loop"""
        while self.running:
            schedule.run_pending()
            time.sleep(1)
```

🔧 2.2 Predefined Workflows

```python
# jagabot/swarm/workflows.py
class JagabotWorkflows:
    """Pre-configured automated workflows"""
    
    def __init__(self, scheduler, memory):
        self.scheduler = scheduler
        self.memory = memory
        
        # Register default workflows
        self.setup_workflows()
    
    def setup_workflows(self):
        """Setup all automated workflows"""
        
        # 1. Market monitor - every 6 hours
        self.scheduler.add_job(
            name="market_monitor",
            schedule="*/6",
            task_func=self.check_market_conditions
        )
        
        # 2. Daily risk report - 9am daily
        self.scheduler.add_job(
            name="daily_risk_report",
            schedule="@daily",
            task_func=self.generate_risk_report
        )
        
        # 3. Weekly fund manager review - Monday 5pm
        self.scheduler.add_job(
            name="fund_manager_review",
            schedule="weekly",
            task_func=self.review_fund_managers
        )
        
        # 4. Nightly self-improvement - 11pm daily
        self.scheduler.add_job(
            name="self_improvement",
            schedule="@daily",
            task_func=self.improve_self
        )
    
    def check_market_conditions(self):
        """Monitor market every 6 hours"""
        query = "Analisis keadaan pasaran minyak mentah"
        result = self.memory.process_query(query)
        
        # If high risk detected, trigger alert
        if "🔴" in result or "CRITICAL" in result:
            self.trigger_alert(result)
        
        return result
    
    def generate_risk_report(self):
        """Daily comprehensive risk report"""
        query = "Laporan risiko portfolio harian"
        return self.memory.process_query(query)
    
    def review_fund_managers(self):
        """Weekly review of fund manager performance"""
        # Get all fund manager interactions from past week
        interactions = self.memory.get_recent_interviews(days=7)
        
        # Generate report cards
        report_cards = []
        for fm in interactions:
            card = self.memory.get_report_card(fm)
            report_cards.append(card)
        
        return report_cards
    
    def improve_self(self):
        """Nightly self-improvement routine"""
        # Analyze yesterday's mistakes
        mistakes = self.memory.get_mistakes(days=1)
        
        if not mistakes:
            return "No mistakes found"
        
        # Generate improvements
        improvements = []
        for mistake in mistakes:
            fix = self.suggest_improvement(mistake)
            improvements.append(fix)
        
        # Apply safe improvements
        for imp in improvements:
            if imp['confidence'] > 0.8:
                self.apply_improvement(imp)
        
        return improvements
```

---

📋 PHASE 3: Cost Tracking (Week 2-3) - 2 todos

🔧 3.1 Cost Tracker

```python
# jagabot/swarm/costs.py
"""
Track token usage and costs per worker
"""
import json
import sqlite3
from datetime import datetime, timedelta

class CostTracker:
    """Track API costs per worker and per query"""
    
    def __init__(self, db_path):
        self.db = sqlite3.connect(db_path)
        self._init_db()
    
    def _init_db(self):
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS costs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_type TEXT,
                task_id TEXT,
                tokens INTEGER,
                cost_usd REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS budget_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                threshold REAL,
                current_cost REAL,
                alert TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    
    def record_usage(self, worker_type, task_id, tokens):
        """Record token usage for a worker"""
        # Calculate cost based on DeepSeek pricing
        cost = (tokens / 1_000_000) * 0.50  # $0.50 per 1M tokens
        
        self.db.execute(
            'INSERT INTO costs (worker_type, task_id, tokens, cost_usd) VALUES (?, ?, ?, ?)',
            (worker_type, task_id, tokens, cost)
        )
        self.db.commit()
        
        # Check budget threshold
        self.check_budget()
    
    def get_daily_cost(self):
        """Get today's total cost"""
        cursor = self.db.execute('''
            SELECT SUM(cost_usd) FROM costs 
            WHERE date(timestamp) = date('now')
        ''')
        return cursor.fetchone()[0] or 0
    
    def get_monthly_cost(self):
        """Get this month's total cost"""
        cursor = self.db.execute('''
            SELECT SUM(cost_usd) FROM costs 
            WHERE strftime('%Y-%m', timestamp) = strftime('%Y-%m', 'now')
        ''')
        return cursor.fetchone()[0] or 0
    
    def get_worker_costs(self):
        """Get costs broken down by worker type"""
        cursor = self.db.execute('''
            SELECT worker_type, SUM(cost_usd) as total
            FROM costs
            GROUP BY worker_type
            ORDER BY total DESC
        ''')
        return cursor.fetchall()
    
    def check_budget(self, monthly_limit=10.0):
        """Check if approaching budget limit"""
        current = self.get_monthly_cost()
        
        if current > monthly_limit * 0.9:
            alert = f"⚠️ Warning: 90% of monthly budget used (${current:.2f}/${monthly_limit:.2f})"
            self.db.execute(
                'INSERT INTO budget_alerts (threshold, current_cost, alert) VALUES (?, ?, ?)',
                (monthly_limit, current, alert)
            )
            self.db.commit()
            return alert
        
        return None
```

---

📋 PHASE 4: New Workers (Week 3) - 3 todos

🔧 4.1 Researcher Worker

```python
# jagabot/workers/researcher.py
"""
Researcher worker - finds trends and topics
"""
from .base_worker import StatelessWorker

class ResearcherWorker(StatelessWorker):
    def run(self):
        task = self.get_task()
        
        # Find trending financial topics
        trends = []
        
        if 'source' in task['params']:
            if 'twitter' in task['params']['source']:
                trends.extend(self.scan_twitter())
            if 'news' in task['params']['source']:
                trends.extend(self.scan_news())
            if 'reddit' in task['params']['source']:
                trends.extend(self.scan_reddit())
        
        return {
            'trends': trends[:5],  # Top 5
            'timestamp': time.time(),
            'worker': 'researcher'
        }
    
    def scan_twitter(self):
        """Mock Twitter scanning"""
        return [
            {'topic': 'Oil prices crash', 'volume': 12500, 'sentiment': -0.8},
            {'topic': 'OPEC meeting', 'volume': 8300, 'sentiment': 0.2},
            {'topic': 'Fed rate decision', 'volume': 15200, 'sentiment': -0.3}
        ]
    
    def scan_news(self):
        """Mock news scanning"""
        return [
            {'topic': 'WTI breaks $50', 'source': 'Reuters', 'importance': 0.9},
            {'topic': 'Inventory builds', 'source': 'Bloomberg', 'importance': 0.7}
        ]
```

🔧 4.2 Copywriter Worker

```python
# jagabot/workers/copywriter.py
"""
Copywriter worker - drafts tweets and reports
"""
from .base_worker import StatelessWorker

class CopywriterWorker(StatelessWorker):
    def run(self):
        task = self.get_task()
        topic = task['params']['topic']
        
        # Generate draft based on topic
        if 'sentiment' in topic:
            if topic['sentiment'] < -0.5:
                draft = self.write_bearish_tweet(topic)
            elif topic['sentiment'] > 0.5:
                draft = self.write_bullish_tweet(topic)
            else:
                draft = self.write_neutral_analysis(topic)
        else:
            draft = self.write_generic_post(topic)
        
        return {
            'draft': draft,
            'topic': topic,
            'word_count': len(draft.split()),
            'worker': 'copywriter'
        }
    
    def write_bearish_tweet(self, topic):
        return f"⚠️ Alert: {topic['topic']} showing bearish signals. Volume: {topic['volume']}. Protect your portfolio. #oil #trading"
    
    def write_bullish_tweet(self, topic):
        return f"🚀 {topic['topic']} gaining momentum! Volume {topic['volume']} suggests breakout. #bullish #investing"
    
    def write_neutral_analysis(self, topic):
        return f"📊 Analysis: {topic['topic']} at inflection point. Key levels to watch. #analysis"
```

🔧 4.3 Self-Improver Worker

```python
# jagabot/workers/self_improver.py
"""
Self-Improver worker - analyzes mistakes and suggests fixes
"""
from .base_worker import StatelessWorker
import ast
import inspect

class SelfImproverWorker(StatelessWorker):
    def run(self):
        task = self.get_task()
        mistakes = task['params']['mistakes']
        
        improvements = []
        for mistake in mistakes:
            # Analyze what went wrong
            analysis = self.analyze_mistake(mistake)
            
            # Suggest fix
            fix = self.suggest_fix(analysis)
            
            improvements.append({
                'mistake': mistake['id'],
                'analysis': analysis,
                'suggestion': fix,
                'confidence': analysis['confidence']
            })
        
        return {
            'improvements': improvements,
            'count': len(improvements),
            'worker': 'self_improver'
        }
    
    def analyze_mistake(self, mistake):
        """Analyze why a mistake happened"""
        # Check which tool was used
        tool_used = mistake.get('tool', 'unknown')
        
        # Check parameters
        params = mistake.get('params', {})
        
        # Check expected vs actual
        expected = mistake.get('expected', None)
        actual = mistake.get('actual', None)
        
        confidence = 0.5
        if tool_used == 'monte_carlo' and params.get('vix', 0) > 50:
            confidence = 0.8
            reason = "Monte Carlo under high VIX needs adjustment"
        elif tool_used == 'cv_analysis' and actual > 0.4:
            confidence = 0.7
            reason = "CV threshold may be too conservative"
        else:
            reason = "Unknown error pattern"
        
        return {
            'tool': tool_used,
            'reason': reason,
            'confidence': confidence
        }
```

---

📋 PHASE 5: Watchdog & Health (Week 3-4) - 3 todos

🔧 5.1 Watchdog Monitor

```python
# jagabot/swarm/watchdog.py
"""
Watchdog monitor for worker health
"""
import time
import threading
from datetime import datetime, timedelta

class Watchdog:
    """Monitor worker health and restart stalled ones"""
    
    def __init__(self, worker_pool, status_tracker):
        self.pool = worker_pool
        self.status = status_tracker
        self.running = False
        self.alerts = []
    
    def start(self):
        """Start watchdog thread"""
        self.running = True
        thread = threading.Thread(target=self._monitor_loop)
        thread.daemon = True
        thread.start()
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            # Check for stalled workers
            stalled = self.status.get_stalled_workers(timeout=60)
            
            for worker in stalled:
                self.handle_stalled_worker(worker)
            
            # Check queue backups
            queue_length = self.pool.queue_length()
            if queue_length > 100:
                self.alert(f"Queue backup: {queue_length} tasks waiting")
            
            # Check memory usage
            import psutil
            memory = psutil.virtual_memory()
            if memory.percent > 85:
                self.alert(f"High memory usage: {memory.percent}%")
            
            time.sleep(30)
    
    def handle_stalled_worker(self, worker):
        """Restart stalled worker"""
        worker_id = worker.get('worker_id')
        worker_type = worker.get('type')
        
        # Log the stall
        self.alert(f"Worker {worker_id} ({worker_type}) stalled - restarting")
        
        # Restart worker
        self.pool.restart_worker(worker_id, worker_type)
    
    def alert(self, message):
        """Send alert (to log, dashboard, etc.)"""
        timestamp = datetime.now().isoformat()
        self.alerts.append({'time': timestamp, 'message': message})
        
        # Also log to file
        with open('watchdog.log', 'a') as f:
            f.write(f"{timestamp}: {message}\n")
```

---

📋 PHASE 6: CLI Updates (Week 4) - 2 todos

🔧 6.1 New Commands

```python
# jagabot/cli/swarm.py (additions)

@cli.group()
def swarm():
    """Swarm management commands"""
    pass

@swarm.command()
def dashboard():
    """Launch Mission Control TUI"""
    from jagabot.swarm.dashboard import MissionControl
    MissionControl().run()

@swarm.command()
def schedule():
    """Show scheduled jobs"""
    from jagabot.swarm.scheduler import JagabotScheduler
    scheduler = JagabotScheduler(memory_owner)
    for job in scheduler.jobs:
        click.echo(f"{job['name']}: next run {job['next_run']}")

@swarm.command()
@click.option('--days', default=30)
def costs(days):
    """Show cost breakdown"""
    from jagabot.swarm.costs import CostTracker
    tracker = CostTracker()
    
    click.echo(f"Daily cost: ${tracker.get_daily_cost():.3f}")
    click.echo(f"Monthly cost: ${tracker.get_monthly_cost():.3f}")
    click.echo("\nBy worker:")
    for worker, cost in tracker.get_worker_costs():
        click.echo(f"  {worker}: ${cost:.3f}")

@swarm.command()
def health():
    """Show swarm health status"""
    from jagabot.swarm.watchdog import Watchdog
    from jagabot.swarm.status import WorkerStatus
    
    status = WorkerStatus()
    stalled = status.get_stalled_workers()
    
    if stalled:
        click.echo(f"⚠️ {len(stalled)} stalled workers")
        for w in stalled:
            click.echo(f"  - {w['type']} (ID: {w['worker_id']})")
    else:
        click.echo("✅ All workers healthy")
```

---

📋 PHASE 7: Testing (Week 4) - 3 todos

🔧 7.1 New Tests

```python
# tests/test_swarm_v2.1.py

def test_mission_control():
    """Test dashboard doesn't crash"""
    from jagabot.swarm.dashboard import MissionControl
    mc = MissionControl()
    dashboard = mc.generate_dashboard()
    assert dashboard is not None

def test_cron_scheduler():
    """Test scheduled jobs"""
    from jagabot.swarm.scheduler import JagabotScheduler
    scheduler = JagabotScheduler(memory_owner)
    scheduler.add_job("test", "@hourly", lambda: "ok")
    assert len(scheduler.jobs) == 1

def test_cost_tracker():
    """Test cost tracking"""
    from jagabot.swarm.costs import CostTracker
    tracker = CostTracker(":memory:")
    tracker.record_usage("monte_carlo", "test123", 1000)
    assert tracker.get_daily_cost() > 0

def test_watchdog():
    """Test worker monitoring"""
    from jagabot.swarm.watchdog import Watchdog
    from jagabot.swarm.status import WorkerStatus
    
    status = WorkerStatus()
    status.register_worker("test_worker", "monte_carlo")
    
    # Simulate stall (old heartbeat)
    time.sleep(2)
    stalled = status.get_stalled_workers(timeout=1)
    assert len(stalled) > 0
```

---

📊 JAGABOT v2.1 SUMMARY

Phase Todos LOC Est. Description
1: Mission Control 4 ~300 TUI dashboard + worker status
2: Cron Scheduler 3 ~250 Automated workflows + predefined jobs
3: Cost Tracking 2 ~150 Token/cost tracking + budget alerts
4: New Workers 3 ~300 Researcher, Copywriter, Self-Improver
5: Watchdog 3 ~200 Health monitoring + auto-restart
6: CLI Updates 2 ~100 New swarm commands
7: Testing 3 ~200 45 new tests
TOTAL 20 ~1,500 4 weeks work

🎯 The Vadim Upgrade Promise

Jagabot v2.1 = v2.0 +

· ✅ Mission Control TUI (watch your swarm live)
· ✅ 24/7 automated workflows (cron jobs)
· ✅ Cost tracking (know exactly what you spend)
· ✅ New workers (Researcher, Copywriter, Self-Improver)
· ✅ Watchdog (auto-healing swarm)
· ✅ 45 new tests (stability guaranteed)

Same solo dev. Same $5 VPS. Now with 24/7 automation.

Ready to start Phase 1? 🚀
