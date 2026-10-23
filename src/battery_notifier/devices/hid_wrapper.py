from dataclasses import dataclass, replace

import hid

from battery_notifier.logs import logger


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
    report_descriptor: str | None = None

    def matching_info(self, other_device: "DeviceInfo") -> bool:
        for key, device_value in self.__dict__.items():
            if device_value is None:
                continue

            other_value = getattr(other_device, key, None)
            if device_value != other_value:
                return False

        return True


class HIDWrapper:
    def __init__(self, device_path: str | None = None):
        """Open the device from HID path and return the device object."""
        self._device = None
        if not device_path:
            return

        try:
            self._device = hid.device()
            self._device.open_path(device_path)
        except Exception as e:
            logger.warning(f"Error open_device: {e} / {device_path=}")

    def __bool__(self) -> bool:
        return self._device is not None

    def __del__(self):
        self.close()

    def close(self):
        if self._device:
            self._device.close()

    def get_report_descriptor(self) -> str:
        if not self._device:
            return ""

        try:
            descriptor = self._device.get_report_descriptor()
        except Exception as e:
            logger.warning(f"Error get_report_descriptor: {e}")
            return ""

        hex_descriptor = " ".join(f"{x:02X}" for x in descriptor)
        return hex_descriptor

    def send_feature_report(self, message: list[int] | None) -> bool:
        if not self._device or message is None:
            return False

        self._device.send_feature_report(message)
        if self._device.error() == "Success":
            return True

        logger.error(f"Error send_feature_report: {self._device.error()} / {message=}")
        return False

    def get_feature_report(self, report_id: int, report_size: int) -> list[int]:
        if not self._device:
            return []

        try:
            return self._device.get_feature_report(report_id, report_size)
        except Exception as e:
            logger.error(f"Error get_feature_report: {e} / {report_id=} / {report_size=}")

        return []

    def get_input_report(self, report_id: int, report_size: int) -> list[int]:
        if not self._device:
            return []

        try:
            return self._device.get_input_report(report_id, report_size)
        except Exception as e:
            logger.error(f"Error get_input_report: {e} / {report_id=} / {report_size=}")

        return []

    def write(self, message: list[int] | None) -> bool:
        if not self._device or message is None:
            return False

        self._device.write(message)
        if self._device.error() == "Success":
            return True

        logger.error(f"Error hid_write: {self._device.error()} / {message=}")
        return False

    def read(self, size: int, timeout_ms: int) -> list[int]:
        if not self._device:
            return []

        try:
            return self._device.read(size, timeout_ms)
        except Exception as e:
            logger.error(f"Error hid_read: {e} / {size=} / {timeout_ms=}")

        return []

    @staticmethod
    def enumerate_matching_devices(VID: int, PID: int, device_filter: DeviceInfo | None = None) -> list[DeviceInfo]:
        """
        List devices matching VID/PID with their report descriptor.
        Only devices matching `device_filter` are opened: opening other interfaces (e.g. keyboard)
        could require extra permissions or block them while open on macOS.
        """
        raw_devices = hid.enumerate(VID, PID)
        pre_filter = replace(device_filter, report_descriptor=None) if device_filter else DeviceInfo()
        devices = []
        for device in raw_devices:
            if not pre_filter.matching_info(DeviceInfo(**device)):
                continue

            hid_device = HIDWrapper(device["path"])
            if not hid_device:
                continue

            device["report_descriptor"] = hid_device.get_report_descriptor()
            devices.append(DeviceInfo(**device))

        return devices
