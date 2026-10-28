// No console window for the release build on Windows
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::ExitCode;
use std::thread::sleep;
use std::time::Duration;

use battery_notifier::core::poller::Poller;
use battery_notifier::core::providers::{BatteryProvider, HidProvider, OsProvider};
use battery_notifier::core::settings::Settings;
use battery_notifier::logs::configure_logging;
use battery_notifier::platforms::{Platform, current_platform};
use battery_notifier::ui::{settings_dialog, tray};
use battery_notifier::updater::AFTER_UPDATE_FLAG;

/// After an update, the previous version may still be exiting and holding the single-instance lock.
const AFTER_UPDATE_LOCK_ATTEMPTS: u32 = 40;
const LOCK_RETRY_DELAY: Duration = Duration::from_millis(250);

const USAGE: &str = "Usage: battery-notifier [settings [--close-with-tray] | --once]

Notify when battery is low.

Commands:
  settings  open the settings dialog
            --close-with-tray: close when stdin closes, the tray app holds the other end
  --once    print the battery levels once and exit

Started by the updater with --after-update: the tray app, waiting for the previous version to exit.";

fn main() -> ExitCode {
    let command = std::env::args().nth(1);
    let platform = current_platform();
    // Command line output, the tray and the dialog have no console
    if command.as_deref().is_some_and(|command| command != "settings" && command != AFTER_UPDATE_FLAG) {
        platform.attach_console();
    }
    configure_logging();

    match command.as_deref() {
        None | Some(AFTER_UPDATE_FLAG) => {
            let attempts = if command.is_some() { AFTER_UPDATE_LOCK_ATTEMPTS } else { 1 };
            let acquired = (0..attempts).any(|attempt| {
                if attempt > 0 {
                    sleep(LOCK_RETRY_DELAY);
                }
                platform.acquire_single_instance("BatteryNotifier")
            });
            if !acquired {
                tracing::info!("Already running, exiting");
                return ExitCode::SUCCESS;
            }
            tray::run(platform)
        }
        Some("settings") => run_settings_dialog(platform, std::env::args().any(|arg| arg == "--close-with-tray")),
        Some("--once") => {
            print_battery_levels(&*platform);
            ExitCode::SUCCESS
        }
        Some("-h" | "--help") => {
            println!("{USAGE}");
            ExitCode::SUCCESS
        }
        Some(other) => {
            eprintln!("Unknown command: {other}\n\n{USAGE}");
            ExitCode::FAILURE
        }
    }
}

/// Exit code 0 when the settings were saved.
fn run_settings_dialog(platform: std::sync::Arc<dyn Platform>, close_with_tray: bool) -> ExitCode {
    if !platform.acquire_single_instance("BatteryNotifier.Settings") {
        tracing::info!("Settings dialog already open, exiting");
        return ExitCode::FAILURE;
    }
    if settings_dialog::run(platform, Settings::load(), close_with_tray) {
        ExitCode::SUCCESS
    } else {
        ExitCode::FAILURE
    }
}

fn print_battery_levels(platform: &dyn Platform) {
    let bluetooth = platform.bluetooth_batteries();
    let providers: Vec<Box<dyn BatteryProvider>> =
        vec![Box::new(HidProvider::default()), Box::new(OsProvider::new(move || bluetooth.clone()))];
    let readings = Poller::new(providers).poll(&Settings::load());
    if readings.is_empty() {
        println!("No device found");
    }
    for reading in readings {
        println!("{reading}");
    }
}
