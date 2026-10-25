// No console window for the release build on Windows
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::ExitCode;

use battery_notifier::core::poller::Poller;
use battery_notifier::core::providers::{BatteryProvider, HidProvider, OsProvider};
use battery_notifier::core::settings::Settings;
use battery_notifier::logs::configure_logging;
use battery_notifier::platforms::{Platform, current_platform};
use battery_notifier::ui::{settings_dialog, tray};

const USAGE: &str = "Usage: battery-notifier [settings | --once]

Notify when battery is low.

Commands:
  settings  open the settings dialog
  --once    print the battery levels once and exit";

fn main() -> ExitCode {
    let command = std::env::args().nth(1);
    let platform = current_platform();
    // Command line output, the tray and the dialog have no console
    if command.as_deref().is_some_and(|command| command != "settings") {
        platform.attach_console();
    }
    configure_logging();

    match command.as_deref() {
        None => {
            if !platform.acquire_single_instance("BatteryNotifier") {
                tracing::info!("Already running, exiting");
                return ExitCode::SUCCESS;
            }
            tray::run(platform)
        }
        Some("settings") => run_settings_dialog(platform),
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
fn run_settings_dialog(platform: std::sync::Arc<dyn Platform>) -> ExitCode {
    if !platform.acquire_single_instance("BatteryNotifier.Settings") {
        return ExitCode::FAILURE;
    }
    if settings_dialog::run(platform, Settings::load()) { ExitCode::SUCCESS } else { ExitCode::FAILURE }
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
