# 🧪 RESEARCH SKILL v1.0
*Last Updated: 2026-03-14*

## 🎯 PURPOSE
Conduct autonomous research using 4-phase pipeline:
1. **Idea Exploration** - Tri-agent debate (Bull/Bear/Buffett)
2. **Experiment Planning** - Main agent methodology design
3. **Execution** - Quad-agent swarm for verified results
4. **Synthesis** - Tri-agent interpretation and reporting

## 📋 CAPABILITIES

### Phase 1: Idea Exploration (Tri-Agent)
```yaml
agents:
  - bull: "Optimistic perspective, identifies opportunities"
  - bear: "Skeptical perspective, identifies risks"
  - buffett: "Value perspective, long-term thinking"
output: research_proposal.md
hallucination_allowed: true  # FEATURE, not bug!
```

Phase 2: Experiment Planning (Main Agent)

```yaml
agent: autojaga_main
inputs: 
  - research_proposal.md
output: experiment_plan.json
hallucination_allowed: false  # MUST BE PRECISE
validation: schema_validation
```

Phase 3: Execution (Quad-Agent)

```yaml
agents:
  - worker: "Executes tasks"
  - verifier: "Checks accuracy"
  - adversary: "Tests robustness"
  - planner: "Adapts if needed"
outputs:
  - results.json
  - verified_data/
hallucination_allowed: false
verification: harness + disk
```

Phase 4: Synthesis (Tri-Agent)

```yaml
agents: [bull, bear, buffett]
inputs:
  - experiment_plan.json
  - results.json
  - verified_data/
output: research_summary.md
hallucination_allowed: true  # Interpretation OK
```

🚀 USAGE

Basic Research Request

```python
from jagabot.skills.research import ResearchSkill

skill = ResearchSkill()
result = skill.run(
    topic="cryptocurrency market trends",
    depth="comprehensive"
)
```

Advanced Configuration

```python
result = skill.run(
    topic="renewable energy investments",
    config={
        "phase1": {"rounds": 3},
        "phase2": {"methodology": "comparative"},
        "phase3": {"workers": 4},
        "phase4": {"format": "academic"}
    }
)
```

🔧 CONFIGURATION

domains.yaml

```yaml
domains:
  finance:
    debate_prompts: finance_prompts.json
    metrics: ["volatility", "roi", "risk"]
    
  technology:
    debate_prompts: tech_prompts.json
    metrics: ["adoption", "innovation", "scalability"]
    
  science:
    debate_prompts: science_prompts.json
    metrics: ["reproducibility", "significance", "impact"]
```

📊 OUTPUT STRUCTURE

research_proposal.md

```markdown
# Research Proposal: [Topic]

## Bull Perspective
- Opportunity 1
- Opportunity 2

## Bear Perspective
- Risk 1
- Risk 2

## Buffett Perspective
- Long-term value 1
- Long-term value 2

## Recommended Focus
[Consensus area]
```

experiment_plan.json

```json
{
  "methodology": "comparative analysis",
  "steps": [
    {"action": "collect_data", "sources": ["a", "b"]},
    {"action": "analyze", "metrics": ["mean", "volatility"]}
  ],
  "success_criteria": ["accuracy > 0.95", "files_exist"]
}
```

research_summary.md

```markdown
# Research Summary: [Topic]

## Key Findings
- Finding 1 (Bull-supported)
- Finding 2 (Bear-supported)
- Finding 3 (Buffett-supported)

## Methodology
[How it was done]

## Results
[Verified data summary]

## Conclusions
[Balanced interpretation]

## Next Steps
[Future research directions]
```

🧪 TESTING

```bash
# Test complete research pipeline
pytest jagabot/skills/research/tests/test_pipeline.py

# Test individual phases
pytest jagabot/skills/research/tests/test_phase1.py
pytest jagabot/skills/research/tests/test_phase2.py
pytest jagabot/skills/research/tests/test_phase3.py
pytest jagabot/skills/research/tests/test_phase4.py
```

🔄 VERSION HISTORY

Version Date Changes
v1.0 2026-03-14 Initial release - 4-phase research pipeline
v1.1 - Planned: Multi-domain support
v2.0 - Planned: Learning from past research
