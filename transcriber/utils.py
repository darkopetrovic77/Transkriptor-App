"""Hilfsfunktionen rund um Audio-/Video-Dateien.

- `extract_audio`: holt die Audiospur aus einer Video-Datei (per ffmpeg).
- `split_audio_into_chunks`: teilt eine grosse Audiodatei in kleinere
  Stuecke auf (z.B. weil die Groq-API maximal 25 MB pro Datei akzeptiert).
"""

import math
import os
import tempfile

import ffmpeg
from pydub import AudioSegment

MAX_GROQ_FILE_SIZE = 25 * 1024 * 1024  # 25 MB


def extract_audio(video_path: str) -> str:
    """Extrahiert die Audiospur aus einer Video-Datei als .wav.

    Gibt den Pfad zur erzeugten Audiodatei (in einem temporaeren
    Ordner) zurueck.
    """
    output_path = os.path.join(tempfile.gettempdir(), f"{os.path.basename(video_path)}.extracted.wav")
    (
        ffmpeg
        .input(video_path)
        .output(output_path, ac=1, ar="16000", vn=None)
        .overwrite_output()
        .run(quiet=True)
    )
    return output_path


def convert_to_mp3(source_path: str, dest_path: str, bitrate: str = "128k") -> None:
    """Konvertiert eine Audio-/Videodatei in eine komprimierte MP3.

    Wird nach erfolgreicher Transkription aufgerufen, um die grosse
    Originaldatei durch eine kleine MP3 fuer den Audio-Player zu ersetzen.
    """
    (
        ffmpeg
        .input(source_path)
        .output(dest_path, audio_bitrate=bitrate, ac=1, vn=None, acodec="libmp3lame")
        .overwrite_output()
        .run(quiet=True)
    )


def split_audio_into_chunks(audio_path: str, max_size_bytes: int = MAX_GROQ_FILE_SIZE) -> list[tuple[str, float]]:
    """Teilt eine Audiodatei in mehrere Teile auf, falls sie zu gross ist.

    Returns:
        Liste von (chunk_pfad, start_zeit_in_sekunden). Wenn die Datei
        bereits klein genug ist, enthaelt die Liste nur ein Element
        mit start_zeit=0.0 und dem Original-Pfad.
    """
    file_size = os.path.getsize(audio_path)
    if file_size <= max_size_bytes:
        return [(audio_path, 0.0)]

    audio = AudioSegment.from_file(audio_path)
    total_duration_ms = len(audio)

    num_chunks = math.ceil(file_size / max_size_bytes)
    chunk_duration_ms = math.ceil(total_duration_ms / num_chunks)

    chunks = []
    for i, start_ms in enumerate(range(0, total_duration_ms, chunk_duration_ms)):
        end_ms = min(start_ms + chunk_duration_ms, total_duration_ms)
        chunk = audio[start_ms:end_ms]
        chunk_path = os.path.join(tempfile.gettempdir(), f"{os.path.basename(audio_path)}.chunk{i}.mp3")
        chunk.export(chunk_path, format="mp3")
        chunks.append((chunk_path, start_ms / 1000.0))

    return chunks
