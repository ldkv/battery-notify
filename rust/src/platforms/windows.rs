use std::env;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::{fs, io};

use windows::Win32::Foundation::{ERROR_ALREADY_EXISTS, GetLastError};
use windows::Win32::System::Console::{ATTACH_PARENT_PROCESS, AttachConsole};
use windows::Win32::System::Threading::CreateMutexW;
use windows::core::HSTRING;
use windows_registry::CURRENT_USER;

use super::{APP_TITLE, Platform};
use crate::core::paths::state_dir;
use crate::ui::icon::{icon_png, icon_renderer};

const RUN_KEY: &str = r"Software\Microsoft\Windows\CurrentVersion\Run";
const RUN_VALUE: &str = "BatteryNotifier";
const PERSONALIZE_KEY: &str = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize";
const ICON_FONTS: [&str; 2] = ["SegoeIcons.ttf", "segmdl2.ttf"];
/// Unpackaged apps need this registered to show toast notifications with their own name and icon.
pub const APP_USER_MODEL_ID: &str = "BatteryNotifier";
const APP_USER_MODEL_KEY: &str = r"Software\Classes\AppUserModelId\BatteryNotifier";

pub struct WindowsPlatform;

impl Platform for WindowsPlatform {
    fn supports_autostart(&self) -> bool {
        true
    }

    fn bluetooth_batteries(&self) -> Vec<(String, u8)> {
        super::windows_bluetooth::bluetooth_batteries()
    }

    fn is_autostart_enabled(&self) -> bool {
        CURRENT_USER.open(RUN_KEY).and_then(|key| key.get_string(RUN_VALUE)).is_ok()
    }

    fn set_autostart(&self, enabled: bool) -> io::Result<()> {
        let key = CURRENT_USER.create(RUN_KEY)?;
        if enabled {
            key.set_string(RUN_VALUE, autostart_command()?)?;
        } else if key.get_string(RUN_VALUE).is_ok() {
            key.remove_value(RUN_VALUE)?;
        }
        Ok(())
    }

    #[allow(unsafe_code)]
    fn acquire_single_instance(&self, name: &str) -> bool {
        // SAFETY: plain Win32 calls. The mutex handle is never closed, so it is held for the lifetime of the process.
        unsafe {
            let Ok(_handle) = CreateMutexW(None, false, &HSTRING::from(format!(r"Local\{name}"))) else {
                return true; // can't tell, don't block the app
            };
            GetLastError() != ERROR_ALREADY_EXISTS
        }
    }

    fn apps_use_dark_theme(&self) -> bool {
        is_dark_theme("AppsUseLightTheme")
    }

    fn taskbar_uses_dark_theme(&self) -> bool {
        is_dark_theme("SystemUsesLightTheme")
    }

    fn icon_font(&self) -> Option<PathBuf> {
        let fonts = PathBuf::from(env::var("WINDIR").unwrap_or_else(|_| r"C:\Windows".to_string())).join("Fonts");
        // Segoe Fluent Icons on Windows 11, Segoe MDL2 Assets on Windows 10
        ICON_FONTS.iter().map(|name| fonts.join(name)).find(|path| path.exists())
    }

    fn register_notifications(&self) {
        if let Err(e) = register_app_user_model_id(self) {
            tracing::warn!("Could not register notifications: {e}");
        }
    }

    fn show_notification(&self, title: &str, body: &str) {
        let result = notify_rust::Notification::new()
            .appname(APP_TITLE)
            .app_id(APP_USER_MODEL_ID)
            .summary(title)
            .body(body)
            .show();
        if let Err(e) = result {
            tracing::error!("Could not show the notification: {e}");
        }
    }

    #[allow(unsafe_code)]
    fn attach_console(&self) {
        // SAFETY: plain Win32 call, fails harmlessly when there is no parent console.
        let _ = unsafe { AttachConsole(ATTACH_PARENT_PROCESS) };
    }

    fn open_folder(&self, path: &Path) {
        if let Err(e) = Command::new("explorer").arg(path).spawn() {
            tracing::warn!("Could not open {}: {e}", path.display());
        }
    }
}

fn is_dark_theme(value_name: &str) -> bool {
    CURRENT_USER.open(PERSONALIZE_KEY).and_then(|key| key.get_u32(value_name)).is_ok_and(|light| light == 0)
}

fn autostart_command() -> io::Result<String> {
    Ok(format!("\"{}\"", env::current_exe()?.display()))
}

/// Name and icon shown on toast notifications.
fn register_app_user_model_id(platform: &WindowsPlatform) -> io::Result<()> {
    let icon_path = state_dir().join("notification_icon.png");
    let renderer = icon_renderer(platform.icon_font(), || false);
    fs::write(&icon_path, icon_png(renderer.as_ref(), Some(20))?)?;
    let key = CURRENT_USER.create(APP_USER_MODEL_KEY)?;
    key.set_string("DisplayName", APP_TITLE)?;
    key.set_string("IconUri", icon_path.display().to_string())?;
    Ok(())
}
