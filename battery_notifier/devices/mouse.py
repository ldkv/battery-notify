import logging
import time
from dataclasses import dataclass

from battery_notifier.devices.base import BaseDevice, DeviceInfo


@dataclass
class Mouse(BaseDevice):
    VID: int = 0x1532
    PID: int = 0x009A
    matching_device: DeviceInfo = DeviceInfo(interface_number=0)
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

    def update_battery_level(self) -> float:
        try:
            device = self.open_device()
            device.send_feature_report(self.battery_message)
            if device.error() != "Success":
                raise Exception(f"{self.name} - Error send_feature_report: {device.error()}")

            time.sleep(0.4)
            report = device.get_feature_report(self.report_id, len(self.battery_message))
            self.battery_level = round(report[self.battery_index] / 255 * 100, 2)
        except Exception as e:
            logging.error(f"{self.name} - Error update_battery_level: {e}")
            self.battery_level = -1
        finally:
            device.close()

        return self.battery_level
