"""Test auditor disk verification for Test 4 fix."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from jagabot.core.auditor import ResponseAuditor
from jagabot.core.tool_harness import ToolHarness


class TestAuditorDiskVerification:
    """Test that auditor verifies files on disk after corrective actions."""

    def test_verify_pending_files_empty_list(self, tmp_path):
        """Test that empty pending files returns approved."""
        harness = ToolHarness(workspace=tmp_path)
        auditor = ResponseAuditor(harness, max_retries=2)
        
        all_exist, still_missing = auditor.verify_pending_files(tmp_path)
        
        assert all_exist is True
        assert still_missing == []

    def test_verify_pending_files_file_exists(self, tmp_path):
        """Test that existing file passes verification."""
        # Create the file first
        test_file = tmp_path / "test_data.txt"
        test_file.write_text("test content")
        
        harness = ToolHarness(workspace=tmp_path)
        auditor = ResponseAuditor(harness, max_retries=2)
        auditor._pending_missing_files = ["test_data.txt"]
        
        all_exist, still_missing = auditor.verify_pending_files(tmp_path)
        
        assert all_exist is True
        assert still_missing == []

    def test_verify_pending_files_file_missing(self, tmp_path):
        """Test that missing file fails verification."""
        harness = ToolHarness(workspace=tmp_path)
        auditor = ResponseAuditor(harness, max_retries=2)
        auditor._pending_missing_files = ["missing_file.txt"]
        
        all_exist, still_missing = auditor.verify_pending_files(tmp_path)
        
        assert all_exist is False
        assert len(still_missing) == 1
        assert "missing_file.txt" in still_missing[0]

    def test_verify_pending_files_mixed(self, tmp_path):
        """Test verification with some files existing and some missing."""
        # Create one file
        existing_file = tmp_path / "exists.txt"
        existing_file.write_text("content")
        
        harness = ToolHarness(workspace=tmp_path)
        auditor = ResponseAuditor(harness, max_retries=2)
        auditor._pending_missing_files = ["exists.txt", "missing.txt"]
        
        all_exist, still_missing = auditor.verify_pending_files(tmp_path)
        
        assert all_exist is False
        assert len(still_missing) == 1
        assert "missing.txt" in still_missing[0]

    def test_verify_pending_files_absolute_path(self, tmp_path):
        """Test verification with absolute paths."""
        # Create file with absolute path
        test_file = tmp_path / "subdir" / "test.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("content")
        
        harness = ToolHarness(workspace=tmp_path)
        auditor = ResponseAuditor(harness, max_retries=2)
        auditor._pending_missing_files = [str(test_file)]
        
        all_exist, still_missing = auditor.verify_pending_files(tmp_path)
        
        assert all_exist is True
        assert still_missing == []

    def test_verify_pending_files_absolute_path_missing(self, tmp_path):
        """Test verification with absolute path for missing file."""
        missing_file = tmp_path / "missing" / "file.txt"
        
        harness = ToolHarness(workspace=tmp_path)
        auditor = ResponseAuditor(harness, max_retries=2)
        auditor._pending_missing_files = [str(missing_file)]
        
        all_exist, still_missing = auditor.verify_pending_files(tmp_path)
        
        assert all_exist is False
        assert len(still_missing) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
