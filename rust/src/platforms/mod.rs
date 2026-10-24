//! OS integration. The `Platform` defaults are used on unsupported OSes:
//! each OS overrides what it supports.

pub mod windows_bluetooth;

#[cfg(windows)]
pub mod windows;

use std::io;
use std::path::{Path, PathBuf};
use std::sync::Arc;

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
    fn acquire_single_instance(&self, _name: &str) -> bool {
        true
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

    /// Show a console when started from one, for command line output.
    fn attach_console(&self) {}

    fn open_folder(&self, path: &Path) {
        let opener = if cfg!(target_os = "macos") { "open" } else { "xdg-open" };
        if let Err(e) = std::process::Command::new(opener).arg(path).spawn() {
            tracing::warn!("Could not open {}: {e}", path.display());
        }
    }
}

#[cfg(not(windows))]
struct DefaultPlatform;

#[cfg(not(windows))]
impl Platform for DefaultPlatform {}

pub fn current_platform() -> Arc<dyn Platform> {
    #[cfg(windows)]
    return Arc::new(windows::WindowsPlatform);
    #[cfg(not(windows))]
    Arc::new(DefaultPlatform)
}
