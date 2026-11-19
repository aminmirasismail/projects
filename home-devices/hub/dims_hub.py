"""Dimensioned drawings for the hub, Rev D (underglow), as SVG over the orthographic renders.

    python dims_hub.py            (needs Pillow; run after `hub.py --drawings`)

Numbers come from renders/dims.json, camera framing from renders/dwg_cameras.json, so every
line lands on the geometry it measures. Text is 1.5x the shared tool's size (readable at
page width), and the image is embedded as JPEG via Pillow (no ImageMagick needed).
"""
import base64
import io
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import dims as D0  # noqa: E402
from PIL import Image  # noqa: E402

K = 1.5                       # text and arrow scale
INK, ACCENT, FONT = D0.INK, D0.ACCENT, D0.FONT
fmt = D0.fmt


class Sheet(D0.Sheet):
    def text(self, a, b, s, anchor="middle", size=24, color=INK, dy=0, rot=0, weight=500):
        super().text(a, b, s, anchor=anchor, size=size * K, color=color, dy=dy * K, rot=rot,
                     weight=weight)

    def _arrow(self, x, y, dx, dy, color=INK):
        n = math.hypot(dx, dy) or 1
        ux, uy = dx / n, dy / n
        L, Wd = 14 * K, 5 * K
        p2 = (x - ux * L - uy * Wd, y - uy * L + ux * Wd)
        p3 = (x - ux * L + uy * Wd, y - uy * L - ux * Wd)
        self.els.append(f'<polygon points="{x:.1f},{y:.1f} {p2[0]:.1f},{p2[1]:.1f} '
                        f'{p3[0]:.1f},{p3[1]:.1f}" fill="{color}"/>')

    def dim_v(self, b1, b2, a_feat, a_line, label, color=INK):
        n = len(self.els)
        super().dim_v(b1, b2, a_feat, a_line, label, color)
        # the parent writes the vertical label at 24 px, 18 px off the line: scale both
        t = self.els[-1]
        side = -1 if a_line < a_feat else 1
        tx, ty = self.p(a_line, (b1 + b2) / 2)
        tx += side * 18 * K
        self.els[-1] = (f'<text x="{tx:.1f}" y="{ty:.1f}" font-family="{FONT}" '
                        f'font-size="{24 * K:.0f}" font-weight="500" fill="{color}" '
                        f'text-anchor="middle" dominant-baseline="middle" '
                        f'transform="rotate(-90 {tx:.1f} {ty:.1f})">{label}</text>')
        assert len(self.els) == n + 6 and t.startswith("<text")

    def svg(self, title, note=""):
        im = Image.open(self.png)
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1] if im.mode == "RGBA" else None)
        buf = io.BytesIO()
        bg.save(buf, "JPEG", quality=90)
        b64 = base64.b64encode(buf.getvalue()).decode()
        fs = 22 * K
        foot = (f'<text x="24" y="{self.h - 28}" font-family="{FONT}" font-size="{20 * K:.0f}" '
                f'fill="#66666a">{note}</text>') if note else ""
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" '
                f'width="{self.w}" height="{self.h}">'
                f'<rect width="100%" height="100%" fill="#ffffff"/>'
                f'<image href="data:image/jpeg;base64,{b64}" width="{self.w}" '
                f'height="{self.h}"/>'
                f'<text x="24" y="{24 + fs:.0f}" font-family="{FONT}" font-size="{fs:.0f}" '
                f'font-weight="600" fill="{INK}" letter-spacing="2">{title}</text>'
                + "".join(self.els) + foot + "</svg>")


def build():
    rd = os.path.join(HERE, "renders")
    d = json.load(open(os.path.join(rd, "dims.json")))
    cams = json.load(open(os.path.join(rd, "dwg_cameras.json")))
    W, Dp, T, L = d["W"], d["D"], d["TOP"], d["LIFT"]
    rev, pl, st = d["rev"], d["plinth"], d["strip"]
    out = {}

    def sheet(name):
        return Sheet(os.path.join(rd, f"dwg_{name}.png"), cams[name])

    # FRONT: overall size and the float
    s = sheet("front")
    s.dim_h(-W / 2, W / 2, 0, -10, fmt(W))
    s.dim_v(0, T, -W / 2, -W / 2 - 10, fmt(T))
    s.dim_v(0, L, W / 2, W / 2 + 8, f"{fmt(L)} float", color=ACCENT)
    fi = pl["foot_in"]
    s.dim_h(W / 2 - fi, W / 2, L / 2, T + 9, f"{fmt(fi)} foot inset", color=ACCENT)
    out["front"] = s.svg(f"FRONT  ·  REV {rev}  ·  mm")

    # LEFT END: port window
    s = sheet("left")
    pw = d["port_win"]
    a0, a1 = -pw["y1"], -pw["y0"]          # screen-right is -Y
    s.dim_h(-Dp / 2, Dp / 2, 0, -10, fmt(Dp))
    s.dim_h(a0, a1, pw["z1"], T + 9, f"{fmt(a1 - a0)} window", color=ACCENT)
    s.dim_v(pw["z0"], pw["z1"], a1, a1 + 9, fmt(pw["z1"] - pw["z0"]), color=ACCENT)
    s.dim_v(0, pw["z0"], a0, a0 - 9, fmt(pw["z0"]), color=ACCENT)
    out["left"] = s.svg(f"PORTS END  ·  REV {rev}  ·  mm",
                        "Window from Pi 5 port data: " + d["pi_source"])

    # BACK: USB-C slot
    s = sheet("back")
    u = d["usbc"]
    ua = -u["x"]                          # screen-right is -X
    s.dim_h(ua - u["w"] / 2, ua + u["w"] / 2, u["z"] + u["h"] / 2, T + 9, fmt(u["w"]),
            color=ACCENT)
    s.dim_v(u["z"] - u["h"] / 2, u["z"] + u["h"] / 2, ua + u["w"] / 2, ua + u["w"] / 2 + 9,
            fmt(u["h"]), color=ACCENT)
    s.dim_h(-W / 2, ua, 0, -10, f"{fmt(W / 2 - u['x'])} to centre")
    s.dim_v(0, u["z"], ua - u["w"] / 2, ua - u["w"] / 2 - 9, fmt(u["z"]))
    out["back"] = s.svg(f"BACK · USB-C  ·  REV {rev}  ·  mm",
                        "Slot clears the plug's moulded grip, not just the metal tip")

    # TOP: footprint, corner, vents, label
    s = sheet("top")
    s.dim_h(-W / 2, W / 2, -Dp / 2, -Dp / 2 - 10, fmt(W))
    s.dim_v(-Dp / 2, Dp / 2, -W / 2, -W / 2 - 10, fmt(Dp))
    s.leader(W / 2 - d["R"] * 0.3, Dp / 2 - d["R"] * 0.3, W / 2 - 2, Dp / 2 + 7,
             f"R{fmt(d['R'])}", anchor="end")
    s.leader(14, 0, 30, 30, "Ø40 vent field, Ø2.2 holes", color=ACCENT)
    lab = d["label"]
    s.leader(W / 2 - lab["right_inset"] - 10, -Dp / 2 + lab["front_inset"] + 2,
             W / 2 - 18, -Dp / 2 - 6, f"label {fmt(lab['size'])} mono, 0.6 deep", anchor="end")
    out["top"] = s.svg(f"TOP  ·  REV {rev}  ·  mm")

    # BOTTOM: screws, foot, LED channel (bottom view: screen-up is -Y)
    s = sheet("bottom")
    bx, by = abs(d["boss"][0][0]), abs(d["boss"][0][1])
    s.dim_h(-bx, bx, -by, -by - 10, f"{fmt(2 * bx)} screws", color=ACCENT)
    s.dim_v(-by, by, bx, bx + 12, fmt(2 * by), color=ACCENT)
    s.leader(-bx, -by, -bx - 8, -by + 18, "4× M3×12 button head", color=ACCENT,
             anchor="end")
    fw, fd = W - 2 * pl["foot_in"], Dp - 2 * pl["foot_in"]
    s.dim_h(-fw / 2, fw / 2, -fd / 2, -fd / 2 + 7, f"{fmt(fw)} foot")
    s.dim_v(-fd / 2, fd / 2, -fw / 2, -fw / 2 + 8, f"{fmt(fd)}")
    fx0, fy0 = d["feet"][0]
    s.leader(fx0, -fy0, fx0 + 10, -fy0 - 10, f"4× Ø8.6 rubber feet", anchor="start")
    a = W / 2 - pl["ch_mid"]
    s.leader(a, 0, a - 22, 6, f"{st['n_long'] * 2 + st['n_short'] * 2} LEDs, 4 runs",
             color=ACCENT, anchor="end")
    out["bottom"] = s.svg(f"UNDERSIDE  ·  REV {rev}  ·  mm")

    # SECTION through the channel, +X end
    s = sheet("section_channel")
    xo = W / 2                               # shell outer face
    xi = W / 2 - d["WALL"]
    lin0 = W / 2 - pl["inset"]               # lining outer face
    ch0, ch1 = W / 2 - pl["ch_in0"], W / 2 - pl["ch_in1"]
    zled, zp = pl["z_led_face"], pl["z_plate_bot"]
    s.dim_v(0, L, xo, xo + 3.5, f"{fmt(L)} float", color=ACCENT)
    s.dim_v(L, zled, ch0 + 1.5, ch0 + 1.5, f"{fmt(zled - L)}", color=ACCENT)
    s.dim_h(ch1, ch0, zp, 14.5, f"{fmt(ch0 - ch1)} channel", color=ACCENT)
    s.dim_h(xi, xo, L + 9, L + 12.5, f"{fmt(d['WALL'])} wall")
    s.leader(ch0 + 0.5, pl["lining_z"] + 1.0, ch0 - 1.0, 3.0,
             f"{fmt(pl['lining_t'])} black lining", anchor="end")
    s.leader((ch0 + ch1) / 2, zled + 0.8, ch1 - 1.0, 17.0, "SK6812 RGBW, LEDs face down",
             color=ACCENT, anchor="end")
    s.leader(ch1 - 1.5, 1.5, ch1 + 1.0, 0.6, "foot", anchor="start")
    out["section_channel"] = s.svg(f"SECTION THROUGH THE LIGHT  ·  REV {rev}  ·  mm  ·  enlarged",
                                   "LED faces sit above the shell's bottom edge: hidden from the side")

    for k, v in out.items():
        with open(os.path.join(rd, f"dwg_{k}.svg"), "w", encoding="utf-8") as f:
            f.write(v)
    for old in ("dwg_section_led.svg",):           # earlier revisions
        p = os.path.join(rd, old)
        if os.path.exists(p):
            os.remove(p)
    return list(out)


if __name__ == "__main__":
    print(build())
