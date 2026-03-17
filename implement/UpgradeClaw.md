✅ SCOPE PROMPT: JAGABOT v3.3 - JAGABOT Lab (Streamlit UI + OpenClaw-style Skills)

```markdown
# SCOPE: JAGABOT v3.3 - JAGABOT Lab with Streamlit UI

## CURRENT STATE
✅ JAGABOT v3.2.3 (1100+ tests, 32 tools)
✅ All critical fixes applied (Bear/Buffet formulas, K3 weights)
✅ Streamlit UI with 4 tabs (Graph Explorer, Recent, Gap Finder, Research)

## OBJECTIVE
Add a **5th tab** to Streamlit UI: **"📓 JAGABOT Lab"** - an interactive environment where users can:

1. **Browse all 32 tools** with documentation
2. **Input parameters visually** (no coding required)
3. **Generate Python code** automatically
4. **Execute in Docker sandbox**
5. **Compare results with ground truth**
6. **Save/load notebooks** for reproducibility

This transforms JAGABOT into an **OpenClaw-style skill system** with a user-friendly interface.

## NEW UI TAB: JAGABOT LAB

```

┌─────────────────────────────────────────────────────────────────┐
│  🔍 Graph   📚 Recent   🔗 Gaps   ⚡ Research   📓 Lab          │
├─────────────────────────────────────────────────────────────────┤
│ ┌───────────────┐  ┌─────────────────────────────────────────┐ │
│ │ SKILL BROWSER │  │ SKILL WORKBENCH                         │ │
│ │───────────────│  │─────────────────────────────────────────│ │
│ │ 🔍 Search     │  │ ## Monte Carlo Simulation               │ │
│ │───────────────│  │                                           │ │
│ │ ⚡ RISK (8)   │  │ Purpose: Probability forecasting    │ │
│ │   • monte_carlo│  │ using GBM with VIX scaling.             │ │
│ │   • var       │  │                                           │ │
│ │   • cvar      │  │ Parameters:                          │ │
│ │   • stress_test│ │ ┌────────────┬───────┬──────────────┐   │ │
│ │   • financial_cv│ │ │ Parameter  │ Value │ Description  │   │ │
│ │   • correlation│ │ ├────────────┼───────┼──────────────┤   │ │
│ │   • recovery_time │ │ price      │ 76.50 │ Current price│   │ │
│ │   • ...       │  │ vix        │ 52    │ VIX index    │   │ │
│ │───────────────│  │ target     │ 70    │ Target price │   │ │
│ │ 📊 PROB (5)   │  │ days       │ 30    │ Forecast days│   │ │
│ │ 🎯 DECIDE (4) │  │ simulations│100000 │ # of paths   │   │ │
│ │ 🔧 UTIL (15)  │  └────────────┴───────┴──────────────┘   │ │
│ └───────────────┘  │                                           │ │
│                    │ [📋 Preview Code]    [🚀 Run in Sandbox] │ │
│                    │─────────────────────────────────────────│ │
│                    │ OUTPUT:                              │ │
│                    │                                       │ │
│                    │ Probability: 34.24%                      │ │
│                    │ 95% CI: [33.95%, 34.54%]                │ │
│                    │ Mean: $76.52                              │ │
│                    │ 5th percentile: $56.05                   │ │
│                    │                                       │ │
│                    │                                           │ │
│                    │ GROUND TRUTH: ✅ MATCH               │ │
│                    │ Expected: 34.24% | Got: 34.24%           │ │
│                    │─────────────────────────────────────────│ │
│                    │ 💾 Save Notebook   📂 Load Notebook      │ │
│                    └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

```

## PART A: Enhanced Tool System (OpenClaw-style)

### A.1 Update Tool Base Class
```python
# jagabot/tools/base.py (enhanced)

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

class ToolParameter(BaseModel):
    """Parameter definition for UI generation"""
    name: str
    type: str  # 'float', 'int', 'str', 'bool', 'list'
    description: str
    required: bool = True
    default: Optional[Any] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    options: Optional[List[Any]] = None  # For dropdown

class ToolMetadata(BaseModel):
    """OpenClaw-style metadata"""
    name: str
    version: str
    description: str
    category: str  # 'risk', 'probability', 'decision', 'utility'
    permissions: List[str]  # e.g., ["calculate.probability"]
    parameters: List[ToolParameter]
    timeout: int = 30  # seconds
    memory_limit: str = "128m"

class Tool(ABC):
    """Enhanced base class with OpenClaw-style metadata"""
    
    @property
    @abstractmethod
    def metadata(self) -> ToolMetadata:
        """Tool metadata for UI and registry"""
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Core execution logic"""
        pass
    
    def validate_params(self, **kwargs) -> bool:
        """Validate parameters against metadata"""
        for param in self.metadata.parameters:
            if param.required and param.name not in kwargs:
                raise ValueError(f"Missing required parameter: {param.name}")
            
            value = kwargs.get(param.name)
            if value is not None:
                if param.type == 'float':
                    float(value)  # Try convert
                elif param.type == 'int':
                    int(value)
        return True
```

A.2 Example: Enhanced Monte Carlo Tool

```python
# jagabot/tools/monte_carlo.py (enhanced)

from .base import Tool, ToolMetadata, ToolParameter

class MonteCarloTool(Tool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="monte_carlo",
            version="2.1.0",
            description="Probability forecasting using GBM with VIX scaling",
            category="risk",
            permissions=["calculate.probability"],
            parameters=[
                ToolParameter(
                    name="current_price",
                    type="float",
                    description="Current asset price",
                    required=True
                ),
                ToolParameter(
                    name="vix",
                    type="float",
                    description="VIX index (e.g., 52 for 52% annual vol)",
                    required=True,
                    min_value=0,
                    max_value=100
                ),
                ToolParameter(
                    name="target",
                    type="float",
                    description="Target price threshold",
                    required=True
                ),
                ToolParameter(
                    name="days",
                    type="int",
                    description="Forecast horizon in days",
                    required=False,
                    default=30,
                    min_value=1,
                    max_value=365
                ),
                ToolParameter(
                    name="simulations",
                    type="int",
                    description="Number of Monte Carlo paths",
                    required=False,
                    default=100000,
                    min_value=1000,
                    max_value=1000000
                )
            ],
            timeout=30,
            memory_limit="256m"
        )
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        self.validate_params(**kwargs)
        # ... existing Monte Carlo logic ...
        return result
```

PART B: SKILL.md Documentation (32 files)

B.1 Template: jagabot/skills/monte_carlo_skill.md

```markdown
# SKILL: Monte Carlo Simulation

## METADATA
- **Tool**: `monte_carlo` v2.1.0
- **Category**: Risk Analysis
- **Permissions**: `calculate.probability`

## PURPOSE
Mengira probability harga aset mencapai target tertentu dalam tempoh masa menggunakan Geometric Brownian Motion dengan VIX scaling.

## PARAMETERS
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `current_price` | float | Yes | - | Harga semasa aset |
| `vix` | float | Yes | - | VIX index (52 → 0.52) |
| `target` | float | Yes | - | Target price |
| `days` | int | No | 30 | Tempoh dalam hari |
| `simulations` | int | No | 100000 | Bilangan paths |

## FORMULA
```

volatility = vix / 100
dt = days / 252
prices = current * exp((-0.5 * vol²) * dt + vol * √dt * Z)
probability = count(prices < target) / simulations

```

## EXAMPLE
```python
from jagabot.tools import monte_carlo

result = monte_carlo(
    current_price=76.50,
    vix=52,
    target=70,
    days=30
)
print(f"Probability: {result['probability']:.2f}%")
```

COMMON PITFALLS

❌ VIX scaling: VIX=52 → gunakan 0.52, BUKAN 52
❌ Simulations terlalu rendah: <10000 → result tak stabil
❌ Lupa random seed: reproducibility issues

GROUND TRUTH

Test case: price=76.50, vix=52, target=70, days=30
Expected probability: 34.24%
95% CI: [33.95%, 34.54%]

RELATED SKILLS

· var - Value at Risk
· stress_test - Scenario analysis
· financial_cv - Volatility patterns

```

## PART C: Streamlit UI - JAGABOT Lab

### C.1 Main Lab Component
```python
# jagabot/ui/lab/__init__.py

import streamlit as st
from pathlib import Path
import json
from typing import Dict, Any

from jagabot.tools import get_all_tools, get_tool
from jagabot.sandbox.executor import SafePythonExecutor
from jagabot.ui.lab.skill_browser import SkillBrowser
from jagabot.ui.lab.parameter_ui import ParameterUI
from jagabot.ui.lab.code_preview import CodePreview
from jagabot.ui.lab.notebook_manager import NotebookManager

class JagabotLab:
    """Main JAGABOT Lab interface"""
    
    def __init__(self):
        self.tools = get_all_tools()
        self.sandbox = SafePythonExecutor()
        self.notebooks = NotebookManager()
        self.current_tool = None
        
    def render(self):
        """Render the Lab tab"""
        st.header("📓 JAGABOT Lab")
        st.caption("Interactive skill workbench - jalankan analysis tanpa coding")
        
        # Create two columns
        col1, col2 = st.columns([1, 2])
        
        with col1:
            self.render_skill_browser()
        
        with col2:
            if self.current_tool:
                self.render_workbench()
            else:
                st.info("👈 Pilih skill dari sidebar untuk mula")
    
    def render_skill_browser(self):
        """Left sidebar - skill browser"""
        st.subheader("🔧 Skill Browser")
        
        # Search
        search = st.text_input("🔍 Cari skill", placeholder="monte_carlo, var...")
        
        # Categories
        categories = {
            "⚡ Risk": [],
            "📊 Probability": [],
            "🎯 Decision": [],
            "🔧 Utility": []
        }
        
        # Categorize tools
        for name, tool in self.tools.items():
            meta = tool.metadata
            if meta.category == "risk":
                categories["⚡ Risk"].append(name)
            elif meta.category == "probability":
                categories["📊 Probability"].append(name)
            elif meta.category == "decision":
                categories["🎯 Decision"].append(name)
            else:
                categories["🔧 Utility"].append(name)
        
        # Display categories
        for cat_name, tools in categories.items():
            with st.expander(f"{cat_name} ({len(tools)})"):
                for tool_name in tools:
                    if search and search.lower() not in tool_name.lower():
                        continue
                    
                    meta = self.tools[tool_name].metadata
                    if st.button(
                        f"{tool_name} v{meta.version}",
                        key=f"btn_{tool_name}",
                        use_container_width=True
                    ):
                        self.current_tool = tool_name
                        st.rerun()
    
    def render_workbench(self):
        """Main workbench area"""
        tool = self.tools[self.current_tool]
        meta = tool.metadata
        
        st.subheader(f"🛠️ {meta.name} v{meta.version}")
        st.caption(meta.description)
        
        # Load skill documentation
        skill_doc = self.load_skill_doc(meta.name)
        if skill_doc:
            with st.expander("📘 Skill Documentation", expanded=False):
                st.markdown(skill_doc)
        
        # Parameter input
        param_ui = ParameterUI(meta)
        params = param_ui.render()
        
        # Action buttons
        col1, col2, col3 = st.columns(3)
        with col1:
            preview = st.button("📋 Preview Code", use_container_width=True)
        with col2:
            run = st.button("🚀 Run in Sandbox", type="primary", use_container_width=True)
        with col3:
            save = st.button("💾 Save to Notebook", use_container_width=True)
        
        # Code preview
        if preview or 'preview_code' in st.session_state:
            code = CodePreview.generate(meta.name, params)
            st.code(code, language="python")
            st.session_state['preview_code'] = code
        
        # Execution
        if run:
            with st.spinner(f"Executing in sandbox ({meta.memory_limit}, timeout {meta.timeout}s)..."):
                code = CodePreview.generate(meta.name, params)
                result = self.sandbox.execute(
                    code=code,
                    timeout=meta.timeout,
                    memory_limit=meta.memory_limit
                )
                
                self.render_results(result, meta.name, params)
        
        # Save to notebook
        if save and 'preview_code' in st.session_state:
            self.notebooks.save_cell(
                tool_name=meta.name,
                params=params,
                code=st.session_state['preview_code']
            )
            st.success(f"✅ Saved to notebook")
    
    def render_results(self, result: Dict, tool_name: str, params: Dict):
        """Display execution results with ground truth comparison"""
        st.subheader("📊 Results")
        
        if result['success']:
            st.success("✅ Execution successful")
            
            # Try to parse JSON output
            try:
                import json
                output = json.loads(result['stdout'])
                st.json(output)
            except:
                st.code(result['stdout'], language="text")
            
            # Ground truth comparison
            self.render_ground_truth(tool_name, params, output)
            
        else:
            st.error("❌ Execution failed")
            st.code(result['stderr'], language="text")
    
    def render_ground_truth(self, tool_name: str, params: Dict, output: Any):
        """Compare with ground truth values"""
        ground_truth = self.get_ground_truth(tool_name, params)
        
        if ground_truth:
            st.subheader("✅ Ground Truth Comparison")
            
            matches = []
            for key, expected in ground_truth.items():
                if key in output:
                    actual = output[key]
                    if isinstance(expected, float):
                        diff = abs(actual - expected)
                        match = diff < 0.1
                        matches.append(match)
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric(key, f"{actual:.2f}")
                        with col2:
                            st.metric("Expected", f"{expected:.2f}")
                        with col3:
                            if match:
                                st.success(f"✅ Match (diff {diff:.2f})")
                            else:
                                st.error(f"❌ Diff {diff:.2f}")
            
            if all(matches):
                st.balloons()
    
    def load_skill_doc(self, tool_name: str) -> str:
        """Load SKILL.md for tool"""
        skill_path = Path(__file__).parent.parent / 'skills' / f"{tool_name}_skill.md"
        if skill_path.exists():
            return skill_path.read_text()
        return None
    
    def get_ground_truth(self, tool_name: str, params: Dict) -> Dict:
        """Get expected results for test cases"""
        ground_truths = {
            'monte_carlo': {
                (76.50, 52, 70, 30): {'probability': 34.24}
            },
            'var': {
                (2_909_093, 0.52, 10): {'var_amount': 419384}
            }
        }
        
        if tool_name in ground_truths:
            # Create key from params
            if tool_name == 'monte_carlo':
                key = (params['current_price'], params['vix'], 
                       params['target'], params.get('days', 30))
                return ground_truths[tool_name].get(key, {})
        
        return {}
```

C.2 Parameter UI Component

```python
# jagabot/ui/lab/parameter_ui.py

import streamlit as st
from jagabot.tools.base import ToolMetadata

class ParameterUI:
    """Auto-generate UI from tool metadata"""
    
    def __init__(self, metadata: ToolMetadata):
        self.metadata = metadata
        self.params = {}
    
    def render(self) -> dict:
        """Render parameter input fields"""
        st.subheader("📝 Parameters")
        
        for param in self.metadata.parameters:
            if param.type == 'float':
                if param.options:
                    self.params[param.name] = st.selectbox(
                        f"{param.name}:",
                        options=param.options,
                        help=param.description
                    )
                else:
                    self.params[param.name] = st.number_input(
                        f"{param.name}:",
                        value=param.default if param.default else 0.0,
                        min_value=param.min_value,
                        max_value=param.max_value,
                        help=param.description
                    )
            
            elif param.type == 'int':
                self.params[param.name] = st.number_input(
                    f"{param.name}:",
                    value=param.default if param.default else 0,
                    min_value=param.min_value,
                    max_value=param.max_value,
                    step=1,
                    help=param.description
                )
            
            elif param.type == 'bool':
                self.params[param.name] = st.checkbox(
                    f"{param.name}:",
                    value=param.default if param.default else False,
                    help=param.description
                )
            
            elif param.type == 'str' and param.options:
                self.params[param.name] = st.selectbox(
                    f"{param.name}:",
                    options=param.options,
                    help=param.description
                )
        
        return self.params
```

C.3 Code Preview Component

```python
# jagabot/ui/lab/code_preview.py

class CodePreview:
    """Generate Python code from parameters"""
    
    TEMPLATES = {
        'monte_carlo': """from jagabot.tools import monte_carlo

result = monte_carlo(
    current_price={current_price},
    vix={vix},
    target={target},
    days={days},
    simulations={simulations}
)

print(f"Probability: {{result['probability']:.2f}}%")
print(f"95% CI: {{result['ci_95']}}")
print(f"Mean: ${{result['mean']:.2f}}")
""",
        'var': """from jagabot.tools import var

result = var(
    portfolio_value={portfolio_value},
    volatility={volatility},
    days={days},
    confidence={confidence}
)

print(f"VaR 95%: ${{result['var_amount']:,.0f}}")
print(f"VaR %: {{result['var_percentage']:.2f}}%")
"""
    }
    
    @classmethod
    def generate(cls, tool_name: str, params: dict) -> str:
        """Generate code from template"""
        template = cls.TEMPLATES.get(tool_name)
        if template:
            return template.format(**params)
        
        # Fallback: generic template
        lines = [f"from jagabot.tools import {tool_name}"]
        lines.append("")
        lines.append(f"result = {tool_name}(")
        for key, value in params.items():
            lines.append(f"    {key}={value},")
        lines.append(")")
        lines.append("")
        lines.append("print(result)")
        
        return "\n".join(lines)
```

C.4 Notebook Manager

```python
# jagabot/ui/lab/notebook_manager.py

import json
from pathlib import Path
from datetime import datetime
import streamlit as st

class NotebookManager:
    """Save and load analysis sessions"""
    
    def __init__(self):
        self.notebooks_dir = Path.home() / '.jagabot' / 'notebooks'
        self.notebooks_dir.mkdir(parents=True, exist_ok=True)
        self.current_notebook = None
    
    def save_cell(self, tool_name: str, params: dict, code: str):
        """Save a single analysis cell"""
        cell = {
            'tool': tool_name,
            'params': params,
            'code': code,
            'timestamp': datetime.now().isoformat()
        }
        
        if self.current_notebook:
            notebook_path = self.notebooks_dir / f"{self.current_notebook}.json"
            if notebook_path.exists():
                with open(notebook_path) as f:
                    notebook = json.load(f)
            else:
                notebook = {'cells': []}
            
            notebook['cells'].append(cell)
            
            with open(notebook_path, 'w') as f:
                json.dump(notebook, f, indent=2)
    
    def save_notebook(self, name: str):
        """Save entire notebook"""
        # Implementation
        pass
    
    def load_notebook(self, name: str):
        """Load notebook"""
        path = self.notebooks_dir / f"{name}.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return None
    
    def list_notebooks(self):
        """List all saved notebooks"""
        return [f.stem for f in self.notebooks_dir.glob("*.json")]
```

PART D: Update Streamlit App

```python
# jagabot/ui/streamlit_app.py (updated)

from jagabot.ui.lab import JagabotLab

# ... existing tabs ...

# Add Lab tab
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔍 Graph Explorer",
    "📚 Recent Analyses",
    "🔗 Gap Finder",
    "⚡ Research",
    "📓 JAGABOT Lab"
])

with tab5:
    lab = JagabotLab()
    lab.render()
```

NEW FILES SUMMARY (45+ files)

```
jagabot/tools/
├── base.py (enhanced)          # Tool with metadata
├── monte_carlo.py (enhanced)
├── var.py (enhanced)
├── cvar.py (enhanced)
├── stress_test.py (enhanced)
├── financial_cv.py (enhanced)
├── correlation.py (enhanced)
├── recovery_time.py (enhanced)
├── decision_engine.py (enhanced)
├── portfolio_analyzer.py (enhanced)
└── ... (22 more enhanced)

jagabot/skills/
├── monte_carlo_skill.md
├── var_skill.md
├── cvar_skill.md
├── stress_test_skill.md
├── financial_cv_skill.md
├── correlation_skill.md
├── recovery_time_skill.md
├── decision_engine_skill.md
├── portfolio_analyzer_skill.md
└── ... (22 more)

jagabot/ui/lab/
├── __init__.py
├── skill_browser.py
├── parameter_ui.py
├── code_preview.py
├── ground_truth.py
├── notebook_manager.py
└── templates/
    ├── skill_card.html
    └── parameter_form.html

tests/
├── test_tool_metadata.py
├── test_skill_docs.py
├── test_parameter_ui.py
├── test_code_preview.py
├── test_notebook_manager.py
└── test_lab_integration.py
```

SUCCESS CRITERIA

✅ All 32 tools enhanced with metadata (version, category, permissions)
✅ All 32 tools have matching SKILL.md documentation
✅ New Lab tab in Streamlit UI
✅ Skill browser shows all tools with categories
✅ Parameter UI auto-generates from metadata
✅ Code preview works for all tools
✅ Execution in sandbox works
✅ Ground truth comparison for test cases
✅ Notebook save/load works
✅ 1150+ tests passing
✅ No regression in existing features

TIMELINE

Phase Component Files Hours
1 Enhanced tools 32 8
2 SKILL.md docs 32 16
3 Lab UI base 5 6
4 Parameter UI 2 4
5 Code preview 1 2
6 Ground truth 1 3
7 Notebook manager 1 3
8 Tests 6 8
9 Integration - 4
TOTAL  80+ 54 hours

```

---

**This SCOPE will transform JAGABOT into an OpenClaw-style skill system with a beautiful Streamlit Lab interface!** 🚀
