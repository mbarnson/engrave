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
let currentLyPath = null;
let currentInstrumentLabels = [];

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
const noAuthOverlay = $("#no-auth-overlay");
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

// --- Claude Code Auth Check ---

async function checkClaudeAuth() {
  try {
    const isAuthed = await invoke("check_claude_auth");
    if (!isAuthed) {
      noAuthOverlay.classList.remove("hidden");
    }
  } catch (e) {
    console.warn("Claude auth check failed:", e);
    // Don't block — may work if claude is available at generation time
  }
}

// Settings modal
$("#settings-btn").addEventListener("click", async () => {
  settingsModal.classList.remove("hidden");
  try {
    const isAuthed = await invoke("check_claude_auth");
    if (isAuthed) {
      $("#auth-status").textContent = "Claude Code is authenticated";
      $("#auth-status").className = "status-text success";
    } else {
      $("#auth-status").textContent = "Claude Code is not set up";
      $("#auth-status").className = "status-text error";
    }
  } catch (e) {
    // Ignore
  }
});

$("#close-settings-btn").addEventListener("click", () => {
  settingsModal.classList.add("hidden");
});

$("#recheck-auth-btn").addEventListener("click", async () => {
  const statusEl = $("#auth-status");
  statusEl.textContent = "Checking...";
  statusEl.className = "status-text";
  try {
    const isAuthed = await invoke("check_claude_auth");
    if (isAuthed) {
      statusEl.textContent = "Claude Code is authenticated";
      statusEl.className = "status-text success";
    } else {
      statusEl.textContent = "Not authenticated — run 'claude login' in your terminal";
      statusEl.className = "status-text error";
    }
  } catch (e) {
    statusEl.textContent = `Check failed: ${e}`;
    statusEl.className = "status-text error";
  }
});

// First-launch overlay
$("#overlay-recheck-btn").addEventListener("click", async () => {
  const statusEl = $("#overlay-status");
  statusEl.textContent = "Checking...";
  try {
    const isAuthed = await invoke("check_claude_auth");
    if (isAuthed) {
      statusEl.textContent = "Authenticated!";
      statusEl.className = "status-text success";
      setTimeout(() => noAuthOverlay.classList.add("hidden"), 600);
    } else {
      statusEl.textContent = "Not authenticated yet — run 'claude login' first";
      statusEl.className = "status-text error";
    }
  } catch (e) {
    statusEl.textContent = `Check failed: ${e}`;
    statusEl.className = "status-text error";
  }
});

// Close modal on backdrop click
settingsModal.addEventListener("click", (e) => {
  if (e.target === settingsModal) settingsModal.classList.add("hidden");
});

// Dismiss error
$("#dismiss-error").addEventListener("click", () => {
  errorBanner.classList.add("hidden");
});

// --- MIDI Upload ---

// Click the drop zone to open a file dialog (Tauri dialog returns full paths)
dropZone.addEventListener("click", async () => {
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

// Tauri v2 drag-drop: provides full file paths (browser dataTransfer does not)
listen("tauri://drag-over", () => {
  dropZone.classList.add("drag-over");
});

listen("tauri://drag-leave", () => {
  dropZone.classList.remove("drag-over");
});

listen("tauri://drag-drop", async (event) => {
  dropZone.classList.remove("drag-over");
  const paths = event.payload.paths;
  if (paths && paths.length > 0) {
    const path = paths[0];
    if (path.match(/\.(mid|midi)$/i)) {
      await loadMidi(path);
    } else {
      showError("Please drop a MIDI file (.mid or .midi)");
    }
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

  // Check Claude auth first
  try {
    const isAuthed = await invoke("check_claude_auth");
    if (!isAuthed) {
      noAuthOverlay.classList.remove("hidden");
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

  // Capture instrument labels for measure fix panel
  currentInstrumentLabels = [];
  for (const sel of $$("#tracks-list select")) {
    currentInstrumentLabels.push(sel.value);
  }

  showSection(progressSection);

  try {
    const result = await invoke("generate", {
      midiPath: currentMidiPath,
      labels,
      hints,
    });

    if (result.success) {
      currentOutputDir = result.output_dir;
      // Track the .ly file path for measure fixes
      if (currentMidiPath) {
        const stem = currentMidiPath.split("/").pop().split("\\").pop().replace(/\.(mid|midi)$/i, "");
        currentLyPath = currentOutputDir + "/" + stem + ".ly";
      }
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

  // Populate measure fix instrument selector
  const fixInstrument = $("#fix-instrument");
  fixInstrument.innerHTML = "";
  for (const name of currentInstrumentLabels) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    fixInstrument.appendChild(opt);
  }
  $("#fix-status").textContent = "";

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

// --- Measure Fix ---

$("#fix-measure-btn").addEventListener("click", async () => {
  const instrument = $("#fix-instrument").value;
  const bar = parseInt($("#fix-bar").value, 10);
  const hint = $("#fix-hint").value.trim();
  const statusEl = $("#fix-status");

  if (!instrument) {
    statusEl.textContent = "Select an instrument";
    statusEl.className = "status-text error";
    return;
  }
  if (!bar || bar < 1) {
    statusEl.textContent = "Enter a valid bar number";
    statusEl.className = "status-text error";
    return;
  }
  if (!hint) {
    statusEl.textContent = "Describe what needs fixing";
    statusEl.className = "status-text error";
    return;
  }
  if (!currentLyPath || !currentOutputDir) {
    statusEl.textContent = "No generated output to fix";
    statusEl.className = "status-text error";
    return;
  }

  statusEl.textContent = "Fixing measure...";
  statusEl.className = "status-text";
  $("#fix-measure-btn").disabled = true;

  try {
    const result = await invoke("fix_measure", {
      lyPath: currentLyPath,
      instrument,
      bar,
      hint,
      outputDir: currentOutputDir,
    });

    if (result.success) {
      statusEl.textContent = `Fixed bar ${bar} for ${instrument}`;
      statusEl.className = "status-text success";

      // Refresh PDF preview with updated files
      if (result.pdf_paths && result.pdf_paths.length > 0) {
        const pdfTabs = $("#pdf-tabs");
        pdfTabs.innerHTML = "";
        for (const pdfPath of result.pdf_paths) {
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
        // Preview first PDF
        pdfTabs.firstChild?.classList.add("active");
        previewPdf(result.pdf_paths[0]);
      }
    } else {
      statusEl.textContent = result.error || "Fix failed";
      statusEl.className = "status-text error";
    }
  } catch (e) {
    statusEl.textContent = `Error: ${e}`;
    statusEl.className = "status-text error";
  } finally {
    $("#fix-measure-btn").disabled = false;
  }
});

// New job
$("#new-job-btn").addEventListener("click", () => {
  currentMidiPath = null;
  currentTracks = [];
  currentOutputDir = null;
  currentLyPath = null;
  currentInstrumentLabels = [];
  fileInput.value = "";
  $("#hints-input").value = "";
  showSection(uploadSection);
});

// --- Init ---

document.addEventListener("DOMContentLoaded", () => {
  checkClaudeAuth();
});
