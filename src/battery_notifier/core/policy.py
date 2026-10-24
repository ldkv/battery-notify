import time
from collections.abc import Callable
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


class Notifier:
    """
    Decide which devices to notify about: when a device drops to the low level,
    then again every `renotify_minutes` while it stays low.
    """

    def __init__(self, clock: Callable[[], float] = time.time):
        self._clock = clock
        self._notified_at: dict[str, float] = {}

    def due(self, readings: list[BatteryReading], settings: Settings) -> list[BatteryReading]:
        now = self._clock()
        due = []
        for reading in readings:
            if reading.level is None:
                continue  # did not answer this time: keep its state
            if battery_status(reading.level, settings) is BatteryStatus.NORMAL:
                self._notified_at.pop(reading.name, None)
                continue
            notified_at = self._notified_at.get(reading.name)
            if notified_at is not None:
                if not settings.renotify_minutes or now - notified_at < settings.renotify_minutes * 60:
                    continue
            self._notified_at[reading.name] = now
            due.append(reading)
        return due
