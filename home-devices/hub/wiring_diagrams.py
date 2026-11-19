"""Electrical assembly diagrams for the hub v5, drawn to scale as SVG (plain Python).

    python wiring_diagrams.py

Writes renders/wiring_schematic.svg, wiring_plan.svg, wiring_corner.svg, wiring_pins.svg.
Geometry numbers below mirror hub.py's v5 constants (asserted where they can be parsed), so the
plan and corner views are to scale. Pad order on the strip (5V / data / GND) varies by brand:
the rule that matters is that each pad stays on the same edge of the channel all the way round.
"""
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "renders")
SRC = open(os.path.join(HERE, "hub.py"), encoding="utf-8").read()

# ---------------------------------------------------------------- v5 geometry (mm)
W, D, R = 106.0, 80.0, 12.0
IN_IN, CH_IN0, FOOT_IN, FOOT_WALL = 2.2, 3.2, 15.5, 1.6
STRIP_W, PITCH = 12.0, 1000 / 144
N_LONG, N_SHORT = 10, 7
BOSS = (42.0, 33.2)
POCKET_D = 6.4
WIRE_HOLE = (46.5, 27.0, 4.0)
PADS = (-3.5, 0.0, 3.5)                    # across the strip: inner, middle, outer (from centre)
assert "N_LONG, N_SHORT = 10, 7" in SRC and "(46.5, 27.0, 4.0)" in SRC and "HEAD_POCKET_D = 6.4" in SRC
CH_MID = (CH_IN0 + FOOT_IN) / 2
XS, YL = W / 2 - CH_MID, D / 2 - CH_MID    # short runs at x = +-XS, long runs at y = +-YL
HS, HL = N_SHORT * PITCH / 2, N_LONG * PITCH / 2

INK, MUTED, LINE = "#18181a", "#6b6b70", "#c9c9c4"
RED, YEL, BLK, ACC = "#d1281f", "#e0a400", "#2b2b2e", "#b3261e"
WIRE = {"5V": RED, "DATA": YEL, "GND": BLK}
FONT = "IBM Plex Mono, JetBrains Mono, Consolas, monospace"


class Svg:
    def __init__(self, w, h, title):
        self.w, self.h, self.els = w, h, []
        self.text(24, 40, title, size=22, weight=600, anchor="start")

    def add(self, s):
        self.els.append(s)

    def text(self, x, y, s, size=16, color=INK, anchor="middle", weight=500, rot=0):
        t = f' transform="rotate({rot} {x:.1f} {y:.1f})"' if rot else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}" '
                 f'font-weight="{weight}" fill="{color}" text-anchor="{anchor}" '
                 f'dominant-baseline="middle"{t}>{s}</text>')

    def rect(self, x, y, w, h, fill="none", stroke=INK, sw=1.5, rx=0, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx:.1f}" '
                 f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def circle(self, x, y, r, fill="none", stroke=INK, sw=1.5, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{fill}" stroke="{stroke}" '
                 f'stroke-width="{sw}"{d}/>')

    def line(self, pts, color=INK, sw=1.5, dash=None, cap="round"):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        self.add(f'<polyline points="{p}" fill="none" stroke="{color}" stroke-width="{sw}" '
                 f'stroke-linecap="{cap}" stroke-linejoin="round"{d}/>')

    def arrow(self, x, y, ang, size=9, color=INK):
        a = math.radians(ang)
        p = [(x + size * math.cos(a), y + size * math.sin(a)),
             (x + size * 0.6 * math.cos(a + 2.5), y + size * 0.6 * math.sin(a + 2.5)),
             (x + size * 0.6 * math.cos(a - 2.5), y + size * 0.6 * math.sin(a - 2.5))]
        self.add('<polygon points="' + " ".join(f"{u:.1f},{v:.1f}" for u, v in p)
                 + f'" fill="{color}"/>')

    def save(self, name):
        body = "".join(self.els)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" '
               f'width="{self.w}" height="{self.h}"><rect width="100%" height="100%" fill="#ffffff"/>'
               f'{body}</svg>')
        open(os.path.join(OUT, name), "w", encoding="utf-8").write(svg)


def rrect_path(cx, cy, w, h, r):
    x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    return (f"M{x0 + r:.1f},{y0:.1f} H{x1 - r:.1f} A{r:.1f},{r:.1f} 0 0 1 {x1:.1f},{y0 + r:.1f} "
            f"V{y1 - r:.1f} A{r:.1f},{r:.1f} 0 0 1 {x1 - r:.1f},{y1:.1f} H{x0 + r:.1f} "
            f"A{r:.1f},{r:.1f} 0 0 1 {x0:.1f},{y1 - r:.1f} V{y0 + r:.1f} "
            f"A{r:.1f},{r:.1f} 0 0 1 {x0 + r:.1f},{y0:.1f} Z")


# ---------------------------------------------------------------- strip runs (world mm)
def runs():
    """Chain order. Each: (name, n, start(x,y), end(x,y), outer normal (nx, ny))."""
    return [("RUN 1", N_SHORT, (XS, HS), (XS, -HS), (1, 0)),
            ("RUN 2", N_LONG, (HL, -YL), (-HL, -YL), (0, -1)),
            ("RUN 3", N_SHORT, (-XS, -HS), (-XS, HS), (-1, 0)),
            ("RUN 4", N_LONG, (-HL, YL), (HL, YL), (0, 1))]


def pads(run, at_start):
    """Pad centres (inner, middle, outer) 1.0 mm in from the cut at a run's start or end."""
    _, n, s, e, (nx, ny) = run
    L = math.dist(s, e)
    ux, uy = (e[0] - s[0]) / L, (e[1] - s[1]) / L
    bx, by = (s[0] + ux * 1.0, s[1] + uy * 1.0) if at_start else (e[0] - ux * 1.0, e[1] - uy * 1.0)
    return [(bx + nx * o, by + ny * o) for o in PADS]


def corner_route(sx, sy):
    """Jumper polylines for the corner at (sx, sy), from the short run's pads to the long run's
    pads (template drawn for +X -Y and mirrored). Returns {signal: [(x, y), ...]}."""
    t = {"GND": [(40.15, -23.3), (40.15, -25.3), (35.4, -25.3), (35.4, -27.15), (33.72, -27.15)],
         "DATA": [(43.65, -23.3), (43.65, -26.3), (36.4, -26.3), (36.4, -30.65), (33.72, -30.65)],
         "5V": [(47.15, -23.3), (47.15, -27.6), (37.4, -27.6), (37.4, -34.15), (33.72, -34.15)]}
    return {k: [(sx * x, -sy * y) for x, y in v] for k, v in t.items()}


# ---------------------------------------------------------------- plan view (from below)
def plan():
    k = 7.2
    S = Svg(1000, 830, "LED STRIP WIRING · plinth upside down on the bench, channel facing you")
    cx, cy = 500, 420

    def P(x, y):                   # bottom view: x as is, world +y down the page
        return cx + x * k, cy + y * k

    def path_rr(inset, r, fill, stroke, sw=1.5):
        w, h = (W - 2 * inset) * k, (D - 2 * inset) * k
        S.add(f'<path d="{rrect_path(cx, cy, w, h, max(r, 0.4) * k)}" fill="{fill}" stroke="{stroke}" '
              f'stroke-width="{sw}"/>')

    path_rr(IN_IN, R - IN_IN, "#2b2b2e", INK)                       # lining (black)
    path_rr(CH_IN0, R - CH_IN0, "#ecebe7", LINE)                     # channel floor (the plate)
    path_rr(FOOT_IN, 4.0, "#2b2b2e", INK)                            # foot ring
    path_rr(FOOT_IN + FOOT_WALL, 3.0, "#f6f6f3", LINE)               # inside the foot
    for x in (-21, -7, 7, 21):
        S.rect(*P(x - 1.5, -20), 3 * k, 40 * k, fill="#e2e2de", stroke=LINE, rx=1.5 * k)
    for sx in (-1, 1):
        for sy in (-1, 1):
            S.circle(*P(sx * 30, sy * 17), 5 * k, fill="#3a3a3d", stroke=INK)
    # strip runs
    for name, n, s, e, (nx, ny) in runs():
        L = math.dist(s, e)
        ux, uy = (e[0] - s[0]) / L, (e[1] - s[1]) / L
        corners = [(s[0] + nx * 6, s[1] + ny * 6), (e[0] + nx * 6, e[1] + ny * 6),
                   (e[0] - nx * 6, e[1] - ny * 6), (s[0] - nx * 6, s[1] - ny * 6)]
        S.add('<polygon points="' + " ".join(f"{u:.1f},{v:.1f}" for u, v in (P(*c) for c in corners))
              + f'" fill="#ffffff" stroke="{INK}" stroke-width="1.5"/>')
        for i in range(n):
            t = (i + 0.5) * PITCH
            x, y = s[0] + ux * t, s[1] + uy * t
            X, Y = P(x, y)
            S.rect(X - 2.5 * k, Y - 2.5 * k, 5 * k, 5 * k, fill="#fbf7e8", stroke="#8c8a80", sw=1, rx=2)
            if i % 2 == 1 and i < n - 1:
                X2, Y2 = P(x + ux * PITCH / 2, y + uy * PITCH / 2)
                S.arrow(X2, Y2, math.degrees(math.atan2(uy, ux)), size=8, color=ACC)
        mx, my = P((s[0] + e[0]) / 2 + nx * 9.4, (s[1] + e[1]) / 2 + ny * 9.4)
        rot = 90 if abs(ux) < 0.5 else 0
        S.text(mx, my, f"{name} · {n} LEDs", size=15, color=INK, weight=600, rot=rot)
    # screw pockets: keep clear for the screwdriver
    for sx in (-1, 1):
        for sy in (-1, 1):
            X, Y = P(sx * BOSS[0], sy * BOSS[1])
            S.circle(X, Y, POCKET_D / 2 * k, fill="#fde9e7", stroke=ACC, sw=1.5, dash="5 4")
    # corner jumpers
    for sx, sy in ((1, -1), (-1, -1), (-1, 1)):
        for sig, pts in corner_route(sx, sy).items():
            S.line([P(*q) for q in pts], color=WIRE[sig], sw=3.2)
    # input wires at the chain's start, into the wire hole
    wx, wy, wd = WIRE_HOLE
    X, Y = P(wx, wy)
    S.circle(X, Y, wd / 2 * k, fill="#ffffff", stroke=INK, sw=2)
    for (px, py), sig in zip(pads(runs()[0], True), ("GND", "DATA", "5V")):
        S.line([P(px, py), P(px, py + 2.2), P(wx + (px - 43.65) * 0.25, wy)], color=WIRE[sig], sw=3.2)
    # labels round the outside
    S.text(cx, P(0, -D / 2)[1] - 26, "FRONT (−Y)", size=14, color=MUTED)
    S.text(cx, P(0, D / 2)[1] + 26, "USB-C SIDE (+Y)", size=14, color=MUTED)
    S.text(P(-W / 2, 0)[0] - 30, cy, "I/O BAY END (−X)", size=14, color=MUTED, rot=-90)
    S.text(P(W / 2, 0)[0] + 30, cy, "ESP32 END (+X)", size=14, color=MUTED, rot=90)
    X, Y = P(wx, wy)
    S.line([(X + 16, Y + 14), (X + 40, Y + 84)], color=MUTED, sw=1)
    S.text(X + 44, Y + 96, "wire hole Ø4 → ESP32", size=14, anchor="end")
    X, Y = P(BOSS[0], -BOSS[1])
    S.line([(X + 18, Y - 18), (X + 40, Y - 62)], color=MUTED, sw=1)
    S.text(X + 44, Y - 72, "keep clear: screwdriver", size=14, anchor="end", color=ACC)
    X, Y = P(*pads(runs()[0], True)[1])
    S.text(X - 70, Y + 34, "START · DIN", size=14, color=ACC, weight=600)
    # legend
    lx, ly = 30, 760
    for i, (sig, col) in enumerate(WIRE.items()):
        S.line([(lx + i * 170, ly), (lx + i * 170 + 40, ly)], color=col, sw=4)
        S.text(lx + i * 170 + 50, ly, sig, size=15, anchor="start")
    S.arrow(lx + 520, ly, 0, size=10, color=ACC)
    S.text(lx + 536, ly, "data direction (= the strip's arrows)", size=15, anchor="start")
    S.text(30, 790, "To scale. Each pad stays on the same edge all the way round, so wires never cross.",
           size=13, color=MUTED, anchor="start")
    S.text(30, 808, "Colours are examples: go by your strip's printed 5V / DIN / GND labels.",
           size=13, color=MUTED, anchor="start")
    S.save("wiring_plan.svg")


# ---------------------------------------------------------------- one corner, enlarged
def corner():
    k = 28.0
    S = Svg(1000, 900, "CORNER JUMPERS · enlarged (front-right corner, from below)")
    ox, oy = 31.0, -38.5                # world point at the top-left of the drawing area

    def P(x, y):
        return 60 + (x - ox) * k, 90 + (y - oy) * k

    # channel edges near the corner
    S.rect(*P(ox, -36.8), (50.0 - ox) * k, (36.8 - 23.0) * k, fill="#ecebe7", stroke="none")
    S.line([P(ox, -36.8), P(41.0, -36.8)], color=INK, sw=2)          # lining inner face (long side)
    S.line([P(49.8, -28.0), P(49.8, -23.0)], color=INK, sw=2)        # lining inner face (short side)
    S.add(f'<path d="M{P(41.0, -36.8)[0]:.1f},{P(41.0, -36.8)[1]:.1f} A{8.8 * k:.1f},{8.8 * k:.1f} 0 0 1 '
          f'{P(49.8, -28.0)[0]:.1f},{P(49.8, -28.0)[1]:.1f}" fill="none" stroke="{INK}" stroke-width="2"/>')
    # run ends
    S.rect(*P(37.65, -24.3), 12 * k, 1.3 * k, fill="#ffffff", stroke=INK)       # run 1 end
    S.rect(*P(ox, -36.65), (34.72 - ox) * k, 12 * k, fill="#ffffff", stroke=INK)  # run 2 start
    for i in range(1):
        S.rect(*P(43.65 - 2.5, -23.0 - 1.0), 5 * k, 0.6 * k, fill="#fbf7e8", stroke="#8c8a80", sw=1)
    X, Y = P(43.65, -24.3)
    S.text(X, Y - 20, "RUN 1 (end)", size=16, weight=600)
    X, Y = P(32.5, -30.65)
    S.text(X, Y, "RUN 2 (start)", size=16, weight=600, rot=-90)
    # pads
    for (px, py), sig in zip(pads(runs()[0], False), ("GND", "DATA", "5V")):
        X, Y = P(px, py)
        S.rect(X - 1.0 * k, Y - 0.7 * k, 2.0 * k, 1.4 * k, fill=WIRE[sig], stroke=INK, sw=1, rx=3)
    for (px, py), sig in zip(pads(runs()[1], True), ("GND", "DATA", "5V")):
        X, Y = P(px, py)
        S.rect(X - 0.7 * k, Y - 1.0 * k, 1.4 * k, 2.0 * k, fill=WIRE[sig], stroke=INK, sw=1, rx=3)
    # screw pocket keep-out
    X, Y = P(BOSS[0], -BOSS[1])
    S.circle(X, Y, POCKET_D / 2 * k, fill="#fde9e7", stroke=ACC, sw=2, dash="8 6")
    S.text(X + 14, Y + 10, "screw pocket Ø6.4", size=15, color=ACC, anchor="start")
    S.text(X + 14, Y + 32, "keep wires out", size=15, color=ACC, anchor="start")
    # wiring bay
    bx0, bx1 = 34.72, BOSS[0] - POCKET_D / 2
    X0, Y0 = P(bx0, -36.8)
    X1, _ = P(bx1, -36.8)
    S.line([(X0, Y0 + 26), (X1, Y0 + 26)], color=MUTED, sw=1)
    S.text((X0 + X1) / 2, Y0 + 44, f"bay {bx1 - bx0:.1f} mm", size=15, color=MUTED)
    # jumpers
    for sig, pts in corner_route(1, -1).items():
        S.line([P(*q) for q in pts], color=WIRE[sig], sw=7)
        S.line([P(*q) for q in pts], color="#ffffff", sw=1.2, dash="1 9")
    # notes
    notes = ["1  Tin the six pads first, then tin each wire end.",
             "2  28 AWG silicone (~1.0 mm), about 25 mm each (5V longest, GND shortest).",
             "3  Route as drawn: the wires never cross and stay out of the screw circle.",
             "4  Solder on the LED side; the wires sit in the 3.5 mm under the strip.",
             "5  Check each joint for continuity, and 5V to GND for no short.",
             "6  After fitting: a dab of hot glue holds the wires flat in the bay."]
    for i, n in enumerate(notes):
        S.text(60, 712 + i * 30, n, size=15, anchor="start")
    S.text(60, 682, "HOW", size=13, color=MUTED, anchor="start", weight=600)
    S.save("wiring_corner.svg")


# ---------------------------------------------------------------- schematic
def schematic():
    S = Svg(1200, 690, "WIRING SCHEMATIC · hub v5")

    def block(x, y, w, h, title, pins, side="right"):
        S.rect(x, y, w, h, fill="#f6f6f3", stroke=INK, sw=2, rx=8)
        S.text(x + w / 2, y + 24, title, size=16, weight=600)
        out = {}
        for i, p in enumerate(pins):
            py = y + 60 + i * 34
            px = x + w if side == "right" else x
            S.circle(px, py, 4, fill=INK, stroke=INK)
            S.text(px - 10 if side == "right" else px + 10, py, p, size=14,
                   anchor="end" if side == "right" else "start")
            out[p] = (px, py)
        return out

    pi = block(40, 90, 220, 140, "Pi 5 header", ["pin 4 · 5V", "pin 6 · GND"])
    esp = block(420, 70, 230, 170, "ESP32-C3", ["5V", "GND", "GPIO4"], side="left")
    ls = block(420, 330, 230, 230, "74AHCT1G125", ["5 · VCC", "3 · GND", "1 · /OE", "2 · A", "4 · Y"],
               side="left")
    cap = (820, 150)
    S.text(cap[0], cap[1] - 40, "470 µF", size=15, weight=600)
    S.line([(cap[0] - 18, cap[1] - 6), (cap[0] + 18, cap[1] - 6)], sw=3)
    S.add(f'<path d="M{cap[0] - 18},{cap[1] + 10} Q{cap[0]},{cap[1] + 2} {cap[0] + 18},{cap[1] + 10}" '
          f'fill="none" stroke="{INK}" stroke-width="3"/>')
    S.text(cap[0] + 26, cap[1] - 10, "+", size=16, anchor="start")
    # strip
    sx0, sy0 = 960, 120
    S.rect(sx0, sy0, 200, 260, fill="#f6f6f3", stroke=INK, sw=2, rx=8)
    S.text(sx0 + 100, sy0 + 24, "LED strip", size=16, weight=600)
    for i, p in enumerate(("5V", "DIN", "GND")):
        S.circle(sx0, sy0 + 70 + i * 50, 4, fill=INK)
        S.text(sx0 + 12, sy0 + 70 + i * 50, p, size=14, anchor="start")
    S.text(sx0 + 100, sy0 + 230, "RUN 1→2→3→4", size=13, color=MUTED)
    v5, gnd = RED, BLK
    S.line([pi["pin 4 · 5V"], (330, pi["pin 4 · 5V"][1]), (330, 50), (760, 50), (760, sy0 + 70),
            (sx0, sy0 + 70)], color=v5, sw=3)
    S.line([(330, pi["pin 4 · 5V"][1]), (330, esp["5V"][1]), esp["5V"]], color=v5, sw=3)
    S.line([(360, 50), (360, ls["5 · VCC"][1]), ls["5 · VCC"]], color=v5, sw=3)
    S.line([(cap[0], 50), (cap[0], cap[1] - 6)], color=v5, sw=3)
    S.line([pi["pin 6 · GND"], (300, pi["pin 6 · GND"][1]), (300, 600), (790, 600), (790, sy0 + 170),
            (sx0, sy0 + 170)], color=gnd, sw=3)
    S.line([(300, esp["GND"][1]), esp["GND"]], color=gnd, sw=3)
    S.line([(300, ls["3 · GND"][1]), ls["3 · GND"]], color=gnd, sw=3)
    S.line([(300, ls["1 · /OE"][1]), ls["1 · /OE"]], color=gnd, sw=3)
    S.line([(cap[0], cap[1] + 6), (cap[0], 600)], color=gnd, sw=3)
    S.line([esp["GPIO4"], (390, esp["GPIO4"][1]), (390, ls["2 · A"][1]), ls["2 · A"]], color=YEL, sw=3)
    yy = ls["4 · Y"][1]
    S.line([ls["4 · Y"], (380, yy), (380, 590), (700, 590), (700, sy0 + 120), (850, sy0 + 120)], color=YEL, sw=3)
    S.rect(850, sy0 + 108, 50, 24, fill="#ffffff", stroke=INK, sw=2)
    S.text(875, sy0 + 145, "330 Ω", size=13)
    S.line([(900, sy0 + 120), (sx0, sy0 + 120)], color=YEL, sw=3)
    for jx, jy in ((330, pi["pin 4 · 5V"][1]), (360, 50), (cap[0], 50), (300, esp["GND"][1]),
                   (300, ls["3 · GND"][1]), (300, ls["1 · /OE"][1]), (cap[0], 600)):
        S.circle(jx, jy, 5, fill=INK, stroke=INK)
    S.text(40, 650, "0.1 µF from pin 5 to pin 3, right at the level shifter.", size=13, color=MUTED,
           anchor="start")
    S.text(40, 280, "1 × 2 female header", size=13, color=MUTED, anchor="start")
    S.text(40, 300, "on pins 4 and 6", size=13, color=MUTED, anchor="start")
    S.text(40, 672, "Cap the LEDs in ESPHome (~0.5 A). Never plug USB into the ESP32 while the Pi is on.",
           size=13, color=MUTED, anchor="start")
    S.save("wiring_schematic.svg")


# ---------------------------------------------------------------- pin maps
def pins():
    S = Svg(1200, 560, "PIN MAPS · the only pins you touch")
    # Pi header: 2 x 20, pin 1 at left, odd row on the inside (board), even row at the edge
    x0, y0, p = 60, 120, 24
    S.text(x0, y0 - 40, "Pi 5 GPIO header (looking down, board edge at the top)", size=15,
           anchor="start", weight=600)
    for c in range(20):
        for r, row in ((0, "even"), (1, "odd")):
            n = 2 * c + (2 if r == 0 else 1)
            X, Y = x0 + c * p, y0 + r * p
            hot = n in (4, 6)
            S.rect(X, Y, p - 4, p - 4, fill=(RED if n == 4 else BLK) if hot else "#f0efea",
                   stroke=INK, sw=1, rx=3)
            if n in (1, 2, 4, 6):
                S.text(X + (p - 4) / 2, Y + (p - 4) / 2, str(n), size=11,
                       color="#ffffff" if hot else INK)
    S.text(x0, y0 + 2 * p + 20, "pin 1 is the square pad, at the ESP32 (+X) end", size=13,
           color=MUTED, anchor="start")
    S.text(x0 + 3 * p, y0 - 14, "4 · 5V", size=13, color=RED, anchor="start")
    S.text(x0 + 3 * p + 70, y0 - 14, "6 · GND", size=13, color=BLK, anchor="start")
    # ESP32-C3 SuperMini
    ex, ey = 640, 90
    S.text(ex, ey - 10, "ESP32-C3 SuperMini (USB-C at the top, chip side up)", size=15,
           anchor="start", weight=600)
    S.rect(ex + 120, ey + 20, 140, 260, fill="#2b2b2e", stroke=INK, rx=8)
    S.rect(ex + 160, ey + 6, 60, 26, fill="#c9c9c4", stroke=INK, rx=4)
    left = ["5V", "GND", "3V3", "GPIO4", "GPIO3", "GPIO2", "GPIO1", "GPIO0"]
    right = ["GPIO5", "GPIO6", "GPIO7", "GPIO8", "GPIO9", "GPIO10", "GPIO20", "GPIO21"]
    for i, (a, b) in enumerate(zip(left, right)):
        y = ey + 50 + i * 30
        hot = {"5V": RED, "GND": BLK, "GPIO4": YEL}.get(a)
        S.circle(ex + 134, y, 7, fill=hot or "#c9c9c4", stroke="#ffffff" if hot else INK,
                 sw=2 if hot else 1)
        S.circle(ex + 246, y, 7, fill="#c9c9c4", stroke=INK, sw=1)
        S.text(ex + 116, y, a, size=13, anchor="end", color=INK if hot else MUTED,
               weight=600 if hot else 500)
        S.text(ex + 264, y, b, size=13, anchor="start", color=MUTED)
    S.text(ex, ey + 320, "Pin labels vary between batches: go by your board's printed labels.",
           size=13, color=MUTED, anchor="start")
    # 74AHCT1G125
    lx, ly = 60, 330
    S.text(lx, ly, "74AHCT1G125 (SOT-23-5, top view, dot = pin 1)", size=15, anchor="start", weight=600)
    S.rect(lx + 150, ly + 40, 120, 90, fill="#2b2b2e", stroke=INK, rx=6)
    S.circle(lx + 166, ly + 56, 4, fill="#ffffff", stroke="#ffffff")
    for i, (n, lab, col) in enumerate(((1, "/OE → GND", BLK), (2, "A ← GPIO4", YEL), (3, "GND", BLK))):
        y = ly + 52 + i * 32
        S.rect(lx + 130, y - 6, 20, 12, fill="#c9c9c4", stroke=INK, sw=1)
        S.text(lx + 122, y, f"{n} · {lab}", size=13, anchor="end", color=INK)
    for i, (n, lab) in enumerate(((5, "VCC ← 5V"), (4, "Y → 330 Ω → DIN"))):
        y = ly + 60 + i * 48
        S.rect(lx + 270, y - 6, 20, 12, fill="#c9c9c4", stroke=INK, sw=1)
        S.text(lx + 298, y, f"{n} · {lab}", size=13, anchor="start", color=INK)
    S.text(lx, ly + 170, "Solder it to a SOT-23 adapter first; 0.1 µF across pins 5 and 3.",
           size=13, color=MUTED, anchor="start")
    S.save("wiring_pins.svg")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    plan()
    corner()
    schematic()
    pins()
    print("wrote wiring_plan.svg, wiring_corner.svg, wiring_schematic.svg, wiring_pins.svg")
