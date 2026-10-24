import pytest

from battery_notifier.core.policy import BatteryStatus, Notifier, battery_status, lowest_level
from battery_notifier.core.providers import BatteryReading
from battery_notifier.core.settings import Settings

SETTINGS = Settings(low_threshold=20, critical_threshold=10, renotify_minutes=60)
HOUR = 60 * 60


def test_lowest_level_ignores_devices_without_level():
    lowest = BatteryReading("Pad", 30)
    readings = [BatteryReading("Mouse", 50), BatteryReading("Headset", None), lowest]
    assert lowest_level(readings) == lowest.level
    assert lowest_level([BatteryReading("Headset", None)]) is None


@pytest.mark.parametrize(
    "level, status",
    [
        (None, BatteryStatus.NORMAL),
        (100, BatteryStatus.NORMAL),
        (21, BatteryStatus.NORMAL),
        (20, BatteryStatus.LOW),
        (11, BatteryStatus.LOW),
        (10, BatteryStatus.CRITICAL),
        (0, BatteryStatus.CRITICAL),
    ],
)
def test_battery_status(level, status):
    assert battery_status(level, SETTINGS) is status


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock():
    return Clock()


def test_notify_once_then_every_renotify_interval(clock):
    notifier = Notifier(clock)
    low = [BatteryReading("Mouse", 15)]

    assert notifier.due(low, SETTINGS) == low
    clock.now = HOUR - 1
    assert notifier.due(low, SETTINGS) == []
    clock.now = HOUR
    assert notifier.due(low, SETTINGS) == low


def test_renotify_disabled(clock):
    notifier = Notifier(clock)
    low = [BatteryReading("Mouse", 15)]
    settings = Settings(renotify_minutes=0)

    assert notifier.due(low, settings) == low
    clock.now = 10 * HOUR
    assert notifier.due(low, settings) == []


def test_notify_again_after_recharging(clock):
    notifier = Notifier(clock)
    low, charged = [BatteryReading("Mouse", 15)], [BatteryReading("Mouse", 80)]

    assert notifier.due(low, SETTINGS) == low
    assert notifier.due(charged, SETTINGS) == []
    assert notifier.due(low, SETTINGS) == low


def test_each_device_is_notified_on_its_own(clock):
    notifier = Notifier(clock)
    mouse, headset = BatteryReading("Mouse", 15), BatteryReading("Headset", 5)

    assert notifier.due([mouse], SETTINGS) == [mouse]
    assert notifier.due([mouse, headset], SETTINGS) == [headset]


def test_device_not_answering_keeps_its_state(clock):
    notifier = Notifier(clock)
    low, unknown = [BatteryReading("Mouse", 15)], [BatteryReading("Mouse", None)]

    assert notifier.due(low, SETTINGS) == low
    assert notifier.due(unknown, SETTINGS) == []
    assert notifier.due(low, SETTINGS) == []
