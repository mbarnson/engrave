//! Claude Code authentication checks.
//!
//! Uses the CLI resolver to find `claude` even when the app is launched
//! from a sandboxed macOS .app bundle with a minimal PATH.

use crate::cli_resolver;
use std::process::Command;

/// Check if `claude` CLI is available (found at any known path).
pub fn is_claude_installed() -> bool {
    cli_resolver::resolve_claude().is_some()
}

/// Check if the user is authenticated with Claude Code.
///
/// Runs `claude auth status` and returns true on a zero exit code.
pub fn is_claude_authenticated() -> bool {
    let Some(claude) = cli_resolver::resolve_claude() else {
        return false;
    };

    Command::new(claude)
        .args(["auth", "status"])
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

/// Return a detailed error message if claude is not found.
pub fn claude_not_found_message() -> String {
    cli_resolver::claude_not_found_error()
}
