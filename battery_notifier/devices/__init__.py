from enum import Enum

from .base import BaseDevice
from .headset import Headset
from .mouse import Mouse


class Device(Enum):
    RazerProClickMini = Mouse
    HyperXAlphaWireless = Headset

    @staticmethod
    def initialize_all() -> list[BaseDevice]:
        devices = list(Device)
        all_devices = [device.value() for device in devices]
        return all_devices