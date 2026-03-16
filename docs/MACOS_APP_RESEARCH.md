# Research: macOS Drag-Installer and Native UI for Engrave

Research bead: en-11j | Date: 2026-03-16

## Executive Summary

**Two viable approaches, depending on team priorities:**

1. **Quick path (Phase 1)**: pywebview + PyInstaller — pure Python, wraps
   the existing FastAPI/htmx UI in a native macOS window with zero frontend
   changes. Fastest to ship but lacks built-in auto-update and code signing tooling.

2. **Full path (Phase 2)**: Tauri v2 shell + Python sidecar — small binary
   (~5-10 MB shell vs ~150 MB for Electron), native macOS integration (uses
   system WebKit), built-in code signing, notarization, auto-update, and
   sidecar support. **Caveat**: Known signing bug with `externalBin` sidecars
   (GitHub #11992) requires workarounds.

Both approaches serve the existing FastAPI/htmx web UI inside a native WebView.
Start with pywebview for rapid validation, graduate to Tauri for production
distribution.

---

## 1. Dependency Bundling Strategy

### The Challenge

Engrave has substantial dependencies that must ship inside the .app bundle:

| Component | Approx. Size | Notes |
|-----------|-------------|-------|
| Python 3.12 runtime | ~50 MB | Standalone interpreter |
| Engrave + Python deps | ~200-400 MB | chromadb, sentence-transformers, audio-separator are heavy |
| LilyPond | ~40 MB | Binary + fonts + scheme libraries |
| ffmpeg | ~30 MB | Static build |
| ML models (optional) | 1-8 GB | Embedding models, local LLM |
| **Total (no local LLM)** | **~320-520 MB** | |

### Recommended: Python Standalone Builds + Vendored Binaries

**Python runtime**: Use [python-build-standalone](https://github.com/indygreg/python-build-standalone)
(Gregory Szorc's project) to get a relocatable, self-contained Python interpreter.
This is what tools like `uv`, Rye, and Briefcase use under the hood. Available
for both arm64 and x86_64 macOS.

**Python packages**: Pre-install all pip dependencies into a vendored `site-packages`
directory within the .app bundle. Use `uv pip install --target` for reproducible
installs. The `uv.lock` already exists in the project.

**LilyPond**: Bundle the macOS binary distribution directly. LilyPond ships
self-contained archives for macOS arm64 and x86_64 from lilypond.org.
Place inside `Engrave.app/Contents/Resources/lilypond/`.

**ffmpeg**: Use a static ffmpeg build (e.g., from evermeet.cx/ffmpeg or
built via Homebrew). Place inside `Engrave.app/Contents/Resources/bin/`.

**Path resolution at runtime**: The Python code needs to find LilyPond and
ffmpeg. Two approaches:
1. Set `PATH` environment variable before spawning subprocesses
2. Add a `BundlePaths` config that auto-detects when running from .app bundle
   (check for `__CFBUNDLE` env var or `sys._MEIPASS`-style detection)

### Size Optimization

- **Exclude CUDA/ROCm from torch**: Only ship CPU or MPS (Metal) backends.
  `pip install torch --extra-index-url` with macOS-specific wheels.
- **ONNX Runtime instead of PyTorch for embeddings**: sentence-transformers
  supports ONNX backend, which is ~200 MB vs ~1.5 GB for full PyTorch.
  ChromaDB supports custom embedding functions, so the ONNX backend can
  replace the default PyTorch one. This is the single highest-impact
  size optimization.
- **Lazy model downloads**: Don't bundle embedding models. Download
  `nomic-embed-text` on first launch (~270 MB) to `~/Library/Application Support/Engrave/`.
- **audio-separator models**: These are large (~100 MB each). Download on first use.
- **Strip .pyc, __pycache__, test files**: Can save 10-20% on Python packages.
- **Clean venv**: One developer went from 911 MB to 83 MB by switching from
  system Python to a minimal venv with only needed packages.

---

## 2. UI Framework Comparison

### Option A: Tauri v2 (RECOMMENDED)

**Architecture**: Rust core + system WebView (WKWebView on macOS) + web frontend.

| Aspect | Detail |
|--------|--------|
| Binary size | ~5-10 MB (app shell only; uses system WebKit) |
| macOS integration | Native window chrome, menu bar, dock icon, notifications |
| Sidecar support | First-class: `tauri::api::process::Command::sidecar()` bundles and manages child processes |
| IPC | Rust ↔ JS via Tauri commands; JS ↔ Python via HTTP or stdin/stdout |
| Code signing | Built-in via `tauri-cli`: signs, notarizes, creates .dmg |
| Auto-update | Built-in updater plugin (checks endpoint, downloads, installs) |
| Drag-and-drop | Native file drop events forwarded to web frontend |
| Maturity | v2 stable since 2024, strong ecosystem |

**How it works with Engrave**:
1. Tauri app launches → starts Python sidecar (uvicorn serving FastAPI)
2. WebView loads `http://localhost:{port}` (the existing htmx UI)
3. File drag-and-drop handled by Tauri's native file drop → forwarded to Python
4. Pipeline progress shown via existing htmx polling or upgraded to WebSocket

**Sidecar bundling**: Tauri's sidecar feature bundles an executable into the
app and manages its lifecycle. For Python, we'd bundle a standalone Python
interpreter plus the engrave package. The sidecar config in `tauri.conf.json`:

```json
{
  "bundle": {
    "externalBin": ["binaries/python-engrave"]
  }
}
```

Alternatively, use PyInstaller/Nuitka to create a single `engrave-server`
binary that Tauri launches as sidecar.

**Known issue**: GitHub #11992 — macOS code signing and notarization can fail
when using `externalBin` sidecars. The Tauri bundler does not always properly
sign external binaries. Workaround: pre-sign the PyInstaller binary before
running `tauri build`. This is an active area of bug fixes as of early 2026.

**Pros**: Tiny shell, native feel, batteries-included (signing, updates, DMG).
**Cons**: Requires Rust toolchain for building the shell. Sidecar + Python
adds complexity vs a pure-Python solution. Known signing issue with sidecars.

### Option B: Electron

| Aspect | Detail |
|--------|--------|
| Binary size | ~150-200 MB (ships entire Chromium) |
| macOS integration | Good but not native (custom title bar, etc.) |
| IPC | Node.js main process → Python child process via HTTP/stdio |
| Code signing | electron-builder handles signing + notarization |
| Auto-update | electron-updater (Squirrel-based) |
| Maturity | Very mature, huge ecosystem |

**How it works with Engrave**: Similar to Tauri — Electron spawns Python as
a child process, loads the web UI in its Chromium window.

**Pros**: Mature, huge ecosystem, easier to find developers.
**Cons**: Massive binary size (Chromium alone is ~120 MB), higher RAM usage
(~100-200 MB baseline), not native-feeling on macOS.

### Option C: PyWebView (RECOMMENDED FOR PHASE 1)

| Aspect | Detail |
|--------|--------|
| Binary size | ~0 MB (uses system WebKit via pyobjc) |
| macOS integration | Native Cocoa window, basic menu/dock control |
| IPC | Python controls the window directly; JS ↔ Python bridge built-in |
| Drag-and-drop | Built-in with `pywebviewFullPath` giving absolute file paths |
| Code signing | Manual (no built-in tooling) |
| Auto-update | Manual implementation required |
| Maturity | Moderate, active development (v5.0+ in 2024) |

**How it works**: Pure Python — start uvicorn in a daemon thread, then
`webview.create_window(url="http://localhost:{port}")`. The existing
FastAPI/htmx UI runs unchanged.

```python
import threading, webview
from engrave.web.app import create_app
import uvicorn

app = create_app()
thread = threading.Thread(target=uvicorn.run, args=(app,), kwargs={"port": 8919}, daemon=True)
thread.start()
webview.create_window("Engrave", "http://localhost:8919")
webview.start()
```

**Pros**: Zero additional binary size, ~30 lines of glue code, stays in Python,
drag-and-drop with full file paths built-in, PDF rendering via WKWebView.
**Cons**: Limited native menu bar (custom menus require PyObjC).
Code signing / DMG creation must be handled separately (use PyInstaller +
create-dmg). No built-in auto-update.

### Option D: SwiftUI + WKWebView

| Aspect | Detail |
|--------|--------|
| Binary size | ~2 MB |
| macOS integration | Perfect (it IS native) |
| IPC | Swift manages Python process; WKWebView loads web UI |
| Code signing | Xcode handles everything |
| Auto-update | Sparkle framework (standard for native Mac apps) |
| Maturity | Apple-supported, but hybrid Swift+Python is unusual |

**How it works**: Swift app with a WKWebView that loads the FastAPI UI.
Swift code manages the Python backend process lifecycle.

**Pros**: Smallest binary, most native feel, best macOS integration.
**Cons**: Requires Swift/Xcode expertise, two-language codebase, harder CI/CD
setup for a primarily-Python team.

### Recommendation Matrix

| Criterion | Tauri | Electron | PyWebView | SwiftUI |
|-----------|-------|----------|-----------|---------|
| Binary size | A | D | A+ | A+ |
| macOS native feel | A | B- | B | A+ |
| Bundling tooling | A | A | C | B |
| Code signing | B+ (*) | A | C | A+ |
| Auto-update | A | A | F | A |
| Dev complexity | B | B | A+ | C |
| Python integration | B | B | A+ | C |
| Time to first .app | C | C | A+ | C |
| **Overall** | **A-** | **B** | **A- (Phase 1)** | **B+** |

(*) Tauri code signing has a known bug with externalBin sidecars (#11992).

**Verdict**: **Phase 1 — pywebview + PyInstaller** for rapid validation.
~30 lines of Python glue wraps the existing FastAPI/htmx UI in a native
macOS window. PyInstaller bundles everything into a .app. create-dmg
produces the installer. This proves the concept in days, not weeks.

**Phase 2 — Tauri v2** for production distribution when you need auto-update,
polished signing/notarization, and a smaller app shell. The sidecar signing
bug should be resolved by then.

SwiftUI would be ideal for a Swift-native team but adds language complexity.
Electron is overkill for wrapping an existing web UI.

---

## 3. LLM Backend Strategy

### Current Architecture

Engrave already has a flexible LLM backend via LiteLLM + role-based routing:
- **Local**: LM Studio (`lm_studio/<model>`) or vllm-mlx
- **Cloud**: Anthropic (`anthropic/claude-*`), OpenAI (`openai/gpt-*`)
- **Remote GPU**: RunPod (`hosted_vllm/<model>`)

The `engrave.toml` config + `.env` for API keys is clean and extensible.

### Recommended: Hybrid (Cloud Default + Optional Local)

**Default experience**: Cloud API (Anthropic Claude or OpenAI).
- User provides API key in Settings UI on first launch
- Stored securely in macOS Keychain (via `keyring` Python library)
- Works immediately, no model downloads needed
- Best quality for music generation tasks

**Optional local**: Detect Ollama or LM Studio on `localhost:11434`/`localhost:1234`.
- If running, show "Local model detected" in UI with option to use it
- No model bundling in the .app — external model server approach
- The optional `[mlx]` extra in pyproject.toml already supports vllm-mlx

**Local model tiers** (already validated in the codebase via vllm-mlx):

| Model | Active Params | 4-bit Size | Min RAM | Quality |
|-------|---------------|------------|---------|---------|
| Qwen3-Coder-30B-A3B (current) | 3B | 17.2 GB | 24 GB | Best local option for LilyPond |
| Qwen3-Coder-14B | 14B | ~8 GB | 16 GB | Good middle ground |
| Qwen3-4B | 0.6B | 2.3 GB | 8 GB | Lightweight fallback |

**Why NOT bundle a local model**:
1. **Size**: Even the smallest viable model is 2.3 GB — makes the app download impractical
2. **Hardware variance**: 8 GB Macs can't run the 30B model; different users need different models
3. **Quality**: Local models underperform Claude/GPT-4 for specialized LilyPond generation
4. **Complexity**: Managing model lifecycle, GPU memory, inference crashes
5. **Staleness**: Models update frequently; bundling locks you to a version

**Implementation plan**:
```
Settings UI:
├── Cloud API (default)
│   ├── Anthropic (API key in Keychain)
│   ├── OpenAI (API key in Keychain)
│   └── Custom endpoint (URL + key)
└── Local Server (auto-detected)
    ├── Ollama (localhost:11434)
    ├── LM Studio (localhost:1234)
    └── Custom (user-specified URL)
```

### API Key Security in Desktop App

- **macOS Keychain**: Use `keyring` library to store API keys in the system
  keychain. Secure, survives app updates, follows macOS conventions.
- **Never store in plaintext files** within the .app bundle.
- **First-launch onboarding**: "Enter your API key" dialog with link to
  provider's key creation page.
- **Key validation**: Test the key with a trivial completion before saving.

---

## 4. Code Signing and Notarization

### Requirements

Since macOS Catalina (10.15), all distributed software must be:
1. **Signed** with a Developer ID certificate
2. **Notarized** by Apple (automated malware scan)
3. **Stapled** (attach notarization ticket to the binary)

Without this, Gatekeeper blocks the app with "cannot be opened because the
developer cannot be verified."

**macOS 15 Sequoia change**: The Control-click override to bypass Gatekeeper
was removed. Users must now navigate to System Settings > Privacy & Security,
find the app, click "Open Anyway", and enter admin credentials. This makes
proper signing and notarization non-optional in practice — users will abandon
an unsigned app.

### What's Needed

| Requirement | Cost | Notes |
|-------------|------|-------|
| Apple Developer Program | $99/year | Required for Developer ID certificate |
| Developer ID Application cert | Free (with program) | For signing .app bundles |
| Developer ID Installer cert | Free (with program) | For signing .pkg installers |
| Xcode Command Line Tools | Free | `codesign`, `notarytool`, `stapler` |

### Signing Bundled Binaries

**Critical gotcha**: Every binary inside the .app must be individually signed.
This includes Python, LilyPond, ffmpeg, and all `.so`/`.dylib` files.

**Important**: Do NOT use `codesign --deep`. Apple explicitly discourages it
as unreliable. Sign from inside-out instead:

```bash
# 1. Sign all .so/.dylib files first
find Engrave.app -name "*.dylib" -o -name "*.so" | while read f; do
  codesign --force --options runtime --entitlements entitlements.plist \
    --sign "Developer ID Application: ..." --timestamp "$f"
done

# 2. Sign embedded binaries (python3, ffmpeg, lilypond)
codesign --force --options runtime --entitlements entitlements.plist \
  --sign "Developer ID Application: ..." --timestamp \
  Engrave.app/Contents/Resources/bin/python3

# 3. Sign the app bundle LAST
codesign --force --options runtime --entitlements entitlements.plist \
  --sign "Developer ID Application: ..." --timestamp Engrave.app
```

### Hardened Runtime Entitlements

Since Engrave spawns subprocesses (Python, LilyPond, ffmpeg), the following
entitlements are needed:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.cs.allow-unsigned-mach-o</key>
    <true/>
    <key>com.apple.security.cs.disable-library-validation</key>
    <true/>
    <key>com.apple.security.cs.allow-dyld-environment-variables</key>
    <true/>
    <key>com.apple.security.network.client</key>
    <true/>
    <key>com.apple.security.files.user-selected.read-write</key>
    <true/>
</dict>
</plist>
```

### Notarization Flow

```bash
# 1. Create ZIP for notarization
ditto -c -k --keepParent Engrave.app Engrave.zip

# 2. Submit for notarization
xcrun notarytool submit Engrave.zip \
  --apple-id "dev@example.com" \
  --team-id "TEAMID" \
  --password "@keychain:AC_PASSWORD" \
  --wait

# 3. Staple the ticket
xcrun stapler staple Engrave.app
```

**Tauri handles all of this automatically** via `tauri-cli build` when
configured with signing credentials in the build config.

### Universal Binaries (arm64 + x86_64)

Two options:
1. **Universal binary (.app)**: Combine arm64 and x86_64 into one using `lipo`.
   Doubles the binary size but simplifies distribution.
2. **Separate downloads**: Offer arm64 and x86_64 DMGs separately.
   Recommended to keep download size manageable given the already-large bundle.

For Python and native extensions, universal binaries can be tricky.
**Recommended**: Ship arm64-only initially (Apple Silicon is now dominant),
with x86_64 as a separate download if needed.

---

## 5. Auto-Update Mechanism

### Option A: Tauri Updater (Recommended if using Tauri)

Tauri's built-in updater plugin:
- Checks a JSON endpoint for new versions
- Downloads differential updates when possible
- Verifies signatures before applying
- Restarts the app after update
- Config in `tauri.conf.json`:

```json
{
  "plugins": {
    "updater": {
      "endpoints": ["https://releases.engrave.app/{{target}}/{{arch}}/{{current_version}}"],
      "pubkey": "..."
    }
  }
}
```

Update endpoint can be a static JSON file on S3/Cloudflare or GitHub Releases.

### Option B: Sparkle (Standard for native Mac apps)

- The de facto standard for non-App-Store Mac app updates
- Mature, well-tested, handles code signing verification
- Requires an appcast XML feed (can be hosted on GitHub Pages)
- Good if using SwiftUI shell

### Option C: Custom GitHub Releases

- Simplest: check GitHub Releases API for new versions
- Download the new DMG, prompt user to install
- No automatic in-place update (user re-drags to Applications)
- Acceptable for v1, upgrade to Tauri/Sparkle later

### Recommendation

Use **Tauri's built-in updater** — it's the simplest path with the recommended
UI framework and handles signature verification automatically.

---

## 6. UX Flow Design

### Primary Flow: MIDI/Audio → Sheet Music

```
┌─────────────────────────────────────────────┐
│  Engrave                              ─ □ ×  │
├─────────────────────────────────────────────┤
│                                             │
│    ┌───────────────────────────────────┐    │
│    │                                   │    │
│    │     Drop MIDI or audio file       │    │
│    │          here                     │    │
│    │                                   │    │
│    │     (.mid .wav .mp3 .flac)        │    │
│    └───────────────────────────────────┘    │
│                                             │
│    Hints: [Big band, swing feel        ]    │
│                                             │
│    [      Engrave      ]                    │
│                                             │
└─────────────────────────────────────────────┘
```

### Processing State

```
┌─────────────────────────────────────────────┐
│  Engrave                              ─ □ ×  │
├─────────────────────────────────────────────┤
│                                             │
│    Processing: my-song.mid                  │
│                                             │
│    ████████████░░░░░░░░░  60%  (2m 34s)    │
│                                             │
│    ✓ Audio separation                       │
│    ✓ MIDI transcription                     │
│    ▸ LilyPond generation (section 3/5)      │
│    ○ Compilation                            │
│    ○ PDF rendering                          │
│                                             │
└─────────────────────────────────────────────┘
```

### Result State

```
┌─────────────────────────────────────────────┐
│  Engrave                              ─ □ ×  │
├─────────────────────────────────────────────┤
│                                             │
│    ✓ Complete! my-song                      │
│                                             │
│    ┌─────────────────────────────────┐      │
│    │                                 │      │
│    │    [PDF Preview of Score]       │      │
│    │                                 │      │
│    │    Page 1 of 4                  │      │
│    │                                 │      │
│    └─────────────────────────────────┘      │
│                                             │
│    Parts: Trumpet, Alto Sax, Bass, Drums    │
│                                             │
│    [Download ZIP]  [Open in Finder]         │
│                                             │
└─────────────────────────────────────────────┘
```

### Settings/Preferences

```
┌─────────────────────────────────────────────┐
│  Engrave › Settings                   ─ □ ×  │
├─────────────────────────────────────────────┤
│                                             │
│  LLM Provider                               │
│  ┌─────────────────────────────────────┐    │
│  │ ○ Anthropic Claude  [API Key: ••••] │    │
│  │ ○ OpenAI GPT-4      [API Key: ••••] │    │
│  │ ○ Local Server       [Auto-detected]│    │
│  │   └ Ollama at localhost:11434       │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  Output                                     │
│  Default save location: [~/Music/Engrave]   │
│  Include MusicXML:      [✓]                 │
│                                             │
└─────────────────────────────────────────────┘
```

### Menu Bar Integration

```
Engrave  File  Edit  View  Help
├── About Engrave
├── Check for Updates...
├── Settings...        ⌘,
├── ─────────
└── Quit Engrave       ⌘Q

File
├── Open MIDI/Audio... ⌘O
├── Recent Files       ▸
├── ─────────
└── Export Last...     ⌘E
```

### Key UX Decisions

1. **Drag-and-drop is primary**: The drop zone is the hero element, not buried in a menu
2. **Progress is granular**: Show pipeline stages, not just a spinner
3. **PDF preview inline**: Don't force the user to open Preview.app
4. **Settings accessible but not required**: Cloud API key prompt on first launch,
   then get out of the way
5. **Recent files**: Remember last 10 engravings for quick re-export
6. **Dock badge**: Show progress percentage while processing in background

---

## 7. Implementation Roadmap

### Phase 1: pywebview PoC (days)

1. **Add pywebview wrapper** (~30 lines of glue code):
   - `pip install pywebview`
   - Launch FastAPI/uvicorn in daemon thread
   - Open native macOS window pointing at localhost
   - Test drag-and-drop (pywebview has built-in `pywebviewFullPath` support)
   - **Goal**: Validate the native window experience

2. **PyInstaller bundling**:
   - Create `engrave.spec` with `--add-binary` for LilyPond and ffmpeg
   - Build standalone .app bundle
   - Measure total bundle size, optimize with ONNX for embeddings
   - Test on clean macOS install

3. **DMG creation**:
   - Use `create-dmg` for drag-to-Applications installer
   - Basic code signing (Apple Developer account required)

### Phase 2: Web UI Enhancements (1-2 weeks)

1. **Upgrade htmx UI**:
   - Progress stages (not just "Processing..." — show pipeline steps)
   - PDF preview inline via pdf.js or WKWebView native rendering
   - Settings page: API key management (stored in macOS Keychain via `keyring`)
   - First-launch onboarding: API key prompt

2. **Local model detection**:
   - Auto-detect Ollama (localhost:11434) and LM Studio (localhost:1234)
   - Show "Local model detected" option in settings
   - Model download manager for vllm-mlx models to `~/Library/Application Support/Engrave/`

### Phase 3: Production Distribution (2-3 weeks)

**Option A: Stay with pywebview** (simpler):
   - Full inside-out code signing of all bundled binaries
   - Notarization via `notarytool`
   - Sparkle framework for auto-update
   - GitHub Actions CI/CD for automated builds

**Option B: Graduate to Tauri** (if auto-update and polish are priority):
   - Initialize Tauri v2 project with Python sidecar
   - Built-in signing, notarization, DMG, auto-update
   - Native menu bar, dock icon, progress badge
   - Wait for sidecar signing bug (#11992) resolution

### Phase 4: Polish (ongoing)

- Crash reporting (Sentry or similar)
- Universal binary support (arm64 + x86_64, or arm64-only for 2026)
- On-demand model download with progress UI
- Recent files history
- Dock badge for background processing progress

---

## 8. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Bundle size too large (>500 MB) | Poor download UX | Lazy model downloads, strip unused deps |
| Code signing breaks bundled Python .so files | App won't launch | Sign every binary individually, test on clean macOS |
| LilyPond subprocess blocked by hardened runtime | Core feature broken | Entitlements for subprocess execution |
| Tauri sidecar Python startup slow | Bad first impression | Splash screen, preload Python on login (optional) |
| API key storage insecure | Security vulnerability | Use macOS Keychain via `keyring` library |
| Auto-update fails with signed app | Users stuck on old version | Fallback to manual download link |
| audio-separator/torch too large | >1 GB bundle | Make audio input optional, download on first use |

---

## 9. Key Technical Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| UI Framework | **Tauri v2** | Small binary, native feel, built-in signing/updates |
| Python bundling | **python-build-standalone + uv** | Relocatable, reproducible, fast |
| LLM Backend | **Cloud default + local detection** | Best UX, avoids model bundling |
| API key storage | **macOS Keychain** | Secure, platform-native |
| Binary deps | **Vendored in .app/Contents/Resources** | Self-contained, no brew dependency |
| Auto-update | **Tauri updater plugin** | Built-in, handles signatures |
| Distribution | **DMG from website** (not Mac App Store) | Avoids App Store review for subprocess-heavy app |
| Architecture target | **arm64 primary**, x86_64 separate | Apple Silicon dominant, keeps downloads small |
| ML models | **Download on first use** to ~/Library/Application Support | Keeps initial download under 500 MB |
