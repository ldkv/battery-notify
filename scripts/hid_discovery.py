"""Standalone script to debug HID devices and get battery status."""

import time

from battery_notifier.core.devices.hid_wrapper import HIDWrapper
from battery_notifier.logs import configure_logging, logger

REPORT_SIZE = 64  # report ID + 63 bytes
READ_TIMEOUT_MS = 1000


def generate_battery_message() -> list[int]:
    # Keychron Launcher, 8K mouse protocol: report ID 0xB3, command 0x06
    return [0xB3, 0x06] + [0] * (REPORT_SIZE - 2)


def get_battery_report_mouse_method(device: HIDWrapper) -> list[int]:
    """Send the battery request and log every report received for 1 second."""
    if not device.write(generate_battery_message()):
        return []

    reply = []
    deadline = time.monotonic() + READ_TIMEOUT_MS / 1000
    while (remaining_ms := int((deadline - time.monotonic()) * 1000)) > 0:
        report = device.read(REPORT_SIZE + 1, remaining_ms)
        if not report:
            break
        logger.info(f"report ({len(report)} bytes): {' '.join(f'{x:02X}' for x in report)}")
        reply = reply or report

    return reply


def enumerate_all_devices(VID: int, PID: int) -> list[int]:
    found_devices = HIDWrapper.enumerate_matching_devices(VID, PID)
    for device_info in found_devices:
        logger.info(f"{device_info=}")
        if (device_info.usage_page, device_info.usage) != (0xFFC1, 0x01):
            continue

        device = HIDWrapper(device_info.path)
        if not device:
            logger.error(f"Error creating HIDWrapper from path: {device_info=}")
            continue

        battery_report = get_battery_report_mouse_method(device)
        if battery_report:
            return battery_report

    return []


if __name__ == "__main__":
    configure_logging()
    VID: int = 0x3434  # Keychron vendor ID
    PID: int = 0xD028  # Keychron Ultra-Link 8K product ID
    battery_report = enumerate_all_devices(VID, PID)
    logger.info(f"{battery_report=}")
