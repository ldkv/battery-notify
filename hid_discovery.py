"""Standalone script to debug HID devices and get battery status."""

import time

from battery_notifier.devices.hid_wrapper import HIDWrapper
from battery_notifier.logs import configure_logging, logger


# pip install -e .
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
    logger.info(f"{found_devices=}")
    for device_info in found_devices:
        device = HIDWrapper(device_info.path)
        report_descriptor = device.get_report_descriptor(0)
        logger.info(f"{device_info=} / {report_descriptor=}")
        battery_report = get_battery_report_mouse_method(device)
        if battery_report >= 0:
            return battery_report

    return []


if __name__ == "__main__":
    configure_logging()
    VID: int = 0x03F0  # 0x19F5
    PID: int = 0x098D  # 0x3247
    battery_report = enumerate_all_devices(VID, PID)
    logger.info(f"{battery_report=}")