import pytest
import os
from pathlib import Path


def test_research_skill_structure():
    """Test that research skill has required files and structure"""
    skill_path = Path("/root/nanojaga/jagabot/skills/research")
    
    # Check required files
    assert (skill_path / "SKILL.md").exists()
    assert (skill_path / "__init__.py").exists()
    assert (skill_path / "core.py").exists()
    
    # Check directories
    assert (skill_path / "templates").exists()
    assert (skill_path / "config").exists()
    assert (skill_path / "phases").exists()
    assert (skill_path / "tests").exists()
    
    # Check template files
    assert (skill_path / "templates" / "debate_prompts.json").exists()
    assert (skill_path / "templates" / "planning_template.md").exists()
    assert (skill_path / "templates" / "synthesis_template.md").exists()
    
    # Check config files
    assert (skill_path / "config" / "domains.yaml").exists()
    
    # Check phase files
    assert (skill_path / "phases" / "phase1_debate.py").exists()
    assert (skill_path / "phases" / "phase2_planning.py").exists()
    assert (skill_path / "phases" / "phase3_execution.py").exists()
    assert (skill_path / "phases" / "phase4_synthesis.py").exists()


def test_research_skill_import():
    """Test that research skill can be imported"""
    try:
        from jagabot.skills.research import ResearchSkill
        assert ResearchSkill is not None
    except ImportError:
        pytest.fail("ResearchSkill cannot be imported")


def test_research_skill_instance():
    """Test that research skill instance can be created"""
    try:
        from jagabot.skills.research import ResearchSkill
        skill = ResearchSkill()
        assert hasattr(skill, 'run')
        assert callable(getattr(skill, 'run'))
    except Exception as e:
        pytest.fail(f"ResearchSkill instance creation failed: {e}")

if __name__ == "__main__":
    pytest.main([__file__])