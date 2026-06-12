"""Vorbereiteter Adapter fuer die OpenAI-API. Aktuell nicht aktiv.

Diese Klasse existiert nur, damit das Adapter-Pattern vollstaendig ist
und eine zukuenftige Aktivierung einfach (drittes Engine-Modul) waere.
"""

from .base import BaseEngine, TranscriptResult


class OpenAIAPIEngine(BaseEngine):
    """Stub-Engine fuer die OpenAI Transcription-API. Noch nicht implementiert."""

    def transcribe(self, audio_path: str, language: str | None = None, model: str | None = None) -> TranscriptResult:
        raise NotImplementedError("OpenAIAPIEngine ist vorbereitet, aber noch nicht aktiv.")
