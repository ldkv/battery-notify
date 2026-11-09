from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Self

from battery_notifier.configs import DEFAULT_BATTERY_LEVEL
from battery_notifier.core.devices.hid_wrapper import DeviceInfo, HIDWrapper
from battery_notifier.logs import logger


@dataclass
class BaseDevice:
    VID: int
    PID: int
    device_info: DeviceInfo
    battery_index: int
    name: str = "BaseDevice"
    type: str = "HID Device"
    battery_message: list[int] | None = field(init=False, default=None)
    battery_level: int = field(init=False, default=DEFAULT_BATTERY_LEVEL)

    def generate_battery_message(self) -> list[int]:
        """Generate message array to send to the device to retrieve battery."""
        return []

    @abstractmethod
    def get_battery_level(self, device: HIDWrapper) -> int:
        """Fetch current battery level of the device."""

    def __post_init__(self):
        if self.device_info.path is None:  # not found by find_all yet
            self.device_info = self.match_device_info()
        self.battery_message = self.generate_battery_message()
        logger.info(f"Device found for {self.name}: {self.device_info=} / {self.battery_message=}")

    def match_device_info(self):
        for device in self.matching_device_infos(self.VID, self.PID, self.device_info):
            return device

        raise Exception(f"Device not found: {self.name}")

    @staticmethod
    def matching_device_infos(VID: int, PID: int, device_info: DeviceInfo) -> list[DeviceInfo]:
        found_devices = HIDWrapper.enumerate_matching_devices(VID, PID, device_info)
        return [device for device in found_devices if device_info.matching_info(device)]

    @classmethod
    def find_all(cls) -> list[Self]:
        """One device per HID collection matching the type, e.g. one per receiver with the same VID/PID."""
        return [
            cls(device_info=device_info)  # pyrefly: ignore[missing-argument]
            for device_info in cls.matching_device_infos(cls.VID, cls.PID, cls.device_info)
        ]

    def update_battery_level(self) -> float:
        """Fetch and update current battery level of the device."""
        if not self.device_info:
            return DEFAULT_BATTERY_LEVEL

        device = HIDWrapper(self.device_info.path)
        self.battery_level = DEFAULT_BATTERY_LEVEL
        if not device:
            return self.battery_level

        try:
            self.battery_level = self.get_battery_level(device)
            logger.info(f"{self.name} - Battery level: {self.battery_level}")
        except Exception as e:
            logger.error(f"{self.name} - Error update_battery_level: {e}")
        finally:
            device.close()

        return self.battery_level
