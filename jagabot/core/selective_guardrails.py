"""
Selective Guardrail Loading

Instead of loading all 11 rules (2098 tokens) every call,
loads only rules relevant to the current query domain.

Domain → Rules mapping:
  financial  → Rules 1, 2, 4, 6, 8, 9 (~800 tokens)
  research   → Rules 1, 3, 4, 5, 7    (~600 tokens)
  general    → Rules 1, 4             (~200 tokens)
  subagent   → Rules 2, 3             (~300 tokens)
  always     → Rule 1 (source hierarchy) always included

Token savings vs full load:
  financial: 2098 → 800 = saves 1298 tokens
  research:  2098 → 600 = saves 1498 tokens
  general:   2098 → 200 = saves 1898 tokens
"""

from __future__ import annotations
import re
from pathlib import Path
from loguru import logger


SKILL_PATH = Path("/root/nanojaga/jagabot/skills/adversarial-guardrails/SKILL.md")

# Which rules apply to which domains
DOMAIN_RULES: dict[str, list[int]] = {
    "financial":  [1, 2, 4, 6, 8, 9],
    "research":   [1, 3, 4, 5, 7],
    "engineering":[1, 2, 3],
    "subagent":   [2, 3],
    "calibration":[1, 4, 7],
    "general":    [1, 4],
}

# Rules always included regardless of domain
ALWAYS_RULES = [1]


def _parse_rules(content: str) -> dict[int, str]:
    """Parse SKILL.md into individual rules by number."""
    rules: dict[int, str] = {}

    # Split on RULE headers: ### RULE N: or ## RULE N: or RULE N:
    pattern = r'(?:#{1,3}\s+)?(?:🔴\s+)?RULE\s+(\d+)[:\s]'
    parts = re.split(pattern, content, flags=re.IGNORECASE)

    # parts = [preamble, num, content, num, content, ...]
    i = 1
    while i < len(parts) - 1:
        try:
            rule_num = int(parts[i])
            rule_body = parts[i + 1] if i + 1 < len(parts) else ""
            rules[rule_num] = f"### RULE {rule_num}\n{rule_body.strip()}"
            i += 2
        except (ValueError, IndexError):
            i += 1

    return rules


def load_for_domain(domain: str) -> str:
    """
    Load only the guardrail rules relevant to a domain.
    Returns formatted string ready for system prompt injection.
    """
    if not SKILL_PATH.exists():
        logger.debug(f"SelectiveGuardrails: skill file not found")
        return ""

    content = SKILL_PATH.read_text(encoding="utf-8")
    rules   = _parse_rules(content)

    if not rules:
        # Fallback: return full content if parsing fails
        logger.debug("SelectiveGuardrails: parse failed, returning full content")
        return content

    # Get rules for this domain
    rule_nums = set(DOMAIN_RULES.get(domain, DOMAIN_RULES["general"]))
    rule_nums.update(ALWAYS_RULES)

    selected = []
    for num in sorted(rule_nums):
        if num in rules:
            selected.append(rules[num])

    if not selected:
        return ""

    full_size    = len(content)
    partial_size = sum(len(r) for r in selected)
    savings      = full_size - partial_size

    logger.debug(
        f"SelectiveGuardrails: domain={domain} "
        f"rules={sorted(rule_nums)} "
        f"({partial_size}/{full_size} chars, saved ~{savings//4} tokens)"
    )

    header = f"## Adversarial Guardrails (Active for: {domain})\n"
    return header + "\n\n".join(selected)


def get_rule_count(domain: str) -> int:
    """Return number of rules that would be loaded for a domain."""
    rules = set(DOMAIN_RULES.get(domain, DOMAIN_RULES["general"]))
    rules.update(ALWAYS_RULES)
    return len(rules)
