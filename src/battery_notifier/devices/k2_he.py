from dataclasses import dataclass

from battery_notifier.devices.base import DEFAULT_BATTERY_LEVEL, BaseDevice, DeviceInfo, HIDWrapper

READ_TIMEOUT_MS = 1000

# Filters in wireshark
# USB: usb.src == "4.13.7" || usb.dst == "4.13.7"
# Bluetooth: _ws.col.def_src == "db:45:ca:9e:2c:cf ()" || _ws.col.def_dst == "db:45:ca:9e:2c:cf ()"
# Handle Value Notification 0x1B - Handle 0x0016 - Value 0x15 == 21
# Try replug the USB receiver


@dataclass
class KeychronK2HE(BaseDevice):
    VID: int = 0x3434  # Keychron
    PID: int = 0xD030  # K2 HE D030 for USB - 0x0E20 for Bluetooth
    device_info: DeviceInfo = DeviceInfo(usage_page=12)
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
        # report = device.read(32, 1000)
        messages = [0x21, 0x09, 0x01, 0x02, 0x00, 0x00, 0x02, 0x00, 0x06, 0x00]
        r = device.send_feature_report(messages)
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
