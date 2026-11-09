"""Sources of battery readings: HID devices with a driver, and devices the OS reports (e.g. Bluetooth)."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from battery_notifier.configs import DEFAULT_BATTERY_LEVEL
from battery_notifier.core.devices.base import BaseDevice
from battery_notifier.core.devices.dualsense import DualSense
from battery_notifier.core.devices.headset import HyperXCloudAlphaWireless
from battery_notifier.core.devices.keyboard import KeychronK2HE
from battery_notifier.core.devices.mouse import KeychronM6, RazerProClickMini
from battery_notifier.core.settings import Settings
from battery_notifier.logs import logger

HID_DEVICES: list[type[BaseDevice]] = [RazerProClickMini, HyperXCloudAlphaWireless, DualSense, KeychronK2HE, KeychronM6]


@dataclass(frozen=True)
class BatteryReading:
    name: str
    level: int | None  # None when the device did not answer


class BatteryProvider(Protocol):
    def read(self, settings: Settings) -> list[BatteryReading]: ...


class HIDProvider:
    """
    Devices are looked up once found, and searched again on each read until then.
    A stored device that does not answer is searched again right away: it may have come back under
    a new path, e.g. after the computer slept, and the stored one would keep failing.
    """

    def __init__(self):
        self._devices: dict[str, BaseDevice] = {}

    @staticmethod
    def device_names() -> list[str]:
        return [device_class.name for device_class in HID_DEVICES]

    def read(self, settings: Settings) -> list[BatteryReading]:
        readings = []
        for device_class in HID_DEVICES:
            if not settings.is_enabled(device_class.name):
                continue
            level = self._level(device_class)
            if level is not None:
                readings.append(BatteryReading(device_class.name, None if level == DEFAULT_BATTERY_LEVEL else level))
        return readings

    def _level(self, device_class: type[BaseDevice]) -> int | None:
        """None when the device is not found."""
        device = self._devices.get(device_class.name)
        if device is not None:
            level = int(device.update_battery_level())
            if level != DEFAULT_BATTERY_LEVEL:
                return level
            logger.info(f"No answer from {device_class.name}, searching it again")
            del self._devices[device_class.name]
        return self._search(device_class)

    def _search(self, device_class: type[BaseDevice]) -> int | None:
        """
        Keep the first matching device that answers: several HID collections can match a device type,
        e.g. two receivers with the same VID/PID, only one of them paired with the device.
        """
        try:
            devices = device_class.find_all()
        except Exception as e:
            logger.info(f"Error searching {device_class.name}: {e}")
            return None
        if not devices:
            logger.info(f"Device not found: {device_class.name}")
            return None

        for device in devices:
            level = int(device.update_battery_level())
            if level != DEFAULT_BATTERY_LEVEL:
                logger.info(f"Device found for {device_class.name}: {device.device_info.path}")
                self._devices[device_class.name] = device
                return level
        return DEFAULT_BATTERY_LEVEL


class OSProvider:
    """Devices whose battery level the OS already knows, e.g. paired Bluetooth devices."""

    def __init__(self, read_batteries: Callable[[], list[tuple[str, int]]]):
        self._read_batteries = read_batteries

    def read(self, settings: Settings) -> list[BatteryReading]:
        return [BatteryReading(name, level) for name, level in self._read_batteries() if settings.is_enabled(name)]
