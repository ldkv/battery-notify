import json
import subprocess
from typing import List, Set, Tuple

apple_script = """
activate application "SystemUIServer"
set deviceName to "Keychron K2 HE"

tell application "System Events"
  tell process "SystemUIServer"
    set bluetoothMenu to (menu bar item 1 of menu bar 1 whose description contains "Control Center")
    tell bluetoothMenu
      click

      set deviceMenuItem to (menu item deviceName of menu 1)
      tell deviceMenuItem
        click

        set batteryLevelMenuItem to (menu item 3 of menu 1)
        tell batteryLevelMenuItem
            set batteryLevelText to title of batteryLevelMenuItem
        end tell
        
        key code 53 -- esc key

        return batteryLevelText
      end tell
    end tell
  end tell
end tell
"""


def execute_command(command: List[str]) -> str:
    """Execute a shell command and return its output."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {e}")
        return ""


def get_available_bluetooth_devices() -> Set[str]:
    """Get list of all connected Bluetooth devices using system_profiler."""
    command = ["system_profiler", "SPBluetoothDataType", "-json"]
    result_output = execute_command(command)

    data = json.loads(result_output)
    connected_devices = data["SPBluetoothDataType"][0].get("device_connected", [])
    device_names = set()
    for device in connected_devices:
        device_names.update(device.keys())
    return filter_connected_bluetooth_devices(device_names)


def filter_connected_bluetooth_devices(devices: set[str]) -> set[str]:
    """Filter out unwanted Bluetooth devices."""
    ignored_devices = {"dualsense wireless controller"}

    filtered_devices = set()
    for device_name in devices:
        if device_name.lower() in ignored_devices:
            continue

        filtered_devices.add(device_name)

    return filtered_devices


def get_bluetooth_battery_level(device_name: str) -> int:
    """Get battery level for a specific Bluetooth device."""
    command = ["osascript", "-e", apple_script]
    result_output = execute_command(command)

    current_device = None
    battery_level = -1

    for line in result_output.split("\n"):
        line = line.strip()
        if ":" in line and not line.startswith("    "):
            current_device = line.split(":")[0].strip()
        elif "Battery Level:" in line and current_device == device_name:
            try:
                # Extract percentage from line like "Battery Level: 80%"
                battery_str = line.split(":")[1].strip().replace("%", "")
                battery_level = int(battery_str)
                break
            except ValueError:
                print(f"Could not parse battery level for {device_name}: {line}")

    return battery_level


def get_bluetooth_devices_with_battery_level() -> List[Tuple[str, int]]:
    """Get all Bluetooth devices with their battery levels."""
    devices = get_available_bluetooth_devices()
    devices_with_battery_level = []

    for device_name in devices:
        battery_level = get_bluetooth_battery_level(device_name)
        print(f"Battery level for {device_name}: {battery_level}")
        devices_with_battery_level.append((device_name, battery_level))

    return devices_with_battery_level


if __name__ == "__main__":
    devices = get_available_bluetooth_devices()
    for device_name in devices:
        battery_level = get_bluetooth_battery_level(device_name)
        print(f"Battery level for {device_name}: {battery_level}")
