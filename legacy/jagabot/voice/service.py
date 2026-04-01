"""VoiceService — local STT + TTS with graceful degradation.

All heavy imports (vosk, pyttsx3, pyaudio) happen lazily inside methods
so the module can always be imported even when deps are missing.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
from typing import Any

from jagabot.voice.config import VoiceConfig

logger = logging.getLogger(__name__)


class VoiceService:
    """Local voice service using Vosk (STT) and pyttsx3 (TTS).

    Designed for graceful degradation: every public method handles
    ``ImportError`` so callers never crash when voice deps are absent.
    """

    def __init__(self, config: VoiceConfig | None = None) -> None:
        self.config = config or VoiceConfig()
        self._stt_model: Any | None = None
        self._tts_engine: Any | None = None
        self._audio_queue: queue.Queue[bytes] = queue.Queue()
        self._recording = False
        self._record_thread: threading.Thread | None = None

        # Lazy backend availability flags (set on first use)
        self._stt_checked = False
        self._stt_ok = False
        self._tts_checked = False
        self._tts_ok = False

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    @property
    def stt_available(self) -> bool:
        """True if Vosk can be imported and a model is loadable."""
        if not self._stt_checked:
            self._stt_checked = True
            try:
                import vosk  # noqa: F401
                self._stt_ok = True
            except ImportError:
                self._stt_ok = False
        return self._stt_ok

    @property
    def tts_available(self) -> bool:
        """True if pyttsx3 can be imported."""
        if not self._tts_checked:
            self._tts_checked = True
            try:
                import pyttsx3  # noqa: F401
                self._tts_ok = True
            except ImportError:
                self._tts_ok = False
        return self._tts_ok

    @property
    def recording_available(self) -> bool:
        """True if pyaudio can be imported."""
        try:
            import pyaudio  # noqa: F401
            return True
        except ImportError:
            return False

    @property
    def is_available(self) -> bool:
        """True if at least STT or TTS is usable."""
        return self.stt_available or self.tts_available

    @property
    def fully_available(self) -> bool:
        """True if STT + TTS + recording are all usable."""
        return self.stt_available and self.tts_available and self.recording_available

    # ------------------------------------------------------------------
    # STT — Speech to Text
    # ------------------------------------------------------------------

    def _ensure_stt_model(self) -> Any | None:
        """Lazily load the Vosk model."""
        if self._stt_model is not None:
            return self._stt_model
        if not self.stt_available:
            return None
        try:
            import vosk
            model_path = self.config.resolved_model_path
            if not model_path.exists():
                logger.warning("Vosk model not found at %s", model_path)
                return None
            vosk.SetLogLevel(-1)  # silence Vosk logs
            self._stt_model = vosk.Model(str(model_path))
            return self._stt_model
        except Exception as exc:
            logger.warning("Failed to load Vosk model: %s", exc)
            return None

    def transcribe(self, audio_data: bytes) -> str:
        """Transcribe audio bytes (16-bit PCM, mono) to text.

        Returns empty string on any failure.
        """
        model = self._ensure_stt_model()
        if model is None:
            logger.debug("STT unavailable — returning empty transcription")
            return ""
        try:
            import vosk
            rec = vosk.KaldiRecognizer(model, self.config.sample_rate)
            rec.AcceptWaveform(audio_data)
            result = json.loads(rec.FinalResult())
            return result.get("text", "")
        except Exception as exc:
            logger.warning("Transcription failed: %s", exc)
            return ""

    # ------------------------------------------------------------------
    # TTS — Text to Speech
    # ------------------------------------------------------------------

    def _ensure_tts_engine(self) -> Any | None:
        """Lazily initialise the pyttsx3 engine."""
        if self._tts_engine is not None:
            return self._tts_engine
        if not self.tts_available:
            return None
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", self.config.tts_rate)
            engine.setProperty("volume", self.config.tts_volume)

            # Try to select language-appropriate voice
            voices = engine.getProperty("voices")
            if self.config.language == "ms":
                for v in voices:
                    if "malay" in v.name.lower() or "ms_" in v.id:
                        engine.setProperty("voice", v.id)
                        break

            self._tts_engine = engine
            return self._tts_engine
        except Exception as exc:
            logger.warning("Failed to init TTS engine: %s", exc)
            return None

    def synthesize(self, text: str) -> None:
        """Speak *text* aloud via pyttsx3.  No-op when TTS unavailable."""
        engine = self._ensure_tts_engine()
        if engine is None:
            logger.debug("TTS unavailable — skipping synthesis")
            return
        try:
            engine.say(text)
            engine.runAndWait()
        except Exception as exc:
            logger.warning("Speech synthesis failed: %s", exc)

    # ------------------------------------------------------------------
    # Recording — microphone capture
    # ------------------------------------------------------------------

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start_recording(self) -> bool:
        """Start capturing from the microphone in a background thread.

        Returns True if recording started, False on failure.
        """
        if self._recording:
            return True
        if not self.recording_available:
            logger.debug("Recording unavailable (pyaudio not installed)")
            return False
        try:
            self._recording = True
            # Drain any leftover data
            while not self._audio_queue.empty():
                self._audio_queue.get_nowait()
            self._record_thread = threading.Thread(
                target=self._record_loop, daemon=True,
            )
            self._record_thread.start()
            return True
        except Exception as exc:
            self._recording = False
            logger.warning("Failed to start recording: %s", exc)
            return False

    def stop_recording(self) -> bytes:
        """Stop recording and return all captured audio as bytes.

        Returns empty bytes on failure.
        """
        if not self._recording:
            return b""
        self._recording = False
        if self._record_thread and self._record_thread.is_alive():
            self._record_thread.join(timeout=5)
        # Collect chunks
        chunks: list[bytes] = []
        while not self._audio_queue.empty():
            try:
                chunks.append(self._audio_queue.get_nowait())
            except queue.Empty:
                break
        return b"".join(chunks)

    def _record_loop(self) -> None:
        """Background microphone capture (runs in thread)."""
        try:
            import pyaudio
            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.config.sample_rate,
                input=True,
                frames_per_buffer=self.config.chunk_size,
            )
            while self._recording:
                data = stream.read(self.config.chunk_size, exception_on_overflow=False)
                self._audio_queue.put(data)
            stream.stop_stream()
            stream.close()
            p.terminate()
        except Exception as exc:
            logger.warning("Recording loop error: %s", exc)
            self._recording = False

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def transcribe_recording(self) -> str:
        """Stop recording and transcribe the captured audio."""
        audio = self.stop_recording()
        if not audio:
            return ""
        return self.transcribe(audio)

    def get_status(self) -> dict[str, Any]:
        """Return a status dict for diagnostics / UI display."""
        return {
            "stt_available": self.stt_available,
            "tts_available": self.tts_available,
            "recording_available": self.recording_available,
            "is_available": self.is_available,
            "fully_available": self.fully_available,
            "is_recording": self.is_recording,
            "language": self.config.language,
            "model_path": str(self.config.resolved_model_path),
        }
