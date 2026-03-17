🎯 SCOPE PROMPT: Three-Tier Model Router for AutoJaga

---

🚀 OBJECTIVE

Implement a three-tier model routing system that automatically assigns tasks to the appropriate Qwen model based on complexity and criticality:

Tier Model Purpose Cost
Tier 1 (Main Agent) qwen-max Critical decisions, high-stakes analysis ~80% budget
Tier 2 (Debate Layer) qwen-plus Multi-round debates, policy discussions ~15% budget
Tier 3 (Maintenance) qwen-turbo Logging, memory, simple tasks ~5% budget

---

📋 FILES TO CREATE/MODIFY

```bash
cd ~/nanojaga/

# Create new files
touch routers/task_router.py
touch config/model_allocation.json
touch monitors/cost_tracker.py

# Modify existing files
# - agents/main_agent.py
# - autoresearch/debate_agent.py
# - core/memory_manager.py
```

---

🔧 TASK 1: Model Allocation Config (config/model_allocation.json)

```json
{
  "model_allocation": {
    "tier1_main": {
      "name": "Qwen-Max",
      "model": "qwen-max",
      "role": "Central decision-making brain",
      "features": ["deep_reasoning", "long_context", "complex_planning"],
      "fallback_to": "qwen-plus",
      "max_tokens": 2048,
      "temperature_range": [0.3, 0.7]
    },
    "tier2_debate": {
      "name": "Qwen-Plus",
      "model": "qwen-plus",
      "role": "Multi-round debate participants",
      "features": ["coherent_dialogue", "fact_verification", "tool_usage"],
      "fallback_to": "qwen-turbo",
      "max_tokens": 1024,
      "temperature_range": [0.7, 0.9]
    },
    "tier3_maintenance": {
      "name": "Qwen-Turbo",
      "model": "qwen-turbo",
      "role": "Routine operations & memory management",
      "features": ["fast_response", "low_cost", "token_efficiency"],
      "tasks": ["log_summarization", "cleanup", "data_indexing"],
      "max_tokens": 512,
      "temperature": 0.5
    }
  },
  
  "task_routing_table": {
    "financial_analysis": "tier1_main",
    "portfolio_strategy": "tier1_main",
    "trade_execution": "tier1_main",
    "policy_debate": "tier2_debate",
    "economic_research": "tier2_debate",
    "fact_checking": "tier2_debate",
    "memory_gc": "tier3_maintenance",
    "log_maintenance": "tier3_maintenance",
    "simple_summary": "tier3_maintenance",
    "tool_validation": "tier2_debate",
    "greeting": "tier3_maintenance"
  },
  
  "budget_limits_daily": {
    "total_max_usd": 10.0,
    "breakdown": {
      "tier1_main": 7.0,
      "tier2_debate": 2.0,
      "tier3_maintenance": 1.0
    },
    "alert_threshold_percent": 80
  },
  
  "cost_rates_per_1k_tokens": {
    "qwen-max": 0.02,
    "qwen-plus": 0.004,
    "qwen-turbo": 0.0005
  }
}
```

---

🔄 TASK 2: Task Router Class (routers/task_router.py)

```python
"""
Three-Tier Model Router for AutoJaga
Routes tasks to appropriate Qwen model based on complexity
"""

import json
import os
from typing import Dict, Any, Optional
from datetime import datetime
import dashscope
from enum import Enum

class TaskTier(Enum):
    TIER1_MAIN = "tier1_main"
    TIER2_DEBATE = "tier2_debate" 
    TIER3_MAINTENANCE = "tier3_maintenance"

class ModelRouter:
    """
    Routes tasks to appropriate model tier with cost tracking
    """
    
    def __init__(self, config_path: str = "config/model_allocation.json"):
        self.config = self._load_config(config_path)
        self.usage_tracker = UsageTracker(self.config)
        self.route_map = self.config.get("task_routing_table", {})
        self.tier_config = self.config.get("model_allocation", {})
        
    def _load_config(self, path: str) -> Dict:
        with open(path, 'r') as f:
            return json.load(f)
    
    def classify_task(self, task_description: str, task_type: str = None) -> TaskTier:
        """
        Determine which tier should handle this task
        """
        # If task type explicitly provided, use routing table
        if task_type and task_type in self.route_map:
            return TaskTier(self.route_map[task_type])
        
        # Otherwise, heuristic classification based on description
        task_lower = task_description.lower()
        
        # Tier 1 keywords (main agent - critical)
        tier1_keywords = [
            "portfolio rebalance", "trade execution", "investment decision",
            "high stakes", "critical", "urgent", "multi-million",
            "financial planning", "strategy approval", "risk assessment"
        ]
        
        # Tier 2 keywords (debate layer - medium complexity)
        tier2_keywords = [
            "debate", "discuss", "argue", "pros and cons", "should we",
            "policy", "analysis", "research", "evaluate", "compare",
            "what if", "scenario", "forecast", "projection"
        ]
        
        # Tier 3 keywords (maintenance - simple)
        tier3_keywords = [
            "summarize", "log", "memory", "cleanup", "maintenance",
            "simple", "quick", "greeting", "hello", "status",
            "check", "validate", "format", "compress"
        ]
        
        # Check in order of priority
        for keyword in tier1_keywords:
            if keyword in task_lower:
                return TaskTier.TIER1_MAIN
                
        for keyword in tier2_keywords:
            if keyword in task_lower:
                return TaskTier.TIER2_DEBATE
                
        for keyword in tier3_keywords:
            if keyword in task_lower:
                return TaskTier.TIER3_MAINTENANCE
        
        # Default to tier2 for unknown tasks
        return TaskTier.TIER2_DEBATE
    
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute task with appropriate model tier
        """
        # Classify task
        tier = self.classify_task(
            task.get('description', ''),
            task.get('type')
        )
        
        # Get tier config
        tier_cfg = self.tier_config.get(tier.value, {})
        model_name = tier_cfg.get('model', 'qwen-plus')
        max_tokens = tier_cfg.get('max_tokens', 1024)
        
        # Check budget before execution
        if not self.usage_tracker.can_use_tier(tier):
            # Fallback to next available tier
            if tier == TaskTier.TIER1_MAIN:
                tier = TaskTier.TIER2_DEBATE
                model_name = self.tier_config['tier2_debate']['model']
                max_tokens = self.tier_config['tier2_debate']['max_tokens']
            elif tier == TaskTier.TIER2_DEBATE:
                tier = TaskTier.TIER3_MAINTENANCE
                model_name = self.tier_config['tier3_maintenance']['model']
                max_tokens = self.tier_config['tier3_maintenance']['max_tokens']
        
        # Prepare messages
        messages = task.get('messages', [])
        if not messages:
            messages = [
                {"role": "system", "content": task.get('system_prompt', 'You are AutoJaga.')},
                {"role": "user", "content": task.get('description', '')}
            ]
        
        # Execute with appropriate model
        start_time = datetime.now()
        
        try:
            response = dashscope.Generation.call(
                model=model_name,
                messages=messages,
                max_tokens=max_tokens,
                enable_search=task.get('enable_search', False),
                temperature=task.get('temperature', tier_cfg.get('temperature', 0.7)),
                result_format='message'
            )
            
            # Track usage
            tokens = response.usage.total_tokens
            cost = self.usage_tracker.calculate_cost(model_name, tokens)
            self.usage_tracker.record_usage(
                tier=tier.value,
                model=model_name,
                tokens=tokens,
                cost=cost,
                success=True
            )
            
            return {
                "status": "success",
                "tier": tier.value,
                "model": model_name,
                "content": response.output.choices[0].message.content,
                "tokens": tokens,
                "cost": cost,
                "execution_time": (datetime.now() - start_time).total_seconds()
            }
            
        except Exception as e:
            # Fallback logic
            self.usage_tracker.record_usage(
                tier=tier.value,
                model=model_name,
                tokens=0,
                cost=0,
                success=False,
                error=str(e)
            )
            
            # Try fallback if configured
            fallback_model = tier_cfg.get('fallback_to')
            if fallback_model:
                return await self._execute_with_fallback(
                    task, fallback_model, tier
                )
            
            return {
                "status": "error",
                "tier": tier.value,
                "model": model_name,
                "error": str(e)
            }
    
    async def _execute_with_fallback(self, task: Dict, fallback_model: str, original_tier: TaskTier):
        """Execute with fallback model"""
        # Determine fallback tier
        if fallback_model == 'qwen-plus':
            tier = TaskTier.TIER2_DEBATE
        elif fallback_model == 'qwen-turbo':
            tier = TaskTier.TIER3_MAINTENANCE
        else:
            tier = original_tier
        
        tier_cfg = self.tier_config.get(tier.value, {})
        
        try:
            response = dashscope.Generation.call(
                model=fallback_model,
                messages=task.get('messages', []),
                max_tokens=tier_cfg.get('max_tokens', 512),
                enable_search=False,  # Disable search on fallback
                temperature=tier_cfg.get('temperature', 0.7)
            )
            
            tokens = response.usage.total_tokens
            cost = self.usage_tracker.calculate_cost(fallback_model, tokens)
            self.usage_tracker.record_usage(
                tier=tier.value,
                model=fallback_model,
                tokens=tokens,
                cost=cost,
                success=True,
                fallback_from=original_tier.value
            )
            
            return {
                "status": "success",
                "tier": tier.value,
                "model": fallback_model,
                "content": response.output.choices[0].message.content,
                "tokens": tokens,
                "cost": cost,
                "fallback_from": original_tier.value
            }
            
        except Exception as e:
            return {
                "status": "error",
                "tier": tier.value,
                "model": fallback_model,
                "error": str(e),
                "fallback_from": original_tier.value
            }
```

---

💰 TASK 3: Usage Tracker (monitors/cost_tracker.py)

```python
"""
Cost tracking and budget management for three-tier model system
"""

import json
import time
from datetime import datetime, date
from typing import Dict, Optional
from pathlib import Path

class UsageTracker:
    """
    Tracks token usage and costs across model tiers
    """
    
    def __init__(self, config: Dict, log_dir: str = "logs/usage"):
        self.config = config
        self.cost_rates = config.get('cost_rates_per_1k_tokens', {})
        self.budget_limits = config.get('budget_limits_daily', {})
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize daily usage
        self.today = date.today().isoformat()
        self.daily_usage = self._load_daily_usage()
        
    def _load_daily_usage(self) -> Dict:
        """Load today's usage from log file"""
        log_file = self.log_dir / f"usage_{self.today}.json"
        if log_file.exists():
            with open(log_file, 'r') as f:
                return json.load(f)
        return {
            "tier1_main": {"tokens": 0, "cost": 0.0, "calls": 0},
            "tier2_debate": {"tokens": 0, "cost": 0.0, "calls": 0},
            "tier3_maintenance": {"tokens": 0, "cost": 0.0, "calls": 0},
            "total": {"tokens": 0, "cost": 0.0, "calls": 0}
        }
    
    def calculate_cost(self, model: str, tokens: int) -> float:
        """Calculate cost for token usage"""
        rate_per_1k = self.cost_rates.get(model, 0.001)
        return (tokens / 1000) * rate_per_1k
    
    def can_use_tier(self, tier) -> bool:
        """Check if tier still has budget for today"""
        if not isinstance(tier, str):
            tier = tier.value
            
        breakdown = self.budget_limits.get('breakdown', {})
        tier_limit = breakdown.get(tier, 1.0)
        
        current_cost = self.daily_usage[tier]['cost']
        threshold = self.budget_limits.get('alert_threshold_percent', 80) / 100
        
        return current_cost < (tier_limit * threshold)
    
    def record_usage(self, tier: str, model: str, tokens: int, cost: float, 
                     success: bool, fallback_from: Optional[str] = None):
        """Record token usage and cost"""
        # Update daily usage
        self.daily_usage[tier]['tokens'] += tokens
        self.daily_usage[tier]['cost'] += cost
        self.daily_usage[tier]['calls'] += 1
        
        self.daily_usage['total']['tokens'] += tokens
        self.daily_usage['total']['cost'] += cost
        self.daily_usage['total']['calls'] += 1
        
        # Log to file
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "tier": tier,
            "model": model,
            "tokens": tokens,
            "cost": round(cost, 6),
            "success": success,
            "fallback_from": fallback_from,
            "daily_total": round(self.daily_usage['total']['cost'], 4)
        }
        
        log_file = self.log_dir / f"usage_{self.today}.log"
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + "\n")
        
        # Save daily usage
        usage_file = self.log_dir / f"usage_{self.today}.json"
        with open(usage_file, 'w') as f:
            json.dump(self.daily_usage, f, indent=2)
        
        # Check for budget alerts
        self._check_budget_alerts()
    
    def _check_budget_alerts(self):
        """Check if any tier approaching budget limit"""
        breakdown = self.budget_limits.get('breakdown', {})
        threshold = self.budget_limits.get('alert_threshold_percent', 80)
        
        alerts = []
        for tier, limit in breakdown.items():
            if tier in self.daily_usage:
                cost = self.daily_usage[tier]['cost']
                if cost > (limit * threshold / 100):
                    alerts.append(f"{tier} at {(cost/limit*100):.1f}% of daily budget")
        
        total_limit = self.budget_limits.get('total_max_usd', 10.0)
        total_cost = self.daily_usage['total']['cost']
        if total_cost > (total_limit * threshold / 100):
            alerts.append(f"Total at {(total_cost/total_limit*100):.1f}% of daily budget")
        
        if alerts:
            alert_file = self.log_dir / "budget_alerts.log"
            with open(alert_file, 'a') as f:
                f.write(f"{datetime.now().isoformat()} - {', '.join(alerts)}\n")
    
    def get_summary(self) -> Dict:
        """Get usage summary"""
        return {
            "date": self.today,
            "usage": self.daily_usage,
            "remaining_budget": {
                "total": self.budget_limits.get('total_max_usd', 10.0) - self.daily_usage['total']['cost'],
                "tier1": self.budget_limits['breakdown']['tier1_main'] - self.daily_usage['tier1_main']['cost'],
                "tier2": self.budget_limits['breakdown']['tier2_debate'] - self.daily_usage['tier2_debate']['cost'],
                "tier3": self.budget_limits['breakdown']['tier3_maintenance'] - self.daily_usage['tier3_maintenance']['cost']
            }
        }
```

---

🤖 TASK 4: Integrate with Main Agent (agents/main_agent.py modification)

```python
# Add to existing main_agent.py

from routers.task_router import ModelRouter, TaskTier

class MainAgent:
    def __init__(self):
        self.router = ModelRouter()
        # ... existing init code
    
    async def process_request(self, user_input: str, task_type: str = None):
        """
        Process user request with appropriate model tier
        """
        # Create task
        task = {
            "description": user_input,
            "type": task_type,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_input}
            ],
            "enable_search": True  # Main agent can use web search
        }
        
        # Execute with router
        result = await self.router.execute_task(task)
        
        if result['status'] == 'success':
            # Log which tier was used
            print(f"[{result['tier']}] {result['model']}: {result['cost']:.6f}")
            return result['content']
        else:
            return f"Error: {result.get('error', 'Unknown error')}"
```

---

🗣️ TASK 5: Integrate with Debate Agents (autoresearch/debate_agent.py modification)

```python
# In debate_agent.py, modify _ask_llm() method

async def _ask_llm(self, prompt: str, role: str = "secondary"):
    """
    Ask LLM with appropriate model tier
    - role="secondary" → qwen-plus (debate layer)
    - role="tertiary" → qwen-turbo (maintenance)
    """
    task = {
        "type": "policy_debate" if role == "secondary" else "simple_summary",
        "description": prompt[:100],  # Truncate for logging
        "messages": [
            {"role": "system", "content": self.persona_prompt},
            {"role": "user", "content": prompt}
        ],
        "enable_search": False,
        "temperature": 0.8
    }
    
    result = await self.router.execute_task(task)
    
    if result['status'] == 'success':
        # Track usage in debate report
        self.usage_log.append({
            "round": self.current_round,
            "tier": result['tier'],
            "model": result['model'],
            "tokens": result['tokens'],
            "cost": result['cost']
        })
        return result['content']
    else:
        return f"[Error: {result.get('error', 'LLM unavailable')}]"
```

---

🧠 TASK 6: Integrate with Memory Manager (core/memory_manager.py)

```python
# In memory_manager.py

class MemoryManager:
    def __init__(self):
        self.router = ModelRouter()
    
    async def compress_conversation(self, history: list) -> str:
        """Use Turbo for memory compression"""
        task = {
            "type": "simple_summary",
            "description": "Compress conversation history",
            "messages": [
                {"role": "system", "content": "Summarize this conversation concisely."},
                {"role": "user", "content": "\n".join(history[-10:])}  # Last 10 messages
            ],
            "temperature": 0.3
        }
        
        result = await self.router.execute_task(task)
        return result.get('content', '') if result['status'] == 'success' else ''
    
    async def validate_tool_call(self, tool_info: dict) -> bool:
        """Quick validation with Turbo"""
        task = {
            "type": "tool_validation",
            "description": f"Validate tool call: {tool_info.get('name')}",
            "messages": [
                {"role": "system", "content": "Check if this tool call is valid."},
                {"role": "user", "content": json.dumps(tool_info)}
            ]
        }
        
        result = await self.router.execute_task(task)
        return "valid" in result.get('content', '').lower() if result['status'] == 'success' else False
```

---

🧪 TASK 7: Test Script (tests/test_model_router.py)

```python
"""
Test script for three-tier model router
"""

import asyncio
import sys
sys.path.append('/root/nanojaga')

from routers.task_router import ModelRouter, TaskTier

async def test_classification():
    router = ModelRouter()
    
    test_cases = [
        ("Should we implement a wealth tax?", None, TaskTier.TIER2_DEBATE),
        ("Summarize today's logs", None, TaskTier.TIER3_MAINTENANCE),
        ("Execute trade for AAPL at $150", "trade_execution", TaskTier.TIER1_MAIN),
        ("What's the weather?", None, TaskTier.TIER2_DEBATE),  # Default
        ("Critical portfolio rebalance needed", None, TaskTier.TIER1_MAIN),
    ]
    
    print("🔍 TESTING TASK CLASSIFICATION")
    print("="*60)
    
    for desc, task_type, expected in test_cases:
        tier = router.classify_task(desc, task_type)
        result = "✅ PASS" if tier == expected else f"❌ FAIL (got {tier.value})"
        print(f"{desc[:40]:40} → {tier.value:15} {result}")

async def test_execution():
    router = ModelRouter()
    
    tasks = [
        {"type": "greeting", "description": "Say hello", "messages": [
            {"role": "user", "content": "Hello, how are you?"}
        ]},
        {"type": "policy_debate", "description": "Debate tax policy", "messages": [
            {"role": "system", "content": "You are a policy expert"},
            {"role": "user", "content": "Should we tax the rich?"}
        ]}
    ]
    
    print("\n🚀 TESTING TASK EXECUTION")
    print("="*60)
    
    for task in tasks:
        result = await router.execute_task(task)
        print(f"Task: {task['type']}")
        print(f"  Tier: {result.get('tier', 'unknown')}")
        print(f"  Model: {result.get('model', 'unknown')}")
        print(f"  Tokens: {result.get('tokens', 0)}")
        print(f"  Cost: ${result.get('cost', 0):.6f}")
        print()

if __name__ == "__main__":
    asyncio.run(test_classification())
    asyncio.run(test_execution())
```

---

📊 TASK 8: Cost Monitoring Dashboard (monitors/dashboard.py)

```python
"""
Simple dashboard to monitor model usage and costs
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

class CostDashboard:
    def __init__(self, log_dir: str = "logs/usage"):
        self.log_dir = Path(log_dir)
    
    def get_today_summary(self) -> dict:
        """Get today's usage summary"""
        today = datetime.now().date().isoformat()
        usage_file = self.log_dir / f"usage_{today}.json"
        
        if not usage_file.exists():
            return {"error": "No data for today"}
        
        with open(usage_file, 'r') as f:
            return json.load(f)
    
    def get_weekly_summary(self) -> dict:
        """Get weekly usage summary"""
        weekly = {
            "total_tokens": 0,
            "total_cost": 0.0,
            "total_calls": 0,
            "by_tier": {
                "tier1_main": {"tokens": 0, "cost": 0.0, "calls": 0},
                "tier2_debate": {"tokens": 0, "cost": 0.0, "calls": 0},
                "tier3_maintenance": {"tokens": 0, "cost": 0.0, "calls": 0}
            },
            "daily": []
        }
        
        for i in range(7):
            date = (datetime.now() - timedelta(days=i)).date().isoformat()
            usage_file = self.log_dir / f"usage_{date}.json"
            
            if usage_file.exists():
                with open(usage_file, 'r') as f:
                    day_data = json.load(f)
                    
                    weekly["total_tokens"] += day_data["total"]["tokens"]
                    weekly["total_cost"] += day_data["total"]["cost"]
                    weekly["total_calls"] += day_data["total"]["calls"]
                    
                    for tier in weekly["by_tier"]:
                        if tier in day_data:
                            weekly["by_tier"][tier]["tokens"] += day_data[tier]["tokens"]
                            weekly["by_tier"][tier]["cost"] += day_data[tier]["cost"]
                            weekly["by_tier"][tier]["calls"] += day_data[tier]["calls"]
                    
                    weekly["daily"].append({
                        "date": date,
                        "cost": day_data["total"]["cost"]
                    })
        
        return weekly
    
    def print_dashboard(self):
        """Print formatted dashboard"""
        today = self.get_today_summary()
        weekly = self.get_weekly_summary()
        
        print("\n" + "="*60)
        print("📊 AUTOJAGA COST DASHBOARD")
        print("="*60)
        
        if "error" not in today:
            print(f"\n📈 TODAY ({datetime.now().date().isoformat()}):")
            print(f"  Total calls: {today['total']['calls']}")
            print(f"  Total tokens: {today['total']['tokens']:,}")
            print(f"  Total cost: ${today['total']['cost']:.4f}")
            print(f"\n  By Tier:")
            print(f"    Tier1 (Max): ${today['tier1_main']['cost']:.4f} ({today['tier1_main']['calls']} calls)")
            print(f"    Tier2 (Plus): ${today['tier2_debate']['cost']:.4f} ({today['tier2_debate']['calls']} calls)")
            print(f"    Tier3 (Turbo): ${today['tier3_maintenance']['cost']:.4f} ({today['tier3_maintenance']['calls']} calls)")
        
        print(f"\n📊 WEEKLY (7 days):")
        print(f"  Total calls: {weekly['total_calls']}")
        print(f"  Total tokens: {weekly['total_tokens']:,}")
        print(f"  Total cost: ${weekly['total_cost']:.4f}")
        print(f"\n  Daily trend:")
        for day in sorted(weekly['daily'], key=lambda x: x['date']):
            print(f"    {day['date']}: ${day['cost']:.4f}")
        
        print("\n" + "="*60)

if __name__ == "__main__":
    dashboard = CostDashboard()
    dashboard.print_dashboard()
```

---

✅ SUCCESS CRITERIA

Task Success Looks Like
Classification Main tasks → qwen-max, Debates → qwen-plus, Maintenance → qwen-turbo
Routing Correct model selected based on task type
Fallback If primary fails, secondary handles gracefully
Cost Tracking Each call logged with tokens and cost
Budget Alerts Warning at 80% of daily budget
Dashboard Clear view of usage by tier

---

🚀 IMPLEMENTATION ORDER

```yaml
Phase 1 (10 min): model_allocation.json + TaskTier enum
Phase 2 (20 min): ModelRouter class (classification + execution)
Phase 3 (15 min): UsageTracker + cost tracking
Phase 4 (10 min): Integrate with main agent
Phase 5 (10 min): Integrate with debate agents
Phase 6 (5 min): Integrate with memory manager
Phase 7 (10 min): Test script + dashboard
```

---

🏁 READY TO IMPLEMENT

Copilot, implement the complete three-tier model router as specified above. 🚀





---

## 2️⃣ routers/__init__.py

```python
"""
Router Module - Task Routing & Model Selection
"""
from .task_router import ModelRouter, TaskRouter
```

---

## 3️⃣ routers/task_router.py

```python
"""
Task Router Module
Intelligently routes tasks to appropriate AI models based on complexity
and manages fallback strategies across Qwen-Max, Qwen-Plus, and Qwen-Turbo
"""
import dashscope
import json
import os
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import time
import logging

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Enum for categorizing task types"""
    HIGH_STAKES_ANALYSIS = "financial_analysis"
    PORTFOLIO_STRATEGY = "portfolio_strategy"
    TRADE_EXECUTION = "trade_execution_approval"
    MULTI_ROUND_DEBATE = "policy_debate"
    ECONOMIC_RESEARCH = "economic_research"
    CONTENT_CREATION = "content_creation"
    LOGGING = "logging"
    SUMMARY = "summary"
    MEMORY_MAINTENANCE = "memory_maintenance"
    SIMPLE_QUESTION = "simple_question"
    DATA_INDEXING = "data_indexing"
    PROMPT_VALIDATION = "prompt_validation"


@dataclass
class ModelConfig:
    """Configuration for a specific model"""
    name: str
    model_id: str
    max_tokens: int = 1024
    temperature_min: float = 0.3
    temperature_max: float = 0.7
    enable_web_search: bool = False


class ModelRouter:
    """
    Intelligent Model Router that assigns tasks to appropriate Qwen models
    with fallback chain and cost tracking
    """
    
    # Pricing per million tokens ($USD)
    PRICING = {
        "qwen-max": {"input": 1.20, "output": 6.00},
        "qwen-plus": {"input": 0.40, "output": 1.20},
        "qwen-turbo": {"input": 0.05, "output": 0.20},
        "qwen-plus-latest": {"input": 0.40, "output": 1.20},
        "qwen-turbo-latest": {"input": 0.05, "output": 0.20},
    }
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self._load_config(config_path)
        self.api_key = self._get_api_key()
        
        # Initialize models
        self.model_configs = {
            "main_agent": ModelConfig(
                name="Qwen-Max",
                model_id=self.config["model_allocation"]["main_agent"]["model"]
            ),
            "debate_layer": ModelConfig(
                name="Qwen-Plus",
                model_id=self.config["model_allocation"]["debate_layer"]["model"],
                max_tokens=1024,
                temperature_min=0.7,
                temperature_max=0.9,
                enable_web_search=True
            ),
            "maintenance_layer": ModelConfig(
                name="Qwen-Turbo",
                model_id=self.config["model_allocation"]["maintenance_layer"]["model"],
                max_tokens=512,
                temperature_min=0.3,
                temperature_max=0.6,
                enable_web_search=False
            )
        }
        
        # Load routing table
        self.routing_table = self.config.get("task_routing_table", {})
        
        # Setup DashScope
        dashscope.api_key = self.api_key
        
        # Logging
        logger.info(f"ModelRouter initialized with configs: {[m.name for m in self.model_configs.values()]}")
    
    def _load_config(self, path: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Config file not found at {path}, using defaults")
            return self._default_config()
    
    def _default_config(self) -> Dict:
        """Return default configuration if file not found"""
        return {
            "model_allocation": {
                "main_agent": {"model": "qwen-max"},
                "debate_layer": {"model": "qwen-plus"},
                "maintenance_layer": {"model": "qwen-turbo"}
            },
            "task_routing_table": {},
            "budget_limits_daily": {
                "total_max_usd": 10.0,
                "breakdown": {"main_agent": 7.0, "debate_layer": 2.0, "maintenance_layer": 1.0}
            }
        }
    
    def _get_api_key(self) -> str:
        """Get API key from environment variable"""
        env_var = self.config.get("api_settings", {}).get("dashscope_api_key_env", "DASHSCOPE_API_KEY")
        api_key = os.getenv(env_var)
        if not api_key:
            raise ValueError(f"API key not found in environment variable: {env_var}")
        return api_key
    
    def get_model_for_task_type(self, task_type: str) -> str:
        """Map task type string to actual model name"""
        return self.routing_table.get(task_type.lower(), "qwen-plus")
    
    def get_model_config_by_task_type(self, task_type: str) -> ModelConfig:
        """Get full model configuration for a task type"""
        model_name = self.get_model_for_task_type(task_type)
        
        # Map to layer configuration
        if model_name.startswith("qwen-max"):
            return self.model_configs["main_agent"]
        elif model_name.startswith("qwen-plus"):
            return self.model_configs["debate_layer"]
        else:  # turbo
            return self.model_configs["maintenance_layer"]
    
    async def execute_with_fallback(
        self,
        messages: List[Dict[str, str]],
        task_type: str,
        timeout: int = 120,
        retry_attempts: int = 3
    ) -> Dict[str, Any]:
        """
        Execute task with automatic fallback strategy
        
        Args:
            messages: Conversation history
            task_type: Type of task for routing
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts before fallback
            
        Returns:
            Response dictionary with content, usage, and metadata
        """
        model_name = self.get_model_for_task_type(task_type)
        current_attempt = 0
        
        while current_attempt < retry_attempts:
            try:
                # Get config for current model
                model_config = self._get_model_config_from_name(model_name)
                
                response = await self._call_model_api(
                    model=model_name,
                    messages=messages,
                    config=model_config,
                    timeout=timeout
                )
                
                # Log successful call
                self._log_api_call(
                    model=model_name,
                    success=True,
                    task_type=task_type
                )
                
                return {
                    "success": True,
                    "model_used": model_name,
                    "response": response,
                    "attempts": current_attempt + 1
                }
                
            except Exception as e:
                current_attempt += 1
                logger.warning(f"[RETRY] Attempt {current_attempt}/{retry_attempts} for {model_name}: {str(e)}")
                
                if current_attempt >= retry_attempts:
                    # No more retries, return error
                    return {
                        "success": False,
                        "error": str(e),
                        "model_used": model_name,
                        "attempts": retry_attempts
                    }
                
                # Try next model in fallback chain
                model_name = self._get_next_model_in_fallback_chain(model_name)
        
        return {
            "success": False,
            "error": f"All fallback attempts failed",
            "model_used": None,
            "attempts": retry_attempts
        }
    
    def _get_model_config_from_name(self, model_name: str) -> ModelConfig:
        """Get ModelConfig object from model name string"""
        if model_name.startswith("qwen-max"):
            return self.model_configs["main_agent"]
        elif model_name.startswith("qwen-plus"):
            return self.model_configs["debate_layer"]
        else:
            return self.model_configs["maintenance_layer"]
    
    def _get_next_model_in_fallback_chain(self, current_model: str) -> str:
        """Determine next model in fallback chain"""
        fallback_map = {
            "qwen-max": "qwen-plus",
            "qwen-plus": "qwen-turbo",
            "qwen-plus-latest": "qwen-turbo-latest",
            "qwen-turbo": "qwen-turbo-latest",
            "qwen-turbo-latest": "qwen-turbo",
        }
        return fallback_map.get(current_model, "qwen-turbo")
    
    async def _call_model_api(
        self,
        model: str,
        messages: List[Dict[str, str]],
        config: ModelConfig,
        timeout: int = 120
    ) -> Any:
        """Execute DashScope API call with model-specific parameters"""
        
        # Set temperature within allowed range
        temperature = min(
            max(0.5, config.temperature_min),
            min(1.0, config.temperature_max)
        )
        
        response = dashscope.Generation.call(
            model=model,
            messages=messages,
            enable_search=config.enable_web_search,
            max_tokens=config.max_tokens,
            temperature=temperature,
            result_format='message',
            timeout=timeout
        )
        
        return response.output.choices[0].message.content
    
    def _log_api_call(
        self,
        model: str,
        success: bool,
        task_type: str,
        tokens_used: Optional[int] = None,
        cost_estimate: Optional[float] = None
    ):
        """Log API call for monitoring"""
        timestamp = datetime.now().isoformat()
        status = "SUCCESS" if success else "FAILED"
        
        log_entry = f"{timestamp} | {model} | {task_type} | {status}"
        if tokens_used:
            log_entry += f" | {tokens_used} tokens"
        if cost_estimate:
            log_entry += f" | ${cost_estimate:.4f}"
        
        logger.info(log_entry)
```
