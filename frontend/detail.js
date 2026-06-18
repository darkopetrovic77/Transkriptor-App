// Detail-Seite: Audio-Player, Zeitstempel-Transkript, Edit-Modus.

const el = (id) => document.getElementById(id);

const params = new URLSearchParams(window.location.search);
const transcriptId = params.get("id");

let transcript = null;
let editMode = false;

function formatDuration(seconds) {
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function formatTimestamp(seconds) {
  const total = Math.round(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

async function loadTranscript() {
  const res = await fetch(`/api/transcripts/${transcriptId}`);
  if (!res.ok) {
    el("filename").textContent = "Transkript nicht gefunden";
    return;
  }
  transcript = await res.json();
  render();
}

async function loadFileSize() {
  try {
    // Range-Request: laedt nur 1 Byte, liefert die Gesamtgroesse im
    // Content-Range-Header (Dateigroesse ist nur eine Zusatzinfo).
    const res = await fetch(`/api/transcripts/${transcriptId}/audio`, { headers: { Range: "bytes=0-0" } });
    const contentRange = res.headers.get("Content-Range"); // "bytes 0-0/12345"
    if (contentRange) {
      const total = contentRange.split("/")[1];
      if (total) return `${(total / (1024 * 1024)).toFixed(1)} MB`;
    }
  } catch (e) {
    // ignorieren, Groesse ist nur eine Zusatzinfo
  }
  return null;
}

async function render() {
  el("filename").textContent = transcript.dateiname;

  const parts = [
    formatDuration(transcript.dauer),
    transcript.sprache,
    formatDuration(transcript.verarbeitungszeit) + " Verarbeitung",
    transcript.modell,
  ];
  const size = await loadFileSize();
  if (size) parts.splice(2, 0, size);
  el("file-meta").textContent = parts.join(" · ");

  const audioRes = await fetch(`/api/transcripts/${transcriptId}/audio`, { method: "HEAD" }).catch(() => null);
  const audioPlayer = el("audio-player");
  if (audioRes && audioRes.ok) {
    audioPlayer.src = `/api/transcripts/${transcriptId}/audio`;
    audioPlayer.style.display = "";
  } else {
    audioPlayer.style.display = "none";
    audioPlayer.insertAdjacentHTML("afterend", "<p style=\"color:var(--muted);font-size:0.9rem\">Audio nicht mehr verfügbar (Originaldatei wurde nach Transkription gelöscht).</p>");
  }

  renderSegments();
}

function renderSegments() {
  const container = el("segments");
  container.innerHTML = "";
  container.classList.toggle("edit-mode", editMode);

  for (const segment of transcript.segments) {
    const row = document.createElement("div");
    row.className = "segment";

    const timestamp = document.createElement("div");
    timestamp.className = "timestamp";
    timestamp.textContent = formatTimestamp(segment.start);
    if (!editMode) {
      timestamp.addEventListener("click", () => {
        const audio = el("audio-player");
        audio.currentTime = segment.start;
        audio.play();
      });
    }
    row.appendChild(timestamp);

    if (editMode) {
      const textarea = document.createElement("textarea");
      textarea.value = segment.text;
      textarea.addEventListener("input", () => {
        segment.text = textarea.value;
        textarea.style.height = "auto";
        textarea.style.height = textarea.scrollHeight + "px";
      });
      row.appendChild(textarea);
    } else {
      const text = document.createElement("div");
      text.className = "text";
      text.textContent = segment.text;
      row.appendChild(text);
    }

    container.appendChild(row);
  }
}

function enterEditMode() {
  editMode = true;
  transcript._backup = JSON.parse(JSON.stringify(transcript.segments));
  el("edit-badge").style.display = "inline-block";
  el("read-actions").style.display = "none";
  el("edit-actions").style.display = "flex";
  renderSegments();

  // Textareas auf Inhaltshoehe anpassen
  for (const textarea of document.querySelectorAll("#segments textarea")) {
    textarea.style.height = "auto";
    textarea.style.height = textarea.scrollHeight + "px";
  }
}

function exitEditMode() {
  editMode = false;
  el("edit-badge").style.display = "none";
  el("read-actions").style.display = "flex";
  el("edit-actions").style.display = "none";
  renderSegments();
}

async function saveChanges() {
  const res = await fetch(`/api/transcripts/${transcriptId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ segments: transcript.segments }),
  });
  transcript = await res.json();
  exitEditMode();
}

function discardChanges() {
  transcript.segments = transcript._backup;
  exitEditMode();
}

function setupEventListeners() {
  el("edit-btn").addEventListener("click", enterEditMode);
  el("save-btn").addEventListener("click", saveChanges);
  el("discard-btn").addEventListener("click", discardChanges);

  el("copy-btn").addEventListener("click", async () => {
    await navigator.clipboard.writeText(transcript.text);
    const btn = el("copy-btn");
    const original = btn.textContent;
    btn.textContent = "Kopiert!";
    setTimeout(() => (btn.textContent = original), 1500);
  });

  el("download-txt").addEventListener("click", () => {
    window.location.href = `/api/transcripts/${transcriptId}/download/txt`;
  });
  el("download-srt").addEventListener("click", () => {
    window.location.href = `/api/transcripts/${transcriptId}/download/srt`;
  });
}

setupEventListeners();
loadTranscript();
