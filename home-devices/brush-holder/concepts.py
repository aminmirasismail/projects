"""Makeup brush drying holder: four collapsible concepts.

Run with Blender's Python:
  blender -b --python concepts.py -- [--only=A,C] [--stills] [--anim] [--preview] [--gpu]

Brushes dry head-down so rinse water drains out of the bristles instead of soaking into
the ferrule glue. Every concept grips the handle in a snap clip and lets the head hang
free in air, with nothing touching the bristles.

  A  Telescope   - round drip dish, three-stage telescoping post, clip disc on top.
                   Collapses to a puck.
  B  Folio       - drip tray with a hinged back panel and a fold-down clip shelf.
                   Folds flat like a closed book.
  C  Fan         - weighted puck, a post with four swivel arms. Arms fan out to dry,
                   swing into one line to store.
  D  Flat-pack   - drip dish, two cross-slotted plates and a clip disc. No moving
                   parts; stacks flat on its own dish.

Placeholder grip sizes until Chelsea's brushes are measured: THICK handles 11 mm,
THIN handles 7 mm, four of each.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import studio as S  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
PREVIEW = "--preview" in ARGS
GPU = "--gpu" in ARGS
ONLY = next((a.split("=")[1].split(",") for a in ARGS if a.startswith("--only=")), list("ABCD"))
OUT = os.path.join(HERE, "renders")
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------- placeholder brushes
THICK, THIN = 11.0, 7.0          # handle diameter at the grip (placeholders)
PLATE = 8.0                      # clip plate thickness
ABOVE = 35.0                     # handle end sticks up this far above the clip plate
BRUSH = {  # total length, head max diameter (fluffed)
    THICK: dict(L=172.0, head=34.0),
    THIN: dict(L=146.0, head=11.0),
}


def seat_edge(d):
    """Distance from clip seat centre to the plate edge it opens through."""
    return d / 2 + 3.0


# ---------------------------------------------------------------- 2D helpers
def circle_pts(r, n=96, c=(0, 0), a0=0.0):
    return [(c[0] + r * math.cos(a0 + 2 * math.pi * i / n),
             c[1] + r * math.sin(a0 + 2 * math.pi * i / n)) for i in range(n)]


def rrect_pts(w, h, r, n=12, c=(0, 0)):
    pts = []
    for cx, cy, a in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
                      (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
        for i in range(n + 1):
            t = math.radians(a + 90 * i / n)
            pts.append((c[0] + cx + r * math.cos(t), c[1] + cy + r * math.sin(t)))
    return pts


def stadium_pts(length, w, n=24):
    """Stadium along X, centred."""
    r = w / 2
    pts = []
    for i in range(n + 1):
        t = -math.pi / 2 + math.pi * i / n
        pts.append((length / 2 - r + r * math.cos(t), r * math.sin(t)))
    for i in range(n + 1):
        t = math.pi / 2 + math.pi * i / n
        pts.append((-length / 2 + r + r * math.cos(t), r * math.sin(t)))
    return pts


def xform(pts, c, ang):
    ca, sa = math.cos(ang), math.sin(ang)
    return [(c[0] + x * ca - y * sa, c[1] + x * sa + y * ca) for x, y in pts]


def prism(name, pts, z0, z1, bevel=0.0):
    """Extrude a simple polygon between z0 and z1 (optionally fillet the rims)."""
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, z0)) for x, y in pts]
    f = bm.faces.new(vs)
    bm.normal_update()
    if f.normal.z > 0:
        f.normal_flip()
    res = bmesh.ops.extrude_face_region(bm, geom=[f])
    top = [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=top, vec=(0, 0, z1 - z0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bevel > 0:
        rims = [e for e in bm.edges if len(e.link_faces) == 2
                and any(abs(fc.normal.z) > 0.9 for fc in e.link_faces)
                and any(abs(fc.normal.z) < 0.1 for fc in e.link_faces)]
        bmesh.ops.bevel(bm, geom=rims, offset=bevel, segments=3, profile=0.5,
                        affect="EDGES", clamp_overlap=True)
    return S._link(name, bm)


def lathe(name, prof, seg=64):
    """Revolve [(r, z), ...] about Z. r=0 ends are closed."""
    bm = bmesh.new()
    rings = []
    for r, z in prof:
        if r < 1e-6:
            rings.append([bm.verts.new((0, 0, z))])
        else:
            rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / seg),
                                        r * math.sin(2 * math.pi * i / seg), z))
                          for i in range(seg)])
    for a, b in zip(rings, rings[1:]):
        for i in range(seg):
            j = (i + 1) % seg
            if len(a) == 1 and len(b) > 1:
                bm.faces.new((a[0], b[j], b[i]))
            elif len(b) == 1 and len(a) > 1:
                bm.faces.new((a[i], a[j], b[0]))
            elif len(a) > 1:
                bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = S._link(name, bm)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def tube(name, ro, ri, z0, z1, seg=96, ch=0.6):
    prof = [(ri, z0), (ro - ch, z0), (ro, z0 + ch), (ro, z1 - ch), (ro - ch, z1), (ri, z1), (ri, z0)]
    bm = bmesh.new()
    loop = prof[:-1]
    rings = [[bm.verts.new((r * math.cos(2 * math.pi * i / seg), r * math.sin(2 * math.pi * i / seg), z))
              for i in range(seg)] for r, z in loop]
    for k in range(len(rings)):
        a, b = rings[k], rings[(k + 1) % len(rings)]
        for i in range(seg):
            j = (i + 1) % seg
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = S._link(name, bm)
    S.smooth(ob, 40)
    return ob


# ---------------------------------------------------------------- the snap clip
def clip_cutters(tag, d, c, ang, z0, z1):
    """Keyhole snap clip: round seat, an entry 0.86 d wide with a small lead-in, and two
    curved relief slots so the jaws flex as a handle is pushed in sideways.
    c = seat centre, ang = direction the clip opens towards (rad)."""
    r = d / 2
    h = 0.43 * d                       # half width of the entry: 0.86 d opening
    e = seat_edge(d)
    jaw, gap = 2.0, 1.2                # jaw thickness, relief slot width
    t0 = math.asin(h / r)
    key = [(r * math.cos(t), r * math.sin(t))
           for t in [t0 + (2 * math.pi - 2 * t0) * i / 48 for i in range(49)]]
    key += [(e - 1.0, -h), (e, -h - 0.9), (e + 12, -h - 0.9), (e + 12, h + 0.9), (e, h + 0.9), (e - 1.0, h)]
    out = [prism(f"{tag}_key", xform(key, c, ang), z0 - 1, z1 + 1)]
    ri, ro = r + jaw, r + jaw + gap
    p1, p2 = math.radians(72), math.radians(150)
    for side in (1, -1):
        pts = [(ri * math.cos(p), ri * math.sin(p)) for p in [p2 - (p2 - p1) * i / 24 for i in range(25)]]
        y_in = ri * math.sin(p1)
        y_out = y_in + gap
        q1 = math.asin(min(1.0, y_out / ro))
        pts += [(e + 12, y_in), (e + 12, y_out)]
        pts += [(ro * math.cos(p), ro * math.sin(p)) for p in [q1 + (p2 - q1) * i / 24 for i in range(25)]]
        if side < 0:
            pts = [(x, -y) for x, y in reversed(pts)]
        out.append(prism(f"{tag}_relief{side}", xform(pts, c, ang), z0 - 1, z1 + 1))
    return out


def clip_plate(name, outline, z_top, clips, bevel=0.8, mat="white"):
    """Plate from an outline with snap clips cut into it. clips: [(d, (x, y), ang)]."""
    z0 = z_top - PLATE
    ob = prism(name, outline, z0, z_top, bevel=bevel)
    cutters = []
    for i, (d, c, ang) in enumerate(clips):
        cutters += clip_cutters(f"{name}{i}", d, c, ang, z0, z_top)
    S.cut(ob, cutters)
    S.assign(ob, S.pla(mat))
    return ob


# ---------------------------------------------------------------- brushes (render props)
def brush_mats():
    handle = S.material("Brush handle", (0.20, 0.10, 0.10, 1), rough=0.35, coat=0.3)
    ferrule = S.material("Ferrule", (0.80, 0.62, 0.48, 1), rough=0.22)
    ferrule.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 1.0
    hair = S.material("Bristles", (0.42, 0.32, 0.25, 1), rough=0.75)
    return handle, ferrule, hair


def brush(kind, x, y, z_plate_top, name):
    """A brush hanging head-down, gripped at the plate. Returns its parts."""
    handle_m, ferrule_m, hair_m = brush_mats()
    top = z_plate_top + ABOVE
    if kind == THICK:
        hd, hl, fl, fd0, fd1, headl, headd = THICK, 100, 28, 13, 16, 44, BRUSH[THICK]["head"]
    else:
        hd, hl, fl, fd0, fd1, headl, headd = THIN, 100, 24, 7.6, 7.0, 22, BRUSH[THIN]["head"]
    z1 = top - hl
    h = lathe(name + "_handle", [(0, top), (hd / 2 - 1.2, top), (hd / 2 - 0.2, top - 0.8),
                                 (hd / 2, top - 3), (hd / 2 + 0.6, z1 + 20), (hd / 2 + 0.9, z1)], 40)
    f = lathe(name + "_ferrule", [(0, z1), (fd0 / 2, z1), (fd0 / 2, z1 - 2),
                                  (fd1 / 2, z1 - fl), (0, z1 - fl)], 40)
    z2 = z1 - fl
    if kind == THICK:
        prof = [(0, z2), (fd1 / 2, z2)] + [
            (fd1 / 2 + (headd / 2 - fd1 / 2) * math.sin(min(1, t / 0.55) * math.pi / 2)
             * (1 if t < 0.55 else math.cos((t - 0.55) / 0.45 * math.pi / 2) ** 0.6),
             z2 - headl * t) for t in [i / 24 for i in range(1, 25)]] + [(0, z2 - headl)]
    else:
        prof = [(0, z2), (fd1 / 2, z2), (headd / 2, z2 - headl * 0.35),
                (headd / 2 * 0.8, z2 - headl * 0.7), (1.2, z2 - headl * 0.98), (0, z2 - headl)]
    b = lathe(name + "_head", prof, 48)
    for ob, m in ((h, handle_m), (f, ferrule_m), (b, hair_m)):
        S.assign(ob, m)
        ob.location.x += x
        ob.location.y += y
        S.bake(ob)
    return [h, f, b]


# ---------------------------------------------------------------- shared parts
def dish(name, R, H=16.0, floor=3.0, wall=2.4):
    """Black drip dish: round, shallow, filleted rim."""
    prof = [(0, 0), (R - 3, 0), (R - 0.6, 0.6), (R, 3), (R, H - 1.2), (R - 0.35, H - 0.35),
            (R - 1.2, H), (R - wall + 0.6, H), (R - wall, H - 0.8), (R - wall, floor + 2),
            (R - wall - 2, floor), (0, floor)]
    ob = lathe(name, prof, 160)
    S.assign(ob, S.pla("black"))
    return ob


def label(body, size, loc, rot=0.0):
    t = S.text("label", body, size, 1.2, loc=(loc[0], loc[1] - size * 0.35, loc[2]), align="CENTER")
    t.rotation_euler.z = rot
    S.bake(t)
    return t


def set_origin(ob, p):
    """Move the object's origin to point p without moving the mesh."""
    ob.data.transform(Matrix.Translation(-Vector(p)))
    ob.location = Vector(p)


def parent_keep(child, parent):
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_basis.inverted()


# ================================================================== concepts
H = 165.0  # clip plate top height for A, B, D
DISC_R = 66.5  # keeps thick-brush seats at r = 58 so heads hang inside the dish


def concept_A():
    """Telescope."""
    parts, brushes = [], []
    base = dish("A_dish", 82)
    boss = tube("A_boss", 17.5, 14.6, 3, 22)
    S.assign(boss, S.pla("black"))
    s1 = tube("A_s1", 14.0, 11.6, 3, 74)
    s2 = tube("A_s2", 11.0, 8.6, 44, 124)
    s3 = tube("A_s3", 8.0, 5.0, 94, H - PLATE)
    c1 = tube("A_c1", 16.0, 11.2, 66, 74)
    c2 = tube("A_c2", 12.8, 8.2, 116, 124)
    for o in (s1, s2, s3):
        S.assign(o, S.pla("white"))
    for o in (c1, c2):
        S.assign(o, S.pla("black"))
    clips = []
    for k in range(8):
        d = THICK if k % 2 == 0 else THIN
        a = math.radians(22.5 + 45 * k)
        rc = DISC_R - seat_edge(d)
        clips.append((d, (rc * math.cos(a), rc * math.sin(a)), a))
    disc = clip_plate("A_disc", circle_pts(DISC_R, 160), H, clips)
    S.cut(disc, [label("BRUSH / 01", 4.2, (0, -30, H), 0)])
    knob = lathe("A_knob", [(0, H + 9), (9, H + 9), (11.2, H + 7.6), (12, H + 5), (12, H), (0, H)], 64)
    S.assign(knob, S.pla("black"))
    for d, (x, y), a in clips:
        brushes += brush(d, x, y, H, f"A_b{len(brushes)}")
    parts = [base, boss, s1, c1, s2, c2, s3, disc, knob]
    # animation: collapsed at f0, extended at f1
    lift2, lift3 = 40.0, 71.0
    for o in (s3, disc, knob):
        parent_keep(o, s3) if o is not s3 else None
    parent_keep(c2, s2)
    anim = [
        (s2, "location", 2, [(0, (0, 0, -lift2)), (0.15, (0, 0, -lift2)), (0.45, (0, 0, 0)), (0.85, (0, 0, 0)), (1.0, (0, 0, -lift2))]),
        (s3, "location", 2, [(0, (0, 0, -lift3)), (0.25, (0, 0, -lift3)), (0.55, (0, 0, 0)), (0.80, (0, 0, 0)), (1.0, (0, 0, -lift3))]),
    ]
    folded = [(s2, "location", (0, 0, -lift2)), (s3, "location", (0, 0, -lift3))]
    return parts, brushes, anim, folded


def concept_B():
    """Folio."""
    W, BD, BH = 176.0, 160.0, 10.0
    yb = 72.0  # back edge / hinge line
    y0 = yb - BD
    tray = prism("B_tray", rrect_pts(W, BD, 10, c=(0, y0 + BD / 2)), 0, BH, bevel=1.0)
    S.cut(tray, [prism("B_well", rrect_pts(W - 4.8, BD - 4.8, 7.6, c=(0, y0 + BD / 2)), 3, BH + 2, bevel=0)])
    S.assign(tray, S.pla("black"))
    # panel: vertical, back face at y=yb-2, thickness 6, hinged on an X axis 20 mm up so
    # that the folded shelf fits between the panel and the tray floor
    hz = BH + 10.0
    pz0, pt = hz - 4.0, 6.0
    py1 = yb - 2.0
    py0 = py1 - pt
    # drawn flat in XY (y = height), then stood up: rotating +90 about X maps y->z, z->-y
    pan = prism("B_panel", rrect_pts(W, H - pz0, 10, c=(0, (pz0 + H) / 2)), 0, pt, bevel=1.0)
    win = prism("B_win", rrect_pts(W - 44, 92, 12, c=(0, pz0 + 30 + 46)), -1, pt + 1)
    S.cut(pan, [win])
    pan.rotation_euler.x = math.pi / 2
    S.bake(pan)  # now spans z pz0..H, y 0..-pt  (x-rotation +90: y->z, z->-y)
    pan.location.y = py1
    S.bake(pan)
    S.assign(pan, S.pla("white"))
    # hinge knuckles: tray (black) and panel (white) alternate along X
    hy = py1 - 3.0
    lip = S.box("B_lip", W - 28, 9, PLATE, loc=(0, py0 - 4.5, H - PLATE / 2))
    S.union(pan, [lip])
    knuckles = []
    for i, x in enumerate((-80, -56, 56, 80)):
        k = S.cylinder(f"B_k{i}", 7.0, 14, loc=(x, hy, hz), rot=(0, math.pi / 2, 0))
        S.bake(k)
        S.assign(k, S.pla("black" if i in (0, 3) else "white"))
        knuckles.append(k)
        if i in (0, 3):
            tw = prism(f"B_tw{i}", rrect_pts(14, 9, 2, c=(x, hy)), 2.0, hz, bevel=0.5)
            S.assign(tw, S.pla("black"))
            knuckles.append(tw)
    # clip shelf: hangs off two side cheeks, 20 mm gap to the panel
    gap, depth = 32.0, 52.0
    sy1 = py0 - gap
    sy0 = sy1 - depth
    clips = []
    for x in (-72, -24, 24, 72):
        clips.append((THICK, (x, sy0 + seat_edge(THICK)), -math.pi / 2))
    for x in (-72, -24, 24, 72):
        clips.append((THIN, (x, sy1 - seat_edge(THIN)), math.pi / 2))
    shelf_ol = rrect_pts(W, depth, 8, c=(0, (sy0 + sy1) / 2))
    shelf = clip_plate("B_shelf", shelf_ol, H, clips)
    cheeks = []
    for sx in (-1, 1):
        ch = prism(f"B_cheek{sx}", rrect_pts(12, gap + 5, 4, c=(sx * (W / 2 - 6), py0 - gap / 2 - 3.5)),
                   H - PLATE, H, bevel=0.6)
        S.assign(ch, S.pla("white"))
        cheeks.append(ch)
    S.union(shelf, cheeks)
    S.cut(shelf, [label("BRUSH / 02", 3.6, (0, sy0 + 26, H))])
    S.assign(shelf, S.pla("white"))
    sk = S.cylinder("B_sk", 5.0, W - 3, loc=(0, py0 - 5, H - 4), rot=(0, math.pi / 2, 0))
    S.bake(sk)
    S.assign(sk, S.pla("black"))
    brushes = []
    for d, (x, y), a in clips:
        brushes += brush(d, x, y, H, f"B_b{len(brushes)}")
    # pivots
    set_origin(pan, (0, hy, hz))
    for k in [k for k in knuckles if k.name in ("B_k1", "B_k2")]:
        parent_keep(k, pan)
    set_origin(shelf, (0, py0 - 5, H - 4))
    parent_keep(shelf, pan)
    parent_keep(sk, pan)
    parts = [tray, pan, shelf, sk] + knuckles
    fold_pan = (math.pi / 2, 0, 0)  # panel tips forward onto the tray
    fold_shelf = (math.pi / 2, 0, 0)          # shelf swings down against the panel face
    anim = [
        (pan, "rotation_euler", 0, [(0, fold_pan), (0.1, fold_pan), (0.4, (0, 0, 0)), (0.8, (0, 0, 0)), (1.0, fold_pan)]),
        (shelf, "rotation_euler", 0, [(0, fold_shelf), (0.4, fold_shelf), (0.6, (0, 0, 0)), (0.75, (0, 0, 0)), (0.9, fold_shelf), (1.0, fold_shelf)]),
    ]
    folded = [(pan, "rotation_euler", fold_pan), (shelf, "rotation_euler", fold_shelf)]
    return parts, brushes, anim, folded


def concept_C():
    """Fan."""
    HC = 170.0
    puck = dish("C_dish", 82)
    S.assign(puck, S.pla("black"))
    post = lathe("C_post", [(0, 3), (13, 3), (13, 20), (10, 22), (10, HC - 2), (9.2, HC - 0.4), (7.5, HC), (0, HC)], 64)
    S.assign(post, S.pla("white"))
    arms, brushes, anim, folded = [], [], [], []
    L, Wd = 128.0, 24.0
    for k in range(4):
        zt = HC - 4 - k * (PLATE + 1.5)
        d = THICK if k < 2 else THIN
        clips = [(d, (L / 2 - seat_edge(d), 0), 0.0), (d, (-L / 2 + seat_edge(d), 0), math.pi)]
        arm = clip_plate(f"C_arm{k}", stadium_pts(L, Wd), zt, clips)
        S.cut(arm, [S.cylinder("hole", 20.4, 40, loc=(0, 0, zt))])
        sp = tube(f"C_sp{k}", 13.5, 10.2, zt - PLATE - 1.5, zt - PLATE)
        S.assign(sp, S.pla("black"))
        ang = math.radians(45 * k + 22.5)
        arm.rotation_euler.z = ang
        for dd, (x, y), a in clips:
            ca, sa = math.cos(ang), math.sin(ang)
            brushes += brush(dd, x * ca - y * sa, x * sa + y * ca, zt, f"C_b{len(brushes)}")
        arms.append((arm, sp, ang))
    cap = lathe("C_cap", [(0, HC + 6), (10, HC + 6), (12.6, HC + 4.6), (13.5, HC + 2), (13.5, HC - 4), (0, HC - 4)], 64)
    S.assign(cap, S.pla("black"))
    parts = [puck, post, cap] + [a for a, _, _ in arms] + [s for _, s, _ in arms]
    for arm, sp, ang in arms:
        f = (0, 0, math.radians(22.5))
        o = (0, 0, ang)
        anim.append((arm, "rotation_euler", 2, [(0, f), (0.12, f), (0.45, o), (0.82, o), (1.0, f)]))
        folded.append((arm, "rotation_euler", f))
    return parts, brushes, anim, folded


def concept_D():
    """Flat-pack."""
    base = dish("D_dish", 82)
    # cross-shaped socket in the dish floor
    sock = []
    for a in (0, math.pi / 2):
        s = prism("D_sock", xform(rrect_pts(136, 11, 3), (0, 0), a), 2, 9, bevel=0.6)
        sock.append(s)
    S.union(sock[0], sock[1:])
    S.cut(sock[0], [prism("D_sg", xform(rrect_pts(130, 5.4, 0.5), (0, 0), a), 4, 12) for a in (0, math.pi / 2)])
    S.assign(sock[0], S.pla("black"))
    plates = []
    T, Wp = 5.0, 128.0
    z0, z1 = 4.0, H - PLATE + 2.5
    for i in range(2):
        prof = rrect_pts(Wp, z1 - z0, 6, c=(0, (z0 + z1) / 2))
        p = prism(f"D_plate{i}", prof, -T / 2, T / 2, bevel=0.8)
        cut = []
        for sx in (-1, 1):  # big airy windows
            cut.append(prism("w", rrect_pts(38, 100, 10, c=(sx * 33, 84)), -T, T))
        # cross slot: plate 0 from the top, plate 1 from the bottom
        if i == 0:
            cut.append(prism("s", rrect_pts(T + 0.4, (z1 - z0) / 2 + 2, 0.1, c=(0, z1 - (z1 - z0) / 4 + 1)), -T, T))
        else:
            cut.append(prism("s", rrect_pts(T + 0.4, (z1 - z0) / 2 + 2, 0.1, c=(0, z0 + (z1 - z0) / 4 - 1)), -T, T))
        S.cut(p, cut)
        p.rotation_euler.x = math.pi / 2           # into the XZ plane
        p.rotation_euler.z = 0 if i == 0 else math.pi / 2
        S.bake(p)
        S.assign(p, S.pla("white"))
        plates.append(p)
    clips = []
    for k in range(8):
        d = THICK if k % 2 == 0 else THIN
        a = math.radians(22.5 + 45 * k)
        rc = DISC_R - seat_edge(d)
        clips.append((d, (rc * math.cos(a), rc * math.sin(a)), a))
    disc = clip_plate("D_disc", circle_pts(DISC_R, 160), H, clips)
    S.cut(disc, [prism("D_dg", xform(rrect_pts(Wp + 1, T + 0.4, 0.2), (0, 0), a), H - PLATE - 1, H - PLATE + 3)
                 for a in (0, math.pi / 2)] + [label("BRUSH / 04", 4.2, (0, -12, H), 0)])
    S.assign(disc, S.pla("white"))
    brushes = []
    for d, (x, y), a in clips:
        brushes += brush(d, x, y, H, f"D_b{len(brushes)}")
    parts = [base, sock[0]] + plates + [disc]
    # pivots at part centres for the assembly animation
    zc = (z0 + z1) / 2
    for p in plates:
        set_origin(p, (0, 0, zc))
    set_origin(disc, (0, 0, H - PLATE / 2))
    flat0 = ((0, 0, 16 + T / 2), (math.pi / 2, 0, 0))
    flat1 = ((0, 0, 16 + 1.5 * T), (0, math.pi / 2, 0))
    flatd = ((0, 0, 16 + 2 * T + PLATE / 2), (0, 0, 0))
    D = lambda p, d: tuple(a - b for a, b in zip(p, d))  # noqa: E731
    zcv = (0, 0, zc)
    zdv = (0, 0, H - PLATE / 2)
    loc0_flat = D(flat0[0], zcv)
    loc1_flat = D(flat1[0], zcv)
    locd_flat = D(flatd[0], zdv)
    anim = [
        (disc, "location", 2, [(0, locd_flat), (0.08, locd_flat), (0.2, (0, -70, 60)), (0.62, (0, -70, 60)), (0.72, (0, 0, 40)), (0.78, (0, 0, 0)), (0.9, (0, 0, 0)), (1.0, locd_flat)]),
        (disc, "rotation_euler", 2, [(0, (0, 0, 0)), (0.2, (0.5, 0, 0)), (0.62, (0.5, 0, 0)), (0.72, (0, 0, 0)), (1.0, (0, 0, 0))]),
        (plates[1], "location", 2, [(0, loc1_flat), (0.2, loc1_flat), (0.32, (0, 0, 110)), (0.42, (60, 0, 40)), (0.5, (60, 0, 40)), (0.6, (0, 0, 0)), (0.9, (0, 0, 0)), (1.0, loc1_flat)]),
        (plates[1], "rotation_euler", 0, [(0, flat1[1]), (0.2, flat1[1]), (0.42, (0, 0, 0)), (0.9, (0, 0, 0)), (1.0, flat1[1])]),
        (plates[0], "location", 2, [(0, loc0_flat), (0.2, loc0_flat), (0.3, (0, 0, 40)), (0.4, (0, 0, 0)), (0.9, (0, 0, 0)), (1.0, loc0_flat)]),
        (plates[0], "rotation_euler", 0, [(0, flat0[1]), (0.22, flat0[1]), (0.4, (0, 0, 0)), (0.9, (0, 0, 0)), (1.0, flat0[1])]),
    ]
    # plate 1 in its rest orientation is already rotated 90 about Z in the mesh; keyframes are deltas
    folded = [(disc, "location", flatd[0]), (plates[1], "location", flat1[0]), (plates[1], "rotation_euler", flat1[1]),
              (plates[0], "location", flat0[0]), (plates[0], "rotation_euler", flat0[1])]
    return parts, brushes, anim, folded


BUILD = {"A": concept_A, "B": concept_B, "C": concept_C, "D": concept_D}
NAMES = {"A": "Telescope", "B": "Folio", "C": "Fan", "D": "Flat-pack"}


# ================================================================== rendering
def use_gpu():
    s = bpy.context.scene
    if not GPU:
        return
    p = bpy.context.preferences.addons["cycles"].preferences
    p.compute_device_type = "OPTIX"
    p.get_devices()
    for d in p.devices:
        d.use = d.type == "OPTIX"
    s.cycles.device = "GPU"


def apply_pose(pose):
    for ob, prop, val in pose:
        setattr(ob, prop, val)


def keyframe(anim, f0, f1):
    for ob, prop, _interp, keys in anim:
        base = Vector(getattr(ob, prop)) if prop == "location" else None
        for t, v in keys:
            f = round(f0 + (f1 - f0) * t)
            if prop == "location":
                ob.location = base + Vector(v)
            else:
                ob.rotation_euler = v
            ob.keyframe_insert(prop, frame=f)
        if prop == "location":
            ob.location = base


CAMS = {  # (loc m, target m, lens)
    "hero": ((0.42, -0.60, 0.36), (0, 0, 0.095), 60),
    "folded": ((0.36, -0.52, 0.30), (0, 0, 0.04), 60),
    "top": ((0.0, -0.12, 0.70), (0, 0, 0.0), 70),
    "anim": ((0.46, -0.64, 0.38), (0, 0, 0.085), 55),
}


def render_concept(key):
    S.reset()
    parts, brushes, anim, folded = BUILD[key]()
    root = S.to_studio([o for o in parts + brushes if o.parent is None])
    for o in parts:
        if o.type == "MESH" and not o.name.endswith(("_handle", "_ferrule", "_head")):
            S.smooth(o, 32)
    S.studio(samples=24 if PREVIEW else 128, res=(700, 525) if PREVIEW else (1400, 1050))
    use_gpu()
    scene = bpy.context.scene
    tag = f"concept_{key}"
    open_pose = [(ob, prop, tuple(getattr(ob, prop))) for ob, prop, _v in folded]

    if "--stills" in ARGS:
        loc, tgt, lens = CAMS["hero"]
        S.camera(loc, tgt, lens)
        S.render(os.path.join(OUT, f"{tag}_hero.png"))
        S.camera((-0.50, -0.50, 0.24), (0, 0, 0.11), 60, name="Cam3q")
        S.render(os.path.join(OUT, f"{tag}_side.png"))
        loc, tgt, lens = CAMS["top"]
        S.camera(loc, tgt, lens, name="CamTop")
        S.render(os.path.join(OUT, f"{tag}_top.png"))
        for b in brushes:
            b.hide_render = True
        S.camera((0.40, -0.58, 0.34), (0, 0, 0.085), 60, name="CamEmpty")
        S.render(os.path.join(OUT, f"{tag}_empty.png"))
        apply_pose(folded)
        loc, tgt, lens = CAMS["folded"] if key != "C" else ((0.40, -0.58, 0.32), (0, 0, 0.085), 60)
        S.camera(loc, tgt, lens, name="CamFold")
        S.render(os.path.join(OUT, f"{tag}_folded.png"))
        apply_pose(open_pose)
        for b in brushes:
            b.hide_render = False

    if "--anim" in ARGS:
        for b in brushes:
            b.hide_render = True
        n = 24 if PREVIEW else 120
        keyframe(anim, 1, n)
        scene.frame_start, scene.frame_end = 1, n
        scene.render.fps = 24
        scene.cycles.samples = 12 if PREVIEW else 48
        scene.render.resolution_x, scene.render.resolution_y = (480, 360) if PREVIEW else (1120, 840)
        loc, tgt, lens = CAMS["anim"]
        S.camera(loc, tgt, lens, name="CamAnim")
        if "--checkframes" in ARGS:  # a few PNG stills along the timeline, for checking motion
            for t in (0.2, 0.3, 0.4, 0.5, 0.6):
                scene.frame_set(round(1 + (n - 1) * t))
                S.render(os.path.join(OUT, "check", f"{tag}_t{int(t * 100):02d}.png"))
            return
        scene.render.image_settings.media_type = "VIDEO"
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.constant_rate_factor = "HIGH"
        scene.render.filepath = os.path.join(OUT, f"{tag}_fold.mp4")
        bpy.ops.render.render(animation=True)

    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, f"concept_{key}.blend"))


def clip_closeup():
    """One shared close-up of the snap clip, with a handle sitting in it."""
    S.reset()
    clips = [(THICK, (-14, 0), -math.pi / 2), (THIN, (14, 0), -math.pi / 2)]
    ol = rrect_pts(60, 30, 6, c=(0, 3.0 + 11))
    # move seat so it opens at the front edge (y = -1)
    clips = [(d, (x, -1 + seat_edge(d)), a) for d, (x, _), a in clips]
    p = clip_plate("Clip", rrect_pts(64, 34, 6, c=(0, 16)), PLATE, clips)
    handle_m = brush_mats()[0]
    hs = []
    x, y = clips[0][1]
    h = lathe("h", [(0, PLATE + 26), (THICK / 2 - 1, PLATE + 26), (THICK / 2, PLATE + 24), (THICK / 2, -30), (0, -30)], 48)
    S.assign(h, handle_m)
    h.location = (x, y, 0)
    S.bake(h)
    S.to_studio([p, h])
    S.smooth(p, 32)
    S.studio(samples=24 if PREVIEW else 160, res=(700, 525) if PREVIEW else (1400, 1050))
    use_gpu()
    S.camera((0.05, -0.10, 0.09), (0.0, 0.010, 0.004), 90)
    S.render(os.path.join(OUT, "clip_closeup.png"))
    S.camera((0.0, 0.013, 0.17), (0.0, 0.013, 0.0), 90, name="ClipTop")
    h.hide_render = True
    S.render(os.path.join(OUT, "clip_top.png"))


if __name__ == "__main__":
    if "--clip" in ARGS:
        clip_closeup()
    for k in ONLY:
        if k in BUILD and ("--stills" in ARGS or "--anim" in ARGS or "--blend" in ARGS):
            render_concept(k)
