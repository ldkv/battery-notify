import subprocess
from pathlib import Path

from battery_notifier.configs import DEFAULT_BATTERY_LEVEL
from battery_notifier.logs import logger


def execute_powershell_command(command: list[str]) -> str:
    command = ["pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass", *command]
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True, startupinfo=startupinfo)
        return result.stdout
    except Exception as e:
        logger.error(f"An error occurred: {e}")

    return ""


def get_available_bluetooth_devices() -> set[str]:
    """
    Get list of all connected Bluetooth devices
    Source: https://www.hexnode.com/mobile-device-management/help/script-to-show-a-list-of-connected-bluetooth-devices-on-windows-10-11/
    """
    select_command = "SELECT * FROM Win32_PnPEntity WHERE PNPClass = 'Bluetooth'"
    command = ["-Command", f'Get-WmiObject -Query "{select_command}" | Select-Object Name']
    result_output = execute_powershell_command(command)
    found_devices = {line.strip() for line in result_output.strip().split("\n")}
    return filter_connected_bluetooth_devices(found_devices)


def filter_connected_bluetooth_devices(devices: set[str]) -> set[str]:
    ignored_texts = {";1m", "Generic", "Service", "Bluetooth"}
    ignored_devices = {"Microsoft Bluetooth Device"}
    filtered_devices = set()
    for device_name in devices:
        if any(ignored_text in device_name for ignored_text in ignored_texts):
            continue

        if device_name.lower() in ignored_devices:
            continue

        if not is_device_connected(device_name):
            continue

        filtered_devices.add(device_name)

    return filtered_devices


def is_device_connected(device_name: str) -> bool:
    """
    Check if a Bluetooth device is connected.

    Source: https://stackoverflow.com/a/71609867/21333661
    """
    command = [
        "-Command",
        f'Get-PnpDevice -class Bluetooth -FriendlyName "{device_name}"',
        "|",
        "Get-PnpDeviceProperty -KeyName '{83DA6326-97A6-4088-9453-A1923F573B29} 15'",
        "|",
        "Select-Object -ExpandProperty Data",
    ]
    result_output = execute_powershell_command(command)
    return result_output.strip().lower() == "true"


def get_bluetooth_battery_level(device_name: str) -> int:
    script_path = Path(__file__).parent / "get_battery_level.ps1"
    command = ["-File", script_path.as_posix(), device_name]
    logger.info(f"Executing command: {command} - {device_name=}")
    result_output = execute_powershell_command(command)

    try:
        return int(result_output)
    except ValueError:
        logger.error(f"Error getting battery level for {device_name}: {result_output}")
        return DEFAULT_BATTERY_LEVEL


if __name__ == "__main__":
    devices = get_available_bluetooth_devices()
    for device_name in devices:
        battery_level = get_bluetooth_battery_level(device_name)
        print(f"Battery level for {device_name}: {battery_level}")
