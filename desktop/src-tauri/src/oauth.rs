//! OAuth 2.0 PKCE flow for Claude authentication.
//!
//! Implements the Authorization Code flow with PKCE for desktop apps:
//! 1. Generate code_verifier + code_challenge (S256)
//! 2. Open browser to Anthropic's authorization endpoint
//! 3. Spin up a local HTTP server to receive the callback
//! 4. Exchange the authorization code for access + refresh tokens
//! 5. Store tokens in the OS keychain
//!
//! Reference: <https://github.com/bartolli/anthropic-agent-sdk>

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::sync::Arc;
use tokio::sync::Mutex;

// OAuth configuration matching the Anthropic Agent SDK
const CLIENT_ID: &str = "9d1c250a-e61b-44d9-88ed-5944d1962f5e";
const AUTH_URL: &str = "https://claude.ai/oauth/authorize";
const TOKEN_URL: &str = "https://console.anthropic.com/v1/oauth/token";
const REDIRECT_URI: &str = "http://127.0.0.1:19275/oauth/callback";
const SCOPES: &str = "user:profile user:inference";
const CALLBACK_PORT: u16 = 19275;

/// Result of an OAuth token exchange.
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct OAuthTokens {
    pub access_token: String,
    pub refresh_token: String,
    pub expires_in: i64,
    pub token_type: String,
    #[serde(default)]
    pub scope: String,
}

/// Auth status returned to the frontend.
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct AuthStatus {
    pub authenticated: bool,
    pub token_valid: bool,
    pub has_legacy_api_key: bool,
}

/// PKCE code verifier and challenge pair.
struct PkceChallenge {
    verifier: String,
    challenge: String,
}

impl PkceChallenge {
    fn generate() -> Self {
        use rand::Rng;
        let mut rng = rand::rng();
        let verifier_bytes: Vec<u8> = (0..32).map(|_| rng.random::<u8>()).collect();
        let verifier = base64_url_encode(&verifier_bytes);

        let mut hasher = Sha256::new();
        hasher.update(verifier.as_bytes());
        let challenge = base64_url_encode(&hasher.finalize());

        PkceChallenge {
            verifier,
            challenge,
        }
    }
}

fn base64_url_encode(input: &[u8]) -> String {
    use base64::Engine;
    base64::engine::general_purpose::URL_SAFE_NO_PAD.encode(input)
}

/// Generate a random state parameter for CSRF protection.
fn generate_state() -> String {
    use rand::Rng;
    let mut rng = rand::rng();
    let bytes: Vec<u8> = (0..16).map(|_| rng.random::<u8>()).collect();
    base64_url_encode(&bytes)
}

/// Build the authorization URL that opens in the user's browser.
fn build_auth_url(pkce: &PkceChallenge, state: &str) -> String {
    format!(
        "{}?response_type=code\
         &client_id={}\
         &redirect_uri={}\
         &scope={}\
         &state={}\
         &code_challenge={}\
         &code_challenge_method=S256",
        AUTH_URL,
        urlencoding::encode(CLIENT_ID),
        urlencoding::encode(REDIRECT_URI),
        urlencoding::encode(SCOPES),
        urlencoding::encode(state),
        urlencoding::encode(&pkce.challenge),
    )
}

/// Exchange an authorization code for tokens.
async fn exchange_code(
    code: &str,
    pkce_verifier: &str,
) -> Result<OAuthTokens, String> {
    let client = reqwest::Client::new();

    let params = [
        ("grant_type", "authorization_code"),
        ("code", code),
        ("redirect_uri", REDIRECT_URI),
        ("client_id", CLIENT_ID),
        ("code_verifier", pkce_verifier),
    ];

    let resp = client
        .post(TOKEN_URL)
        .form(&params)
        .send()
        .await
        .map_err(|e| format!("Token exchange request failed: {e}"))?;

    if !resp.status().is_success() {
        let status = resp.status();
        let body = resp.text().await.unwrap_or_default();
        return Err(format!("Token exchange failed ({status}): {body}"));
    }

    resp.json::<OAuthTokens>()
        .await
        .map_err(|e| format!("Failed to parse token response: {e}"))
}

/// Refresh an expired access token using the refresh token.
pub async fn refresh_access_token(refresh_token: &str) -> Result<OAuthTokens, String> {
    let client = reqwest::Client::new();

    let params = [
        ("grant_type", "refresh_token"),
        ("refresh_token", refresh_token),
        ("client_id", CLIENT_ID),
    ];

    let resp = client
        .post(TOKEN_URL)
        .form(&params)
        .send()
        .await
        .map_err(|e| format!("Token refresh request failed: {e}"))?;

    if !resp.status().is_success() {
        let status = resp.status();
        let body = resp.text().await.unwrap_or_default();
        return Err(format!("Token refresh failed ({status}): {body}"));
    }

    resp.json::<OAuthTokens>()
        .await
        .map_err(|e| format!("Failed to parse refresh response: {e}"))
}

/// Start the full OAuth PKCE flow.
///
/// 1. Generates PKCE challenge
/// 2. Opens browser to authorization URL
/// 3. Starts local server to receive callback
/// 4. Exchanges code for tokens
/// 5. Stores tokens in keychain
///
/// Returns the auth URL (for the frontend to open if shell open fails).
pub async fn start_oauth_flow() -> Result<String, String> {
    let pkce = PkceChallenge::generate();
    let state = generate_state();
    let auth_url = build_auth_url(&pkce, &state);

    // Store PKCE verifier and state for the callback handler
    let flow_state = Arc::new(Mutex::new(Some(FlowState {
        pkce_verifier: pkce.verifier.clone(),
        expected_state: state.clone(),
    })));

    // Start callback server in background
    let flow_state_clone = flow_state.clone();
    tokio::spawn(async move {
        if let Err(e) = run_callback_server(flow_state_clone).await {
            eprintln!("OAuth callback server error: {e}");
        }
    });

    // Try to open browser
    if let Err(e) = open::that(&auth_url) {
        eprintln!("Failed to open browser: {e}");
        // Frontend will use the returned URL as fallback
    }

    Ok(auth_url)
}

struct FlowState {
    pkce_verifier: String,
    expected_state: String,
}

/// Run a one-shot local HTTP server to receive the OAuth callback.
async fn run_callback_server(
    flow_state: Arc<Mutex<Option<FlowState>>>,
) -> Result<(), String> {
    use tokio::io::{AsyncReadExt, AsyncWriteExt};
    use tokio::net::TcpListener;

    let listener = TcpListener::bind(format!("127.0.0.1:{CALLBACK_PORT}"))
        .await
        .map_err(|e| format!("Failed to bind callback server: {e}"))?;

    // Accept one connection (with timeout)
    let accept_result = tokio::time::timeout(
        std::time::Duration::from_secs(300), // 5 minute timeout
        listener.accept(),
    )
    .await;

    let (mut stream, _) = match accept_result {
        Ok(Ok(conn)) => conn,
        Ok(Err(e)) => return Err(format!("Accept failed: {e}")),
        Err(_) => return Err("OAuth callback timed out after 5 minutes".into()),
    };

    // Read the HTTP request
    let mut buf = vec![0u8; 4096];
    let n = stream
        .read(&mut buf)
        .await
        .map_err(|e| format!("Read failed: {e}"))?;
    let request = String::from_utf8_lossy(&buf[..n]);

    // Parse the request line to get query parameters
    let first_line = request.lines().next().unwrap_or("");
    let path = first_line.split_whitespace().nth(1).unwrap_or("");

    // Parse query string
    let query = path.split('?').nth(1).unwrap_or("");
    let params: std::collections::HashMap<&str, &str> = query
        .split('&')
        .filter_map(|pair| {
            let mut parts = pair.splitn(2, '=');
            Some((parts.next()?, parts.next()?))
        })
        .collect();

    let state = flow_state.lock().await.take();
    let flow = state.ok_or("OAuth flow state missing")?;

    // Verify state parameter
    let received_state = params.get("state").unwrap_or(&"");
    if *received_state != flow.expected_state {
        let error_html = error_response("State mismatch — possible CSRF attack. Please try again.");
        let _ = stream.write_all(error_html.as_bytes()).await;
        return Err("OAuth state mismatch".into());
    }

    // Check for error response
    if let Some(error) = params.get("error") {
        let desc = params.get("error_description").unwrap_or(error);
        let error_html = error_response(&format!("Authorization denied: {desc}"));
        let _ = stream.write_all(error_html.as_bytes()).await;
        return Err(format!("OAuth error: {desc}"));
    }

    // Get authorization code
    let code = params
        .get("code")
        .ok_or("No authorization code in callback")?;

    // Exchange code for tokens
    let tokens = exchange_code(code, &flow.pkce_verifier).await?;

    // Calculate expiry timestamp
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs() as i64;
    let expires_at = now + tokens.expires_in;

    // Store in keychain
    crate::keychain::save_oauth_tokens(
        &tokens.access_token,
        &tokens.refresh_token,
        expires_at,
    )
    .map_err(|e| format!("Failed to save tokens to keychain: {e}"))?;

    // Send success response to browser
    let success_html = success_response();
    let _ = stream.write_all(success_html.as_bytes()).await;

    Ok(())
}

fn success_response() -> String {
    let body = r#"<!DOCTYPE html>
<html><head><title>Engrave — Signed In</title>
<style>body{font-family:system-ui;display:flex;align-items:center;justify-content:center;
min-height:100vh;margin:0;background:#f8f9fa}
.card{text-align:center;padding:2rem;border-radius:12px;background:white;
box-shadow:0 2px 8px rgba(0,0,0,.1);max-width:400px}
h1{color:#2d7d46;margin-bottom:.5rem}p{color:#666}</style></head>
<body><div class="card"><h1>Signed in to Engrave</h1>
<p>You can close this tab and return to the app.</p></div></body></html>"#;
    format!(
        "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
        body.len(),
        body
    )
}

fn error_response(message: &str) -> String {
    let body = format!(
        r#"<!DOCTYPE html>
<html><head><title>Engrave — Auth Error</title>
<style>body{{font-family:system-ui;display:flex;align-items:center;justify-content:center;
min-height:100vh;margin:0;background:#f8f9fa}}
.card{{text-align:center;padding:2rem;border-radius:12px;background:white;
box-shadow:0 2px 8px rgba(0,0,0,.1);max-width:400px}}
h1{{color:#d32f2f;margin-bottom:.5rem}}p{{color:#666}}</style></head>
<body><div class="card"><h1>Authentication Failed</h1>
<p>{message}</p></div></body></html>"#
    );
    format!(
        "HTTP/1.1 400 Bad Request\r\nContent-Type: text/html\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
        body.len(),
        body
    )
}

/// Get the current authentication status.
pub fn get_auth_status() -> Result<AuthStatus, String> {
    let has_token = crate::keychain::has_oauth_token().map_err(|e| e.to_string())?;
    let token_valid = crate::keychain::is_token_valid().map_err(|e| e.to_string())?;
    let has_legacy = crate::keychain::load_legacy_api_key()
        .map_err(|e| e.to_string())?
        .is_some();

    Ok(AuthStatus {
        authenticated: has_token,
        token_valid,
        has_legacy_api_key: has_legacy,
    })
}

/// Get a valid access token, refreshing if needed.
///
/// Returns None if not authenticated at all.
pub async fn get_valid_token() -> Result<Option<String>, String> {
    // Check if we have a token
    let access_token = crate::keychain::load_access_token()
        .map_err(|e| e.to_string())?;

    if access_token.is_none() {
        return Ok(None);
    }

    // Check if token is still valid
    let valid = crate::keychain::is_token_valid().map_err(|e| e.to_string())?;
    if valid {
        return Ok(access_token);
    }

    // Try to refresh
    let refresh_token = crate::keychain::load_refresh_token()
        .map_err(|e| e.to_string())?;

    match refresh_token {
        Some(refresh) => {
            let tokens = refresh_access_token(&refresh).await?;
            let now = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs() as i64;
            let expires_at = now + tokens.expires_in;

            crate::keychain::save_oauth_tokens(
                &tokens.access_token,
                &tokens.refresh_token,
                expires_at,
            )
            .map_err(|e| format!("Failed to save refreshed tokens: {e}"))?;

            Ok(Some(tokens.access_token))
        }
        None => {
            // No refresh token — user needs to re-authenticate
            Ok(None)
        }
    }
}

/// Logout — delete all stored tokens.
pub fn logout() -> Result<(), String> {
    crate::keychain::delete_oauth_tokens().map_err(|e| e.to_string())
}
