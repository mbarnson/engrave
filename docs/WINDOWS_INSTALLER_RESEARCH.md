# Windows Installer and UI Research for Engrave

Research bead: en-o3b | Date: 2026-03-16

## Executive Summary

Engrave is a Python 3.12+ CLI/web app with heavy native dependencies (LilyPond,
audio-separator, ML models). To ship on Windows for Sam, the recommended stack is:

- **UI**: Tauri 2.x (shared codebase with macOS) with Python backend as sidecar
- **Python bundling**: Nuitka (fewer AV false positives than PyInstaller)
- **Installer**: NSIS for v1 (maximum flexibility), MSIX for Store distribution later
- **LilyPond**: Bundle the official mingw ZIP (~80 MB), invoke via subprocess with PATH override
- **Package manager**: Scoop first (easiest submission), then winget
- **Code signing**: EV certificate (~$300-560/yr) to bypass SmartScreen immediately

---

## 1. Installer Format Comparison

### NSIS (Recommended for v1)

- Free, open-source, actively maintained (v3.11, March 2025)
- Highly scriptable — full control over file placement, PATH, registry
- Tiny installer overhead (~34 KB stub)
- Can bundle LilyPond ZIP, Python runtime, and Tauri app into one installer
- Drawback: unsigned installers trigger SmartScreen; scripting language is arcane
- Best for: consumer apps where you need flexibility with bundled tools

### MSIX (Recommended for Store distribution)

- Modern Windows 10/11 standard, containerized (clean install/uninstall)
- **Avoids SmartScreen warnings entirely** when distributed via Microsoft Store
- Automatic updates built in
- Python itself is moving to MSIX distribution (Python 3.16+)
- Drawback: sandbox restrictions may complicate LilyPond invocation; requires testing
- Best for: Store distribution, corporate environments

### MSI (Not recommended unless enterprise demand)

- Enterprise standard (Group Policy deployment)
- Complex authoring via WiX Toolset
- Unnecessary overhead for a consumer music app

**Recommendation**: Start with NSIS for maximum control over bundling LilyPond and
setting up PATH. Plan MSIX as a stretch goal for Microsoft Store presence.

---

## 2. Python Bundling Tools

### Nuitka (Recommended)

- Compiles Python to C, producing native Windows executables
- **Significantly fewer antivirus false positives** than PyInstaller (native binary,
  not a self-extracting archive)
- 2-4x performance improvement from compilation
- Handles complex dependencies via YAML-based package configuration
- Requires a C compiler (MSVC from Visual Studio Build Tools, or MinGW)
- Actively maintained, ~14.4k GitHub stars

### PyInstaller (Fallback/faster iteration)

- Most popular, best out-of-box dependency detection
- **Severe AV false positive problem**: PyInstaller's shared bootloader is used by
  actual malware, causing 4-10/70+ VirusTotal detections on clean binaries
- `--onedir` mode (vs `--onefile`) reduces but doesn't eliminate false positives
- Faster iteration cycle than Nuitka (no compilation step)
- ~12.8k GitHub stars

### Others

- **cx_Freeze**: Simpler alternative, fewer features, smaller community
- **Briefcase (BeeWare)**: Produces MSI via WiX, good if using Toga UI. Not ideal for Tauri sidecar pattern
- **PyOxidizer**: **Abandoned** — no releases since Jan 2023, do not use

**Recommendation**: Use Nuitka for production builds. Use PyInstaller during
development for faster iteration. Both produce a standalone directory that can
be wrapped by NSIS.

### Engrave-Specific Bundling Concerns

Engrave has heavy dependencies that affect bundling:

| Dependency | Size Impact | Windows Notes |
|------------|-------------|---------------|
| `audio-separator` | ~500 MB+ (ML models) | ONNX Runtime needed; models downloaded on first use |
| `sentence-transformers` | ~400 MB+ | Torch dependency; consider server-side for Windows |
| `chromadb` | ~100 MB | SQLite-based, works on Windows |
| `music21` | ~50 MB | Pure Python, no issues |
| `python-ly` | Small | Pure Python, no issues |
| `pydub` | Small | Requires ffmpeg on PATH |
| `yt-dlp` | ~15 MB | Standalone exe available for Windows |

**Total estimated bundle size**: 1-2 GB with all ML models included. Consider:
1. Ship without ML models; download on first use (like audio-separator already does)
2. Offer a "lite" install (~200 MB) that connects to a server for ML-heavy tasks
3. Use ONNX Runtime instead of full PyTorch where possible

---

## 3. UI Framework: Tauri vs Electron

### Tauri 2.x (Recommended)

| Aspect | Detail |
|--------|--------|
| App size | 3-10 MB (uses system WebView2 on Windows) |
| RAM usage | ~50-100 MB less than Electron |
| Startup | <0.5s |
| Python integration | First-class **sidecar** support (`externalBin` in tauri.conf.json) |
| WebView on Windows | Edge WebView2 (ships with Windows 11, auto-installs on 10) |
| Cross-platform | Same codebase for Windows + macOS (companion bead en-11j) |

**Sidecar pattern for Engrave**:
```
engrave-app/
├── tauri-frontend/          # Tauri + HTML/CSS/JS (or React/Svelte)
├── engrave-backend/         # Nuitka-compiled Python binary
│   ├── engrave-server.exe   # FastAPI server (from engrave.web.app)
│   └── ...                  # Bundled Python deps
├── lilypond/                # Extracted LilyPond mingw ZIP
│   └── bin/lilypond.exe
└── installer/               # NSIS scripts
```

Tauri launches `engrave-server.exe` as a sidecar on startup, communicates via
`http://localhost:PORT`. The existing `engrave.web.app` FastAPI module is already
a perfect fit — it has file upload, job status polling, and download endpoints.

### Electron (Not recommended)

- 50+ MB base size (bundles Chromium)
- Higher RAM usage
- Same Python integration story (subprocess + HTTP)
- More mature ecosystem but unnecessary overhead
- Only advantage: pixel-perfect cross-platform rendering

### Shared UI Codebase with macOS

Both Windows and macOS (en-11j) should use Tauri 2.x:
- Same frontend code (HTML/CSS/JS or framework like Svelte/React)
- Same sidecar pattern (Python backend compiled per-platform)
- Platform-specific: installer (NSIS vs .dmg), code signing, WebView engine
- Engrave's existing `web/templates/index.html` can be the starting point

---

## 4. Windows-Specific Concerns

### SmartScreen and Code Signing

| Certificate Type | Cost/yr | SmartScreen Behavior |
|-----------------|---------|---------------------|
| None | $0 | Full warning ("Windows protected your PC") — most users won't proceed |
| OV (Organization Validation) | $226-300 | Warnings until reputation builds (weeks/months of downloads) |
| EV (Extended Validation) | $300-560 | **Immediate bypass** — no SmartScreen warning on first release |

- **Certum offers discounted certificates for open-source projects** — worth investigating
- EV certificates require a hardware token (HSM/USB key)
- Certificate lifespans capped at 1 year as of Feb 2026
- MSIX packaging via Microsoft Store avoids SmartScreen entirely

**Recommendation**: Get an EV certificate for the initial release. The cost is
justified by the trust barrier — Sam (and other Windows users) will abandon the
app if SmartScreen blocks it.

### Antivirus False Positives

- PyInstaller executables: 4-10 false positive detections on VirusTotal (70+ scanners)
- Root cause: shared bootloader with actual malware
- **Mitigations**:
  1. Use Nuitka instead (native binary, not self-extracting archive)
  2. Code sign with EV certificate
  3. Submit to major AV vendors for whitelisting (Microsoft, Avast, AVG, Kaspersky)
  4. Use `--onedir` not `--onefile` if using PyInstaller

### PATH Management

- **Do NOT modify system PATH** (requires admin, fragile)
- Engrave's Python backend should set PATH in subprocess environments:
  ```python
  env = os.environ.copy()
  env["PATH"] = str(lilypond_dir / "bin") + os.pathsep + env["PATH"]
  subprocess.run(["lilypond", ...], env=env)
  ```
- The existing `LilyPondCompiler` class would need a `lilypond_bin` config option
  that defaults to the bundled location on Windows

### UAC (User Account Control)

- **Target per-user installation** (no admin required)
- Install to `%LOCALAPPDATA%\Engrave\` (standard for per-user apps)
- Scoop's per-user model is a good reference
- Only request admin if user opts for system-wide install

---

## 5. Package Manager Distribution

### Priority Order

1. **Scoop** (target first)
   - Developer-friendly audience (musicians who code)
   - Per-user install (no admin)
   - Submission: JSON manifest PR to a "bucket" repo
   - Can create a custom bucket (`scoop bucket add engrave <url>`)
   - Easiest maintenance

2. **winget** (target second)
   - Ships with Windows 11, growing user base
   - Submission: PR to `microsoft/winget-pkgs` GitHub repo
   - Good discoverability for general Windows users

3. **Chocolatey** (target third)
   - LilyPond 2.24.4 is already a Chocolatey package (good precedent)
   - More moderation overhead
   - Enterprise-oriented audience

### Scoop Manifest Example

```json
{
    "version": "0.1.0",
    "description": "AI-powered music engraving pipeline",
    "homepage": "https://github.com/<org>/engrave",
    "license": "MIT",
    "url": "https://github.com/<org>/engrave/releases/download/v0.1.0/engrave-0.1.0-win-x64.zip",
    "hash": "<sha256>",
    "bin": "engrave.exe",
    "depends": "lilypond"
}
```

---

## 6. LilyPond on Windows

### Current State

- Latest stable: **2.24.4**, beta: 2.25.35
- Distributed as a ZIP: `lilypond-2.24.4-mingw-x86_64.zip` (~80 MB)
- 64-bit only, Windows 10+ required
- Available on Chocolatey: `choco install lilypond --version=2.24.4`
- **Supports relocation**: computes paths relative to binary location at runtime

### Bundling Strategy

1. Download official mingw ZIP at build time
2. Extract into app tree: `engrave-app/lilypond/`
3. Invoke via subprocess with modified PATH:
   ```python
   lilypond_dir = app_dir / "lilypond"
   env = os.environ.copy()
   env["PATH"] = str(lilypond_dir / "bin") + os.pathsep + env["PATH"]
   subprocess.run(["lilypond", source_file], env=env, cwd=output_dir)
   ```
4. LilyPond's relocation support means no registry entries or system PATH needed
5. Frescobaldi (the main LilyPond IDE) already bundles LilyPond this way — proven pattern

### Additional External Dependencies

| Tool | Windows Availability | Bundling Approach |
|------|---------------------|-------------------|
| LilyPond | Official mingw ZIP | Bundle in app tree |
| ffmpeg | Static Windows build available | Bundle `ffmpeg.exe` in app tree |
| FluidSynth | Windows DLL available | Bundle or make optional |
| yt-dlp | Standalone Windows exe | Bundle in app tree |

---

## 7. Recommended Architecture

```
Engrave.exe (Tauri shell)
│
├── Frontend (WebView2)
│   └── index.html + JS/CSS (from engrave/web/templates, enhanced)
│
├── Sidecar: engrave-server.exe (Nuitka-compiled Python)
│   ├── FastAPI server (engrave.web.app)
│   ├── All Python dependencies bundled
│   └── ML models downloaded on first use
│
├── lilypond/
│   └── bin/lilypond.exe (from official mingw ZIP)
│
├── ffmpeg/
│   └── ffmpeg.exe (static build)
│
└── Installed via NSIS to %LOCALAPPDATA%\Engrave\
```

### Build Pipeline

1. `nuitka --standalone src/engrave/` → `engrave-server.exe` + deps
2. Download LilyPond mingw ZIP, ffmpeg static build
3. `npm run tauri build` → Tauri app with sidecar
4. NSIS wraps everything into `Engrave-Setup-0.1.0.exe`
5. Sign with EV certificate
6. Upload to GitHub Releases + Scoop bucket

### Cross-Platform Code Sharing (with macOS bead en-11j)

| Component | Shared? | Notes |
|-----------|---------|-------|
| Tauri frontend (HTML/JS/CSS) | Yes | Same UI code |
| Python backend (engrave package) | Yes | Same source, compiled per-platform |
| Tauri config | Partial | Platform-specific sidecar paths, icons |
| Installer | No | NSIS (Windows) vs .dmg (macOS) |
| Code signing | No | EV cert (Windows) vs Apple Developer ID (macOS) |
| LilyPond bundle | No | mingw ZIP (Windows) vs macOS universal binary |

---

## 8. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| SmartScreen blocks unsigned installer | **High** | EV code signing certificate |
| AV false positives on bundled exe | **High** | Use Nuitka, EV cert, submit to AV vendors |
| Bundle size too large (>1 GB) | Medium | Download ML models on first use, offer lite mode |
| WebView2 inconsistency vs macOS WebKit | Medium | Test thoroughly, use progressive enhancement |
| LilyPond sandbox issues in MSIX | Medium | Test early; fall back to NSIS if needed |
| Nuitka compilation complexity | Low | Well-documented, CI can automate |
| ffmpeg/FluidSynth Windows compatibility | Low | Static builds available, well-tested |

---

## 9. Recommended Implementation Order

1. **Phase 1: Tauri skeleton + existing web UI**
   - Wrap `engrave.web.app` in Tauri with sidecar
   - Prove the sidecar pattern works on Windows
   - Use existing `index.html` as the frontend

2. **Phase 2: Nuitka compilation + LilyPond bundling**
   - Compile Python backend with Nuitka
   - Bundle LilyPond mingw ZIP
   - Test full pipeline on Windows

3. **Phase 3: NSIS installer + code signing**
   - Create NSIS installer script
   - Obtain EV certificate and sign
   - Publish to GitHub Releases

4. **Phase 4: Package manager distribution**
   - Submit to Scoop bucket
   - Submit to winget-pkgs
   - Optional: Chocolatey

5. **Phase 5: Polish**
   - Auto-update mechanism (Tauri's built-in updater)
   - First-run experience (model download progress)
   - Offline mode support
