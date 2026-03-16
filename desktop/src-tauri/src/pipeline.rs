//! Pipeline execution: calls the `engrave` CLI from the Rust backend.
//!
//! The desktop app shells out to `engrave generate` and `engrave render`
//! rather than embedding the Python runtime. This keeps the Tauri binary
//! small and avoids Python/Rust FFI complexity.

use crate::{GenerationResult, MeasureFixResult};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use tauri::Emitter;
use tokio::process::Command;

/// Find the engrave CLI executable.
///
/// Checks (in order):
/// 1. `ENGRAVE_CLI` environment variable
/// 2. `engrave` on PATH (via `uv run engrave` or installed globally)
fn find_engrave_cli() -> String {
    std::env::var("ENGRAVE_CLI").unwrap_or_else(|_| "engrave".to_string())
}

/// Emit a progress event to the frontend.
fn emit_progress(app: &tauri::AppHandle, stage: &str, detail: &str, percent: f32) {
    let _ = app.emit(
        "generation-progress",
        serde_json::json!({
            "stage": stage,
            "detail": detail,
            "percent": percent,
        }),
    );
}

/// Run the engrave generation + render pipeline.
///
/// Steps:
/// 1. `engrave generate <midi_path> --labels <json> [--hints <text>]`
/// 2. `engrave render <output_dir>`
///
/// Progress events are emitted to the frontend at each stage.
pub async fn run_generation(
    app: &tauri::AppHandle,
    midi_path: &str,
    labels: &HashMap<String, String>,
    hints: Option<&str>,
) -> Result<GenerationResult, Box<dyn std::error::Error + Send + Sync>> {
    let engrave = find_engrave_cli();
    let midi = PathBuf::from(midi_path);

    if !midi.exists() {
        return Err(format!("MIDI file not found: {midi_path}").into());
    }

    // Create output directory next to the MIDI file
    let stem = midi.file_stem().unwrap_or_default().to_string_lossy();
    let output_dir = midi
        .parent()
        .unwrap_or(Path::new("."))
        .join(format!("{stem}_output"));
    std::fs::create_dir_all(&output_dir)?;

    let ly_output = output_dir.join(format!("{stem}.ly"));

    // --- Step 1: Generate LilyPond from MIDI ---
    emit_progress(app, "generate", "Generating LilyPond from MIDI...", 10.0);

    let labels_json = serde_json::to_string(labels)?;

    let mut cmd = Command::new(&engrave);
    cmd.arg("generate")
        .arg(midi_path)
        .arg("--output")
        .arg(&ly_output)
        .arg("--labels")
        .arg(&labels_json);

    if let Some(hints_text) = hints {
        cmd.arg("--hints").arg(hints_text);
    }

    // Pass OAuth token from keychain to subprocess (preferred),
    // falling back to legacy API key for migration.
    match crate::oauth::get_valid_token().await {
        Ok(Some(token)) => {
            cmd.env("ANTHROPIC_AUTH_TOKEN", &token);
        }
        _ => {
            if let Ok(Some(key)) = crate::keychain::load_legacy_api_key() {
                cmd.env("ANTHROPIC_API_KEY", &key);
            }
        }
    }

    let gen_output = cmd.output().await?;

    if !gen_output.status.success() {
        let stderr = String::from_utf8_lossy(&gen_output.stderr);
        let stdout = String::from_utf8_lossy(&gen_output.stdout);
        return Ok(GenerationResult {
            success: false,
            output_dir: Some(output_dir.to_string_lossy().to_string()),
            zip_path: None,
            error: Some(format!(
                "Generation failed:\n{}\n{}",
                stdout.trim(),
                stderr.trim()
            )),
            pdf_paths: vec![],
        });
    }

    emit_progress(app, "generate", "LilyPond generated successfully", 50.0);

    // --- Step 2: Render to PDF ---
    emit_progress(app, "render", "Rendering PDFs and packaging...", 60.0);

    let render_output = Command::new(&engrave)
        .arg("render")
        .arg(&output_dir)
        .arg("--title")
        .arg(stem.as_ref())
        .output()
        .await?;

    if !render_output.status.success() {
        let stderr = String::from_utf8_lossy(&render_output.stderr);
        // Render failure is non-fatal — we still have the .ly files
        emit_progress(
            app,
            "render",
            &format!("Render warning: {}", stderr.trim()),
            80.0,
        );
    }

    // --- Collect output files ---
    emit_progress(app, "complete", "Collecting output files...", 90.0);

    let mut pdf_paths = Vec::new();
    let mut zip_path = None;

    if let Ok(entries) = std::fs::read_dir(&output_dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if let Some(ext) = path.extension() {
                match ext.to_string_lossy().as_ref() {
                    "pdf" => pdf_paths.push(path.to_string_lossy().to_string()),
                    "zip" => zip_path = Some(path.to_string_lossy().to_string()),
                    _ => {}
                }
            }
        }
    }
    pdf_paths.sort();

    emit_progress(app, "complete", "Done!", 100.0);

    Ok(GenerationResult {
        success: true,
        output_dir: Some(output_dir.to_string_lossy().to_string()),
        zip_path,
        error: None,
        pdf_paths,
    })
}

/// Run a per-measure fix on a compiled .ly file, then re-render.
///
/// Steps:
/// 1. `engrave fix-measure <ly_path> -i <instrument> -b <bar> --hint <hint>`
/// 2. `engrave render <output_dir>` to regenerate PDFs
pub async fn run_measure_fix(
    app: &tauri::AppHandle,
    ly_path: &str,
    instrument: &str,
    bar: u32,
    hint: &str,
    output_dir: &str,
) -> Result<MeasureFixResult, Box<dyn std::error::Error + Send + Sync>> {
    let engrave = find_engrave_cli();

    if !Path::new(ly_path).exists() {
        return Err(format!("LilyPond file not found: {ly_path}").into());
    }

    // --- Step 1: Fix the measure ---
    emit_progress(app, "fix-measure", &format!("Fixing bar {bar} for {instrument}..."), 10.0);

    let mut cmd = Command::new(&engrave);
    cmd.arg("fix-measure")
        .arg(ly_path)
        .arg("--instrument")
        .arg(instrument)
        .arg("--bar")
        .arg(bar.to_string())
        .arg("--hint")
        .arg(hint);

    // Pass OAuth token from keychain to subprocess (preferred),
    // falling back to legacy API key for migration.
    match crate::oauth::get_valid_token().await {
        Ok(Some(token)) => {
            cmd.env("ANTHROPIC_AUTH_TOKEN", &token);
        }
        _ => {
            if let Ok(Some(key)) = crate::keychain::load_legacy_api_key() {
                cmd.env("ANTHROPIC_API_KEY", &key);
            }
        }
    }

    let fix_output = cmd.output().await?;

    if !fix_output.status.success() {
        let stderr = String::from_utf8_lossy(&fix_output.stderr);
        let stdout = String::from_utf8_lossy(&fix_output.stdout);
        return Ok(MeasureFixResult {
            success: false,
            error: Some(format!(
                "Measure fix failed:\n{}\n{}",
                stdout.trim(),
                stderr.trim()
            )),
            pdf_paths: vec![],
        });
    }

    emit_progress(app, "fix-measure", "Measure fixed, re-rendering...", 50.0);

    // --- Step 2: Re-render PDFs ---
    emit_progress(app, "render", "Re-rendering PDFs...", 60.0);

    let stem = Path::new(ly_path)
        .file_stem()
        .unwrap_or_default()
        .to_string_lossy();

    let render_output = Command::new(&engrave)
        .arg("render")
        .arg(output_dir)
        .arg("--title")
        .arg(stem.as_ref())
        .output()
        .await?;

    if !render_output.status.success() {
        let stderr = String::from_utf8_lossy(&render_output.stderr);
        emit_progress(
            app,
            "render",
            &format!("Render warning: {}", stderr.trim()),
            80.0,
        );
    }

    // --- Collect updated PDF files ---
    emit_progress(app, "complete", "Collecting updated files...", 90.0);

    let mut pdf_paths = Vec::new();
    if let Ok(entries) = std::fs::read_dir(output_dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|e| e.to_str()) == Some("pdf") {
                pdf_paths.push(path.to_string_lossy().to_string());
            }
        }
    }
    pdf_paths.sort();

    emit_progress(app, "complete", "Measure fix complete!", 100.0);

    Ok(MeasureFixResult {
        success: true,
        error: None,
        pdf_paths,
    })
}
