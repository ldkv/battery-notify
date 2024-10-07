import logging
import time

from PIL import Image
from pystray import Icon, Menu, MenuItem, _base

from battery_notifier.battery import BatteryThreshold
from battery_notifier.configs import DEFAULT_BATTERY_LEVEL
from battery_notifier.devices import Device

CHECK_FREQUENCY = 60 * 10  # 10 minutes


def initialize_system_tray():
    BatteryThreshold.validate_battery_icons()
    image = Image.open(BatteryThreshold.default())
    system_tray = Icon(
        name="Battery Notifier",
        icon=image,
        title="No device found yet",
        menu=Menu(
            MenuItem(text="Left-Click-Action", action=update_system_tray, default=True, visible=False),
            MenuItem("Quit", Icon.stop),
        ),
    )
    return system_tray


def battery_loop(system_tray: _base.Icon):
    while True:
        update_system_tray(system_tray)
        logging.info(f"Next check in {CHECK_FREQUENCY} seconds...")
        time.sleep(CHECK_FREQUENCY)


def update_system_tray(system_tray: _base.Icon):
    all_devices = Device.initialize_all()
    title_text = ""
    min_battery = 100
    for device in all_devices:
        battery_level = int(device.update_battery_level())
        battery_text = f"{battery_level}%"
        if battery_level == DEFAULT_BATTERY_LEVEL:
            battery_text = "N/A"
            battery_level = min_battery + 1
        min_battery = min(min_battery, battery_level)
        title_text += f"{device.name}: {battery_text}\n"

    title_text = title_text.strip()
    system_tray.title = title_text
    battery_threshold = BatteryThreshold.get_battery_threshold(min_battery)
    system_tray.icon = Image.open(battery_threshold.icon())
    send_notification(system_tray, min_battery)


def send_notification(system_tray: _base.Icon, min_battery: float):
    if BatteryThreshold.should_notify(min_battery):
        system_tray.notify("Low Battery", system_tray.title)
