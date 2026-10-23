from battery_notifier.bluetooth import windows_devices


def test_bluetooth_device_list_skips_blank_lines(monkeypatch):
    checked_devices = []

    def is_device_connected(device_name: str) -> bool:
        checked_devices.append(device_name)
        return True

    monkeypatch.setattr(windows_devices, "execute_powershell_command", lambda _: "Headset\n\nMouse\n")
    monkeypatch.setattr(windows_devices, "is_device_connected", is_device_connected)

    assert windows_devices.get_available_bluetooth_devices() == {"Headset", "Mouse"}
    assert sorted(checked_devices) == ["Headset", "Mouse"]


def test_no_bluetooth_device_found(monkeypatch):
    checked_devices = []

    def is_device_connected(device_name: str) -> bool:
        checked_devices.append(device_name)
        return False

    monkeypatch.setattr(windows_devices, "execute_powershell_command", lambda _: "")
    monkeypatch.setattr(windows_devices, "is_device_connected", is_device_connected)

    assert windows_devices.get_available_bluetooth_devices() == set()
    assert checked_devices == []
