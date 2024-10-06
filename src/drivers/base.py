import time
from abc import abstractmethod
from dataclasses import dataclass

import hid


@dataclass
class DeviceInfo:
    path: str
    vendor_id: int
    product_id: int
    interface_number: int
    manufacturer_string: str
    product_string: str
    serial_number: str
    release_number: int
    usage: int
    usage_page: int
    bus_type: int


@dataclass
class BaseDevice:
    VID: int
    PID: int
    interface_number: int
    message_size: int
    battery_index: int
    name: str = "BaseDevice"

    @abstractmethod
    def generate_battery_message(self) -> list[int]:
        """Generate message array to send to the device to retrieve battery."""

    def __post_init__(self):
        self.device_info = self.get_device()
        if not self.device_info:
            raise Exception(f"Device not found: {self.name}")

        self.battery_message = self.generate_battery_message()
        message_length = len(self.battery_message)
        if message_length != self.message_size:
            raise ValueError(
                f"Invalid message: {message_length=} / {self.message_size=}"
            )

    def get_device(self) -> DeviceInfo | None:
        found_devices = hid.enumerate(self.VID, self.PID)
        for device in found_devices:
            if device["interface_number"] == self.interface_number:
                return DeviceInfo(**device)

        return None

    def get_battery_level(self) -> float:
        device = hid.device()
        device.open_path(self.device_info.path)
        res = device.send_feature_report(self.battery_message)
        print(f"Erorr code: {device.error()}")
        time.sleep(0.4)
        res = device.get_feature_report(0, self.message_size)
        battery_level = round(res[self.battery_index] / 255 * 100, 2)
        device.close()

        return battery_level
