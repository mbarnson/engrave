//! OS keychain integration for secure OAuth token storage.
//!
//! Stores OAuth access tokens, refresh tokens, and expiry timestamps
//! in the platform's native credential store:
//! - macOS: Keychain Services
//! - Windows: Credential Manager
//! - Linux: Secret Service (GNOME Keyring / KDE Wallet)

use keyring::Entry;

const SERVICE: &str = "com.engrave.desktop";
const ACCESS_TOKEN_KEY: &str = "oauth-access-token";
const REFRESH_TOKEN_KEY: &str = "oauth-refresh-token";
const EXPIRY_KEY: &str = "oauth-expiry";
// Legacy key for migration
const LEGACY_API_KEY: &str = "api-key";

fn entry(username: &str) -> Result<Entry, keyring::Error> {
    Entry::new(SERVICE, username)
}

/// Store the full OAuth token set in the keychain.
pub fn save_oauth_tokens(
    access_token: &str,
    refresh_token: &str,
    expires_at: i64,
) -> Result<(), keyring::Error> {
    entry(ACCESS_TOKEN_KEY)?.set_password(access_token)?;
    entry(REFRESH_TOKEN_KEY)?.set_password(refresh_token)?;
    entry(EXPIRY_KEY)?.set_password(&expires_at.to_string())?;
    // Clean up legacy API key if present
    let _ = delete_legacy_api_key();
    Ok(())
}

/// Load the OAuth access token from the keychain.
pub fn load_access_token() -> Result<Option<String>, keyring::Error> {
    match entry(ACCESS_TOKEN_KEY)?.get_password() {
        Ok(token) => Ok(Some(token)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(e) => Err(e),
    }
}

/// Load the OAuth refresh token from the keychain.
pub fn load_refresh_token() -> Result<Option<String>, keyring::Error> {
    match entry(REFRESH_TOKEN_KEY)?.get_password() {
        Ok(token) => Ok(Some(token)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(e) => Err(e),
    }
}

/// Load the token expiry timestamp (Unix seconds).
pub fn load_expiry() -> Result<Option<i64>, keyring::Error> {
    match entry(EXPIRY_KEY)?.get_password() {
        Ok(s) => Ok(s.parse::<i64>().ok()),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(e) => Err(e),
    }
}

/// Check if we have a stored OAuth token (may be expired).
pub fn has_oauth_token() -> Result<bool, keyring::Error> {
    match entry(ACCESS_TOKEN_KEY)?.get_password() {
        Ok(_) => Ok(true),
        Err(keyring::Error::NoEntry) => Ok(false),
        Err(e) => Err(e),
    }
}

/// Check if the stored token is still valid (not expired).
/// Returns true if token exists and expires more than 60s in the future.
pub fn is_token_valid() -> Result<bool, keyring::Error> {
    if !has_oauth_token()? {
        return Ok(false);
    }
    match load_expiry()? {
        Some(expires_at) => {
            let now = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs() as i64;
            // Consider expired 60s early to avoid edge cases
            Ok(expires_at - now > 60)
        }
        None => Ok(false),
    }
}

/// Delete all OAuth tokens from the keychain (logout).
pub fn delete_oauth_tokens() -> Result<(), keyring::Error> {
    for key in [ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY, EXPIRY_KEY] {
        match entry(key)?.delete_credential() {
            Ok(()) | Err(keyring::Error::NoEntry) => {}
            Err(e) => return Err(e),
        }
    }
    Ok(())
}

/// Delete the legacy API key (migration helper).
fn delete_legacy_api_key() -> Result<(), keyring::Error> {
    match entry(LEGACY_API_KEY)?.delete_credential() {
        Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
        Err(e) => Err(e),
    }
}

/// Load legacy API key if OAuth tokens are not present (migration path).
pub fn load_legacy_api_key() -> Result<Option<String>, keyring::Error> {
    match entry(LEGACY_API_KEY)?.get_password() {
        Ok(key) => Ok(Some(key)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(e) => Err(e),
    }
}
