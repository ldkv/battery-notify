import sys

import pytest

if sys.platform != "win32":
    pytest.skip("winrt is only installed on Windows", allow_module_level=True)

from battery_notifier.platforms.windows_bluetooth import (  # noqa: E402
    bluetooth_batteries,
    connected_device_names,
    match_batteries,
)


def test_connected_device_names_skips_disconnected_and_system_devices():
    devices = [
        ("WH-1000XM4", True),
        ("MX Keys", False),
        ("Microsoft Bluetooth Enumerator", True),
        ("Generic Attribute Profile", True),
        ("DualSense Wireless Controller", True),
    ]
    assert connected_device_names(devices) == {"WH-1000XM4"}


def test_match_batteries_reads_level_from_any_node_containing_the_name():
    batteries = [("Other Speaker", 10), ("WH-1000XM4 Hands-Free AG", 70)]
    assert match_batteries({"WH-1000XM4", "MX Keys"}, batteries) == [("WH-1000XM4", 70)]


def test_bluetooth_batteries_runs():
    """No Bluetooth device on CI runners: checks the WinRT calls themselves."""
    assert isinstance(bluetooth_batteries(), list)
