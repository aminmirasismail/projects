"""Brush drying stand, Folio v2 (concept B taken into detail design).

Run with Blender's Python:
  blender -b --python folio.py -- [--stills] [--closeups] [--anim] [--checkframes]
                                  [--carts] [--stats] [--preview] [--gpu]

What changed from the concept:
  * 11 brushes in two rows, positions sized from Chelsea's measured brushes
    (front row: the five big heads, back row: six slimmer ones).
  * Clips are drop-in black cartridges in three sizes (S 6.9-10, M 10.8-13, L 16.5-19.5 mm)
    with long straight spring fingers, so each clip grips a range of handle sizes.
  * 52 mm loading gap between the back row and the panel, so heads pass without touching.
  * Shelf hinges over the top of the panel and rests on it: brush weight presses it onto
    a hard stop instead of trying to fold it.
  * Two black prop stays lock the panel upright (no springs, no latch to wear out).
  * Pour lip on the front edge, right of centre; the tray floor falls ~2 mm towards it.
"""
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import studio as S  # noqa: E402
import concepts as C  # noqa: E402  (shared helpers: prism, lathe, rrect_pts, ...)

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
PREVIEW = "--preview" in ARGS
OUT = os.path.join(HERE, "renders", "v2")
os.makedirs(OUT, exist_ok=True)
prism, rrect_pts, circle_pts, lathe = C.prism, C.rrect_pts, C.circle_pts, C.lathe

# ================================================================== the brushes
# name: (grip dia, head dia(s), overall length, kind)  head dia = widest point, measured dry
BRUSHES = {
    "B1": (8.1, (8.1,), 165, "liner"),
    "B2": (11.9, (11.9,), 170, "liner"),
    "B3": (10.0, (21.9,), 172, "single"),
    "B4": (9.5, (23.75,), 170, "single"),
    "B5": (8.3, (30.5,), 175, "single"),
    "B6": (8.9, (34.2,), 178, "single"),
    "B7": (10.0, (28.0,), 172, "single"),
    "B8": (6.95, (38.0,), 180, "single"),
    "B9": (19.0, (46.8, 39.3), 176, "double"),
    "B10": (12.3, (37.0, 37.0), 166, "double"),
    "B11": (16.8, (55.0, 55.0), 180, "double"),
}
# clip sizes: grip range (mm), finger thickness
SIZES = {"S": (6.9, 10.0, 1.0), "M": (10.8, 13.0, 1.1), "L": (16.5, 19.5, 1.2)}


def size_of(d):
    return next(k for k, (lo, hi, _t) in SIZES.items() if lo <= d <= hi)


# x positions from a packing search (pack10.py): every pair of heads keeps >= 3 mm apart
FRONT = [("B11", -64.4), ("B4", -22.0), ("B10", 11.3), ("B1", 38.0), ("B9", 68.5)]
BACK = [("B8", -72.5), ("B2", -44.5), ("B5", -17.8), ("B3", 11.4), ("B7", 39.3), ("B6", 73.5)]

# ================================================================== main dimensions
W = 176.0                 # tray and shelf width (A1 Mini bed is 180)
YF, YB = -86.0, 72.0      # tray front and back edges
BH = 22.5                 # tray rim height: deep enough that the folded panel, rail and stays sit inside it
PF, PT = 58.0, 8.0        # panel front face, panel thickness
PX = 80.0                 # panel half width (stays run just outside it)
HZ = 19.0                 # panel hinge axis height (folded front face lands at z 15, clear of the rim)
HY = PF + PT / 2          # panel hinge axis y
H = 152.0                 # shelf top (stowed shelf then clears the tray rim)
T = 10.0                  # shelf thickness
RAIL = (H - 22.0, H - 10.0)  # panel top rail, the shelf's hard stop
GAP = 52.0                # loading gap, shelf back edge to panel
SD = 72.0                 # shelf depth
SB = PF - GAP             # shelf back edge  (8)
SF = SB - SD              # shelf front edge (-60)
WALL = 1.6                # shelf wall in front of each cartridge
AX = (YB, H)              # shelf hinge axis (y, z): top-back corner of the shelf cheeks
STAY_P = (14.0, 9.0)      # stay pivot on the tray (y, z)
STAY_Q = (PF + PT / 2, 85.0)  # steel peg in the panel side: high, so the panel above it is a short cantilever
STAY_X = (PX + 0.6, PX + 4.6)
SPOUT_X = 50.0
WIN_W = 80.0              # carry window width in the panel
DOWN = 16.0               # depth of the shelf's under-ribs below the plate
RIB_Y = ((SF + SB) / 2 - 3.0, (SF + SB) / 2 + 3.0)   # cross rib in the web between the two rows of pockets
RAIL_W = 3.5              # side rails under the shelf ends (outside the pocket openings)
PRIB_X = (44.5, 59.5, 74.5)  # panel back ribs (x centres, both signs), 5 wide x 5 deep
SILL = (-76.0, 32.0)      # ballast pocket x range (clear of the stowed left stay) in the front sill (stops short of the spout)
FEET = [(-1, -78), (1, -78), (-1, 62), (1, 62)]   # silicone bumpers (x sign, y)


# ================================================================== helpers
def hull(pts):
    pts = sorted(set(pts))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def yz_prism(name, yz, x0, x1, bevel=0.0):
    """Polygon drawn in the (y, z) plane, extruded along x."""
    ob = prism(name, [(-z, y) for y, z in yz], x0, x1, bevel)
    ob.rotation_euler.y = math.pi / 2
    S.bake(ob)
    return ob


def xz_prism(name, xz, y0, y1, bevel=0.0):
    """Polygon drawn in the (x, z) plane, extruded along y."""
    ob = prism(name, xz, -y1, -y0, bevel)
    ob.rotation_euler.x = math.pi / 2
    S.bake(ob)
    return ob


def xcyl(name, r, x0, x1, y, z, seg=48):
    ob = S.cylinder(name, 2 * r, x1 - x0, loc=((x0 + x1) / 2, y, z), rot=(0, math.pi / 2, 0), seg=seg)
    S.bake(ob)
    return ob


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def stadium_seg(p, q, r, n=16):
    """2D stadium between points p and q."""
    a = math.atan2(q[1] - p[1], q[0] - p[0])
    pts = []
    for c, a0 in ((q, a - math.pi / 2), (p, a + math.pi / 2)):
        for i in range(n + 1):
            t = a0 + math.pi * i / n
            pts.append((c[0] + r * math.cos(t), c[1] + r * math.sin(t)))
    return pts


def steel():
    m = S.material("Steel", (0.62, 0.63, 0.65, 1), rough=0.3)
    m.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 1.0
    return m


def silicone():
    return S.material("Silicone", (0.30, 0.30, 0.31, 1), rough=0.6)


# ================================================================== clip cartridge
# Wet weights (g). GRIP_G sizes the clip fingers (hold 2x at friction 0.25); double-ended brushes are
# also held positively by their waist, so their grip weight is capped. LOAD_G are upper-bound design
# weights for the structure (published brushes: eye 8-15 g, face/kabuki 30-50 g dry, plus water).
GRIP_G = {"B1": 10, "B2": 12, "B3": 15, "B4": 15, "B5": 30, "B6": 35, "B7": 30, "B8": 35,
          "B9": 42, "B10": 42, "B11": 42}
LOAD_G = {"B1": 12, "B2": 15, "B3": 20, "B4": 20, "B5": 40, "B6": 45, "B7": 40, "B8": 45,
          "B9": 65, "B10": 60, "B11": 75}
WET_G = GRIP_G


def wet_g(name):
    return GRIP_G[name]


MU_R = 0.3                            # neoprene pad on a wet, soapy lacquered handle (design value)
HOLD_SF = 2.0                         # grip holds 2x the brush's upper-bound wet weight
PAD = (4.0, 7.0, 1.59)                # rubber pad: length along y, height, thickness (1/16 in neoprene sheet)
PAD_FIT = 0.25                        # pad pocket clearance per side (takes jig-cut pads 4.0-4.5 x 7.0-7.5)
PAD_PROUD = 0.3                       # rubber stands this far proud of the PLA rim
CREST = 0.15                          # PLA crest ahead of the pad, inboard of the rubber: a light click
GLUE = 0.15                           # extra pocket depth for the E6000 film
EXIT_DEG = 30.0                       # crest back face, so pulling a brush out is easy
RAMP_DEG = 32.0                       # lead-in ramp angle
FRONT_GAP = 1.03                      # pocket extends this far ahead of the cartridge: room to slide under the lip
LIP = (1.0, 1.2)                      # pocket back lip: overhang, thickness (the cartridge's back hook tucks under)


def cart_geom(d, w=18.0):
    """Numbers for the cartridge made for one handle diameter d (it accepts d +/- 0.6 mm) and a brush of
    wet weight w grams. Two spring fingers end in pad blocks; each pad block holds a glued 4 x 7 mm
    neoprene pad in a walled pocket, with a PLA ramp and crest ahead of it. The handle is gripped
    between the two rubber pads. Local frame: entry face at y=0, body towards +y."""
    lo, hi = d - 0.6, d + 0.6
    r_n, rhi = d / 2, hi / 2
    pre = 1.6                                   # finger deflection with the nominal handle seated
    x_c = r_n - pre                             # free rubber face
    x_fi = x_c + PAD[2] + GLUE + 0.8            # finger inner face (behind the pocket floor)
    dx_ramp = (x_fi + 0.3) - (x_c - CREST)
    y_cr = 0.4 + dx_ramp / math.tan(math.radians(RAMP_DEG))     # crest line
    run = (PAD_PROUD + CREST) / math.tan(math.radians(EXIT_DEG))
    y_p = y_cr + 0.3 + run + PAD[0] / 2 + PAD_FIT   # pad centre line
    y_wall = y_p + rhi + 0.3                    # flat back stop
    d_hi = pre + 0.3 + CREST                    # worst deflection: biggest handle passing the crest
    d_lo = pre - 0.3
    yr = 30.0                                   # finger root
    E, h = 3500.0, T - 1.0
    L = yr
    W_N = w * 9.81e-3
    F = max(0.4, HOLD_SF * W_N / (2 * MU_R))
    k = F / pre
    t = round(min(2.0, max(1.0, (k * 12 * L ** 3 / (3 * E * h)) ** (1 / 3))), 2)
    I = h * t ** 3 / 12
    k = 3 * E * I / L ** 3
    x_so = x_fi + t + d_hi + 0.7
    Wc = 2 * (x_so + 1.6)
    Dc = yr + 2.5
    return dict(size=f"{d:.2f}".rstrip("0").rstrip("."), d=d, lo=lo, hi=hi, t=t, pre=pre, x_c=x_c, x_fi=x_fi,
                y_cr=y_cr, y_p=y_p, yp=y_p, y_wall=y_wall, yr=yr, x_so=x_so, W=Wc, D=Dc, k=k, L=L, h=h,
                defl_lo=d_lo, defl_hi=d_hi, strain_nom=3 * t * pre / (2 * L * L), strain_max=3 * t * d_hi / (2 * L * L),
                f_nom=k * pre, f_lo=k * d_lo, f_hi=k * d_hi, entry=2 * (x_c - CREST), w=w,
                hold_sf=(2 * MU_R * k * pre) / W_N, hold_sf_lo=(2 * MU_R * k * d_lo) / W_N,
                push=2 * k * d_hi * math.tan(math.radians(RAMP_DEG + 14)),
                pullout=2 * k * d_hi * math.tan(math.radians(EXIT_DEG + 14)))


Z0C = H - T + 1.0                     # cartridges sit on a 1 mm ledge at the pocket bottom
FIT = 0.10                            # pocket clearance per side (the fit block tests 0.05 / 0.10 / 0.15)


def cartridge(name, g, z0=Z0C, z1=H):
    """Black drop-in clip. Back hook (a step on the top of the back bar) tucks under a lip at the back
    of the pocket; 0.6 mm snap bumps on the free front ends of the frame arms click into grooves.
    Crush ribs on the back face take out the play. Spring fingers end in pad blocks with walled
    pockets for glued neoprene pads."""
    Wd, Dd = g["W"], g["D"]
    body = prism(name, rrect_pts(Wd, Dd, 2.0, c=(0, Dd / 2)), z0, z1, bevel=0.4)
    xf, t, yr, yw, xc = g["x_fi"], g["t"], g["yr"], g["y_wall"], g["x_c"]
    xs = g["x_so"]
    adds = []
    for s in (1, -1):   # snap bumps near the arms' free ends: 30 deg lead-in below, 45 deg retaining face
        xw = s * Wd / 2
        prof = [(xw - s * 0.3, z0 + 2.0), (xw, z0 + 2.0), (xw + s * 0.6, z0 + 3.04), (xw + s * 0.6, z0 + 3.4),
                (xw, z0 + 4.0), (xw - s * 0.3, z0 + 4.0)]
        adds.append(xz_prism(name + f"_bp{s}", prof, 2.0, 8.0))
    for x in (-Wd / 4, 0.0, Wd / 4):   # crush ribs on the back face, below the hook step
        adds.append(prism(name + f"_cb{x:.0f}", circle_pts(0.35, 16, c=(x, Dd - 0.1)), z0 + 0.6, z1 - LIP[1] - 0.6))
    S.union(body, adds)
    cut = [prism(name + "_seat", rect(-xf, -3, xf, yw), z0 - 1, z1 + 1)]
    for s in (1, -1):
        cut.append(prism(name + f"_in{s}",
                         rect(min(s * (xf - 0.5), s * xf), yw - 0.1, max(s * (xf - 0.5), s * xf), yr), z0 - 1, z1 + 1))
        cut.append(prism(name + f"_out{s}", rect(min(s * (xf + t), s * xs), -3, max(s * (xf + t), s * xs), yr),
                         z0 - 1, z1 + 1))
    # back hook: the top of the back bar steps down so the pocket's lip sits over it
    cut.append(prism(name + "_hook", rect(-Wd, Dd - LIP[0] - 0.15, Wd, Dd + 1), z1 - LIP[1] - 0.15, z1 + 1))
    S.cut(body, cut)
    pads = []
    yc, yp = g["y_cr"], g["y_p"]
    rim = xc + PAD_PROUD
    yb = yp + PAD[0] / 2 + PAD_FIT + 1.2          # back wall of the pad pocket
    run = (rim - (xc - CREST)) / math.tan(math.radians(EXIT_DEG))
    for s in (1, -1):
        pts = [(s * (xf + 0.3), 0.4), (s * (xc - CREST), yc), (s * (xc - CREST), yc + 0.3),
               (s * rim, yc + 0.3 + run), (s * rim, yb), (s * (xf + 0.3), yb)]
        if s < 0:
            pts = list(reversed(pts))
        pads.append(prism(name + f"_pad{s}", pts, z0, z1))
    S.union(body, pads)
    zc = (z0 + z1) / 2
    pk = []
    for s in (1, -1):   # walled pocket for the rubber: 4.2 x 7.2, floor PAD thickness behind the rubber face
        x0_, x1_ = rim - 0.6, xc + PAD[2] + GLUE
        pk.append(prism(name + f"_pk{s}", rect(min(s * x0_, s * x1_), yp - PAD[0] / 2 - PAD_FIT,
                                               max(s * x0_, s * x1_), yp + PAD[0] / 2 + PAD_FIT),
                        zc - PAD[1] / 2 - PAD_FIT, zc + PAD[1] / 2 + PAD_FIT))
    let = S.text(name + "_t", g["size"], 2.6, 0.8, loc=(0, (yw + yr) / 2 - 1.0, z1), align="CENTER")
    S.bake(let)
    S.cut(body, pk + [let])
    clean(body, min_vol=5.0)
    S.assign(body, S.pla("black"))
    return body


def pads_for(name, g, z0=Z0C, z1=H):
    """The two neoprene pads (render props), in cartridge-local coordinates."""
    m = S.material("Neoprene", (0.06, 0.06, 0.065, 1), rough=0.8)
    zc = (z0 + z1) / 2
    out = []
    for s in (1, -1):
        x0_, x1_ = g["x_c"], g["x_c"] + PAD[2]
        o = prism(f"{name}_rub{s}", rrect_pts(PAD[2], PAD[0], 0.3, c=(s * (x0_ + x1_) / 2, g["y_p"])),
                  zc - PAD[1] / 2, zc + PAD[1] / 2, bevel=0.2)
        S.assign(o, m)
        out.append(o)
    return out


def place(ob, x0, front):
    """Cartridge local -> world. Front row opens to -y, back row to +y."""
    if front:
        M = Matrix.Translation((x0, SF + WALL + FRONT_GAP, 0))
    else:
        M = Matrix.Translation((x0, SB - WALL - FRONT_GAP, 0)) @ Matrix.Rotation(math.pi, 4, "Z")
    ob.data.transform(M)
    return ob


def pocket_cutters(tag, g, x0, front, fit=None):
    fit = FIT if fit is None else fit
    hi, Wc, Dc = g["hi"], g["W"], g["D"]
    y0 = -FRONT_GAP - fit
    # main pocket up to the lip, then the top layer stops short of the back by the lip overhang
    a = prism(tag + "_pk", rrect_pts(Wc + 2 * fit, Dc + FRONT_GAP + 2 * fit, 2.1, c=(0, (y0 + Dc + fit) / 2)),
              Z0C, H - LIP[1])
    b = prism(tag + "_pt", rrect_pts(Wc + 2 * fit, Dc + FRONT_GAP + 2 * fit - LIP[0], 2.1,
                                     c=(0, (y0 + Dc + fit - LIP[0]) / 2)), H - LIP[1] - 0.3, H + 1)
    o = prism(tag + "_op", rect(-(Wc / 2 - 1.0), y0 - 0.37, Wc / 2 - 1.0, Dc - 1.0), H - T - 1, Z0C + 0.5)
    gr = prism(tag + "_gr", rect(-(Wc / 2 + fit + 0.7), 1.4, Wc / 2 + fit + 0.7, 8.6), Z0C + 1.8, Z0C + 4.2)
    sl = prism(tag + "_sl", [(-(hi / 2 + 1.7), -WALL - FRONT_GAP - 0.37), (hi / 2 + 1.7, -WALL - FRONT_GAP - 0.37),
                             (hi / 2 + 0.4, -WALL - FRONT_GAP + 1.0), (hi / 2 + 0.4, 0.5), (-(hi / 2 + 0.4), 0.5),
                             (-(hi / 2 + 0.4), -WALL - FRONT_GAP + 1.0)], H - T - 1, H + 1)
    # paperclip release: a hole down to each bump from the shelf top, pressing the bump's 45 deg face in
    rel = [prism(tag + f"_rh{s_}", circle_pts(0.6, 20, c=(s_ * (Wc / 2 + fit + 0.45), 5.0)), Z0C + 3.0, H + 1)
           for s_ in (1, -1)]
    return [place(q, x0, front) for q in (a, b, o, gr, sl) + tuple(rel)]


def seat_xy(g, d, x0, front):
    yl = g["y_wall"] - d / 2 + FRONT_GAP
    return (x0, SF + WALL + yl) if front else (x0, SB - WALL - yl)


def clean(ob, min_vol=50.0):
    """Drop loose shells a boolean left behind (tiny or inside-out pieces)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.faces.ensure_lookup_table()
    seen, kill = set(), []
    for f in bm.faces:
        if f.index in seen:
            continue
        comp, stack = [], [f]
        seen.add(f.index)
        while stack:
            g_ = stack.pop()
            comp.append(g_)
            for e in g_.edges:
                for h_ in e.link_faces:
                    if h_.index not in seen:
                        seen.add(h_.index)
                        stack.append(h_)
        vol = 0.0
        for g_ in comp:
            vs = [v.co for v in g_.verts]
            for i in range(1, len(vs) - 1):
                vol += vs[0].dot(vs[i].cross(vs[i + 1])) / 6
        if vol < min_vol:
            kill += comp
    if kill:
        bmesh.ops.delete(bm, geom=list(set(kill)), context="FACES")
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bm.to_mesh(ob.data)
    bm.free()
    return len(kill)


# ================================================================== brushes (render props)
HANDLES = [((0.012, 0.012, 0.013, 1), 0.25, 0.0), ((0.80, 0.55, 0.45, 1), 0.25, 1.0),
           ((0.55, 0.33, 0.18, 1), 0.45, 0.0), ((0.78, 0.74, 0.72, 1), 0.3, 0.0),
           ((0.55, 0.30, 0.32, 1), 0.3, 0.0)]
HAIRS = [(0.42, 0.32, 0.25, 1), (0.16, 0.10, 0.07, 1), (0.75, 0.68, 0.58, 1), (0.05, 0.045, 0.045, 1)]


def bmat(kind, i):
    if kind == "h":
        col, rough, metal = HANDLES[i % len(HANDLES)]
        m = S.material(f"Handle{i % len(HANDLES)}", col, rough=rough, coat=0.4)
        m.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = metal
        return m
    if kind == "f":
        m = S.material("Ferrule", (0.80, 0.62, 0.48, 1), rough=0.22)
        m.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 1.0
        return m
    return S.material(f"Hair{i % len(HAIRS)}", HAIRS[i % len(HAIRS)], rough=0.8)


def head_prof(z0, hd, rf, down=True, liner=False):
    """Bristle head hanging from z0 (down) or standing on z0 (up)."""
    sgn = -1 if down else 1
    if liner:
        hl = 16 + hd
        pts = [(rf, z0), (hd / 2, z0 + sgn * hl * 0.35), (hd / 2 * 0.7, z0 + sgn * hl * 0.75),
               (0.8, z0 + sgn * hl * 0.98), (0, z0 + sgn * hl)]
        return [(0, z0)] + pts, hl
    hl = min(52, 10 + 0.75 * hd)
    pts = []
    for i in range(1, 25):
        u = i / 24
        rr = rf + (hd / 2 - rf) * math.sin(min(1, u / 0.55) * math.pi / 2) * \
            (1 if u < 0.55 else math.cos((u - 0.55) / 0.45 * math.pi / 2) ** 0.6)
        pts.append((max(rr, 0.01), z0 + sgn * hl * u))
    return [(0, z0), (rf, z0)] + pts[:-1] + [(0, z0 + sgn * hl)], hl


def brush(name, i, x, y, zc):
    """One measured brush hanging head-down, gripped at its middle at height zc."""
    d, heads, L, kind = BRUSHES[name]
    r0 = d / 2
    top, bot = zc + L / 2, zc - L / 2
    hm, fm, am = bmat("h", i), bmat("f", i), bmat("a", i)
    parts = []
    if kind == "double":
        rf = r0 * 1.25
        fl = 16
        hl_dn = min(52, 10 + 0.75 * heads[0])
        hl_up = min(52, 10 + 0.75 * heads[1])
        z_fd, z_fu = bot + hl_dn, top - hl_up
        h = lathe(name + "_handle", [(0, z_fd + fl), (rf * 0.95, z_fd + fl), (r0, zc - 15), (r0, zc + 15),
                                     (rf * 0.95, z_fu - fl), (0, z_fu - fl)], 40)
        f1 = lathe(name + "_f1", [(0, z_fd), (rf, z_fd), (rf, z_fd + fl), (0, z_fd + fl)], 40)
        f2 = lathe(name + "_f2", [(0, z_fu - fl), (rf, z_fu - fl), (rf, z_fu), (0, z_fu)], 40)
        p1, _ = head_prof(z_fd, heads[0], rf, down=True)
        p2, _ = head_prof(z_fu, heads[1], rf, down=False)
        a1 = lathe(name + "_head", p1, 48)
        a2 = lathe(name + "_head2", list(reversed(p2)), 48)
        parts = [(h, hm), (f1, fm), (f2, fm), (a1, am), (a2, am)]
    else:
        liner = kind == "liner"
        rf = r0 * (0.8 if liner else 1.0) + (0 if liner else 1.3)
        fl = 14 if liner else 20
        prof, hl = head_prof(0, heads[0], rf * 0.95, down=True, liner=liner)
        z_f = bot + hl
        h = lathe(name + "_handle", [(0, top), (r0 - 1.0, top), (r0, top - 1.5), (r0, zc - 10),
                                     (rf + (0 if liner else 0.6), z_f + fl), (0, z_f + fl)], 40)
        f = lathe(name + "_ferrule", [(0, z_f), (rf * 0.95, z_f), (rf, z_f + fl), (0, z_f + fl)], 40)
        a = lathe(name + "_head", [(r, z + z_f) for r, z in prof], 48)
        parts = [(h, hm), (f, fm), (a, am)]
    out = []
    for ob, m in parts:
        S.assign(ob, m)
        ob.location.x += x
        ob.location.y += y
        S.bake(ob)
        out.append(ob)
    return out


def safe_cut(target, cutters):
    """EXACT boolean, one cutter at a time; if a cut wipes out most of the part (a known EXACT failure on
    near-coincident faces), undo it and retry with the cutter nudged by 0.013 mm."""
    for c in cutters:
        cname = c.name
        before = target.data.copy()
        v0 = vol_com(target)[0]
        spare = c.copy()
        spare.data = c.data.copy()
        bpy.context.collection.objects.link(spare)
        S.cut(target, [c])
        if vol_com(target)[0] < 0.7 * v0:
            target.data = before
            spare.data.transform(Matrix.Translation((0.013, 0.011, 0.0)))
            S.cut(target, [spare])
            if vol_com(target)[0] < 0.7 * v0:
                raise RuntimeError(f"boolean failed on {cname}")
        else:
            bpy.data.objects.remove(spare, do_unlink=True)
    return target


# ================================================================== the stand
def build():
    P = {}
    # ---------------------------------------------------------------- tray (black)
    yc0 = (YF + YB) / 2
    # pour spout: a lip drawn out of the front edge, right of centre, under the carry window's reach
    SPX = SPOUT_X
    lip = [(SPX - 16, YF), (SPX - 10, YF - 3.2), (SPX - 6, YF - 8.2), (SPX - 3, YF - 10.2), (SPX, YF - 10.8),
           (SPX + 3, YF - 10.2), (SPX + 6, YF - 8.2), (SPX + 10, YF - 3.2), (SPX + 16, YF)]
    ol = rrect_pts(W, YB - YF, 10, c=(0, yc0))
    k = next(i for i in range(len(ol)) if abs(ol[i][1] - YF) < 1e-6 and ol[i][0] < 0 and
             abs(ol[(i + 1) % len(ol)][1] - YF) < 1e-6)
    ol = ol[:k + 1] + lip + ol[k + 1:]
    tray = prism("Tray", ol, 0, BH, bevel=1.0)
    well = prism("Well", rrect_pts(W - 4.8, YB - YF - 4.8, 7.6, c=(0, yc0)), 2.4, BH + 2)
    for v in well.data.vertices:          # floor falls ~2 mm towards the front edge and spout
        if v.co.z < 3:
            v.co.z = 2.4 + 1.8 * (v.co.y - YF) / (YB - YF)
    chan = prism("Chan", stadium_seg((SPX, YF + 14), (SPX, YF - 16), 5.5), 9.0, BH + 2)   # spout notch down to z 9
    drip = prism("Drip", rect(SPX - 7, YF - 8.6, SPX + 7, YF - 7.6), -1, 1.0)   # drip break under the lip
    feet = [S.cylinder(f"FootPk{i}", 10.4, 2.0, loc=(sx * 70, sy, 0)) for i, (sx, sy) in
            enumerate(FEET)]
    # the back wall stays low behind the panel: the panel and the stowed shelf swing out of this slot
    slot = prism("BackSlot", rrect_pts(2 * (PX + 0.8), 12.0, 1.0, c=(0, YB + 1.0)), 14.0, BH + 2)
    S.cut(tray, [well, chan, drip, slot] + feet)
    # hinge towers, back stop, stay pivots
    adds = []
    for sx in (-1, 1):
        adds.append(prism(f"Tw{sx}", rrect_pts(10, 12, 2, c=(sx * 73, HY)), 2, HZ, bevel=0.4))
        adds.append(xcyl(f"TwK{sx}", 6, *sorted((sx * 68, sx * 78)), HY, HZ))
        adds.append(xcyl(f"PivB{sx}", 4, *sorted((sx * (STAY_X[1] + 0.3), sx * 85.8)), *STAY_P))
        # inboard clevis tab: the stay pivot dowel works in double shear, not as a cantilever
        tab = hull(circle_pts(4.0, 32, c=STAY_P) + [(STAY_P[0] - 6, 2.0), (STAY_P[0] + 6, 2.0)])
        adds.append(yz_prism(f"Clevis{sx}", tab, *sorted((sx * 77.0, sx * (STAY_X[0] - 0.3))), bevel=0.4))
    # back stop: a low rib in front of the panel foot; the panel's below-axis edge rests on it
    adds.append(prism("Rib", rrect_pts(96, 4.9, 1.0, c=(0, PF - 2.55)), 2.0, 14.5, bevel=0.4))
    # ballast sill along the front wall, hollow from below for ~95 g of steel
    adds.append(prism("Sill", rrect_pts(SILL[1] - SILL[0] + 6, 14.0, 2.0, c=((SILL[0] + SILL[1]) / 2, YF + 2.4 + 7.0)),
                      2.0, 12.6, bevel=0.6))
    for sx in (-1, 1):    # rest pads under the folded panel's free end
        adds.append(prism(f"Pad{sx}", circle_pts(4.0, 32, c=(sx * 60, -45)), 2.0, 14.9, bevel=0.4))
    S.union(tray, adds)
    bores = []
    for sx in (-1, 1):
        bores.append(xcyl(f"TwB{sx}", 2.95 / 2, *sorted((sx * 67.5, sx * 79)), HY, HZ, seg=24))
        bores.append(xcyl(f"PvB{sx}", 2.95 / 2, *sorted((sx * 76.0, sx * 87.0)), *STAY_P, seg=24))  # tab + boss, blind
    bores.append(prism("BallastPk", rect(SILL[0], YF + 3.4, SILL[1], YF + 13.8), -1, 10.4))  # 100x10x10 bar, glued
    S.cut(tray, bores)
    clean(tray)
    S.assign(tray, S.pla("black"))
    P["tray"] = tray
    caps = []   # steel dowels: panel hinge 3 x 25, stay pivots 3 x 8
    for sx in (-1, 1):
        caps.append(xcyl(f"DowelT{sx}", 1.5, *sorted((sx * 53, sx * 78)), HY, HZ, seg=24))
    for c_ in caps:
        S.assign(c_, steel())
    P["tray_caps"] = caps
    feet_o = []
    for i, (sx, sy) in enumerate(FEET):
        f = lathe(f"Foot{i}", [(0, -1.2), (4.6, -1.2), (5.0, -0.6), (5.0, 1.0), (0, 1.0)], 32)
        f.location = (sx * 70, sy, 0)
        S.bake(f)
        S.assign(f, silicone())
        feet_o.append(f)
    P["feet"] = feet_o

    # ---------------------------------------------------------------- panel (white)
    z_bot = HZ - 6.0
    pan = xz_prism("Panel", rrect_pts(2 * PX, RAIL[0] + 2 - z_bot, 4, c=(0, (RAIL[0] + 2 + z_bot) / 2)), PF, PF + PT,
                   bevel=1.0)
    rail = prism("Rail", rrect_pts(2 * 85.0, YB - 0.6 - PF, 2.0, c=(0, (PF + YB - 0.6) / 2)), RAIL[0], RAIL[1], bevel=1.0)
    knk = [xcyl(f"PanK{sx}", 6, *sorted((sx * 52, sx * 66)), HY, HZ) for sx in (-1, 1)]
    S.union(pan, [rail] + knk)
    win = xz_prism("Win", C.stadium_pts(WIN_W, 26), PF - 1, PF + PT + 1)
    win.location.z = 108
    S.bake(win)
    ears = []
    for sx in (-1, 1):   # rail ears carry the shelf hinge pin, inboard of the cheek knuckles
        ears.append(xcyl(f"Ear{sx}", 5.0, *sorted((sx * 73.37, sx * 80.6)), *AX, seg=40))
        ears.append(yz_prism(f"EarB{sx}", rect(PF + 3.0, RAIL[1] - 1.37, YB, H - 0.3), *sorted((sx * 73.21, sx * 80.6)),
                             bevel=0.0))
    pribs = [prism(f"PRib{sx}{k}", rrect_pts(5, 5.2, 1.0, c=(sx * xr, PF + PT + 2.4)), 30, RAIL[0] + 0.5, bevel=0.5)
             for sx in (-1, 1) for k, xr in enumerate(PRIB_X)]
    S.union(pan, ears + pribs)
    notch = [prism(f"Notch{sx}", rect(min(sx * 67.4, sx * 81), PF - 1, max(sx * 67.4, sx * 81), PF + PT + 1),
                   0, HZ + 6.6) for sx in (-1, 1)]       # clears the tray's hinge towers
    S.cut(pan, notch)
    flat = prism("KnFlat", rect(-90, PF - 8, 90, PF + PT + 8), z_bot - 10, z_bot)   # knuckles flat at the foot
    bores = [xcyl(f"PanB{sx}", 1.6, *sorted((sx * 50, sx * 68)), HY, HZ, seg=24) for sx in (-1, 1)]
    bores += [xcyl(f"PegB{sx}", 2.95 / 2, *sorted((sx * (PX - 8.0), sx * (PX + 1))), *STAY_Q, seg=24) for sx in (-1, 1)]
    bores += [xcyl(f"EarB{sx}", 2.95 / 2, *sorted((sx * 72.2, sx * 81.3)), *AX, seg=24) for sx in (-1, 1)]
    S.cut(pan, [win, flat, C.label("BRUSH / 02", 3.4, (0, (PF + YB) / 2 - 2, RAIL[1]))] + bores)
    clean(pan)
    S.assign(pan, S.pla("white"))
    P["panel"] = pan
    P["pegs"] = []
    for sx in (-1, 1):   # 3 x 12 steel dowels pressed 8 mm into the panel sides; the stays hook over them
        pg = xcyl(f"PegD{sx}", 1.5, *sorted((sx * (PX - 8.0), sx * (STAY_X[1] + 0.3))), *STAY_Q, seg=24)
        S.assign(pg, steel())
        P["pegs"].append(pg)

    # ---------------------------------------------------------------- shelf (white) + cartridges
    shelf = prism("Shelf", rrect_pts(W, SD, 6, c=(0, (SF + SB) / 2)), H - T, H, bevel=1.0)
    cheeks = [prism(f"Cheek{sx}", rrect_pts(7, YB - SB + 4, 2, c=(sx * 84.5, (SB - 4 + YB) / 2)), H - T, H,
                    bevel=0.8) for sx in (-1, 1)]
    ck = [xcyl(f"CheekK{sx}", 5.0, *sorted((sx * 81, sx * 88)), *AX) for sx in (-1, 1)]
    # stiffening: a T-rib under the web between the rows, and the cheeks run forward as deep side rails,
    # so the shelf is a stiff frame hung from the hinge instead of a perforated plate on two tabs
    dz0 = H - T - DOWN
    rib = prism("Rib", rrect_pts(W - 4, RIB_Y[1] - RIB_Y[0], 1.5, c=(0, sum(RIB_Y) / 2)), dz0, H - T + 0.5, bevel=0.6)
    # side rails, tapering up into the cheek over the last 10 mm (no abrupt end at the stop)
    rprof = [(SF + 1.5, dz0), (PF - 12, dz0), (PF - 2, H - T - 1.0), (PF - 2, H - T + 0.5), (SF + 1.5, H - T + 0.5)]
    rails = [yz_prism(f"Rail{sx}", rprof, *sorted((sx * (W / 2 - RAIL_W), sx * (W / 2 - 0.4))), bevel=0.5)
             for sx in (-1, 1)]
    # cheeks widen inboard to 11 mm behind the loading corridor, where the stop moment peaks
    cheeks += [prism(f"CheekW{sx}", rrect_pts(5, PF + 2.5 - (SB + 12), 1.5, c=(sx * 79.5, (PF + 2.5 + SB + 12) / 2)),
                     H - T, H, bevel=0.8) for sx in (-1, 1)]
    S.union(shelf, cheeks + ck + [rib] + rails)
    carts, brushes, seats, rings = [], [], [], []
    cutters = []
    for row, front in ((FRONT, True), (BACK, False)):
        for name, x0 in row:
            d = BRUSHES[name][0]
            g = cart_geom(d, LOAD_G[name])
            cutters += pocket_cutters(f"P{name}", g, x0, front)
            c_ = place(cartridge(f"Cart{name}", g), x0, front)
            c_["size"] = g["size"]
            carts.append(c_)
            for o_ in pads_for(f"Cart{name}", g):
                place(o_, x0, front)
                rings.append(o_)
            seats.append((name, g["size"], front, seat_xy(g, d, x0, front)))
    safe_cut(shelf, cutters + [xcyl(f"ChB{sx}", 3.05 / 2, *sorted((sx * 80, sx * 90)), *AX, seg=24) for sx in (-1, 1)])
    P["shelf_clean"] = clean(shelf)
    S.assign(shelf, S.pla("white"))
    P["shelf"], P["carts"], P["orings"] = shelf, carts, rings
    scaps = [xcyl(f"DowelS{sx}", 1.5, *sorted((sx * 74, sx * 88)), *AX, seg=24) for sx in (-1, 1)]
    for c_ in scaps:
        S.assign(c_, steel())
    P["shelf_caps"] = scaps

    # ---------------------------------------------------------------- prop stays (black)
    stays = []
    for sx in (-1, 1):
        p, q = STAY_P, STAY_Q
        st = yz_prism(f"Stay{sx}", stadium_seg(p, q, 4.0), *sorted((sx * STAY_X[0], sx * STAY_X[1])), bevel=0.5)
        holes = [xcyl(f"StH{sx}", 3.2 / 2, *sorted((sx * 79, sx * 87)), *p, seg=24)]   # running fit
        # hook at the top: a slot open downwards along the stay so the peg drops in
        ang = math.atan2(q[1] - p[1], q[0] - p[0])
        tail = (q[0] - 6 * math.cos(ang) + 0 * math.sin(ang), q[1] - 6 * math.sin(ang))
        hook = yz_prism(f"StHk{sx}", stadium_seg(q, (q[0] + 7 * math.sin(ang), q[1] - 7 * math.cos(ang)), 1.55),
                        *sorted((sx * 79, sx * 87)))
        S.cut(st, holes + [hook])
        _ = tail
        # detent: two 0.3 mm bumps at the slot mouth; the peg clicks past them
        dv = (math.sin(ang), -math.cos(ang))
        pv = (math.cos(ang), math.sin(ang))
        m = (q[0] + 3.4 * dv[0], q[1] + 3.4 * dv[1])
        S.union(st, [yz_prism(f"StD{sx}{k}", circle_pts(0.55, 16, c=(m[0] + k * 1.98 * pv[0], m[1] + k * 1.98 * pv[1])),
                              *sorted((sx * STAY_X[0], sx * STAY_X[1]))) for k in (1, -1)])
        stay_dw = xcyl(f"DowelP{sx}", 1.5, *sorted((sx * 77.0, sx * 87.0)), *p, seg=24)   # 3 x 10, clevis to boss
        S.assign(stay_dw, steel())
        P.setdefault("stay_dowels", []).append(stay_dw)
        S.assign(st, S.pla("black"))
        C.set_origin(st, (0, *p))
        C.parent_keep(stay_dw, st)
        stays.append(st)
    P["stays"] = stays

    # ---------------------------------------------------------------- brushes
    zc = H - T / 2
    for i, (name, size, front, (x, y)) in enumerate(seats):
        brushes += brush(name, i, x, y, zc)
    P["brushes"] = brushes
    P["seats"] = seats

    # ---------------------------------------------------------------- pivots / hierarchy
    C.set_origin(pan, (0, HY, HZ))
    C.set_origin(shelf, (0, *AX))
    C.parent_keep(shelf, pan)
    for o in carts + scaps + rings:
        C.parent_keep(o, shelf)
    for o in P["pegs"]:
        C.parent_keep(o, pan)
    return P


def parts_of(P):
    return ([P["tray"], P["panel"], P["shelf"]] + P["tray_caps"] + P["feet"] + P["carts"] +
            P["shelf_caps"] + P["stays"] + P["stay_dowels"] + P["pegs"] + P["orings"])


FOLD_PAN = (math.pi / 2, 0, 0)
FOLD_SHELF = (-3 * math.pi / 2, 0, 0)
FOLD_STAY = (math.pi - math.atan2(STAY_Q[1] - STAY_P[1], STAY_Q[0] - STAY_P[0]), 0, 0)  # lies flat


def folded(P):
    return ([(P["panel"], "rotation_euler", FOLD_PAN), (P["shelf"], "rotation_euler", FOLD_SHELF)] +
            [(s, "rotation_euler", FOLD_STAY) for s in P["stays"]])


def anim(P):
    """Loop: folded -> panel up -> shelf over the top -> stays hooked -> hold -> reverse."""
    Z = (0, 0, 0)
    pk = [(0, FOLD_PAN), (0.06, FOLD_PAN), (0.24, Z), (0.80, Z), (0.94, FOLD_PAN), (1.0, FOLD_PAN)]
    sk = [(0, FOLD_SHELF), (0.24, FOLD_SHELF), (0.40, Z), (0.66, Z), (0.80, FOLD_SHELF), (1.0, FOLD_SHELF)]
    tk = [(0, FOLD_STAY), (0.40, FOLD_STAY), (0.50, Z), (0.58, Z), (0.66, FOLD_STAY), (1.0, FOLD_STAY)]
    out = [(P["panel"], "rotation_euler", 0, pk), (P["shelf"], "rotation_euler", 0, sk)]
    out += [(s, "rotation_euler", 0, tk) for s in P["stays"]]
    return out


# ================================================================== stats
def vol_com(ob):
    """Volume (mm^3) and centroid (world mm) of a closed mesh."""
    me = ob.data
    Mw = ob.matrix_world
    v = [Mw @ x.co for x in me.vertices]
    tot, cx, cy, cz = 0.0, 0.0, 0.0, 0.0
    me.calc_loop_triangles()
    for tri in me.loop_triangles:
        a, b, c = (v[i] for i in tri.vertices)
        dv = a.dot(b.cross(c)) / 6
        tot += dv
        cx += dv * (a.x + b.x + c.x) / 4
        cy += dv * (a.y + b.y + c.y) / 4
        cz += dv * (a.z + b.z + c.z) / 4
    return abs(tot), (cx / tot, cy / tot, cz / tot) if tot else (0, 0, 0)


def stats(P):
    bpy.context.view_layer.update()
    rho = 1.24e-3 * 0.57          # g/mm^3: PLA at 2 walls / 15 % infill (calibrated on the sliced parts)
    rows, mass, mx, my, mz = [], 0.0, 0.0, 0.0, 0.0
    for o in [P["tray"], P["panel"], P["shelf"]] + P["stays"] + P["carts"]:
        vv, c = vol_com(o)
        m = vv * rho
        rows.append((o.name, round(vv / 1000, 1), round(m, 1)))
        mass += m
        mx += m * c[0]
        my += m * c[1]
        mz += m * c[2]
    bal = 78.0                    # steel in the front sill (100 x 10 x 10 mm bar)
    mass += bal
    mx += bal * (SILL[0] + SILL[1]) / 2
    my += bal * (YF + 8.6)
    mz += bal * 6
    stand = mass
    ecom_y = my / mass
    # brushes: 12-40 g dry each; take wet weights
    bw = {"liner": 10, "single": 18, "double": 38}
    for name, _s, _f, (x, y) in P["seats"]:
        m = wet_g(name)
        mass += m
        mx += m * x
        my += m * y
        mz += m * (H - 10)
    com = (mx / mass, my / mass, mz / mass)
    g = 9.81e-3
    foot_back, foot_front = FEET[2][1] + 3, FEET[0][1] - 3   # bumper outer edge
    h = H - T / 2
    tip_back = mass * g * (foot_back - com[1]) / h      # N, pushing a front-row brush in (backwards)
    tip_fwd = mass * g * (com[1] - foot_front) / h      # N, pushing a back-row brush in (forwards)
    carts = {n: cart_geom(BRUSHES[n][0], LOAD_G[n]) for n, _x in FRONT + BACK}
    e_back = stand * g * (foot_back - ecom_y) / h
    e_fwd = stand * g * (ecom_y - foot_front) / h
    out = dict(empty_tip_back_N=round(e_back, 2), empty_tip_fwd_N=round(e_fwd, 2), parts=rows, stand_g=round(stand), loaded_g=round(mass), com=[round(c, 1) for c in com],
               tip_push_back_N=round(tip_back, 2), tip_push_fwd_N=round(tip_fwd, 2),
               carts={k: {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in g_.items()}
                      for k, g_ in carts.items()},
               seats=[(n, s, "front" if f else "back", round(x, 1), round(y, 1)) for n, s, f, (x, y) in P["seats"]])
    with open(os.path.join(OUT, "folio_stats.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))
    return out


# ================================================================== rendering
def gpu():
    if "--gpu" not in ARGS:
        return
    p = bpy.context.preferences.addons["cycles"].preferences
    p.compute_device_type = "OPTIX"
    p.get_devices()
    for d in p.devices:
        d.use = d.type == "OPTIX"
    bpy.context.scene.cycles.device = "GPU"


def setup(P, samples=128, res=(1400, 1050)):
    S.to_studio([o for o in parts_of(P) + P["brushes"] if o.parent is None])
    for o in parts_of(P):
        if o.type == "MESH":
            S.smooth(o, 32)
    S.studio(samples=24 if PREVIEW else samples, res=(700, 525) if PREVIEW else res)
    gpu()


def show_brushes(P, on):
    for b in P["brushes"]:
        b.hide_render = not on


def stills(P):
    open_pose = [(o, p, tuple(getattr(o, p))) for o, p, _ in folded(P)]
    S.camera((0.44, -0.62, 0.38), (0, -0.005, 0.105), 55, name="Hero")
    S.render(os.path.join(OUT, "hero.png"))
    S.camera((-0.52, -0.50, 0.26), (0, 0, 0.11), 55, name="Side")
    S.render(os.path.join(OUT, "side.png"))
    S.camera((-0.62, 0.02, 0.16), (0, 0, 0.11), 55, name="Profile")
    S.render(os.path.join(OUT, "profile.png"))
    S.camera((0.0, -0.10, 0.78), (0, -0.005, 0.0), 60, name="Top")
    S.render(os.path.join(OUT, "top.png"))
    S.camera((0.30, 0.55, 0.42), (0, 0.0, 0.10), 55, name="Back")
    S.render(os.path.join(OUT, "back.png"))
    show_brushes(P, False)
    S.camera((0.42, -0.60, 0.36), (0, 0, 0.085), 55, name="Empty")
    S.render(os.path.join(OUT, "empty.png"))
    C.apply_pose(folded(P))
    S.camera((0.36, -0.52, 0.30), (0, -0.005, 0.02), 60, name="Folded")
    S.render(os.path.join(OUT, "folded.png"))
    C.apply_pose(open_pose)
    # exploded
    moves = [(P["shelf"], (0, 0, 70)), (P["panel"], (0, 40, 30))]
    for c_ in P["carts"]:
        moves.append((c_, (0, 0, 32)))
    for s in P["stays"]:
        moves.append((s, (math.copysign(40, s.matrix_world.translation.x), 0, 0)))
    base = [(o, o.location.copy()) for o, _ in moves]
    for o, d in moves:
        o.location = o.location + Vector(d)
    S.camera((0.50, -0.66, 0.44), (0, 0.01, 0.12), 55, name="Exploded")
    S.render(os.path.join(OUT, "exploded.png"))
    for o, l in base:
        o.location = l
    show_brushes(P, True)


def closeups(P):
    sc = bpy.context.scene
    # 1 clip cartridges, front-left (L and S) with handles in
    S.camera((0.02, -0.22, 0.25), (-0.030, -0.050, 0.140), 55, name="CuClip")
    S.render(os.path.join(OUT, "cu_clip.png"))
    show_brushes(P, False)
    S.camera((-0.043, -0.10, 0.235), (-0.043, -0.045, 0.150), 60, name="CuClipEmpty")
    S.render(os.path.join(OUT, "cu_clip_empty.png"))
    # 2 spout
    S.camera((0.11, -0.22, 0.16), (0.045, -0.085, 0.006), 70, name="CuSpout")
    S.render(os.path.join(OUT, "cu_spout.png"))
    # 3 stay and hook
    S.camera((0.26, -0.06, 0.08), (0.085, 0.035, 0.035), 60, name="CuStay")
    S.render(os.path.join(OUT, "cu_stay.png"))
    # 4 shelf hinge over the rail
    S.camera((0.20, 0.18, 0.20), (0.08, 0.06, 0.14), 60, name="CuHinge")
    S.render(os.path.join(OUT, "cu_hinge.png"))
    # 5 loading gap, looking down past the back row
    show_brushes(P, True)
    S.camera((0.10, 0.20, 0.33), (0.0, 0.02, 0.10), 50, name="CuGap")
    S.render(os.path.join(OUT, "cu_gap.png"))
    _ = sc


def run_anim(P):
    show_brushes(P, False)
    sc = bpy.context.scene
    n = 24 if PREVIEW else 144
    C.keyframe(anim(P), 1, n)
    sc.frame_start, sc.frame_end = 1, n
    sc.render.fps = 24
    sc.cycles.samples = 12 if PREVIEW else 28
    sc.render.resolution_x, sc.render.resolution_y = (480, 360) if PREVIEW else (960, 720)
    S.camera((0.50, -0.66, 0.40), (0, 0.0, 0.085), 50, name="CamAnim")
    if "--checkframes" in ARGS:
        os.makedirs(os.path.join(OUT, "check"), exist_ok=True)
        for t in (0.0, 0.15, 0.3, 0.45, 0.55, 0.7, 0.85):
            sc.frame_set(round(1 + (n - 1) * t))
            S.render(os.path.join(OUT, "check", f"fold_t{int(t * 100):02d}.png"))
        return
    sc.render.image_settings.media_type = "VIDEO"
    sc.render.image_settings.file_format = "FFMPEG"
    sc.render.ffmpeg.format = "MPEG4"
    sc.render.ffmpeg.codec = "H264"
    sc.render.ffmpeg.constant_rate_factor = "HIGH"
    sc.render.filepath = os.path.join(OUT, "fold.mp4")
    bpy.ops.render.render(animation=True)


def cart_set():
    """Three of the cartridges (smallest, middle, largest handle) with their handle seated."""
    S.reset()
    obs = []
    hm = S.material("Handle", (0.20, 0.10, 0.10, 1), rough=0.35, coat=0.3)
    for d, w, x in ((6.95, 45, -36), (12.3, 60, 0), (16.8, 75, 40)):
        g = cart_geom(d, w)
        c_ = cartridge(f"C{d}", g, 0, T - 1)
        c_.data.transform(Matrix.Translation((x, -g["D"] / 2, 0)))
        obs.append(c_)
        for o_ in pads_for(f"C{d}", g, 0, T - 1):
            o_.data.transform(Matrix.Translation((x, -g["D"] / 2, 0)))
            obs.append(o_)
        h = lathe(f"H{d}", [(0, T + 18), (d / 2 - 0.8, T + 18), (d / 2, T + 17), (d / 2, -12), (0, -12)], 48)
        S.assign(h, hm)
        h.location = (x, -g["D"] / 2 + g["y_wall"] - d / 2, 0)
        S.bake(h)
        obs.append(h)
    S.to_studio(obs)
    for o in obs:
        S.smooth(o, 32)
    S.studio(samples=24 if PREVIEW else 160, res=(700, 525) if PREVIEW else (1400, 1050))
    gpu()
    S.camera((0.05, -0.17, 0.15), (0.002, -0.005, 0.004), 60, name="Carts")
    S.render(os.path.join(OUT, "carts.png"))
    for o in obs:
        if o.name.startswith("H"):
            o.hide_render = True
    S.camera((0.002, -0.004, 0.24), (0.002, -0.004, 0.0), 50, name="CartsTop")
    S.render(os.path.join(OUT, "carts_top.png"))
    # close-up of the 12.3 mm cartridge: post, O-ring, ramp, snap bump
    S.camera((0.030, -0.058, 0.036), (0.004, -0.017, 0.0045), 50, name="CartDetail")
    S.render(os.path.join(OUT, "cart_detail.png"))


# ================================================================== clip test strip
TEST = [("B11", -52.0), ("B10", 3.0), ("B8", 50.0)]   # heaviest, mid, thinnest-handle-with-big-head


def write_3mf(objs, path):
    """Several objects in one 3MF, each sitting on z = 0 (Blender's loop triangles, never a hand fan).
    Bambu Studio's --arrange places them on the plate."""
    res, items = [], []
    x_off = 0.0
    for i, ob in enumerate(objs, start=1):
        me = ob.data
        Mw = ob.matrix_world
        vs = [Mw @ v.co for v in me.vertices]
        lo = [min(v[k] for v in vs) for k in range(3)]
        hi = [max(v[k] for v in vs) for k in range(3)]
        off = (x_off - lo[0], -(lo[1] + hi[1]) / 2, -lo[2])
        x_off += hi[0] - lo[0] + 6
        me.calc_loop_triangles()
        vx = "".join(f'<vertex x="{v[0] + off[0]:.5f}" y="{v[1] + off[1]:.5f}" z="{v[2] + off[2]:.5f}"/>' for v in vs)
        tx = "".join(f'<triangle v1="{t.vertices[0]}" v2="{t.vertices[1]}" v3="{t.vertices[2]}"/>'
                     for t in me.loop_triangles)
        res.append(f'<object id="{i}" name="{ob.name}" type="model"><mesh><vertices>{vx}</vertices>'
                   f'<triangles>{tx}</triangles></mesh></object>')
        items.append(f'<item objectid="{i}"/>')
    model = ('<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
             f'<resources>{"".join(res)}</resources><build>{"".join(items)}</build></model>')
    ct = ('<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/'
          'package/2006/content-types"><Default Extension="rels" ContentType="application/'
          'vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" '
          'ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.'
            'openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.'
            'model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/'
            '3dmodel"/></Relationships>')
    import zipfile
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", model)


def test_strip():
    """A 156 x 100 mm slice of the front row with the three hardest brushes' cartridges.
    Lay it on the counter with the clips past the edge and a book on the back half."""
    S.reset()
    depth = 100.0
    strip = prism("ClipTest", rrect_pts(156, depth, 10, c=(0, SF + depth / 2)), H - T, H, bevel=1.0)
    cutters, carts, test_rings = [], [], []
    for name, x0 in TEST:
        g = cart_geom(BRUSHES[name][0], LOAD_G[name])
        cutters += pocket_cutters(f"T{name}", g, x0, True)
        c_ = place(cartridge(f"Cart_{g['size']}", g), x0, True)
        carts.append(c_)
        for o_ in pads_for(f"Cart_{g['size']}", g):
            test_rings.append(place(o_, x0, True))
    lab = C.label("CLIP TEST", 3.4, (0, SF + depth - 14, H))
    safe_cut(strip, cutters + [lab])
    clean(strip)
    S.assign(strip, S.pla("white"))
    # dowel fit coupon: printed upright like the panel, three horizontal bores for the 3 mm steel dowels
    fit = prism("DowelFit", rrect_pts(42, 12, 2.0, c=(0, 200)), 0, 20, bevel=0.6)
    holes = []
    for x, d in ((-13, 2.95), (0, 3.0), (13, 3.05)):
        h = S.cylinder(f"FB{d}", d, 16, loc=(x, 200, 10), rot=(math.pi / 2, 0, 0), seg=48)
        S.bake(h)
        holes.append(h)
        t = S.text(f"FT{d}", f"{d:g}", 2.2, 0.8, loc=(x, 200 - 0.9, 20), align="CENTER")
        S.bake(t)
        holes.append(t)
    S.cut(fit, holes)
    clean(fit)
    S.assign(fit, S.pla("white"))
    if "--fit" in ARGS:            # the dowel-fit block was on the first test plate; add it back with --fit
        carts = carts + [fit]
    else:
        bpy.data.objects.remove(fit, do_unlink=True)
    os.makedirs(os.path.join(HERE, "stl"), exist_ok=True)
    for o in [strip] + carts:
        S.export_stl(o, os.path.join(HERE, "stl", f"test_{o.name.lower()}.stl"))
    write_3mf([strip] + carts, os.path.join(HERE, "clip_test_white.3mf"))
    print("wrote clip_test_white.3mf")
    if "--render" in ARGS:
        hm = S.material("Handle", (0.20, 0.10, 0.10, 1), rough=0.35, coat=0.3)
        obs = [strip] + carts + test_rings
        for name, x0 in TEST:
            d = BRUSHES[name][0]
            g = cart_geom(d, LOAD_G[name])
            hx, hy = seat_xy(g, d, x0, True)
            h = lathe(f"H{name}", [(0, H + 30), (d / 2 - 0.8, H + 30), (d / 2, H + 29), (d / 2, H - 40), (0, H - 40)], 48)
            S.assign(h, hm)
            h.location = (hx, hy, 0)
            S.bake(h)
            obs.append(h)
        for o in carts:
            S.assign(o, S.pla("white"))
        S.to_studio(obs)
        for o in obs:
            S.smooth(o, 32)
        S.studio(samples=24 if PREVIEW else 160, res=(700, 525) if PREVIEW else (1400, 1050))
        gpu()
        S.camera((0.16, -0.30, 0.30), (0.0, -0.025, 0.14), 55, name="Strip")
        S.render(os.path.join(OUT, "clip_test.png"))
    return strip, carts


# ================================================================== fit block and rubber-cutting jigs
FIT_TEST = (0.05, 0.10, 0.15)


def fit_and_jigs():
    """Plate A (white): a 96 x 50 mm slab with three pockets for the same small cartridge at pocket
    clearances 0.05 / 0.10 / 0.15 mm, three of those cartridges, and two jigs for cutting the 4 x 7 mm
    neoprene pads from 1/16 in sheet: a 7 mm strip gauge and a 4 mm chop box."""
    S.reset()
    g = cart_geom(BRUSHES["B1"][0], LOAD_G["B1"])
    slab = prism("FitBlock", rrect_pts(96, 50, 4, c=(0, SF + 25)), H - T, H, bevel=0.8)
    cut, carts = [], []
    for (x0, fit) in zip((-30.0, 0.0, 30.0), FIT_TEST):
        cut += pocket_cutters(f"F{fit}", g, x0, True, fit=fit)
        lab = S.text(f"FL{fit}", f"{int(round(fit * 100)):02d}", 3.0, 0.8, loc=(x0, SF + 44.5 - 1.1, H), align="CENTER")
        S.bake(lab)
        cut.append(lab)
        c_ = place(cartridge(f"FitCart{fit}", g), x0, True)
        S.assign(c_, S.pla("white"))
        carts.append(c_)
    safe_cut(slab, cut)
    clean(slab)
    S.assign(slab, S.pla("white"))
    # strip gauge, modelled in print orientation (hook up); flip it over to use: the hook catches the
    # sheet edge and the knife runs along the far edge, 7.0 mm away
    gw, glen = PAD[1] - 0.2, 140.0              # knife runs on the bar edge: the strip comes out ~7.0
    gauge = prism("StripGauge", rect(-glen / 2, -2.5, glen / 2, gw), 0, 6.0, bevel=0.4)
    hook = prism("GaugeHook", rect(-glen / 2, -2.5, glen / 2, 0.0), 5.9, 6.0 + 1.2, bevel=0.3)
    S.union(gauge, [hook])
    gl = S.text("GaugeL", "7.0 STRIP", 3.0, 0.8, loc=(0, gw / 2 - 1.1, 6.0), align="CENTER")
    S.bake(gl)
    S.cut(gauge, [gl])
    gauge.data.transform(Matrix.Translation((0, 60, 0)))
    # chop box: channel holds the 7 mm strip, an end stop, and a blade slot 4.0 mm from the stop through
    # two guide towers
    cw_, cd_ = PAD[1] + 0.25, PAD[2] + 0.15
    stop_x = 12.0
    x_cut = stop_x - (PAD[0] - 0.1)            # slot's stop-side face 3.9 mm from the stop: pads ~4.1-4.3
    box = prism("ChopBox", rrect_pts(48, 26, 3, c=(-4, 0)), 0, 8.0, bevel=0.5)
    towers = [prism(f"Tower{s_}", rrect_pts(12, 6.5, 1.5, c=(x_cut - 0.4, s_ * (cw_ / 2 + 4.2))), 7.5, 20.0, bevel=0.5)
              for s_ in (1, -1)]
    S.union(box, towers)
    chan = prism("Chan", rect(-30, -cw_ / 2, stop_x, cw_ / 2), 8.0 - cd_, 9.0)
    slot_ = prism("Slot", rect(x_cut - 0.6, -14, x_cut, 14), 8.0 - cd_ - 0.6, 21)
    bl = S.text("BoxL", "4.0", 3.0, 0.8, loc=(-16, -cw_ / 2 - 4.0, 8.0), align="CENTER")
    S.bake(bl)
    S.cut(box, [chan, slot_, bl])
    box.data.transform(Matrix.Translation((60, 0, 0)))
    for o in (gauge, box):
        clean(o)
        S.assign(o, S.pla("white"))
    os.makedirs(os.path.join(HERE, "stl"), exist_ok=True)
    objs = [slab] + carts + [gauge, box]
    for o in objs:
        S.export_stl(o, os.path.join(HERE, "stl", f"plateA_{o.name.lower()}.stl"))
    write_3mf([slab] + carts, os.path.join(HERE, "fit_block_white.3mf"))   # production settings
    write_3mf([gauge, box], os.path.join(HERE, "jigs_white.3mf"))           # any quick profile
    print("wrote fit_block_white.3mf, jigs_white.3mf")
    if "--render" in ARGS:
        rub = []
        for (x0, fit), c_ in zip(zip((-30.0, 0.0, 30.0), FIT_TEST), carts):
            for o_ in pads_for(f"FitCart{fit}", g):
                rub.append(place(o_, x0, True))
        # a strip of rubber in the chop box, for the picture
        m = S.material("Neoprene", (0.06, 0.06, 0.065, 1), rough=0.8)
        st = prism("RubberStrip", rect(-40, -PAD[1] / 2, stop_x, PAD[1] / 2), 8.0 - cd_, 8.0 - cd_ + PAD[2], bevel=0.2)
        st.data.transform(Matrix.Translation((60, 0, 0)))
        S.assign(st, m)
        for o in [slab] + carts + rub:             # bring the slab down from shelf height to the table
            o.data.transform(Matrix.Translation((0, 0, -(H - T))))
        obs = objs + rub + [st]
        S.to_studio(obs)
        for o in obs:
            S.smooth(o, 32)
        S.studio(samples=24 if PREVIEW else 160, res=(700, 525) if PREVIEW else (1400, 1050))
        gpu()
        S.camera((0.08, -0.36, 0.34), (0.01, 0.0, 0.0), 38, name="PlateA")
        S.render(os.path.join(OUT, "plateA.png"))
        S.camera((0.11, -0.075, 0.075), (0.058, 0.0, 0.008), 50, name="ChopCU")
        S.render(os.path.join(OUT, "chopbox.png"))
        S.camera((0.05, -0.16, 0.12), (0.0, -0.042, 0.004), 45, name="FitCU")
        S.render(os.path.join(OUT, "fitblock.png"))


if __name__ == "__main__":
    if "--carts" in ARGS:
        cart_set()
    if "--teststrip" in ARGS:
        test_strip()
    if "--fitjigs" in ARGS:
        fit_and_jigs()
    if any(a in ARGS for a in ("--stills", "--closeups", "--anim", "--stats", "--blend", "--stl")):
        S.reset()
        P = build()
        if "--stats" in ARGS:
            stats(P)
        if "--stl" in ARGS:
            d = os.path.join(HERE, "stl")
            os.makedirs(d, exist_ok=True)
            done = set()
            for o in [P["tray"], P["panel"], P["shelf"], P["stays"][1]] + P["carts"]:
                key = o.get("size", o.name)
                if key in done:
                    continue
                done.add(key)
                S.export_stl(o, os.path.join(d, f"folio_{('cart_' + key) if 'size' in o else o.name.lower()}.stl"))
        setup(P)
        if "--stills" in ARGS:
            stills(P)
        if "--closeups" in ARGS:
            closeups(P)
        if "--anim" in ARGS:
            run_anim(P)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "folio_v2.blend"))
