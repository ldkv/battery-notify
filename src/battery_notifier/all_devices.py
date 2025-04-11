from enum import Enum

from .devices.base import BaseDevice
from .devices.dualsense import DualSense
from .devices.headset import HyperXCloudAlphaWireless
from .devices.mouse import RazerProClickMini
from .logs import logger

_ALL_DEVICES = {}


class HIDDevice(Enum):
    RazerProClickMini = RazerProClickMini
    HyperXCloudAlphaWireless = HyperXCloudAlphaWireless
    DualSense = DualSense


def initialize_all_devices() -> dict[str, BaseDevice]:
    for hid_device in list(HIDDevice):
        if hid_device.name in _ALL_DEVICES:
            continue

        try:
            _ALL_DEVICES[hid_device.name] = hid_device.value()
            logger.info(f"Initialized {hid_device.name}")
        except Exception as e:
            logger.info(f"Error initializing {hid_device.name}: {e}")

    return _ALL_DEVICES
