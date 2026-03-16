use serde::{Deserialize, Serialize};
use std::path::PathBuf;

mod keychain;
mod midi;
mod pipeline;

// --- Data types shared with the frontend ---

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct MidiTrack {
    pub index: usize,
    pub name: String,
    pub channel: u8,
    pub note_count: usize,
    pub instrument_guess: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GenerationProgress {
    pub stage: String,
    pub detail: String,
    pub percent: f32,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct GenerationResult {
    pub success: bool,
    pub output_dir: Option<String>,
    pub zip_path: Option<String>,
    pub error: Option<String>,
    pub pdf_paths: Vec<String>,
}

// --- Tauri Commands ---

#[tauri::command]
async fn save_api_key(key: String) -> Result<(), String> {
    keychain::save_api_key(&key).map_err(|e| e.to_string())
}

#[tauri::command]
async fn delete_api_key() -> Result<(), String> {
    keychain::delete_api_key().map_err(|e| e.to_string())
}

#[tauri::command]
async fn has_api_key() -> Result<bool, String> {
    keychain::has_api_key().map_err(|e| e.to_string())
}

#[tauri::command]
async fn analyze_midi(path: String) -> Result<Vec<MidiTrack>, String> {
    midi::analyze_midi(&path).map_err(|e| e.to_string())
}

#[tauri::command]
async fn generate(
    app: tauri::AppHandle,
    midi_path: String,
    labels: std::collections::HashMap<String, String>,
    hints: Option<String>,
) -> Result<GenerationResult, String> {
    pipeline::run_generation(&app, &midi_path, &labels, hints.as_deref())
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
async fn read_pdf_base64(path: String) -> Result<String, String> {
    use std::fs;

    // Validate the path is a PDF within a known output directory (ends with _output/)
    let canonical = fs::canonicalize(&path)
        .map_err(|e| format!("Invalid path: {e}"))?;
    let is_in_output_dir = canonical
        .ancestors()
        .any(|ancestor| {
            ancestor
                .file_name()
                .map(|n| n.to_string_lossy().ends_with("_output"))
                .unwrap_or(false)
        });
    if !is_in_output_dir {
        return Err("Access denied: path must be within an engrave output directory".to_string());
    }
    if canonical.extension().and_then(|e| e.to_str()) != Some("pdf") {
        return Err("Access denied: only PDF files can be read".to_string());
    }

    let bytes = fs::read(&canonical).map_err(|e| format!("Failed to read PDF: {e}"))?;
    use base64::Engine;
    Ok(base64::engine::general_purpose::STANDARD.encode(&bytes))
}

#[tauri::command]
async fn get_output_files(output_dir: String) -> Result<Vec<String>, String> {
    let dir = PathBuf::from(&output_dir);
    if !dir.is_dir() {
        return Err(format!("Not a directory: {output_dir}"));
    }
    let mut files = Vec::new();
    for entry in std::fs::read_dir(&dir).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        let path = entry.path();
        if let Some(ext) = path.extension() {
            let ext = ext.to_string_lossy().to_lowercase();
            if matches!(ext.as_str(), "pdf" | "ly" | "zip" | "mid" | "midi" | "musicxml") {
                files.push(path.to_string_lossy().to_string());
            }
        }
    }
    files.sort();
    Ok(files)
}

// --- App setup ---

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_os::init())
        .invoke_handler(tauri::generate_handler![
            save_api_key,
            delete_api_key,
            has_api_key,
            analyze_midi,
            generate,
            read_pdf_base64,
            get_output_files,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
