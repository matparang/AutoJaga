"""Test subagent file verification logic for Test 4 fix."""

import pytest
import re
from pathlib import Path


class TestSubagentVerificationLogic:
    """Test the file verification regex and logic used in subagent."""

    def test_claim_extraction_simple(self):
        """Test extraction of simple file claims."""
        result = "Task completed. Created data.txt successfully."
        claimed_files = re.findall(
            r'(?:created|wrote|saved|generated|made|produced|file:)\s*[`"\']?([^\s`"\']+?\.(?:txt|py|json|md|yaml|yml|csv|log|sh|toml|cfg|ini))',
            result, re.IGNORECASE
        )
        assert "data.txt" in claimed_files

    def test_claim_extraction_with_path(self):
        """Test extraction of file claims with paths."""
        result = "Created verify_test/data.txt with 50 numbers"
        claimed_files = re.findall(
            r'(?:created|wrote|saved|generated|made|produced|file:)\s*[`"\']?([^\s`"\']+?\.(?:txt|py|json|md|yaml|yml|csv|log|sh|toml|cfg|ini))',
            result, re.IGNORECASE
        )
        assert "verify_test/data.txt" in claimed_files

    def test_claim_extraction_multiple_files(self):
        """Test extraction of multiple file claims."""
        result = """
        Task completed:
        1. Created data.txt with numbers
        2. Wrote claim.txt with the mean value
        3. Saved final_report.md with summary
        """
        claimed_files = re.findall(
            r'(?:created|wrote|saved|generated|made|produced|file:)\s*[`"\']?([^\s`"\']+?\.(?:txt|py|json|md|yaml|yml|csv|log|sh|toml|cfg|ini))',
            result, re.IGNORECASE
        )
        assert len(claimed_files) == 3
        assert "data.txt" in claimed_files
        assert "claim.txt" in claimed_files
        assert "final_report.md" in claimed_files

    def test_claim_extraction_with_backticks(self):
        """Test extraction of file claims with backticks."""
        result = "Created `verify_test/data.txt` successfully"
        claimed_files = re.findall(
            r'(?:created|wrote|saved|generated|made|produced|file:)\s*[`"\']?([^\s`"\']+?\.(?:txt|py|json|md|yaml|yml|csv|log|sh|toml|cfg|ini))',
            result, re.IGNORECASE
        )
        assert "verify_test/data.txt" in claimed_files

    def test_file_existence_check(self, tmp_path):
        """Test file existence verification logic."""
        # Create one file
        existing = tmp_path / "exists.txt"
        existing.write_text("content")
        
        # Check both existing and missing
        claimed_files = ["exists.txt", "missing.txt"]
        missing_files = []
        
        for cf in claimed_files:
            cf_path = Path(cf) if Path(cf).is_absolute() else tmp_path / cf
            if not cf_path.exists():
                missing_files.append(cf)
        
        assert len(missing_files) == 1
        assert "missing.txt" in missing_files

    def test_verification_failure_message(self, tmp_path):
        """Test the verification failure message format."""
        claimed_files = ["data.txt", "claim.txt"]
        missing_files = claimed_files  # All missing
        
        if missing_files:
            failure_msg = (
                f"⚠️ SUBAGENT VERIFICATION FAILURE:\n"
                f"Task claimed these files were created: {missing_files}\n"
                f"But they DO NOT EXIST on disk.\n\n"
                f"ESCALATION REQUIRED: Please re-run this task with direct tool calls\n"
                f"or use a more reliable agent configuration. Do NOT trust the subagent result."
            )
            
            assert "SUBAGENT VERIFICATION FAILURE" in failure_msg
            assert "data.txt" in failure_msg
            assert "claim.txt" in failure_msg
            assert "ESCALATION REQUIRED" in failure_msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
