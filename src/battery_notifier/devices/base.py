from abc import abstractmethod
from dataclasses import dataclass, field

from battery_notifier.configs import DEFAULT_BATTERY_LEVEL
from battery_notifier.devices.hid_wrapper import DeviceInfo, HIDWrapper
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
        self.device_info = self.match_device_info()
        self.battery_message = self.generate_battery_message()
        logger.info(f"Device found for {self.name}: {self.device_info=} / {self.battery_message=}")

    def match_device_info(self):
        found_devices = HIDWrapper.enumerate_matching_devices(self.VID, self.PID)
        for device in found_devices:
            if self.device_info.matching_info(device):
                return device

        raise Exception(f"Device not found: {self.name}")

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
