"""
Render the app icon from assets/icon/app-icon.svg into the files the builds use:
the Windows .ico, the macOS .icns and a 256 px PNG, for Rust and for the Python package.

    uvx --from cairosvg --with pillow python scripts/render_app_icon.py
"""

import io
from pathlib import Path

import cairosvg
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets/icon/app-icon.svg"
ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]
PNG_OUTPUTS = [ROOT / "assets/icon/app-icon.png", ROOT / "src/battery_notifier/assets/app-icon.png"]


def render(size: int) -> Image.Image:
    png = cairosvg.svg2png(url=str(SOURCE), output_width=size, output_height=size)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def main():
    # Each .ico size is rendered from the SVG, sharper than scaling one bitmap down
    sizes = [render(size) for size in ICO_SIZES]
    sizes[-1].save(ROOT / "assets/icon/app-icon.ico", sizes=[(s, s) for s in ICO_SIZES], append_images=sizes[:-1])
    render(1024).save(ROOT / "assets/icon/app-icon.icns")
    for path in PNG_OUTPUTS:
        sizes[-1].save(path)
    print("Rendered", ", ".join(str(path.relative_to(ROOT)) for path in [*PNG_OUTPUTS, SOURCE.with_suffix(".ico")]))


if __name__ == "__main__":
    main()
