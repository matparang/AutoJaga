"""JAGABOT Voice — optional local voice integration.

v3.7: STT (Vosk) + TTS (pyttsx3) with graceful degradation.
All voice dependencies are optional — ``is_voice_available()`` returns
False when they are not installed.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _check_import(module: str) -> bool:
    try:
        __import__(module)
        return True
    except ImportError:
        return False


def is_voice_available() -> bool:
    """Return True if all voice dependencies (vosk, pyttsx3, pyaudio) are importable."""
    return all(_check_import(m) for m in ("vosk", "pyttsx3", "pyaudio"))


# Eagerly evaluated at import time for fast checks.
VOICE_AVAILABLE: bool = is_voice_available()

from jagabot.voice.config import VoiceConfig  # noqa: E402
from jagabot.voice.service import VoiceService  # noqa: E402

__all__ = ["VoiceConfig", "VoiceService", "is_voice_available", "VOICE_AVAILABLE"]
