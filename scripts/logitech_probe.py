# /// script
# requires-python = ">=3.12"
# dependencies = ["hidapi==0.15.0"]
# ///
"""
Probe Logitech HID++ 2.0 devices (Lightspeed / Bolt receivers, or wired) for their battery features.

    uv run scripts/logitech_probe.py
"""

import logging
import time

import hid

logger = logging.getLogger("logitech_probe")

LOGITECH_VID = 0x046D
HIDPP_USAGE_PAGE = 0xFF00
HIDPP_LONG_USAGE = 0x02
LONG_REPORT_ID = 0x11
LONG_REPORT_SIZE = 20
SOFTWARE_ID = 0x0A
READ_TIMEOUT_S = 1.0
# 0xFF: the device itself (wired), 1-6: devices paired to a receiver
DEVICE_INDEXES = [0xFF, 1, 2, 3, 4, 5, 6]

FEATURES = {
    0x0001: "FeatureSet",
    0x0003: "DeviceFwVersion",
    0x0005: "DeviceName",
    0x1000: "BatteryStatus",
    0x1001: "BatteryVoltage",
    0x1004: "UnifiedBattery",
    0x1D4B: "WirelessDeviceStatus",
}


def to_hex(data: list[int]) -> str:
    return " ".join(f"{x:02X}" for x in data)


def request(device: hid.device, index: int, feature_index: int, function: int, params: list[int] = ()) -> list[int]:
    """Send a long HID++ request and return the matching reply's parameters, [] on error or timeout."""
    function_byte = (function << 4) | SOFTWARE_ID
    message = [LONG_REPORT_ID, index, feature_index, function_byte, *params]
    message += [0] * (LONG_REPORT_SIZE - len(message))
    try:
        device.write(message)
    except (OSError, ValueError) as e:
        logger.error(f"  write failed: {e} / {to_hex(message)}")
        return []

    deadline = time.monotonic() + READ_TIMEOUT_S
    while (remaining_ms := int((deadline - time.monotonic()) * 1000)) > 0:
        report = device.read(64, remaining_ms)
        if not report:
            break
        if len(report) < 4 or report[1] != index:
            logger.debug(f"  skipped: {to_hex(report)}")
            continue
        if report[2] == 0x8F:  # HID++ 1.0 error, e.g. no device at this index
            logger.info(f"  HID++ 1.0 error: {to_hex(report)}")
            return []
        if report[2] == 0xFF and report[3] == feature_index and report[4] == function_byte:
            logger.info(f"  HID++ 2.0 error {report[5]:#04x}: {to_hex(report)}")
            return []
        if report[2] == feature_index and report[3] == function_byte:
            logger.info(f"  reply: {to_hex(report)}")
            return report[4:]
        logger.debug(f"  skipped: {to_hex(report)}")
    logger.info("  timeout")
    return []


def device_name(device: hid.device, index: int, feature_index: int) -> str:
    reply = request(device, index, feature_index, 0)
    if not reply:
        return ""
    length, name = reply[0], []
    while len(name) < length:
        chunk = request(device, index, feature_index, 1, [len(name)])
        if not chunk:
            break
        name += chunk[: length - len(name)]
    return bytes(name).decode(errors="replace")


def probe_index(device: hid.device, index: int) -> None:
    logger.info(f"Device index {index:#04x}: protocol version")
    version = request(device, index, 0x00, 1, [0, 0, 0x5A])
    if not version:
        return
    logger.info(f"  HID++ {version[0]}.{version[1]}")

    feature_indexes = {}
    for feature_id, feature_name in FEATURES.items():
        logger.info(f"  getFeature {feature_id:#06x} ({feature_name})")
        reply = request(device, index, 0x00, 0, [feature_id >> 8, feature_id & 0xFF])
        if reply and reply[0]:
            feature_indexes[feature_id] = reply[0]
            logger.info(f"  -> index {reply[0]}, version {reply[2]}")

    if 0x0005 in feature_indexes:
        logger.info(f"  name: {device_name(device, index, feature_indexes[0x0005])!r}")
    if 0x1004 in feature_indexes:
        logger.info("  UnifiedBattery getCapabilities")
        request(device, index, feature_indexes[0x1004], 0)
        logger.info("  UnifiedBattery getStatus (params: percentage, level, charging status, external power)")
        request(device, index, feature_indexes[0x1004], 1)
    if 0x1001 in feature_indexes:
        logger.info("  BatteryVoltage getBatteryInfo (params: millivolts, flags)")
        request(device, index, feature_indexes[0x1001], 0)
    if 0x1000 in feature_indexes:
        logger.info("  BatteryStatus getBatteryLevelStatus (params: level, next level, status)")
        request(device, index, feature_indexes[0x1000], 0)


def main() -> None:
    infos = hid.enumerate(LOGITECH_VID, 0)
    for info in infos:
        logger.info(
            f"{info['vendor_id']:04X}:{info['product_id']:04X} {info['product_string']!r} "
            f"usage_page={info['usage_page']:#06x} usage={info['usage']:#04x} "
            f"interface={info['interface_number']} bus={info.get('bus_type')} path={info['path']!r}"
        )
    for info in infos:
        if (info["usage_page"], info["usage"]) != (HIDPP_USAGE_PAGE, HIDPP_LONG_USAGE):
            continue
        logger.info(f"=== Probing {info['vendor_id']:04X}:{info['product_id']:04X} {info['product_string']!r}")
        device = hid.device()
        try:
            device.open_path(info["path"])
        except (OSError, ValueError) as e:
            logger.warning(f"Cannot open: {e}")
            continue
        try:
            for index in DEVICE_INDEXES:
                probe_index(device, index)
        finally:
            device.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
