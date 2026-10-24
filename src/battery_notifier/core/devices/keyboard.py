import time
from dataclasses import dataclass

from battery_notifier.core.devices.base import DEFAULT_BATTERY_LEVEL, BaseDevice, DeviceInfo, HIDWrapper
from battery_notifier.logs import logger

REPORT_SIZE = 32
READ_TIMEOUT_MS = 1000

# Keychron Link receiver command, works with stock firmware
FR_GET_STATE = 0xB2
# Keyboard command, requires the custom firmware described in docs/keychron-k2-he.md
KC_GET_BATTERY = 0xA4

K2_HE_PIDS = {0x0E20, 0x0E21, 0x0E22}  # ANSI, ISO, JIS
RECEIVER_SLOT_SIZE = 5
MAX_BATTERY_LEVEL = 100


def strip_report_id(report: list[int], command: int) -> list[int]:
    """Some platforms prepend the report ID 0x00 to the received data."""
    if len(report) > 1 and report[0] == 0 and report[1] == command:
        return report[1:]
    return report


def parse_receiver_state(report: list[int]) -> dict[int, bool]:
    """
    Parse the reply to FR_GET_STATE into {keyboard PID: connected}.
    Reply: B2 xx, then up to 3 slots of 5 bytes: VID (LE), PID (LE), connected.
    """
    report = strip_report_id(report, FR_GET_STATE)
    if not report or report[0] != FR_GET_STATE:
        return {}

    devices = {}
    for offset in (2, 7, 12):
        slot = report[offset : offset + RECEIVER_SLOT_SIZE]
        if len(slot) < RECEIVER_SLOT_SIZE:
            break
        vid = slot[0] | slot[1] << 8
        pid = slot[2] | slot[3] << 8
        if vid == 0:
            continue
        devices[pid] = bool(slot[4])

    return devices


def parse_battery_report(report: list[int]) -> int:
    """
    Parse the reply to KC_GET_BATTERY, same layout as Keychron/qmk_firmware#477:
    A4, percentage, voltage in mV (LE, 2 bytes), charging state, transport, model ID.
    """
    report = strip_report_id(report, KC_GET_BATTERY)
    if len(report) <= 1 or report[0] != KC_GET_BATTERY or report[1] > MAX_BATTERY_LEVEL:
        return DEFAULT_BATTERY_LEVEL

    return report[1]


@dataclass
class KeychronK2HE(BaseDevice):
    """
    Keychron K2 HE connected via the 2.4 GHz receiver Keychron Link.
    The keyboard only answers battery requests with the custom firmware described in docs/keychron-k2-he.md.
    """

    VID: int = 0x3434  # Keychron
    PID: int = 0xD030  # Keychron Link
    device_info: DeviceInfo = DeviceInfo(usage_page=0xFF60, usage=0x61)
    battery_index: int = 1
    name: str = "Keychron K2 HE"
    type: str = "keyboard"

    def get_battery_level(self, device: HIDWrapper) -> int:
        state = parse_receiver_state(self.request(device, FR_GET_STATE))
        connected = [pid for pid, is_connected in state.items() if pid in K2_HE_PIDS and is_connected]
        if state and not connected:
            logger.info(f"{self.name} - Not connected to the receiver (asleep or off): {state=}")
            return DEFAULT_BATTERY_LEVEL

        battery_level = parse_battery_report(self.request(device, KC_GET_BATTERY))
        if battery_level == DEFAULT_BATTERY_LEVEL:
            logger.warning(f"{self.name} - No battery reply, is the custom firmware flashed? {state=}")

        return battery_level

    @staticmethod
    def request(device: HIDWrapper, command: int) -> list[int]:
        """Send a command and return the first reply for it, skipping unrelated reports."""
        message = [0, command] + [0] * (REPORT_SIZE - 1)  # leading report ID 0
        if not device.write(message):
            return []

        deadline = time.monotonic() + READ_TIMEOUT_MS / 1000
        while (remaining_ms := int((deadline - time.monotonic()) * 1000)) > 0:
            report = strip_report_id(device.read(REPORT_SIZE + 1, remaining_ms), command)
            if not report:
                return []
            if report[0] == command:
                return report

        return []


if __name__ == "__main__":
    keyboard = KeychronK2HE()
    battery_level = keyboard.update_battery_level()
    print(f"{keyboard.name} - Battery level: {battery_level}")
