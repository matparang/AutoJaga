"""Tests for v3.7.2 — Telegram-Optimized 3-Part Response Format.

Validates ResponseFormatter section detection, word limits, message splitting,
and ContextBuilder channel-specific prompt injection.
"""

import pytest
from pathlib import Path

from jagabot.channels.formatter import (
    ResponseFormatter, Section, FormattedResponse,
    TELEGRAM_CHAR_LIMIT, DEFAULT_WORD_LIMITS,
)
from jagabot.agent.context import ContextBuilder


# ── Sample 3-part response ───────────────────────────────────────────────

SAMPLE_3PART = """🧠 UNDERSTANDING THE TASK
• Modal: $2,000,000, Leverage: 1:3
• Position: 60% WTI (buy $76.50, now $70)
• VIX: 52, DXY: 104

📌 SKILL TO BE USED: var — Value at Risk calculation
⏳ Executing analysis...
━━━━━━━━━━━━━━━━━━━━━━

📊 CRITICAL SUMMARY:
• Margin Level: 45% ⚠️
• Equity: $908,610
• Probability <target: 42.33%
• VaR 95%: $819,534 (15.73% of equity)

🎯 RECOMMENDATIONS:
1. SELL — margin call risk is critical
2. Reduce leverage to 1:1 immediately
3. Set stop-loss at $68
━━━━━━━━━━━━━━━━━━━━━━

📈 MARKET CONTEXT:
• VIX 52: Extreme fear — hedging costs elevated
• DXY 104: Strong dollar pressures commodities

⚠️ RISK LEVELS:
• High: Margin call probability >40%
• Medium: Oil price recovery uncertain
"""

SAMPLE_PLAIN = "Hello! I'm jagabot. How can I help you today?"

SAMPLE_2PART = """🧠 UNDERSTANDING THE TASK
• You asked about portfolio risk

📊 CRITICAL SUMMARY:
• Your portfolio VaR is $50,000
• Risk level: moderate
"""


# ── Section Detection ────────────────────────────────────────────────────


class TestSectionDetection:
    def test_detects_three_sections(self):
        """Full 3-part response should yield 3 sections."""
        fmt = ResponseFormatter()
        sections = fmt.detect_sections(SAMPLE_3PART)
        assert len(sections) == 4  # 🧠, 📊, 📈, ⚠️

    def test_section_labels(self):
        """Sections should have correct labels."""
        fmt = ResponseFormatter()
        sections = fmt.detect_sections(SAMPLE_3PART)
        labels = [s.label for s in sections]
        assert labels[0] == "part1"
        assert labels[1] == "part2"
        assert "part3" in labels

    def test_two_part_response(self):
        """2-part response with 🧠 and 📊 markers."""
        fmt = ResponseFormatter()
        sections = fmt.detect_sections(SAMPLE_2PART)
        assert len(sections) == 2
        assert sections[0].label == "part1"
        assert sections[1].label == "part2"

    def test_plain_text_no_sections(self):
        """Plain text with no markers should return empty list."""
        fmt = ResponseFormatter()
        sections = fmt.detect_sections(SAMPLE_PLAIN)
        assert sections == []

    def test_section_content_non_empty(self):
        """Each detected section should have non-empty content."""
        fmt = ResponseFormatter()
        sections = fmt.detect_sections(SAMPLE_3PART)
        for s in sections:
            assert s.content.strip()
            assert s.word_count > 0


# ── Word Limit Enforcement ───────────────────────────────────────────────


class TestWordLimits:
    def test_short_text_unchanged(self):
        """Text under limit should be returned as-is."""
        text = "This is a short response."
        result = ResponseFormatter.enforce_word_limit(text, 300)
        assert result == text

    def test_long_text_truncated(self):
        """Text over limit should be truncated."""
        text = " ".join(["word"] * 400)
        result = ResponseFormatter.enforce_word_limit(text, 300)
        assert len(result.split()) <= 302  # 300 + "…" marker

    def test_truncation_ends_with_ellipsis(self):
        """Truncated text should end with ellipsis marker."""
        text = " ".join(["word"] * 400)
        result = ResponseFormatter.enforce_word_limit(text, 300)
        assert "…" in result

    def test_truncation_prefers_sentence_boundary(self):
        """Should cut at sentence end when possible."""
        # Place a sentence end well past halfway of a 20-word limit
        text = "word " * 12 + "End sentence here. " + "word " * 300
        result = ResponseFormatter.enforce_word_limit(text, 20)
        assert "…" in result
        # Should have cut at the "." since it's past halfway of 20 words
        assert "End sentence here." in result

    def test_default_limits(self):
        """Default limits should be 300/500/300."""
        assert DEFAULT_WORD_LIMITS == {"part1": 300, "part2": 500, "part3": 300}


# ── Message Splitting ────────────────────────────────────────────────────


class TestMessageSplitting:
    def test_short_message_single_part(self):
        """Short message should stay as one part."""
        fmt = ResponseFormatter()
        parts = fmt.split_long_message("Hello world")
        assert len(parts) == 1
        assert parts[0] == "Hello world"

    def test_long_message_splits(self):
        """Message exceeding char limit should be split."""
        fmt = ResponseFormatter(char_limit=100)
        text = "\n\n".join([f"Paragraph {i}: " + "x" * 40 for i in range(10)])
        parts = fmt.split_long_message(text)
        assert len(parts) > 1
        for p in parts:
            assert len(p) <= 100

    def test_splits_at_paragraph_boundary(self):
        """Split should prefer paragraph breaks."""
        fmt = ResponseFormatter(char_limit=60)
        text = "First paragraph here.\n\nSecond paragraph here.\n\nThird paragraph."
        parts = fmt.split_long_message(text)
        assert len(parts) >= 2
        # Each part should be a clean paragraph
        for p in parts:
            assert not p.startswith("\n")

    def test_every_chunk_within_limit(self):
        """All chunks must be ≤ char_limit."""
        fmt = ResponseFormatter(char_limit=200)
        text = " ".join(["LongWord" * 5] * 100)
        parts = fmt.split_long_message(text)
        for p in parts:
            assert len(p) <= 200


# ── Full format_for_telegram ─────────────────────────────────────────────


class TestFormatForTelegram:
    def test_3part_produces_multiple_messages(self):
        """3-part response should produce multiple Telegram messages."""
        fmt = ResponseFormatter()
        parts = fmt.format_for_telegram(SAMPLE_3PART)
        assert len(parts) >= 2  # At minimum part1+part2 merged or separate

    def test_plain_text_single_message(self):
        """Plain text stays as single message."""
        fmt = ResponseFormatter()
        parts = fmt.format_for_telegram(SAMPLE_PLAIN)
        assert len(parts) == 1
        assert parts[0] == SAMPLE_PLAIN

    def test_empty_content(self):
        """Empty content should return single empty string."""
        fmt = ResponseFormatter()
        parts = fmt.format_for_telegram("")
        assert parts == [""]

    def test_all_parts_within_telegram_limit(self):
        """Every message part must be ≤ 4096 chars."""
        fmt = ResponseFormatter()
        # Generate a very long 3-part response
        long_part1 = "🧠 UNDERSTANDING\n" + "• Parameter detail\n" * 200
        long_part2 = "📊 ANALYSIS\n" + "• Metric result\n" * 200
        long_part3 = "📈 CONTEXT\n" + "• Market info\n" * 200
        content = f"{long_part1}\n{long_part2}\n{long_part3}"
        parts = fmt.format_for_telegram(content)
        for p in parts:
            assert len(p) <= TELEGRAM_CHAR_LIMIT

    def test_custom_word_limits(self):
        """Custom word limits should be respected."""
        fmt = ResponseFormatter(word_limits={"part1": 10, "part2": 10, "part3": 10})
        parts = fmt.format_for_telegram(SAMPLE_3PART)
        for p in parts:
            assert len(p.split()) <= 15  # 10 words + small overflow from ellipsis


# ── ContextBuilder Telegram Instructions ─────────────────────────────────


class TestContextBuilderTelegram:
    @pytest.fixture
    def builder(self, tmp_path):
        return ContextBuilder(workspace=tmp_path)

    def test_telegram_gets_format_instructions(self, builder):
        """build_messages with channel=telegram should include format instructions."""
        msgs = builder.build_messages(
            history=[], current_message="analyze my portfolio",
            channel="telegram", chat_id="12345",
        )
        system = msgs[0]["content"]
        assert "Response Format (Telegram)" in system
        assert "🧠" in system
        assert "📊" in system
        assert "<300 words" in system

    def test_non_telegram_no_format_instructions(self, builder):
        """Non-telegram channels should NOT get format instructions."""
        msgs = builder.build_messages(
            history=[], current_message="hello",
            channel="discord", chat_id="99",
        )
        system = msgs[0]["content"]
        assert "Response Format (Telegram)" not in system

    def test_no_channel_no_format_instructions(self, builder):
        """No channel specified → no format instructions."""
        msgs = builder.build_messages(
            history=[], current_message="hello",
        )
        system = msgs[0]["content"]
        assert "Response Format (Telegram)" not in system

    def test_format_instructions_mention_skill_declaration(self, builder):
        """Telegram instructions should require skill declaration."""
        msgs = builder.build_messages(
            history=[], current_message="check risk",
            channel="telegram", chat_id="12345",
        )
        system = msgs[0]["content"]
        assert "SKILL TO BE USED" in system

    def test_format_instructions_mention_word_limits(self, builder):
        """Instructions should mention all three word limits."""
        msgs = builder.build_messages(
            history=[], current_message="x",
            channel="telegram", chat_id="1",
        )
        system = msgs[0]["content"]
        assert "<300 words" in system
        assert "<500 words" in system
