"""
Unit tests for Phase 3 Advanced Features.
Tests Dynamic Skill System and Kernel Composition Pipeline.
"""
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
import json


class TestDynamicSkill:
    """Test DynamicSkill functionality."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def skills(self, temp_workspace: Path):
        from jagabot.skills.dynamic_skill import DynamicSkill
        return DynamicSkill(workspace=temp_workspace)
    
    def test_creation(self, skills):
        """Test DynamicSkill creation."""
        assert skills is not None
        assert skills.workspace.exists()
        assert skills.skills_dir.exists()
    
    def test_compose_skill(self, skills):
        """Test skill composition."""
        definition = skills.compose_skill(
            name="test_analysis",
            steps=["financial_cv", "monte_carlo", "decision_engine"],
            metadata={"category": "analysis", "difficulty": "medium"}
        )
        
        assert definition["name"] == "test_analysis"
        assert len(definition["steps"]) == 3
        assert "test_analysis" in skills.skill_definitions
    
    def test_register_custom_skill(self, skills):
        """Test registering custom skill function."""
        def custom_func(data):
            return {"result": "custom", "input": data}
        
        skills.register_skill("custom_skill", custom_func)
        
        assert "custom_skill" in skills.skill_definitions
        assert skills.skill_definitions["custom_skill"]["type"] == "custom"
    
    def test_list_skills(self, skills):
        """Test listing skills."""
        skills.compose_skill("skill1", ["step1"])
        skills.compose_skill("skill2", ["step2"])
        
        skill_list = skills.list_skills()
        
        assert len(skill_list) == 2
        assert "skill1" in skill_list
        assert "skill2" in skill_list
    
    def test_get_performance(self, skills):
        """Test performance retrieval."""
        skills.compose_skill("test_skill", ["step1"])
        skills.record_outcome("test_skill", success=True, duration=1.5)
        skills.record_outcome("test_skill", success=False, duration=2.0)
        
        perf = skills.get_performance("test_skill")
        
        assert perf["calls"] == 2
        assert perf["successes"] == 1
        assert perf["success_rate"] == 0.5
    
    def test_get_rankings(self, skills):
        """Test skill rankings."""
        for i in range(5):
            skills.compose_skill(f"skill_{i}", [f"step_{i}"])
            for j in range(10):
                skills.record_outcome(f"skill_{i}", success=(j > 2), duration=1.0)
        
        rankings = skills.get_rankings(limit=3)
        
        assert len(rankings) <= 3
        assert "success_rate" in rankings[0]
    
    def test_get_best_skill(self, skills):
        """Test getting best performing skill."""
        # Create skills with different success rates
        skills.compose_skill("good_skill", ["step1"])
        skills.compose_skill("bad_skill", ["step2"])
        
        for i in range(10):
            skills.record_outcome("good_skill", success=True, duration=1.0)
            skills.record_outcome("bad_skill", success=(i < 3), duration=1.0)
        
        best = skills.get_best_skill(min_calls=5)
        
        assert best == "good_skill"
    
    def test_evolve_skill(self, skills):
        """Test skill evolution."""
        skills.compose_skill("evolving_skill", ["step1", "step2"])
        
        evolved = skills.evolve_skill(
            "evolving_skill",
            new_steps=["step1", "step2", "step3"]
        )
        
        assert len(evolved["steps"]) == 3
        assert evolved.get("version", 1) > 1
    
    def test_delete_skill(self, skills):
        """Test skill deletion."""
        skills.compose_skill("to_delete", ["step1"])
        
        success = skills.delete_skill("to_delete")
        
        assert success is True
        assert "to_delete" not in skills.skill_definitions
    
    def test_get_stats(self, skills):
        """Test statistics retrieval."""
        skills.compose_skill("skill1", ["step1"])
        skills.record_outcome("skill1", success=True, duration=1.0)
        
        stats = skills.get_stats()
        
        assert "total_skills" in stats
        assert "total_calls" in stats
        assert "overall_success_rate" in stats
    
    def test_persistence(self, temp_workspace):
        """Test that skills persist across instances."""
        from jagabot.skills.dynamic_skill import DynamicSkill
        
        # Create instance and compose skill
        skills_v1 = DynamicSkill(workspace=temp_workspace)
        skills_v1.compose_skill("persistent", ["step1", "step2"])
        
        # Create new instance
        skills_v2 = DynamicSkill(workspace=temp_workspace)
        
        # Should have loaded existing skill
        assert "persistent" in skills_v2.skill_definitions


class TestDynamicSkillTool:
    """Test DynamicSkillTool wrapper."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.mark.asyncio
    async def test_compose_action(self, temp_workspace):
        """Test compose action."""
        from jagabot.skills.dynamic_skill import DynamicSkillTool
        
        tool = DynamicSkillTool(workspace=temp_workspace)
        result = await tool.execute(
            action="compose",
            name="test_skill",
            steps=["step1", "step2"]
        )
        
        data = json.loads(result)
        assert data["name"] == "test_skill"
    
    @pytest.mark.asyncio
    async def test_list_action(self, temp_workspace):
        """Test list action."""
        from jagabot.skills.dynamic_skill import DynamicSkillTool
        
        tool = DynamicSkillTool(workspace=temp_workspace)
        
        # Compose some skills
        await tool.execute(action="compose", name="skill1", steps=["s1"])
        await tool.execute(action="compose", name="skill2", steps=["s2"])
        
        result = await tool.execute(action="list")
        data = json.loads(result)
        
        assert "skills" in data
        assert data["count"] == 2
    
    @pytest.mark.asyncio
    async def test_stats_action(self, temp_workspace):
        """Test stats action."""
        from jagabot.skills.dynamic_skill import DynamicSkillTool
        
        tool = DynamicSkillTool(workspace=temp_workspace)
        result = await tool.execute(action="stats")
        
        data = json.loads(result)
        assert "total_skills" in data
    
    @pytest.mark.asyncio
    async def test_rankings_action(self, temp_workspace):
        """Test rankings action."""
        from jagabot.skills.dynamic_skill import DynamicSkillTool
        
        tool = DynamicSkillTool(workspace=temp_workspace)
        result = await tool.execute(action="rankings", limit=5)
        
        data = json.loads(result)
        assert "rankings" in data
    
    @pytest.mark.asyncio
    async def test_best_action(self, temp_workspace):
        """Test best action."""
        from jagabot.skills.dynamic_skill import DynamicSkillTool
        
        tool = DynamicSkillTool(workspace=temp_workspace)
        result = await tool.execute(action="best", min_calls=0)
        
        data = json.loads(result)
        assert "best_skill" in data
    
    @pytest.mark.asyncio
    async def test_delete_action(self, temp_workspace):
        """Test delete action."""
        from jagabot.skills.dynamic_skill import DynamicSkillTool
        
        tool = DynamicSkillTool(workspace=temp_workspace)
        
        # Compose then delete
        await tool.execute(action="compose", name="to_delete", steps=["s1"])
        result = await tool.execute(action="delete", name="to_delete")
        
        data = json.loads(result)
        assert data["deleted"] is True


class TestKernelPipeline:
    """Test KernelPipeline functionality."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def pipeline(self, temp_workspace: Path):
        from jagabot.kernels.composition import KernelPipeline
        return KernelPipeline(workspace=temp_workspace)
    
    def test_creation(self, pipeline):
        """Test pipeline creation."""
        assert pipeline is not None
        assert pipeline.workspace.exists()
    
    def test_analyze_basic(self, pipeline):
        """Test basic analysis."""
        data = {
            "topic": "test_analysis",
            "probability_below_target": 0.40,
            "current_price": 150,
            "target_price": 180
        }
        
        result = pipeline.analyze(data)
        
        assert isinstance(result, dict)
        assert "confidence" in result
        assert "recommendation" in result
        assert "k1_beliefs" in result
        assert "k3_perspectives" in result
        assert "k7_evaluation" in result
    
    def test_analyze_with_context(self, pipeline):
        """Test analysis with context."""
        data = {
            "topic": "contextual_analysis",
            "probability_below_target": 0.35,
            "current_price": 150,
            "target_price": 180
        }
        context = {"market_sentiment": "positive", "sector": "technology"}
        
        result = pipeline.analyze(data, context)
        
        assert isinstance(result, dict)
        assert "confidence" in result
    
    def test_get_stats(self, pipeline):
        """Test statistics retrieval."""
        # Run some analyses
        for i in range(3):
            pipeline.analyze({
                "topic": f"analysis_{i}",
                "probability_below_target": 0.4 + i * 0.1,
                "current_price": 150,
                "target_price": 180
            })
        
        stats = pipeline.get_stats()
        
        assert stats["runs"] == 3
        assert "avg_confidence" in stats
        assert "avg_execution_time_ms" in stats
    
    def test_get_history(self, pipeline):
        """Test history retrieval."""
        for i in range(5):
            pipeline.analyze({
                "topic": f"history_{i}",
                "probability_below_target": 0.5,
                "current_price": 150,
                "target_price": 180
            })
        
        history = pipeline.get_history(limit=3)
        
        assert len(history) == 3
        assert "confidence" in history[0]
    
    def test_clear_history(self, pipeline):
        """Test clearing history."""
        pipeline.analyze({
            "topic": "test",
            "probability_below_target": 0.5,
            "current_price": 150,
            "target_price": 180
        })
        
        pipeline.clear_history()
        stats = pipeline.get_stats()
        
        assert stats["runs"] == 0
    
    def test_confidence_calculation(self, pipeline):
        """Test confidence calculation."""
        # High confidence scenario
        result_high = pipeline.analyze({
            "topic": "high_conf",
            "probability_below_target": 0.20,  # Low risk
            "current_price": 150,
            "target_price": 180
        })
        
        # Low confidence scenario
        result_low = pipeline.analyze({
            "topic": "low_conf",
            "probability_below_target": 0.80,  # High risk
            "current_price": 150,
            "target_price": 120
        })
        
        assert "confidence" in result_high
        assert "confidence" in result_low


class TestKernelPipelineTool:
    """Test KernelPipelineTool wrapper."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.mark.asyncio
    async def test_analyze_action(self, temp_workspace):
        """Test analyze action."""
        from jagabot.kernels.composition import KernelPipelineTool
        
        tool = KernelPipelineTool(workspace=temp_workspace)
        result = await tool.execute(
            action="analyze",
            data={
                "topic": "test",
                "probability_below_target": 0.40,
                "current_price": 150,
                "target_price": 180
            }
        )
        
        data = json.loads(result)
        assert "confidence" in data
        assert "recommendation" in data
    
    @pytest.mark.asyncio
    async def test_stats_action(self, temp_workspace):
        """Test stats action."""
        from jagabot.kernels.composition import KernelPipelineTool
        
        tool = KernelPipelineTool(workspace=temp_workspace)
        result = await tool.execute(action="stats")
        
        data = json.loads(result)
        assert "runs" in data
    
    @pytest.mark.asyncio
    async def test_history_action(self, temp_workspace):
        """Test history action."""
        from jagabot.kernels.composition import KernelPipelineTool
        
        tool = KernelPipelineTool(workspace=temp_workspace)
        
        # Run analysis
        await tool.execute(
            action="analyze",
            data={
                "topic": "test",
                "probability_below_target": 0.5,
                "current_price": 150,
                "target_price": 180
            }
        )
        
        result = await tool.execute(action="history", limit=5)
        data = json.loads(result)
        
        assert "history" in data
    
    @pytest.mark.asyncio
    async def test_clear_action(self, temp_workspace):
        """Test clear action."""
        from jagabot.kernels.composition import KernelPipelineTool
        
        tool = KernelPipelineTool(workspace=temp_workspace)
        result = await tool.execute(action="clear")
        
        data = json.loads(result)
        assert data["cleared"] is True


class TestE2EPipeline:
    """End-to-end pipeline tests."""
    
    @pytest.fixture
    def temp_workspace(self) -> Path:
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_full_analysis_flow(self, temp_workspace):
        """Test complete analysis flow from composition to execution."""
        from jagabot.skills.dynamic_skill import DynamicSkill
        from jagabot.kernels.composition import KernelPipeline
        
        # 1. Compose analysis skill
        skills = DynamicSkill(workspace=temp_workspace)
        skills.compose_skill(
            name="full_analysis",
            steps=["financial_cv", "monte_carlo", "decision_engine"],
            metadata={"category": "analysis"}
        )
        
        # 2. Run kernel pipeline
        pipeline = KernelPipeline(workspace=temp_workspace)
        result = pipeline.analyze({
            "topic": "AAPL analysis",
            "probability_below_target": 0.35,
            "current_price": 150,
            "target_price": 180
        })
        
        # 3. Verify results
        assert result["confidence"] > 0
        assert "recommendation" in result
        
        # 4. Record outcome
        skills.record_outcome(
            "full_analysis",
            success=result["confidence"] > 50,
            duration=result["execution_time_ms"] / 1000
        )
        
        # 5. Check performance
        perf = skills.get_performance("full_analysis")
        assert perf["calls"] == 1
