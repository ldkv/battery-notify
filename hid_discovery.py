"""Standalone script to debug HID devices and get battery status."""

import time

from src.battery_notifier.devices.hid_wrapper import HIDWrapper
from src.battery_notifier.logs import configure_logging, logger


def generate_battery_message() -> list[int]:
    return [1]


def get_battery_report_mouse_method(device: HIDWrapper) -> list[int]:
    battery_message = generate_battery_message()
    if not device.send_feature_report(battery_message):
        return -1

    time.sleep(0.4)
    report_id = battery_message[0]
    report = device.get_feature_report(report_id, len(battery_message))
    return report


def enumerate_all_devices(VID: int, PID: int) -> list[int]:
    found_devices = HIDWrapper.enumerate_matching_devices(VID, PID)
    for device_info in found_devices:
        device = HIDWrapper(device_info.path)
        if not device:
            logger.error(f"Error creating HIDWrapper from path: {device_info=}")
            continue

        report_descriptor = device.get_report_descriptor()
        logger.info(f"{device_info=} / {report_descriptor=}")
        battery_report = get_battery_report_mouse_method(device)
        if battery_report:
            return battery_report

    return []


if __name__ == "__main__":
    configure_logging()
    VID: int = 0x03F0  # 0x19F5
    PID: int = 0x098D  # 0x3247
    VID: int = 0x3434  # Keychron vendor ID
    PID: int = 0xD030  # Keychron Link product ID
    battery_report = enumerate_all_devices(VID, PID)
    logger.info(f"{battery_report=}")
