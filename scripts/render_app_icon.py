"""
Render the app icon from src/battery_notifier/assets/app-icon.svg into the files beside it:
a 256 px PNG (loaded by the Python dialog, embedded in the Rust binary), the Windows .ico and the macOS .icns.
They live in the Python package, which must contain the PNG at runtime.

    uvx --from cairosvg --with pillow python scripts/render_app_icon.py
"""

import io
from pathlib import Path

import cairosvg
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "src/battery_notifier/assets"
SOURCE = ASSETS / "app-icon.svg"
ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]
PNG = ASSETS / "app-icon.png"


def render(size: int) -> Image.Image:
    png = cairosvg.svg2png(url=str(SOURCE), output_width=size, output_height=size)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def main():
    # Each .ico size is rendered from the SVG, sharper than scaling one bitmap down
    sizes = [render(size) for size in ICO_SIZES]
    sizes[-1].save(ASSETS / "app-icon.ico", sizes=[(s, s) for s in ICO_SIZES], append_images=sizes[:-1])
    render(1024).save(ASSETS / "app-icon.icns")
    sizes[-1].save(PNG)
    print("Rendered the .png, .ico and .icns in", ASSETS.relative_to(ROOT))


if __name__ == "__main__":
    main()
