"""SkillTriggerTool — Tool ABC wrapper for the auto-triggering system.

Actions:
  detect          — detect the best skill for a query + market data
  list_triggers   — show all registered trigger rules
  register        — add a new trigger rule at runtime
"""

from __future__ import annotations

import json
from typing import Any

from jagabot.agent.tools.base import Tool
from jagabot.skills.trigger import SkillTrigger


class SkillTriggerTool(Tool):
    name = "skill_trigger"
    description = (
        "Auto-detect which financial skill/workflow to use based on "
        "the user query and market conditions. Returns the best-matching "
        "skill with confidence score."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["detect", "list_triggers", "register"],
                "description": "Action to perform.",
            },
            "query": {
                "type": "string",
                "description": "User query text (for detect).",
            },
            "market_data": {
                "type": "object",
                "description": "Market conditions dict, e.g. {\"vix\": 45} (for detect).",
            },
            "skill_name": {
                "type": "string",
                "description": "Name of the skill to register (for register).",
            },
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Trigger keywords (for register).",
            },
            "conditions": {
                "type": "object",
                "description": "Market conditions for boost (for register).",
            },
        },
        "required": ["action"],
    }

    def __init__(self) -> None:
        self._trigger = SkillTrigger()

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "")

        if action == "detect":
            query = kwargs.get("query", "")
            market = kwargs.get("market_data", {})
            if not query:
                return json.dumps({"error": "query is required for detect"})
            result = self._trigger.detect(query, market)
            return json.dumps(result)

        if action == "list_triggers":
            return json.dumps(self._trigger.get_triggers(), indent=2)

        if action == "register":
            skill_name = kwargs.get("skill_name", "")
            keywords = kwargs.get("keywords", [])
            conditions = kwargs.get("conditions", {})
            if not skill_name or not keywords:
                return json.dumps({"error": "skill_name and keywords required"})
            rule = self._trigger.register_trigger(skill_name, keywords, conditions)
            return json.dumps({
                "registered": True,
                "skill": rule.skill,
                "keywords": rule.keywords,
            })

        return json.dumps({"error": f"Unknown action: {action}"})
