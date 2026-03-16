// Engrave Desktop — Frontend Application
// Uses Tauri's IPC to communicate with the Rust backend.

const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;
const { open: shellOpen } = window.__TAURI__.shell;
const { open: dialogOpen, save: dialogSave } = window.__TAURI__.dialog;

// --- State ---

let currentMidiPath = null;
let currentTracks = [];
let currentOutputDir = null;

// --- DOM refs ---

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const dropZone = $("#drop-zone");
const fileInput = $("#midi-file-input");
const uploadSection = $("#upload-section");
const tracksSection = $("#tracks-section");
const progressSection = $("#progress-section");
const resultsSection = $("#results-section");
const settingsModal = $("#settings-modal");
const noKeyOverlay = $("#no-key-overlay");
const errorBanner = $("#error-banner");

// --- Instrument options for the track editor ---

const INSTRUMENTS = [
  "Trumpet", "Trombone", "Bass Trombone", "Tuba", "French Horn",
  "Alto Sax", "Tenor Sax", "Baritone Sax", "Soprano Sax",
  "Flute", "Clarinet", "Oboe", "Bassoon",
  "Piano", "Guitar", "Bass", "Drums",
  "Violin", "Viola", "Cello", "Double Bass",
  "Vocals",
];

// --- Big Band preset mapping ---

const PRESETS = {
  "big-band": [
    "Alto Sax", "Alto Sax", "Tenor Sax", "Tenor Sax", "Baritone Sax",
    "Trumpet", "Trumpet", "Trumpet", "Trumpet",
    "Trombone", "Trombone", "Trombone", "Bass Trombone",
    "Piano", "Guitar", "Bass", "Drums",
  ],
  "small-combo": ["Trumpet", "Tenor Sax", "Piano", "Bass", "Drums"],
  "string-quartet": ["Violin", "Violin", "Viola", "Cello"],
};

// --- Utility ---

function showError(msg) {
  $("#error-text").textContent = msg;
  errorBanner.classList.remove("hidden");
  setTimeout(() => errorBanner.classList.add("hidden"), 8000);
}

function showSection(section) {
  [uploadSection, tracksSection, progressSection, resultsSection].forEach(
    (s) => s.classList.add("hidden")
  );
  section.classList.remove("hidden");
}

function fileExtIcon(name) {
  if (name.endsWith(".pdf")) return "📄";
  if (name.endsWith(".ly")) return "🎼";
  if (name.endsWith(".zip")) return "📦";
  if (name.endsWith(".mid") || name.endsWith(".midi")) return "🎵";
  if (name.endsWith(".musicxml")) return "📋";
  return "📁";
}

// --- API Key Management ---

async function checkApiKey() {
  try {
    const hasKey = await invoke("has_api_key");
    if (!hasKey) {
      noKeyOverlay.classList.remove("hidden");
    }
  } catch (e) {
    console.warn("Keychain check failed:", e);
    // Don't block — user can still set key via settings
  }
}

async function saveApiKey(key, statusEl) {
  if (!key || !key.startsWith("sk-ant-")) {
    statusEl.textContent = "Key must start with sk-ant-";
    statusEl.className = "status-text error";
    return false;
  }
  try {
    await invoke("save_api_key", { key });
    statusEl.textContent = "Key saved securely";
    statusEl.className = "status-text success";
    return true;
  } catch (e) {
    statusEl.textContent = `Failed to save: ${e}`;
    statusEl.className = "status-text error";
    return false;
  }
}

// Settings modal
$("#settings-btn").addEventListener("click", async () => {
  settingsModal.classList.remove("hidden");
  try {
    const hasKey = await invoke("has_api_key");
    if (hasKey) {
      $("#api-key-input").value = "";
      $("#api-key-input").placeholder = "••••••••  (key stored in keychain)";
      $("#key-status").textContent = "API key is configured";
      $("#key-status").className = "status-text success";
    }
  } catch (e) {
    // Ignore
  }
});

$("#close-settings-btn").addEventListener("click", () => {
  settingsModal.classList.add("hidden");
});

$("#save-key-btn").addEventListener("click", async () => {
  const key = $("#api-key-input").value.trim();
  await saveApiKey(key, $("#key-status"));
});

$("#delete-key-btn").addEventListener("click", async () => {
  try {
    await invoke("delete_api_key");
    $("#api-key-input").value = "";
    $("#key-status").textContent = "Key removed";
    $("#key-status").className = "status-text";
  } catch (e) {
    showError(`Failed to delete key: ${e}`);
  }
});

$("#toggle-key-vis").addEventListener("click", () => {
  const input = $("#api-key-input");
  input.type = input.type === "password" ? "text" : "password";
});

// First-launch overlay
$("#overlay-save-btn").addEventListener("click", async () => {
  const key = $("#overlay-api-key").value.trim();
  const ok = await saveApiKey(key, $("#overlay-status"));
  if (ok) {
    setTimeout(() => noKeyOverlay.classList.add("hidden"), 600);
  }
});

// Open Anthropic console links
for (const link of $$("#platform-link, #overlay-platform-link")) {
  link.addEventListener("click", (e) => {
    e.preventDefault();
    shellOpen("https://console.anthropic.com/settings/keys");
  });
}

// Close modal on backdrop click
settingsModal.addEventListener("click", (e) => {
  if (e.target === settingsModal) settingsModal.classList.add("hidden");
});

// Dismiss error
$("#dismiss-error").addEventListener("click", () => {
  errorBanner.classList.add("hidden");
});

// --- MIDI Upload ---

dropZone.addEventListener("click", () => fileInput.click());

dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("drag-over");
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("drag-over");
});

dropZone.addEventListener("drop", async (e) => {
  e.preventDefault();
  dropZone.classList.remove("drag-over");

  const files = e.dataTransfer?.files;
  if (files && files.length > 0) {
    const file = files[0];
    if (file.name.match(/\.(mid|midi)$/i)) {
      // In Tauri, dropped files give us the path
      const path = file.path || file.name;
      await loadMidi(path);
    } else {
      showError("Please drop a MIDI file (.mid or .midi)");
    }
  }
});

fileInput.addEventListener("change", async () => {
  const file = fileInput.files?.[0];
  if (file) {
    await loadMidi(file.path || file.name);
  }
});

// Also support the dialog picker
dropZone.addEventListener("dblclick", async () => {
  try {
    const selected = await dialogOpen({
      filters: [{ name: "MIDI Files", extensions: ["mid", "midi"] }],
      multiple: false,
    });
    if (selected) {
      await loadMidi(selected);
    }
  } catch (e) {
    // User cancelled
  }
});

async function loadMidi(path) {
  try {
    const tracks = await invoke("analyze_midi", { path });
    currentMidiPath = path;
    currentTracks = tracks;
    renderTrackEditor(tracks);
    showSection(tracksSection);

    const filename = path.split("/").pop().split("\\").pop();
    $("#midi-filename").textContent = filename;
  } catch (e) {
    showError(`Failed to analyze MIDI: ${e}`);
  }
}

// --- Track Editor ---

function renderTrackEditor(tracks) {
  const list = $("#tracks-list");
  list.innerHTML = "";

  tracks.forEach((track, i) => {
    const row = document.createElement("div");
    row.className = "track-row";
    row.innerHTML = `
      <span class="track-idx">${track.index}</span>
      <span class="track-name">${escapeHtml(track.name)}</span>
      <select data-track-index="${track.index}">
        ${INSTRUMENTS.map(
          (inst) =>
            `<option value="${inst}" ${inst === track.instrument_guess ? "selected" : ""}>${inst}</option>`
        ).join("")}
        <option value="__custom">Other...</option>
      </select>
      <span class="note-count">${track.note_count} notes</span>
    `;
    list.appendChild(row);
  });
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Preset selector
$("#preset-select").addEventListener("change", (e) => {
  const preset = PRESETS[e.target.value];
  if (!preset) return;

  const selects = $$("#tracks-list select");
  selects.forEach((sel, i) => {
    if (i < preset.length) {
      sel.value = preset[i];
    }
  });
});

// Change file
$("#change-file-btn").addEventListener("click", () => {
  currentMidiPath = null;
  currentTracks = [];
  fileInput.value = "";
  showSection(uploadSection);
});

// --- Generation ---

$("#generate-btn").addEventListener("click", async () => {
  if (!currentMidiPath) {
    showError("No MIDI file loaded");
    return;
  }

  // Check API key first
  try {
    const hasKey = await invoke("has_api_key");
    if (!hasKey) {
      noKeyOverlay.classList.remove("hidden");
      return;
    }
  } catch (e) {
    // Continue anyway
  }

  // Build labels map from track editor
  const labels = {};
  for (const sel of $$("#tracks-list select")) {
    const idx = sel.dataset.trackIndex;
    labels[idx] = sel.value;
  }

  const hints = $("#hints-input").value.trim() || null;

  showSection(progressSection);

  try {
    const result = await invoke("generate", {
      midiPath: currentMidiPath,
      labels,
      hints,
    });

    if (result.success) {
      currentOutputDir = result.output_dir;
      await showResults(result);
    } else {
      showError(result.error || "Generation failed");
      showSection(tracksSection);
    }
  } catch (e) {
    showError(`Generation error: ${e}`);
    showSection(tracksSection);
  }
});

// Listen for progress events from the backend
listen("generation-progress", (event) => {
  const { stage, detail, percent } = event.payload;
  $("#progress-bar").style.width = `${percent}%`;
  $("#progress-stage").textContent = stage;
  $("#progress-detail").textContent = detail;
});

// --- Results ---

async function showResults(result) {
  showSection(resultsSection);

  // Build file list
  const fileList = $("#file-list");
  fileList.innerHTML = "";

  const allFiles = [];
  if (result.output_dir) {
    try {
      const files = await invoke("get_output_files", {
        outputDir: result.output_dir,
      });
      allFiles.push(...files);
    } catch (e) {
      console.warn("Failed to list output files:", e);
    }
  }

  for (const filePath of allFiles) {
    const name = filePath.split("/").pop().split("\\").pop();
    const item = document.createElement("div");
    item.className = "file-item";
    item.innerHTML = `
      <span class="file-icon">${fileExtIcon(name)}</span>
      <span class="file-name">${escapeHtml(name)}</span>
    `;
    item.addEventListener("click", () => {
      if (name.endsWith(".pdf")) {
        previewPdf(filePath);
      }
    });
    fileList.appendChild(item);
  }

  // Build PDF tabs
  const pdfTabs = $("#pdf-tabs");
  pdfTabs.innerHTML = "";

  const pdfFiles = result.pdf_paths || [];
  for (const pdfPath of pdfFiles) {
    const name = pdfPath.split("/").pop().split("\\").pop();
    const tab = document.createElement("button");
    tab.className = "pdf-tab";
    tab.textContent = name.replace(".pdf", "");
    tab.addEventListener("click", () => {
      for (const t of $$(".pdf-tab")) t.classList.remove("active");
      tab.classList.add("active");
      previewPdf(pdfPath);
    });
    pdfTabs.appendChild(tab);
  }

  // Auto-preview first PDF (score)
  if (pdfFiles.length > 0) {
    pdfTabs.firstChild?.classList.add("active");
    previewPdf(pdfFiles[0]);
  }

  // Download ZIP button
  const zipBtn = $("#download-zip-btn");
  if (result.zip_path) {
    zipBtn.classList.remove("hidden");
    zipBtn.onclick = async () => {
      try {
        const dest = await dialogSave({
          defaultPath: result.zip_path.split("/").pop(),
          filters: [{ name: "ZIP Archive", extensions: ["zip"] }],
        });
        if (dest) {
          // Copy ZIP to chosen location
          // For now, the ZIP is already in output_dir
          showError("ZIP is available at: " + result.zip_path);
        }
      } catch (e) {
        showError(`Save failed: ${e}`);
      }
    };
  } else {
    zipBtn.classList.add("hidden");
  }
}

async function previewPdf(path) {
  const viewer = $("#pdf-viewer");
  try {
    const base64 = await invoke("read_pdf_base64", { path });
    viewer.innerHTML = `<embed src="data:application/pdf;base64,${base64}" type="application/pdf" />`;
  } catch (e) {
    viewer.innerHTML = `<p class="placeholder-text">Failed to load PDF: ${e}</p>`;
  }
}

// New job
$("#new-job-btn").addEventListener("click", () => {
  currentMidiPath = null;
  currentTracks = [];
  currentOutputDir = null;
  fileInput.value = "";
  $("#hints-input").value = "";
  showSection(uploadSection);
});

// --- Init ---

document.addEventListener("DOMContentLoaded", () => {
  checkApiKey();
});
