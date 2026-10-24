# Battery Notifier in Rust

A port of the Python app, not released yet: the Python version stays the released one until this one reaches parity and is tested on Windows.

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
```

Run it from `rust/`:

```sh
cargo run              # tray app
cargo run -- settings  # settings dialog
cargo run -- --once    # print the battery levels once
```

CI builds the Windows executable on each pull request: download `rust-windows-executable` from the workflow run's artifacts.

## Layout

Same modules as the Python version:

- `core/`: devices, providers, poller, notification policy, settings. No GUI.
- `platforms/`: the `Platform` trait, whose defaults are the unsupported-OS fallback, and the Windows implementation (registry, mutex, WinRT Bluetooth).
- `ui/`: tray icon and menu (`tray-icon` on a `tao` event loop), icon renderer, settings dialog (`egui`, in its own process).

A new device is a `DeviceType` in `core/devices/`, added to `HID_DEVICES`.
