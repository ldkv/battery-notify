from enum import Enum

from battery_notifier.bluetooth.windows_devices import get_bluetooth_battery_level

from .devices.base import BaseDevice
from .devices.dualsense import DualSense
from .devices.headset import HyperXCloudAlphaWireless
from .devices.mouse import RazerProClickMini
from .logs import logger

_ALL_DEVICES = {}


class BluetoothDevice(Enum):
    WH_1000XM4 = "WH-1000XM4 Hands-Free AG"
    Keychron_K2_HE = "Keychron K2 HE"

    def update_battery_level(self):
        return get_bluetooth_battery_level(self.value)


class HIDDevice(Enum):
    RazerProClickMini = RazerProClickMini
    HyperXCloudAlphaWireless = HyperXCloudAlphaWireless
    DualSense = DualSense


def initialize_all_devices() -> dict[str, BaseDevice | BluetoothDevice]:
    for hid_device in list(HIDDevice):
        if hid_device.name in _ALL_DEVICES:
            continue

        try:
            _ALL_DEVICES[hid_device.name] = hid_device.value()
            logger.info(f"Initialized {hid_device.name}")
        except Exception as e:
            logger.info(f"Error initializing {hid_device.name}: {e}")

    for bluetooth_device in list(BluetoothDevice):
        if bluetooth_device.name in _ALL_DEVICES:
            continue

        _ALL_DEVICES[bluetooth_device.value] = bluetooth_device
        logger.info(f"Initialized {bluetooth_device.value}")

    return _ALL_DEVICES
