"""
JIT (Just-in-Time) Tool Schema Injection

Instead of sending full tool schemas every call:
  BEFORE: 5 tools × 400 chars = 2000 chars = ~500 tokens
  AFTER:  5 tool stubs × 40 chars = 200 chars = ~50 tokens
          + full schema injected only when tool is called

Flow:
  1. Send stub schemas to LLM (name + 1-line description only)
  2. LLM decides to call yahoo_finance
  3. Full yahoo_finance schema injected into next message
  4. LLM calls with correct parameters
  5. Result returned

Token savings: ~450 tokens per call on tool schema overhead
"""

from __future__ import annotations
import json
from loguru import logger


def make_stub_schema(full_schema: dict) -> dict:
    """
    Convert a full tool schema to a minimal stub.
    Keeps name and a one-line description only.
    Strips all parameter definitions.
    """
    fn = full_schema.get("function", {})
    name = fn.get("name", "unknown")
    desc = fn.get("description", "")

    # Keep only first line of description
    short_desc = desc.split("\n")[0][:80].strip()

    # Keep parameter names but strip descriptions
    fn_params = fn.get("parameters", {})
    props = fn_params.get("properties", {})
    slim_props = {}
    for param_name, param_def in props.items():
        slim_props[param_name] = {
            "type": param_def.get("type", "string"),
            "enum": param_def["enum"] if "enum" in param_def else None,
        }
        # Remove None values
        slim_props[param_name] = {k: v for k, v in slim_props[param_name].items() if v is not None}

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": short_desc,
            "parameters": {
                "type": "object",
                "properties": slim_props,
                "required": fn_params.get("required", []),
            },
        },
    }


def make_full_schemas_message(tool_names: list[str], all_schemas: list[dict]) -> str:
    """
    Build a system message injecting full schemas for requested tools.
    Called when LLM uses a tool for the first time this turn.
    """
    schema_map = {s["function"]["name"]: s for s in all_schemas}
    lines = ["[TOOL SCHEMAS — full parameter definitions]\n"]

    for name in tool_names:
        if name in schema_map:
            schema_json = json.dumps(schema_map[name], indent=2)
            lines.append(f"Tool: {name}\n{schema_json}\n")

    return "\n".join(lines)


class JITSchemaManager:
    """
    Manages JIT tool schema injection.

    Usage:
        jit = JITSchemaManager(full_schemas)
        stub_payload = jit.get_stubs()          # send this to LLM
        # LLM calls a tool...
        jit.mark_used("yahoo_finance")          # track which tools used
        full_msg = jit.get_injection_message()  # inject full schemas
    """

    def __init__(self, full_schemas: list[dict], enabled: bool = True):
        self._full    = {s["function"]["name"]: s for s in full_schemas}
        self._stubs   = {name: make_stub_schema(s) for name, s in self._full.items()}
        self._used:   set[str] = set()
        self._injected: set[str] = set()
        self.enabled  = enabled
        self.saved_chars = 0

    def get_stubs(self) -> list[dict]:
        """Return stub schemas for all tools — send these to LLM initially."""
        if not self.enabled:
            return list(self._full.values())

        stubs = list(self._stubs.values())

        # Calculate savings
        full_size  = sum(len(json.dumps(s)) for s in self._full.values())
        stub_size  = sum(len(json.dumps(s)) for s in stubs)
        self.saved_chars = full_size - stub_size

        logger.debug(
            f"JIT: sending {len(stubs)} stubs "
            f"(saved ~{self.saved_chars//4} tokens vs full schemas)"
        )
        return stubs

    def mark_used(self, tool_name: str) -> bool:
        """Mark a tool as used this turn. Returns True if new."""
        if tool_name not in self._used:
            self._used.add(tool_name)
            return True
        return False

    def needs_injection(self, tool_name: str) -> bool:
        """Check if full schema needs to be injected for this tool."""
        return (
            self.enabled
            and tool_name in self._full
            and tool_name not in self._injected
        )

    def get_full_schema(self, tool_name: str) -> dict | None:
        """Get full schema for a specific tool."""
        return self._full.get(tool_name)

    def mark_injected(self, tool_name: str) -> None:
        """Mark tool schema as already injected this turn."""
        self._injected.add(tool_name)

    def get_stats(self) -> dict:
        return {
            "tools":      len(self._full),
            "used":       list(self._used),
            "injected":   list(self._injected),
            "saved_chars": self.saved_chars,
            "saved_tokens": self.saved_chars // 4,
        }
