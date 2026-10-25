# Battery Notifier in Rust

A port of the Python app, released alongside it: each release contains the Windows executable and the macOS app of this version.

It has the same features and shares its files with the Python version: `config.toml`, the remembered device names and the single-instance lock. Its logs go to `battery_notifier_rust.<date>.log` in the same `Logs` folder. Only one of the two versions can run at a time.

## Build and run

Install [rustup](https://rustup.rs): the toolchain pinned in `rust-toolchain.toml` is installed on first use. On Linux, also install the system libraries for HID and the tray icon:

```sh
sudo apt install build-essential pkg-config libudev-dev libgtk-3-dev libxdo-dev libayatana-appindicator3-dev
```

Then, from the repository root:

```sh
task rust-check  # formatting and lints
task rust-test
task rust-build  # rust/target/release/battery-notifier(.exe)
task rust-build-macos  # rust/target/release/Battery Notifier.app, for Apple Silicon and Intel
```

Run it from `rust/`:

```sh
cargo run              # tray app
cargo run -- settings  # settings dialog
cargo run -- --once    # print the battery levels once
```

CI builds the Windows executable on each pull request, and the macOS app on `main`: download `rust-windows-executable` or `rust-macos-app` from the workflow run's artifacts.

## macOS

The app lives in the menu bar, without a Dock icon. Bluetooth devices are not supported.

- Move `Battery Notifier.app` to Applications or `~/Applications` before opening it: macOS refuses notifications to an app run from elsewhere, e.g. the build folder. The first launch asks to allow notifications.
- Run from source (`cargo run`), there is no app bundle, so notifications go through AppleScript and show as from Script Editor.
- Run at startup writes a LaunchAgent, `~/Library/LaunchAgents/io.github.ldkv.battery-notifier.plist`.
- The app is not notarized: see [Install on macOS](../README.md#macos) to open it after downloading.

## Layout

Same modules as the Python version:

- `core/`: devices, providers, poller, notification policy, settings. No GUI.
- `platforms/`: the `Platform` trait, whose defaults are the unsupported-OS fallback, the Windows implementation (registry, mutex, WinRT Bluetooth) and the macOS one (UserNotifications, LaunchAgent).
- `ui/`: tray icon and menu (`tray-icon` on a `tao` event loop), icon renderer, settings dialog (`egui`, in its own process).

A new device is a `DeviceType` in `core/devices/`, added to `HID_DEVICES`.
