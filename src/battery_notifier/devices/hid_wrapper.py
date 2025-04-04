from dataclasses import dataclass

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
    report_descriptor: str = ""

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
        if message is None:
            return False

        self._device.send_feature_report(message)  # type: ignore[union-attr]
        if self._device.error() == "Success":  # type: ignore[union-attr]
            return True

        logger.error(f"Error send_feature_report: {self._device.error()} / {message=}")  # type: ignore[union-attr]
        return False

    def get_feature_report(self, report_id: int, report_size: int) -> list[int]:
        try:
            return self._device.get_feature_report(report_id, report_size)  # type: ignore[union-attr]
        except Exception as e:
            logger.error(f"Error get_feature_report: {e} / {report_id=} / {report_size=}")

        return []

    def write(self, message: list[int] | None) -> bool:
        if message is None:
            return False

        self._device.write(message)  # type: ignore[union-attr]
        if self._device.error() == "Success":  # type: ignore[union-attr]
            return True

        logger.error(f"Error hid_write: {self._device.error()} / {message=}")  # type: ignore[union-attr]
        return False

    def read(self, size: int, timeout_ms: int) -> list[int]:
        try:
            return self._device.read(size, timeout_ms)  # type: ignore[union-attr]
        except Exception as e:
            logger.error(f"Error hid_read: {e} / {size=} / {timeout_ms=}")

        return []

    def get_battery_level(self, report_id: int = 0, report_size: int = 8) -> int:
        """
        Request and read battery level from input report.
        
        Args:
            report_id: The report ID for battery information (usually 0)
            report_size: Expected size of the battery report
            
        Returns:
            Battery level as percentage (0-100) or -1 if error
        """
        try:
            # First try to get battery level via feature report
            feature_report = self.get_feature_report(report_id, report_size)
            if feature_report:
                # The battery level is often in the second byte (index 1)
                return feature_report[1]
            
            # If feature report fails, try reading input report
            # For DualSense, we need to read the input report
            response = self.read(report_size, 1000)  # 1 second timeout
            if not response:
                logger.error("No response received for battery request")
                return -1
            
            # Parse battery level from response
            # For DualSense, battery info is in bytes 52-53 (USB) or 53-54 (Bluetooth)
            # Format:
            # Byte 52/53: 
            #   - Bits 0-3: Battery level (0-8, multiply by 12.5 to get percentage)
            #   - Bit 5: Battery full
            # Byte 53/54:
            #   - Bit 3: Charging status
            
            # Try USB format first (byte 52)
            if len(response) > 52:
                battery_byte = response[52]
                battery_level = (battery_byte & 0x0F) * 12.5  # Convert 0-8 to 0-100%
                return int(battery_level)
            
            # Try Bluetooth format (byte 53)
            if len(response) > 53:
                battery_byte = response[53]
                battery_level = (battery_byte & 0x0F) * 12.5  # Convert 0-8 to 0-100%
                return int(battery_level)
            
            logger.error("Response too short to contain battery information")
            return -1
            
        except Exception as e:
            logger.error(f"Error getting battery level: {e}")
            return -1

    def get_dualsense_battery_info(self) -> tuple[int, bool, bool]:
        """
        Get detailed battery information from DualSense controller.
        
        Returns:
            Tuple of (battery_level, is_charging, is_full)
            battery_level: Percentage (0-100)
            is_charging: True if charging
            is_full: True if fully charged
        """
        try:
            # Read a large enough report to get battery info
            response = self.read(64, 1000)  # Read 64 bytes with 1 second timeout
            if not response:
                logger.error("No response received from DualSense")
                return (-1, False, False)
            
            # Try USB format first (bytes 52-53)
            if len(response) > 53:
                battery_byte = response[52]
                charging_byte = response[53]
                
                battery_level = (battery_byte & 0x0F) * 12.5  # Convert 0-8 to 0-100%
                is_full = bool(battery_byte & 0x20)  # Bit 5 indicates full charge
                is_charging = bool(charging_byte & 0x08)  # Bit 3 indicates charging
                
                return (int(battery_level), is_charging, is_full)
            
            # Try Bluetooth format (bytes 53-54)
            if len(response) > 54:
                battery_byte = response[53]
                charging_byte = response[54]
                
                battery_level = (battery_byte & 0x0F) * 12.5  # Convert 0-8 to 0-100%
                is_full = bool(battery_byte & 0x20)  # Bit 5 indicates full charge
                is_charging = bool(charging_byte & 0x08)  # Bit 3 indicates charging
                
                return (int(battery_level), is_charging, is_full)
            
            logger.error("Response too short to contain battery information")
            return (-1, False, False)
            
        except Exception as e:
            logger.error(f"Error getting DualSense battery info: {e}")
            return (-1, False, False)

    @staticmethod
    def enumerate_matching_devices(VID: int, PID: int) -> list[DeviceInfo]:
        raw_devices = hid.enumerate(VID, PID)
        devices = []
        for device in raw_devices:
            hid_device = HIDWrapper(device["path"])
            if not hid_device:
                continue

            device["report_descriptor"] = hid_device.get_report_descriptor()
            devices.append(DeviceInfo(**device))

        return devices
