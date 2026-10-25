//! OS integration. The `Platform` defaults are used on unsupported OSes:
//! each OS overrides what it supports.

pub mod windows_bluetooth;

#[cfg(windows)]
pub mod windows;

#[cfg(target_os = "macos")]
pub mod macos;

use std::fs::{File, TryLockError};
use std::io;
use std::path::{Path, PathBuf};
use std::sync::Arc;

use crate::core::paths::state_dir;

pub const APP_TITLE: &str = "Battery Notifier";

pub trait Platform: Send + Sync {
    fn supports_autostart(&self) -> bool {
        false
    }

    /// Name and battery level of the connected devices whose level the OS knows.
    fn bluetooth_batteries(&self) -> Vec<(String, u8)> {
        Vec::new()
    }

    fn is_autostart_enabled(&self) -> bool {
        false
    }

    fn set_autostart(&self, _enabled: bool) -> io::Result<()> {
        Err(io::Error::new(io::ErrorKind::Unsupported, "Run at startup is not supported on this OS"))
    }

    /// Return false if another process already holds `name`.
    fn acquire_single_instance(&self, name: &str) -> bool {
        lock_for_process(&state_dir().join(format!("{name}.lock")))
    }

    fn apps_use_dark_theme(&self) -> bool {
        false
    }

    fn taskbar_uses_dark_theme(&self) -> bool {
        false
    }

    /// Font with the Segoe battery glyphs, None to draw the tray icon instead.
    fn icon_font(&self) -> Option<PathBuf> {
        None
    }

    /// Register what the OS needs to show the app's notifications, called once at startup.
    fn register_notifications(&self) {}

    fn show_notification(&self, title: &str, body: &str) {
        if let Err(e) = notify_rust::Notification::new().appname(APP_TITLE).summary(title).body(body).show() {
            tracing::error!("Could not show the notification: {e}");
        }
    }

    /// Show a console when started from one, for command line output.
    fn attach_console(&self) {}

    fn open_folder(&self, path: &Path) {
        let opener = if cfg!(target_os = "macos") { "open" } else { "xdg-open" };
        if let Err(e) = std::process::Command::new(opener).arg(path).spawn() {
            tracing::warn!("Could not open {}: {e}", path.display());
        }
    }
}

/// Lock `path` until the process exits, return false if another process holds it.
fn lock_for_process(path: &Path) -> bool {
    let file = match File::create(path) {
        Ok(file) => file,
        Err(e) => {
            tracing::warn!("Could not create {}: {e}", path.display());
            return true; // can't tell, don't block the app
        }
    };
    match file.try_lock() {
        Ok(()) => {
            std::mem::forget(file); // the OS releases the lock when the process exits
            true
        }
        Err(TryLockError::WouldBlock) => false,
        Err(TryLockError::Error(e)) => {
            tracing::warn!("Could not lock {}: {e}", path.display());
            true
        }
    }
}

#[cfg(not(any(windows, target_os = "macos")))]
struct DefaultPlatform;

#[cfg(not(any(windows, target_os = "macos")))]
impl Platform for DefaultPlatform {}

pub fn current_platform() -> Arc<dyn Platform> {
    #[cfg(windows)]
    return Arc::new(windows::WindowsPlatform);
    #[cfg(target_os = "macos")]
    return Arc::new(macos::MacPlatform);
    #[cfg(not(any(windows, target_os = "macos")))]
    Arc::new(DefaultPlatform)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lock_for_process_excludes_a_second_holder() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("test.lock");
        assert!(lock_for_process(&path));
        assert!(!lock_for_process(&path));
        assert!(lock_for_process(&dir.path().join("other.lock")));
    }
}
