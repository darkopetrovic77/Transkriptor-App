"""FastAPI-Backend fuer den Transkriptor.

Stellt die REST-API bereit (Upload, Warteschlange, Transkripte, Verlauf,
Downloads) und liefert das Frontend (statische Dateien) aus.
"""

import json
import os
import zipfile
from io import BytesIO

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import db, queue_manager
from .models import BulkDownloadRequest, EngineUpdate, TranscriptUpdate, segments_to_srt

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
LANGUAGES_PATH = os.path.join(BASE_DIR, "languages.json")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

ALLOWED_EXTENSIONS = {".mp3", ".mp4", ".wav", ".m4a", ".mov", ".webm", ".ts"}
GROQ_AUDIO_SECONDS_PER_HOUR_LIMIT = 7200  # Free-Tier-Limit pro Stunde

os.makedirs(UPLOADS_DIR, exist_ok=True)

db.init_db()

app = FastAPI(title="Transkriptor")


# --- Sprachen & Engine ----------------------------------------------------

@app.get("/api/languages")
def get_languages():
    """Liest languages.json bei jedem Aufruf frisch ein (editierbar ohne Neustart)."""
    if not os.path.exists(LANGUAGES_PATH):
        return []
    with open(LANGUAGES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/engine")
def get_engine():
    return {"engine": queue_manager.get_current_engine(), "groq_key_present": bool(os.environ.get("GROQ_API_KEY"))}


@app.post("/api/engine")
def set_engine(update: EngineUpdate):
    try:
        queue_manager.set_current_engine(update.engine)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"engine": queue_manager.get_current_engine()}


# --- Upload & Warteschlange ------------------------------------------------

@app.post("/api/upload")
async def upload_files(
    files: list[UploadFile] = File(...),
    language: str = Form("auto"),
    model: str | None = Form(None),
    confirmed: bool = Form(False),
):
    results = []
    for upload in files:
        ext = os.path.splitext(upload.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            results.append({"filename": upload.filename, "error": f"Format '{ext}' wird nicht unterstuetzt."})
            continue

        dest_path = os.path.join(UPLOADS_DIR, f"{os.urandom(8).hex()}_{upload.filename}")
        try:
            content = await upload.read()
            with open(dest_path, "wb") as f:
                f.write(content)
        except Exception as exc:
            results.append({"filename": upload.filename, "error": f"Datei konnte nicht gespeichert werden: {exc}"})
            continue

        try:
            duration = queue_manager.get_audio_duration(dest_path)
        except Exception as exc:
            os.remove(dest_path)
            results.append({"filename": upload.filename, "error": f"Datei konnte nicht gelesen werden (ffmpeg): {exc}"})
            continue

        if (
            queue_manager.get_current_engine() == "groq"
            and duration > GROQ_AUDIO_SECONDS_PER_HOUR_LIMIT
            and not confirmed
        ):
            os.remove(dest_path)
            results.append({
                "filename": upload.filename,
                "warning": "groq_limit",
                "duration": duration,
                "message": (
                    f"Diese Aufnahme ist {duration / 60:.0f} Minuten lang und ueberschreitet "
                    f"das Groq-Limit von {GROQ_AUDIO_SECONDS_PER_HOUR_LIMIT // 60} Audio-Minuten/Stunde. "
                    "Die Transkription wird wahrscheinlich mit einem Rate-Limit-Fehler abbrechen. "
                    "Empfehlung: lokale Engine verwenden. Trotzdem mit Groq versuchen?"
                ),
            })
            continue

        try:
            item = queue_manager.add_to_queue(dest_path, upload.filename, language, model)
        except Exception as exc:
            os.remove(dest_path)
            results.append({"filename": upload.filename, "error": f"Fehler beim Hinzufügen zur Warteschlange: {exc}"})
            continue
        results.append(item.to_dict())

    return results


@app.get("/api/queue")
def get_queue():
    items = [item.to_dict() for item in queue_manager.get_queue()]
    return {"items": items, "estimated_seconds": queue_manager.estimated_total_seconds()}


@app.post("/api/queue/start")
def start_queue():
    queue_manager.start_processing()
    return {"status": "gestartet"}


@app.delete("/api/queue")
def clear_queue():
    queue_manager.clear_finished()
    return {"status": "geleert"}


@app.delete("/api/queue/{item_id}")
def remove_queue_item(item_id: str):
    queue_manager.remove_item(item_id)
    return {"status": "entfernt"}


@app.post("/api/queue/{item_id}/cancel")
def cancel_queue_item(item_id: str):
    if not queue_manager.cancel_item(item_id):
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    return {"status": "abgebrochen"}


@app.post("/api/queue/{item_id}/retry")
def retry_queue_item(item_id: str):
    if not queue_manager.retry_item(item_id):
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden")
    return {"status": "erneut gestartet"}


# --- Transkripte -----------------------------------------------------------

def _transcript_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "dateiname": row["dateiname"],
        "dauer": row["dauer"],
        "sprache": row["sprache"],
        "modell": row["modell"],
        "engine": row["engine"],
        "erstellt_am": row["erstellt_am"],
        "text": row["text"],
        "segments": json.loads(row["segments_json"]),
        "verarbeitungszeit": row["verarbeitungszeit"],
    }


@app.get("/api/transcripts/{transcript_id}")
def get_transcript(transcript_id: int):
    row = db.get_transcript(transcript_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Transkript nicht gefunden")
    return _transcript_to_dict(row)


@app.put("/api/transcripts/{transcript_id}")
def update_transcript(transcript_id: int, update: TranscriptUpdate):
    row = db.get_transcript(transcript_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Transkript nicht gefunden")

    db.update_transcript_text(transcript_id, update.segments)

    text = " ".join(segment["text"] for segment in update.segments)
    with open(row["pfad_txt"], "w", encoding="utf-8") as f:
        f.write(text)
    with open(row["pfad_srt"], "w", encoding="utf-8") as f:
        f.write(segments_to_srt(update.segments))

    return _transcript_to_dict(db.get_transcript(transcript_id))


@app.get("/api/transcripts/{transcript_id}/audio")
def get_transcript_audio(transcript_id: int):
    row = db.get_transcript(transcript_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Transkript nicht gefunden")
    if not row["pfad_audio"] or not os.path.exists(row["pfad_audio"]):
        raise HTTPException(status_code=404, detail="Audiodatei nicht verfügbar")
    return FileResponse(row["pfad_audio"])


@app.get("/api/transcripts/{transcript_id}/download/{fmt}")
def download_transcript(transcript_id: int, fmt: str):
    row = db.get_transcript(transcript_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Transkript nicht gefunden")

    if fmt not in ("txt", "srt"):
        raise HTTPException(status_code=400, detail="Format muss 'txt' oder 'srt' sein")

    path = row["pfad_txt"] if fmt == "txt" else row["pfad_srt"]
    base_name = os.path.splitext(row["dateiname"])[0]
    return FileResponse(path, filename=f"{base_name}.{fmt}", media_type="text/plain")


@app.post("/api/transcripts/bulk-download")
def bulk_download(payload: BulkDownloadRequest):
    rows = db.get_transcripts_by_ids(payload.ids)
    if not rows:
        raise HTTPException(status_code=404, detail="Keine Transkripte gefunden")

    formats = []
    if payload.format in ("txt", "both"):
        formats.append("txt")
    if payload.format in ("srt", "both"):
        formats.append("srt")
    if not formats:
        raise HTTPException(status_code=400, detail="Format muss 'txt', 'srt' oder 'both' sein")

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for row in rows:
            base_name = os.path.splitext(row["dateiname"])[0]
            for fmt in formats:
                path = row["pfad_txt"] if fmt == "txt" else row["pfad_srt"]
                if os.path.exists(path):
                    zf.write(path, arcname=f"{base_name}.{fmt}")
    buffer.seek(0)

    from datetime import datetime
    zip_filename = f"transkripte_{datetime.now().strftime('%Y-%m-%d')}.zip"

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )


# --- Verlauf -----------------------------------------------------------------

@app.get("/api/history")
def get_history(query: str = "", period: str = "alle", offset: int = 0, limit: int = 50):
    rows = db.search_history(query, period, limit, offset)
    return [_transcript_to_dict(row) for row in rows]


# --- Frontend ------------------------------------------------------------------

if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
