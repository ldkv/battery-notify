import logging
from abc import abstractmethod
from dataclasses import dataclass, field

import hid


@dataclass(frozen=True)
class DeviceInfo:
    path: str | None = None
    vendor_id: int | None = None
    product_id: int | None = None
    interface_number: int | None = None
    manufacturer_string: str | None = None
    product_string: str | None = None
    serial_number: str | None = None
    release_number: int | None = None
    usage: int | None = None
    usage_page: int | None = None
    bus_type: int | None = None

    def check_match(self, device: dict) -> bool:
        for key, device_value in device.items():
            matching_value = getattr(self, key, None)
            if matching_value is not None and device_value != matching_value:
                return False

        return True


@dataclass
class BaseDevice:
    VID: int
    PID: int
    matching_device: DeviceInfo
    battery_index: int
    name: str = "BaseDevice"
    type: str = "HID Device"
    device_info: DeviceInfo | None = field(init=False, default=None)
    battery_message: list[int] | None = field(init=False, default=None)
    battery_level: float = field(init=False, default=-1)

    @abstractmethod
    def generate_battery_message(self) -> list[int]:
        """Generate message array to send to the device to retrieve battery."""

    @abstractmethod
    def update_battery_level(self) -> float:
        """Fetch and update current battery level of the device."""

    def __post_init__(self):
        self.device_info = self.match_device_info()
        if not self.device_info:
            raise Exception(f"Device not found: {self.name}")

        self.battery_message = self.generate_battery_message()
        logging.info(f"Device found for {self.name}: {self.device_info=} / {self.battery_message=}")

    def match_device_info(self) -> DeviceInfo | None:
        found_devices: list[dict] = hid.enumerate(self.VID, self.PID)
        for device in found_devices:
            if self.matching_device.check_match(device):
                return DeviceInfo(**device)

        return None

    def open_device(self) -> hid.device:
        device = hid.device()
        device.open_path(self.device_info.path)  # type: ignore
        return device

    def get_report_descriptor(self) -> str:
        """get_report_descriptor is not yet supported in hdiapi."""
        try:
            device = self.open_device()
            descriptor = device.get_report_descriptor()
        except Exception as e:
            logging.error(f"Error get_report_descriptor: {e}")
            descriptor = []
        finally:
            device.close()

        hex_descriptor = " ".join(f"{x:02X}" for x in descriptor)
        return hex_descriptor

    def update_battery_level_all(self) -> float:
        found_devices: list[dict] = hid.enumerate(self.VID, self.PID)
        for device in found_devices:
            self.device_info = DeviceInfo(**device)
            report_descriptor = self.get_report_descriptor()
            # report = device.get_input_report(self.report_id, 37)
            logging.info(f"{self.device_info=} / {report_descriptor=}")
            battery_level = self.update_battery_level()
            if battery_level > 0:
                return battery_level

        return self.battery_level
