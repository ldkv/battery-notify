"""
Per-user locations, following each OS convention.
On Windows, everything lives under %LOCALAPPDATA%\\battery-notifier.
"""

from pathlib import Path

from platformdirs import user_config_path, user_log_path, user_state_path

APP_NAME = "battery-notifier"


def config_dir() -> Path:
    return user_config_path(APP_NAME, appauthor=False, roaming=False, ensure_exists=True)


def state_dir() -> Path:
    return user_state_path(APP_NAME, appauthor=False, roaming=False, ensure_exists=True)


def log_dir() -> Path:
    return user_log_path(APP_NAME, appauthor=False, ensure_exists=True)


def config_file() -> Path:
    return config_dir() / "config.toml"


def seen_devices_file() -> Path:
    return state_dir() / "seen_devices.json"
