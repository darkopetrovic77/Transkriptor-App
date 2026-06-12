"""SQLite-Datenbank fuer den Transkriptions-Verlauf.

Die Datenbank liegt als Datei `transkriptor.db` im Projekt-Root und
wird beim ersten Start automatisch angelegt.
"""

import json
import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "transkriptor.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS transkripte (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dateiname TEXT NOT NULL,
            dauer REAL NOT NULL,
            sprache TEXT NOT NULL,
            modell TEXT NOT NULL,
            engine TEXT NOT NULL,
            erstellt_am TEXT NOT NULL,
            pfad_audio TEXT NOT NULL,
            pfad_txt TEXT NOT NULL,
            pfad_srt TEXT NOT NULL,
            text TEXT NOT NULL,
            segments_json TEXT NOT NULL,
            verarbeitungszeit REAL NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def insert_transcript(
    dateiname: str,
    dauer: float,
    sprache: str,
    modell: str,
    engine: str,
    pfad_audio: str,
    pfad_txt: str,
    pfad_srt: str,
    text: str,
    segments: list[dict],
    verarbeitungszeit: float,
) -> int:
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO transkripte
            (dateiname, dauer, sprache, modell, engine, erstellt_am, pfad_audio, pfad_txt, pfad_srt, text, segments_json, verarbeitungszeit)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            dateiname,
            dauer,
            sprache,
            modell,
            engine,
            datetime.now().isoformat(),
            pfad_audio,
            pfad_txt,
            pfad_srt,
            text,
            json.dumps(segments, ensure_ascii=False),
            verarbeitungszeit,
        ),
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def get_transcript(transcript_id: int) -> sqlite3.Row | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM transkripte WHERE id = ?", (transcript_id,)).fetchone()
    conn.close()
    return row


def update_transcript_text(transcript_id: int, segments: list[dict]) -> None:
    text = " ".join(segment["text"] for segment in segments)
    conn = get_connection()
    conn.execute(
        "UPDATE transkripte SET text = ?, segments_json = ? WHERE id = ?",
        (text, json.dumps(segments, ensure_ascii=False), transcript_id),
    )
    conn.commit()
    conn.close()


def search_history(query: str, period: str, limit: int, offset: int) -> list[sqlite3.Row]:
    """Sucht im Verlauf nach Dateinamen, gefiltert nach Zeitraum.

    `period` ist eines von "alle", "woche", "monat", "3monate".
    """
    sql = "SELECT * FROM transkripte WHERE dateiname LIKE ?"
    params: list = [f"%{query}%"]

    if period != "alle":
        days = {"woche": 7, "monat": 30, "3monate": 90}.get(period)
        if days:
            cutoff = datetime.now().timestamp() - days * 86400
            sql += " AND erstellt_am >= ?"
            params.append(datetime.fromtimestamp(cutoff).isoformat())

    sql += " ORDER BY erstellt_am DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    conn = get_connection()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def get_transcripts_by_ids(ids: list[int]) -> list[sqlite3.Row]:
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    conn = get_connection()
    rows = conn.execute(f"SELECT * FROM transkripte WHERE id IN ({placeholders})", ids).fetchall()
    conn.close()
    return rows
