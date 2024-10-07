from enum import Enum
from pathlib import Path

from battery_notifier.configs import NOTIFICATION_THRESHOLD, image_path


class BatteryThreshold(Enum):
    CRITICAL = 10
    LOW = 20
    MEDIUM = 60
    FULL = 100

    @classmethod
    def ascending_order(cls) -> list["BatteryThreshold"]:
        return sorted(cls, key=lambda threshold: threshold.value)

    @classmethod
    def default(cls) -> Path:
        return cls.icon(cls.FULL)

    @classmethod
    def get_battery_threshold(cls, battery_level: float) -> "BatteryThreshold":
        for threshold in cls.ascending_order():
            if battery_level <= threshold.value:
                return threshold

        return cls.CRITICAL

    def icon(self) -> Path:
        filename = f"battery-{self.name.lower()}.png"
        return image_path(filename)

    @classmethod
    def validate_battery_icons(cls):
        for threshold in list(cls):
            if not threshold.icon().exists():
                raise FileNotFoundError(f"Icon not found: {threshold.name}")

    @staticmethod
    def should_notify(battery_level: float) -> bool:
        return battery_level <= NOTIFICATION_THRESHOLD
