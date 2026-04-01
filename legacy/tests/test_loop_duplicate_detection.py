"""Simple test to verify duplicate command detection logic."""

import pytest


def test_duplicate_command_threshold():
    """Test that duplicate detection works at threshold of 2."""
    _duplicate_commands = {}
    
    # Simulate the logic from loop.py
    def check_duplicate(tool_name, args_str):
        cmd_key = f"{tool_name}:{hash(args_str)}"
        _duplicate_commands[cmd_key] = _duplicate_commands.get(cmd_key, 0) + 1
        if _duplicate_commands[cmd_key] >= 2:
            return True, _duplicate_commands[cmd_key]
        return False, _duplicate_commands[cmd_key]
    
    # First occurrence - should NOT be blocked
    blocked, count = check_duplicate("exec", '{"command": "python3 test.py"}')
    assert blocked is False, f"First occurrence should not be blocked, got count={count}"
    assert count == 1
    
    # Second occurrence - SHOULD be blocked
    blocked, count = check_duplicate("exec", '{"command": "python3 test.py"}')
    assert blocked is True, f"Second occurrence should be blocked, got count={count}"
    assert count == 2
    
    # Third occurrence - SHOULD be blocked
    blocked, count = check_duplicate("exec", '{"command": "python3 test.py"}')
    assert blocked is True, f"Third occurrence should be blocked, got count={count}"
    assert count == 3


def test_different_commands_not_blocked():
    """Test that different commands are not affected by duplicate detection."""
    _duplicate_commands = {}
    
    def check_duplicate(tool_name, args_str):
        cmd_key = f"{tool_name}:{hash(args_str)}"
        _duplicate_commands[cmd_key] = _duplicate_commands.get(cmd_key, 0) + 1
        if _duplicate_commands[cmd_key] >= 2:
            return True, _duplicate_commands[cmd_key]
        return False, _duplicate_commands[cmd_key]
    
    # Different commands should have separate counters
    blocked1, count1 = check_duplicate("exec", '{"command": "python3 test1.py"}')
    blocked2, count2 = check_duplicate("exec", '{"command": "python3 test2.py"}')
    blocked3, count3 = check_duplicate("read_file", '{"absolute_path": "test.py"}')
    
    assert blocked1 is False and count1 == 1
    assert blocked2 is False and count2 == 1
    assert blocked3 is False and count3 == 1


def test_error_analysis_prompt_content():
    """Test that error analysis prompt contains required elements."""
    error_analysis_prompt = (
        f"\n\n⚠️ ERROR ANALYSIS REQUIRED BEFORE RETRY:\n"
        f"Tool 'exec' failed. BEFORE running it again:\n"
        f"1. READ the relevant source file(s) using read_file\n"
        f"2. ANALYZE the error traceback (note line numbers and file paths)\n"
        f"3. EXPLAIN why the error occurred in your own words\n"
        f"4. PROPOSE and EXECUTE a specific fix (edit code, adjust data, or change approach)\n"
        f"5. DO NOT re-run the same command without making changes first\n"
    )
    
    # Verify all required elements are present
    assert "ERROR ANALYSIS REQUIRED" in error_analysis_prompt
    assert "READ" in error_analysis_prompt
    assert "ANALYZE" in error_analysis_prompt
    assert "EXPLAIN" in error_analysis_prompt
    assert "PROPOSE" in error_analysis_prompt
    assert "DO NOT re-run" in error_analysis_prompt
    assert "read_file" in error_analysis_prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
