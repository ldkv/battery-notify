from dataclasses import dataclass

from base import BaseDevice


@dataclass
class Mouse(BaseDevice):
    VID: int = 0x1532
    PID: int = 0x009A
    interface_number: int = 0
    message_size: int = 91
    battery_index: int = 10
    name: str = "Razer Pro Click Mini"

    def generate_battery_message(self) -> list[int]:
        msg = [
            0,  # report_id
            0,  # status
            31,  # transaction_id = 0x1f
            0,  # remaining packets
            0,  # remaining packets
            0,  # protocol_type
            2,  # command_class = 0x02
            7,  # command_id = 0x07
            128,  # data_size = 0x80
        ]
        msg += [0] * (self.message_size - len(msg))
        crc = 133  # 0x85
        msg[-2] = crc
        return msg
