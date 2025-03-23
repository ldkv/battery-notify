from dataclasses import dataclass

from battery_notifier.devices.base import DEFAULT_BATTERY_LEVEL, BaseDevice, DeviceInfo, HIDWrapper

READ_TIMEOUT_MS = 1000


@dataclass
class Headset(BaseDevice):
    VID: int = 0x03F0
    PID: int = 0x098D
    device_info: DeviceInfo = DeviceInfo(
        usage=514,
        report_descriptor="06 43 FF 0A 02 02 A1 01 85 21 95 1E 75 08 15 00 26 FF 00 09 00 81 02 09 00 91 02 C0 05 0C 09 01 A1 01 85 01 15 00 25 01 05 0C 09 CD 09 E9 09 EA 09 B5 09 B6 09 E2 95 06 75 01 81 02 75 02 95 01 81 03 C0",
    )
    battery_index: int = 3
    name: str = "HyperX Cloud Alpha Wireless"
    type: str = "Headset"

    def generate_battery_message(self) -> list[int]:
        message_size = 52
        self.report_id = 0x21
        msg = [
            self.report_id,
            0xBB,  # 187
            0x0B,  # 11
        ]
        msg += [0] * (message_size - len(msg))
        return msg

    def get_battery_level(self, device: HIDWrapper) -> int:
        if not device.write(self.battery_message):
            return DEFAULT_BATTERY_LEVEL

        report = device.read(self.battery_index + 1, READ_TIMEOUT_MS)
        if len(report) < self.battery_index + 1:
            return DEFAULT_BATTERY_LEVEL

        return report[self.battery_index]


if __name__ == "__main__":
    headset = Headset()
    battery_level = headset.update_battery_level()
    print(f"{headset.name} - Battery level: {battery_level}")
