"""Test that tool harness catches unquoted file creation claims."""

import pytest
from pathlib import Path
from unittest.mock import patch

from jagabot.core.tool_harness import ToolHarness


class TestUnquotedFileClaims:
    """Test verification of unquoted file creation claims."""

    def test_caught_unquoted_created_file(self, tmp_path):
        """Test that 'Created file.txt' without quotes is verified."""
        harness = ToolHarness(workspace=tmp_path)
        
        # Agent claims it created a file but didn't use write_file tool
        content = "✅ Created verify_test/data.txt with 50 random numbers"
        tools_used = []  # No tools used
        
        result = harness.verify_response(content, tools_used)
        
        # Should have verification warning
        assert "VERIFICATION FAILED" in result or "VERIFICATION WARNING" in result
        assert "verify_test/data.txt" in result

    def test_caught_unquoted_created_file_with_write_tool_but_missing(self, tmp_path):
        """Test that file claim is caught even when write_file was used but file missing."""
        harness = ToolHarness(workspace=tmp_path)
        
        content = "✅ Created data.txt with 50 random numbers"
        tools_used = ["write_file"]  # write_file was used
        
        result = harness.verify_response(content, tools_used)
        
        # Should have warning about missing file
        assert "VERIFICATION WARNING" in result
        assert "data.txt" in result
        assert "NOT found on disk" in result

    def test_passes_when_file_exists(self, tmp_path):
        """Test that verification passes when file actually exists."""
        # Create the file first
        test_file = tmp_path / "test_data.txt"
        test_file.write_text("test content")
        
        harness = ToolHarness(workspace=tmp_path)
        
        content = "✅ Created test_data.txt with test content"
        tools_used = ["write_file"]
        
        result = harness.verify_response(content, tools_used)
        
        # Should pass without warnings
        assert "VERIFICATION" not in result

    def test_quoted_filename_still_works(self, tmp_path):
        """Test that quoted filenames are still verified."""
        harness = ToolHarness(workspace=tmp_path)
        
        content = '✅ Created `data.txt` with 50 random numbers'
        tools_used = []
        
        result = harness.verify_response(content, tools_used)
        
        assert "VERIFICATION" in result

    def test_multiple_unquoted_files(self, tmp_path):
        """Test detection of multiple unquoted file claims."""
        harness = ToolHarness(workspace=tmp_path)
        
        content = (
            "✅ Created data.txt with numbers\n"
            "✅ Generated report.md with analysis\n"
            "✅ Saved config.yaml with settings"
        )
        tools_used = []
        
        result = harness.verify_response(content, tools_used)
        
        assert "VERIFICATION" in result
        assert "data.txt" in result
        assert "report.md" in result
        assert "config.yaml" in result

    def test_future_tense_not_flagged(self, tmp_path):
        """Test that future tense (planning) is not flagged."""
        harness = ToolHarness(workspace=tmp_path)
        
        content = "I will create data.txt tomorrow"
        tools_used = []
        
        result = harness.verify_response(content, tools_used)
        
        # Should not flag future tense
        assert "VERIFICATION" not in result

    def test_mixed_quoted_and_unquoted(self, tmp_path):
        """Test detection of both quoted and unquoted file claims."""
        harness = ToolHarness(workspace=tmp_path)
        
        content = (
            '✅ Created `quoted.txt` with data\n'
            '✅ Generated unquoted.md with analysis'
        )
        tools_used = []
        
        result = harness.verify_response(content, tools_used)
        
        assert "VERIFICATION" in result
        assert "quoted.txt" in result
        assert "unquoted.md" in result

    def test_backtick_normalized_no_duplicates(self, tmp_path):
        """Test that backtick-quoted and unquoted versions are normalized to same path."""
        harness = ToolHarness(workspace=tmp_path)
        
        # Same file mentioned with and without backticks
        content = (
            '✅ Created `verify_test/data.txt` with numbers\n'
            'The file verify_test/data.txt contains 50 numbers'
        )
        tools_used = []
        
        result = harness.verify_response(content, tools_used)
        
        assert "VERIFICATION" in result
        # Should only appear once (normalized), not duplicated
        assert result.count("verify_test/data.txt") < 4  # Not multiple duplicates

    def test_written_paths_cross_reference(self, tmp_path):
        """Test that files written by tools are matched even if claim uses shorter path."""
        # Create the actual file at the written path
        written_dir = tmp_path / "verify_test"
        written_dir.mkdir(parents=True, exist_ok=True)
        written_file = written_dir / "data.txt"
        written_file.write_text("test content")
        
        harness = ToolHarness(workspace=tmp_path)
        
        # Simulate write_file tool result
        ex = type('obj', (object,), {
            'tool_name': 'write_file',
            'status': 'complete',
            'result_text': 'Successfully wrote 150 bytes to verify_test/data.txt (verified on disk)'
        })()
        harness._history.append(ex)
        
        # Agent claims "data.txt" but tool wrote "verify_test/data.txt"
        content = "✅ Created data.txt with 50 numbers"
        tools_used = ["write_file"]
        
        result = harness.verify_response(content, tools_used)
        
        # Should NOT have warning because file exists at written path
        assert "VERIFICATION WARNING" not in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
