"""Warteschlange fuer Transkriptions-Auftraege.

Die Warteschlange liegt im Arbeitsspeicher (kein Redis/Datenbank-Queue
notwendig fuer einen lokalen Single-User-Server). Ein Hintergrund-Thread
arbeitet die Eintraege sequentiell ab, sobald "Alle starten" gedrueckt
wurde. Laeuft die App, kann der Browser geschlossen werden -- der
Worker-Thread arbeitet im Server-Prozess weiter.
"""

import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field

import ffmpeg

from transcriber.groq_engine import GroqAPIEngine, GroqAPIKeyMissingError, GroqRateLimitError
from transcriber.local_whisper import LocalWhisperEngine
from transcriber.utils import convert_to_mp3, extract_audio

from . import db
from .models import default_model_for_language, estimate_seconds, segments_to_srt

TRANSCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "transcripts")
os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".ts"}


@dataclass
class QueueItem:
    id: str
    filename: str
    filepath: str
    language: str
    model: str
    duration: float
    size_bytes: int
    status: str = "queued"  # queued, running, done, error, cancelled
    error: str | None = None
    error_code: str | None = None
    engine: str | None = None  # wird beim Start fixiert
    transcript_id: int | None = None
    selected: bool = False
    cancel_requested: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# globaler Zustand -------------------------------------------------------

_lock = threading.Lock()
_queue: list[QueueItem] = []
_current_engine = "local"  # "local" oder "groq", per Toggle umschaltbar
_worker_thread: threading.Thread | None = None

_local_engine = LocalWhisperEngine()


def get_current_engine() -> str:
    with _lock:
        return _current_engine


def set_current_engine(engine: str) -> None:
    if engine not in ("local", "groq"):
        raise ValueError("engine muss 'local' oder 'groq' sein")
    with _lock:
        global _current_engine
        _current_engine = engine


def get_audio_duration(path: str) -> float:
    try:
        probe = ffmpeg.probe(path)
        return float(probe["format"]["duration"])
    except Exception:
        return 0.0


def add_to_queue(filepath: str, filename: str, language: str, model: str | None) -> QueueItem:
    duration = get_audio_duration(filepath)
    resolved_model = model or default_model_for_language(language)
    item = QueueItem(
        id=str(uuid.uuid4()),
        filename=filename,
        filepath=filepath,
        language=language,
        model=resolved_model,
        duration=duration,
        size_bytes=os.path.getsize(filepath),
    )
    with _lock:
        _queue.append(item)
    return item


def get_queue() -> list[QueueItem]:
    with _lock:
        return list(_queue)


def get_item(item_id: str) -> QueueItem | None:
    with _lock:
        for item in _queue:
            if item.id == item_id:
                return item
    return None


def clear_finished() -> None:
    """Entfernt alle Eintraege, die nicht gerade laufen ("Liste leeren")."""
    with _lock:
        _queue[:] = [item for item in _queue if item.status == "running"]


def remove_item(item_id: str) -> None:
    with _lock:
        _queue[:] = [item for item in _queue if item.id != item_id]


def estimated_total_seconds() -> float:
    total = 0.0
    with _lock:
        for item in _queue:
            if item.status == "queued":
                engine = _current_engine
                total += estimate_seconds(item.duration, engine, item.model)
    return total


def start_processing() -> None:
    global _worker_thread
    with _lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return
        _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
        _worker_thread.start()


def _next_queued_item() -> QueueItem | None:
    with _lock:
        for item in _queue:
            if item.status == "queued":
                return item
    return None


def _worker_loop() -> None:
    while True:
        item = _next_queued_item()
        if item is None:
            return
        _process_item(item)


def _get_engine_instance(engine_name: str):
    if engine_name == "groq":
        return GroqAPIEngine()  # prueft GROQ_API_KEY direkt bei Erstellung
    return _local_engine


def _process_item(item: QueueItem) -> None:
    item.status = "running"
    item.engine = get_current_engine()

    audio_path = item.filepath
    extracted_path = None

    try:
        ext = os.path.splitext(item.filepath)[1].lower()
        if ext in VIDEO_EXTENSIONS:
            extracted_path = extract_audio(item.filepath)
            audio_path = extracted_path

        engine = _get_engine_instance(item.engine)

        start_time = time.time()
        result = engine.transcribe(audio_path, language=_resolve_language(item.language), model=item.model)
        processing_time = time.time() - start_time

        if item.cancel_requested:
            item.status = "cancelled"
            return

        segments = [{"start": s.start, "end": s.end, "text": s.text} for s in result.segments]

        base_name = os.path.splitext(item.filename)[0]
        txt_path = os.path.join(TRANSCRIPTS_DIR, f"{item.id}_{base_name}.txt")
        srt_path = os.path.join(TRANSCRIPTS_DIR, f"{item.id}_{base_name}.srt")
        mp3_path = os.path.join(TRANSCRIPTS_DIR, f"{item.id}_{base_name}.mp3")

        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(result.text)
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(segments_to_srt(segments))

        # Original durch kleine MP3 ersetzen (spart Gigabytes in uploads/)
        convert_to_mp3(audio_path, mp3_path)
        if os.path.exists(item.filepath):
            os.remove(item.filepath)

        transcript_id = db.insert_transcript(
            dateiname=item.filename,
            dauer=item.duration,
            sprache=result.language or item.language,
            modell=item.model,
            engine=item.engine,
            pfad_audio=mp3_path,
            pfad_txt=txt_path,
            pfad_srt=srt_path,
            text=result.text,
            segments=segments,
            verarbeitungszeit=processing_time,
        )

        item.transcript_id = transcript_id
        item.status = "done"

    except GroqAPIKeyMissingError as exc:
        item.status = "error"
        item.error_code = "groq_key_missing"
        item.error = str(exc)
    except GroqRateLimitError as exc:
        item.status = "error"
        item.error_code = "groq_rate_limit"
        item.error = str(exc)
    except Exception as exc:  # noqa: BLE001 - wir wollen jeden Fehler im UI anzeigen
        item.status = "error"
        item.error_code = "unbekannt"
        item.error = str(exc)
    finally:
        if extracted_path and os.path.exists(extracted_path):
            os.remove(extracted_path)


def _resolve_language(language: str) -> str | None:
    if language in ("auto", ""):
        return None
    if language == "de-ch":
        return "de"
    return language


def cancel_item(item_id: str) -> bool:
    item = get_item(item_id)
    if item is None:
        return False
    if item.status == "queued":
        item.status = "cancelled"
    elif item.status == "running":
        item.cancel_requested = True  # Worker verwirft das Ergebnis nach Abschluss
    return True


def retry_item(item_id: str) -> bool:
    item = get_item(item_id)
    if item is None:
        return False
    item.status = "queued"
    item.error = None
    item.error_code = None
    start_processing()
    return True
