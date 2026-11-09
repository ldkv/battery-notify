use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{self, Receiver, RecvTimeoutError, Sender};
use std::sync::{Arc, Mutex, PoisonError};
use std::thread;
use std::time::{Duration, Instant};

use tao::event::{Event, StartCause};
use tao::event_loop::{ControlFlow, EventLoopBuilder, EventLoopProxy};
use tray_icon::menu::{Menu, MenuEvent, MenuItem, PredefinedMenuItem};
use tray_icon::{Icon, MouseButton, MouseButtonState, TrayIcon, TrayIconBuilder, TrayIconEvent};

use crate::VERSION;
use crate::core::paths::config_dir;
use crate::core::policy::{BatteryStatus, Notifier, battery_status, lowest_level};
use crate::core::poller::Poller;
use crate::core::providers::{BatteryProvider, BatteryReading, HidProvider, OsProvider};
use crate::core::settings::Settings;
use crate::platforms::Platform;
use crate::ui::icon::{IconImage, SIZE, icon_renderer};
use crate::updater::{self, AvailableUpdate, RELEASES_PAGE};

const NO_DEVICE_TEXT: &str = "No device found yet";
const REFRESH_ID: &str = "refresh";
const SETTINGS_ID: &str = "settings";
const OPEN_FOLDER_ID: &str = "open_folder";
const QUIT_ID: &str = "quit";
const UPDATE_ID: &str = "update";
const UPDATE_CHECK_INTERVAL: Duration = Duration::from_hours(24);

enum UserEvent {
    Readings(Vec<BatteryReading>, IconImage),
    Menu(MenuEvent),
    Tray(TrayIconEvent),
    UpdateAvailable(AvailableUpdate),
    /// The new version is in place: start it with this command, then exit.
    UpdateInstalled(Command),
    UpdateFailed(String),
}

/// What the tray menu shows besides its fixed items.
#[derive(Default)]
struct MenuState {
    readings: Vec<BatteryReading>,
    update: Option<AvailableUpdate>,
    updating: bool,
}

type SharedSettings = Arc<Mutex<Settings>>;

fn current(settings: &SharedSettings) -> Settings {
    settings.lock().unwrap_or_else(PoisonError::into_inner).clone()
}

pub fn run(platform: Arc<dyn Platform>) -> ! {
    // Keep "run at startup" pointing to this executable, e.g. after an update
    if cfg!(not(debug_assertions))
        && platform.is_autostart_enabled()
        && let Err(e) = platform.set_autostart(true)
    {
        tracing::warn!("Could not update run at startup: {e}");
    }
    platform.register_notifications();

    let settings: SharedSettings = Arc::new(Mutex::new(Settings::load()));
    #[cfg_attr(not(target_os = "macos"), allow(unused_mut))]
    let mut event_loop = EventLoopBuilder::<UserEvent>::with_user_event().build();
    // No Dock icon: the app lives in the menu bar
    #[cfg(target_os = "macos")]
    tao::platform::macos::EventLoopExtMacOS::set_activation_policy(
        &mut event_loop,
        tao::platform::macos::ActivationPolicy::Accessory,
    );
    let proxy = event_loop.create_proxy();
    let menu_proxy = proxy.clone();
    MenuEvent::set_event_handler(Some(move |event| {
        let _ = menu_proxy.send_event(UserEvent::Menu(event));
    }));
    let tray_proxy = proxy.clone();
    TrayIconEvent::set_event_handler(Some(move |event| {
        let _ = tray_proxy.send_event(UserEvent::Tray(event));
    }));

    // Send to check the batteries right away instead of waiting for the next check
    let (wake, wake_receiver) = mpsc::channel();
    let mut wake_receiver = Some(wake_receiver);
    let mut tray: Option<TrayIcon> = None;
    let mut menu = MenuState::default();
    let dialog_open = Arc::new(AtomicBool::new(false));

    event_loop.run(move |event, _, control_flow| {
        *control_flow = ControlFlow::Wait;
        match event {
            // Create the tray icon once the event loop runs, as tray-icon requires on macOS
            Event::NewEvents(StartCause::Init) => {
                let theme_platform = platform.clone();
                let renderer = icon_renderer(platform.icon_font(), move || theme_platform.taskbar_uses_dark_theme());
                tray = build_tray(renderer.render(None, &current(&settings)));
                if let Some(wake_receiver) = wake_receiver.take() {
                    start_background_loops(&platform, &settings, wake_receiver, &proxy);
                }
            }
            Event::UserEvent(UserEvent::Readings(readings, icon)) => {
                menu.readings = readings;
                if let Some(tray) = &tray {
                    update_tray(tray, &menu, icon);
                }
            }
            Event::UserEvent(UserEvent::UpdateAvailable(update)) => {
                menu.update = Some(update);
                refresh_menu(tray.as_ref(), &menu);
            }
            Event::UserEvent(UserEvent::UpdateInstalled(mut command)) => match command.spawn() {
                Ok(_) => {
                    tracing::info!("Updated, starting the new version");
                    *control_flow = ControlFlow::Exit;
                }
                Err(e) => {
                    menu.updating = false;
                    refresh_menu(tray.as_ref(), &menu);
                    update_failed(platform.as_ref(), &format!("could not start the new version: {e}"));
                }
            },
            Event::UserEvent(UserEvent::UpdateFailed(error)) => {
                menu.updating = false;
                refresh_menu(tray.as_ref(), &menu);
                update_failed(platform.as_ref(), &error);
            }
            Event::UserEvent(UserEvent::Tray(TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            })) => {
                let _ = wake.send(());
            }
            Event::UserEvent(UserEvent::Menu(event)) => match event.id().as_ref() {
                REFRESH_ID => {
                    let _ = wake.send(());
                }
                SETTINGS_ID => open_settings(&dialog_open, &settings, &wake),
                OPEN_FOLDER_ID => platform.open_folder(&config_dir()),
                UPDATE_ID => {
                    if let Some(update) = menu.update.clone().filter(|_| !menu.updating) {
                        menu.updating = true;
                        refresh_menu(tray.as_ref(), &menu);
                        install_update(update, proxy.clone());
                    }
                }
                QUIT_ID => *control_flow = ControlFlow::Exit,
                _ => {}
            },
            _ => {}
        }
    })
}

fn tray_icon(image: IconImage) -> Option<Icon> {
    Icon::from_rgba(image.rgba, SIZE, SIZE).inspect_err(|e| tracing::error!("Invalid tray icon: {e}")).ok()
}

fn build_tray(icon: IconImage) -> Option<TrayIcon> {
    let mut builder = TrayIconBuilder::new()
        .with_tooltip(NO_DEVICE_TEXT)
        .with_menu(Box::new(build_menu(&MenuState::default())))
        .with_menu_on_left_click(false);
    if let Some(icon) = tray_icon(icon) {
        builder = builder.with_icon(icon);
    }
    builder.build().inspect_err(|e| tracing::error!("Could not create the tray icon: {e}")).ok()
}

fn build_menu(state: &MenuState) -> Menu {
    let menu = Menu::new();
    let mut items: Vec<MenuItem> =
        state.readings.iter().map(|reading| MenuItem::new(reading.to_string(), false, None)).collect();
    if state.readings.is_empty() {
        items.push(MenuItem::new(NO_DEVICE_TEXT, false, None));
    }
    let update = state.update.as_ref().map(|update| {
        if state.updating {
            MenuItem::new(format!("Updating to {}…", update.version), false, None)
        } else {
            MenuItem::with_id(UPDATE_ID, format!("Update to {}", update.version), true, None)
        }
    });
    let appended = items
        .iter()
        .try_for_each(|item| menu.append(item))
        .and_then(|()| menu.append(&PredefinedMenuItem::separator()))
        .and_then(|()| menu.append(&MenuItem::with_id(REFRESH_ID, "Refresh", true, None)))
        .and_then(|()| menu.append(&MenuItem::with_id(SETTINGS_ID, "Settings…", true, None)))
        .and_then(|()| menu.append(&MenuItem::with_id(OPEN_FOLDER_ID, "Open settings folder", true, None)))
        .and_then(|()| menu.append(&PredefinedMenuItem::separator()))
        .and_then(|()| update.as_ref().map_or(Ok(()), |item| menu.append(item)))
        .and_then(|()| menu.append(&MenuItem::new(format!("Battery Notifier v{VERSION}"), false, None)))
        .and_then(|()| menu.append(&MenuItem::with_id(QUIT_ID, "Quit", true, None)));
    if let Err(e) = appended {
        tracing::error!("Could not build the tray menu: {e}");
    }
    menu
}

/// Update tray icon, tooltip and menu from the devices' battery levels.
fn update_tray(tray: &TrayIcon, state: &MenuState, icon: IconImage) {
    let tooltip = tooltip(&state.readings);
    if let Err(e) = tray.set_tooltip(Some(tooltip)).and_then(|()| tray.set_icon(tray_icon(icon))) {
        tracing::error!("Could not update the tray icon: {e}");
    }
    refresh_menu(Some(tray), state);
}

fn refresh_menu(tray: Option<&TrayIcon>, state: &MenuState) {
    if let Some(tray) = tray {
        tray.set_menu(Some(Box::new(build_menu(state))));
    }
}

fn tooltip(readings: &[BatteryReading]) -> String {
    if readings.is_empty() {
        return NO_DEVICE_TEXT.to_string();
    }
    readings.iter().map(ToString::to_string).collect::<Vec<_>>().join("\n")
}

/// Separate thread to check battery levels of all devices.
fn device_loop(
    platform: &Arc<dyn Platform>,
    settings: &SharedSettings,
    wake: &Receiver<()>,
    proxy: &EventLoopProxy<UserEvent>,
) {
    let bluetooth_platform = platform.clone();
    let providers: Vec<Box<dyn BatteryProvider>> = vec![
        Box::new(HidProvider::default()),
        Box::new(OsProvider::new(move || bluetooth_platform.bluetooth_batteries())),
    ];
    let mut poller = Poller::new(providers);
    let theme_platform = platform.clone();
    let renderer = icon_renderer(platform.icon_font(), move || theme_platform.taskbar_uses_dark_theme());
    let mut notifier = Notifier::default();
    loop {
        let settings = current(settings);
        let readings = poller.poll(&settings);
        let icon = renderer.render(lowest_level(&readings), &settings);
        if proxy.send_event(UserEvent::Readings(readings.clone(), icon)).is_err() {
            return; // the event loop has exited
        }
        let due = notifier.due(&readings, &settings, Instant::now());
        if !due.is_empty() {
            notify(platform.as_ref(), &due, &settings);
        }

        let interval = Duration::from_secs(u64::try_from(settings.check_interval_minutes).unwrap_or(1) * 60);
        tracing::info!("Next check in {} seconds...", interval.as_secs());
        if let Err(RecvTimeoutError::Disconnected) = wake.recv_timeout(interval) {
            return;
        }
        while wake.try_recv().is_ok() {} // several wake-ups in a row only need one check
    }
}

fn notify(platform: &dyn Platform, due: &[BatteryReading], settings: &Settings) {
    let critical = due.iter().any(|reading| battery_status(reading.level, settings) == BatteryStatus::Critical);
    platform.show_notification(if critical { "Critical battery" } else { "Low battery" }, &tooltip(due));
}

/// Open the settings dialog in its own process, and reload the settings once it saved them.
fn open_settings(dialog_open: &Arc<AtomicBool>, settings: &SharedSettings, wake: &Sender<()>) {
    if dialog_open.swap(true, Ordering::SeqCst) {
        return;
    }
    // The dialog closes itself when its stdin closes, i.e. when the tray app quits or crashes
    let child = std::env::current_exe()
        .and_then(|exe| Command::new(exe).args(["settings", "--close-with-tray"]).stdin(Stdio::piped()).spawn());
    let mut child = match child {
        Ok(child) => child,
        Err(e) => {
            tracing::error!("Could not open the settings dialog: {e}");
            dialog_open.store(false, Ordering::SeqCst);
            return;
        }
    };
    let (dialog_open, settings, wake) = (dialog_open.clone(), settings.clone(), wake.clone());
    thread::spawn(move || {
        // Keep the dialog's stdin open while it runs: Child::wait closes it before waiting
        let _tray_end = child.stdin.take();
        let saved = child.wait().is_ok_and(|status| status.success());
        dialog_open.store(false, Ordering::SeqCst);
        if saved {
            let reloaded = Settings::load();
            tracing::info!("Settings reloaded: {reloaded:?}");
            *settings.lock().unwrap_or_else(PoisonError::into_inner) = reloaded;
            let _ = wake.send(());
        }
    });
}

/// Separate thread to look for a newer release, now and then every day.
fn update_loop(platform: &Arc<dyn Platform>, proxy: &EventLoopProxy<UserEvent>) {
    let mut notified: Option<String> = None;
    loop {
        match updater::check() {
            Ok(Some(update)) => {
                if notified.as_ref() != Some(&update.version) {
                    tracing::info!("Update available: {}", update.version);
                    platform.show_notification(
                        "Update available",
                        &format!(
                            "Battery Notifier {} is available: choose Update in the menu to install it.",
                            update.version
                        ),
                    );
                    notified = Some(update.version.clone());
                }
                if proxy.send_event(UserEvent::UpdateAvailable(update)).is_err() {
                    return; // the event loop has exited
                }
            }
            Ok(None) => tracing::info!("No update available"),
            Err(e) => tracing::warn!("Could not check for updates: {e}"),
        }
        thread::sleep(UPDATE_CHECK_INTERVAL);
    }
}

fn install_update(update: AvailableUpdate, proxy: EventLoopProxy<UserEvent>) {
    let spawned = thread::Builder::new().name("update_install".to_string()).spawn(move || {
        tracing::info!("Installing update {}", update.version);
        let event = match updater::install(&update) {
            Ok(command) => UserEvent::UpdateInstalled(command),
            Err(e) => UserEvent::UpdateFailed(e.to_string()),
        };
        let _ = proxy.send_event(event);
    });
    if let Err(e) = spawned {
        tracing::error!("Could not start the update: {e}");
    }
}

fn update_failed(platform: &dyn Platform, error: &str) {
    tracing::error!("Update failed: {error}");
    platform.show_notification("Update failed", &format!("{error}. Opening the release page to download it."));
    platform.open_url(RELEASES_PAGE);
}

/// Battery checks, and update checks except in development builds, which must not replace the built binary.
fn start_background_loops(
    platform: &Arc<dyn Platform>,
    settings: &SharedSettings,
    wake_receiver: Receiver<()>,
    proxy: &EventLoopProxy<UserEvent>,
) {
    let (device_platform, settings, device_proxy) = (platform.clone(), settings.clone(), proxy.clone());
    let spawned = thread::Builder::new()
        .name("device_loop".to_string())
        .spawn(move || device_loop(&device_platform, &settings, &wake_receiver, &device_proxy));
    if let Err(e) = spawned {
        tracing::error!("Could not start the device loop: {e}");
    }
    if cfg!(not(debug_assertions)) {
        let (platform, proxy) = (platform.clone(), proxy.clone());
        let spawned =
            thread::Builder::new().name("update_check".to_string()).spawn(move || update_loop(&platform, &proxy));
        if let Err(e) = spawned {
            tracing::error!("Could not start the update checks: {e}");
        }
    }
}
