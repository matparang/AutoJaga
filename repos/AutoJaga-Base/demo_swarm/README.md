# Mangliwood Research Swarm Configuration

## Overview

This directory contains configuration for the demo Mangliwood research swarm — a multi-agent system for botanical research.

## Specialists

The swarm includes 5 specialist agents:

### 1. Botanist
- **Role:** Styrax Biology Expert
- **Expertise:** Mangliwood (Styrax) taxonomy, morphology, ecology
- **Tools:** web_search, read_file

### 2. Materials Scientist
- **Role:** Resin Properties Expert
- **Expertise:** Natural resins, extraction methods, material properties
- **Tools:** web_search, read_file

### 3. Chemist
- **Role:** Benzoin Compound Analyst
- **Expertise:** Cinnamic acid derivatives, benzoin compounds, antimicrobial activity
- **Tools:** web_search

### 4. Pathologist
- **Role:** Antimicrobial Research
- **Expertise:** Infectious diseases, natural antimicrobials, mechanisms of action
- **Tools:** web_search

### 5. Synthesizer
- **Role:** Research Integration
- **Expertise:** Cross-disciplinary synthesis, connecting perspectives
- **Tools:** read_file, write_file

## Running the Swarm

```bash
python -m autojaga

> /swarm What are the therapeutic applications of Mangliwood compounds?
```

The conductor will:
1. Dispatch the query to all 5 specialists in parallel
2. Collect their responses
3. Synthesize into a unified analysis

## Example Queries

```
/swarm What compounds in Styrax benzoin have antimicrobial activity?
/swarm How is benzoin resin traditionally harvested?
/swarm What are the conservation concerns for Mangliwood trees?
/swarm Compare Styrax benzoin with Styrax tonkinensis chemically
```

## Customization

To create a custom swarm, see `autojaga/swarm/conductor.py`:

```python
from autojaga.swarm import Conductor, SpecialistConfig

my_specialists = [
    SpecialistConfig(
        name="Expert1",
        role="Domain Expert",
        persona="Your specialist description...",
        tools=["web_search"],
    ),
    # Add more specialists...
]

swarm = Conductor(
    provider=provider,
    workspace=workspace,
    specialists=my_specialists,
)

result = await swarm.execute("Your research question")
```
