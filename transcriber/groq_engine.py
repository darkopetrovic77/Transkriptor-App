"""Transkription ueber die Groq-API (whisper-large-v3-turbo)."""

import os

from dotenv import load_dotenv
from groq import Groq

from .base import BaseEngine, TranscriptResult, TranscriptSegment
from .utils import split_audio_into_chunks

GROQ_MODEL = "whisper-large-v3-turbo"


class GroqAPIKeyMissingError(Exception):
    """Wird ausgeloest, wenn kein GROQ_API_KEY konfiguriert ist."""


class GroqAPIEngine(BaseEngine):
    """Transkribiert Audiodateien ueber die Groq Cloud-API.

    Bei Dateien >25 MB wird die Datei automatisch in kleinere
    Stuecke aufgeteilt (siehe `transcriber.utils.split_audio_into_chunks`),
    da die Groq-API eine maximale Dateigroesse von 25 MB hat.
    """

    def __init__(self) -> None:
        load_dotenv()
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise GroqAPIKeyMissingError(
                "Kein GROQ_API_KEY gefunden. Bitte trage ihn in der .env-Datei ein "
                "(siehe console.groq.com fuer einen kostenlosen API-Key)."
            )
        self._client = Groq(api_key=api_key)

    def transcribe(self, audio_path: str, language: str | None = None, model: str | None = None) -> TranscriptResult:
        chunks = split_audio_into_chunks(audio_path)

        all_segments: list[TranscriptSegment] = []
        detected_language = ""

        for chunk_path, offset_seconds in chunks:
            with open(chunk_path, "rb") as audio_file:
                response = self._client.audio.transcriptions.create(
                    file=audio_file,
                    model=GROQ_MODEL,
                    language=language,
                    response_format="verbose_json",
                )

            detected_language = getattr(response, "language", detected_language) or detected_language

            for segment in getattr(response, "segments", []) or []:
                all_segments.append(
                    TranscriptSegment(
                        start=segment["start"] + offset_seconds,
                        end=segment["end"] + offset_seconds,
                        text=segment["text"].strip(),
                    )
                )

        full_text = " ".join(segment.text for segment in all_segments)
        return TranscriptResult(text=full_text, segments=all_segments, language=detected_language)
