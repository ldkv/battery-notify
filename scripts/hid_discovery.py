# /// script
# requires-python = ">=3.12"
# dependencies = ["hidapi==0.15.0"]
# ///
"""
Standalone script to debug HID devices and get battery status.

    uv run scripts/hid_discovery.py
"""

import logging
import time

import hid

logger = logging.getLogger("hid_discovery")

REPORT_SIZE = 64  # report ID + 63 bytes
READ_TIMEOUT_MS = 1000


def to_hex(data: list[int]) -> str:
    return " ".join(f"{x:02X}" for x in data)


def open_device(path: bytes) -> hid.device | None:
    try:
        device = hid.device()
        device.open_path(path)
        return device
    except (OSError, ValueError) as e:
        logger.warning(f"Error open_device: {e} / {path=}")
        return None


def get_report_descriptor(device: hid.device) -> str:
    try:
        return to_hex(device.get_report_descriptor())
    except (OSError, ValueError) as e:
        logger.warning(f"Error get_report_descriptor: {e}")
        return ""


def generate_battery_message() -> list[int]:
    # Keychron Launcher, 8K mouse protocol: report ID 0xB3, command 0x06
    return [0xB3, 0x06] + [0] * (REPORT_SIZE - 2)


def get_battery_report_mouse_method(device: hid.device) -> list[int]:
    """Send the battery request and log every report received for 1 second."""
    message = generate_battery_message()
    device.write(message)
    if device.error() != "Success":
        logger.error(f"Error hid_write: {device.error()} / {message=}")
        return []

    reply = []
    deadline = time.monotonic() + READ_TIMEOUT_MS / 1000
    while (remaining_ms := int((deadline - time.monotonic()) * 1000)) > 0:
        try:
            report = device.read(REPORT_SIZE + 1, remaining_ms)
        except (OSError, ValueError) as e:
            logger.error(f"Error hid_read: {e}")
            break
        if not report:
            break
        logger.info(f"report ({len(report)} bytes): {to_hex(report)}")
        reply = reply or report

    return reply


def enumerate_all_devices(VID: int, PID: int) -> list[int]:
    for device_info in hid.enumerate(VID, PID):
        device = open_device(device_info["path"])
        if not device:
            continue

        try:
            device_info["report_descriptor"] = get_report_descriptor(device)
            logger.info(f"{device_info=}")
            if (device_info["usage_page"], device_info["usage"]) != (0xFFC1, 0x01):
                continue

            battery_report = get_battery_report_mouse_method(device)
            if battery_report:
                return battery_report
        finally:
            device.close()

    return []


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    VID: int = 0x3434  # Keychron vendor ID
    PID: int = 0xD028  # Keychron Ultra-Link 8K product ID
    battery_report = enumerate_all_devices(VID, PID)
    logger.info(f"{battery_report=}")
