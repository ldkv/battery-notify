import time
from dataclasses import dataclass

from battery_notifier.devices.base import DEFAULT_BATTERY_LEVEL, BaseDevice, DeviceInfo, HIDWrapper


@dataclass
class Mouse(BaseDevice):
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

    def get_battery_level(self, device: HIDWrapper | None = None) -> int:
        if not device:
            device = HIDWrapper(self.device_info.path)

        if not device.send_feature_report(self.battery_message):
            return DEFAULT_BATTERY_LEVEL

        time.sleep(0.4)
        report = device.get_feature_report(self.report_id, len(self.battery_message))  # type: ignore[arg-type]
        # Battery level is a value between 0 and 255
        battery_255 = report[self.battery_index]
        return self.convert_battery_level(battery_255)

    @staticmethod
    def convert_battery_level(battery_level: int) -> int:
        return int(battery_level / 255 * 100)


if __name__ == "__main__":
    mouse = Mouse()
    battery_level = mouse.update_battery_level()
    print(f"{mouse.name} - Battery level: {battery_level}")
