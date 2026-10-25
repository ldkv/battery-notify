# battery-notifier

## About

A Windows tray app that watches the battery of your wireless devices:

- The tray icon shows the lowest battery level, following the taskbar theme, amber when low and red when critical.
- Hover the icon or right-click it to see the level of each device.
- A notification shows when a device runs low, and repeats while it stays low (configurable).

## Install

### Windows

1. Download `battery_notifier-<version>-windows-x64.exe` and `SHA256SUMS.txt` from the [latest release](https://github.com/ldkv/battery-notify/releases/latest).
2. Optionally verify the download: the hash printed by the command below must match the one in `SHA256SUMS.txt`.

   ```powershell
   certutil -hashfile battery_notifier-<version>-windows-x64.exe SHA256
   ```

   The build provenance can also be verified with the GitHub CLI:

   ```powershell
   gh attestation verify battery_notifier-<version>-windows-x64.exe --repo ldkv/battery-notify
   ```

3. Run the executable. It is not code-signed, so Windows SmartScreen may warn about an unknown publisher: click **More info** → **Run anyway**.

   The first launch of each version unpacks the app to `%LOCALAPPDATA%\battery-notifier\app\<version>`, later launches reuse it. Folders of previous versions are deleted automatically.

The app runs in the system tray. Only one instance runs at a time.

### macOS / Linux: run from source

There is no official release for macOS or Linux. These platforms are untested, and Bluetooth devices are only supported on Windows.

Install [uv](https://docs.astral.sh/uv/) and [Task](https://taskfile.dev/), then:

```bash
git clone https://github.com/ldkv/battery-notify.git
cd battery-notify
task dev-install
uv run battery-notifier
```

To build the standalone executable into `dist/` on Windows, run `task generate-executable` (uses [Nuitka](https://nuitka.net/) and a C compiler, e.g. Visual Studio Build Tools).

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
