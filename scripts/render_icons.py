"""Render the tray icon for a few battery levels on dark and light taskbars, into a PNG preview."""

import sys

from PIL import Image

from battery_notifier.core.settings import Settings
from battery_notifier.platforms import current_platform
from battery_notifier.ui.icon import SIZE, icon_renderer

LEVELS = [None, 100, 60, 30, 15, 5]
BACKGROUNDS = {True: "#202020", False: "#f3f3f3"}
SCALES = [16, 32, 64]  # tray icon sizes at 100%, 200% DPI, and the source size
GAP = 8


def main(output: str):
    column = sum(SCALES) + GAP * len(SCALES)
    preview = Image.new("RGBA", (column * len(LEVELS), (SIZE + GAP) * len(BACKGROUNDS)))
    for row, (dark, background) in enumerate(BACKGROUNDS.items()):
        preview.paste(background, (0, row * (SIZE + GAP), preview.width, (row + 1) * (SIZE + GAP)))
        renderer = icon_renderer(current_platform(), lambda dark=dark: dark)
        for index, level in enumerate(LEVELS):
            icon = renderer.render(level, Settings())
            x = index * column + GAP // 2
            for scale in SCALES:
                preview.alpha_composite(icon.resize((scale, scale), Image.Resampling.LANCZOS), (x, row * (SIZE + GAP)))
                x += scale + GAP
    preview.save(output)
    print(f"Saved {output}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "icons.png")
