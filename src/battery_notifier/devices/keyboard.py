import logging
from dataclasses import dataclass, field

import hid

from battery_notifier.devices.base import BaseDevice
from battery_notifier.devices.hid_wrapper import DeviceInfo, HIDWrapper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("battery_notifier")


@dataclass
class KeychronLink(BaseDevice):
    VID: int = 0x3434  # Keychron vendor ID
    PID: int = 0xD030  # Keychron Link product ID
    interface_number: int = 1  # Try interface 1 first
    message_size: int = 32  # From report descriptor (0x20)
    battery_index: int = 2  # Will be determined after testing
    name: str = "Keychron Link"
    matching_device: DeviceInfo = field(
        default_factory=lambda: DeviceInfo(
            vendor_id=0x3434,
            product_id=0xD030,
            product_string="Keychron Link ",  # Note the space at the end
            interface_number=1,  # Match interface 1
        )
    )

    def match_device_info(self) -> list[DeviceInfo]:
        """Enumerate all devices matching VID/PID and try to find the correct one."""
        found_devices = HIDWrapper.enumerate_matching_devices(self.VID, self.PID)
        print(f"\nFound {len(found_devices)} devices matching VID/PID")
        return found_devices

    def get_battery_level(self) -> int:
        """Fetch current battery level of the device."""
        # Try USB HID
        devices = hid.enumerate(self.VID, self.PID)
        if not devices:
            print("No devices found")
            return 0

        print(f"\nFound {len(devices)} devices matching VID/PID")

        # Try each interface
        for device_dict in devices:
            print(f"{device_dict=}")

            try:
                h = hid.device()
                h.open_path(device_dict["path"])

                # Try status report (Report ID 0x54)
                try:
                    response = h.get_input_report(0x54, 20)  # 20 bytes status report
                    print(f"Status report (0x54) response: {[hex(x) for x in response]}")
                    if response and len(response) > 0:
                        # Try different potential battery level positions
                        for i, byte in enumerate(response):
                            if byte:
                                logger.info(f"Found battery level in status report at index {i}: {byte}%")
                                return byte
                except Exception as e:
                    print(f"Status report error: {str(e)}")

                # Try vendor-specific input report (Report ID 0xB1)
                try:
                    response = h.get_input_report(0xB1, 32)  # 32 bytes input report
                    print(f"Input report (0xB1) response: {[hex(x) for x in response]}")
                    if response and len(response) > 0:
                        for i, byte in enumerate(response):
                            if byte:
                                logger.info(f"Found battery level in input report at index {i}: {byte}%")
                                return byte
                except Exception as e:
                    print(f"Input report error: {str(e)}")

                # Try sending battery request via output report (Report ID 0xB2)
                try:
                    # Construct battery request message
                    msg = [0xB2]  # Report ID
                    msg.append(0x01)  # Command type (battery request)
                    msg += [0] * (32 - len(msg))  # Pad to 32 bytes

                    print(f"Sending battery request: {[hex(x) for x in msg[:8]]}")
                    h.write(msg)

                    # Read response
                    response = h.read(32, timeout_ms=1000)
                    print(f"Response: {[hex(x) for x in response]}")
                    if response and len(response) > 0:
                        for i, byte in enumerate(response):
                            if byte:
                                logger.info(f"Found battery level in response at index {i}: {byte}%")
                                return byte
                except Exception as e:
                    print(f"Write/read error: {str(e)}")

                # Try feature reports as fallback
                for report_id in [0x51, 0x52, 0x53]:  # Try all feature report IDs
                    try:
                        size = 20 if report_id == 0x51 else (64 if report_id == 0x52 else 32)  # Limit size for 0x53
                        response = h.get_feature_report(report_id, size)
                        print(f"Feature report (0x{report_id:02X}) response: {[hex(x) for x in response]}")
                        if response and len(response) > 0:
                            for i, byte in enumerate(response):
                                if byte:
                                    logger.info(
                                        f"Found battery level in feature report 0x{report_id:02X} at index {i}: {byte}%"
                                    )
                                    return byte
                    except Exception as e:
                        print(f"Feature report 0x{report_id:02X} error: {str(e)}")

                h.close()

            except Exception as e:
                print(f"Device error: {str(e)}")
                continue

        return 0

    def __str__(self):
        return "Keychron Link"


if __name__ == "__main__":
    keyboard = KeychronLink()
    battery_level = keyboard.get_battery_level()
    logger.info(f"{keyboard} - Battery level: {battery_level}")
    print(f"Battery level: {battery_level}%")

    # all_devices = keyboard.match_device_info()
    # for device in all_devices:
    #     hid_device = HIDWrapper(device.path)
    # print("No Keychron Link device found")
