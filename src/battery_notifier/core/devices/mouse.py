import time
from dataclasses import dataclass

from battery_notifier.core.devices.base import DEFAULT_BATTERY_LEVEL, BaseDevice, DeviceInfo, HIDWrapper
from battery_notifier.logs import logger

# Keychron 8K mouse protocol, as used by Keychron Launcher
M6_REPORT_SIZE = 64  # report ID + 63 bytes
M6_READ_TIMEOUT_MS = 1000
M6_REQUEST_ID = 0xB3
M6_REPLY_ID = 0xB4
M6_GET_INFO = 0x06
M6_BATTERY_INDEX = 20  # after report ID and command
M6_PERCENTAGE_MASK = 0x7F  # bit 7 is the charging state
MAX_BATTERY_LEVEL = 100


@dataclass
class RazerProClickMini(BaseDevice):
    VID: int = 0x1532
    PID: int = 0x009A
    device_info: DeviceInfo = DeviceInfo(interface_number=0)
    battery_index: int = 10
    name: str = "Razer Pro Click Mini"
    type: str = "mouse"

    def generate_battery_message(self) -> list[int]:
        message_size = 91
        self.report_id = 0
        msg = [
            self.report_id,
            0,  # status
            31,  # transaction_id = 0x1f
            0,  # remaining packets
            0,  # remaining packets
            0,  # protocol_type
            2,  # command_class = 0x02
            7,  # command_id = 0x07
            128,  # data_size = 0x80
        ]
        msg += [0] * (message_size - len(msg))
        crc = 133  # 0x85
        msg[-2] = crc
        return msg

    def get_battery_level(self, device: HIDWrapper) -> int:
        if self.battery_message is None or not device.send_feature_report(self.battery_message):
            return DEFAULT_BATTERY_LEVEL

        time.sleep(0.4)
        report = device.get_feature_report(self.report_id, len(self.battery_message))
        # Battery level is a value between 0 and 255
        battery_255 = report[self.battery_index]
        return self.convert_battery_level(battery_255)

    @staticmethod
    def convert_battery_level(battery_level: int) -> int:
        return int(battery_level / 255 * 100)


def parse_m6_battery_report(report: list[int]) -> int:
    """Parse the reply to M6_GET_INFO: B4 06 ..., battery at index 20, percentage in bits 0-6."""
    if len(report) <= M6_BATTERY_INDEX or report[0] != M6_REPLY_ID or report[1] != M6_GET_INFO:
        return DEFAULT_BATTERY_LEVEL

    battery_level = report[M6_BATTERY_INDEX] & M6_PERCENTAGE_MASK
    return battery_level if battery_level <= MAX_BATTERY_LEVEL else DEFAULT_BATTERY_LEVEL


@dataclass
class KeychronM6(BaseDevice):
    """Keychron M6 8K connected via the 2.4 GHz receiver Keychron Ultra-Link 8K, with stock firmware."""

    VID: int = 0x3434  # Keychron
    PID: int = 0xD028  # Keychron Ultra-Link 8K
    device_info: DeviceInfo = DeviceInfo(usage_page=0xFFC1, usage=0x01)
    battery_index: int = M6_BATTERY_INDEX
    name: str = "Keychron M6"
    type: str = "mouse"

    def get_battery_level(self, device: HIDWrapper) -> int:
        message = [M6_REQUEST_ID, M6_GET_INFO] + [0] * (M6_REPORT_SIZE - 2)
        if not device.write(message):
            return DEFAULT_BATTERY_LEVEL

        # Skip unrelated reports, e.g. the receiver's E2 status notifications
        deadline = time.monotonic() + M6_READ_TIMEOUT_MS / 1000
        while (remaining_ms := int((deadline - time.monotonic()) * 1000)) > 0:
            report = device.read(M6_REPORT_SIZE + 1, remaining_ms)
            if not report:
                break
            if report[:2] == [M6_REPLY_ID, M6_GET_INFO]:
                return parse_m6_battery_report(report)

        logger.info(f"{self.name} - No battery reply (asleep, off or charging?)")
        return DEFAULT_BATTERY_LEVEL


if __name__ == "__main__":
    mouse = RazerProClickMini()
    battery_level = mouse.update_battery_level()
    print(f"{mouse.name} - Battery level: {battery_level}")
