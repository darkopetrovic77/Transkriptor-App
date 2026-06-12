"""Lokale Transkription mit faster-whisper (CPU, int8-Quantisierung)."""

import os

from faster_whisper import WhisperModel

from .base import BaseEngine, TranscriptResult, TranscriptSegment

# Ordner, in dem die Whisper-Modelle beim ersten Gebrauch
# heruntergeladen und danach gecached werden.
MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")

DEFAULT_MODEL = "medium"


class LocalWhisperEngine(BaseEngine):
    """Transkribiert Audiodateien lokal ueber faster-whisper.

    Geladene Modelle werden im Arbeitsspeicher zwischengespeichert
    (`_loaded_models`), damit ein Modell nicht fuer jede Datei neu
    von der Festplatte geladen werden muss.
    """

    def __init__(self) -> None:
        self._loaded_models: dict[str, WhisperModel] = {}

    def _get_model(self, model_name: str) -> WhisperModel:
        if model_name not in self._loaded_models:
            self._loaded_models[model_name] = WhisperModel(
                model_name,
                device="cpu",
                compute_type="int8",
                download_root=MODELS_DIR,
            )
        return self._loaded_models[model_name]

    def transcribe(self, audio_path: str, language: str | None = None, model: str | None = None) -> TranscriptResult:
        model_name = model or DEFAULT_MODEL
        whisper_model = self._get_model(model_name)

        segments_iter, info = whisper_model.transcribe(
            audio_path,
            language=language,
        )

        segments = []
        full_text_parts = []
        for segment in segments_iter:
            text = segment.text.strip()
            segments.append(TranscriptSegment(start=segment.start, end=segment.end, text=text))
            full_text_parts.append(text)

        return TranscriptResult(
            text=" ".join(full_text_parts),
            segments=segments,
            language=info.language,
        )
