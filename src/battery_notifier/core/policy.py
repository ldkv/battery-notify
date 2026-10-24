from enum import Enum

from battery_notifier.core.providers import BatteryReading
from battery_notifier.core.settings import Settings


class BatteryStatus(Enum):
    NORMAL = "normal"
    LOW = "low"
    CRITICAL = "critical"


def lowest_level(readings: list[BatteryReading]) -> int | None:
    levels = [reading.level for reading in readings if reading.level is not None]
    return min(levels, default=None)


def battery_status(level: int | None, settings: Settings) -> BatteryStatus:
    if level is None or level > settings.low_threshold:
        return BatteryStatus.NORMAL
    if level > settings.critical_threshold:
        return BatteryStatus.LOW
    return BatteryStatus.CRITICAL


def should_notify(level: int | None, settings: Settings) -> bool:
    return battery_status(level, settings) is not BatteryStatus.NORMAL
