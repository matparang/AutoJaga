"""Tests for v3.8.0 — Anthropic Financial Plugin Integration.

Validates plugin skill discovery, loading, trigger matching, and metadata.
"""

import pytest
from pathlib import Path

from jagabot.agent.skills import SkillsLoader, BUILTIN_SKILLS_DIR
from jagabot.skills.trigger import SkillTrigger


# ── Skill Discovery ─────────────────────────────────────────────────────


class TestPluginDiscovery:
    @pytest.fixture
    def loader(self):
        return SkillsLoader(
            workspace=Path("/tmp/_test_no_workspace"),
            builtin_skills_dir=BUILTIN_SKILLS_DIR,
        )

    def test_discovers_all_plugins(self, loader):
        """Should discover at least 53 plugin skills + original builtins."""
        skills = loader.list_skills(filter_unavailable=False)
        assert len(skills) >= 53

    def test_financial_analysis_skills(self, loader):
        """Should find all 9 fa- prefixed skills."""
        skills = loader.list_skills(filter_unavailable=False)
        fa = [s for s in skills if s["name"].startswith("fa-")]
        assert len(fa) == 9
        names = {s["name"] for s in fa}
        assert "fa-dcf-model" in names
        assert "fa-comps-analysis" in names
        assert "fa-lbo-model" in names

    def test_equity_research_skills(self, loader):
        """Should find all 9 er- prefixed skills."""
        skills = loader.list_skills(filter_unavailable=False)
        er = [s for s in skills if s["name"].startswith("er-")]
        assert len(er) == 9
        names = {s["name"] for s in er}
        assert "er-earnings-analysis" in names
        assert "er-initiating-coverage" in names

    def test_investment_banking_skills(self, loader):
        """Should find all 9 ib- prefixed skills."""
        skills = loader.list_skills(filter_unavailable=False)
        ib = [s for s in skills if s["name"].startswith("ib-")]
        assert len(ib) == 9
        names = {s["name"] for s in ib}
        assert "ib-merger-model" in names
        assert "ib-pitch-deck" in names

    def test_private_equity_skills(self, loader):
        """Should find all 9 pe- prefixed skills."""
        skills = loader.list_skills(filter_unavailable=False)
        pe = [s for s in skills if s["name"].startswith("pe-")]
        assert len(pe) == 9
        names = {s["name"] for s in pe}
        assert "pe-ic-memo" in names
        assert "pe-deal-screening" in names

    def test_wealth_management_skills(self, loader):
        """Should find all 6 wm- prefixed skills."""
        skills = loader.list_skills(filter_unavailable=False)
        wm = [s for s in skills if s["name"].startswith("wm-")]
        assert len(wm) == 6
        names = {s["name"] for s in wm}
        assert "wm-financial-plan" in names
        assert "wm-tax-loss-harvesting" in names

    def test_partner_lseg_skills(self, loader):
        """Should find all 8 lseg- prefixed skills."""
        skills = loader.list_skills(filter_unavailable=False)
        lseg = [s for s in skills if s["name"].startswith("lseg-")]
        assert len(lseg) == 8

    def test_partner_spglobal_skills(self, loader):
        """Should find all 3 spg- prefixed skills."""
        skills = loader.list_skills(filter_unavailable=False)
        spg = [s for s in skills if s["name"].startswith("spg-")]
        assert len(spg) == 3

    def test_original_builtins_still_present(self, loader):
        """Original builtin skills should still be discoverable."""
        skills = loader.list_skills(filter_unavailable=False)
        names = {s["name"] for s in skills}
        assert "financial" in names
        assert "memory" in names


# ── Skill Loading ────────────────────────────────────────────────────────


class TestPluginLoading:
    @pytest.fixture
    def loader(self):
        return SkillsLoader(
            workspace=Path("/tmp/_test_no_workspace"),
            builtin_skills_dir=BUILTIN_SKILLS_DIR,
        )

    def test_load_dcf_model(self, loader):
        """Should load fa-dcf-model content."""
        content = loader.load_skill("fa-dcf-model")
        assert content is not None
        assert "DCF" in content or "dcf" in content.lower()

    def test_load_earnings_analysis(self, loader):
        """Should load er-earnings-analysis content."""
        content = loader.load_skill("er-earnings-analysis")
        assert content is not None
        assert "earnings" in content.lower()

    def test_load_merger_model(self, loader):
        """Should load ib-merger-model content."""
        content = loader.load_skill("ib-merger-model")
        assert content is not None
        assert "merger" in content.lower()

    def test_load_ic_memo(self, loader):
        """Should load pe-ic-memo content."""
        content = loader.load_skill("pe-ic-memo")
        assert content is not None

    def test_load_financial_plan(self, loader):
        """Should load wm-financial-plan content."""
        content = loader.load_skill("wm-financial-plan")
        assert content is not None

    def test_load_nonexistent_returns_none(self, loader):
        """Unknown skill should return None."""
        assert loader.load_skill("nonexistent-skill-xyz") is None


# ── Skill Metadata ───────────────────────────────────────────────────────


class TestPluginMetadata:
    @pytest.fixture
    def loader(self):
        return SkillsLoader(
            workspace=Path("/tmp/_test_no_workspace"),
            builtin_skills_dir=BUILTIN_SKILLS_DIR,
        )

    def test_dcf_has_metadata(self, loader):
        """fa-dcf-model should have name and description in frontmatter."""
        meta = loader.get_skill_metadata("fa-dcf-model")
        assert meta is not None
        assert meta.get("name") == "dcf-model"

    def test_earnings_has_description(self, loader):
        """er-earnings-analysis should have a description."""
        meta = loader.get_skill_metadata("er-earnings-analysis")
        assert meta is not None
        assert meta.get("description")
        assert len(meta["description"]) > 10

    def test_skills_summary_includes_plugins(self, loader):
        """build_skills_summary should include plugin skills."""
        summary = loader.build_skills_summary()
        assert "fa-dcf-model" in summary
        assert "er-earnings-analysis" in summary
        assert "ib-merger-model" in summary
        assert "pe-ic-memo" in summary
        assert "wm-financial-plan" in summary


# ── Trigger Matching ─────────────────────────────────────────────────────


class TestPluginTriggers:
    @pytest.fixture
    def trigger(self):
        return SkillTrigger()

    def test_dcf_trigger(self, trigger):
        """DCF keywords should match fa-dcf-model."""
        result = trigger.detect("Build a DCF model for Apple")
        assert result["skill"] == "fa-dcf-model"

    def test_comps_trigger(self, trigger):
        """Comparable analysis keywords should match fa-comps-analysis."""
        result = trigger.detect("Run comparable analysis with trading multiples")
        assert result["skill"] == "fa-comps-analysis"

    def test_lbo_trigger(self, trigger):
        """LBO keywords should match fa-lbo-model."""
        result = trigger.detect("Build an LBO model for the target")
        assert result["skill"] == "fa-lbo-model"

    def test_earnings_trigger(self, trigger):
        """Earnings update keywords should match er-earnings-analysis."""
        result = trigger.detect("Write earnings update for Q3 results")
        assert result["skill"] == "er-earnings-analysis"

    def test_coverage_trigger(self, trigger):
        """Initiating coverage should match er-initiating-coverage."""
        result = trigger.detect("Write an initiating coverage report")
        assert result["skill"] == "er-initiating-coverage"

    def test_merger_trigger(self, trigger):
        """Merger model keywords should match ib-merger-model."""
        result = trigger.detect("Build a merger model for this acquisition analysis")
        assert result["skill"] == "ib-merger-model"

    def test_pitch_deck_trigger(self, trigger):
        """Pitch deck keywords should match ib-pitch-deck."""
        result = trigger.detect("Create a pitch deck for the client")
        assert result["skill"] == "ib-pitch-deck"

    def test_ic_memo_trigger(self, trigger):
        """IC memo keywords should match pe-ic-memo."""
        result = trigger.detect("Draft an IC memo for the investment committee")
        assert result["skill"] == "pe-ic-memo"

    def test_due_diligence_trigger(self, trigger):
        """Due diligence keywords should match pe-dd-checklist."""
        result = trigger.detect("Prepare a due diligence checklist")
        assert result["skill"] == "pe-dd-checklist"

    def test_financial_plan_trigger(self, trigger):
        """Financial plan keywords should match wm-financial-plan."""
        result = trigger.detect("Create a financial plan for retirement")
        assert result["skill"] == "wm-financial-plan"

    def test_tax_loss_trigger(self, trigger):
        """Tax loss harvesting should match wm-tax-loss-harvesting."""
        result = trigger.detect("Run tax loss harvesting analysis")
        assert result["skill"] == "wm-tax-loss-harvesting"

    def test_fx_carry_trigger(self, trigger):
        """FX carry keywords should match lseg-fx-carry-trade."""
        result = trigger.detect("Analyze fx carry trade opportunities")
        assert result["skill"] == "lseg-fx-carry-trade"

    def test_option_vol_trigger(self, trigger):
        """Option vol keywords should match lseg-option-vol-analysis."""
        result = trigger.detect("Analyze the option vol surface")
        assert result["skill"] == "lseg-option-vol-analysis"

    def test_original_triggers_still_work(self, trigger):
        """Original crisis_management trigger should still work."""
        result = trigger.detect("VIX is spiking, margin call incoming!")
        assert result["skill"] == "crisis_management"

    def test_total_trigger_count(self, trigger):
        """Should have 7 original + 21 plugin triggers = 28 total."""
        triggers = trigger.get_triggers()
        assert len(triggers) >= 28
