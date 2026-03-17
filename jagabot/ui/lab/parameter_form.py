"""Dynamic Streamlit parameter form from JSON Schema.

Generates the right widget for each parameter type:
  - string + enum → selectbox
  - string → text_input
  - number/integer → number_input (with min/max from schema)
  - boolean → checkbox
  - array/object → text_area (JSON)
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ParameterForm:
    """Render a Streamlit form from a JSON Schema ``parameters`` dict."""

    def render(
        self,
        tool_name: str,
        schema: dict[str, Any],
        method: str | None = None,
    ) -> dict[str, Any]:
        """Build widgets and return filled parameter dict.

        Requires Streamlit runtime. Falls back to returning defaults
        if Streamlit is not available (useful for testing).
        """
        try:
            import streamlit as st
        except ImportError:
            return self.defaults(schema, method=method)

        return self._render_st(st, tool_name, schema, method)

    # ------------------------------------------------------------------
    # Streamlit rendering
    # ------------------------------------------------------------------

    def _render_st(
        self, st: Any, tool_name: str, schema: dict[str, Any], method: str | None
    ) -> dict[str, Any]:
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        result: dict[str, Any] = {}

        if method:
            result["method"] = method

        for pname, pschema in props.items():
            if pname == "method":
                continue  # handled by method selector in parent
            if pname == "params":
                # Dispatch sub-params — render inner schema if available
                inner = pschema.get("properties", {})
                if inner:
                    sub_result = {}
                    for sp_name, sp_schema in inner.items():
                        key = f"lab_{tool_name}_{method or ''}_{sp_name}"
                        sub_result[sp_name] = self._widget(st, sp_name, sp_schema, key)
                    result["params"] = sub_result
                else:
                    key = f"lab_{tool_name}_params"
                    raw = st.text_area(
                        "params (JSON)", value="{}", key=key, height=120
                    )
                    try:
                        result["params"] = json.loads(raw)
                    except json.JSONDecodeError:
                        result["params"] = {}
                continue

            key = f"lab_{tool_name}_{method or ''}_{pname}"
            req_label = " *" if pname in required else ""
            result[pname] = self._widget(st, f"{pname}{req_label}", pschema, key)

        return result

    def _widget(self, st: Any, label: str, schema: dict[str, Any], key: str) -> Any:
        ptype = schema.get("type", "string")
        desc = schema.get("description", "")

        if "enum" in schema:
            options = schema["enum"]
            return st.selectbox(label, options=options, key=key, help=desc)

        if ptype in ("number", "integer"):
            min_val = schema.get("minimum")
            max_val = schema.get("maximum")
            default = schema.get("default", 0.0 if ptype == "number" else 0)
            kwargs: dict[str, Any] = {"key": key, "help": desc}
            if min_val is not None:
                kwargs["min_value"] = float(min_val) if ptype == "number" else int(min_val)
            if max_val is not None:
                kwargs["max_value"] = float(max_val) if ptype == "number" else int(max_val)
            return st.number_input(label, value=default, **kwargs)

        if ptype == "boolean":
            default = schema.get("default", False)
            return st.checkbox(label, value=default, key=key, help=desc)

        if ptype in ("array", "object"):
            default = schema.get("default", [] if ptype == "array" else {})
            raw = st.text_area(
                label,
                value=json.dumps(default, indent=2),
                key=key,
                help=desc,
                height=100,
            )
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return default

        # Default: string
        default = schema.get("default", "")
        return st.text_input(label, value=str(default), key=key, help=desc)

    # ------------------------------------------------------------------
    # Non-Streamlit fallback (for testing)
    # ------------------------------------------------------------------

    @staticmethod
    def defaults(schema: dict[str, Any], method: str | None = None) -> dict[str, Any]:
        """Return default values for all parameters (no Streamlit needed)."""
        props = schema.get("properties", {})
        result: dict[str, Any] = {}
        if method:
            result["method"] = method

        _TYPE_DEFAULTS = {
            "string": "",
            "number": 0.0,
            "integer": 0,
            "boolean": False,
            "array": [],
            "object": {},
        }

        for pname, pschema in props.items():
            if pname == "method":
                continue
            if "default" in pschema:
                result[pname] = pschema["default"]
            elif "enum" in pschema:
                result[pname] = pschema["enum"][0]
            else:
                result[pname] = _TYPE_DEFAULTS.get(pschema.get("type", "string"), "")
        return result

    @staticmethod
    def widget_type_for(schema: dict[str, Any]) -> str:
        """Return the Streamlit widget type name for a given JSON Schema property."""
        if "enum" in schema:
            return "selectbox"
        ptype = schema.get("type", "string")
        return {
            "number": "number_input",
            "integer": "number_input",
            "boolean": "checkbox",
            "array": "text_area",
            "object": "text_area",
            "string": "text_input",
        }.get(ptype, "text_input")
