import os
import subprocess
import threading

from pystray import Icon, Menu, MenuItem

from battery_notifier import __version__
from battery_notifier.core.paths import config_dir
from battery_notifier.core.policy import lowest_level, should_notify
from battery_notifier.core.poller import Poller
from battery_notifier.core.providers import HIDProvider, OSProvider
from battery_notifier.core.settings import Settings
from battery_notifier.launcher import app_command, is_frozen
from battery_notifier.logs import logger
from battery_notifier.platforms.base import Platform
from battery_notifier.ui.icon import PngIconRenderer

NO_DEVICE_TEXT = "No device found yet"


class TrayApp:
    def __init__(self, platform: Platform):
        self.platform = platform
        self.settings = Settings.load()
        self.poller = Poller([HIDProvider(), OSProvider(platform.bluetooth_batteries)])
        self.icon_renderer = PngIconRenderer()
        # Set to check the batteries right away instead of waiting for the next check
        self.wake = threading.Event()
        self.dialog: subprocess.Popen | None = None
        self.icon = Icon(
            name="Battery Notifier",
            icon=self.icon_renderer.render(None, self.settings),
            title=NO_DEVICE_TEXT,
            menu=Menu(
                MenuItem(text="Left-Click-Action", action=self.wake.set, default=True, visible=False),
                MenuItem(f"Battery Notifier v{__version__}", None, enabled=False),
                Menu.SEPARATOR,
                MenuItem("Settings…", self.open_settings),
                MenuItem("Open settings folder", lambda: platform.open_folder(config_dir())),
                MenuItem("Quit", Icon.stop),
            ),
        )

    def run(self):
        # Keep "run at startup" pointing to this executable, e.g. after an update
        if is_frozen() and self.platform.is_autostart_enabled():
            self.platform.set_autostart(True)
        threading.Thread(name="device_loop", target=self.device_loop, daemon=True).start()
        self.icon.run()

    def device_loop(self):
        """Separate thread to check battery levels of all devices."""
        while True:
            self.wake.clear()
            self.update()
            interval = self.settings.check_interval_minutes * 60
            logger.info(f"Next check in {interval} seconds...")
            self.wake.wait(interval)

    def update(self):
        """Update tray icon and title from the devices' battery levels."""
        readings = self.poller.poll(self.settings)
        lines = [f"{reading.name}: {'N/A' if reading.level is None else f'{reading.level}%'}" for reading in readings]
        self.icon.title = "\n".join(lines) or NO_DEVICE_TEXT
        level = lowest_level(readings)
        self.icon.icon = self.icon_renderer.render(level, self.settings)
        if should_notify(level, self.settings):
            self.icon.notify("Low Battery", self.icon.title)

    def open_settings(self):
        if self.dialog and self.dialog.poll() is None:
            return
        # Let a PyInstaller onefile child unpack itself instead of reusing the parent's files
        env = os.environ | {"PYINSTALLER_RESET_ENVIRONMENT": "1"}
        self.dialog = subprocess.Popen(app_command("settings"), env=env)
        threading.Thread(name="settings_dialog", target=self.wait_for_dialog, args=[self.dialog], daemon=True).start()

    def wait_for_dialog(self, dialog: subprocess.Popen):
        if dialog.wait() != 0:
            return
        self.settings = Settings.load()
        logger.info(f"Settings reloaded: {self.settings}")
        self.wake.set()
