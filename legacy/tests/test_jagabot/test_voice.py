"""Tests for JAGABOT v3.7 — Voice Integration.

Covers VoiceConfig, VoiceService (graceful degradation), availability
checks, recording lifecycle, and chat.py voice integration.
All tests work WITHOUT actual voice deps (vosk/pyttsx3/pyaudio).
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from jagabot.voice.config import VoiceConfig
from jagabot.voice.service import VoiceService


# ====================================================================
# VoiceConfig
# ====================================================================

class TestVoiceConfig:
    def test_defaults(self):
        cfg = VoiceConfig()
        assert cfg.language == "ms"
        assert cfg.sample_rate == 16000
        assert cfg.chunk_size == 4000
        assert cfg.tts_rate == 150
        assert cfg.tts_volume == 0.9
        assert cfg.model_path is None

    def test_custom_values(self):
        cfg = VoiceConfig(language="en", sample_rate=22050, tts_rate=200)
        assert cfg.language == "en"
        assert cfg.sample_rate == 22050
        assert cfg.tts_rate == 200

    def test_model_name_malay(self):
        cfg = VoiceConfig(language="ms")
        assert cfg.model_name == "vosk-model-small-ms-0.3"

    def test_model_name_english(self):
        cfg = VoiceConfig(language="en")
        assert cfg.model_name == "vosk-model-small-en-us-0.15"

    def test_model_url_malay(self):
        cfg = VoiceConfig(language="ms")
        assert "ms" in cfg.model_url

    def test_model_url_english(self):
        cfg = VoiceConfig(language="en")
        assert "en-us" in cfg.model_url

    def test_resolved_model_path_default(self):
        cfg = VoiceConfig(language="ms")
        expected = cfg.models_dir / "vosk-model-small-ms-0.3"
        assert cfg.resolved_model_path == expected

    def test_resolved_model_path_explicit(self):
        cfg = VoiceConfig(model_path="/custom/model")
        assert cfg.resolved_model_path == Path("/custom/model")

    def test_models_dir_default(self):
        cfg = VoiceConfig()
        assert ".jagabot" in str(cfg.models_dir)
        assert "voice_models" in str(cfg.models_dir)


# ====================================================================
# is_voice_available
# ====================================================================

class TestVoiceAvailability:
    def test_voice_not_available_in_test_env(self):
        """In this env, vosk/pyttsx3/pyaudio are NOT installed."""
        from jagabot.voice import is_voice_available, VOICE_AVAILABLE
        assert is_voice_available() is False
        assert VOICE_AVAILABLE is False

    def test_check_import_helper(self):
        from jagabot.voice import _check_import
        assert _check_import("os") is True
        assert _check_import("nonexistent_module_xyz") is False


# ====================================================================
# VoiceService — graceful degradation (no deps)
# ====================================================================

class TestVoiceServiceNoDeps:
    def test_init_no_crash(self):
        vs = VoiceService()
        assert vs is not None
        assert vs.config.language == "ms"

    def test_stt_not_available(self):
        vs = VoiceService()
        assert vs.stt_available is False

    def test_tts_not_available(self):
        vs = VoiceService()
        assert vs.tts_available is False

    def test_recording_not_available(self):
        vs = VoiceService()
        assert vs.recording_available is False

    def test_is_available_false(self):
        vs = VoiceService()
        assert vs.is_available is False

    def test_fully_available_false(self):
        vs = VoiceService()
        assert vs.fully_available is False

    def test_transcribe_returns_empty(self):
        vs = VoiceService()
        assert vs.transcribe(b"fake audio data") == ""

    def test_synthesize_noop(self):
        vs = VoiceService()
        # Should not raise
        vs.synthesize("Hello world")

    def test_start_recording_returns_false(self):
        vs = VoiceService()
        assert vs.start_recording() is False

    def test_stop_recording_returns_empty(self):
        vs = VoiceService()
        assert vs.stop_recording() == b""

    def test_transcribe_recording_returns_empty(self):
        vs = VoiceService()
        assert vs.transcribe_recording() == ""

    def test_get_status(self):
        vs = VoiceService()
        status = vs.get_status()
        assert status["stt_available"] is False
        assert status["tts_available"] is False
        assert status["recording_available"] is False
        assert status["is_available"] is False
        assert status["language"] == "ms"
        assert status["is_recording"] is False

    def test_is_recording_initially_false(self):
        vs = VoiceService()
        assert vs.is_recording is False


# ====================================================================
# VoiceService — with mocked deps
# ====================================================================

class TestVoiceServiceMocked:
    def test_stt_available_when_vosk_importable(self):
        vs = VoiceService()
        vs._stt_checked = False
        with patch("builtins.__import__", side_effect=lambda name, *a, **kw: (
            MagicMock() if name == "vosk" else __import__(name, *a, **kw)
        )):
            assert vs.stt_available is True

    def test_tts_available_when_pyttsx3_importable(self):
        vs = VoiceService()
        vs._tts_checked = False
        with patch("builtins.__import__", side_effect=lambda name, *a, **kw: (
            MagicMock() if name == "pyttsx3" else __import__(name, *a, **kw)
        )):
            assert vs.tts_available is True

    def test_recording_start_stop_with_mock(self):
        """Simulate recording with a mock that puts data into the queue."""
        vs = VoiceService()

        # Pretend pyaudio is available
        with patch.object(type(vs), "recording_available", new_callable=PropertyMock, return_value=True):
            # Mock _record_loop to just add some fake audio
            def fake_record():
                vs._audio_queue.put(b"\x00" * 100)
                vs._audio_queue.put(b"\x01" * 100)

            with patch.object(vs, "_record_loop", side_effect=fake_record):
                started = vs.start_recording()
                assert started is True
                assert vs.is_recording is True

                # Let thread run
                if vs._record_thread:
                    vs._record_thread.join(timeout=2)

                audio = vs.stop_recording()
                assert len(audio) == 200
                assert vs.is_recording is False

    def test_custom_config(self):
        cfg = VoiceConfig(language="en", tts_rate=180, tts_volume=0.7)
        vs = VoiceService(cfg)
        assert vs.config.language == "en"
        assert vs.config.tts_rate == 180


# ====================================================================
# Chat voice integration
# ====================================================================

class TestChatVoiceIntegration:
    def test_voice_available_import(self):
        """VOICE_AVAILABLE imported in chat.py should be False in test env."""
        from jagabot.ui.chat import VOICE_AVAILABLE
        assert VOICE_AVAILABLE is False

    def test_render_chat_still_importable(self):
        from jagabot.ui.chat import render_chat
        assert callable(render_chat)

    def test_init_voice_session(self):
        """_init_voice_session creates a VoiceService in mock session state."""
        from jagabot.ui.chat import _init_voice_session
        mock_st = MagicMock()
        mock_st.session_state = {}
        _init_voice_session(mock_st)
        assert "voice_service" in mock_st.session_state
        assert isinstance(mock_st.session_state["voice_service"], VoiceService)

    def test_handle_general_still_works(self):
        """v3.6 general handling unaffected by voice changes."""
        from jagabot.ui.chat import _handle_general
        r = _handle_general("Hello!")
        assert "JAGABOT" in r["message"]
