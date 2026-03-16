//! Claude Code authentication checks.
//!
//! Replaced the previous OS keychain / OAuth token storage with checks for
//! Claude Code CLI installation and authentication status.

use std::process::Command;

/// Check if `claude` CLI is available on PATH.
pub fn is_claude_installed() -> bool {
    Command::new("claude")
        .arg("--version")
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

/// Check if the user is authenticated with Claude Code.
///
/// Runs `claude auth status` and returns true on a zero exit code.
pub fn is_claude_authenticated() -> bool {
    Command::new("claude")
        .args(["auth", "status"])
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}
