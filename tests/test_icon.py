import pytest

from battery_notifier.core.settings import Settings
from battery_notifier.ui.icon import (
    COLORS,
    SIZE,
    THEME_COLORS,
    UNKNOWN_GLYPH,
    BatteryStatus,
    DrawnIconRenderer,
    battery_glyph,
    icon_color,
)

OPAQUE = 255


@pytest.mark.parametrize(
    "level, code",
    [(0, 0xE850), (4, 0xE850), (5, 0xE850), (6, 0xE851), (42, 0xE854), (90, 0xE859), (95, 0xE83F), (100, 0xE83F)],
)
def test_battery_glyph(level, code):
    assert battery_glyph(level) == chr(code)


def test_unknown_battery_glyph():
    assert battery_glyph(None) == UNKNOWN_GLYPH


@pytest.mark.parametrize("dark", [True, False])
def test_icon_color(dark):
    settings = Settings(low_threshold=20, critical_threshold=10)
    assert icon_color(80, settings, dark) == THEME_COLORS[dark]
    assert icon_color(None, settings, dark) == THEME_COLORS[dark]
    assert icon_color(15, settings, dark) == COLORS[BatteryStatus.LOW]
    assert icon_color(5, settings, dark) == COLORS[BatteryStatus.CRITICAL]


def test_drawn_icon_fills_up_to_the_level():
    renderer = DrawnIconRenderer(lambda: True)
    empty, full = renderer.render(0, Settings()), renderer.render(100, Settings())

    assert empty.size == full.size == (SIZE, SIZE)
    center = (SIZE // 2, SIZE // 2)
    assert empty.getchannel("A").getpixel(center) == 0  # transparent inside an empty battery
    assert full.getchannel("A").getpixel(center) == OPAQUE
