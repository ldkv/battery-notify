import logging
import time

from battery import BatteryThreshold
from devices import BaseDevice, Device
from PIL import Image
from pystray import Icon, Menu, MenuItem, _base

CHECK_FREQUENCY = 60 * 10  # 10 minutes


def initialize_system_tray():
    BatteryThreshold.validate_battery_icons()
    image = Image.open(BatteryThreshold.default())
    system_tray = Icon(
        name="Battery Notifier",
        icon=image,
        title="No device found yet",
        menu=Menu(
            MenuItem("Quit", Icon.stop),
        ),
    )
    return system_tray


def battery_loop(system_tray: _base.Icon):
    all_devices = Device.initialize_all()
    while True:
        update_system_tray(system_tray, all_devices)


def update_system_tray(system_tray: _base.Icon, all_devices: list[BaseDevice]):
    title_text = ""
    min_battery = 100
    for device in all_devices:
        battery_level = int(device.update_battery_level())
        battery_text = f"{battery_level}%"
        if battery_level == -1:
            battery_text = "N/A"
            battery_level = min_battery + 1
        if battery_level < min_battery:
            min_battery = battery_level
        title_text += f"{device.name}: {battery_text}\n"

    title_text = title_text.strip()
    system_tray.title = title_text
    battery_threshold = BatteryThreshold.get_battery_threshold(min_battery)
    system_tray.icon = Image.open(battery_threshold.icon())
    if battery_threshold.should_notify():
        system_tray.notify("Low Battery", system_tray.title)
    logging.info(f"Next check in {CHECK_FREQUENCY} seconds...")
    time.sleep(CHECK_FREQUENCY)
