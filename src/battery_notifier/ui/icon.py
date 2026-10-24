"""
Tray icon: a battery glyph that follows the taskbar theme, amber when low and red when critical.
Uses the battery glyphs of the Windows icon font, or draws a battery where the font is missing.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageDraw, ImageFont

from battery_notifier.core.policy import BatteryStatus, battery_status
from battery_notifier.core.settings import Settings
from battery_notifier.platforms.base import Platform

SIZE = 64
COLORS = {
    BatteryStatus.LOW: "#ffb900",  # Windows amber
    BatteryStatus.CRITICAL: "#e81123",  # Windows red
}
THEME_COLORS = {True: "#ffffff", False: "#1c1c1c"}  # on dark / light background
# Segoe Fluent Icons / Segoe MDL2 Assets: Battery0 to Battery9, Battery10 is out of sequence
BATTERY_GLYPHS = [chr(code) for code in range(0xE850, 0xE85A)] + ["\ue83f"]
UNKNOWN_GLYPH = "\ue996"


class IconRenderer(Protocol):
    def render(self, level: int | None, settings: Settings) -> Image.Image:
        """Tray icon for the lowest battery level, None when no device reports one."""
        ...


def battery_glyph(level: int | None) -> str:
    if level is None:
        return UNKNOWN_GLYPH
    return BATTERY_GLYPHS[round(max(0, min(level, 100)) / 10)]


def icon_color(level: int | None, settings: Settings, dark_background: bool) -> str:
    return COLORS.get(battery_status(level, settings), THEME_COLORS[dark_background])


class GlyphIconRenderer:
    def __init__(self, font_path: Path, is_dark_background: Callable[[], bool]):
        self.font = ImageFont.truetype(str(font_path), SIZE)
        self.is_dark_background = is_dark_background

    def render(self, level: int | None, settings: Settings) -> Image.Image:
        image = Image.new("RGBA", (SIZE, SIZE))
        color = icon_color(level, settings, self.is_dark_background())
        ImageDraw.Draw(image).text((SIZE / 2, SIZE / 2), battery_glyph(level), font=self.font, fill=color, anchor="mm")
        return image


class DrawnIconRenderer:
    """Fallback for OSes without the icon font: a horizontal battery, filled up to the level."""

    def __init__(self, is_dark_background: Callable[[], bool]):
        self.is_dark_background = is_dark_background

    def render(self, level: int | None, settings: Settings) -> Image.Image:
        image = Image.new("RGBA", (SIZE, SIZE))
        draw = ImageDraw.Draw(image)
        color = icon_color(level, settings, self.is_dark_background())
        left, top, right, bottom, stroke = 4, 18, 54, 46, 4
        draw.rounded_rectangle((left, top, right, bottom), radius=6, outline=color, width=stroke)
        draw.rounded_rectangle((right + 2, 26, right + 7, 38), radius=2, fill=color)  # terminal
        if level is not None and level > 0:
            inner = right - left - 4 * stroke
            fill_right = left + 2 * stroke + inner * min(level, 100) / 100
            draw.rectangle((left + 2 * stroke, top + 2 * stroke, fill_right, bottom - 2 * stroke), fill=color)
        return image


def icon_renderer(platform: Platform, is_dark_background: Callable[[], bool]) -> IconRenderer:
    font_path = platform.icon_font()
    if font_path is not None:
        return GlyphIconRenderer(font_path, is_dark_background)
    return DrawnIconRenderer(is_dark_background)
