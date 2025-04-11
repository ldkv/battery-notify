from dataclasses import dataclass

from battery_notifier.devices.base import DEFAULT_BATTERY_LEVEL, BaseDevice, DeviceInfo, HIDWrapper

READ_TIMEOUT_MS = 1000


@dataclass
class HyperXCloudAlphaWireless(BaseDevice):
    VID: int = 0x03F0
    PID: int = 0x098D
    device_info: DeviceInfo = DeviceInfo(usage=514)
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
    headset = HyperXCloudAlphaWireless()
    battery_level = headset.update_battery_level()
    print(f"{headset.name} - Battery level: {battery_level}")
