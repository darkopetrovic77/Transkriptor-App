"""Einfacher Kommandozeilen-Test fuer die Transcriber-Engines.

Aufruf:
    python -m transcriber.cli transcribe <datei> [--language de] [--model medium]
"""

import argparse
import sys

from .groq_engine import GroqAPIEngine
from .local_whisper import DEFAULT_MODEL, LocalWhisperEngine


def main() -> None:
    # Windows-Konsolen nutzen oft nicht UTF-8 -> Umlaute wuerden falsch
    # angezeigt. Hier erzwingen wir UTF-8 fuer die Ausgabe.
    sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Transkribiert eine Audiodatei (lokal, faster-whisper).")
    subparsers = parser.add_subparsers(dest="command", required=True)

    transcribe_parser = subparsers.add_parser("transcribe", help="Audiodatei transkribieren")
    transcribe_parser.add_argument("audio_path", help="Pfad zur Audiodatei")
    transcribe_parser.add_argument("--language", default=None, help="Sprachcode, z.B. de, en (Standard: Auto-Erkennung)")
    transcribe_parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Whisper-Modell (Standard: {DEFAULT_MODEL})")
    transcribe_parser.add_argument("--engine", default="local", choices=["local", "groq"], help="Engine: local oder groq (Standard: local)")

    args = parser.parse_args()

    if args.command == "transcribe":
        if args.engine == "groq":
            engine = GroqAPIEngine()
        else:
            engine = LocalWhisperEngine()
        print(f"Transkribiere '{args.audio_path}' mit Engine '{args.engine}' / Modell '{args.model}' ...")
        result = engine.transcribe(args.audio_path, language=args.language, model=args.model)

        print(f"\nErkannte Sprache: {result.language}")
        print("\n--- Transkript mit Zeitstempeln ---")
        for segment in result.segments:
            print(f"[{segment.start:6.2f}s -> {segment.end:6.2f}s] {segment.text}")

        print("\n--- Volltext ---")
        print(result.text)


if __name__ == "__main__":
    main()
