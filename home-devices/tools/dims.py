"""Draw dimensioned technical drawings as SVG over orthographic renders.

Plain Python (no Blender needed). Reads renders/dims.json (numbers from the model)
and renders/dwg_cameras.json (where each orthographic camera was), so every line
lands on the geometry it measures.

    python dims.py <device_dir>
"""
import base64
import io
import json
import os
import subprocess
import sys

INK = "#1b1b1d"
ACCENT = "#c8231c"
FONT = "JetBrains Mono, ui-monospace, Consolas, monospace"

# screen axes per view: world axis index and sign for screen-right and screen-up
AXES = {
    "front": ((0, 1), (2, 1)), "back": ((0, -1), (2, 1)),
    "left": ((1, -1), (2, 1)), "right": ((1, 1), (2, 1)),
    "top": ((0, 1), (1, 1)), "bottom": ((0, 1), (1, -1)),
}


class Sheet:
    def __init__(self, png, cam, pad=(0, 0, 0, 0)):
        self.cam = cam
        self.w, self.h = cam["res"]
        self.k = self.w / cam["scale_mm"]           # px per mm
        self.png = png
        self.els = []
        self.crop = pad

    def p(self, a, b):
        """Screen-plane mm (right, up), relative to world origin -> px."""
        (ia, sa), (ib, sb) = AXES[self.cam["view"]]
        c = self.cam["center_mm"]
        ca, cb = sa * c[ia], sb * c[ib]
        return self.w / 2 + (a - ca) * self.k, self.h / 2 - (b - cb) * self.k

    def line(self, a1, b1, a2, b2, w=1.2, color=INK, dash=None):
        x1, y1 = self.p(a1, b1)
        x2, y2 = self.p(a2, b2)
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.els.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                        f'stroke="{color}" stroke-width="{w}"{d}/>')

    def text(self, a, b, s, anchor="middle", size=24, color=INK, dy=0, rot=0, weight=500):
        x, y = self.p(a, b)
        t = f' transform="rotate({rot} {x:.1f} {y + dy:.1f})"' if rot else ""
        self.els.append(f'<text x="{x:.1f}" y="{y + dy:.1f}" font-family="{FONT}" '
                        f'font-size="{size}" font-weight="{weight}" fill="{color}" '
                        f'text-anchor="{anchor}" dominant-baseline="middle"{t}>{s}</text>')

    def _arrow(self, x, y, dx, dy, color=INK):
        import math
        n = math.hypot(dx, dy) or 1
        ux, uy = dx / n, dy / n
        L, Wd = 14, 5
        p1 = (x, y)
        p2 = (x - ux * L - uy * Wd, y - uy * L + ux * Wd)
        p3 = (x - ux * L + uy * Wd, y - uy * L - ux * Wd)
        self.els.append(f'<polygon points="{p1[0]:.1f},{p1[1]:.1f} {p2[0]:.1f},{p2[1]:.1f} '
                        f'{p3[0]:.1f},{p3[1]:.1f}" fill="{color}"/>')

    def dim_h(self, a1, a2, b_feat, b_line, label, color=INK):
        """Horizontal dimension between screen-x a1..a2, measured at b_line."""
        gap = 1.0 if b_line < b_feat else -1.0
        self.line(a1, b_feat - gap * 0.8, a1, b_line - gap * 1.5, w=0.8, color=color)
        self.line(a2, b_feat - gap * 0.8, a2, b_line - gap * 1.5, w=0.8, color=color)
        self.line(a1, b_line, a2, b_line, w=1.2, color=color)
        x1, y = self.p(a1, b_line)
        x2, _ = self.p(a2, b_line)
        self._arrow(x1, y, x1 - x2, 0, color)
        self._arrow(x2, y, x2 - x1, 0, color)
        self.text((a1 + a2) / 2, b_line, label, dy=-18 if b_line > b_feat else 22, color=color)

    def dim_v(self, b1, b2, a_feat, a_line, label, color=INK):
        gap = 1.0 if a_line < a_feat else -1.0
        self.line(a_feat - gap * 0.8, b1, a_line - gap * 1.5, b1, w=0.8, color=color)
        self.line(a_feat - gap * 0.8, b2, a_line - gap * 1.5, b2, w=0.8, color=color)
        self.line(a_line, b1, a_line, b2, w=1.2, color=color)
        x, y1 = self.p(a_line, b1)
        _, y2 = self.p(a_line, b2)
        self._arrow(x, y1, 0, y1 - y2, color)
        self._arrow(x, y2, 0, y2 - y1, color)
        side = -1 if a_line < a_feat else 1
        tx, ty = self.p(a_line, (b1 + b2) / 2)
        tx += side * 18
        self.els.append(f'<text x="{tx:.1f}" y="{ty:.1f}" font-family="{FONT}" font-size="24" '
                        f'font-weight="500" fill="{color}" text-anchor="middle" '
                        f'dominant-baseline="middle" transform="rotate(-90 {tx:.1f} {ty:.1f})">'
                        f'{label}</text>')

    def leader(self, a, b, a_t, b_t, label, color=INK, anchor="start"):
        self.line(a, b, a_t, b_t, w=1.0, color=color)
        x, y = self.p(a, b)
        self.els.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}"/>')
        self.text(a_t, b_t, label, anchor=anchor, dy=-16, color=color, size=22)

    def svg(self, title, note=""):
        img = subprocess.run(["convert", self.png, "-background", "white", "-flatten",
                              "-quality", "90", "jpg:-"], capture_output=True, check=True).stdout
        b64 = base64.b64encode(img).decode()
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


def fmt(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def build(device_dir):
    rd = os.path.join(device_dir, "renders")
    d = json.load(open(os.path.join(rd, "dims.json")))
    cams = json.load(open(os.path.join(rd, "dwg_cameras.json")))
    W, D, T, B = d["W"], d["D"], d["TOP"], d["BASE_T"]
    rev = d["rev"]
    out = {}

    def sheet(name):
        return Sheet(os.path.join(rd, f"dwg_{name}.png"), cams[name])

    # FRONT: overall size, light pipe position
    s = sheet("front")
    s.dim_h(-W / 2, W / 2, 0, -9, f"{fmt(W)}")
    s.dim_v(0, T, -W / 2, -W / 2 - 9, f"{fmt(T)}")
    s.dim_v(0, B, W / 2, W / 2 + 7, f"{fmt(B)} base")
    p = d["pipe"]
    s.dim_h(p["x"], W / 2, p["z"], T + 8, f"{fmt(W / 2 - p['x'])}", color=ACCENT)
    s.dim_v(0, p["z"], p["x"], p["x"] - 8, f"{fmt(p['z'])}", color=ACCENT)
    s.leader(p["x"] + 1.4, p["z"] + 1.4, p["x"] + 12, p["z"] + 9,
             f"Ø{fmt(p['d'])} light pipe (hole Ø{fmt(p['hole_d'])})", color=ACCENT)
    out["front"] = s.svg(f"FRONT  ·  REV {rev}  ·  mm")

    # LEFT END: port window
    s = sheet("left")
    pw = d["port_win"]
    a0, a1 = -pw["y1"], -pw["y0"]          # screen-right is -Y
    s.dim_h(-D / 2, D / 2, 0, -9, f"{fmt(D)}")
    s.dim_h(a0, a1, pw["z1"], T + 8, f"{fmt(a1 - a0)} window", color=ACCENT)
    s.dim_v(pw["z0"], pw["z1"], a1, a1 + 8, f"{fmt(pw['z1'] - pw['z0'])}", color=ACCENT)
    s.dim_v(0, pw["z0"], a0, a0 - 8, f"{fmt(pw['z0'])}", color=ACCENT)
    out["left"] = s.svg(f"PORTS END  ·  REV {rev}  ·  mm",
                        "Window sized from Pi 5 port data: " + d["pi_source"])

    # BACK: USB-C slot
    s = sheet("back")
    u = d["usbc"]
    ua = -u["x"]                          # screen-right is -X
    s.dim_h(ua - u["w"] / 2, ua + u["w"] / 2, u["z"] + u["h"] / 2, T + 8,
            f"{fmt(u['w'])}", color=ACCENT)
    s.dim_v(u["z"] - u["h"] / 2, u["z"] + u["h"] / 2, ua + u["w"] / 2, ua + u["w"] / 2 + 8,
            f"{fmt(u['h'])}", color=ACCENT)
    s.dim_h(-W / 2, ua, 0, -9, f"{fmt(W / 2 - u['x'])} to centre")
    s.dim_v(0, u["z"], ua - u["w"] / 2, ua - u["w"] / 2 - 8, f"{fmt(u['z'])}")
    out["back"] = s.svg(f"BACK · USB-C  ·  REV {rev}  ·  mm",
                        "Slot clears the plug's moulded grip, not just the metal tip")

    # TOP: footprint, vents, label
    s = sheet("top")
    s.dim_h(-W / 2, W / 2, -D / 2, -D / 2 - 9, f"{fmt(W)}")
    s.dim_v(-D / 2, D / 2, -W / 2, -W / 2 - 9, f"{fmt(D)}")
    fx, fy = d["fan_c"]
    s.dim_h(fx - 17, fx + 17, fy - 17, fy - 21, "Ø34 vent field", color=ACCENT)
    s.leader(fx + 1.95, fy, fx + 26, fy + 8, "Ø2.2 holes, 3.9 hex pitch", color=ACCENT)
    s.leader(W / 2 - R_corner(d), D / 2 - 3, W / 2 - 4, D / 2 + 6, f"R{fmt(d['R'])}",
             anchor="end")
    s.leader(W / 2 - 22, -D / 2 + 11.5, W / 2 - 10, -D / 2 + 22, "label 4.2 tall, 0.8 deep",
             anchor="end")
    out["top"] = s.svg(f"TOP  ·  REV {rev}  ·  mm")

    # BOTTOM: screws, feet
    s = sheet("bottom")
    bx = abs(d["boss"][0][0])
    by = abs(d["boss"][0][1])
    s.dim_h(-bx, bx, by, -by - 8, f"{fmt(2 * bx)}", color=ACCENT)    # bottom: up = -Y
    s.dim_v(-by, by, bx, bx + 9, f"{fmt(2 * by)}", color=ACCENT)
    s.leader(-bx + 2.2, -by + 2.2, -bx + 14, -by + 12, "4× M3 countersunk", color=ACCENT)
    fx0, fy0 = d["feet"][0]
    s.leader(fx0 + 3, fy0, fx0 + 16, fy0 + 7, "4× Ø8.6 recess for feet", anchor="start")
    out["bottom"] = s.svg(f"UNDERSIDE  ·  REV {rev}  ·  mm")

    # SECTION through the LED
    s = sheet("section_led")
    y_out, y_in = -D / 2, -D / 2 + d["WALL"]
    sk, pz = d["socket"], p["z"]
    s.dim_h(y_out, y_in, pz - 6, pz - 9, f"{fmt(d['WALL'])} wall")
    s.dim_h(y_in, y_in + sk["len"], pz + sk["od"] / 2, pz + 8, f"{fmt(sk['len'])} socket",
            color=ACCENT)
    s.dim_v(pz - sk["id"] / 2, pz + sk["id"] / 2, y_in + sk["len"], y_in + sk["len"] + 4,
            f"Ø{fmt(sk['id'])}", color=ACCENT)
    s.dim_v(pz - p["d"] / 2, pz + p["d"] / 2, y_out, y_out - 3, f"Ø{fmt(p['d'])}")
    s.leader(y_in + 0.4, pz + p["collar_d"] / 2 - 0.3, y_in - 2, pz + 7,
             f"collar Ø{fmt(p['collar_d'])} × {fmt(p['collar_t'])}", anchor="end")
    s.leader(y_in + 5, pz - 1.5, y_in + 7, pz - 7.5, "5 mm LED, tip on collar", color=ACCENT)
    s.leader(y_in + sk["len"] - 1, pz + sk["od"] / 2 - 0.3, y_in + sk["len"] + 2, pz + 7,
             f"socket OD Ø{fmt(sk['od'])}")
    out["section_led"] = s.svg(f"SECTION THROUGH LIGHT  ·  REV {rev}  ·  mm  ·  enlarged")

    for k, v in out.items():
        with open(os.path.join(rd, f"dwg_{k}.svg"), "w") as f:
            f.write(v)
    return list(out)


def R_corner(d):
    return d["R"] * 0.3


if __name__ == "__main__":
    print(build(sys.argv[1] if len(sys.argv) > 1 else "."))
