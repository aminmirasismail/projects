"""Dimensioned drawings of the bag hook as SVG, drawn straight from the model's numbers.

Plain Python (no Blender). Reads renders/dims.json written by bag_hook.py.

    python bag_dims.py        -> renders/dwg_front.svg, dwg_section.svg, dwg_back.svg

Text and strokes are sized for the review page, where each drawing is shown full width
(~1100 px), so 16 px text on a ~1000 px wide sheet reads at about 17 px on screen.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "renders")
D = json.load(open(os.path.join(OUT, "dims.json")))

INK, ACC, MUTE, STEEL = "#1b1b1d", "#c8231c", "#8a8a90", "#6d7480"
FONT = "JetBrains Mono, ui-monospace, Consolas, monospace"
FS = 17


class Sheet:
    """mm drawing space -> px; y up in mm, down in px."""

    def __init__(self, w_px, h_px, k, origin):
        self.w, self.h, self.k, self.o = w_px, h_px, k, origin
        self.els = []

    def p(self, x, y):
        return self.o[0] + x * self.k, self.o[1] - y * self.k

    def poly(self, pts, fill="#e8e8e6", stroke=INK, sw=2.0, dash=None, close=True):
        d = " ".join(f"{a:.1f},{b:.1f}" for a, b in (self.p(*q) for q in pts))
        tag = "polygon" if close else "polyline"
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self.els.append(f'<{tag} points="{d}" fill="{fill}" stroke="{stroke}" '
                        f'stroke-width="{sw}" stroke-linejoin="round"{da}/>')

    def line(self, a, b, stroke=INK, sw=1.2, dash=None):
        (x1, y1), (x2, y2) = self.p(*a), self.p(*b)
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self.els.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                        f'stroke="{stroke}" stroke-width="{sw}"{da}/>')

    def text(self, xy, s, anchor="middle", color=INK, size=FS, px=False, rot=0, weight=400):
        x, y = xy if px else self.p(*xy)
        tr = f' transform="rotate({rot} {x:.1f} {y:.1f})"' if rot else ""
        self.els.append(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}" '
                        f'font-weight="{weight}" fill="{color}" text-anchor="{anchor}"{tr}>{s}</text>')

    def arrow(self, tip, frm, color=INK):
        (tx, ty), (fx, fy) = self.p(*tip), self.p(*frm)
        a = math.atan2(ty - fy, tx - fx)
        L, w = 11, 4
        p1 = (tx - L * math.cos(a) + w * math.sin(a), ty - L * math.sin(a) - w * math.cos(a))
        p2 = (tx - L * math.cos(a) - w * math.sin(a), ty - L * math.sin(a) + w * math.cos(a))
        self.els.append(f'<polygon points="{tx:.1f},{ty:.1f} {p1[0]:.1f},{p1[1]:.1f} '
                        f'{p2[0]:.1f},{p2[1]:.1f}" fill="{color}"/>')

    def dim(self, a, b, off, label, color=INK, horiz=None):
        """Linear dimension between points a and b, offset `off` mm perpendicular."""
        horiz = abs(a[1] - b[1]) < 1e-6 if horiz is None else horiz
        if horiz:
            y = a[1] + off
            A, B = (a[0], y), (b[0], y)
            self.line(a, (a[0], y + math.copysign(1.5, off)), MUTE, 1)
            self.line(b, (b[0], y + math.copysign(1.5, off)), MUTE, 1)
            mid = ((A[0] + B[0]) / 2, y)
            tx, ty = self.p(*mid)
            ty += -7 if off > 0 else 21
        else:
            x = a[0] + off
            A, B = (x, a[1]), (x, b[1])
            self.line(a, (x + math.copysign(1.5, off), a[1]), MUTE, 1)
            self.line(b, (x + math.copysign(1.5, off), b[1]), MUTE, 1)
            mid = (x, (A[1] + B[1]) / 2)
            tx, ty = self.p(*mid)
        self.line(A, B, color, 1.3)
        self.arrow(A, B, color)
        self.arrow(B, A, color)
        if horiz:
            self.text((tx, ty), label, px=True, color=color)
        else:
            tx += -9 if off < 0 else 22
            self.text((tx, ty), label, px=True, color=color, rot=-90)

    def note(self, xy, s, anchor="start", color=INK, size=FS - 1):
        self.text(xy, s, anchor=anchor, color=color, size=size)

    def svg(self, title):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" '
                f'width="{self.w}" height="{self.h}"><rect width="100%" height="100%" fill="#fff"/>'
                f'<text x="24" y="34" font-family="{FONT}" font-size="{FS + 3}" font-weight="700" '
                f'fill="{INK}">{title}</text>' + "".join(self.els) + "</svg>")


def arcp(c, r, a0, a1, n=24):
    return [(c[0] + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             c[1] + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def outline(W, H, R):
    k = R * (1 - math.cos(math.radians(45)))
    pts = [(2 * k, 0), (W - 2 * k, 0)] + arcp((W - R, R), R, -45, 0) + arcp((W - R, H - R), R, 0, 45)
    pts += [(W - 2 * k, H), (2 * k, H)] + arcp((R, H - R), R, 135, 180) + arcp((R, R), R, 180, 225)
    return pts


def peg_side(T, d, ang, L, z0):
    """Peg silhouette from the side: (u, z) polygon, from the front face to the end face."""
    a = math.radians(ang)
    ax, az = math.cos(a), math.sin(a)
    nx, nz = -az, ax
    r = d / 2
    s = (T, z0)
    e = (T + L * ax, z0 + L * az)
    # where the two silhouette lines meet the front face u = T
    lo = (T, z0 - r / ax)
    hi = (T, z0 + r / ax)
    return [lo, (e[0] - nx * r, e[1] - nz * r), (e[0] + nx * r, e[1] + nz * r), hi], s, e


def front():
    W, H, R = D["W"], D["H"], D["R"]
    pg = D["peg"]
    k = 7.0
    sh = Sheet(1080, 760, k, (150, 640))
    sh.poly(outline(W, H, R))
    a = math.radians(pg["angle"])
    r = pg["d"] / 2
    for px in pg["x"]:
        # peg seen from the front: root ellipse merged with the end disc, as a stadium
        z0, z1 = pg["z"], pg["z"] + pg["len"] * math.sin(a)
        pts = arcp((px, z1), r, 0, 180) + arcp((px, z0), r, 180, 360)
        sh.poly(pts, fill="#f6f6f4", sw=1.6)
        sh.poly(arcp((px, z1), r, 0, 360, 48), fill="#fbfbfa", sw=1.6)
        sh.line((px, z0 - 4), (px, z1 + r + 4), MUTE, 0.8, "6 4")
    lb = D["label_box"]
    sh.poly([(lb[0], lb[1]), (lb[2], lb[1]), (lb[2], lb[3]), (lb[0], lb[3])], fill="none",
            stroke=ACC, sw=1.2, dash="4 3")
    sh.note(((lb[0] + lb[2]) / 2, (lb[1] + lb[3]) / 2 - 1.6), "BAGS · 01", "middle", ACC, FS - 2)
    sh.dim((0, 0), (W, 0), -12, f"{W:.0f}")
    sh.dim((W, 0), (W, H), 12, f"{H:.0f}")
    sh.dim((pg["x"][0], H), (pg["x"][1], H), 9, f"{pg['x'][1] - pg['x'][0]:.0f} peg spacing")
    sh.dim((0, H), (pg["x"][0], H), 9, f"{pg['x'][0]:.0f}")
    sh.dim((0, 0), (0, pg["z"]), -10, f"{pg['z']:.0f}", horiz=False)
    sh.note((W + 24, H - 6), f"corners R{R:.0f}, stopped at 45°", size=FS - 2)
    sh.note((W + 24, H - 12), "with a short 45° flat (bed)", size=FS - 2)
    sh.note((W + 24, H - 21), f"rims R{D['edge']}", size=FS - 2)
    sh.note((W + 24, 16), f"pegs Ø{pg['d']:.0f}, {pg['angle']:.0f}° up", size=FS - 2)
    sh.note((W + 24, 10), f"{pg['len']:.0f} mm long", size=FS - 2)
    sh.note((W + 24, 2), "label 6 mm, 0.6 deep", ACC, size=FS - 2)
    return sh.svg("FRONT  ·  as it hangs  ·  mm")


def section():
    W, H, T = D["W"], D["H"], D["T"]
    pg, cl, tg = D["peg"], D["claw"], D["tongue"]
    k = 11.0
    sh = Sheet(1080, 960, k, (760, 860))
    # mirror so the wall is on the right: u -> -u
    M = lambda pts: [(-u, z) for u, z in pts]  # noqa: E731
    pts, s, e = peg_side(T, pg["d"], pg["angle"], pg["len"], pg["z"])
    sh.poly(M(pts), fill="#f2f2f0")
    # body section through a bay (x = 60): outline minus recess and bay
    bg, tu = tg["back_gap"], tg["back_gap"] + tg["t"]
    rec, fl, pu = D["recess"], D["floor"], D["pocket_u"]
    # cut face through a bay: recess behind the tongue, bay in front of and below it
    body = [(0, 0), (T, 0), (T, H), (0, H), (0, rec[1]), (bg, rec[1]), (bg, tg["bot"]),
            (tu, tg["bot"]), (tu, tg["top"]), (pu, tg["top"]), (pu, fl), (bg, fl),
            (bg, rec[0]), (0, rec[0])]
    sh.poly(M(body), fill="#dcdcda", sw=2.2)
    # hatch hint on the cut face
    sh.note(M([(T / 2, 8)])[0], "cut", "middle", MUTE, FS - 4)
    # CLAW: plate on the wall and its tab, hinge at hinge_z
    a = math.radians(cl["tab_ang"])
    plate = [(0, cl["plate_bottom_z"]), (cl["t"], cl["plate_bottom_z"]), (cl["t"], cl["hinge_z"]),
             (0, cl["hinge_z"])]
    plate2 = [(0, cl["hinge_z"] + cl["tab_h"] + 1), (cl["t"], cl["hinge_z"] + cl["tab_h"] + 1),
              (cl["t"], cl["plate_top_z"]), (0, cl["plate_top_z"])]
    h0 = cl["hinge_z"]
    tab = [(0, h0), (cl["t"], h0),
           (cl["t"] + cl["tab_h"] * math.sin(a), h0 + cl["tab_h"] * math.cos(a)),
           (cl["tab_h"] * math.sin(a), h0 + cl["tab_h"] * math.cos(a))]
    for q in (plate, plate2, tab):
        sh.poly(M(q), fill=STEEL, stroke="#3a3f47", sw=1.2)
    # wall
    sh.line((0.0, -4), (0.0, H + 6), INK, 2.6)
    for i in range(18):
        z = -4 + i * 4.3
        sh.line((0.0, z), (-3.0, z + 3.0), MUTE, 1)
    sh.note((2.2, H + 3), "WALL", "middle", MUTE, FS - 2)
    # dimensions
    sh.dim((0, 0), (-T, 0), -6, f"{T:.0f}", horiz=True)
    depth = e[0] + pg["d"] / 2 * math.sin(math.radians(pg["angle"]))
    sh.dim((0, -9), (-depth, -9), -4, f"{D['hook_dims'][1]:.1f} off the wall", horiz=True)
    sh.dim((-T, 0), (-T, pg["z"]), -4, f"{pg['z']:.0f}", horiz=False)
    sh.dim((0, 0), (0, H), 8, f"{H:.0f}", horiz=False)
    sh.text(M([(T + 13, pg["z"] + 8)])[0], f"{pg['angle']:.0f}°", color=ACC)
    sh.line(M([(T, pg["z"])])[0], M([(T + 22, pg["z"])])[0], ACC, 1, "5 4")
    sh.text(M([((s[0] + e[0]) / 2 - 6, (s[1] + e[1]) / 2 + 7)])[0], f"{pg['len']:.0f}", color=INK)
    # tongue call-outs
    sh.note((4, tg["bot"] - 1), f"tongue {tg['t']} thick, {tg['top'] - tg['bot']:.0f} tall", size=FS - 2)
    sh.note((4, tg["bot"] - 5), f"{tg['back_gap']} off the wall (plate {cl['t']})", size=FS - 2)
    sh.note((4, tg["bot"] - 9), "rests ~3.5 up the CLAW's V", size=FS - 2)
    sh.line((4, tg["bot"] - 0.4), (-tg["back_gap"] - tg["t"] / 2, tg["bot"] + 1), ACC, 1)
    sh.dim((0, cl["plate_top_z"]), (0, H), 22, f"{H - cl['plate_top_z']:.1f}", ACC, horiz=False)
    sh.dim((0, cl["plate_bottom_z"]), (0, cl["plate_top_z"]), 22, "CLAW 23", STEEL, horiz=False)
    sh.note((4, cl["plate_top_z"] + 5), "hook top sits", color=ACC, size=FS - 2)
    sh.note((4, cl["plate_top_z"] + 1.5), f"{H - cl['plate_top_z']:.1f} above the CLAW", color=ACC,
            size=FS - 2)
    sh.note((-T - 2, H - 4), f"bay {D['pocket_u']:.0f} deep", "end", size=FS - 2)
    sh.note((-T - 2, H - 8), f"front wall {T - D['pocket_u']:.0f}", "end", size=FS - 2)
    return sh.svg("SECTION through a CLAW  ·  wall on the right  ·  mm")


def back():
    W, H, R = D["W"], D["H"], D["R"]
    cl = D["claw"]
    k = 7.0
    sh = Sheet(1080, 800, k, (120, 650))
    # seen from the wall side: mirror x so it reads as you'd hold it facing you
    X = lambda x: W - x  # noqa: E731
    sh.poly([(X(x), z) for x, z in outline(W, H, R)])
    rx = D["recess_x"]
    rc = D["recess"]
    sh.poly([(X(rx[0]), rc[0]), (X(rx[1]), rc[0]), (X(rx[1]), rc[1]), (X(rx[0]), rc[1])],
            fill="#f1f1ef", sw=1.4)
    for i, (x0, x1) in enumerate(D["bays"]):
        sh.poly([(X(x0), D["floor"]), (X(x1), D["floor"]), (X(x1), D["tongue"]["bot"]),
                 (X(x0), D["tongue"]["bot"])], fill="#cfcfcd", sw=1.4)
        sh.note((X((x0 + x1) / 2), D["floor"] + 4), f"{i + 1}", "middle", INK, FS + 2)
    sh.line((X(rx[0]), D["tongue"]["bot"]), (X(rx[1]), D["tongue"]["bot"]), ACC, 2.2)
    sh.note((X(rx[0]) + 2, D["tongue"]["bot"] + 2), "tongue edge", "start", ACC, FS - 2)
    # CLAW positions for the 80 mm spacing (bays 1 and 5)
    for xc in (20.0, 100.0):
        b, t = cl["plate_bottom_z"], cl["plate_top_z"]
        sh.poly([(X(xc - 11.5), b), (X(xc + 11.5), b), (X(xc + 11.5), t), (X(xc - 11.5), t)],
                fill="none", stroke=STEEL, sw=1.8, dash="7 4")
        sh.line((X(xc), b - 3), (X(xc), t + 3), STEEL, 1, "3 3")
    sh.dim((X(20.0), H), (X(100.0), H), 9, "80  CLAW centres (bays 1 + 5)", STEEL)
    for (x0, x1) in D["bays"][:1]:
        sh.dim((X(x0), D["floor"]), (X(x1), D["floor"]), -8, f"bay {x1 - x0:.0f}")
    rib = D["ribs"][0]
    sh.dim((X(rib - 1.5), D["floor"]), (X(rib + 1.5), D["floor"]), -16, "rib 3")
    sh.dim((X(0), 0), (X(W), 0), -26, f"{W:.0f}")
    sh.note((X(0) + 3, -6), "Each CLAW's tab goes in any numbered bay (17 mm wide: ±5 mm slack).",
            size=FS - 1)
    sh.note((X(0) + 3, -11.5), "80 mm apart (bays 1 + 5) is steadiest; 40 mm (2 + 4) or one in bay 3 also work.",
            size=FS - 1)
    return sh.svg("BACK  ·  wall side  ·  CLAW bays  ·  mm")


if __name__ == "__main__":
    for name, fn in (("dwg_front", front), ("dwg_section", section), ("dwg_back", back)):
        with open(os.path.join(OUT, name + ".svg"), "w", encoding="utf-8") as f:
            f.write(fn())
        print("wrote", name)
