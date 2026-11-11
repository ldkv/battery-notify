# /// script
# requires-python = ">=3.12,<3.15"  # hidapi has no wheels for newer Python yet
# dependencies = ["hidapi==0.15.0"]
# ///
"""
Standalone script to debug HID devices and get battery status.

    uv run scripts/hid_discovery.py                # Keychron Ultra-Link 8K
    uv run scripts/hid_discovery.py 19F5 0         # every NuPhy device (PID 0 matches any)

Vendor-defined interfaces other than the Keychron mouse one are only listened to:
type, plug or unplug the charger meanwhile to catch status reports.

--probe-cz also sends, once, the status read of Mchose's 2.4 GHz dongle to 0xFF31/0x74 interfaces
(evren-oct/vigil-watt#104): the reply starts with AA 05, its data at byte 0x20 holds the battery.
"""

import argparse
import logging
import time

import hid

logger = logging.getLogger("hid_discovery")

REPORT_SIZE = 64  # report ID + 63 bytes
READ_TIMEOUT_MS = 1000
LISTEN_SECONDS = 15
VENDOR_USAGE_PAGE = 0xFF00  # vendor-defined usage pages are 0xFF00-0xFFFF
CZ_INTERFACE = (0xFF31, 0x74)
CZ_STATUS_READ = [0x55, 0x05, 0x00, 0x38, 0x38, 0x00, 0x00, 0x00]  # read 0x38 bytes at offset 0
CZ_LISTEN_SECONDS = 5


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


def listen(device: hid.device, seconds: int) -> None:
    """Log every report the interface sends, without writing to it."""
    logger.info(f"Listening for {seconds}s...")
    deadline = time.monotonic() + seconds
    while (remaining_ms := int((deadline - time.monotonic()) * 1000)) > 0:
        try:
            report = device.read(REPORT_SIZE + 1, min(remaining_ms, READ_TIMEOUT_MS))
        except (OSError, ValueError) as e:
            logger.error(f"Error hid_read: {e}")
            return
        if report:
            logger.info(f"report ({len(report)} bytes): {to_hex(report)}")


def probe_cz(device: hid.device) -> None:
    """Send the Mchose status read once and log the replies."""
    message = [0] + CZ_STATUS_READ + [0] * (REPORT_SIZE - len(CZ_STATUS_READ))  # leading report ID 0
    logger.info(f"Sending CZ status read: {to_hex(message)}")
    if device.write(message) < 0:
        logger.error(f"Error hid_write: {device.error()}")
        return
    listen(device, CZ_LISTEN_SECONDS)


def enumerate_all_devices(VID: int, PID: int, probe: bool) -> list[int]:
    for device_info in hid.enumerate(VID, PID):
        device = open_device(device_info["path"])
        if not device:
            continue

        try:
            device_info["report_descriptor"] = get_report_descriptor(device)
            logger.info(f"{device_info=}")
            if (device_info["usage_page"], device_info["usage"]) != (0xFFC1, 0x01):
                if probe and (device_info["usage_page"], device_info["usage"]) == CZ_INTERFACE:
                    probe_cz(device)
                elif device_info["usage_page"] >= VENDOR_USAGE_PAGE:
                    listen(device, LISTEN_SECONDS)
                continue

            battery_report = get_battery_report_mouse_method(device)
            if battery_report:
                return battery_report
        finally:
            device.close()

    return []


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("vid", nargs="?", type=lambda x: int(x, 16), default=0x3434, help="hex, default Keychron")
    parser.add_argument("pid", nargs="?", type=lambda x: int(x, 16), default=0xD028, help="hex, default Ultra-Link 8K")
    parser.add_argument("--probe-cz", action="store_true", help="send the Mchose status read, see above")
    args = parser.parse_args()
    battery_report = enumerate_all_devices(args.vid, args.pid, args.probe_cz)
    logger.info(f"{battery_report=}")
