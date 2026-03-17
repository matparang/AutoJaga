📋 ARAHAN UNTUK JAGABOT - Implement Goal-Setter Tool

```
Jagabot, saya nak tambah Goal-Setting Loop supaya awak boleh auto-pilih task berdasarkan VERSION.md deficits.

TOLONG BUATKAN:

## 1. GOAL-SETTER TOOL

Buat file baru: /root/nanojaga/jagabot/tools/goal_setter.py

```python
"""
Goal-Setter Tool - Auto-select next task based on VERSION.md deficits
"""

import re
from pathlib import Path
from datetime import datetime

class GoalSetterTool:
    """
    Tool untuk auto-pilih next task berdasarkan priority dalam VERSION.md
    """
    
    def __init__(self):
        self.version_path = Path("/root/nanojaga/VERSION.md")
        self.priority_order = {'🔴': 3, '🟡': 2, '🟢': 1}
    
    def execute(self):
        """
        Main execution: baca deficits, pilih highest priority, spawn subagent
        """
        # 1. Baca VERSION.md
        gaps = self.parse_deficits()
        
        if not gaps:
            return "✅ No open gaps found. Standing by."
        
        # 2. Pilih highest priority
        next_gap = self.select_highest_priority(gaps)
        
        if not next_gap:
            return "✅ No actionable gaps found."
        
        # 3. Execute berdasarkan priority
        if next_gap['priority'] == '🔴':
            return self.handle_high_priority(next_gap)
        elif next_gap['priority'] == '🟡':
            return self.handle_medium_priority(next_gap)
        else:
            return self.handle_low_priority(next_gap)
    
    def parse_deficits(self):
        """Parse VERSION.md untuk extract gaps"""
        if not self.version_path.exists():
            return []
        
        content = self.version_path.read_text()
        
        # Cari table deficits
        table_pattern = r"\|\s*([🔴🟡🟢])\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|"
        matches = re.findall(table_pattern, content)
        
        gaps = []
        for match in matches:
            gaps.append({
                'priority': match[0],
                'description': match[1].strip(),
                'status': match[2].strip(),
                'priority_score': self.priority_order.get(match[0], 0)
            })
        
        # Filter yang masih OPEN
        return [g for g in gaps if 'OPEN' in g['status']]
    
    def select_highest_priority(self, gaps):
        """Pilih gap dengan priority tertinggi"""
        if not gaps:
            return None
        
        # Sort by priority (🔴 > 🟡 > 🟢)
        sorted_gaps = sorted(gaps, 
                            key=lambda x: x['priority_score'], 
                            reverse=True)
        
        return sorted_gaps[0]
    
    def handle_high_priority(self, gap):
        """Handle 🔴 HIGH priority gaps - auto-execute"""
        
        # Update VERSION.md kepada IN PROGRESS
        self.update_gap_status(gap, "🔄 IN PROGRESS")
        
        # Spawn subagent untuk fix
        spawn_command = f"""spawn(
            task="Fix {gap['description']} based on gap analysis",
            label="Auto-fix: {gap['description'][:30]}..."
        )"""
        
        # Log action
        log_entry = f"\n[{datetime.now().isoformat()}] Auto-started: {gap['description']}"
        with open("/root/.jagabot/logs/goal_setter.log", "a") as f:
            f.write(log_entry)
        
        return f"""
🤖 GOAL-SETTER: Auto-starting HIGH priority task

Gap: {gap['description']}
Priority: 🔴 HIGH
Action: Spawning subagent to fix

You will be notified when complete.
"""
    
    def handle_medium_priority(self, gap):
        """Handle 🟡 MEDIUM priority - propose but auto-execute if user agrees"""
        
        return f"""
🎯 GOAL-SETTER: Medium priority task detected

Gap: {gap['description']}
Priority: 🟡 MEDIUM

Shall I proceed? (auto-continues in 10 seconds)
Type 'continue' or wait.
"""
    
    def handle_low_priority(self, gap):
        """Handle 🟢 LOW priority - just inform"""
        
        return f"""
📋 GOAL-SETTER: Low priority task available

Gap: {gap['description']}
Priority: 🟢 LOW

No action taken. Will revisit later.
"""
    
    def update_gap_status(self, gap, new_status):
        """Update status dalam VERSION.md"""
        if not self.version_path.exists():
            return
        
        content = self.version_path.read_text()
        
        # Pattern untuk line yang mengandung gap
        pattern = rf"(\|\s*{gap['priority']}\s*\|[^|]+\|)\s*[^|]+\s*(\|)"
        replacement = rf"\1 {new_status} \2"
        
        new_content = re.sub(pattern, replacement, content)
        
        if new_content != content:
            self.version_path.write_text(new_content)
```

2. TOOL REGISTRATION

Tambah dalam /root/nanojaga/jagabot/tools/init.py:

```python
from .goal_setter import GoalSetterTool

def register_all_tools(registry):
    # ... existing tools ...
    registry.register(
        name="goal_setter",
        tool=GoalSetterTool(),
        description="Auto-select next task based on VERSION.md deficits"
    )
```

3. HEARTBEAT INTEGRATION

Tambah dalam /root/nanojaga/config.yaml:

```yaml
heartbeat:
  enabled: true
  interval_minutes: 30
  tasks:
    - name: goal_setter
      enabled: true
      command: "jagabot tool execute goal_setter"
```

4. UPDATE VERSION.md DENGAN DEFICIT TRACKER

Pastikan VERSION.md ada section ini:

```markdown
## DEFICIT TRACKER

| Priority | Gap | Status |
|----------|-----|--------|
| 🔴 HIGH | Version tracking | OPEN |
| 🟡 MEDIUM | Test suite (only 1 test) | OPEN |
| 🟡 MEDIUM | QuantaLogic integration | OPEN |
| 🟢 LOW | Upsonic integration | OPEN |

## AUTO-GOAL SETTING ENABLED ✅
Next task will be auto-selected from 🔴 HIGH priority.
```

5. TEST

```bash
# Test manual
jagabot tool execute goal_setter

# Seharusnya output:
# 🤖 GOAL-SETTER: Auto-starting HIGH priority task
# Gap: Version tracking
# Priority: 🔴 HIGH
# Action: Spawning subagent to fix
```

Tolong implement semua step di atas. Pastikan goal_setter.py boleh berfungsi dan integrate dengan heartbeat.

```
