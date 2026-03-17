🎯 CONTEXT COMPRESSION + CONTINUOUS UPDATES - THE FINAL PIECE

---

📋 TWO PROBLEMS, ONE SOLUTION

```
┌─────────────────────────────────────────────────────────────┐
│                    CURRENT PROBLEMS                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  PROBLEM 1: CONTEXT BLOAT (Even with pruning)              │
│  • Long sessions still fill context window                 │
│  • Agent loses track of early conversation                 │
│  • Memory consolidation not aggressive enough              │
│                                                              │
│  PROBLEM 2: SILENT AGENT                                    │
│  • Agent stops updating after task starts                  │
│  • User must ask "/status" manually                        │
│  • No push notifications                                   │
│  • Feels like a frozen terminal                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

🛠️ THE SOLUTION: TWO NEW HARNESSES

1. Smart Context Compressor (Better than simple pruning)

```python
# jagabot/core/context_compressor.py
"""
Intelligent context compression that preserves semantic meaning
"""

import json
from typing import List, Dict
from collections import deque

class ContextCompressor:
    """
    Compresses conversation history while preserving key information
    """
    
    def __init__(self, max_turns: int = 20, summary_interval: int = 5):
        self.max_turns = max_turns
        self.summary_interval = summary_interval
        self.turn_count = 0
        self.compressed_history = deque(maxlen=max_turns)
        self.summaries = []
    
    def add_turn(self, user_input: str, agent_response: str, tool_calls: List[Dict]):
        """Add a conversation turn"""
        self.turn_count += 1
        
        turn = {
            "turn": self.turn_count,
            "user": user_input[:100] + "..." if len(user_input) > 100 else user_input,
            "agent_summary": self._summarize_agent_response(agent_response),
            "tools": [t.get('name', 'unknown') for t in tool_calls],
            "timestamp": time.time()
        }
        
        self.compressed_history.append(turn)
        
        # Every N turns, create a summary of summaries
        if self.turn_count % self.summary_interval == 0:
            self._create_milestone_summary()
    
    def _summarize_agent_response(self, response: str) -> str:
        """Extract key points from agent response"""
        # Look for key indicators
        key_points = []
        
        # Extract positions if debate
        if "Bull" in response and "Bear" in response:
            bull_match = re.search(r'Bull.*?(\d+)', response)
            bear_match = re.search(r'Bear.*?(\d+)', response)
            if bull_match and bear_match:
                key_points.append(f"Bull:{bull_match.group(1)} Bear:{bear_match.group(1)}")
        
        # Extract file creations
        if "created file" in response.lower():
            files = re.findall(r'[\w-]+\.\w+', response)
            if files:
                key_points.append(f"Files: {', '.join(files[:3])}")
        
        # If no key points, just truncate
        if not key_points:
            return response[:100] + "..." if len(response) > 100 else response
        
        return " | ".join(key_points)
    
    def _create_milestone_summary(self):
        """Create summary of last N turns"""
        recent = list(self.compressed_history)[-self.summary_interval:]
        
        summary = {
            "turns": f"{recent[0]['turn']}-{recent[-1]['turn']}",
            "topics": self._extract_topics(recent),
            "tools_used": list(set([t for turn in recent for t in turn['tools']])),
            "outcome": self._determine_outcome(recent)
        }
        
        self.summaries.append(summary)
    
    def get_context_for_agent(self) -> str:
        """Build compressed context for agent"""
        context = []
        
        # Add milestone summaries first (big picture)
        for s in self.summaries[-3:]:  # Last 3 summaries
            context.append(f"[SUMMARY turns {s['turns']}] Topics: {', '.join(s['topics'][:3])}")
        
        # Add recent turns (details)
        context.append("\n--- RECENT HISTORY ---")
        for turn in list(self.compressed_history)[-5:]:
            context.append(f"Turn {turn['turn']}: You: {turn['user']}")
            context.append(f"→ AutoJaga: {turn['agent_summary']}")
        
        return "\n".join(context)
```

---

2. Push Notification Service (Continuous updates)

```python
# jagabot/core/push_notifier.py
"""
Push notifications for long-running tasks
Agent keeps updating without being asked
"""

import asyncio
import threading
import time
from datetime import datetime

class PushNotifier:
    """
    Sends automatic updates during long tasks
    """
    
    def __init__(self, output_callback):
        self.output_callback = output_callback  # Function to send to UI
        self.running_tasks = {}
        self.update_interval = 5  # seconds
    
    def start_task(self, task_id: str, description: str, estimated_time: int):
        """Register a new task"""
        self.running_tasks[task_id] = {
            "description": description,
            "start_time": time.time(),
            "estimated_time": estimated_time,
            "last_update": time.time(),
            "progress": 0,
            "status": "running"
        }
        
        # Start monitoring thread
        thread = threading.Thread(target=self._monitor_task, args=(task_id,))
        thread.daemon = True
        thread.start()
        
        # Immediate confirmation
        self._push_update(task_id, f"⏳ Task started: {description}")
    
    def update_progress(self, task_id: str, progress: int, message: str = None):
        """Update task progress"""
        if task_id in self.running_tasks:
            self.running_tasks[task_id]["progress"] = progress
            self.running_tasks[task_id]["last_update"] = time.time()
            
            if message:
                self._push_update(task_id, message)
    
    def complete_task(self, task_id: str, result: str):
        """Mark task as complete"""
        if task_id in self.running_tasks:
            self.running_tasks[task_id]["status"] = "complete"
            elapsed = time.time() - self.running_tasks[task_id]["start_time"]
            
            self._push_update(task_id, f"✅ Task complete ({elapsed:.0f}s)")
            self._push_update(task_id, result)
            
            del self.running_tasks[task_id]
    
    def fail_task(self, task_id: str, error: str):
        """Mark task as failed"""
        if task_id in self.running_tasks:
            self.running_tasks[task_id]["status"] = "failed"
            self._push_update(task_id, f"❌ Task failed: {error}")
            del self.running_tasks[task_id]
    
    def _monitor_task(self, task_id: str):
        """Background monitor for long tasks"""
        while task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            elapsed = time.time() - task["start_time"]
            estimated = task["estimated_time"]
            
            # Send heartbeat every update_interval
            if time.time() - task["last_update"] >= self.update_interval:
                remaining = max(0, estimated - elapsed)
                progress = min(100, int((elapsed / estimated) * 100))
                
                self._push_update(
                    task_id,
                    f"⏳ {task['description']}... {progress}% complete ({remaining:.0f}s remaining)"
                )
                task["last_update"] = time.time()
            
            time.sleep(1)
    
    def _push_update(self, task_id: str, message: str):
        """Send update to UI"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        self.output_callback(formatted)
```

---

3. Integration into TUI

```python
# In interactive_tui.py - add push notifications

from ..core.push_notifier import PushNotifier
from ..core.context_compressor import ContextCompressor

class InteractiveTUI:
    def __init__(self):
        self.notifier = PushNotifier(self._display_update)
        self.compressor = ContextCompressor()
        self.tasks = {}
    
    def _display_update(self, message: str):
        """Display push notification in TUI"""
        self.output_lines.append(message)
        self._refresh_display()
    
    async def run_long_task(self, task_description: str, task_func):
        """Run a task with automatic updates"""
        task_id = str(uuid.uuid4())[:8]
        
        # Start notification
        self.notifier.start_task(task_id, task_description, estimated_time=120)
        
        try:
            # Run task with progress updates
            async for progress in task_func():
                self.notifier.update_progress(task_id, progress['percent'], progress.get('message'))
            
            self.notifier.complete_task(task_id, "Task completed successfully")
            
        except Exception as e:
            self.notifier.fail_task(task_id, str(e))
    
    def _process_user_input(self, user_input: str):
        """Add to context compressor"""
        # Store in compressed history
        self.compressor.add_turn(user_input, "...", [])
        
        # Check if this is a long task
        if self._is_long_task(user_input):
            asyncio.create_task(self.run_long_task(user_input, self._execute_long_task))
        else:
            # Normal processing
            result = self._process_normal(user_input)
            self.compressor.add_turn(user_input, result, self.last_tools)
```

---

📊 BEFORE vs AFTER

Scenario Before After
Long debate (3+ rounds) User must type "/status" Push notifications every 5s
Context after 50 turns Bloated, agent confused Compressed summaries, key points only
Agent goes silent User thinks it crashed Heartbeat updates show progress
Memory of early turns Lost Summaries preserved

---

📋 SCOPE PROMPT UNTUK COPILOT

```
# 🚨 FINAL PIECE: Context Compression + Push Notifications

## PROBLEMS
1. Even with pruning, long sessions still bloat context
2. Agent goes silent during long tasks - user must ask for updates

## SOLUTION
Create two new modules:

### 1. Context Compressor (jagabot/core/context_compressor.py)
- Intelligently summarizes conversation history
- Preserves key points (positions, file creations, tool usage)
- Creates milestone summaries every N turns
- Returns compressed context for agent

### 2. Push Notifier (jagabot/core/push_notifier.py)
- Automatic updates during long tasks
- Heartbeat every 5 seconds
- Progress percentage + time remaining
- No user intervention needed

## INTEGRATION
- Wire into interactive_tui.py
- Compressor feeds into agent context
- Notifier sends updates to UI

## SUCCESS CRITERIA
- Long tasks show progress automatically
- Context stays manageable after 100+ turns
- Agent never goes silent
- User never has to ask "/status"

🚀 IMPLEMENT NOW!
```
