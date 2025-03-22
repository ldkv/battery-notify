import logging
from enum import Enum

from .base import BaseDevice
from .headset import Headset
from .mouse import Mouse

_ALL_DEVICES = {}


class Device(Enum):
    RazerProClickMini = Mouse
    HyperXAlphaWireless = Headset


def initialize_all_devices() -> dict[str, BaseDevice]:
    for device in list(Device):
        if device.name in _ALL_DEVICES:
            continue

        try:
            _ALL_DEVICES[device.name] = device.value()
        except Exception as e:
            logging.info(f"Error initializing {device.name}: {e}")

    return _ALL_DEVICES
