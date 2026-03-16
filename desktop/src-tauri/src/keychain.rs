//! OS keychain integration for secure API key storage.
//!
//! Uses the `keyring` crate which maps to:
//! - macOS: Keychain Services
//! - Windows: Credential Manager
//! - Linux: Secret Service (GNOME Keyring / KDE Wallet)

use keyring::Entry;

const SERVICE: &str = "com.engrave.desktop";
const USERNAME: &str = "api-key";

fn entry() -> Result<Entry, keyring::Error> {
    Entry::new(SERVICE, USERNAME)
}

pub fn save_api_key(key: &str) -> Result<(), keyring::Error> {
    entry()?.set_password(key)
}

pub fn load_api_key() -> Result<Option<String>, keyring::Error> {
    match entry()?.get_password() {
        Ok(password) => Ok(Some(password)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(e) => Err(e),
    }
}

pub fn delete_api_key() -> Result<(), keyring::Error> {
    match entry()?.delete_credential() {
        Ok(()) => Ok(()),
        Err(keyring::Error::NoEntry) => Ok(()),
        Err(e) => Err(e),
    }
}

pub fn has_api_key() -> Result<bool, keyring::Error> {
    match entry()?.get_password() {
        Ok(_) => Ok(true),
        Err(keyring::Error::NoEntry) => Ok(false),
        Err(e) => Err(e),
    }
}
