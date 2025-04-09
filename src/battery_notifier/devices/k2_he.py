from dataclasses import dataclass

from battery_notifier.devices.base import DEFAULT_BATTERY_LEVEL, BaseDevice, DeviceInfo, HIDWrapper

READ_TIMEOUT_MS = 1000


@dataclass
class KeychronK2HE(BaseDevice):
    VID: int = 0x3434 # Keychron
    PID: int = 0xD030 # K2 HE
    device_info: DeviceInfo = DeviceInfo(usage_page=140)
    battery_index: int = 8
    name: str = "Keychron K2 HE"
    type: str = "keyboard"

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
        # if not device.write(self.battery_message):
        #     return DEFAULT_BATTERY_LEVEL

        report = device.read(32, 1000)
        messages = [0] * 300
        messages[0] = 0xB2
        messages[1] = 0x01
        r = device.write(messages)
        r = device.read(32, 1000)
        report = device.get_input_report(0xB1, 32)
        if len(report) < self.battery_index + 1:
            return DEFAULT_BATTERY_LEVEL

        return report[self.battery_index]


if __name__ == "__main__":
    headset = KeychronK2HE()
    battery_level = headset.update_battery_level()
    print(f"{headset.name} - Battery level: {battery_level}")
