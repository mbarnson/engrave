//! Resolve CLI executable paths in sandboxed environments.
//!
//! macOS .app bundles don't inherit the user's shell PATH, so executables like
//! `claude` and `engrave` can't be found by name alone. This module searches
//! well-known installation paths and caches the result.

use std::path::PathBuf;
use std::process::Command;
use std::sync::OnceLock;

/// Cached resolved path for the `claude` CLI.
static CLAUDE_PATH: OnceLock<Option<String>> = OnceLock::new();

/// Cached resolved path for the `engrave` CLI.
static ENGRAVE_PATH: OnceLock<Option<String>> = OnceLock::new();

/// Try to resolve a binary by spawning a login shell (macOS/Linux).
///
/// On macOS, `/bin/zsh -l -c 'which <name>'` loads the user's full PATH.
fn resolve_via_login_shell(name: &str) -> Option<String> {
    let shell = if cfg!(target_os = "macos") {
        "/bin/zsh"
    } else {
        "/bin/bash"
    };

    let output = Command::new(shell)
        .args(["-l", "-c", &format!("which {name}")])
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::null())
        .output()
        .ok()?;

    if output.status.success() {
        let path = String::from_utf8_lossy(&output.stdout).trim().to_string();
        if !path.is_empty() && std::path::Path::new(&path).exists() {
            return Some(path);
        }
    }
    None
}

/// Return the home directory, if available.
fn home_dir() -> Option<PathBuf> {
    std::env::var("HOME")
        .ok()
        .map(PathBuf::from)
        .or_else(|| {
            #[allow(deprecated)]
            std::env::home_dir()
        })
}

/// Search well-known paths for a binary and return the first match.
fn search_known_paths(name: &str, extra_candidates: &[PathBuf]) -> Option<String> {
    for candidate in extra_candidates {
        if candidate.exists() {
            return Some(candidate.to_string_lossy().to_string());
        }
    }

    // Try the bare name on the (possibly minimal) PATH
    let output = Command::new("which")
        .arg(name)
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::null())
        .output()
        .ok()?;

    if output.status.success() {
        let path = String::from_utf8_lossy(&output.stdout).trim().to_string();
        if !path.is_empty() && std::path::Path::new(&path).exists() {
            return Some(path);
        }
    }

    None
}

/// Build candidate paths for the `claude` CLI.
fn claude_candidates() -> Vec<PathBuf> {
    let mut candidates = Vec::new();

    if let Some(home) = home_dir() {
        // npm global installs
        candidates.push(home.join(".npm-global/bin/claude"));
        candidates.push(home.join("node_modules/.bin/claude"));

        // nvm installs — glob for any node version
        if let Ok(entries) = std::fs::read_dir(home.join(".nvm/versions/node")) {
            for entry in entries.flatten() {
                candidates.push(entry.path().join("bin/claude"));
            }
        }

        // Volta
        candidates.push(home.join(".volta/bin/claude"));

        // Local bin
        candidates.push(home.join(".local/bin/claude"));
    }

    // System paths
    candidates.push(PathBuf::from("/usr/local/bin/claude"));
    candidates.push(PathBuf::from("/opt/homebrew/bin/claude"));

    #[cfg(target_os = "windows")]
    {
        if let Ok(appdata) = std::env::var("APPDATA") {
            candidates.push(PathBuf::from(format!("{appdata}/npm/claude.cmd")));
            candidates.push(PathBuf::from(format!("{appdata}/npm/claude")));
        }
        candidates.push(PathBuf::from("C:/Program Files/nodejs/claude.cmd"));
        candidates.push(PathBuf::from("C:/Program Files/nodejs/claude"));
    }

    candidates
}

/// Resolve the path to a bundled resource binary shipped inside the Tauri app.
///
/// The binary is placed in the `resources/` directory at build time via
/// `tauri.conf.json`.  At runtime the layout is:
///
///   macOS:   Engrave.app/Contents/Resources/<name>
///   Windows: <install-dir>/<name>.exe   (resources are next to the exe)
///   Linux:   <exe-dir>/<name>           (AppImage/deb)
fn resolve_bundled_binary(name: &str) -> Option<PathBuf> {
    let exe = std::env::current_exe().ok()?;

    let mut candidates = Vec::new();

    // macOS .app bundle: exe is at Contents/MacOS/Engrave
    // resources live at Contents/Resources/
    if cfg!(target_os = "macos") {
        if let Some(macos_dir) = exe.parent() {
            let resources = macos_dir
                .parent() // Contents
                .map(|p| p.join("Resources").join(name));
            if let Some(p) = resources {
                candidates.push(p);
            }
        }
    }

    // Windows / Linux: resources/ directory next to the executable
    if let Some(exe_dir) = exe.parent() {
        let bin_name = if cfg!(target_os = "windows") {
            format!("{name}.exe")
        } else {
            name.to_string()
        };
        candidates.push(exe_dir.join("resources").join(&bin_name));
        candidates.push(exe_dir.join(&bin_name));
    }

    candidates.into_iter().find(|p| p.exists())
}

/// Build candidate paths for the `engrave` CLI.
fn engrave_candidates() -> Vec<PathBuf> {
    let mut candidates = Vec::new();

    // Bundled binary inside the app package (highest priority)
    if let Some(bundled) = resolve_bundled_binary("engrave") {
        candidates.push(bundled);
    }

    if let Some(home) = home_dir() {
        candidates.push(home.join(".local/bin/engrave"));
        candidates.push(home.join(".cargo/bin/engrave"));
    }

    candidates.push(PathBuf::from("/usr/local/bin/engrave"));
    candidates.push(PathBuf::from("/opt/homebrew/bin/engrave"));

    candidates
}

/// Resolve the `claude` CLI path, caching the result.
///
/// Search order:
/// 1. `CLAUDE_CLI` environment variable
/// 2. Well-known filesystem paths
/// 3. Login shell resolution (`/bin/zsh -l -c 'which claude'`)
pub fn resolve_claude() -> Option<&'static str> {
    CLAUDE_PATH
        .get_or_init(|| {
            // 1. Env var override
            if let Ok(path) = std::env::var("CLAUDE_CLI") {
                if std::path::Path::new(&path).exists() {
                    return Some(path);
                }
            }

            // 2. Known paths
            if let Some(path) = search_known_paths("claude", &claude_candidates()) {
                return Some(path);
            }

            // 3. Login shell
            resolve_via_login_shell("claude")
        })
        .as_deref()
}

/// Resolve the `engrave` CLI path, caching the result.
///
/// Search order:
/// 1. `ENGRAVE_CLI` environment variable
/// 2. Well-known filesystem paths
/// 3. Login shell resolution
pub fn resolve_engrave() -> Option<&'static str> {
    ENGRAVE_PATH
        .get_or_init(|| {
            // 1. Env var override
            if let Ok(path) = std::env::var("ENGRAVE_CLI") {
                if std::path::Path::new(&path).exists() {
                    return Some(path);
                }
            }

            // 2. Known paths
            if let Some(path) = search_known_paths("engrave", &engrave_candidates()) {
                return Some(path);
            }

            // 3. Login shell
            resolve_via_login_shell("engrave")
        })
        .as_deref()
}

/// Format a helpful "not found" error listing all paths that were checked.
pub fn not_found_error(name: &str, candidates: &[PathBuf]) -> String {
    let mut msg = format!(
        "Could not find '{name}' CLI. Checked the following locations:\n"
    );
    for c in candidates {
        msg.push_str(&format!("  - {}\n", c.display()));
    }
    msg.push_str(&format!(
        "  - login shell: `/bin/zsh -l -c 'which {name}'`\n\n"
    ));
    msg.push_str(&format!(
        "You can also set the {}_CLI environment variable to the full path.",
        name.to_uppercase()
    ));
    msg
}

/// Get a "not found" error for claude with all checked paths.
pub fn claude_not_found_error() -> String {
    not_found_error("claude", &claude_candidates())
}

/// Get a "not found" error for engrave with all checked paths.
pub fn engrave_not_found_error() -> String {
    not_found_error("engrave", &engrave_candidates())
}
