from typing import Protocol

from PIL import Image

from battery_notifier.configs import image_path
from battery_notifier.core.policy import BatteryStatus, battery_status
from battery_notifier.core.settings import Settings

MEDIUM_THRESHOLD = 60


class IconRenderer(Protocol):
    def render(self, level: int | None, settings: Settings) -> Image.Image:
        """Tray icon for the lowest battery level, None when no device reports one."""
        ...


class PngIconRenderer:
    def __init__(self):
        for name in ("critical", "low", "medium", "full"):
            if not image_path(f"battery-{name}.png").exists():
                raise FileNotFoundError(f"Icon not found: {name}")

    def render(self, level: int | None, settings: Settings) -> Image.Image:
        match battery_status(level, settings):
            case BatteryStatus.CRITICAL:
                name = "critical"
            case BatteryStatus.LOW:
                name = "low"
            case _:
                name = "medium" if level is not None and level <= MEDIUM_THRESHOLD else "full"
        return Image.open(image_path(f"battery-{name}.png"))
