import time
from dataclasses import dataclass
from enum import Enum

from battery_notifier.devices.base import DEFAULT_BATTERY_LEVEL, BaseDevice, DeviceInfo, HIDWrapper


@dataclass
class DualSense(BaseDevice):
    """
    DualSense controller using via USB or Bluetooth.
    Docs: https://controllers.fandom.com/wiki/Sony_DualSense
    Inspired by: https://github.com/nondebug/dualsense
    """

    VID: int = 0x054C  # Sony
    PID: int = 0x0CE6  # DualSense
    device_info: DeviceInfo = DeviceInfo(usage=5)
    battery_index: int = 54  # Bluetooth
    is_bluetooth: bool = True
    name: str = "DualSense controller"
    type: str = "controller"

    def __post_init__(self):
        super().__post_init__()
        # USB mode has a different battery index
        if self.device_info.bus_type == 1:
            self.battery_index = 53
            self.is_bluetooth = False

    def get_battery_level(self, device: HIDWrapper) -> int:
        """
        By default, bluetooth-connected DualSense only sends input report 0x01 which omits battery data.
        Reading feature report 0x05 activates sending input report 0x31 which includes battery data.
        """
        if self.is_bluetooth:
            report_id = 0x05
            report_size = 78
            device.get_feature_report(report_id, report_size)
            time.sleep(0.1)

        response = device.read(self.battery_index + 1, 1000)
        if len(response) <= self.battery_index:
            return DEFAULT_BATTERY_LEVEL

        battery_byte = response[self.battery_index]
        battery_level = battery_byte & 0x0F  # last 4 bits
        return self.convert_battery_level(battery_level)

    @staticmethod
    def convert_battery_level(battery_level: int) -> int:
        """
        Battery level is a number from 0 to 10 (0x0A).
        """
        return int(battery_level * 10)


class BatteryState(Enum):
    """
    Battery state from input report 0x31.
    May be useful in the future.
    """

    DISCHARGING = 0x00
    CHARGING = 0x01
    COMPLETE = 0x02
    ABNORMAL_VOLTAGE = 0x0A
    ABNORMAL_TEMPERATURE = 0x0B
    CHARGING_ERROR = 0x0F

    @staticmethod
    def from_battery_byte(battery_byte: int) -> "BatteryState":
        return BatteryState(battery_byte >> 4 & 0x0F)


if __name__ == "__main__":
    controller = DualSense()
    battery_level = controller.update_battery_level()
    print(f"{controller.name} - Battery level: {battery_level}")
