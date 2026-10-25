import subprocess
import threading

from PIL import Image
from pystray import Icon, Menu, MenuItem

from battery_notifier import __version__
from battery_notifier.core.paths import config_dir
from battery_notifier.core.policy import BatteryStatus, Notifier, battery_status, lowest_level
from battery_notifier.core.poller import Poller
from battery_notifier.core.providers import BatteryReading, HIDProvider, OSProvider
from battery_notifier.core.settings import Settings
from battery_notifier.launcher import app_command, app_environment, is_frozen, remove_old_versions
from battery_notifier.logs import logger
from battery_notifier.platforms.base import Platform
from battery_notifier.ui.icon import icon_renderer

NO_DEVICE_TEXT = "No device found yet"


class TrayApp:
    def __init__(self, platform: Platform):
        self.platform = platform
        self.settings = Settings.load()
        self.poller = Poller([HIDProvider(), OSProvider(platform.bluetooth_batteries)])
        self.icon_renderer = icon_renderer(platform, platform.taskbar_uses_dark_theme)
        self.notifier = Notifier()
        self.readings: list[BatteryReading] = []
        # Set to check the batteries right away instead of waiting for the next check
        self.wake = threading.Event()
        self.dialog: subprocess.Popen | None = None
        self.icon = Icon(
            name="Battery Notifier",
            icon=self.icon_renderer.render(None, self.settings),
            title=NO_DEVICE_TEXT,
            menu=Menu(self.menu_items),
        )

    def menu_items(self):
        yield MenuItem(text="Left-Click-Action", action=self.wake.set, default=True, visible=False)
        for reading in self.readings:
            yield MenuItem(format_reading(reading), None, enabled=False)
        if not self.readings:
            yield MenuItem(NO_DEVICE_TEXT, None, enabled=False)
        yield Menu.SEPARATOR
        yield MenuItem("Refresh", self.wake.set)
        yield MenuItem("Settings…", self.open_settings)
        yield MenuItem("Open settings folder", lambda: self.platform.open_folder(config_dir()))
        yield Menu.SEPARATOR
        yield MenuItem(f"Battery Notifier v{__version__}", None, enabled=False)
        yield MenuItem("Quit", Icon.stop)

    def run(self):
        # Keep "run at startup" pointing to this executable, e.g. after an update
        if is_frozen() and self.platform.is_autostart_enabled():
            self.platform.set_autostart(True)
        remove_old_versions()
        threading.Thread(name="device_loop", target=self.device_loop, daemon=True).start()
        self.icon.run()

    def device_loop(self):
        """Separate thread to check battery levels of all devices."""
        while True:
            self.wake.clear()
            try:
                self.update()
            except Exception:
                logger.exception("Error checking batteries")
            interval = self.settings.check_interval_minutes * 60
            logger.info(f"Next check in {interval} seconds...")
            self.wake.wait(interval)

    def update(self):
        """Update tray icon, title and menu from the devices' battery levels."""
        self.readings = self.poller.poll(self.settings)
        title = "\n".join(map(format_reading, self.readings)) or NO_DEVICE_TEXT
        image = self.icon_renderer.render(lowest_level(self.readings), self.settings)
        self.platform.run_on_main_thread(lambda: self.refresh_icon(title, image))
        if due := self.notifier.due(self.readings, self.settings):
            critical = any(battery_status(reading.level, self.settings) is BatteryStatus.CRITICAL for reading in due)
            self.icon.notify("\n".join(map(format_reading, due)), "Critical battery" if critical else "Low battery")

    def refresh_icon(self, title: str, image: Image.Image):
        self.icon.title = title
        self.icon.icon = image
        self.icon.update_menu()

    def open_settings(self):
        if self.dialog and self.dialog.poll() is None:
            return
        self.dialog = subprocess.Popen(app_command("settings"), env=app_environment())
        threading.Thread(name="settings_dialog", target=self.wait_for_dialog, args=[self.dialog], daemon=True).start()

    def wait_for_dialog(self, dialog: subprocess.Popen):
        if dialog.wait() != 0:
            return
        self.settings = Settings.load()
        logger.info(f"Settings reloaded: {self.settings}")
        self.wake.set()


def format_reading(reading: BatteryReading) -> str:
    return f"{reading.name}: {'N/A' if reading.level is None else f'{reading.level}%'}"
