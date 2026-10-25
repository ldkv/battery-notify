use std::path::{Path, PathBuf};
use std::process::Command;
use std::{env, fs, io};

use block2::RcBlock;
use objc2::runtime::Bool;
use objc2_foundation::{NSBundle, NSError, NSString};
use objc2_user_notifications::{
    UNAuthorizationOptions, UNMutableNotificationContent, UNNotificationRequest, UNUserNotificationCenter,
};

use super::Platform;

/// Also the bundle identifier of the .app built by CI.
const LAUNCH_AGENT_LABEL: &str = "io.github.ldkv.battery-notifier";
/// Each notification replaces the previous one rather than piling up.
const NOTIFICATION_ID: &str = "battery";
/// Text as arguments rather than in the script, so that it needs no escaping.
const NOTIFICATION_SCRIPT: &str =
    "on run argv\ndisplay notification (item 2 of argv) with title (item 1 of argv)\nend run";

pub struct MacPlatform;

impl Platform for MacPlatform {
    fn supports_autostart(&self) -> bool {
        true
    }

    fn is_autostart_enabled(&self) -> bool {
        launch_agent_file().is_ok_and(|path| path.exists())
    }

    fn set_autostart(&self, enabled: bool) -> io::Result<()> {
        let path = launch_agent_file()?;
        if enabled {
            if let Some(dir) = path.parent() {
                fs::create_dir_all(dir)?;
            }
            fs::write(&path, launch_agent_plist(&env::current_exe()?))
        } else {
            match fs::remove_file(&path) {
                Err(e) if e.kind() != io::ErrorKind::NotFound => Err(e),
                _ => Ok(()),
            }
        }
    }

    fn apps_use_dark_theme(&self) -> bool {
        is_dark_mode()
    }

    fn taskbar_uses_dark_theme(&self) -> bool {
        is_dark_mode()
    }

    fn register_notifications(&self) {
        if !in_app_bundle() {
            return;
        }
        let handler = RcBlock::new(|granted: Bool, error: *mut NSError| {
            if !granted.as_bool() {
                tracing::warn!("Notifications are not allowed: {}", error_text(error));
            }
        });
        UNUserNotificationCenter::currentNotificationCenter()
            .requestAuthorizationWithOptions_completionHandler(UNAuthorizationOptions::Alert, &handler);
    }

    fn show_notification(&self, title: &str, body: &str) {
        if in_app_bundle() {
            show_user_notification(title, body);
        } else {
            show_script_notification(title, body);
        }
    }
}

/// UserNotifications needs an app bundle: it raises an exception without one.
fn in_app_bundle() -> bool {
    NSBundle::mainBundle().bundleIdentifier().is_some()
}

fn show_user_notification(title: &str, body: &str) {
    let content = UNMutableNotificationContent::new();
    content.setTitle(&NSString::from_str(title));
    content.setBody(&NSString::from_str(body));
    let request = UNNotificationRequest::requestWithIdentifier_content_trigger(
        &NSString::from_str(NOTIFICATION_ID),
        &content,
        None,
    );
    let handler = RcBlock::new(|error: *mut NSError| {
        if !error.is_null() {
            tracing::error!("Could not show the notification: {}", error_text(error));
        }
    });
    UNUserNotificationCenter::currentNotificationCenter()
        .addNotificationRequest_withCompletionHandler(&request, Some(&handler));
}

#[allow(unsafe_code)]
fn error_text(error: *mut NSError) -> String {
    // SAFETY: completion handlers get either null or a valid NSError.
    unsafe { error.as_ref() }.map_or_else(|| "no reason given".to_string(), |e| e.localizedDescription().to_string())
}

/// Through AppleScript when running outside an app bundle, as macOS drops notifications from a bare binary.
/// They show as from Script Editor.
fn show_script_notification(title: &str, body: &str) {
    let output = Command::new("osascript").args(["-e", NOTIFICATION_SCRIPT, title, body]).output();
    match output {
        Ok(output) if !output.status.success() => {
            tracing::error!("Could not show the notification: {}", String::from_utf8_lossy(&output.stderr).trim());
        }
        Err(e) => tracing::error!("Could not show the notification: {e}"),
        Ok(_) => {}
    }
}

fn launch_agent_file() -> io::Result<PathBuf> {
    let home = dirs::home_dir().ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "No home directory"))?;
    Ok(home.join("Library/LaunchAgents").join(format!("{LAUNCH_AGENT_LABEL}.plist")))
}

/// Start `exe` at login.
fn launch_agent_plist(exe: &Path) -> String {
    let exe = exe.display().to_string().replace('&', "&amp;").replace('<', "&lt;").replace('>', "&gt;");
    format!(
        r#"<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{LAUNCH_AGENT_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{exe}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
"#
    )
}

/// `AppleInterfaceStyle` is only set in dark mode, also when the appearance is automatic.
fn is_dark_mode() -> bool {
    Command::new("defaults")
        .args(["read", "-g", "AppleInterfaceStyle"])
        .output()
        .is_ok_and(|output| output.status.success() && String::from_utf8_lossy(&output.stdout).trim() == "Dark")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn launch_agent_plist_escapes_the_executable_path() {
        let plist = launch_agent_plist(Path::new("/Applications/A & B <1>.app/Contents/MacOS/battery-notifier"));
        assert!(
            plist.contains("<string>/Applications/A &amp; B &lt;1&gt;.app/Contents/MacOS/battery-notifier</string>")
        );
        assert!(plist.contains(&format!("<string>{LAUNCH_AGENT_LABEL}</string>")));
        assert!(plist.contains("<key>RunAtLoad</key>\n    <true/>"));
    }
}
