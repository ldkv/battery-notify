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

### Changed

- Refactor `initialize_all_devices`
- Rename `main.pyw` to main.py
- Generate `uv.lock` file
- Bump `hdiapi` version to `0.14.0.post4`
- Generate `uv.lock`
- Move to `src` as package root

## [0.0.1] - 2023-10-06

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
