# Contributing

## Development environment

Install [rustup](https://rustup.rs), the toolchain pinned in `rust-toolchain.toml` is installed on first use, and [Task](https://taskfile.dev/). On Linux, also install the system libraries for HID and the tray icon:

```sh
sudo apt install build-essential pkg-config libudev-dev libgtk-3-dev libxdo-dev libayatana-appindicator3-dev
```

Then:

```sh
task check-all    # formatting, lints and tests
task build        # target/release/battery-notifier(.exe)
task build-macos  # target/release/Battery Notifier.app, for Apple Silicon and Intel

cargo run              # tray app
cargo run -- settings  # settings dialog
cargo run -- --once    # print the battery levels once
```

More tasks are in the [Taskfile](./Taskfile.yml), or listed by `task --list-all`. The code is formatted with `rustfmt` and linted with `clippy`: `task format` and `task lint-fix` fix most issues.

CI builds the Windows executable on each pull request, and the macOS app on `main`: download `battery_notifier_rust-<version>-windows-x64.zip` or `battery_notifier_rust-<version>-macos.zip` from the workflow run's artifacts.

## macOS

- Move `Battery Notifier.app` to Applications or `~/Applications` before opening it: macOS refuses notifications to an app run from elsewhere, e.g. the build folder. The first launch asks to allow notifications.
- Run from source (`cargo run`), there is no app bundle, so notifications go through AppleScript and show as from Script Editor.
- Run at startup writes a LaunchAgent, `~/Library/LaunchAgents/io.github.ldkv.battery-notifier.plist`.

## Updates

The app updates itself from GitHub releases (`src/updater.rs`): it finds the release zip for its platform, checks its signature against `updater-key.pub`, then installs it and restarts with `--after-update`, which waits for the previous version to exit.

On Windows, the zip holds `battery_notifier_rust-<version>.exe`: the updater copies it next to the running exe, which cannot be overwritten, and starts it with `--after-update <previous exe>` so that it deletes the previous version; Run at startup is pointed to the exe on each start. On macOS, it replaces the whole `.app` bundle. Development builds do not check for updates.

The release workflow signs each zip with [zipsign](https://github.com/Kijewski/zipsign), for its file name, using the `ZIPSIGN_PRIVATE_KEY` repository secret, then verifies it against `updater-key.pub`. To create or replace the key pair:

```sh
cargo install zipsign --locked
zipsign gen-key priv.key updater-key.pub
base64 -w0 priv.key   # save as the ZIPSIGN_PRIVATE_KEY repository secret, then delete priv.key
```

Apps only accept updates signed by the key they were built with: after replacing the key, released apps cannot update to the next version and need a manual download.

## Layout

- `src/core/`: devices, providers, poller, notification policy, settings. No GUI.
- `src/platforms/`: the `Platform` trait, whose defaults are the unsupported-OS fallback, the Windows implementation (registry, mutex, WinRT Bluetooth) and the macOS one (UserNotifications, LaunchAgent).
- `src/ui/`: tray icon and menu (`tray-icon` on a `tao` event loop), icon renderer, settings dialog (`egui`, in its own process).
- `assets/`: the app icon, see `scripts/render_app_icon.py`.

A new device is a `DeviceType` in `src/core/devices/`, added to `HID_DEVICES`. Each check reads the devices in parallel, except those with the same VID/PID (e.g. behind one receiver), read one after the other.
