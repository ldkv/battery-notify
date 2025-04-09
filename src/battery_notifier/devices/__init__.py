import logging
from enum import Enum

from .base import BaseDevice
from .dualsense import DualSense
from .headset import HyperXCloudAlphaWireless
from .mouse import RazerProClickMini

_ALL_DEVICES = {}


class Device(Enum):
    RazerProClickMini = RazerProClickMini
    HyperXCloudAlphaWireless = HyperXCloudAlphaWireless
    DualSense = DualSense


def initialize_all_devices() -> dict[str, BaseDevice]:
    for device in list(Device):
        if device.name in _ALL_DEVICES:
            continue

        try:
            _ALL_DEVICES[device.name] = device.value()
        except Exception as e:
            logging.info(f"Error initializing {device.name}: {e}")

    return _ALL_DEVICES
