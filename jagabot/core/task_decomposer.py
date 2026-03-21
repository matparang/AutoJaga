"""
TaskDecomposer — classifies and decomposes tasks before answer generation.

Forces the agent to identify:
  1. Task type (diagnosis/analysis/recommendation/factual/creative)
  2. Stakes level (LOW/MEDIUM/HIGH/CATASTROPHIC)
  3. Missing variables (what info is needed but absent)
  4. Output contract (what the answer MUST contain)
  5. Reasoning mode (fast/systematic/adversarial/calibrated)

Runs as a pre-pass before main response generation.
Injects decomposition into system context.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class TaskDecomposition:
    """Result of task decomposition."""
    task_type:       str          # diagnosis/analysis/recommendation/factual/creative
    stakes:          str          # LOW/MEDIUM/HIGH/CATASTROPHIC
    missing_vars:    list[str]    # what info is needed but not provided
    output_contract: list[str]    # what the answer MUST contain
    reasoning_mode:  str          # fast/systematic/adversarial/calibrated
    domain:          str          # financial/risk/operations/health/strategy/general
    one_liner:       str          # "This is a X task requiring Y"


# Task type signals
TASK_SIGNALS = {
    "diagnosis": [
        "why", "what caused", "root cause", "failure", "broke",
        "what went wrong", "diagnose", "debug", "what breaks",
    ],
    "analysis": [
        "analyze", "analysis", "assess", "evaluate", "examine",
        "risk", "compare", "measure", "quantify",
    ],
    "recommendation": [
        "should i", "recommend", "advise", "what to do",
        "best approach", "suggest", "what would you do",
        "buy", "sell", "invest", "hire", "fire",
    ],
    "factual": [
        "what is", "what are", "how does", "define",
        "price", "rate", "when", "who", "where",
    ],
    "creative": [
        "write", "draft", "create", "generate", "design",
        "brainstorm", "ideas", "suggest new",
    ],
}

# Domain signals
DOMAIN_SIGNALS = {
    "financial":   ["stock", "price", "invest", "portfolio", "risk", "return", "market", "financial"],
    "risk":        ["risk", "failure", "scenario", "disaster", "disruption", "crisis", "threat"],
    "operations":  ["supplier", "production", "supply chain", "logistics", "process", "workflow"],
    "health":      ["medical", "health", "diagnosis", "symptom", "treatment", "patient"],
    "strategy":    ["strategy", "competitive", "market position", "growth", "expansion"],
}

# Output contracts per task type
OUTPUT_CONTRACTS = {
    "diagnosis": [
        "what breaks first",
        "failure type (sensor/model/decision/execution)",
        "causal chain",
        "intervention lag vs threat velocity",
        "what assumption fails first",
    ],
    "analysis": [
        "controlled variable",
        "observed variable (leading or lagging)",
        "quantified threshold",
        "confidence with evidence basis",
        "what would change the conclusion",
    ],
    "recommendation": [
        "explicit recommendation (not hedged)",
        "confidence level with justification",
        "top 2 risks of this recommendation",
        "decision rule: IF/THEN/ELSE",
        "when to reverse this recommendation",
    ],
    "factual": [
        "direct answer",
        "source quality",
        "confidence",
    ],
    "creative": [
        "deliverable",
        "constraints respected",
    ],
}

# Reasoning modes per task type + stakes
REASONING_MODES = {
    ("diagnosis",       "HIGH"):         "adversarial",
    ("diagnosis",       "CATASTROPHIC"): "adversarial",
    ("analysis",        "HIGH"):         "systematic",
    ("analysis",        "CATASTROPHIC"): "adversarial",
    ("recommendation",  "HIGH"):         "calibrated",
    ("recommendation",  "CATASTROPHIC"): "adversarial",
    ("factual",         "LOW"):          "fast",
    ("factual",         "MEDIUM"):       "fast",
    ("creative",        "LOW"):          "fast",
}


def decompose(query: str, stake_level: str = None) -> TaskDecomposition:
    """
    Decompose a task before answer generation.
    Returns structured decomposition to inject into context.
    """
    q_lower = query.lower()

    # Detect task type
    task_type = "analysis"  # default
    for t_type, signals in TASK_SIGNALS.items():
        if any(s in q_lower for s in signals):
            task_type = t_type
            break

    # Detect domain
    domain = "general"
    for d, signals in DOMAIN_SIGNALS.items():
        if any(s in q_lower for s in signals):
            domain = d
            break

    # Detect stakes if not provided
    if not stake_level:
        if any(w in q_lower for w in ["life savings", "all-in", "irreversible", "catastrophic"]):
            stake_level = "CATASTROPHIC"
        elif any(w in q_lower for w in ["invest", "buy", "sell", "risk", "medical", "legal"]):
            stake_level = "HIGH"
        elif any(w in q_lower for w in ["analyze", "assess", "compare", "research"]):
            stake_level = "MEDIUM"
        else:
            stake_level = "LOW"

    # Identify missing variables
    missing = []
    if task_type in ("analysis", "diagnosis"):
        if domain == "financial" and not re.search(r'\b[A-Z]{2,5}\b|\$\d+', query):
            missing.append("specific asset or dollar amount not specified")
        if domain == "risk" and "timeframe" not in q_lower and "horizon" not in q_lower:
            missing.append("time horizon not specified")
        if "threshold" not in q_lower and "when" not in q_lower:
            missing.append("escalation threshold not defined")

    # Get output contract
    contract = OUTPUT_CONTRACTS.get(task_type, OUTPUT_CONTRACTS["analysis"])

    # Get reasoning mode
    mode_key = (task_type, stake_level)
    reasoning_mode = REASONING_MODES.get(mode_key, "systematic")

    # Build one-liner
    one_liner = f"This is a {stake_level}-stakes {task_type} task in the {domain} domain requiring {reasoning_mode} reasoning."

    decomp = TaskDecomposition(
        task_type       = task_type,
        stakes          = stake_level,
        missing_vars    = missing,
        output_contract = contract,
        reasoning_mode  = reasoning_mode,
        domain          = domain,
        one_liner       = one_liner,
    )

    logger.debug(
        f"TaskDecomposer: {task_type}/{domain}/{stake_level} "
        f"→ {reasoning_mode} mode, {len(contract)} output requirements"
    )

    return decomp


def build_injection(decomp: TaskDecomposition) -> str:
    """Build system prompt injection from decomposition."""
    lines = [
        "\n[TASK DECOMPOSITION]",
        f"Type: {decomp.task_type} | Domain: {decomp.domain} | Stakes: {decomp.stakes}",
        f"Mode: {decomp.reasoning_mode} reasoning",
    ]

    if decomp.missing_vars:
        lines.append(f"⚠️ Missing variables: {', '.join(decomp.missing_vars)}")
        lines.append("→ State assumptions explicitly before proceeding")

    lines.append("\n[OUTPUT CONTRACT] Your response MUST include:")
    for i, req in enumerate(decomp.output_contract, 1):
        lines.append(f"  {i}. {req}")

    lines.append("\n[REASONING CONSTRAINT]")
    if decomp.reasoning_mode == "adversarial":
        lines.append("Apply adversarial mode: find what breaks first before recommending fixes.")
    elif decomp.reasoning_mode == "calibrated":
        lines.append("Apply calibrated mode: state confidence with evidence basis. No symmetric percentages.")
    elif decomp.reasoning_mode == "systematic":
        lines.append("Apply systematic mode: follow output contract fields in order.")
    else:
        lines.append("Apply fast mode: direct answer, minimal elaboration.")

    return "\n".join(lines)
