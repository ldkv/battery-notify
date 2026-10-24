"""
User settings, stored as TOML.
Each field carries its own label and limits in `metadata`: the settings dialog is generated from them.
"""

import os
import tomllib
import typing
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Any

import tomli_w

from battery_notifier.core.paths import config_file
from battery_notifier.logs import logger

RANGE_ERROR = "Must be between {min} and {max}"
THRESHOLD_ERROR = "Must be below the low battery level"


def setting(default: Any, label: str, help_text: str = "", **limits: int) -> Any:
    """Declare a setting with its dialog label, help text and optional `min` / `max` limits."""
    return field(default=default, metadata={"label": label, "help": help_text, **limits})


@dataclass(frozen=True)
class Settings:
    check_interval_minutes: int = setting(10, "Check interval (minutes)", min=1, max=120)
    low_threshold: int = setting(20, "Low battery (%)", "Notify when a device drops to this level", min=1, max=99)
    critical_threshold: int = setting(10, "Critical battery (%)", min=1, max=99)
    disabled_devices: frozenset[str] = setting(frozenset(), "Devices", "Unchecked devices are ignored")

    def validate(self) -> dict[str, str]:
        """Return an error message per invalid field name."""
        errors = {}
        for setting_field in fields(self):
            value = getattr(self, setting_field.name)
            low, high = setting_field.metadata.get("min"), setting_field.metadata.get("max")
            if low is not None and high is not None and not low <= value <= high:
                errors[setting_field.name] = RANGE_ERROR.format(min=low, max=high)

        if "critical_threshold" not in errors and self.critical_threshold >= self.low_threshold:
            errors["critical_threshold"] = THRESHOLD_ERROR
        return errors

    def is_enabled(self, device_name: str) -> bool:
        return device_name not in self.disabled_devices

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        """Load settings, falling back to the default of every missing or invalid value."""
        path = path or config_file()
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls()
        except (OSError, tomllib.TOMLDecodeError) as e:
            logger.warning(f"Invalid settings file {path}, using defaults: {e}")
            return cls()

        values = {}
        hints = typing.get_type_hints(cls)
        for setting_field in fields(cls):
            if setting_field.name not in data:
                continue
            value = _parse(data[setting_field.name], hints[setting_field.name])
            if value is None:
                logger.warning(f"Invalid setting {setting_field.name}={data[setting_field.name]!r}, using default")
                continue
            values[setting_field.name] = value

        settings = cls(**values)
        if errors := settings.validate():
            logger.warning(f"Invalid settings, using defaults for: {errors}")
            defaults = cls()
            settings = replace(settings, **{name: getattr(defaults, name) for name in errors})
        # Resetting one field may still conflict with another one: give up on the whole file
        return cls() if settings.validate() else settings

    def save(self, path: Path | None = None):
        """Write atomically, so a crash never leaves a half-written file."""
        path = path or config_file()
        data = {}
        for setting_field in fields(self):
            value = getattr(self, setting_field.name)
            data[setting_field.name] = sorted(value) if isinstance(value, frozenset) else value
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(tomli_w.dumps(data), encoding="utf-8")
        os.replace(temp_path, path)


def _parse(value: Any, expected_type: Any) -> Any:
    if expected_type is int:
        return value if isinstance(value, int) and not isinstance(value, bool) else None
    if typing.get_origin(expected_type) is frozenset:
        is_strings = isinstance(value, list) and all(isinstance(item, str) for item in value)
        return frozenset(value) if is_strings else None
    raise TypeError(f"Unsupported setting type: {expected_type}")
