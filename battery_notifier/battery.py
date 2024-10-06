from enum import Enum
from pathlib import Path

ASSET_PATH = Path("assets/")


class BatteryThreshold(Enum):
    CRITICAL = 10
    LOW = 20
    MEDIUM = 60
    FULL = 100

    @classmethod
    def ascending_order(cls) -> list["BatteryThreshold"]:
        return sorted(list(cls), key=lambda threshold: threshold.value)

    @classmethod
    def default(cls) -> Path:
        return cls.icon(cls.FULL)

    @classmethod
    def get_battery_threshold(cls, battery_level: float) -> "BatteryThreshold":
        for threshold in cls.ascending_order():
            if battery_level <= threshold.value:
                return threshold

    def icon(self) -> Path:
        return ASSET_PATH / f"battery-{self.name.lower()}.png"

    @classmethod
    def validate_battery_icons(cls):
        for threshold in list(cls):
            if not (ASSET_PATH / f"battery-{threshold.name.lower()}.png").exists():
                raise FileNotFoundError(f"Icon not found: {threshold.name}")

    def should_notify(self) -> bool:
        return self in (self.CRITICAL, self.LOW)
