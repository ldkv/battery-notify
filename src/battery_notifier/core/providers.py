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
    """Devices are looked up once found, and searched again on each read until then."""

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
            device = self._find(device_class)
            if device is None:
                continue
            level = int(device.update_battery_level())
            readings.append(BatteryReading(device.name, None if level == DEFAULT_BATTERY_LEVEL else level))
        return readings

    def _find(self, device_class: type[BaseDevice]) -> BaseDevice | None:
        if device_class.name not in self._devices:
            try:
                self._devices[device_class.name] = device_class()  # pyrefly: ignore[missing-argument]
                logger.info(f"Initialized {device_class.name}")
            except Exception as e:
                logger.info(f"Error initializing {device_class.name}: {e}")
        return self._devices.get(device_class.name)


class OSProvider:
    """Devices whose battery level the OS already knows, e.g. paired Bluetooth devices."""

    def __init__(self, read_batteries: Callable[[], list[tuple[str, int]]]):
        self._read_batteries = read_batteries

    def read(self, settings: Settings) -> list[BatteryReading]:
        return [BatteryReading(name, level) for name, level in self._read_batteries() if settings.is_enabled(name)]
