"""Folding makeup-brush drying rack. Rev A.

Folded it is a flat white tray (170 x 112 x 8.6 mm) that fits in a drawer. To use it,
flip up the two black frames: the back frame first, then the front one. Brushes lie
across both frames, bristles forward and tilted 10 degrees down, so water runs out
of the bristles, not back into the ferrule, and the heads dry in free air.

  - 10 slots: 4 large V-notches (handles up to ~14 mm, heads up to ~28 mm wide)
    and 6 small ones (eye brushes, handles 5-9 mm).
  - Both frames lie flat in the same layer: the front frame's legs sit inside the
    back frame's legs, so the folded tray is only 8.6 mm tall.
  - No latches. The front frame leans 10 deg forward and the back frame 20 deg back,
    and both rest on a heel against the floor, so gravity holds each one up.

Run:  python brush_rack.py [--check] [--renders] [--details] [--preview]
Writes brush_rack.blend, stl/*.stl and optionally renders/*.png.

Printed parts (one colour each, no AMS):
  tray         - white PLA, floor down
  front frame  - black PLA, flat
  back frame   - black PLA, flat
Hinge pins: 4 pieces of 1.75 mm filament, about 10 mm long.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "home-devices", "tools"))
import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402
import studio as S  # noqa: E402

REV = "A"
rad = math.radians

# ---------------------------------------------------------------- tray (mm)
L = 170.0             # length (X)
FLOOR = 2.0           # floor thickness; floor top is Z0
Z0 = FLOOR
WALL = 2.4
WALL_H = 6.6          # wall height above the floor top
H_TRAY = FLOOR + WALL_H
XI = L / 2 - WALL     # inner face of the end walls

# ---------------------------------------------------------------- frames
T = 5.0               # frame thickness
PZ = 3.4              # hinge axis height above the floor top
TILT = rad(10)        # brush tilt, bristles down
LEAN_F = rad(10)      # front frame leans forward (square to the brushes)
LEAN_B = rad(20)      # back frame leans back
HN = 46.0             # groove bottom (large notch) at the front frame, above floor top
SPAN = 66.0           # horizontal distance between the two supports along a brush
BAR_BELOW, BAR_ABOVE = 7.0, 15.0   # bar extent below / above the large groove bottom
LEG_W = 5.0
# x-ranges (positive side; mirrored)
BACK_LEG = (XI - 0.4 - LEG_W, XI - 0.4)          # 77.2 .. 82.2, hinge in the end wall
FRONT_LEG = (BACK_LEG[0] - 1.2 - LEG_W, BACK_LEG[0] - 1.2)   # 71.0 .. 76.0
BLOCK = (FRONT_LEG[0] - 0.4 - 5.0, FRONT_LEG[0] - 0.4)       # pivot block, inboard
PIN_D = 1.75
HOLE_TIGHT, HOLE_FREE = 1.8, 2.1     # frame (holds the pin) / tray (pin turns in it)
PIN_DEPTH = 4.5

# notches: small for eye brushes, large for face brushes
NOTCH = {"S": dict(half=rad(22.5), depth=10.5, rr=0.9),
         "L": dict(half=rad(25.0), depth=15.0, rr=1.2)}
SLOTS = "SLSLSSLSLS"
GAP = 3.0

# ---------------------------------------------------------------- derived layout
UF = (HN - PZ) / math.cos(LEAN_F)                 # groove bottom along the front frame
Z_NB = HN + SPAN * math.tan(TILT)
UB = (Z_NB - PZ) / math.cos(LEAN_B)
_yf = 0.0
_ynf = _yf - UF * math.sin(LEAN_F)
_yb = _ynf + SPAN - UB * math.sin(LEAN_B)
_front_in = _ynf - 40.0                           # 40 mm of tray in front of the front notch
_back_in = max(_yf + UF + BAR_ABOVE + 2.0, _yb + 8.0)
D = (_back_in - _front_in) + 2 * WALL
_shift = -(_front_in + _back_in) / 2
YF, YB, YNF = _yf + _shift, _yb + _shift, _ynf + _shift
Y_FRONT_IN, Y_BACK_IN = _front_in + _shift, _back_in + _shift
TH_F = math.pi / 2 + LEAN_F      # deploy angle, front frame (from folded)
TH_B = math.pi / 2 + LEAN_B      # deploy angle, back frame
DIR = Vector((0, math.cos(TILT), math.sin(TILT)))     # along a brush, towards the handle
NRM = Vector((0, -math.sin(TILT), math.cos(TILT)))    # up, square to the brush
P0 = Vector((0, YNF, Z0 + HN))                         # large groove bottom at front frame


def slot_x():
    widths = [2 * NOTCH[k]["depth"] * math.tan(NOTCH[k]["half"]) for k in SLOTS]
    total = sum(widths) + GAP * (len(SLOTS) - 1)
    x, out = -total / 2, []
    for k, w in zip(SLOTS, widths):
        out.append((k, x + w / 2, w))
        x += w + GAP
    return out, total


# ---------------------------------------------------------------- poses
def pose_front(th):
    return Matrix.Translation((0, YF, Z0 + PZ)) @ Matrix.Rotation(th, 4, "X")


def pose_back(th):
    return (Matrix.Translation((0, YB, Z0 + PZ)) @ Matrix.Rotation(-th, 4, "X")
            @ Matrix.Rotation(math.pi, 4, "Z"))


# ---------------------------------------------------------------- mesh helpers
def prism_x(name, poly, x0, x1):
    """Extrude a polygon given in the local (u, w) plane along X; u->Y, w->Z."""
    bm = bmesh.new()
    a = [bm.verts.new((x0, u, w)) for u, w in poly]
    b = [bm.verts.new((x1, u, w)) for u, w in poly]
    n = len(poly)
    bm.faces.new(a[::-1])
    bm.faces.new(b)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return S._link(name, bm)


def prism_world(name, poly2d, origin, ax, ay, ext, s0, s1):
    """Polygon in (ax, ay) plane at origin, extruded along ext from s0 to s1."""
    bm = bmesh.new()
    a = [bm.verts.new(origin + ax * p + ay * q + ext * s0) for p, q in poly2d]
    b = [bm.verts.new(origin + ax * p + ay * q + ext * s1) for p, q in poly2d]
    n = len(poly2d)
    bm.faces.new(a[::-1])
    bm.faces.new(b)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return S._link(name, bm)


def clip(poly, a, b, c):
    """Keep the part of a convex polygon where a*u + b*w >= c."""
    out = []
    for i in range(len(poly)):
        p, q = poly[i], poly[(i + 1) % len(poly)]
        fp, fq = a * p[0] + b * p[1] - c, a * q[0] + b * q[1] - c
        if fp >= 0:
            out.append(p)
        if (fp >= 0) != (fq >= 0):
            t = fp / (fp - fq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out


def heel_profile(th_deploy):
    """Square leg end, trimmed so it clears the floor all the way from folded to
    deployed and lands flat on the floor exactly at the deploy angle (the stop)."""
    poly = [(-5.5, -T / 2), (3.0, -T / 2), (3.0, T / 2), (-5.5, T / 2)]
    n = 90
    for i in range(n + 1):
        th = th_deploy * i / n
        # local z of point (u, w) at angle th is u*sin(th) + w*cos(th); keep >= -PZ
        # 0.25 mm clearance while swinging, closing to contact over the last 6 degrees
        c = 0.25 * min(1.0, (th_deploy - th) / rad(6))
        poly = clip(poly, math.sin(th), math.cos(th), -PZ + c)
    return poly


def v_profile(k):
    """V-notch cross-section with a rounded bottom, apex at (0, 0), opening up (+q)."""
    nd = NOTCH[k]
    ph, rr, H = nd["half"], nd["rr"], 60.0
    c = rr / math.sin(ph)
    arc = []
    m = 10
    for i in range(m + 1):
        be = -(math.pi / 2 - ph) + (math.pi - 2 * ph) * i / m
        arc.append((rr * math.sin(be), c - rr * math.cos(be)))
    return [(-H * math.tan(ph), H)] + arc + [(H * math.tan(ph), H)]


# ---------------------------------------------------------------- parts
def frame(name, U, leg, bar_half, th_deploy, pin_side):
    """One fold-out frame in its local frame (u along the legs, w thickness)."""
    parts = []
    bar = S.box(name + "_bar", 2 * bar_half, BAR_BELOW + BAR_ABOVE, T,
                loc=(0, U + (BAR_ABOVE - BAR_BELOW) / 2, 0))
    parts.append(bar)
    heel = heel_profile(th_deploy)
    for sx in (-1, 1):
        x0, x1 = sorted((sx * leg[0], sx * leg[1]))
        lg = S.box(name + "_leg", leg[1] - leg[0], U - BAR_BELOW + 1.0, T,
                   loc=((x0 + x1) / 2, (U - BAR_BELOW + 1.0) / 2 + 1.5, 0))
        parts.append(lg)
        parts.append(prism_x(name + "_heel", heel, x0, x1))
    ob = parts[0]
    S.union(ob, parts[1:])
    # pin holes (blind, from the hinge side)
    cutters = []
    for sx in (-1, 1):
        face = leg[0] if pin_side == "in" else leg[1]
        into = 1 if pin_side == "in" else -1
        xc = sx * (face + into * PIN_DEPTH / 2)
        cutters.append(S.cylinder("pinhole", HOLE_TIGHT, PIN_DEPTH + 0.02, loc=(xc, 0, 0),
                                  rot=(0, math.pi / 2, 0), seg=24))
    # soften the bar's outer corners in plan (u-x plane)
    S.cut(ob, cutters)
    ob.name = name
    return ob


def notch_cutters():
    cs = []
    slots, _ = slot_x()
    for k, x, _w in slots:
        lift = NOTCH["L"]["depth"] - NOTCH[k]["depth"]   # small grooves sit higher
        org = P0 + NRM * lift + Vector((x, 0, 0))
        cs.append(prism_world("notch", v_profile(k), org, Vector((1, 0, 0)), NRM, DIR,
                              -60, 140))
    return cs


def tray():
    base = S.rounded_box("tray", L, D, H_TRAY, r=S.CORNER_R, r_top=S.EDGE_R)
    pocket = S.rounded_box("pocket", L - 2 * WALL, D - 2 * WALL, 50,
                           r=S.CORNER_R - WALL, loc=(0, 0, Z0))
    S.cut(base, [pocket])
    blocks = []
    for sx in (-1, 1):
        x0, x1 = sorted((sx * BLOCK[0], sx * BLOCK[1]))
        b = S.rounded_box("block", x1 - x0, 9.0, PZ + 3.0, r=1.5, r_top=0.8,
                          loc=((x0 + x1) / 2, YF, Z0 - 0.5))
        blocks.append(b)
    S.union(base, blocks)
    cut = []
    for sx in (-1, 1):
        # back hinge: through the end wall
        cut.append(S.cylinder("hole", HOLE_FREE, WALL + 2, loc=(sx * (XI + WALL / 2), YB, Z0 + PZ),
                              rot=(0, math.pi / 2, 0), seg=24))
        # front hinge: through the pivot block
        cut.append(S.cylinder("hole", HOLE_FREE, 7.0, loc=(sx * sum(BLOCK) / 2, YF, Z0 + PZ),
                              rot=(0, math.pi / 2, 0), seg=24))
    # finger holes under each folded bar: push up from below to lift a frame
    y_back_bar = YB - UB - (BAR_ABOVE - BAR_BELOW) / 2
    y_front_bar = YF + UF + (BAR_ABOVE - BAR_BELOW) / 2
    for y in (y_back_bar, y_front_bar):
        cut.append(S.slot("finger", 28, 13, 10, loc=(0, y, 0), axis="Z"))
    lab = mono_text("label", "BRUSH / 01", 3.6, 1.2, loc=(L / 2 - WALL - 34, Y_FRONT_IN + 7, Z0 - 0.4))
    cut.append(lab)
    S.cut(base, cut)
    return base


def mono_text(name, body, size, depth, loc):
    """Engraving cutter in JetBrains Mono (the family's label font)."""
    bpy.ops.object.text_add(location=loc)
    ob = bpy.context.active_object
    ob.name = name
    font = "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Medium.ttf"
    if os.path.exists(font):
        ob.data.font = bpy.data.fonts.load(font)
    ob.data.body = body
    ob.data.size = size
    ob.data.extrude = depth / 2
    ob.data.space_character = 1.1
    bpy.ops.object.convert(target="MESH")
    return ob


def _slot_z(name, w, h, depth, loc):
    return S.rounded_box(name, w, h, depth, r=min(w, h) / 2 - 1e-3, seg=16,
                         loc=(loc[0], loc[1], loc[2] - depth / 2))


S.slot = (lambda f: (lambda name, w, h, depth, loc, axis="Y", r=None:
                     _slot_z(name, w, h, depth, loc) if axis == "Z"
                     else f(name, w, h, depth, loc, axis, r)))(S.slot)


def pins():
    out = []
    for sx in (-1, 1):
        out.append(S.cylinder("pin_b", PIN_D, WALL + PIN_DEPTH,
                              loc=(sx * (XI + WALL - (WALL + PIN_DEPTH) / 2), YB, Z0 + PZ),
                              rot=(0, math.pi / 2, 0), seg=16))
        out.append(S.cylinder("pin_f", PIN_D, 5.0 + PIN_DEPTH,
                              loc=(sx * (BLOCK[0] + (5.0 + PIN_DEPTH) / 2), YF, Z0 + PZ),
                              rot=(0, math.pi / 2, 0), seg=16))
    return out


def apply_mods(ob):
    """Apply modifiers but keep the mesh in object-local space."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)


def build():
    S.reset()
    fr = frame("front_frame", UF, FRONT_LEG, FRONT_LEG[1], TH_F, "in")
    bk = frame("back_frame", UB, BACK_LEG, BACK_LEG[1], TH_B, "out")
    fr.matrix_world = pose_front(TH_F)
    bk.matrix_world = pose_back(TH_B)
    bpy.context.view_layer.update()
    for c in notch_cutters():
        for ob in (fr, bk):
            md = ob.modifiers.new("n", "BOOLEAN")
            md.operation, md.solver, md.object = "DIFFERENCE", "EXACT", c
        bpy.context.view_layer.update()
        apply_mods(fr)
        apply_mods(bk)
        bpy.data.objects.remove(c, do_unlink=True)
    tr = tray()
    return tr, fr, bk


# ---------------------------------------------------------------- props: brushes
def lathe(name, prof, seg=40):
    """Surface of revolution about Y from a list of (y, r) points (r=0 closes an end)."""
    bm = bmesh.new()
    rings = []
    for y, r in prof:
        if r < 1e-6:
            rings.append([bm.verts.new((0, y, 0))])
        else:
            rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / seg), y,
                                        r * math.sin(2 * math.pi * i / seg)))
                          for i in range(seg)])
    for a, b in zip(rings, rings[1:]):
        if len(a) == 1 and len(b) == 1:
            continue
        if len(a) == 1:
            for i in range(seg):
                bm.faces.new((a[0], b[(i + 1) % seg], b[i]))
        elif len(b) == 1:
            for i in range(seg):
                bm.faces.new((a[i], a[(i + 1) % seg], b[0]))
        else:
            for i in range(seg):
                j = (i + 1) % seg
                bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = S._link(name, bm)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def brush(name, hd, fd, flen, bd, blen, hlen, shape="dome"):
    """Brush along +Y from the ferrule's back end (y=0) towards the handle end.
    Bristles point -Y. Returns objects (handle, ferrule, bristles)."""
    r = hd / 2
    hp = [(0, 0)]
    for i in range(13):
        t = i / 12
        k = 1.0 - 0.30 * max(0.0, (t - 0.5) / 0.5) ** 1.3
        hp.append((t * hlen, r * k))
    hp.append((hlen + 0.8, r * 0.55))
    hp.append((hlen + 1.0, 0))
    h = lathe(name + "_h", hp)
    fp = [(0.5, 0), (0.5, r * 1.02)]
    for i in range(9):
        t = i / 8
        fp.append((-t * flen, r * 1.02 + (fd / 2 - r * 1.02) * min(1, t * 1.4)))
    fp.append((-flen, 0))
    f = lathe(name + "_f", fp)
    bp = [(-flen + 0.5, 0)]
    for i in range(17):
        t = i / 16
        if shape == "dome":
            rr = bd / 2 * (0.62 + 0.38 * min(1, t * 2.2)) if t < 0.62 else \
                bd / 2 * math.sqrt(max(0.0, 1 - ((t - 0.62) / 0.38) ** 2))
        else:
            rr = bd / 2 * (1 - 0.8 * t ** 1.6)
        bp.append((-flen - t * blen, max(rr, 0.05)))
    bp.append((-flen - blen, 0))
    b = lathe(name + "_b", bp)
    return [h, f, b]


def place_brush(objs, k, x, s_back, hd):
    """Lay a brush in slot k at x; s_back = ferrule back end along DIR from the front
    groove point (negative = ahead of the front frame)."""
    half = NOTCH[k]["half"]
    lift = NOTCH["L"]["depth"] - NOTCH[k]["depth"]
    centre = P0 + NRM * (lift + (hd / 2) / math.sin(half)) + Vector((x, 0, 0)) + DIR * s_back
    rot = Matrix.Rotation(TILT, 4, "X")
    M = Matrix.Translation(centre) @ rot
    for o in objs:
        o.matrix_world = M @ o.matrix_world


def brush_set():
    """A believable set: eye brushes in the small slots, face brushes in the large."""
    slots, _ = slot_x()
    small = [  # hd, fd, flen, bd, blen, hlen, shape
        (7.0, 6.5, 16, 7, 12, 118, "eye"), (6.5, 6.0, 15, 9, 10, 112, "dome"),
        (7.5, 7.0, 17, 8, 14, 120, "eye"), (7.0, 6.5, 16, 10, 11, 116, "dome"),
        (6.5, 6.0, 15, 7, 13, 110, "eye"), (7.0, 7.0, 16, 9, 12, 118, "dome")]
    large = [(12.0, 15, 24, 27, 34, 128, "dome"), (11.0, 14, 22, 22, 28, 124, "dome"),
             (12.5, 16, 24, 26, 32, 130, "dome"), (11.0, 13, 22, 20, 26, 122, "dome")]
    out = []
    si = li = 0
    for i, (k, x, _w) in enumerate(slots):
        if k == "S":
            p = small[si]
            si += 1
            s_back = 10.0          # eye brushes sit further back: heads just ahead of the frame
        else:
            p = large[li]
            li += 1
            s_back = -4.0          # face brushes sit forward so heads clear the eye brushes
        objs = brush(f"brush{i}", *p)
        place_brush(objs, k, x, s_back, p[0])
        out.append(objs)
    return out


# ---------------------------------------------------------------- checks
def bvh(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    bm.from_object(ob, dg)
    bm.transform(ob.matrix_world)
    t = BVHTree.FromBMesh(bm)
    bm.free()
    return t


def check(tr, fr, bk):
    """Sweep both frames through their fold and report any collisions."""
    report = []

    def hits(a, b):
        return len(bvh(a).overlap(bvh(b)))

    def at(mf, mb):
        fr.matrix_world, bk.matrix_world = mf, mb
        bpy.context.view_layer.update()

    # unfolding order: back frame up first (front lying folded), then front frame
    for i in range(0, 23):
        th = (TH_B - rad(1)) * i / 22
        at(pose_front(0), pose_back(th))
        report.append(("back unfolds", round(math.degrees(th)), hits(bk, tr), hits(bk, fr)))
    for i in range(0, 21):
        th = (TH_F - rad(1)) * i / 20
        at(pose_front(th), pose_back(TH_B))
        report.append(("front unfolds", round(math.degrees(th)), hits(fr, tr), hits(fr, bk)))
    at(pose_front(TH_F), pose_back(TH_B))
    bad = [r for r in report if r[2] or r[3]]
    print("sweep steps:", len(report), "collisions:", len(bad))
    for r in bad:
        print("  ", r)
    return bad


def layout_report():
    slots, total = slot_x()
    print(f"tray {L:.1f} x {D:.1f} x {H_TRAY:.1f} mm (folded)")
    print(f"front hinge y={YF:.1f}, back hinge y={YB:.1f}, front groove y={YNF:.1f}")
    print(f"UF={UF:.1f} UB={UB:.1f}  frame lengths {UF + BAR_ABOVE:.1f} / {UB + BAR_ABOVE:.1f}")
    top_b = Z0 + PZ + (UB + BAR_ABOVE) * math.cos(LEAN_B)
    top_f = Z0 + PZ + (UF + BAR_ABOVE) * math.cos(LEAN_F)
    print(f"open height: back {top_b:.1f}, front {top_f:.1f}")
    print(f"slots {SLOTS}: span {total:.1f} mm, x = " + ", ".join(f"{x:.1f}" for _k, x, _w in slots))
    print(f"heel: {[(round(u, 2), round(w, 2)) for u, w in heel_profile(TH_F)]}")


# ---------------------------------------------------------------- main
def main():
    args = sys.argv[1:]
    layout_report()
    tr, fr, bk = build()
    if "--check" in args:
        check(tr, fr, bk)
    # STL in print orientation: frames lying flat, w = up
    os.makedirs(os.path.join(HERE, "stl"), exist_ok=True)

    def export_flat(ob, path):
        tmp = ob.copy()
        tmp.data = ob.data.copy()
        bpy.context.collection.objects.link(tmp)
        tmp.matrix_world = Matrix.Translation((0, 0, T / 2))
        S.export_stl(tmp, path)
        bpy.data.objects.remove(tmp, do_unlink=True)

    S.export_stl(tr, os.path.join(HERE, "stl", "brushrack_tray_white.stl"))
    export_flat(fr, os.path.join(HERE, "stl", "brushrack_frontframe_black.stl"))
    export_flat(bk, os.path.join(HERE, "stl", "brushrack_backframe_black.stl"))

    S.assign(tr, S.pla("white"))
    S.assign(fr, S.pla("black"))
    S.assign(bk, S.pla("black"))
    pn = pins()
    fil = S.material("Filament pin", (0.55, 0.55, 0.53, 1), rough=0.4)
    for p in pn:
        S.assign(p, fil)
    for o in (tr, fr, bk):
        S.smooth(o, 35)

    brushes = brush_set()
    handle_m = S.material("Brush handle", (0.012, 0.011, 0.011, 1), rough=0.35, coat=0.3)
    ferrule_m = S.material("Brush ferrule", (0.75, 0.62, 0.50, 1), rough=0.28)
    ferrule_m.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 1.0
    bristle_m = S.material("Bristles", (0.32, 0.24, 0.18, 1), rough=0.85)
    flat = []
    for h, f, b in brushes:
        S.assign(h, handle_m)
        S.assign(f, ferrule_m)
        S.assign(b, bristle_m)
        flat += [h, f, b]

    root = S.to_studio([tr, fr, bk] + pn + flat)
    S.studio(samples=80)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "brush_rack.blend"))
    out = os.path.join(HERE, "renders")
    sc = bpy.context.scene
    if "--preview" in args:
        out = os.path.join(HERE, "renders", "_preview")
        sc.cycles.samples = 16
        sc.render.resolution_x, sc.render.resolution_y = 800, 600
    os.makedirs(out, exist_ok=True)
    m = 0.001

    def show(objs, on):
        for o in objs:
            o.hide_render = not on

    def setpose(th_f, th_b):
        fr.matrix_parent_inverse.identity()
        bk.matrix_parent_inverse.identity()
        fr.matrix_basis = pose_front(th_f)
        bk.matrix_basis = pose_back(th_b)
        bpy.context.view_layer.update()

    for o in (fr, bk):
        o.parent = root
        o.matrix_parent_inverse.identity()
    setpose(TH_F, TH_B)

    if "--renders" in args:
        show(flat, True)
        S.camera((0.30, -0.36, 0.25), target=(0, 0.005, 0.030), lens=70)
        S.render(os.path.join(out, "br_hero.png"))
        show(flat, False)
        S.camera((0.30, -0.36, 0.25), target=(0, 0.005, 0.030), lens=70)
        S.render(os.path.join(out, "br_open.png"))
        S.camera((0.40, 0.02, 0.07), target=(0, 0.0, 0.032), lens=75)
        show(flat, True)
        S.render(os.path.join(out, "br_side.png"))
        show(flat, False)
        setpose(0, 0)
        S.camera((0.26, -0.33, 0.24), target=(0, 0, 0.004), lens=75)
        S.render(os.path.join(out, "br_folded.png"))
        setpose(0, TH_B * 0.55)
        S.render(os.path.join(out, "br_unfold_1.png"))
        setpose(TH_F * 0.5, TH_B)
        S.render(os.path.join(out, "br_unfold_2.png"))
        setpose(TH_F, TH_B)
        show(flat, True)
        S.camera((0.06, -0.12, 0.55), target=(0, 0.0, 0.02), lens=70)
        S.render(os.path.join(out, "br_top.png"))
        show(flat, False)
        setpose(0, 0)
        root.rotation_euler = (math.pi, 0, 0)
        root.location = (0, 0, H_TRAY * m)
        S.camera((0.22, -0.30, 0.20), target=(0, 0, 0.004), lens=70)
        S.render(os.path.join(out, "br_underside.png"))
        root.rotation_euler = (0, 0, 0)
        root.location = (0, 0, 0)
        setpose(TH_F, TH_B)

    if "--details" in args:
        res0 = (sc.render.resolution_x, sc.render.resolution_y)
        if "--preview" not in args:
            sc.render.resolution_x, sc.render.resolution_y = 1400, 1050
        show(flat, True)
        slots, _ = slot_x()
        x_l = slots[1][1]
        S.camera(((x_l - 30) * m, (YNF - 75) * m, 0.085),
                 target=(x_l * m, YNF * m, (Z0 + HN) * m), lens=90)
        S.render(os.path.join(out, "d_notches.png"))
        show(flat, False)
        xh = L / 2
        S.camera(((xh + 45) * m, (YF - 60) * m, 0.045), target=((xh - 10) * m, YF * m, 0.008),
                 lens=85)
        S.render(os.path.join(out, "d_hinge.png"))
        S.camera((0.075, (Y_FRONT_IN - 70) * m, 0.085),
                 target=((L / 2 - 20) * m, (Y_FRONT_IN + 8) * m, Z0 * m), lens=100)
        S.render(os.path.join(out, "d_label.png"))
        setpose(0, 0)
        S.camera((0.13, -0.11, 0.035), target=(0.07, -0.03, 0.004), lens=80)
        S.render(os.path.join(out, "d_folded_edge.png"))
        setpose(TH_F, TH_B)
        sc.render.resolution_x, sc.render.resolution_y = res0

    if "--drawings" in args:
        import json
        show(flat, False)
        for p in pn:
            p.hide_render = True
        S.drawing_setup()
        grey = S.material("Drawing grey", (0.86, 0.86, 0.86, 1), rough=0.9)
        sc.view_layers[0].material_override = grey
        meta = {}
        views = [("open_side", "right", (0, 0, 40), 0.200, (TH_F, TH_B)),
                 ("open_front", "front", (0, 0, 40), 0.200, (TH_F, TH_B)),
                 ("folded_top", "top", (0, 0, 0), 0.235, (0, 0)),
                 ("folded_side", "right", (0, 0, 4.3), 0.140, (0, 0))]
        for name, v, c, scale, (a, b) in views:
            setpose(a, b)
            S.ortho_camera(v, tuple(k * m for k in c), scale)
            S.render(os.path.join(out, f"dwg_{name}.png"))
            meta[name] = {"view": v, "center_mm": c, "scale_mm": scale * 1000,
                          "res": [sc.render.resolution_x, sc.render.resolution_y]}
        with open(os.path.join(out, "dwg_cameras.json"), "w") as f:
            json.dump(meta, f, indent=1)
        slots, _ = slot_x()
        dims = {"rev": REV, "L": L, "D": D, "H_TRAY": H_TRAY, "Z0": Z0, "PZ": PZ,
                "YF": YF, "YB": YB, "YNF": YNF, "HN": HN, "SPAN": SPAN,
                "TILT": math.degrees(TILT), "LEAN_F": math.degrees(LEAN_F),
                "LEAN_B": math.degrees(LEAN_B), "UF": UF, "UB": UB,
                "BAR_ABOVE": BAR_ABOVE, "BAR_BELOW": BAR_BELOW,
                "Y_FRONT_IN": Y_FRONT_IN, "Y_BACK_IN": Y_BACK_IN,
                "slots": [{"k": k, "x": x, "w": w, "depth": NOTCH[k]["depth"],
                           "angle": 2 * math.degrees(NOTCH[k]["half"])} for k, x, w in slots]}
        with open(os.path.join(out, "dims.json"), "w") as f:
            json.dump(dims, f, indent=1)


if __name__ == "__main__":
    main()
