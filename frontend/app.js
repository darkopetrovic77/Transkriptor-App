// Haupt-Screen: Engine-Toggle, Drag&Drop-Upload, Warteschlange, Verlauf.

const state = {
  engine: "local",
  languages: [],
  queue: [],
  queueSelected: new Set(), // transcript_id der ausgewaehlten "Fertig"-Eintraege
  history: {
    query: "",
    period: "alle",
    offset: 0,
    limit: 50,
    items: [],
    selected: new Set(),
  },
  openErrorId: null,
};

const el = (id) => document.getElementById(id);

// --- Hilfsfunktionen --------------------------------------------------

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return "0:00";
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function formatSize(bytes) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(isoString) {
  const date = new Date(isoString);
  return date.toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

async function downloadBlob(response, fallbackName) {
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : fallbackName;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// --- Sprachen & Engine --------------------------------------------------

async function loadLanguages() {
  const res = await fetch("/api/languages");
  state.languages = await res.json();
  const select = el("language-select");
  select.innerHTML = "";
  for (const lang of state.languages) {
    const option = document.createElement("option");
    option.value = lang.code;
    option.textContent = lang.name;
    if (lang.code === "auto") option.selected = true;
    select.appendChild(option);
  }
}

function updateModelRowVisibility() {
  el("model-row").style.display = state.engine === "local" ? "flex" : "none";
  el("groq-warning").style.display = state.engine === "groq" ? "block" : "none";
}

async function loadEngine() {
  const res = await fetch("/api/engine");
  const data = await res.json();
  state.engine = data.engine;
  renderEngineToggle();
  updateModelRowVisibility();
}

async function setEngine(engine) {
  const res = await fetch("/api/engine", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ engine }),
  });
  const data = await res.json();
  state.engine = data.engine;
  renderEngineToggle();
  updateModelRowVisibility();
}

function renderEngineToggle() {
  for (const btn of el("engine-toggle").querySelectorAll("button")) {
    btn.classList.toggle("active", btn.dataset.engine === state.engine);
  }
}

// --- Upload / Drag&Drop ---------------------------------------------------

function setupDropzone() {
  const dropzone = el("dropzone");
  const fileInput = el("file-input");

  dropzone.addEventListener("click", () => fileInput.click());

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files);
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) uploadFiles(fileInput.files);
    fileInput.value = "";
  });
}

async function uploadFiles(fileList, confirmed = false) {
  const language = el("language-select").value;
  const model = el("model-select").value;

  for (const file of fileList) {
    const formData = new FormData();
    formData.append("files", file);
    formData.append("language", language);
    formData.append("model", model);
    formData.append("confirmed", confirmed ? "true" : "false");

    const res = await fetch("/api/upload", { method: "POST", body: formData });
    const results = await res.json();

    for (const result of results) {
      if (result.error) {
        alert(`${result.filename}: ${result.error}`);
      } else if (result.warning === "lange_aufnahme") {
        const ok = confirm(`${result.message}\n\nDatei "${result.filename}" trotzdem verarbeiten?`);
        if (ok) await uploadFiles([file], true);
      }
    }
  }

  refreshQueue();
}

// --- Warteschlange --------------------------------------------------------

async function refreshQueue() {
  const res = await fetch("/api/queue");
  const data = await res.json();
  state.queue = data.items;
  renderEstimate(data.estimated_seconds);
  renderQueue();
}

function renderEstimate(seconds) {
  const minutes = Math.ceil(seconds / 60);
  el("estimate-text").textContent = `Geschätzte Verarbeitung der Warteschlange: ~${minutes} Min`;
}

function renderQueue() {
  const list = el("queue-list");
  list.innerHTML = "";

  // Auswahl bereinigen: nur "done"-Items duerfen ausgewaehlt sein
  const doneIds = new Set(state.queue.filter((i) => i.status === "done").map((i) => i.transcript_id));
  for (const id of Array.from(state.queueSelected)) {
    if (!doneIds.has(id)) state.queueSelected.delete(id);
  }

  el("queue-empty").style.display = state.queue.length === 0 ? "block" : "none";

  for (const item of state.queue) {
    list.appendChild(renderQueueItem(item));
    if (item.status === "error" && state.openErrorId === item.id) {
      list.appendChild(renderErrorDetails(item));
    }
  }

  updateQueueActionBar();
}

function renderQueueItem(item) {
  const row = document.createElement("div");
  row.className = "list-item" + (item.status === "error" ? " error" : "");

  if (item.status === "done") {
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = state.queueSelected.has(item.transcript_id);
    checkbox.addEventListener("click", (e) => e.stopPropagation());
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) state.queueSelected.add(item.transcript_id);
      else state.queueSelected.delete(item.transcript_id);
      updateQueueActionBar();
    });
    row.appendChild(checkbox);
  }

  const info = document.createElement("div");
  info.className = "info";
  const filename = document.createElement("div");
  filename.className = "filename";
  filename.textContent = item.filename;
  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = `${formatDuration(item.duration)} · ${formatSize(item.size_bytes)}`;
  info.append(filename, meta);
  row.appendChild(info);

  const tag = document.createElement("span");
  tag.className = `status-tag ${item.status}`;
  const labels = { queued: "Warteschlange", running: "Läuft", done: "Fertig", error: "Fehler – Klick für Details" };
  tag.textContent = labels[item.status] || item.status;
  if (item.status === "error") {
    tag.addEventListener("click", (e) => {
      e.stopPropagation();
      state.openErrorId = state.openErrorId === item.id ? null : item.id;
      renderQueue();
    });
  }
  row.appendChild(tag);

  if (item.status === "done") {
    row.addEventListener("click", () => {
      window.location.href = `detail.html?id=${item.transcript_id}`;
    });
  }

  return row;
}

const ERROR_EXPLANATIONS = {
  groq_key_missing: "Groq API-Key fehlt. Bitte in der .env-Datei eintragen (siehe console.groq.com).",
};

function renderErrorDetails(item) {
  const box = document.createElement("div");
  box.className = "error-details";

  const explanation = ERROR_EXPLANATIONS[item.error_code] || item.error || "Unbekannter Fehler.";
  box.textContent = explanation;

  const actions = document.createElement("div");
  actions.className = "actions";

  const retryBtn = document.createElement("button");
  retryBtn.className = "btn small";
  retryBtn.textContent = "Erneut versuchen";
  retryBtn.addEventListener("click", async () => {
    await fetch(`/api/queue/${item.id}/retry`, { method: "POST" });
    state.openErrorId = null;
    refreshQueue();
  });

  const removeBtn = document.createElement("button");
  removeBtn.className = "btn small";
  removeBtn.textContent = "Entfernen";
  removeBtn.addEventListener("click", async () => {
    await fetch(`/api/queue/${item.id}`, { method: "DELETE" });
    state.openErrorId = null;
    refreshQueue();
  });

  actions.append(retryBtn, removeBtn);
  box.appendChild(actions);
  return box;
}

function updateQueueActionBar() {
  const bar = el("queue-action-bar");
  const count = state.queueSelected.size;
  bar.style.display = count > 0 ? "flex" : "none";
  el("queue-selected-count").textContent = `${count} ausgewählt`;

  const doneIds = state.queue.filter((i) => i.status === "done").map((i) => i.transcript_id);
  const masterCheckbox = el("queue-select-all");
  masterCheckbox.checked = doneIds.length > 0 && doneIds.every((id) => state.queueSelected.has(id));
}

// --- Verlauf ---------------------------------------------------------------

async function loadHistory(reset) {
  if (reset) {
    state.history.offset = 0;
    state.history.items = [];
    state.history.selected.clear();
  }

  const params = new URLSearchParams({
    query: state.history.query,
    period: state.history.period,
    offset: state.history.offset,
    limit: state.history.limit,
  });
  const res = await fetch(`/api/history?${params}`);
  const items = await res.json();

  state.history.items = state.history.items.concat(items);
  state.history.offset += items.length;
  el("load-more").style.display = items.length === state.history.limit ? "inline-block" : "none";

  renderHistory();
}

function renderHistory() {
  const list = el("history-list");
  list.innerHTML = "";

  el("history-empty").style.display = state.history.items.length === 0 ? "block" : "none";

  for (const item of state.history.items) {
    const row = document.createElement("div");
    row.className = "list-item";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = state.history.selected.has(item.id);
    checkbox.addEventListener("click", (e) => e.stopPropagation());
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) state.history.selected.add(item.id);
      else state.history.selected.delete(item.id);
      updateHistoryActionBar();
    });
    row.appendChild(checkbox);

    const info = document.createElement("div");
    info.className = "info";
    const filename = document.createElement("div");
    filename.className = "filename";
    filename.textContent = item.dateiname;
    const meta = document.createElement("div");
    meta.className = "meta";
    meta.textContent = `${formatDuration(item.dauer)} · ${item.sprache} · ${formatDate(item.erstellt_am)}`;
    info.append(filename, meta);
    row.appendChild(info);

    const arrow = document.createElement("span");
    arrow.className = "arrow";
    arrow.textContent = "→";
    row.appendChild(arrow);

    row.addEventListener("click", () => {
      window.location.href = `detail.html?id=${item.id}`;
    });

    list.appendChild(row);
  }

  updateHistoryActionBar();
}

function updateHistoryActionBar() {
  const bar = el("history-action-bar");
  const count = state.history.selected.size;
  bar.style.display = count > 0 ? "flex" : "none";
  el("history-selected-count").textContent = `${count} ausgewählt`;

  const allIds = state.history.items.map((i) => i.id);
  const masterCheckbox = el("history-select-all");
  masterCheckbox.checked = allIds.length > 0 && allIds.every((id) => state.history.selected.has(id));
}

// --- Downloads ---------------------------------------------------------------

async function downloadSelected(target, fmt) {
  const ids = target === "queue" ? Array.from(state.queueSelected) : Array.from(state.history.selected);
  if (ids.length === 0) return;

  if (ids.length === 1) {
    const id = ids[0];
    if (fmt === "both") {
      window.location.href = `/api/transcripts/${id}/download/txt`;
      setTimeout(() => (window.location.href = `/api/transcripts/${id}/download/srt`), 300);
    } else {
      window.location.href = `/api/transcripts/${id}/download/${fmt}`;
    }
    return;
  }

  const res = await fetch("/api/transcripts/bulk-download", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids, format: fmt }),
  });
  if (!res.ok) {
    alert("Download fehlgeschlagen.");
    return;
  }
  await downloadBlob(res, "transkripte.zip");
}

// --- Init ---------------------------------------------------------------

function setupEventListeners() {
  for (const btn of el("engine-toggle").querySelectorAll("button")) {
    btn.addEventListener("click", () => setEngine(btn.dataset.engine));
  }

  el("start-all").addEventListener("click", async () => {
    await fetch("/api/queue/start", { method: "POST" });
    refreshQueue();
  });

  el("clear-queue").addEventListener("click", async () => {
    await fetch("/api/queue", { method: "DELETE" });
    refreshQueue();
  });

  el("queue-select-all").addEventListener("change", (e) => {
    const doneIds = state.queue.filter((i) => i.status === "done").map((i) => i.transcript_id);
    if (e.target.checked) doneIds.forEach((id) => state.queueSelected.add(id));
    else doneIds.forEach((id) => state.queueSelected.delete(id));
    renderQueue();
  });

  el("history-select-all").addEventListener("change", (e) => {
    const allIds = state.history.items.map((i) => i.id);
    if (e.target.checked) allIds.forEach((id) => state.history.selected.add(id));
    else allIds.forEach((id) => state.history.selected.delete(id));
    renderHistory();
  });

  for (const btn of document.querySelectorAll("[data-fmt]")) {
    btn.addEventListener("click", () => downloadSelected(btn.dataset.target, btn.dataset.fmt));
  }

  let searchTimeout;
  el("history-search").addEventListener("input", (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      state.history.query = e.target.value;
      loadHistory(true);
    }, 300);
  });

  el("history-period").addEventListener("change", (e) => {
    state.history.period = e.target.value;
    loadHistory(true);
  });

  el("load-more").addEventListener("click", () => loadHistory(false));
}

async function init() {
  setupDropzone();
  setupEventListeners();
  await Promise.all([loadLanguages(), loadEngine()]);
  await refreshQueue();
  await loadHistory(true);
  setInterval(refreshQueue, 2000);
}

init();
