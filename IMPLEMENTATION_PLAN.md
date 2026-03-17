# 🚀 JAGABOT IMPLEMENTATION PLAN
## Based on Gapsadd.md Blueprint & Current State Audit

**Generated:** March 14, 2026  
**Status:** Ready for Implementation  
**Target:** TOAD Integration + Gap Resolution

---

## 📊 CURRENT STATE ASSESSMENT

### ✅ What Already Exists (v3.0-v4.2 Integrated)

| Component | Status | File Location | Tests |
|-----------|--------|---------------|-------|
| **MemoryFleet** | ✅ Integrated | `jagabot/memory/` (fractal_manager, als_manager, consolidation) | ❌ Missing |
| **KnowledgeGraph** | ✅ Integrated | `jagabot/agent/tools/knowledge_graph.py` | ❌ Missing |
| **K1 Bayesian** | ✅ Integrated | `jagabot/kernels/k1_bayesian.py` | ❌ Missing |
| **K3 Perspective** | ✅ Integrated | `jagabot/kernels/k3_perspective.py` | ❌ Missing |
| **K7 Evaluation** | ✅ Integrated | `jagabot/agent/tools/evaluation.py` | ❌ Missing |
| **MetaLearning** | ✅ Integrated | `jagabot/engines/meta_learning.py` | ❌ Missing |
| **Evolution** | ✅ Integrated | `jagabot/evolution/engine.py` | ❌ Missing |
| **Tri-Agent** | ✅ Integrated | `jagabot/agent/tools/tri_agent.py` | ❌ Missing |
| **Quad-Agent** | ✅ Integrated | `jagabot/agent/tools/quad_agent.py` | ❌ Missing |
| **Offline Swarm** | ✅ Integrated | `jagabot/agent/tools/offline_swarm.py` | ❌ Missing |

### ❌ Critical Gaps (Per Blueprint)

| Gap | Priority | Current Status | Target |
|-----|----------|----------------|--------|
| **Test Coverage** | 🔴 HIGH | 7 unit tests (financial tools only) | 85% coverage |
| **v3.0 Component Tests** | 🔴 HIGH | 0 tests | 7 test files |
| **Documentation** | 🔴 HIGH | Outdated (v2.7 audit) | v4.2 docs |
| **Vector Embeddings** | 🟡 MEDIUM | Not implemented | Semantic search |
| **Entity Extraction** | 🟡 MEDIUM | Not implemented | KnowledgeGraph enhancement |
| **Adaptive Planning** | 🟡 MEDIUM | Not implemented | Dynamic replanning |
| **Channel Tests** | 🟡 MEDIUM | 0 tests | Telegram, Slack, Email |
| **Dynamic Skills** | 🟢 LOW | Static markdown | Runtime composition |
| **Kernel Pipeline** | 🟢 LOW | Isolated kernels | K1→K3→K7 chaining |
| **E2E Tests** | 🟢 LOW | 0 tests | Mock LLM tests |

---

## 🏗️ IMPLEMENTATION PHASES

### PHASE 1: TEST COVERAGE EXPANSION (Week 1)
**Priority:** 🔴 CRITICAL  
**Effort:** ~40 hours  
**Dependencies:** None

#### Task 1.1: v3.0 Component Unit Tests (7 files)

| # | Test File | Component | LOC Est | Priority |
|---|-----------|-----------|---------|----------|
| 1.1.1 | `tests/unit/test_memory_fleet.py` | MemoryFleet | ~150 | 🔴 |
| 1.1.2 | `tests/unit/test_k1_bayesian.py` | K1 Bayesian | ~120 | 🔴 |
| 1.1.3 | `tests/unit/test_k3_perspective.py` | K3 Perspective | ~120 | 🔴 |
| 1.1.4 | `tests/unit/test_evaluation.py` | K7 Evaluation | ~150 | 🔴 |
| 1.1.5 | `tests/unit/test_meta_learning.py` | MetaLearning | ~180 | 🔴 |
| 1.1.6 | `tests/unit/test_evolution.py` | Evolution | ~150 | 🔴 |
| 1.1.7 | `tests/unit/test_knowledge_graph.py` | KnowledgeGraph | ~100 | 🔴 |

**Example Test Structure (test_memory_fleet.py):**
```python
"""Unit tests for MemoryFleet system."""
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from jagabot.agent.tools.memory_fleet import MemoryFleet, MemoryFleetTool

class TestMemoryFleet:
    @pytest.fixture
    def temp_workspace(self):
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_fractal_creation(self, temp_workspace):
        """Test fractal memory node creation."""
        fleet = MemoryFleet(temp_workspace)
        events = fleet.on_interaction(
            user_message="What is VIX?",
            agent_response="VIX measures volatility...",
            topic="volatility"
        )
        assert fleet.fractal.total_count == 1
        assert len(events) >= 0
    
    def test_consolidation(self, temp_workspace):
        """Test memory consolidation pipeline."""
        fleet = MemoryFleet(temp_workspace)
        # Add 10 interactions to trigger auto-consolidation
        for i in range(10):
            fleet.on_interaction(f"Q{i}", f"A{i}")
        # Check consolidation occurred
        assert fleet.consolidation.pending_count == 0
    
    def test_retrieval(self, temp_workspace):
        """Test context retrieval."""
        fleet = MemoryFleet(temp_workspace)
        fleet.on_interaction("What is portfolio risk?", "Risk is...")
        context = fleet.get_context("portfolio risk", k=1)
        assert "Risk" in context
```

#### Task 1.2: Integration Tests (3 files)

| # | Test File | Coverage | LOC Est | Priority |
|---|-----------|----------|---------|----------|
| 1.2.1 | `tests/integration/test_guardian_pipeline.py` | Web→Support→Billing→Supervisor | ~200 | 🔴 |
| 1.2.2 | `tests/integration/test_swarm_orchestrator.py` | Planner→WorkerPool→Stitcher | ~250 | 🔴 |
| 1.2.3 | `tests/integration/test_tool_harness.py` | Track/Verify/Fabrication | ~180 | 🔴 |

**Example Integration Test Structure:**
```python
"""Test Guardian subagent pipeline."""
import pytest
from unittest.mock import AsyncMock, patch
from jagabot.guardian.core import Jagabot

class TestGuardianPipeline:
    @pytest.fixture
    def guardian(self, temp_workspace):
        return Jagabot(workspace=temp_workspace)
    
    @pytest.mark.asyncio
    async def test_websearch_to_support(self, guardian):
        """Test WebSearch → Support data flow."""
        with patch('jagabot.guardian.subagents.websearch.websearch_agent') as mock_web:
            mock_web.return_value = {"news": [{"title": "Test"}]}
            # Test pipeline stage 1→2
            result = await guardian.handle_query(
                user_query="Analyze AAPL",
                portfolio={"capital": 100000},
                market_data={"AAPL": 150.0}
            )
            assert "web" in result
            assert "support" in result
```

#### Task 1.3: Channel Tests (3 files)

| # | Test File | Channel | LOC Est | Priority |
|---|-----------|---------|---------|----------|
| 1.3.1 | `tests/integration/test_telegram.py` | Telegram | ~120 | 🟡 |
| 1.3.2 | `tests/integration/test_slack.py` | Slack | ~120 | 🟡 |
| 1.3.3 | `tests/integration/test_email.py` | Email | ~120 | 🟡 |

#### Task 1.4: CLI Tests (1 file)

| # | Test File | Commands | LOC Est | Priority |
|---|-----------|----------|---------|----------|
| 1.4.1 | `tests/test_cli.py` | agent, swarm, gateway | ~150 | 🟡 |

**Phase 1 Deliverables:**
- [ ] 14 test files created
- [ ] 608+ total tests (matching v2.7 audit claim)
- [ ] pytest coverage report showing 85% unit coverage
- [ ] CI/CD pipeline integration

---

### PHASE 2: CORE ENHANCEMENTS (Week 2)
**Priority:** 🟡 HIGH  
**Effort:** ~35 hours  
**Dependencies:** Phase 1 tests (for validation)

#### Task 2.1: Vector Memory with Semantic Search

**File:** `jagabot/memory/vector_memory.py`  
**LOC:** ~200  
**Dependencies:** `sentence-transformers` package

```python
"""Vector-based memory with semantic search."""
import numpy as np
from pathlib import Path
from typing import List, Dict, Any

try:
    from sentence_transformers import SentenceTransformer
    VECTOR_SUPPORT = True
except ImportError:
    VECTOR_SUPPORT = False

class VectorMemory:
    """
    Adds semantic search to MemoryFleet.
    Wraps FractalManager with vector embeddings.
    """
    
    def __init__(self, workspace: Path | None = None, model_name: str = 'all-MiniLM-L6-v2'):
        self.workspace = workspace or Path.home() / ".jagabot" / "workspace"
        self.memory_dir = self.workspace / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        if VECTOR_SUPPORT:
            self.model = SentenceTransformer(model_name)
            self.vectors_file = self.memory_dir / "vectors.npy"
            self.vectors = self._load_vectors()
        else:
            self.model = None
            self.vectors = []
        
        # Import fractal manager for hybrid search
        from jagabot.memory.fractal_manager import FractalManager
        self.fractal = FractalManager(self.memory_dir)
    
    def _load_vectors(self) -> np.ndarray:
        """Load existing vectors or create empty array."""
        if self.vectors_file.exists():
            return np.load(self.vectors_file)
        return np.array([])
    
    def _save_vectors(self):
        """Persist vectors to disk."""
        if self.vectors.size > 0:
            np.save(self.vectors_file, self.vectors)
    
    def add_memory(self, text: str, metadata: Dict[str, Any] = None) -> str:
        """Add memory with vector embedding."""
        if not VECTOR_SUPPORT or self.model is None:
            # Fallback to keyword-only
            return self.fractal.save_node(content=text)
        
        vector = self.model.encode(text)
        self.vectors = np.append(self.vectors, vector.reshape(1, -1), axis=0)
        self._save_vectors()
        
        # Also save to fractal for backward compatibility
        node_id = self.fractal.save_node(
            content=text,
            tags=metadata.get("tags", []) if metadata else []
        )
        return node_id
    
    def semantic_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Find semantically similar memories."""
        if not VECTOR_SUPPORT or self.model is None or len(self.vectors) == 0:
            # Fallback to keyword search
            return self.fractal.retrieve_relevant(query, k=top_k)
        
        query_vector = self.model.encode(query)
        similarities = np.dot(self.vectors, query_vector)
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        results = []
        all_nodes = self.fractal.get_all_nodes()
        for idx in top_indices:
            if idx < len(all_nodes):
                node = all_nodes[idx]
                results.append({
                    "id": node.id,
                    "content": node.content,
                    "summary": node.summary,
                    "tags": node.tags,
                    "similarity": float(similarities[idx])
                })
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Return memory statistics."""
        return {
            "vector_support": VECTOR_SUPPORT,
            "total_vectors": len(self.vectors),
            "total_nodes": self.fractal.total_count,
            "pending_nodes": self.fractal.pending_count,
        }
```

**Integration with MemoryFleetTool:**
```python
# Edit jagabot/agent/tools/memory_fleet.py
# Add new action: "semantic_search"
```

#### Task 2.2: Enhanced KnowledgeGraph with Entity Extraction

**File:** `jagabot/memory/knowledge_graph_enhanced.py`  
**LOC:** ~250  
**Dependencies:** `spacy` package

```python
"""Enhanced KnowledgeGraph with entity extraction."""
import spacy
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Any

class EnhancedKnowledgeGraph:
    """
    Extracts entities and relationships from text.
    Extends basic KnowledgeGraph with NLP capabilities.
    """
    
    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace or Path.home() / ".jagabot" / "workspace"
        self.memory_dir = self.workspace / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            self.nlp = spacy.load("en_core_web_sm")
            NLP_SUPPORT = True
        except OSError:
            NLP_SUPPORT = False
            print("Warning: spaCy model not loaded. Run: python -m spacy download en_core_web_sm")
        
        self.entities: Dict[str, Set[str]] = defaultdict(set)
        self.relations: List[Dict[str, str]] = []
        self.entity_graph: Dict[str, Set[str]] = defaultdict(set)
    
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract named entities from text."""
        if not NLP_SUPPORT:
            return {}
        
        doc = self.nlp(text)
        extracted = defaultdict(list)
        
        for ent in doc.ents:
            entity_type = ent.label_
            entity_text = ent.text
            extracted[entity_type].append(entity_text)
            self.entities[entity_type].add(entity_text)
        
        return dict(extracted)
    
    def extract_relations(self, text: str) -> List[Dict[str, str]]:
        """Extract subject-verb-object relations."""
        if not NLP_SUPPORT:
            return []
        
        doc = self.nlp(text)
        relations = []
        
        for token in doc:
            if token.dep_ == "ROOT" and token.pos_ == "VERB":
                subjects = [w for w in token.lefts if w.dep_ in ("nsubj", "nsubjpass")]
                objects = [w for w in token.rights if w.dep_ in ("dobj", "pobj")]
                
                if subjects and objects:
                    relation = {
                        "subject": subjects[0].text,
                        "verb": token.text,
                        "object": objects[0].text,
                        "sentence": token.sent.text
                    }
                    relations.append(relation)
                    
                    # Build entity graph
                    self.entity_graph[subjects[0].text].add(objects[0].text)
        
        self.relations.extend(relations)
        return relations
    
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """Full NLP analysis of text."""
        entities = self.extract_entities(text)
        relations = self.extract_relations(text)
        
        return {
            "entities": entities,
            "relations": relations,
            "entity_count": sum(len(v) for v in entities.values()),
            "relation_count": len(relations),
            "connected_entities": len(self.entity_graph)
        }
    
    def get_entity_connections(self, entity: str) -> List[str]:
        """Get all entities connected to given entity."""
        return list(self.entity_graph.get(entity, []))
    
    def export_graph(self, output_file: str = "entity_graph.json") -> Path:
        """Export entity-relation graph to JSON."""
        import json
        
        output_path = self.workspace / output_file
        data = {
            "entities": {k: list(v) for k, v in self.entities.items()},
            "relations": self.relations,
            "graph": {k: list(v) for k, v in self.entity_graph.items()}
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        return output_path
```

#### Task 2.3: Adaptive Swarm with Dynamic Replanning

**File:** `jagabot/swarm/adaptive_planner.py`  
**LOC:** ~280  
**Dependencies:** None (uses existing swarm infrastructure)

```python
"""Adaptive swarm with dynamic replanning."""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

class FailureType(Enum):
    TIMEOUT = "timeout"
    TOOL_MISSING = "tool_missing"
    DATA_CORRUPTED = "data_corrupted"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    DEPENDENCY_FAILED = "dependency_failed"

@dataclass
class FailureRecord:
    task_id: str
    failure_type: FailureType
    error_message: str
    retry_count: int
    timestamp: float

@dataclass
class TaskPlan:
    task_id: str
    steps: List[Dict[str, Any]]
    strategy: str = "default"
    timeout_multiplier: float = 1.0
    fallback_enabled: bool = True

class AdaptivePlanner:
    """
    Plans and replans based on execution results.
    Wraps existing TaskPlanner with adaptive capabilities.
    """
    
    def __init__(self):
        self.strategies: List[Dict[str, Any]] = []
        self.failures: List[FailureRecord] = []
        self.success_patterns: Dict[str, int] = {}
        
        # Import existing planner
        from jagabot.swarm.planner import TaskPlanner
        self.base_planner = TaskPlanner()
    
    def plan(self, task: str, context: Dict[str, Any] = None) -> TaskPlan:
        """Generate initial plan using base planner."""
        # Use existing planner for initial plan
        plan_groups = self.base_planner._category_tasks(task, context or {})
        
        # Convert to TaskPlan format
        steps = []
        for group_idx, group in enumerate(plan_groups):
            for task_spec in group:
                steps.append({
                    "group": group_idx,
                    "tool": task_spec.tool_name,
                    "params": task_spec.params,
                    "timeout": 30  # default
                })
        
        return TaskPlan(
            task_id=task,
            steps=steps,
            strategy="default",
            timeout_multiplier=1.0
        )
    
    def replan(self, task: str, failures: List[FailureRecord]) -> TaskPlan:
        """Adapt plan based on failures."""
        # Analyze failure patterns
        patterns = self._analyze_failures(failures)
        
        # Adjust strategy based on patterns
        if FailureType.TIMEOUT in patterns:
            return self._add_timeout_handling(task)
        if FailureType.TOOL_MISSING in patterns:
            return self._add_fallback_tools(task)
        if FailureType.DATA_CORRUPTED in patterns:
            return self._add_validation(task)
        if FailureType.RESOURCE_EXHAUSTED in patterns:
            return self._add_resource_limits(task)
        if FailureType.DEPENDENCY_FAILED in patterns:
            return self._add_dependency_handling(task)
        
        # Default replan
        return self._create_plan(task)
    
    def _analyze_failures(self, failures: List[FailureRecord]) -> Set[FailureType]:
        """Identify failure patterns."""
        patterns = set()
        for f in failures:
            patterns.add(f.failure_type)
        return patterns
    
    def _add_timeout_handling(self, task: str) -> TaskPlan:
        """Create plan with extended timeouts."""
        base_plan = self.plan(task)
        base_plan.strategy = "timeout_resilient"
        base_plan.timeout_multiplier = 2.0
        
        # Add timeout monitoring steps
        for step in base_plan.steps:
            step["timeout"] = int(step["timeout"] * base_plan.timeout_multiplier)
            step["retry_on_timeout"] = True
        
        return base_plan
    
    def _add_fallback_tools(self, task: str) -> TaskPlan:
        """Create plan with fallback tools."""
        base_plan = self.plan(task)
        base_plan.strategy = "fallback_enabled"
        
        # Define fallback mappings
        fallback_map = {
            "web_search": ["web_fetch", "researcher"],
            "monte_carlo": ["statistical_engine"],
            "swarm_analysis": ["offline_swarm"],
        }
        
        for step in base_plan.steps:
            tool_name = step["tool"]
            if tool_name in fallback_map:
                step["fallbacks"] = fallback_map[tool_name]
        
        return base_plan
    
    def _add_validation(self, task: str) -> TaskPlan:
        """Create plan with data validation."""
        base_plan = self.plan(task)
        base_plan.strategy = "validation_strict"
        
        # Add validation steps after each tool
        validated_steps = []
        for step in base_plan.steps:
            validated_steps.append(step)
            validated_steps.append({
                "group": step["group"],
                "tool": "evaluate_result",
                "params": {"action": "anomaly", "actual": "${previous_result}"},
                "is_validation": True
            })
        
        base_plan.steps = validated_steps
        return base_plan
    
    def _add_resource_limits(self, task: str) -> TaskPlan:
        """Create plan with conservative resource usage."""
        base_plan = self.plan(task)
        base_plan.strategy = "resource_conservative"
        
        # Reduce parallelism
        base_plan.max_parallel = 4  # instead of 8
        
        return base_plan
    
    def _add_dependency_handling(self, task: str) -> TaskPlan:
        """Create plan with explicit dependency tracking."""
        base_plan = self.plan(task)
        base_plan.strategy = "dependency_aware"
        
        # Add dependency metadata
        for idx, step in enumerate(base_plan.steps):
            step["depends_on"] = [i for i in range(idx) if base_plan.steps[i]["group"] < step["group"]]
        
        return base_plan
    
    def record_success(self, task_id: str, strategy: str):
        """Record successful strategy for future learning."""
        self.success_patterns[strategy] = self.success_patterns.get(strategy, 0) + 1
    
    def get_best_strategy(self) -> str:
        """Get most successful strategy based on history."""
        if not self.success_patterns:
            return "default"
        return max(self.success_patterns, key=self.success_patterns.get)
```

**Phase 2 Deliverables:**
- [ ] VectorMemory class with semantic search
- [ ] EnhancedKnowledgeGraph with entity/relation extraction
- [ ] AdaptivePlanner with dynamic replanning
- [ ] Integration tests for all 3 components
- [ ] Documentation updates

---

### PHASE 3: ADVANCED FEATURES (Week 3)
**Priority:** 🟢 MEDIUM  
**Effort:** ~30 hours  
**Dependencies:** Phase 1 tests, Phase 2 enhancements

#### Task 3.1: Dynamic Skill System

**File:** `jagabot/skills/dynamic_skill.py`  
**LOC:** ~200  

```python
"""Runtime skill composition and execution."""
from typing import Callable, Dict, List, Any, Optional
from pathlib import Path
import importlib.util

class DynamicSkill:
    """
    Skills that can be composed at runtime.
    Extends static markdown skills with dynamic composition.
    """
    
    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace or Path.home() / ".jagabot" / "workspace"
        self.skills_dir = self.workspace / "skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        
        self.skill_registry: Dict[str, Callable] = {}
        self.skill_performance: Dict[str, Dict[str, Any]] = {}
        
        # Load existing markdown skills
        self._load_markdown_skills()
    
    def _load_markdown_skills(self):
        """Load existing markdown skill files."""
        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    skill_name = skill_dir.name
                    self.skill_registry[skill_name] = self._create_markdown_skill(skill_file)
    
    def _create_markdown_skill(self, skill_file: Path) -> Callable:
        """Create callable from markdown skill."""
        def skill_executor(context: Dict[str, Any] = None) -> str:
            content = skill_file.read_text(encoding='utf-8')
            # Parse markdown and execute steps
            # This is a simplified version - full implementation needs markdown parser
            return f"Executed skill from {skill_file}"
        return skill_executor
    
    def register_skill(self, name: str, function: Callable, metadata: Dict[str, Any] = None):
        """Register a skill function."""
        self.skill_registry[name] = function
        self.skill_performance[name] = metadata or {
            "calls": 0,
            "success_rate": 1.0,
            "avg_duration": 0.0
        }
    
    def compose_skill(self, name: str, steps: List[str]) -> Callable:
        """Create new skill by composing existing ones."""
        def composed_skill(context: Dict[str, Any] = None) -> Any:
            result = None
            for step in steps:
                if step in self.skill_registry:
                    skill_fn = self.skill_registry[step]
                    result = skill_fn(context or {})
                    # Track performance
                    self._update_performance(step, success=True)
            return result
        
        self.register_skill(name, composed_skill)
        return composed_skill
    
    def evolve_skill(self, name: str, performance_data: Dict[str, Any]):
        """Improve skill based on performance."""
        if name not in self.skill_performance:
            self.skill_performance[name] = performance_data
            return
        
        # Update performance metrics
        current = self.skill_performance[name]
        current["calls"] = current.get("calls", 0) + 1
        
        # Update success rate (exponential moving average)
        alpha = 0.1
        current["success_rate"] = (
            alpha * performance_data.get("success_rate", 1.0) +
            (1 - alpha) * current.get("success_rate", 1.0)
        )
        
        # Auto-disable skills with low success rate
        if current["success_rate"] < 0.5:
            print(f"Warning: Skill '{name}' has low success rate: {current['success_rate']}")
    
    def _update_performance(self, skill_name: str, success: bool, duration: float = 0.0):
        """Update skill performance metrics."""
        if skill_name not in self.skill_performance:
            return
        
        perf = self.skill_performance[skill_name]
        perf["calls"] = perf.get("calls", 0) + 1
        
        if success:
            perf["successes"] = perf.get("successes", 0) + 1
        
        perf["success_rate"] = perf.get("successes", 0) / perf["calls"]
        
        # Update average duration
        old_avg = perf.get("avg_duration", 0.0)
        n = perf["calls"]
        perf["avg_duration"] = ((old_avg * (n - 1)) + duration) / n
    
    def get_skill_rankings(self) -> List[Dict[str, Any]]:
        """Get skills ranked by performance."""
        rankings = []
        for name, perf in self.skill_performance.items():
            rankings.append({
                "name": name,
                "calls": perf.get("calls", 0),
                "success_rate": perf.get("success_rate", 0.0),
                "avg_duration": perf.get("avg_duration", 0.0)
            })
        
        # Sort by success rate (descending)
        rankings.sort(key=lambda x: x["success_rate"], reverse=True)
        return rankings
    
    def export_skills(self, output_file: str = "skills_export.json") -> Path:
        """Export skill registry and performance to JSON."""
        import json
        
        output_path = self.workspace / output_file
        
        # Can't serialize functions, so export metadata only
        export_data = {
            "skills": list(self.skill_registry.keys()),
            "performance": self.skill_performance
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2)
        
        return output_path
```

#### Task 3.2: Kernel Composition Pipeline

**File:** `jagabot/kernels/composition.py`  
**LOC:** ~180  

```python
"""K1 → K3 → K7 composition pipeline."""
from typing import Dict, Any, List, Optional
from pathlib import Path

class KernelPipeline:
    """
    Automatic chaining of reasoning kernels.
    Orchestrates K1 (Bayesian) → K3 (Perspective) → K7 (Evaluation)
    """
    
    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace or Path.home() / ".jagabot" / "workspace"
        
        # Import kernels
        from jagabot.kernels.k1_bayesian import K1Bayesian
        from jagabot.kernels.k3_perspective import K3MultiPerspective
        from jagabot.agent.tools.evaluation import EvaluationKernel
        
        self.k1 = K1Bayesian(workspace)
        self.k3 = K3MultiPerspective(workspace=workspace)
        self.k7 = EvaluationKernel()
        
        # Pipeline state
        self.pipeline_history: List[Dict[str, Any]] = []
    
    def analyze(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Run full pipeline: K1 → K3 → K7
        
        Args:
            data: Input data for analysis
            context: Additional context (similar memories, entities, etc.)
        
        Returns:
            Combined result with confidence scoring
        """
        # Step 1: Bayesian reasoning (K1)
        k1_result = self._run_k1(data, context)
        
        # Step 2: Multi-perspective analysis (K3)
        k3_result = self._run_k3(k1_result, data, context)
        
        # Step 3: Evaluation (K7)
        k7_result = self._run_k7(k1_result, k3_result, data)
        
        # Combine results
        final_result = {
            "k1_beliefs": k1_result,
            "k3_perspectives": k3_result,
            "k7_evaluation": k7_result,
            "confidence": self._calculate_confidence(k1_result, k3_result, k7_result),
            "recommendation": self._generate_recommendation(k1_result, k3_result, k7_result)
        }
        
        # Record for learning
        self.pipeline_history.append(final_result)
        
        return final_result
    
    def _run_k1(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run K1 Bayesian reasoning."""
        # Extract topic and evidence from data
        topic = data.get("topic", "analysis")
        evidence = data.get("evidence", data)
        
        # Update beliefs
        result = self.k1.update(topic, evidence)
        
        # Assess uncertainty
        if "problem" in data:
            assessment = self.k1.assess(data["problem"])
            result["assessment"] = assessment
        
        return result
    
    def _run_k3(self, k1_result: Dict[str, Any], data: Dict[str, Any], 
                context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run K3 multi-perspective analysis."""
        # Prepare data for perspectives
        perspective_data = {
            "probability_below_target": data.get("probability_below_target", 0.5),
            "current_price": data.get("current_price", 100),
            "target_price": data.get("target_price", 100),
            "confidence": k1_result.get("confidence", 50),
        }
        
        # Get calibrated decision
        result = self.k3.calibrated_collapse(perspective_data)
        
        return result
    
    def _run_k7(self, k1_result: Dict[str, Any], k3_result: Dict[str, Any], 
                data: Dict[str, Any]) -> Dict[str, Any]:
        """Run K7 evaluation."""
        # Define expected outcomes
        expected = {
            "has_beliefs": True,
            "has_perspectives": True,
            "confidence_range": (0, 100)
        }
        
        # Define actual outcomes
        actual = {
            "has_beliefs": "beliefs" in k1_result,
            "has_perspectives": "verdict" in k3_result,
            "confidence": k3_result.get("confidence", 0)
        }
        
        # Evaluate
        result = self.k7.evaluate_result(expected, actual)
        
        return result
    
    def _calculate_confidence(self, k1_result: Dict, k3_result: Dict, 
                             k7_result: Dict) -> float:
        """Calculate combined confidence score."""
        # Weight factors
        k1_weight = 0.3  # Bayesian confidence
        k3_weight = 0.4  # Perspective agreement
        k7_weight = 0.3  # Evaluation score
        
        # Extract individual confidences
        k1_conf = k1_result.get("confidence", 50) / 100.0
        k3_conf = k3_result.get("confidence", 50) / 100.0
        k7_conf = k7_result.get("score", 0.5)
        
        # Weighted average
        combined = (k1_weight * k1_conf + 
                   k3_weight * k3_conf + 
                   k7_weight * k7_conf)
        
        return round(combined * 100, 2)
    
    def _generate_recommendation(self, k1_result: Dict, k3_result: Dict, 
                                k7_result: Dict) -> str:
        """Generate actionable recommendation."""
        verdict = k3_result.get("verdict", "HOLD")
        confidence = self._calculate_confidence(k1_result, k3_result, k7_result)
        
        if confidence > 80:
            strength = "STRONG"
        elif confidence > 60:
            strength = "MODERATE"
        else:
            strength = "WEAK"
        
        return f"{strength} {verdict} (confidence: {confidence}%)"
    
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Get pipeline execution statistics."""
        if not self.pipeline_history:
            return {"runs": 0}
        
        avg_confidence = sum(
            r["confidence"] for r in self.pipeline_history
        ) / len(self.pipeline_history)
        
        return {
            "runs": len(self.pipeline_history),
            "avg_confidence": round(avg_confidence, 2),
            "last_verdict": self.pipeline_history[-1].get("recommendation", "N/A")
        }
```

#### Task 3.3: E2E Tests with Mock LLM

**File:** `jagabot/tests/e2e/test_full_pipeline.py`  
**LOC:** ~250  

```python
"""End-to-end tests with mock LLM."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
from tempfile import TemporaryDirectory

class MockLLMProvider:
    """Mock LLM provider for testing."""
    
    def __init__(self):
        self.responses: Dict[str, str] = {}
        self.call_history: List[Dict[str, Any]] = []
    
    def register_response(self, prompt_pattern: str, response: str):
        """Register a response for a prompt pattern."""
        self.responses[prompt_pattern] = response
    
    async def chat(self, messages: list, tools: list = None, **kwargs):
        """Mock chat method."""
        # Record call
        self.call_history.append({
            "messages": messages,
            "tools": tools,
            "kwargs": kwargs
        })
        
        # Find matching response
        last_message = messages[-1]["content"] if messages else ""
        for pattern, response in self.responses.items():
            if pattern in last_message:
                return Mock(content=response, has_tool_calls=False)
        
        # Default response
        return Mock(content="Mock LLM response", has_tool_calls=False)
    
    def get_default_model(self) -> str:
        return "mock-model"

@pytest.mark.e2e
class TestFullAnalysisPipeline:
    """Test complete financial analysis flow."""
    
    @pytest.fixture
    def mock_provider(self):
        return MockLLMProvider()
    
    @pytest.fixture
    def temp_workspace(self):
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.mark.asyncio
    async def test_monte_carlo_analysis(self, mock_provider, temp_workspace):
        """Test Monte Carlo analysis pipeline."""
        # Setup mock responses
        mock_provider.register_response("monte_carlo", """
        Monte Carlo simulation complete.
        Probability of reaching target: 65%
        Confidence interval: [140, 160]
        """)
        
        # Import and run pipeline
        from jagabot.agent.tools.monte_carlo import MonteCarloTool
        
        tool = MonteCarloTool()
        result = await tool.execute(
            current_price=150.0,
            target_price=120.0,
            vix=58.0,
            days=30,
            simulations=1000
        )
        
        # Assert
        assert result is not None
        assert "probability" in result.lower() or "65" in result
    
    @pytest.mark.asyncio
    async def test_guardian_full_pipeline(self, mock_provider, temp_workspace):
        """Test Guardian 4-stage pipeline."""
        from jagabot.guardian.core import Jagabot
        
        guardian = Jagabot(workspace=temp_workspace)
        
        # Mock all subagents
        with patch('jagabot.guardian.subagents.websearch.websearch_agent') as mock_web, \
             patch('jagabot.guardian.subagents.support.support_agent') as mock_support, \
             patch('jagabot.guardian.subagents.billing.billing_agent') as mock_billing, \
             patch('jagabot.guardian.subagents.supervisor.supervisor_agent') as mock_supervisor:
            
            # Setup mock responses
            mock_web.return_value = {"news": [{"title": "Market Update"}]}
            mock_support.return_value = {"cv_analysis": {"risk": "MEDIUM"}}
            mock_billing.return_value = {"probability": 0.65, "equity": 50000}
            mock_supervisor.return_value = {"report": "Final analysis report"}
            
            # Run pipeline
            result = await guardian.handle_query(
                user_query="Analyze AAPL risk",
                portfolio={"capital": 100000, "positions": {}},
                market_data={"AAPL": 150.0}
            )
            
            # Assert all stages executed
            assert "web" in result or "report" in result
            mock_web.assert_called_once()
            mock_support.assert_called_once()
            mock_billing.assert_called_once()
            mock_supervisor.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_kernel_pipeline(self, mock_provider, temp_workspace):
        """Test K1→K3→K7 kernel composition."""
        from jagabot.kernels.composition import KernelPipeline
        
        pipeline = KernelPipeline(temp_workspace)
        
        data = {
            "topic": "AAPL analysis",
            "evidence": {"price": 150, "target": 120},
            "probability_below_target": 0.65,
            "current_price": 150,
            "target_price": 120
        }
        
        result = pipeline.analyze(data)
        
        # Assert pipeline completed
        assert "k1_beliefs" in result
        assert "k3_perspectives" in result
        assert "k7_evaluation" in result
        assert "confidence" in result
        assert "recommendation" in result
```

**Phase 3 Deliverables:**
- [ ] DynamicSkill class with runtime composition
- [ ] KernelPipeline class with K1→K3→K7 chaining
- [ ] E2E test suite with mock LLM
- [ ] Performance tracking for skills
- [ ] Pipeline statistics and monitoring

---

### PHASE 4: TOAD INTEGRATION (Parallel Track)
**Priority:** 🟡 HIGH  
**Effort:** ~25 hours  
**Dependencies:** Phase 1-3 (for full feature integration)

#### Task 4.1: Enhanced TOAD Bridge

**File:** `autojaga-toad/enhanced_bridge.py`  
**LOC:** ~200  

```python
"""Enhanced bridge with all JAGABOT features."""
from typing import List, Dict, Any, Optional
from pathlib import Path

class ToadJagabotBridge:
    """
    Full integration with all JAGABOT capabilities.
    Bridges TOAD UI with JAGABOT backend.
    """
    
    def __init__(self, workspace: Path | None = None):
        self.workspace = workspace or Path.home() / ".jagabot" / "workspace"
        
        # Initialize all components
        try:
            from jagabot.memory.vector_memory import VectorMemory
            self.memory = VectorMemory(self.workspace)
        except ImportError:
            from jagabot.agent.tools.memory_fleet import MemoryFleet
            self.memory = MemoryFleet(self.workspace)
        
        try:
            from jagabot.memory.knowledge_graph_enhanced import EnhancedKnowledgeGraph
            self.graph = EnhancedKnowledgeGraph(self.workspace)
        except ImportError:
            from jagabot.agent.tools.knowledge_graph import KnowledgeGraphTool
            self.graph = KnowledgeGraphTool()
        
        try:
            from jagabot.swarm.adaptive_planner import AdaptivePlanner
            self.swarm = AdaptivePlanner()
        except ImportError:
            from jagabot.swarm.planner import TaskPlanner
            self.swarm = TaskPlanner()
        
        try:
            from jagabot.skills.dynamic_skill import DynamicSkill
            self.skills = DynamicSkill(self.workspace)
        except ImportError:
            self.skills = None
        
        try:
            from jagabot.kernels.composition import KernelPipeline
            self.kernels = KernelPipeline(self.workspace)
        except ImportError:
            self.kernels = None
        
        # Tool registry
        self._register_tools()
    
    def _register_tools(self):
        """Register all 45+ tools."""
        from jagabot.agent.tool_loader import register_default_tools
        from jagabot.agent.tools.registry import ToolRegistry
        
        self.tools = ToolRegistry()
        register_default_tools(
            self.tools,
            workspace=self.workspace,
            restrict_to_workspace=False,
            exec_config=None,  # Use defaults
            brave_api_key=None,
            bus=None,
            subagents=None,
            cron_service=None,
        )
    
    def handle_query(self, query: str, files: List[str] = None, 
                    context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Handle user query with full pipeline."""
        result = {
            "query": query,
            "files": files or [],
            "stages": {}
        }
        
        # Stage 1: Semantic search in memory
        if hasattr(self.memory, 'semantic_search'):
            similar = self.memory.semantic_search(query)
            result["stages"]["memory"] = similar[:3]  # Top 3 results
        else:
            result["stages"]["memory"] = "Memory search not available"
        
        # Stage 2: Extract entities
        if hasattr(self.graph, 'analyze_text'):
            entities = self.graph.analyze_text(query)
            result["stages"]["entities"] = entities
        else:
            result["stages"]["entities"] = "Entity extraction not available"
        
        # Stage 3: Kernel analysis (if available)
        if self.kernels:
            kernel_data = {
                "topic": query[:50],
                "evidence": context or {},
            }
            kernel_result = self.kernels.analyze(kernel_data, context)
            result["stages"]["kernels"] = kernel_result
        else:
            # Fallback to tool execution
            result["stages"]["tools"] = "Kernel pipeline not available"
        
        # Stage 4: Format result
        result["formatted"] = self._format_result(result)
        
        return result
    
    def _format_result(self, result: Dict[str, Any]) -> str:
        """Format result for TOAD display."""
        lines = [
            "## Analysis Results",
            "",
            f"**Query:** {result['query']}",
            ""
        ]
        
        # Memory section
        if "memory" in result["stages"] and isinstance(result["stages"]["memory"], list):
            lines.append("### Relevant Memories")
            for mem in result["stages"]["memory"]:
                lines.append(f"- {mem.get('summary', mem.get('content', 'N/A'))}")
            lines.append("")
        
        # Entities section
        if "entities" in result["stages"] and isinstance(result["stages"]["entities"], dict):
            lines.append("### Extracted Entities")
            entities = result["stages"]["entities"]
            for entity_type, items in entities.get("entities", {}).items():
                if items:
                    lines.append(f"- **{entity_type}:** {', '.join(items)}")
            lines.append("")
        
        # Kernel section
        if "kernels" in result["stages"] and isinstance(result["stages"]["kernels"], dict):
            kernel_result = result["stages"]["kernels"]
            lines.append("### Analysis")
            lines.append(f"- **Confidence:** {kernel_result.get('confidence', 'N/A')}%")
            lines.append(f"- **Recommendation:** {kernel_result.get('recommendation', 'N/A')}")
            lines.append("")
        
        return "\n".join(lines)
```

#### Task 4.2: TOAD Configuration

**File:** `autojaga-toad/config.yaml`

```yaml
# TOAD-JAGABOT Integration Configuration
toad:
  theme: "monokai"
  mouse_support: true
  keybindings:
    run_analysis: "F5"
    save_result: "Ctrl+S"
    clear_screen: "Ctrl+L"

jagabot:
  workspace: "/root/.jagabot/workspace"
  
  features:
    memory:
      vector_embeddings: true
      semantic_search: true
      auto_consolidate: true
      consolidation_threshold: 10
    
    graph:
      entity_extraction: true
      relation_extraction: true
      auto_export: true
    
    swarm:
      adaptive_planning: true
      max_workers: 8
      timeout_multiplier: 2.0
      fallback_enabled: true
    
    kernels:
      composition: true
      confidence_scoring: true
      pipeline: "K1→K3→K7"
    
    skills:
      dynamic_composition: true
      performance_tracking: true
      auto_evolution: false  # Experimental
    
    tools:
      total_registered: 45
      financial_tools: 22
      utility_tools: 7
      v3_components: 7

  tests:
    unit_coverage_target: 85%
    integration_coverage_target: 70%
    e2e_coverage_target: 50%
  
  logging:
    level: "INFO"
    file: "/root/.jagabot/logs/toad_bridge.log"
    max_size_mb: 100
    backup_count: 5
```

**Phase 4 Deliverables:**
- [ ] ToadJagabotBridge class
- [ ] Configuration file
- [ ] Integration tests
- [ ] Documentation for TOAD users

---

## 📊 SUCCESS METRICS

| Metric | Before | Target | After | Status |
|--------|--------|--------|-------|--------|
| **Test Coverage (unit)** | 30% | 85% | ⏳ | Phase 1 |
| **Test Coverage (integration)** | 20% | 70% | ⏳ | Phase 1 |
| **Test Coverage (E2E)** | 0% | 50% | ⏳ | Phase 3 |
| **Memory Search** | Keyword | Semantic | ⏳ | Phase 2 |
| **KnowledgeGraph** | Static | Entity extraction | ⏳ | Phase 2 |
| **Swarm Planning** | Sequential | Adaptive | ⏳ | Phase 2 |
| **Skills** | Static | Dynamic | ⏳ | Phase 3 |
| **Kernels** | Isolated | Composed | ⏳ | Phase 3 |
| **TOAD Integration** | None | Full | ⏳ | Phase 4 |

---

## ⚠️ RISKS & MITIGATIONS

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **spaCy model download fails** | Medium | Low | Fallback to keyword extraction |
| **sentence-transformers slow** | Medium | Medium | Cache embeddings, async loading |
| **Test suite breaks existing code** | High | Medium | Run tests in isolated environment first |
| **TOAD integration conflicts** | Medium | High | Version pinning, compatibility layer |
| **Performance degradation** | Medium | Medium | Benchmark before/after, optimize hot paths |
| **Memory bloat from vectors** | Low | Low | Implement vector pruning, compression |

---

## 🚀 IMPLEMENTATION CHECKLIST

### Phase 1: Test Coverage (Week 1)
- [ ] 1.1.1 Create `test_memory_fleet.py`
- [ ] 1.1.2 Create `test_k1_bayesian.py`
- [ ] 1.1.3 Create `test_k3_perspective.py`
- [ ] 1.1.4 Create `test_evaluation.py`
- [ ] 1.1.5 Create `test_meta_learning.py`
- [ ] 1.1.6 Create `test_evolution.py`
- [ ] 1.1.7 Create `test_knowledge_graph.py`
- [ ] 1.2.1 Create `test_guardian_pipeline.py`
- [ ] 1.2.2 Create `test_swarm_orchestrator.py`
- [ ] 1.2.3 Create `test_tool_harness.py`
- [ ] 1.3.1 Create `test_telegram.py`
- [ ] 1.3.2 Create `test_slack.py`
- [ ] 1.3.3 Create `test_email.py`
- [ ] 1.4.1 Create `test_cli.py`
- [ ] Run full test suite
- [ ] Generate coverage report

### Phase 2: Core Enhancements (Week 2)
- [ ] 2.1.1 Create `vector_memory.py`
- [ ] 2.1.2 Add `semantic_search` action to MemoryFleetTool
- [ ] 2.1.3 Test vector memory
- [ ] 2.2.1 Create `knowledge_graph_enhanced.py`
- [ ] 2.2.2 Download spaCy model
- [ ] 2.2.3 Test entity extraction
- [ ] 2.3.1 Create `adaptive_planner.py`
- [ ] 2.3.2 Integrate with existing swarm
- [ ] 2.3.3 Test adaptive replanning

### Phase 3: Advanced Features (Week 3)
- [ ] 3.1.1 Create `dynamic_skill.py`
- [ ] 3.1.2 Test skill composition
- [ ] 3.2.1 Create `composition.py` (KernelPipeline)
- [ ] 3.2.2 Test K1→K3→K7 pipeline
- [ ] 3.3.1 Create `test_full_pipeline.py`
- [ ] 3.3.2 Add mock LLM tests
- [ ] 3.3.3 Run E2E test suite

### Phase 4: TOAD Integration (Parallel)
- [ ] 4.1.1 Create `enhanced_bridge.py`
- [ ] 4.1.2 Test bridge with all components
- [ ] 4.2.1 Create `config.yaml`
- [ ] 4.2.2 Test configuration loading
- [ ] 4.2.3 Document TOAD integration

---

## 📝 NEXT STEPS

1. **Review this plan** - Confirm priorities and timeline
2. **Start Phase 1** - Begin with test coverage (highest priority)
3. **Track progress** - Update checklist as tasks complete
4. **Iterate** - Adjust plan based on findings during implementation

---

**Ready to begin implementation?** 

Run this to start Phase 1:
```bash
cd /root/nanojaga
mkdir -p jagabot/tests/unit
mkdir -p jagabot/tests/integration
mkdir -p jagabot/tests/e2e
```

Then I'll create the first test file: `test_memory_fleet.py`
