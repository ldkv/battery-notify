import pytest

from battery_notifier.core.policy import BatteryStatus, battery_status, lowest_level, should_notify
from battery_notifier.core.providers import BatteryReading
from battery_notifier.core.settings import Settings

SETTINGS = Settings(low_threshold=20, critical_threshold=10)


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
    assert should_notify(level, SETTINGS) is (status is not BatteryStatus.NORMAL)
