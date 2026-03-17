"""Test JSON normalization for agent loop plan parsing."""

import json
import pytest

from jagabot.agent.loop import _normalize_json_escapes


class TestNormalizeJsonEscapes:
    """Test the _normalize_json_escapes helper function."""

    def test_simple_json_no_changes_needed(self):
        """Test that simple JSON without escape issues passes through."""
        test_str = '[{"tool":"test","args":{"content":"hello"}}]'
        normalized = _normalize_json_escapes(test_str)
        parsed = json.loads(normalized)
        assert parsed == [{"tool": "test", "args": {"content": "hello"}}]

    def test_double_escaped_newline(self):
        """Test that double-escaped newlines (\\\\n) are converted to single (\\n)."""
        # LLMs often output \\n which appears as \\\\n in Python string
        test_str = r'[{"tool":"write_file","args":{"content":"92\n75\n13"}}]'
        normalized = _normalize_json_escapes(test_str)
        parsed = json.loads(normalized)
        assert parsed == [{"tool": "write_file", "args": {"content": "92\n75\n13"}}]

    def test_double_escaped_tab(self):
        """Test that double-escaped tabs are converted."""
        test_str = r'[{"tool":"test","args":{"content":"tab\there"}}]'
        normalized = _normalize_json_escapes(test_str)
        parsed = json.loads(normalized)
        assert parsed == [{"tool": "test", "args": {"content": "tab\there"}}]

    def test_double_escaped_quote(self):
        """Test that double-escaped quotes are converted."""
        test_str = r'[{"tool":"test","args":{"content":"say \"hello\""}}]'
        normalized = _normalize_json_escapes(test_str)
        parsed = json.loads(normalized)
        assert parsed == [{"tool": "test", "args": {"content": 'say "hello"'}}]

    def test_realistic_llm_output(self):
        """Test with a realistic LLM output containing multiple escape sequences."""
        # This simulates what an LLM might output when asked to create a file with numbers
        test_str = r'''[{"tool":"write_file","args":{"path":"/tmp/data.txt","content":"92\n75\n13\n48\n62"}}]'''
        normalized = _normalize_json_escapes(test_str)
        parsed = json.loads(normalized)
        assert len(parsed) == 1
        assert parsed[0]["tool"] == "write_file"
        assert parsed[0]["args"]["content"] == "92\n75\n13\n48\n62"

    def test_multiple_actions(self):
        """Test with multiple actions in the plan."""
        test_str = r'''[
            {"tool":"write_file","args":{"path":"/tmp/data.txt","content":"92\n75\n13"}},
            {"tool":"exec","args":{"command":"cat /tmp/data.txt"}}
        ]'''
        normalized = _normalize_json_escapes(test_str)
        parsed = json.loads(normalized)
        assert len(parsed) == 2
        assert parsed[0]["tool"] == "write_file"
        assert parsed[1]["tool"] == "exec"

    def test_already_correct_json(self):
        """Test that already-correct JSON is not broken."""
        test_str = '{"tool":"test","args":{"value":42}}'
        normalized = _normalize_json_escapes(test_str)
        parsed = json.loads(normalized)
        assert parsed == {"tool": "test", "args": {"value": 42}}

    def test_backslash_handling(self):
        """Test that backslashes in paths are preserved."""
        # Simple case: path with backslashes
        test_str = r'[{"tool":"test","args":{"path":"C:\\temp\\file.txt"}}]'
        normalized = _normalize_json_escapes(test_str)
        parsed = json.loads(normalized)
        # Backslashes should be preserved for JSON to parse correctly
        assert parsed[0]["tool"] == "test"
        assert "path" in parsed[0]["args"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
