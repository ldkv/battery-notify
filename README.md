[![Copier](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-grayscale-inverted-border-orange.json)](https://github.com/copier-org/copier)

# battery-notifier

This repository is generated and synced from [template-python-package](https://github.com/veesion-io/template-python-package).

## About

Notify when battery is low

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

The app runs in the system tray. Logs are written to `battery_notifier.log` in the working directory.

### macOS / Linux: run from source

There is no official release for macOS or Linux. These platforms are untested, and Bluetooth devices are only supported on Windows.

Install [uv](https://docs.astral.sh/uv/) and [Task](https://taskfile.dev/), then:

```bash
git clone https://github.com/ldkv/battery-notify.git
cd battery-notify
task dev-install
uv run battery-notifier
```

To build a standalone executable into `dist/`, run `task generate-executable`.

## Supported devices

- Razer Pro Click Mini
- HyperX Cloud Alpha Wireless
- DualSense controller
- Keychron K2 HE via the 2.4 GHz receiver, with custom firmware: see [docs/keychron-k2-he.md](docs/keychron-k2-he.md)
- Bluetooth devices with battery level on Windows

## Battery icons

Assets downloaded from [flaticon](https://www.flaticon.com/).
