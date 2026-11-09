//! The tray holds the other end of the settings dialog's stdin: closing it is the tray quitting.

use std::process::{Command, Stdio};
use std::thread::sleep;
use std::time::{Duration, Instant};

const STARTUP: Duration = Duration::from_secs(5);
const CLOSE_TIMEOUT: Duration = Duration::from_secs(15);

fn has_display() -> bool {
    cfg!(any(windows, target_os = "macos"))
        || std::env::var_os("DISPLAY").is_some()
        || std::env::var_os("WAYLAND_DISPLAY").is_some()
}

#[test]
fn dialog_closes_when_the_tray_quits() {
    if !has_display() {
        eprintln!("No display, skipped");
        return;
    }
    let mut dialog = Command::new(env!("CARGO_BIN_EXE_battery-notifier"))
        .args(["settings", "--close-with-tray"])
        .stdin(Stdio::piped())
        .spawn()
        .expect("start the settings dialog");

    sleep(STARTUP);
    assert!(dialog.try_wait().unwrap().is_none(), "the dialog must stay open while the tray runs");

    drop(dialog.stdin.take());
    let deadline = Instant::now() + CLOSE_TIMEOUT;
    let status = loop {
        if let Some(status) = dialog.try_wait().unwrap() {
            break status;
        }
        if Instant::now() > deadline {
            let _ = dialog.kill();
            panic!("the dialog did not close after its stdin closed");
        }
        sleep(Duration::from_millis(100));
    };
    assert!(!status.success(), "closed without saving");
}
