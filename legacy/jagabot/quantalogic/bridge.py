"""Bridge adapter: wrap a QuantaLogic Tool into a jagabot Tool.

QuantaLogic Tool (Pydantic model):
  - arguments: List[ToolArgument] with arg_type strings
  - execute(**kwargs) -> Any  (sync)
  - async_execute(**kwargs) -> Any

Jagabot Tool (ABC):
  - parameters: JSON Schema dict
  - execute(**kwargs) -> str  (async)
"""

from __future__ import annotations

import json
from typing import Any

from jagabot.agent.tools.base import Tool as JagabotTool


# Mapping from QuantaLogic arg_type strings to JSON Schema types
_TYPE_MAP: dict[str, str] = {
    "string": "string",
    "str": "string",
    "int": "integer",
    "integer": "integer",
    "float": "number",
    "number": "number",
    "bool": "boolean",
    "boolean": "boolean",
    "list": "array",
    "dict": "object",
    "object": "object",
}


def _ql_type_to_json_schema(arg_type: str) -> str:
    """Convert a QuantaLogic arg_type string to a JSON Schema type."""
    base = arg_type.split("[")[0].strip().lower()
    return _TYPE_MAP.get(base, "string")


def _ql_args_to_json_schema(arguments: list) -> dict[str, Any]:
    """Convert QuantaLogic ToolArgument list to a JSON Schema parameters object."""
    properties: dict[str, Any] = {}
    required: list[str] = []

    for arg in arguments:
        name = arg.name
        schema_type = _ql_type_to_json_schema(arg.arg_type or "string")
        prop: dict[str, Any] = {"type": schema_type}

        if arg.description:
            prop["description"] = arg.description
        if arg.example:
            prop["examples"] = [arg.example]
        if arg.default is not None:
            prop["default"] = arg.default

        properties[name] = prop
        if arg.required:
            required.append(name)

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


class ToolBridge(JagabotTool):
    """Wraps a QuantaLogic Tool instance as a jagabot Tool.

    Usage::

        from quantalogic.tools import SomeTool
        from jagabot.quantalogic.bridge import ToolBridge

        bridge = ToolBridge(SomeTool())
        registry.register(bridge)
    """

    def __init__(self, ql_tool: Any) -> None:
        """
        Args:
            ql_tool: A QuantaLogic Tool instance (subclass of quantalogic_toolbox Tool).
        """
        self._ql_tool = ql_tool
        self._name = ql_tool.name
        self._description = ql_tool.description or f"QuantaLogic tool: {ql_tool.name}"
        self._parameters = _ql_args_to_json_schema(getattr(ql_tool, "arguments", []) or [])

    # ------------------------------------------------------------------
    # Jagabot Tool ABC
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters(self) -> dict[str, Any]:
        return self._parameters

    async def execute(self, **kwargs: Any) -> str:
        """Delegate to the QuantaLogic tool, converting result to string."""
        try:
            if hasattr(self._ql_tool, "async_execute"):
                result = await self._ql_tool.async_execute(**kwargs)
            else:
                result = self._ql_tool.execute(**kwargs)
        except Exception as exc:
            return f"QuantaLogic tool error ({self._name}): {exc}"

        if isinstance(result, str):
            return result
        try:
            return json.dumps(result, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(result)
