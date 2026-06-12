"""Pydantic-Modelle fuer Request-Bodies und kleine Hilfsfunktionen
(Modell-Mapping, SRT-Erzeugung, Zeit-Schaetzung)."""

from pydantic import BaseModel

# Sprache -> lokales Whisper-Modell (Auto-Mapping, vom User ueberschreibbar)
LOCAL_MODEL_MAP = {
    "en": "small.en",
    "de": "medium",
    "de-ch": "medium",
    "pt": "medium",
    "sr": "medium",
}
DEFAULT_LOCAL_MODEL = "medium"

# Grobe Schaetzung: Sekunden Verarbeitung pro Sekunde Audio
SPEED_FACTORS = {
    "local": {"small.en": 0.15, "medium": 0.4, "large-v3": 0.8},
    "groq": {"whisper-large-v3-turbo": 0.05},
}


def default_model_for_language(language: str) -> str:
    return LOCAL_MODEL_MAP.get(language, DEFAULT_LOCAL_MODEL)


def estimate_seconds(duration: float, engine: str, model: str) -> float:
    if engine == "groq":
        factor = SPEED_FACTORS["groq"]["whisper-large-v3-turbo"]
    else:
        factor = SPEED_FACTORS["local"].get(model, SPEED_FACTORS["local"][DEFAULT_LOCAL_MODEL])
    return duration * factor


def _format_srt_timestamp(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def segments_to_srt(segments: list[dict]) -> str:
    lines = []
    for i, segment in enumerate(segments, start=1):
        lines.append(str(i))
        lines.append(f"{_format_srt_timestamp(segment['start'])} --> {_format_srt_timestamp(segment['end'])}")
        lines.append(segment["text"])
        lines.append("")
    return "\n".join(lines)


class EngineUpdate(BaseModel):
    engine: str  # "local" oder "groq"


class TranscriptUpdate(BaseModel):
    segments: list[dict]


class BulkDownloadRequest(BaseModel):
    ids: list[int]
    format: str  # "txt", "srt" oder "both"
