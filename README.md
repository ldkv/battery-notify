# battery-notifier

## About

A Windows tray app that watches the battery of your wireless devices:

- The tray icon shows the lowest battery level, following the taskbar theme, amber when low and red when critical.
- Hover the icon or right-click it to see the level of each device.
- A notification shows when a device runs low, and repeats while it stays low (configurable).

## Install

Each [release](https://github.com/ldkv/battery-notify/releases/latest) contains:

| File                                              | For                                        |
| ------------------------------------------------- | ------------------------------------------ |
| `battery_notifier_rust-<version>-windows-x64.exe` | Windows, Rust version                      |
| `battery_notifier-<version>-windows-x64.exe`      | Windows, Python version                    |
| `battery_notifier_rust-<version>-macos.zip`       | macOS 11 or later, Apple Silicon and Intel |
| `SHA256SUMS.txt`                                  | Checksums of the files above               |

The Rust and Python versions have the same features and share their settings; the Rust one uses less memory. Only one of them runs at a time.

### Verify a download

Optionally, the hash of a file must match the one in `SHA256SUMS.txt`:

```powershell
certutil -hashfile <file> SHA256   # Windows
shasum -a 256 <file>               # macOS
```

The build provenance can also be verified with the GitHub CLI:

```powershell
gh attestation verify <file> --repo ldkv/battery-notify
```

### Windows

Run the executable. It is not code-signed, so Windows SmartScreen may warn about an unknown publisher: click **More info** → **Run anyway**.

The first launch of each version of the Python executable unpacks it to `%LOCALAPPDATA%\battery-notifier\app\<version>`, later launches reuse it. Folders of previous versions are deleted automatically.

The app runs in the system tray.

### macOS

1. Unzip the file and move `Battery Notifier.app` to Applications: macOS only allows notifications from an app in Applications or `~/Applications`.
2. The app is not notarized by Apple, so macOS blocks its first launch. Open it once, then allow it in **System Settings** → **Privacy & Security** → **Open Anyway**. Alternatively, clear the download's quarantine flag from a terminal: `xattr -dr com.apple.quarantine "/Applications/Battery Notifier.app"`.
3. Allow notifications when asked.

The app lives in the menu bar, without a Dock icon. Bluetooth devices are only supported on Windows.

### Linux: run from source

There is no release for Linux, which is untested. Install [uv](https://docs.astral.sh/uv/) and [Task](https://taskfile.dev/), then:

```bash
git clone https://github.com/ldkv/battery-notify.git
cd battery-notify
task dev-install
uv run battery-notifier
```

To build the Python executable into `dist/` on Windows, run `task generate-executable` (uses [Nuitka](https://nuitka.net/) and a C compiler, e.g. Visual Studio Build Tools). To build and run the Rust version, see [rust/README.md](rust/README.md).

## Settings

Right-click the tray icon → **Settings…** to change the check interval, the low and critical battery levels, how often the low battery notification repeats, which devices are checked, and whether the app runs at startup.

Settings are saved to `config.toml` and logs to `Logs/battery_notifier.log`, both under `%LOCALAPPDATA%\battery-notifier` (**Open settings folder** in the tray menu). On macOS / Linux, they follow the OS conventions of [platformdirs](https://platformdirs.readthedocs.io/).

The dialog can also be opened from a terminal with `battery-notifier settings`.

## Supported devices

- Razer Pro Click Mini
- HyperX Cloud Alpha Wireless
- DualSense controller
- Keychron K2 HE via the 2.4 GHz receiver, with custom firmware: see [docs/keychron-k2-he.md](docs/keychron-k2-he.md)
- Keychron M6 8K via the 2.4 GHz receiver Keychron Ultra-Link 8K, tested on Windows: see [docs/keychron-m6.md](docs/keychron-m6.md)
- Bluetooth devices with battery level on Windows
