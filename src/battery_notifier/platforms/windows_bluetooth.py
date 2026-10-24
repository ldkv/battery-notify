"""
Battery level of connected Bluetooth devices, as shown in Windows Settings.
Reads the PnP device properties through WinRT, in process.
"""

import asyncio
from collections.abc import Callable
from typing import Any

from winrt.system import unbox_boolean, unbox_uint8
from winrt.windows.devices.enumeration import DeviceInformation, DeviceInformationKind

from battery_notifier.logs import logger

BLUETOOTH_DEVICES = 'System.Devices.ClassGuid:="{e0cbf06c-cd8b-4647-bb8a-263b43f0f974}"'
# "Is connected" property, source: https://stackoverflow.com/a/71609867/21333661
CONNECTED_KEY = "{83DA6326-97A6-4088-9453-A1923F573B29} 15"
BATTERY_KEY = "{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2"
IGNORED_TEXTS = {"Generic", "Service", "Bluetooth"}
# DualSense has its own HID driver
IGNORED_DEVICES = {"microsoft bluetooth device", "dualsense wireless controller"}


def bluetooth_batteries() -> list[tuple[str, int]]:
    try:
        return asyncio.run(find_bluetooth_batteries())
    except OSError as e:
        logger.error(f"Error reading Bluetooth devices: {e}")
        return []


async def find_bluetooth_batteries() -> list[tuple[str, int]]:
    bluetooth = await find_devices(BLUETOOTH_DEVICES, CONNECTED_KEY, unbox_boolean)
    names = connected_device_names(bluetooth)
    # The battery level is often on another device node of the same device, e.g. "<name> Hands-Free AG"
    batteries = await find_devices("", BATTERY_KEY, unbox_uint8)
    found = match_batteries(names, batteries)
    logger.info(f"Bluetooth battery levels: {found}")
    return found


async def find_devices(aqs_filter: str, key: str, unbox: Callable[[Any], Any]) -> list[tuple[str, Any]]:
    """Name and property value of the device nodes that have the property."""
    devices = await DeviceInformation.find_all_async_with_kind_aqs_filter_and_additional_properties(
        aqs_filter, [key], DeviceInformationKind.DEVICE
    )
    found = []
    for device in devices:
        value = device.properties.get(key)
        if value is not None:
            found.append((device.name, value if isinstance(value, int) else unbox(value)))
    return found


def connected_device_names(devices: list[tuple[str, bool]]) -> set[str]:
    names = set()
    for name, connected in devices:
        if not connected or any(text in name for text in IGNORED_TEXTS) or name.lower() in IGNORED_DEVICES:
            continue
        names.add(name)
    return names


def match_batteries(names: set[str], batteries: list[tuple[str, int]]) -> list[tuple[str, int]]:
    """Battery level of each named device, read from the first device node whose name contains it."""
    found = []
    for name in sorted(names):
        level = next((level for node_name, level in batteries if name in node_name), None)
        if level is not None:
            found.append((name, level))
    return found
