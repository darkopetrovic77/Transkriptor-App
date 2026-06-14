# Installationsanleitung – Transkriptor

Diese Anleitung beschreibt, wie du die Transkriptor-App auf einem anderen
Windows-Rechner einrichtest.

## Voraussetzungen

- **Windows 10/11**, CPU mit ≥16 GB RAM (kein GPU nötig)
- **Python 3.12** (NICHT 3.13 – führt zu Abstürzen bei der lokalen
  Transkriptions-Engine)
- **ffmpeg** (für Audio-Extraktion aus Videos)
- Internetverbindung beim ersten Start (zum Herunterladen des
  Whisper-Modells, ca. 1,5 GB für "medium")

---

## Schritt 1: Python 3.12 installieren

Prüfen, ob Python 3.12 schon vorhanden ist:

```powershell
py -3.12 --version
```

Falls nicht installiert:

```powershell
winget install --id Python.Python.3.12
```

## Schritt 2: ffmpeg installieren

```powershell
winget install --id Gyan.FFmpeg
```

Danach Terminal neu öffnen und prüfen:

```powershell
ffmpeg -version
```

## Schritt 3: Projekt herunterladen

Das Projekt liegt auf GitHub (privates Repository). Im gewünschten
Zielordner ein Terminal öffnen und klonen:

```powershell
git clone https://github.com/darkopetrovic77/Transkriptor-App.git
cd Transkriptor-App
```

Bei der Anmeldung öffnet sich ein Browser-Fenster für den GitHub-Login.

**Hinweis:** Folgende Ordner/Dateien sind absichtlich nicht im Repository
(sie werden automatisch neu erstellt bzw. enthalten lokale/geheime Daten):

- `.venv/`
- `models/`
- `uploads/`
- `transcripts/`
- `transkriptor.db`
- `.env`
- `*.log`

## Schritt 4: Virtuelle Umgebung erstellen

Im Projektordner ein Terminal öffnen (PowerShell) und:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
```

Die Eingabeaufforderung zeigt jetzt `(.venv)` am Anfang – das bedeutet, die
isolierte Python-Umgebung ist aktiv.

## Schritt 5: Abhängigkeiten installieren

```powershell
pip install -r requirements.txt
```

Das installiert FastAPI, faster-whisper, Groq-Client und alle weiteren
benötigten Pakete (dauert ein paar Minuten).

## Schritt 6: Groq API-Key einrichten (optional)

Nur nötig, wenn du die Groq-Engine (Cloud-Transkription) nutzen möchtest.
Die lokale Engine funktioniert ohne diesen Schritt.

1. Datei `.env.example` kopieren und in `.env` umbenennen
2. In der `.env`-Datei den eigenen Key eintragen:
   ```
   GROQ_API_KEY=dein-key-hier
   ```
3. Kostenlosen Key erhältst du auf [console.groq.com](https://console.groq.com)

## Schritt 7: Server starten

```powershell
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

## Schritt 8: App im Browser öffnen

```
http://127.0.0.1:8000/index.html
```

**Hinweis zum ersten Start:** Beim ersten Hochladen einer Datei mit der
lokalen Engine wird das Whisper-Modell (~1,5 GB für "medium") automatisch
heruntergeladen und in `models/` gespeichert. Das kann je nach
Internetverbindung einige Minuten dauern – danach läuft alles offline.

---

## Optional: Zugriff von anderen Geräten im Netzwerk

Wenn du z.B. vom Handy oder Laptop im selben WLAN auf den Server zugreifen
willst, beim Start `0.0.0.0` statt `127.0.0.1` verwenden:

```powershell
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Dann ist die App über `http://<IP-Adresse-des-Rechners>:8000/index.html`
erreichbar (IP-Adresse mit `ipconfig` herausfinden). Eventuell muss die
Windows-Firewall den Port 8000 freigeben.

---

## Server zukünftig wieder starten

Sobald alles einmal eingerichtet ist, reicht für künftige Starts:

```powershell
cd "Pfad\zum\Projektordner"
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```
