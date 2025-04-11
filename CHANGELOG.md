# Changelog

## Guidelines

https://keepachangelog.com/en/1.0.0/

**Added** for new features.\
**Changed** for changes in existing functionality.\
**Deprecated** for soon-to-be removed features.\
**Removed** for now removed features.\
**Fixed** for any bug fixes.\
**Security** in case of vulnerabilities.

## [Unreleased]

## [0.2.1] - 2025-04-12

### Changed

- Show battery level of all connected Bluetooth devices on Windows

## [0.2.0] - 2025-04-12

### Added

- Module to get battery level of Bluetooth devices on Windows

### Changed

- Move all devices initialization to `all_devices.py`

### Fixed

- HyperX Cloud Alpha Wireless device matching info

## [0.1.0] - 2025-04-09

### Added

- Makefile rule to build executable with PyInstaller
- New field `report_descriptor` to `DeviceInfo`
- Standalone script to debug HID devices and get battery status

### Changed

- Refactor `initialize_all_devices`
- Rename `main.pyw` to main.py
- Generate `uv.lock` file
- Bump `hdiapi` version to `0.14.0.post4`
- Generate `uv.lock`
- Move to `src` as package root
- Update to template v0.5.3

## [0.0.1] - 2024-10-06

### Added

- Base HID device class interface
- Device implementation for mouse `Razer Pro Click Mini`
- Device implementation for headset `HyperX Cloud Alpha Wireless`
- System tray management with `pystray`
- Allow manual update with left click on system tray icon
- Use `uv` for project management
- Wrapper class for `hdiapi` library
- New `configs` module to centralize configuration
- Convert `update_battery_level` method to base class
- New abstract method `get_battery_level` to be implemented by device classes
- Main entrypoint is converted to `pyw` for Windows compatibility
- Log to file with rotating file handler
