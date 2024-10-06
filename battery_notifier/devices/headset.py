import logging
from dataclasses import dataclass

from devices.base import BaseDevice, DeviceInfo

READ_TIMEOUT_MS = 1000


@dataclass
class Headset(BaseDevice):
    VID: int = 0x03F0
    PID: int = 0x098D
    matching_device: DeviceInfo = DeviceInfo(usage=514)
    battery_index: int = 3
    name: str = "HyperX Cloud Alpha Wireless"
    type: str = "Headset"

    def generate_battery_message(self) -> list[int]:
        message_size = 52
        self.report_id = 0x21
        msg = [
            self.report_id,
            0xBB,
            0x0B,
        ]
        msg += [0] * (message_size - len(msg))
        return msg

    def update_battery_level(self) -> float:
        try:
            device = self.open_device()
            device.write(self.battery_message)
            if device.error() != "Success":
                raise Exception(f"{self.name} - Error writing message: {device.error()}")

            report = device.read(4, READ_TIMEOUT_MS)
            self.battery_level = report[self.battery_index]
        except Exception as e:
            logging.error(f"{self.name} - Error update_battery_level: {e}")
            self.battery_level = -1
        finally:
            device.close()

        return self.battery_level
