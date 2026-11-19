"""Dimensioned SVG drawings for the purge bin, over the orthographic renders.

    uv run --no-project --with pillow python bin_dims.py

Reads renders/dims.json and renders/dwg_cameras.json (written by purge_bin.py --drawings).
Uses tools/dims.py's Sheet, but embeds the render with Pillow (on Windows, `convert` is the
disk converter, not ImageMagick).
"""
import base64
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
from dims import ACCENT, FONT, INK, Sheet, fmt  # noqa: E402
from PIL import Image  # noqa: E402


class PilSheet(Sheet):
    def svg(self, title, note=""):
        im = Image.open(self.png).convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        buf = io.BytesIO()
        bg.convert("RGB").save(buf, "JPEG", quality=90)
        b64 = base64.b64encode(buf.getvalue()).decode()
        foot = (f'<text x="24" y="{self.h - 24}" font-family="{FONT}" font-size="20" '
                f'fill="#77777a">{note}</text>') if note else ""
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" '
                f'width="{self.w}" height="{self.h}">'
                f'<rect width="100%" height="100%" fill="#ffffff"/>'
                f'<image href="data:image/jpeg;base64,{b64}" width="{self.w}" '
                f'height="{self.h}"/>'
                f'<text x="24" y="40" font-family="{FONT}" font-size="22" font-weight="600" '
                f'fill="{INK}" letter-spacing="2">{title}</text>'
                + "".join(self.els) + foot + "</svg>")


def main():
    rd = os.path.join(HERE, "renders")
    d = json.load(open(os.path.join(rd, "dims.json")))
    cams = json.load(open(os.path.join(rd, "dwg_cameras.json")))
    W, D, T, B = d["W"], d["D"], d["TOP"], d["BASE_T"]
    rev = d["rev"]
    out = {}

    def sheet(name):
        return PilSheet(os.path.join(rd, f"dwg_{name}.png"), cams[name])

    # FRONT (looks +Y; right = +X, up = +Z)
    s = sheet("front")
    s.dim_h(-W / 2, W / 2, 0, -7, fmt(W))
    s.dim_v(0, T, -W / 2, -W / 2 - 8, fmt(T))
    s.dim_v(0, B, W / 2, W / 2 + 6, f"{fmt(B)} base")
    lb = d["label_box"]
    s.dim_v(lb[1], lb[3], lb[2], lb[2] + 6, fmt(lb[3] - lb[1]), color=ACCENT)
    s.dim_v(lb[3], T, lb[0], lb[0] - 5, fmt(T - lb[3]), color=ACCENT)
    s.leader(lb[0] + 2, lb[1] + 0.5, -W / 2 + 4, 12,
             f"label {d['label_size']:g} mm bold mono, {fmt(d['engrave'])} deep", color=ACCENT)
    out["front"] = s.svg(f"FRONT  ·  REV {rev}  ·  mm")

    # LEFT (looks +X; right = -Y, up = +Z): the long side away from the printer
    s = sheet("left")
    s.dim_h(-D / 2, D / 2, 0, -7, fmt(D))
    s.dim_v(0, T, -D / 2, -D / 2 - 8, fmt(T))
    s.leader(D / 2 - 3, T - 0.6, D / 2 - 18, T + 9, f"R{fmt(d['EDGE'])} top edge", anchor="end")
    out["left"] = s.svg(f"OUTER SIDE  ·  REV {rev}  ·  mm",
                        "Printer side (+X) is identical; the bin is symmetric")

    # TOP (looks -Z; right = +X, up = +Y)
    s = sheet("top")
    s.dim_h(-W / 2, W / 2, -D / 2, -D / 2 - 8, fmt(W))
    s.dim_v(-D / 2, D / 2, -W / 2, -W / 2 - 8, fmt(D))
    r = d["R"]
    s.leader(W / 2 - r * 0.3, D / 2 - r * 0.3, W / 2 + 8, D / 2 + 6, f"R{fmt(r)}")
    s.dim_h(W / 2 - d["WALL"], W / 2, 10, 20, f"{fmt(d['WALL'])} wall", color=ACCENT)
    s.text(0, 0, "PRINTER SIDE →", size=22, color="#77777a")
    out["top"] = s.svg(f"TOP  ·  REV {rev}  ·  mm")

    # SECTION at y = pin row, seen from the front
    s = sheet("section")
    px, ph = d["pins"][2][0], d["hole_h"]
    s.dim_v(B, B + d["FLOOR"], -W / 2 + d["WALL"] + 10, -W / 2 + d["WALL"] + 10,
            f"{fmt(d['FLOOR'])} floor")
    s.dim_h(-W / 2, -W / 2 + d["WALL"], 30, 34, f"{fmt(d['WALL'])}", color=ACCENT)
    s.leader(-W / 2 + d["WALL"] + d["FLOOR_R"] * 0.3, B + d["FLOOR"] + d["FLOOR_R"] * 0.3,
             -W / 2 + 14, 22, f"R{fmt(d['FLOOR_R'])} inside floor", color=ACCENT)
    s.leader(px + d["hole_d"] / 2, B + ph - 0.3, px + 4, 16,
             f"4× pin Ø{fmt(d['pin_d'])} × {fmt(d['pin_h'])} in Ø{fmt(d['hole_d'])} × "
             f"{fmt(ph)} hole", anchor="end")
    s.leader(W / 2 - d["GAP"] / 2, B / 2, W / 2 + 4, -5, f"{fmt(d['GAP'])} shadow line")
    out["section"] = s.svg(f"SECTION THROUGH PINS  ·  REV {rev}  ·  mm")

    for k, v in out.items():
        with open(os.path.join(rd, f"dwg_{k}.svg"), "w", encoding="utf-8") as f:
            f.write(v)
    print(list(out))


if __name__ == "__main__":
    main()
