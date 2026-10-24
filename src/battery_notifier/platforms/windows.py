import ctypes
import os
import subprocess
import sys
import winreg
from ctypes import wintypes
from pathlib import Path

from battery_notifier.bluetooth.windows_devices import get_bluetooth_devices_with_battery_level
from battery_notifier.launcher import app_command, is_frozen
from battery_notifier.platforms.base import Platform

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "BatteryNotifier"
PERSONALIZE_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
ERROR_ALREADY_EXISTS = 183
PROCESS_SYSTEM_DPI_AWARE = 1
ICON_FONTS = ["SegoeIcons.ttf", "segmdl2.ttf"]


class WindowsPlatform(Platform):
    supports_autostart = True

    def __init__(self):
        # Mutex handles must stay open for the lifetime of the process
        self._mutexes: list[int] = []

    def bluetooth_batteries(self) -> list[tuple[str, int]]:
        return get_bluetooth_devices_with_battery_level()

    def is_autostart_enabled(self) -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                winreg.QueryValueEx(key, RUN_VALUE)
            return True
        except FileNotFoundError:
            return False

    def set_autostart(self, enabled: bool):
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            if enabled:
                winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, subprocess.list2cmdline(autostart_command()))
                return
            try:
                winreg.DeleteValue(key, RUN_VALUE)
            except FileNotFoundError:
                pass

    def acquire_single_instance(self, name: str) -> bool:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        handle = kernel32.CreateMutexW(None, False, f"Local\\{name}")
        if not handle:
            return True  # can't tell, don't block the app
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False
        self._mutexes.append(handle)
        return True

    def apps_use_dark_theme(self) -> bool:
        return is_dark_theme("AppsUseLightTheme")

    def taskbar_uses_dark_theme(self) -> bool:
        return is_dark_theme("SystemUsesLightTheme")

    def icon_font(self) -> Path | None:
        fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        # Segoe Fluent Icons on Windows 11, Segoe MDL2 Assets on Windows 10
        return next((path for name in ICON_FONTS if (path := fonts / name).exists()), None)

    def enable_high_dpi(self):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(PROCESS_SYSTEM_DPI_AWARE)
        except OSError:
            pass

    def open_folder(self, path: Path):
        os.startfile(path)


def is_dark_theme(value_name: str) -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PERSONALIZE_KEY) as key:
            return winreg.QueryValueEx(key, value_name)[0] == 0
    except OSError:
        return False


def autostart_command() -> list[str]:
    """Same as `app_command`, but without a console window when running from source."""
    command = app_command()
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not is_frozen() and pythonw.exists():
        command[0] = str(pythonw)
    return command
