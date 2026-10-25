"""Neutral icon of a Type 2 charging plug (IEC 62196-2) for the integration.

Draws at 2048 px and scales down to 256 (icon.png) and 512 (icon@2x.png) for sharp edges.
Usage (needs Pillow): python tools/draw_icon.py custom_components/plugchoice/brand
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

S = 2048
OUT = Path(sys.argv[1])

BODY = (0, 137, 123, 255)  # teal: the outer rim of the plug
FACE = (0, 77, 64, 255)  # darker teal: the face with the contacts
PIN = (255, 255, 255, 255)


def type2_shape(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float, flat: float, fill) -> None:
    """Circle with a flat top: the typical Type 2 shape. flat = height of the flat edge above the centre."""
    mask = Image.new("L", (S, S), 0)
    m = ImageDraw.Draw(mask)
    m.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
    m.rectangle((0, 0, S, cy - flat), fill=0)
    draw._image.paste(Image.new("RGBA", (S, S), fill), (0, 0), mask)


img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

cx, cy = S / 2, S * 0.45  # shape runs from 0.11 to 0.91 of the height
type2_shape(d, cx, cy, S * 0.46, S * 0.34, BODY)
type2_shape(d, cx, cy, S * 0.39, S * 0.28, FACE)


def pin(x: float, y: float, r: float) -> None:
    d.ellipse((x - r, y - r, x + r, y + r), fill=PIN)


big, small = S * 0.075, S * 0.045
dx = S * 0.205
# Top: 2 small contacts (CP, PP); middle 3 and bottom 2 large ones (L1-L3, N, PE).
pin(cx - S * 0.11, cy - S * 0.19, small)
pin(cx + S * 0.11, cy - S * 0.19, small)
pin(cx - dx, cy + S * 0.01, big)
pin(cx, cy + S * 0.01, big)
pin(cx + dx, cy + S * 0.01, big)
pin(cx - S * 0.11, cy + S * 0.21, big)
pin(cx + S * 0.11, cy + S * 0.21, big)

OUT.mkdir(parents=True, exist_ok=True)
for name, size in (("icon.png", 256), ("icon@2x.png", 512)):
    img.resize((size, size), Image.LANCZOS).save(OUT / name, optimize=True)
    print(OUT / name, size)
