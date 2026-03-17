"""Voice configuration for JAGABOT."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VoiceConfig:
    """Configuration for voice services (STT + TTS)."""

    language: str = "ms"  # "ms" (Malay) or "en" (English)
    sample_rate: int = 16000
    chunk_size: int = 4000
    model_path: str | None = None  # explicit Vosk model path
    tts_rate: int = 150  # words per minute
    tts_volume: float = 0.9  # 0.0 – 1.0
    models_dir: Path = field(default_factory=lambda: Path.home() / ".jagabot" / "voice_models")

    # Vosk model URLs by language
    MODEL_URLS: dict[str, str] = field(default_factory=lambda: {
        "ms": "https://alphacephei.com/vosk/models/vosk-model-small-ms-0.3.zip",
        "en": "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
    }, repr=False)

    MODEL_NAMES: dict[str, str] = field(default_factory=lambda: {
        "ms": "vosk-model-small-ms-0.3",
        "en": "vosk-model-small-en-us-0.15",
    }, repr=False)

    @property
    def model_name(self) -> str:
        return self.MODEL_NAMES.get(self.language, self.MODEL_NAMES["en"])

    @property
    def model_url(self) -> str:
        return self.MODEL_URLS.get(self.language, self.MODEL_URLS["en"])

    @property
    def resolved_model_path(self) -> Path:
        """Return explicit model_path if set, else default location."""
        if self.model_path:
            return Path(self.model_path)
        return self.models_dir / self.model_name
