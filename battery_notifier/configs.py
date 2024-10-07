import sys
from pathlib import Path

ASSET_DIR = "assets"
DEFAULT_BATTERY_LEVEL = -1
NOTIFICATION_THRESHOLD = 20


def resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and for PyInstaller"""
    current_path = Path(__file__).parent.parent
    base_path = getattr(sys, "_MEIPASS", current_path.absolute())
    return base_path / relative_path


def image_path(image_name: str) -> Path:
    return resource_path(ASSET_DIR) / image_name
