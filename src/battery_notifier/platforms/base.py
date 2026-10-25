import webbrowser
from collections.abc import Callable
from pathlib import Path


class Platform:
    """
    OS integration. These defaults are used on unsupported OSes:
    subclass it per OS and override what that OS supports.
    """

    supports_autostart = False

    def bluetooth_batteries(self) -> list[tuple[str, int]]:
        """Name and battery level of the connected devices whose level the OS knows."""
        return []

    def is_autostart_enabled(self) -> bool:
        return False

    def set_autostart(self, enabled: bool):
        raise NotImplementedError("Run at startup is not supported on this OS")

    def acquire_single_instance(self, name: str) -> bool:
        """Return False if another process already holds `name`."""
        return True

    def apps_use_dark_theme(self) -> bool:
        return False

    def taskbar_uses_dark_theme(self) -> bool:
        return False

    def icon_font(self) -> Path | None:
        """Font with the Segoe battery glyphs, None to draw the tray icon instead."""
        return None

    def enable_high_dpi(self):
        """Render GUI windows sharply on high DPI screens."""

    def open_folder(self, path: Path):
        webbrowser.open(path.as_uri())

    def run_on_main_thread(self, function: Callable[[], None]):
        """Run `function` on the thread running the tray icon, which owns the GUI."""
        function()
