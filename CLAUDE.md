# Transkriptor App

## Was ist das?
Lokale Web-App zum Transkribieren von Audio-/Video-Dateien per Drag & Drop.
Ergebnisse können gelesen, editiert und als .txt/.srt heruntergeladen werden.

## Stack
- **transcriber/**: eigenständiges Python-Package (Adapter-Pattern für Engines)
  - `LocalWhisperEngine` (faster-whisper, CPU/int8) – Standard
  - `GroqAPIEngine` (Groq Whisper API, whisper-large-v3-turbo)
  - `OpenAIAPIEngine` – vorbereiteter Stub, nicht aktiv
- **Backend**: FastAPI + Uvicorn, SQLite (transkriptor.db)
- **Frontend**: Vanilla HTML/CSS/JS (kein Build-Tooling)
- **Hardware**: CPU-only PC, ≥16 GB RAM, kein GPU

## Konventionen / Präferenzen
- User hat keine Programmiererfahrung → jeder Schritt wird auf Deutsch erklärt
  (was wird gemacht und warum)
- Schritt-für-Schritt-Vorgehen gemäss Plan in `.claude/plans/`
- Nach jedem grösseren Meilenstein: git commit mit aussagekräftiger Botschaft
- Bei wichtigen Entscheidungen nachfragen, nicht durchrauschen
- Ergebnis nach jedem grösseren Schritt zeigen und auf OK warten

## Konfiguration
- `languages.json` im Projekt-Root – editierbar ohne Code-Änderung, Sprachliste
- `.env` – GROQ_API_KEY für Groq-Engine
- Modell-Mapping (lokal): Englisch → small.en, Deutsch/Schweizerdeutsch/
  Portugiesisch/Serbisch/Andere → medium

## Mockups
UI-Mockups in `mockups/` zeigen Haupt-Screen und Detail-Seite (Lese-/Edit-Modus).
