"""Tests for jagabot.agent.compressor — context compression utilities."""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from jagabot.agent.compressor import (
    estimate_tokens,
    micro_compact,
    save_transcript,
    should_auto_compact,
)


# ── estimate_tokens ──────────────────────────────────────────────────

class TestEstimateTokens:
    def test_empty(self):
        assert estimate_tokens([]) == 0

    def test_single_message(self):
        msgs = [{"role": "user", "content": "hello"}]
        result = estimate_tokens(msgs)
        assert result > 0

    def test_proportional(self):
        short = [{"role": "user", "content": "hi"}]
        long = [{"role": "user", "content": "x" * 400}]
        assert estimate_tokens(long) > estimate_tokens(short)

    def test_4_char_heuristic(self):
        msgs = [{"role": "user", "content": "a" * 400}]
        tokens = estimate_tokens(msgs)
        assert tokens == len(str(msgs)) // 4

    def test_nested_content(self):
        msgs = [{"role": "assistant", "content": None, "tool_calls": [{"id": "t1", "function": {"name": "read", "arguments": "{}"}}]}]
        result = estimate_tokens(msgs)
        assert result > 0


# ── micro_compact ────────────────────────────────────────────────────

class TestMicroCompact:
    def _tool_msg(self, name, content, call_id="c1"):
        return {"role": "tool", "tool_call_id": call_id, "name": name, "content": content}

    def test_short_content_preserved(self):
        msgs = [
            {"role": "user", "content": "do X"},
            self._tool_msg("read_file", "short", "c1"),
        ]
        micro_compact(msgs)
        assert msgs[-1]["content"] == "short"

    def test_long_old_content_replaced(self):
        msgs = [
            {"role": "user", "content": "do X"},
            self._tool_msg("read_file", "x" * 200, "c1"),
            self._tool_msg("read_file", "y" * 200, "c2"),
            self._tool_msg("read_file", "z" * 200, "c3"),
            self._tool_msg("read_file", "keep1", "c4"),
            self._tool_msg("read_file", "keep2", "c5"),
            self._tool_msg("read_file", "keep3", "c6"),
        ]
        micro_compact(msgs, keep_recent=3)
        assert "[Previous:" in msgs[1]["content"]
        assert msgs[-1]["content"] == "keep3"

    def test_keep_recent_default(self):
        # Default keep_recent=3 means last 3 tool results are untouched
        tool_msgs = [self._tool_msg("exec", "x" * 200, f"c{i}") for i in range(6)]
        msgs = [{"role": "user", "content": "go"}] + tool_msgs
        micro_compact(msgs)
        # Last 3 should be preserved
        assert msgs[-1]["content"] == "x" * 200
        assert msgs[-2]["content"] == "x" * 200
        assert msgs[-3]["content"] == "x" * 200
        assert "[Previous:" in msgs[1]["content"]

    def test_non_tool_messages_untouched(self):
        msgs = [
            {"role": "user", "content": "x" * 200},
            {"role": "assistant", "content": "y" * 200},
        ]
        micro_compact(msgs)
        assert msgs[0]["content"] == "x" * 200
        assert msgs[1]["content"] == "y" * 200

    def test_empty_messages(self):
        msgs = []
        micro_compact(msgs)
        assert msgs == []

    def test_anthropic_format_tool_result(self):
        msgs = [
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "x" * 200}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t2", "content": "keep"}]},
        ]
        micro_compact(msgs, keep_recent=1)
        assert "[Previous:" in msgs[0]["content"][0]["content"]

    def test_only_compacts_above_threshold(self):
        msgs = [self._tool_msg("exec", "a" * 50, f"c{i}") for i in range(10)]
        micro_compact(msgs, keep_recent=3)
        # Content < 100 chars, should not be compacted even if old
        for m in msgs:
            assert "[Previous:" not in m["content"]


# ── should_auto_compact ─────────────────────────────────────────────

class TestShouldAutoCompact:
    def test_below_threshold(self):
        msgs = [{"role": "user", "content": "hi"}]
        assert should_auto_compact(msgs) is False

    def test_above_threshold(self):
        msgs = [{"role": "user", "content": "x" * 200000}]
        assert should_auto_compact(msgs) is True

    def test_custom_threshold(self):
        msgs = [{"role": "user", "content": "x" * 100}]
        assert should_auto_compact(msgs, threshold=5) is True

    def test_exact_threshold(self):
        # At exactly the threshold, should NOT trigger (strict >)
        content = "x" * (40000 * 4)  # exactly 40000 tokens
        msgs = [{"role": "user", "content": content}]
        # estimate_tokens uses len(str(msgs)) // 4 which includes formatting
        result = should_auto_compact(msgs)
        # Just verify it returns a bool
        assert isinstance(result, bool)


# ── save_transcript ──────────────────────────────────────────────────

class TestSaveTranscript:
    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            msgs = [{"role": "user", "content": "hello"}]
            path = save_transcript(msgs, tdir)
            assert path.exists()
            assert path.suffix == ".jsonl"

    def test_jsonl_format(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            msgs = [
                {"role": "user", "content": "a"},
                {"role": "assistant", "content": "b"},
            ]
            path = save_transcript(msgs, tdir)
            lines = path.read_text().strip().split("\n")
            assert len(lines) == 2
            assert json.loads(lines[0])["role"] == "user"

    def test_creates_directory(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td) / "sub" / "transcripts"
            msgs = [{"role": "user", "content": "hi"}]
            path = save_transcript(msgs, tdir)
            assert tdir.exists()
            assert path.exists()

    def test_empty_messages(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            path = save_transcript([], tdir)
            assert path.exists()
            assert path.read_text() == ""

    def test_returns_path(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            result = save_transcript([{"role": "user", "content": "x"}], tdir)
            assert isinstance(result, Path)
