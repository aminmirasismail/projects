"""Tote-bag hook that hangs on 3M CLAW 15 lb drywall picture hangers. Rev C.

Run inside Blender:
  blender --background --factory-startup --python bag_hook.py -- [--renders] [--details]
                                                                  [--views] [--preview]
Writes bag_hook_white.3mf, fittest_white.3mf, stl/, renders/ and renders/dims.json.

Coordinates (mm): X along the wall, Y = -(distance out from the wall), Z up. The wall is the
plane Y = 0 and the part sits in Y < 0. `u` below means distance out from the wall (u = -Y).

How it hangs
  The CLAW is a 23 x 23 mm stainless plate, ~0.9 mm thick, pushed flat onto drywall. A tab
  struck from the middle of the plate is hinged at its bottom and leans outward, so it makes a
  V that opens upward (that's where picture wire or a D-ring drops in). On the back of this
  hook a tongue (1.2 mm at the tip) runs across the full width, 0.34 mm in front of the plate. Lift the hook,
  slide it down the wall and the tongue drops into each CLAW's V. The bag load pushes the
  tongue down into the V; the tab stops the top of the hook pulling away from the wall.

Printing: upright, as it hangs (bottom face on the plate), no supports.
  - Pegs rise at 45 degrees, so their undersides are 45-degree overhangs.
  - The tongue hangs down inside a back pocket. Its bottom edge is bridged in 17 mm spans
    between ribs; a CLAW tab sits in any of the five bays between the ribs.
  - Bottom plan corners are square and sit flat on the bed; the top corners are R10 arcs.
  - Print with a 4 mm brim: it stands 70 mm tall on a 12 mm wide footprint on a bed-slinger.
"""
import json
import math
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import studio as S  # noqa: E402

REV = "C"

# ---------------------------------------------------------------- body
W, H, T = 120.0, 70.0, 14.0     # width along the wall, height, thickness off the wall
R = S.CORNER_R                  # 10 mm plan-view (front-view) corners
EDGE = S.EDGE_R                 # 1.2 mm round on every front and back rim

# ---------------------------------------------------------------- pegs
PEG_D = 14.0
PEG_ANGLE = 45.0                # above horizontal; also the overhang limit when printed upright
PEG_L = 60.0                    # along the axis, from the front face to the end face (rev A: 48)
PEG_Z = 20.0                    # axis height where it leaves the front face
PEG_X = (W / 2 - 30, W / 2 + 30)
PEG_EMBED = 8.0                 # >= r tan 45 = 7, so the start cap is fully inside the body
PEG_END_R = 3.0                 # end-face round: handles slide off it instead of snagging

# ---------------------------------------------------------------- CLAW interface
CLAW_W, CLAW_H, CLAW_T = 23.0, 23.0, 0.9   # 3M: 0.9 in square; plate ~0.034 in (0.86 mm)
TAB_W, TAB_H, TAB_ANG = 7.0, 9.0, 28.0     # estimated from 3M's drawings; checked by the fit test
TAB_HINGE = 11.0                           # tab hinge height above the plate's bottom edge
BACK_GAP = 1.2                  # tongue's back face: plate (0.86 by 3M) + 0.34 for paint, dishing
TONGUE_T = 1.2                  # at the tip: 2 wall lines + gap fill (>= 0.5 mm rule)
TONGUE_ROOT_T = 2.2             # front face drafts out to this at the root: ~3x less root stress
TIP_T, TIP_TAPER = 0.5, 2.5     # front face tapers to a 0.5 mm edge over the bottom 2.5 mm, so the
                                # tip seats deeper in the V: owner wants ~5 mm lift to release
FIN_W, FIN_GAP, FIN_END = 0.6, 0.16, 0.6   # breakaway fin under the tip: 0.6 wide, top 2 layers
                                # (0.16) below the tip, 0.6 clear of the ribs; snap out after print
TONGUE_BOT, TONGUE_TOP = 53.0, 60.0   # tongue tip and root heights
RECESS = (29.0, 66.0)           # back recess (u < BACK_GAP) where the plates sit
RECESS_X = (3.0, W - 3.0)
POCKET_FLOOR = 31.0             # bays: tab space; floor above the peg roots so they sit on solid
POCKET_U = 9.0                  # bays reach 9 mm into the 14 mm body (5 mm front wall left)
RIB_W = 3.0
RIBS = (30.0, 50.0, 70.0, 90.0)
BAY_ENDS = (11.5, W - 11.5)
# Above the hinge the plate has a hole where the tab was punched out, so the V runs from the
# plate's edges (u = 0.9) to the tab's back face (u = h tan TAB_ANG). The tongue's front face
# (u = 2.4 at the tip) seats where the tab has leaned out that far: h = 2.4 / tan 28 = 4.5 mm.
TAB_TOP = TAB_H * math.cos(math.radians(TAB_ANG))          # tab top above its hinge: 7.95
TIP_IN_V = (BACK_GAP + TIP_T) / math.tan(math.radians(TAB_ANG))   # 3.2: tip seat above the hinge
RELEASE_LIFT = TAB_TOP - TIP_IN_V                                 # ~4.8 mm to lift it off (est.)
LIFT = 7.0                      # lift the hook this much to drop it on (needs ~4)

# ---------------------------------------------------------------- label
LABEL = ("HOOK", "01")          # engraved HOOK · 01 (house dot separator)
LABEL_SIZE, ENGRAVE = 6.0, 0.6
LABEL_Z = 54.0                  # centre height on the front face, between the pegs
CLEAR = 1.0                     # text stays this far from any fillet tangent line

M = 0.001


def bays():
    edges = [BAY_ENDS[0]] + [v for r in RIBS for v in (r - RIB_W / 2, r + RIB_W / 2)] + [BAY_ENDS[1]]
    return [(edges[i], edges[i + 1]) for i in range(0, len(edges), 2)]


def claw_z(bay_tip=TONGUE_BOT):
    """CLAW plate bottom/top and tab hinge heights (part coordinates) when hung."""
    hinge = bay_tip - TIP_IN_V
    bottom = hinge - TAB_HINGE
    return bottom, bottom + CLAW_H, hinge


# ---------------------------------------------------------------- 2D helpers
def arc(c, r, a0, a1, n=None):
    n = n or S.arc_segments(r, abs(a1 - a0))
    return [(c[0] + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             c[1] + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def front_outline():
    """Front-view outline in (x, z), counter-clockwise seen from the front.
    Top corners are R10 arcs. Bottom corners are square (the owner's call): they sit flat on
    the bed, so nothing overhangs on the first layers."""
    pts = [(0.0, 0.0), (W, 0.0)]
    pts += arc((W - R, H - R), R, 0, 90)               # top corners: full R10 arcs
    pts += arc((R, H - R), R, 90, 180)
    out = []
    for p in pts:                                      # drop duplicates
        if not out or (abs(out[-1][0] - p[0]) > 1e-6 or abs(out[-1][1] - p[1]) > 1e-6):
            out.append(p)
    return out


# ---------------------------------------------------------------- mesh builders
def _prism(name, pts, to3d, a0, a1, rim=0.0):
    """Extrude a convex-or-concave 2D polygon between a0 and a1; to3d(p, a) -> (x, y, z)."""
    bm = bmesh.new()
    lo = [bm.verts.new(to3d(p, a0)) for p in pts]
    hi = [bm.verts.new(to3d(p, a1)) for p in pts]
    f0 = bm.faces.new(lo[::-1])
    f1 = bm.faces.new(hi)
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if rim > 0:
        caps = {f0, f1}
        edges = [e for e in bm.edges if any(f in caps for f in e.link_faces)]
        bmesh.ops.bevel(bm, geom=edges, offset=rim, segments=S.arc_segments(rim),
                        profile=0.5, affect="EDGES")
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    return S._link(name, bm)


def body():
    """Front-view outline extruded from the wall (u = 0) to the front face (u = T)."""
    return _prism("Hook", front_outline(), lambda p, a: (p[0], -a, p[1]), 0.0, T, rim=EDGE)


def peg(x):
    """Ø14 peg rising at PEG_ANGLE, flat end with a PEG_END_R round, axis from inside the body.
    Printed upright, the end round's normals stay within 45 degrees of horizontal."""
    bm = bmesh.new()
    seg = S.arc_segments(PEG_D / 2, 360, minimum=48)
    length = PEG_L + PEG_EMBED
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=PEG_D / 2,
                          radius2=PEG_D / 2, depth=length)
    for v in bm.verts:
        v.co.z += length / 2
    tip = [e for e in bm.edges if all(abs(v.co.z - length) < 1e-6 for v in e.verts)
           and len(e.link_faces) == 2 and any(abs(f.normal.z) < 0.5 for f in e.link_faces)]
    bmesh.ops.bevel(bm, geom=tip, offset=PEG_END_R, segments=S.arc_segments(PEG_END_R), profile=0.5,
                    affect="EDGES")
    a = math.radians(PEG_ANGLE)
    # rotating by t about X sends +Z to (0, -sin t, cos t); with t = 90 - a that is
    # (0, -cos a, sin a): out of the wall (-Y) and up, PEG_ANGLE above horizontal
    rot = Matrix.Rotation(math.pi / 2 - a, 4, "X")
    d = Vector((0, -math.cos(a), math.sin(a)))
    start = Vector((x, -T, PEG_Z)) - d * PEG_EMBED
    bmesh.ops.transform(bm, matrix=Matrix.Translation(start) @ rot, verts=bm.verts)
    ob = S._link(f"Peg {x:.0f}", bm)
    return ob


def pocket_cutters():
    """Back recess for the CLAW plates plus five bays (tab space) separated by ribs."""
    cut = []
    rec = [(-1.0, RECESS[0]), (BACK_GAP, RECESS[0]), (BACK_GAP, RECESS[1]), (-1.0, RECESS[1])]
    to3d = lambda p, a: (a, -p[0], p[1])  # noqa: E731
    cut.append(_prism("recess", rec, to3d, *RECESS_X))
    # bay profile (u, z): starts 0.2 mm inside the recess so faces never coincide
    bay = [(BACK_GAP - 0.2, POCKET_FLOOR), (POCKET_U, POCKET_FLOOR), (POCKET_U, TONGUE_TOP),
           (BACK_GAP + TONGUE_ROOT_T, TONGUE_TOP), (BACK_GAP + TONGUE_T, TONGUE_BOT + TIP_TAPER),
           (BACK_GAP + TIP_T, TONGUE_BOT),
           (BACK_GAP - 0.2, TONGUE_BOT)]
    for i, (x0, x1) in enumerate(bays()):
        cut.append(_prism(f"bay{i}", bay, to3d, x0, x1))
    return cut


def fins():
    """Breakaway fins: one per bay, standing on the bay floor under the tongue tip, stopping
    FIN_GAP short of it. The tip prints onto them instead of sagging across the 17 mm span."""
    out = []
    for i, (x0, x1) in enumerate(bays()):
        h = TONGUE_BOT - FIN_GAP - POCKET_FLOOR + 0.05      # 0.05 into the floor so it welds
        out.append(S.box(f"fin{i}", x1 - x0 - 2 * FIN_END, FIN_W, h,
                         loc=((x0 + x1) / 2, -(BACK_GAP + FIN_W / 2), POCKET_FLOOR - 0.05 + h / 2)))
    return out


def front_label():
    """HOOK · 01 engraved on the front face, centred between the pegs."""
    ob = S.product_label("label", LABEL, LABEL_SIZE, 2 * ENGRAVE, sep="dot", slant=1.0)
    for v in ob.data.vertices:          # XY text, +z out of the face -> front face (-Y), +y up
        x, y, z = v.co
        v.co = (x, -T - z, y)
    vs = [v.co for v in ob.data.vertices]
    bx = (min(v.x for v in vs), max(v.x for v in vs))
    bz = (min(v.z for v in vs), max(v.z for v in vs))
    dx, dz = W / 2 - sum(bx) / 2, LABEL_Z - sum(bz) / 2
    for v in ob.data.vertices:
        v.co.x += dx
        v.co.z += dz
    ob.data.update()
    # the slant moves the deep end of each glyph down; the face outline is what we check
    face = [v.co for v in ob.data.vertices if abs(v.co.y + T + ENGRAVE) < 0.05]
    box = (min(v.x for v in face), min(v.z for v in face),
           max(v.x for v in face), max(v.z for v in face))
    # flat front face: inside the plan-corner tangents and the rim round; clear of the pegs
    flat = (R, EDGE, W - R, H - EDGE)
    assert (box[0] >= flat[0] + CLEAR and box[2] <= flat[2] - CLEAR
            and box[1] >= flat[1] + CLEAR and box[3] <= flat[3] - CLEAR), \
        f"label {box} not {CLEAR} mm inside flat face {flat}"
    for px in PEG_X:                    # peg roots are ellipses PEG_D wide
        assert box[2] < px - PEG_D / 2 - 3 or box[0] > px + PEG_D / 2 + 3, "label hits a peg"
    return ob, box


def check(ob, size=None):
    d = S.dims(ob)
    v = S.volume(ob)
    assert v > 0, f"{ob.name}: volume {v}"
    if size:
        assert all(abs(a - b) < 0.05 for a, b in zip(d, size)), f"{ob.name}: {d} vs {size}"
    return d, v


def build():
    hook = body()
    check(hook, (W, T, H))
    S.union(hook, [peg(x) for x in PEG_X])
    S.cut(hook, pocket_cutters())
    S.union(hook, fins())
    hook.name = "Hook"
    fit = hook.copy()
    fit.data = hook.data.copy()
    bpy.context.collection.objects.link(fit)
    lab, box = front_label()
    S.cut(hook, lab)
    return hook, fit, box


def fit_test(fit):
    """30 mm slice through the middle bay (x 45..75), z 20..70: the full CLAW interface."""
    keep = S.box("keep", 30, T + 2, H - 20, loc=(W / 2, -T / 2, 20 + (H - 20) / 2))
    md = fit.modifiers.new("k", "BOOLEAN")
    md.operation, md.solver, md.object = "INTERSECT", "EXACT", keep
    S.bake(fit)
    bpy.data.objects.remove(keep, do_unlink=True)
    fit.name = "Fit test"
    return fit


# ---------------------------------------------------------------- export
def write_3mf(ob, path, bed=(180.0, 180.0), rot=None):
    """One object centred on the A1 Mini plate, sitting on z = 0. Blender's loop triangles
    (a hand-written fan folds concave faces)."""
    me = ob.data
    mat = rot or Matrix.Identity(3)
    vs = [mat @ v.co for v in me.vertices]
    lo = [min(v[i] for v in vs) for i in range(3)]
    hi = [max(v[i] for v in vs) for i in range(3)]
    off = (bed[0] / 2 - (lo[0] + hi[0]) / 2, bed[1] / 2 - (lo[1] + hi[1]) / 2, -lo[2])
    me.calc_loop_triangles()
    vx = "".join(f'<vertex x="{v[0] + off[0]:.5f}" y="{v[1] + off[1]:.5f}" z="{v[2] + off[2]:.5f}"/>'
                 for v in vs)
    tx = "".join(f'<triangle v1="{t.vertices[0]}" v2="{t.vertices[1]}" v3="{t.vertices[2]}"/>'
                 for t in me.loop_triangles)
    model = ('<?xml version="1.0" encoding="UTF-8"?>\n'
             '<model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
             f'<resources><object id="1" name="{ob.name}" type="model"><mesh>'
             f'<vertices>{vx}</vertices><triangles>{tx}</triangles></mesh></object></resources>'
             '<build><item objectid="1"/></build></model>')
    ct = ('<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/'
          'package/2006/content-types"><Default Extension="rels" ContentType="application/'
          'vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" '
          'ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.'
            'openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.'
            'model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/'
            '3dmodel"/></Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", model)


def write_dims_json(out, box, hook, fit):
    bottom, top, hinge = claw_z()
    data = {"rev": REV, "W": W, "H": H, "T": T, "R": R, "edge": EDGE,
            "peg": {"end_r": PEG_END_R, "d": PEG_D, "angle": PEG_ANGLE, "len": PEG_L, "z": PEG_Z, "x": PEG_X},
            "claw": {"w": CLAW_W, "h": CLAW_H, "t": CLAW_T, "tab_w": TAB_W, "tab_h": TAB_H,
                     "tab_ang": TAB_ANG, "tab_hinge": TAB_HINGE, "plate_bottom_z": bottom,
                     "plate_top_z": top, "hinge_z": hinge},
            "tongue": {"tip_t": TIP_T, "taper": TIP_TAPER, "release_lift": RELEASE_LIFT, "fin_w": FIN_W, "fin_gap": FIN_GAP, "t": TONGUE_T, "root_t": TONGUE_ROOT_T, "back_gap": BACK_GAP, "bot": TONGUE_BOT, "top": TONGUE_TOP},
            "recess": RECESS, "recess_x": RECESS_X, "floor": POCKET_FLOOR, "pocket_u": POCKET_U,
            "ribs": RIBS, "rib_w": RIB_W, "bays": bays(), "lift": LIFT,
            "label": " · ".join(LABEL), "label_box": box, "label_z": LABEL_Z,
            "hook_dims": S.dims(hook), "hook_volume": S.volume(hook),
            "fit_dims": S.dims(fit), "fit_volume": S.volume(fit)}
    with open(os.path.join(out, "dims.json"), "w") as f:
        json.dump(data, f, indent=1)
    return data


# ---------------------------------------------------------------- scene props
def claw_mock(xc):
    """3M CLAW stand-in: plate on the wall, tab hinged at TAB_HINGE leaning out TAB_ANG."""
    bottom, top, hinge = claw_z()
    plate = S.box("CLAW plate", CLAW_W, CLAW_T, CLAW_H, loc=(xc, -CLAW_T / 2, bottom + CLAW_H / 2))
    hole = S.box("tab hole", TAB_W + 2, CLAW_T + 2, TAB_H + 1,
                 loc=(xc, -CLAW_T / 2, hinge + (TAB_H + 1) / 2))
    S.cut(plate, hole)
    a = math.radians(TAB_ANG)
    tab = S.box("CLAW tab", TAB_W, CLAW_T, TAB_H, loc=(0, -CLAW_T / 2, TAB_H / 2))
    # rotation about X by +a tips +Z towards -Y (out of the wall)
    tab.data.transform(Matrix.Translation((xc, 0, hinge)) @ Matrix.Rotation(a, 4, "X"))
    S.union(plate, tab)        # one closed solid (not a join), so section booleans keep the tab
    plate.name = f"CLAW {xc:.0f}"
    return plate


def strap(x, u, z_axis, width, color, name):
    """A tote handle hanging over a peg: two legs and a curve over the top, in the plane
    y = -u (a loop around the peg's elliptical section there)."""
    rx, rz = PEG_D / 2 + 1.2, PEG_D / 2 / math.cos(math.radians(PEG_ANGLE)) + 1.2
    pts = [(x - rx - 3, z_axis - 260)]
    pts += [(x + rx * math.cos(math.radians(t)), z_axis + rz * math.sin(math.radians(t)))
            for t in range(180, -1, -6)]
    pts += [(x + rx + 3, z_axis - 260)]
    # ribbon: the strap's width runs along the peg axis, so the loop stays wrapped round it
    a = math.radians(PEG_ANGLE)
    d = Vector((0, -math.cos(a), math.sin(a)))
    bm = bmesh.new()
    rows = [[bm.verts.new(Vector((px, -u, pz)) + d * s) for px, pz in pts]
            for s in (-width / 2, width / 2)]
    for i in range(len(pts) - 1):
        bm.faces.new((rows[0][i], rows[0][i + 1], rows[1][i + 1], rows[1][i]))
    ob = S._link(name, bm)
    md = ob.modifiers.new("t", "SOLIDIFY")
    md.thickness = 1.6
    S.assign(ob, S.material(f"strap {name}", color, rough=0.85))
    return ob


def wall():
    ob = S.box("Wall", 900, 30, 600, loc=(W / 2, 15, 120))
    S.assign(ob, S.material("Drywall", (0.035, 0.035, 0.037, 1), rough=0.95))
    return ob


# ---------------------------------------------------------------- main
def args():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def main():
    a = args()
    S.reset()
    hook, fit, box = build()
    fit = fit_test(fit)
    print("hook", S.dims(hook), round(S.volume(hook)), "fit", S.dims(fit), round(S.volume(fit)))
    os.makedirs(os.path.join(HERE, "stl"), exist_ok=True)
    S.export_stl(hook, os.path.join(HERE, "stl", "bag_hook_white.stl"))
    S.export_stl(fit, os.path.join(HERE, "stl", "bag_hook_fittest_white.stl"))
    # print upright as it hangs, turned 90 degrees so the 120 mm length runs along the bed's
    # Y travel: with 60 mm pegs the centre of mass sits over the front edge of the 12 mm
    # footprint, so the bed's front-back moves must push along the part, not across it.
    # The wall face points -X; seam_position=back puts the seam on the right end face.
    write_3mf(hook, os.path.join(HERE, "bag_hook_white.3mf"),
              rot=Matrix.Rotation(math.pi / 2, 3, "Z"))
    write_3mf(fit, os.path.join(HERE, "fittest_white.3mf"))

    out = os.path.join(HERE, "renders")
    if "--preview" in a:
        out = os.path.join(HERE, "renders", "_preview")
    os.makedirs(out, exist_ok=True)
    write_dims_json(out, box, hook, fit)

    S.assign(hook, S.pla("white"))
    S.assign(fit, S.pla("white"))
    S.smooth(hook, 40)
    S.smooth(fit, 40)
    fit.hide_render = True
    claws = [claw_mock(x) for x in (20.0, 100.0)]
    steel = S.material("Steel", (0.55, 0.56, 0.58, 1), rough=0.35)
    steel.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 1.0
    for c in claws:
        S.assign(c, steel)
    wl = wall()
    z0 = 70.0                       # hook bottom above the studio floor
    root = S.to_studio([hook, fit, wl] + claws)
    root.location = (-W / 2 * M, 0, z0 * M)
    S.studio()
    sc = bpy.context.scene
    if "--preview" in a:
        sc.cycles.samples = 16
        sc.render.resolution_x, sc.render.resolution_y = 800, 600

    def P(x, y, z):                 # model mm -> world m
        return ((x - W / 2) * M, y * M, (z + z0) * M)

    if "--renders" in a:
        S.camera(P(-120, -330, 190), target=P(W / 2, -20, 38), lens=70)
        S.render(os.path.join(out, "hook_hero.png"))
        S.camera(P(W / 2, -420, 40), target=P(W / 2, -10, 38), lens=70)
        S.render(os.path.join(out, "hook_front.png"))
        S.camera(P(330, -230, 60), target=P(W / 2, -24, 36), lens=70)
        S.render(os.path.join(out, "hook_side.png"))
        # in use: four tote handles, two per peg
        cols = [(0.42, 0.31, 0.18, 1), (0.02, 0.03, 0.07, 1), (0.36, 0.02, 0.02, 1),
                (0.42, 0.31, 0.18, 1)]
        straps = []
        a_ = math.radians(PEG_ANGLE)
        for i, (px, us) in enumerate(((PEG_X[0], (31.0, 50.0)), (PEG_X[1], (31.0, 50.0)))):
            for j, u in enumerate(us):
                zx = PEG_Z + (u - T) * math.tan(a_)
                s = strap(px, u, zx, 26.0, cols[2 * i + j], f"strap{i}{j}")
                s.parent = root
                straps.append(s)
        S.camera(P(-160, -420, 160), target=P(W / 2, -24, 10), lens=55)
        S.render(os.path.join(out, "hook_inuse.png"))
        for s in straps:
            s.hide_render = True
        # back: how it meets the CLAWs (hook swung out from the wall, CLAWs stay on the wall)
        wl.hide_render = True
        for c in claws:
            c.hide_render = True
        S.camera(P(-150, 330, 170), target=P(W / 2, -7, 40), lens=70)
        S.render(os.path.join(out, "hook_back.png"))
        wl.hide_render = False
        for c in claws:
            c.hide_render = False

    if "--details" in a:
        res0 = (sc.render.resolution_x, sc.render.resolution_y)
        if "--preview" not in a:
            sc.render.resolution_x, sc.render.resolution_y = 1400, 1050
        # label
        S.camera(P(W / 2 - 25, -130, LABEL_Z + 40), target=P(W / 2, -T, LABEL_Z), lens=100)
        S.render(os.path.join(out, "d_label.png"))
        # bottom-left corner (square) and rim
        S.camera(P(-40, -90, -25), target=P(6, -T / 2, 6), lens=100)
        S.render(os.path.join(out, "d_corner.png"))
        # peg end and root
        S.camera(P(PEG_X[0] - 80, -125, 100), target=P(PEG_X[0], -34, 38), lens=85)
        S.render(os.path.join(out, "d_peg.png"))
        # section through the right CLAW (x = 100), keeping x < 100, seen from +X
        sec = S.box("sec", 200, 300, 300, loc=(100 + 100, -50, 60))
        sec.parent = root
        sec.hide_render = True
        for o in [hook] + claws:
            md = o.modifiers.new("sec", "BOOLEAN")
            md.operation, md.solver, md.object = "DIFFERENCE", "EXACT", sec
        wl.hide_render = True
        S.camera(P(330, -260, 170), target=P(70, -20, 35), lens=60)
        S.render(os.path.join(out, "hook_cutaway.png"))
        bottom, top, hinge = claw_z()
        cam = S.ortho_camera("right", P(100, -9, (hinge + TONGUE_TOP) / 2), 0.030)
        S.render(os.path.join(out, "d_tongue_section.png"))
        cam.data.ortho_scale = 0.095
        cam.location = Vector(P(100, -27, 36)) + Vector((0.5, 0, 0))
        S.render(os.path.join(out, "d_section_full.png"))
        for o in [hook] + claws:
            o.modifiers.remove(o.modifiers["sec"])
        bpy.data.objects.remove(sec, do_unlink=True)
        wl.hide_render = False
        sc.render.resolution_x, sc.render.resolution_y = res0

    if "--views" in a:
        # part on its own: four views plus print orientation on a bed plate
        wl.hide_render = True
        for c in claws:
            c.hide_render = True
        views = {"view_front": ((W / 2, -420, 35), (W / 2, -20, 35)),
                 "view_back": ((W / 2, 420, 35), (W / 2, -7, 35)),
                 "view_side": ((420, -26, 35), (W / 2, -26, 35)),
                 "view_top": ((W / 2, -60, 420), (W / 2, -26, 35))}
        for nm, (loc, tgt) in views.items():
            S.camera(P(*loc), target=P(*tgt), lens=55)
            S.render(os.path.join(out, f"{nm}.png"))
        # print orientation: upright on a 180 mm plate
        bed = S.box("Bed", 180, 180, 2, loc=(W / 2, -T / 2 - 20, -1))
        bed.parent = root
        S.assign(bed, S.material("PEI", (0.03, 0.03, 0.032, 1), rough=0.7))
        S.camera(P(-120, -330, 230), target=P(W / 2, -30, 25), lens=50)
        S.render(os.path.join(out, "view_printbed.png"))
        bed.hide_render = True
        fit.hide_render = False
        hook.hide_render = True
        bed.hide_render = False
        S.camera(P(-30, -200, 140), target=P(W / 2, -10, 40), lens=70)
        S.render(os.path.join(out, "view_fittest.png"))

    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "bag_hook.blend"))


if __name__ == "__main__":
    main()
