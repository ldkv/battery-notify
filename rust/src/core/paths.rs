//! Per-user locations, the same as the Python version (platformdirs) so that both share their files.
//! On Windows, everything lives under %LOCALAPPDATA%\battery-notifier.

use std::fs;
use std::path::PathBuf;

pub const APP_NAME: &str = "battery-notifier";

fn ensure(path: PathBuf) -> PathBuf {
    if let Err(e) = fs::create_dir_all(&path) {
        tracing::warn!("Could not create {}: {e}", path.display());
    }
    path
}

fn home() -> PathBuf {
    dirs::home_dir().unwrap_or_default()
}

pub fn config_dir() -> PathBuf {
    let base = if cfg!(target_os = "linux") {
        dirs::config_dir().unwrap_or_else(|| home().join(".config"))
    } else {
        // %LOCALAPPDATA% on Windows, ~/Library/Application Support on macOS
        dirs::data_local_dir().unwrap_or_else(home)
    };
    ensure(base.join(APP_NAME))
}

pub fn state_dir() -> PathBuf {
    if cfg!(target_os = "linux") {
        let base = dirs::state_dir().unwrap_or_else(|| home().join(".local/state"));
        ensure(base.join(APP_NAME))
    } else {
        config_dir()
    }
}

pub fn log_dir() -> PathBuf {
    if cfg!(target_os = "windows") {
        ensure(config_dir().join("Logs"))
    } else if cfg!(target_os = "macos") {
        ensure(home().join("Library/Logs").join(APP_NAME))
    } else {
        ensure(state_dir().join("log"))
    }
}

pub fn config_file() -> PathBuf {
    config_dir().join("config.toml")
}

pub fn seen_devices_file() -> PathBuf {
    state_dir().join("seen_devices.json")
}
