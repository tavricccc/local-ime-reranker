"""Render the authored SVG glyphs to Windows multi-size ICO assets."""
import io
from pathlib import Path

import resvg_py
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
icons = ROOT / "rime/icons"
sizes = [(n, n) for n in (16, 20, 24, 32, 40, 48, 64, 128, 256)]
preview = Image.new("RGBA", (160, 80), "#F5F6F7")
for index, name in enumerate(("chinese", "english")):
    svg = (icons / f"{name}.svg").read_text("utf-8")
    bitmap = Image.open(io.BytesIO(resvg_py.svg_to_bytes(svg_string=svg, width=256, height=256))).convert("RGBA")
    bitmap.save(icons / f"{name}.ico", sizes=sizes)
    small = Image.open(io.BytesIO(resvg_py.svg_to_bytes(svg_string=svg, width=40, height=40))).convert("RGBA")
    preview.alpha_composite(small, (20 + index * 80, 20))
preview.save(icons / "preview.png")
print("Authored Chinese/English icons built", sizes)
