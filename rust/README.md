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

CI builds the Windows executable on each pull request, and the macOS app on `main`: download `battery_notifier_rust-<version>-windows-x64.zip` or `battery_notifier_rust-<version>-macos.zip` from the workflow run's artifacts.

## macOS

The app lives in the menu bar, without a Dock icon. Bluetooth devices are not supported.

- Move `Battery Notifier.app` to Applications or `~/Applications` before opening it: macOS refuses notifications to an app run from elsewhere, e.g. the build folder. The first launch asks to allow notifications.
- Run from source (`cargo run`), there is no app bundle, so notifications go through AppleScript and show as from Script Editor.
- Run at startup writes a LaunchAgent, `~/Library/LaunchAgents/io.github.ldkv.battery-notifier.plist`.
- The app is not notarized: see [Install on macOS](../README.md#macos) to open it after downloading.

## Updates

The app updates itself from GitHub releases (`src/updater.rs`): it finds the release zip for its platform, checks its signature against `updater-key.pub`, then installs it and restarts with `--after-update`, which waits for the previous version to exit. On Windows, the zip holds `battery_notifier_rust-<version>.exe`: the updater copies it next to the running exe, which cannot be overwritten, and starts it with `--after-update <previous exe>` so that it deletes the previous version; Run at startup is pointed to the exe on each start. On macOS, it replaces the whole `.app` bundle. Development builds do not check for updates.

The release workflow signs each Rust zip with [zipsign](https://github.com/Kijewski/zipsign), for its file name, using the `ZIPSIGN_PRIVATE_KEY` repository secret, then verifies it against `updater-key.pub`. To create or replace the key pair:

```sh
cargo install zipsign --locked
zipsign gen-key priv.key rust/updater-key.pub
base64 -w0 priv.key   # save as the ZIPSIGN_PRIVATE_KEY repository secret, then delete priv.key
```

Apps only accept updates signed by the key they were built with: after replacing the key, released apps cannot update to the next version and need a manual download.

## Layout

Same modules as the Python version:

- `core/`: devices, providers, poller, notification policy, settings. No GUI.
- `platforms/`: the `Platform` trait, whose defaults are the unsupported-OS fallback, the Windows implementation (registry, mutex, WinRT Bluetooth) and the macOS one (UserNotifications, LaunchAgent).
- `ui/`: tray icon and menu (`tray-icon` on a `tao` event loop), icon renderer, settings dialog (`egui`, in its own process).

A new device is a `DeviceType` in `core/devices/`, added to `HID_DEVICES`.
