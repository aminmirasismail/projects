"""Purge bin for the Bambu A1 Mini. Rev C (backboard).

A side bin that sits against the left side of the printer, under the end of the X gantry
where the nozzle wiper flicks off the purged filament. Rev C adds a backboard: the rim stays
low on the printer side (it tucks under the gantry) and sweeps up in an S-curve to a 100 mm
wall on the far side, which catches purge that gets flung sideways. It is wider (90 mm) for a
steadier footprint under the taller wall. A clip-on deflector (deflector.py) drops most purge
straight down into the low end.

Same family as the hub: white shell, black base inset 0.6 mm as a shadow line, 10 mm plan
corners, 1.2 mm rim fillet (carried along the curve), a small engraved mono label.

Run (bpy via uv):
  uv run --no-project --python 3.13 --with bpy --with trimesh --with networkx --with lxml \
      python purge_bin.py [--renders] [--details] [--drawings] [--preview]
Writes stl/*.stl, purge_bin_shell_white.3mf, purge_bin_base_black.3mf, and renders/.

Printed parts (one colour each, no AMS):
  shell - white PLA, printed upright (open top up), no supports
  base  - black PLA, printed flat; four pins locate the shell so the shadow line is even
Join: a drop of CA glue on each pin, or leave loose (the pins are a snug fit).

Coordinates: X across (printer on the +X side), Y front-to-back (front is -Y), Z up.
Print settings: PRINT_PROCESS (0.08 mm) plus PRINT_SETS, which slows only the outer wall.
Three wall loops fill the 2.5 mm wall solid (two left a sparse-infill core that ghosts
through white PLA), twelve top layers (~1 mm) keep the floor from pillowing, and
elephant-foot compensation keeps the shadow line crisp.
The shell sits on the plate with its back end (+Y) to the back of the bed, where
seam_position=back puts the seam: on the plain back end, never on the label face.

Fit under the gantry: 70 mm measured clearance vs 52.2 mm bin (GANTRY_CLEAR below).
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import bpy  # noqa: E402
import studio as S  # noqa: E402

REV = "C"

# slicer settings on top of "0.12mm Fine @BBL A1M" (see docstring)
PRINT_PROCESS = "0.08mm Extra Fine @BBL A1M"     # High Quality slows everything: 6.5 h vs 4.3 h
PRINT_SETS = {"wall_loops": "3", "top_shell_layers": "12", "elefant_foot_compensation": "0.15",
              "seam_position": "back",
              "outer_wall_speed": "60", "outer_wall_acceleration": "2000",   # only what shows
              "gap_infill_speed": "60",        # gap fill sits right under the rim top
              "top_surface_speed": "100",      # calmer floor finish, cheaper than ironing
              # rev B showed faint layer lines: inner walls at ~300 mm/s behind a 60 mm/s
              # outer wall swing the nozzle pressure every loop. Keep them closer.
              "inner_wall_speed": "120", "inner_wall_acceleration": "3000"}

# ---------------------------------------------------------------- size (mm)
W, D = 90.0, 150.0          # footprint: across x along the printer's side (rev B: 72 wide)
R = 10.0                    # plan corner radius (design language: 10-12)
EDGE = S.EDGE_R             # 1.2 top edge fillet
BASE_T = 3.0                # black base
# rim heights above the desk; flats sit on the 0.08 grid (shell = 0.2 + 0.08 k)
LOW = BASE_T + 42.04        # printer side, under the gantry: 45.04
HIGH = BASE_T + 97.0        # backboard on the far side: 100.0
X1, X2 = 12.0, -33.0        # S-curve from LOW at x = X1 up to HIGH at x = X2 (max slope ~62 deg)
SHELL_H = HIGH - BASE_T
TOP = LOW                   # the rim the label and the gantry check work from


def rim_z(x):
    """Rim height at x: flat LOW on the printer side, a cosine S-curve, flat HIGH beyond."""
    if x >= X1:
        return LOW
    if x <= X2:
        return HIGH
    t = (X1 - x) / (X1 - X2)
    return LOW + (HIGH - LOW) * (1 - math.cos(math.pi * t)) / 2
WALL = 2.5                  # ~6 lines with a 0.4 nozzle
FLOOR = 3.64                # on the 0.08 grid; leaves 1.2 mm over the pin holes
FLOOR_R = 6.0               # inside floor fillet: purge slides out when you tip it
GAP = S.SHADOW_GAP          # base inset under the shell
RIM_CH = 0.5                # 45-deg inside chamfer; leaves a 0.8 mm flat = two clean lines

# The bin sits under the left end of the X gantry. The lowest the toolhead/gantry passes over
# it must clear the rim, or it will hit on homing.
GANTRY_CLEAR = 70.0         # mm above the desk, lowest moving part over the bin (owner measured)
DEFLECTOR_DROP = 14.0       # the clip-on deflector hangs this far below the wiper (deflector.py)
assert LOW <= GANTRY_CLEAR - DEFLECTOR_DROP - 5, "low rim too close to the deflector"
# the rim passes 70 mm for x < -9.2: only the far 55 mm of the width; nothing on the printer
# may pass over that zone at its lowest Z (owner to confirm against the gantry end)

# base-to-shell locating pins
PIN_D, PIN_H, PIN_CH = 3.0, 1.8, 0.4      # pin with a 0.4 mm lead-in chamfer on its tip
HOLE_D, HOLE_H = 3.4, 2.44  # depth on the 0.08 grid; 0.2 mm a side: drops on blind; printed holes come out small
PIN_XY = [(sx * (W / 2 - 16), sy * (D / 2 - 22)) for sx in (-1, 1) for sy in (-1, 1)]

# label on the front end
LABEL = ("PURGE", "A1M")    # engraved as PURGE · A1M
SEP = "dot"                 # house separator: Ø1.3 dot, 1.2 deep (S.product_label)
LABEL_SIZE = 6.0            # bold mono at 6 mm: strokes ~0.65 mm, wider than the nozzle
ENGRAVE = 0.6
LABEL_Z = LOW - 9.0         # centre height of the text
SEPS = []                   # separator centres on the front face (x, z), set by build()
CLEAR = 1.0                 # min gap from text to any fillet tangent line


def check(ob, size):
    d = S.dims(ob)
    assert all(abs(a - b) < 0.02 for a, b in zip(d, size)), f"{ob.name}: size {d}, expected {size}"
    assert S.volume(ob) > 0, f"{ob.name}: volume {S.volume(ob)}"


def front_label():
    """Engraved text on the front (-Y) face, centred on its real bounding box."""
    ob = S.product_label("label", LABEL, LABEL_SIZE, 2 * ENGRAVE, sep=SEP)
    # text lies in XY, extruded along Z; stand it up on the -Y face with a rotation about X
    # (a plain axis swap would mirror it, turn its normals inside out and the cut does nothing)
    for v in ob.data.vertices:
        x, y, z = v.co
        v.co = (x, -D / 2 - z, y)
    vs = [v.co for v in ob.data.vertices]
    bx = (min(v.x for v in vs), max(v.x for v in vs))
    bz = (min(v.z for v in vs), max(v.z for v in vs))
    dx, dz = -sum(bx) / 2, LABEL_Z - sum(bz) / 2
    for v in ob.data.vertices:
        v.co.x += dx
        v.co.z += dz
    ob.data.update()
    seps = [(cx + dx, cz + dz) for cx, cz in ob["seps"]]     # on the front face, x and z
    box = (bx[0] + dx, bz[0] + dz, bx[1] + dx, bz[1] + dz)
    # flat part of the front face: between the plan-corner tangents, above the base,
    # below the top-edge fillet
    flat = (-W / 2 + R, BASE_T, W / 2 - R, min(rim_z(x) for x in (box[0], box[2])) - EDGE)
    assert (box[0] >= flat[0] + CLEAR and box[2] <= flat[2] - CLEAR
            and box[1] >= flat[1] + CLEAR and box[3] <= flat[3] - CLEAR), \
        f"label {box} not {CLEAR} mm inside flat face {flat}"
    return ob, box, seps


def inlays(seps):
    """Red filament stubs for the inlay separator: 1.75 mm, flush with the front face."""
    red = S.pla("red")
    out = []
    for x, z in seps:
        rod = S.cylinder("inlay", 1.75, 2 * ENGRAVE, loc=(x, -D / 2 + ENGRAVE, z),
                         rot=(math.pi / 2, 0, 0))
        S.bake(rod)
        out.append(S.assign(rod, red))
    return out


def offset_top(ob, z_top, c):
    """Push the verts at z_top outward by c along the rounded-rect outline's normal, turning a
    rounded-rect prism into a 45-degree flare (an exact offset, corners included)."""
    vs = ob.data.vertices
    a = W / 2 - R                                  # half-size of the cavity's straight core
    b = D / 2 - R
    for v in vs:
        if abs(v.co.z - z_top) < 1e-4:
            cx, cy = max(-a, min(a, v.co.x)), max(-b, min(b, v.co.y))
            nx, ny = v.co.x - cx, v.co.y - cy
            n = math.hypot(nx, ny)
            v.co.x += c * nx / n
            v.co.y += c * ny / n
    ob.data.update()
    return ob


def pin(x, y):
    p = S.cylinder("pin", PIN_D, PIN_H - PIN_CH, loc=(x, y, BASE_T + (PIN_H - PIN_CH) / 2))
    bpy.ops.mesh.primitive_cone_add(vertices=S.arc_segments(PIN_D / 2, 360, minimum=32),
                                    radius1=PIN_D / 2, radius2=PIN_D / 2 - PIN_CH, depth=PIN_CH, location=(x, y, BASE_T + PIN_H - PIN_CH / 2))
    S.union(p, [bpy.context.active_object])
    return p


def outline(d):
    """The plan outline offset inward by d, as (x, y, nx, ny) points with the outward normal.
    Every offset has the same point count and order, so rings join with quads. The straight
    front and back runs are split every 0.5 mm so the rim curve stays smooth."""
    a, b, r = W / 2 - R, D / 2 - R, R - d
    nc = S.arc_segments(R, 90, minimum=12)
    nx_run = max(2, int(2 * a / 0.5))
    pts = []
    corners = [(a, b, 0), (-a, b, 90), (-a, -b, 180), (a, -b, 270)]
    for i, (cx, cy, a0) in enumerate(corners):
        for k in range(nc):
            t = math.radians(a0 + 90 * k / nc)
            pts.append((cx + r * math.cos(t), cy + r * math.sin(t), math.cos(t), math.sin(t)))
        # straight run to the next corner
        ncx, ncy, a1 = corners[(i + 1) % 4]
        t = math.radians(a1)
        n = (math.cos(t), math.sin(t))
        steps = nx_run if abs(n[1]) > 0.5 else 8
        for k in range(steps):
            f = k / steps
            x0, y0 = cx + r * n[0], cy + r * n[1]
            x1, y1 = ncx + r * n[0], ncy + r * n[1]
            pts.append((x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, n[0], n[1]))
    return pts


def shell_mesh():
    """The white shell as one swept surface: rings around the plan outline, each ring a step of
    the wall's cross-section (outside, rim fillet, rim, inner chamfer, inside, floor fillet).
    Each point's rim height comes from rim_z() at the outer outline's x, so the whole cross
    section - fillet included - rides the S-curve; rim features are offset square to the rim."""
    import bmesh
    base_pts = outline(0.0)
    zt = [rim_z(p[0]) for p in base_pts]
    # rim slope along the wall: the rim fillet and chamfer are offset along the rim's normal
    # (-z', 0, 1)/L, i.e. square to the rim, so they keep full size on the steep S-curve
    slope = [(rim_z(p[0] + 0.01) - rim_z(p[0] - 0.01)) / 0.02 for p in base_pts]
    prof = [(0.0, "abs", BASE_T)]                     # (inward offset d, kind, value)
    ne = S.arc_segments(EDGE, 90, minimum=6)
    for k in range(ne + 1):
        t = math.pi / 2 * k / ne
        prof.append((EDGE * (1 - math.cos(t)), "rim", -EDGE + EDGE * math.sin(t)))
    prof.append((WALL - RIM_CH, "rim", 0.0))
    prof.append((WALL, "rim", -RIM_CH))
    zf = BASE_T + FLOOR
    nf = S.arc_segments(FLOOR_R, 90, minimum=8)
    for k in range(nf + 1):
        t = math.pi / 2 * k / nf
        prof.append((WALL + FLOOR_R * (1 - math.cos(t)), "abs",
                     zf + FLOOR_R - FLOOR_R * math.sin(t)))
    bm = bmesh.new()
    rings = []
    for d, kind, val in prof:
        ring = []
        for (x, y, nx, ny), z, zp in zip(outline(d), zt, slope):
            if kind == "abs":
                ring.append(bm.verts.new((x, y, val)))
            else:
                L = math.hypot(1.0, zp)
                ring.append(bm.verts.new((x - val * zp / L, y, z + val / L)))
        rings.append(ring)
    n = len(base_pts)
    for r0, r1 in zip(rings[:-1], rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    bm.faces.new(list(reversed(rings[0])))                    # underside
    bm.faces.new(rings[-1])                                   # floor
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return S._link("Shell", bm)


def build():
    S.reset()
    white, black = S.pla("white"), S.pla("black")

    shell = shell_mesh()
    holes = [S.cylinder("hole", HOLE_D, 2 * HOLE_H, loc=(x, y, BASE_T)) for x, y in PIN_XY]
    S.cut(shell, holes)
    lab, box, seps = front_label()
    SEPS[:] = seps
    v0 = S.volume(shell)
    S.cut(shell, [lab])
    assert S.volume(shell) < v0 - 5, "label cut removed no material"
    check(shell, (W, D, SHELL_H))
    S.assign(shell, white)
    S.smooth(shell, 35)

    base = S.rounded_box("Base", W - 2 * GAP, D - 2 * GAP, BASE_T, r=R - GAP)
    S.bake(base)
    S.union(base, [pin(x, y) for x, y in PIN_XY])
    check(base, (W - 2 * GAP, D - 2 * GAP, BASE_T + PIN_H))
    S.assign(base, black)
    S.smooth(base, 35)

    cap_l = (W - 2 * WALL) * (D - 2 * WALL) * (LOW - BASE_T - FLOOR) / 1e6
    print(f"label box {box}; capacity ~{cap_l:.2f} L")
    extras = inlays(seps) if SEP == "inlay" else []
    return shell, base, box, extras


def write_3mf(ob, path, bed=(180.0, 180.0), rot_z=0.0):
    """One part centred on the A1 Mini plate, sitting on z = 0 (Bambu Studio opens it)."""
    import trimesh
    me = ob.data
    z0 = min(p.co.z for p in me.vertices)
    c, s = math.cos(rot_z), math.sin(rot_z)
    v = [(c * p.co.x - s * p.co.y + bed[0] / 2, s * p.co.x + c * p.co.y + bed[1] / 2,
          p.co.z - z0) for p in me.vertices]
    me.calc_loop_triangles()          # Blender's triangulation; a fan folds concave ngons
    f = [tuple(t.vertices) for t in me.loop_triangles]
    sc = trimesh.Scene()
    sc.add_geometry(trimesh.Trimesh(vertices=v, faces=f, process=True), node_name=ob.name,
                    geom_name=ob.name)
    sc.export(path, file_type="3mf")


def write_dims_json(out, box):
    data = {"rev": REV, "W": W, "D": D, "TOP": TOP, "LOW": LOW, "HIGH": HIGH, "X1": X1, "X2": X2, "BASE_T": BASE_T, "SHELL_H": SHELL_H,
            "WALL": WALL, "FLOOR": FLOOR, "FLOOR_R": FLOOR_R, "R": R, "EDGE": EDGE, "GAP": GAP,
            "pins": PIN_XY, "pin_d": PIN_D, "pin_h": PIN_H, "hole_d": HOLE_D, "hole_h": HOLE_H,
            "label": " · ".join(LABEL), "sep": SEP, "seps": SEPS, "dot_d": 0.22 * LABEL_SIZE, "dot_depth": S.DOT_DEPTH,
            "label_box": box, "label_size": LABEL_SIZE, "engrave": ENGRAVE}
    with open(os.path.join(out, "dims.json"), "w") as f:
        json.dump(data, f, indent=1)


def main():
    args = sys.argv[1:]
    shell, base, box, extras = build()
    os.makedirs(os.path.join(HERE, "stl"), exist_ok=True)
    S.export_stl(shell, os.path.join(HERE, "stl", "purge_bin_shell_white.stl"))
    S.export_stl(base, os.path.join(HERE, "stl", "purge_bin_base_black.stl"))
        # model +Y faces the bed back: seam_position=back puts the seam on the plain back face (at
    # 90 deg it rode the S-curve crest on the label face), and the 150 mm backboard runs along
    # the bed's Y travel instead of taking its acceleration face-on
    write_3mf(shell, os.path.join(HERE, "purge_bin_shell_white.3mf"))
    write_3mf(base, os.path.join(HERE, "purge_bin_base_black.3mf"))

    if "--coupon" in args:
        # finish test: a 70 x 12 mm piece of the front wall up to 50 mm (label, low rim, start
        # of the S-curve). Same plate orientation as the shell, so seams and speeds match.
        cp = shell.copy()
        cp.data = shell.data.copy()
        bpy.context.collection.objects.link(cp)
        keep = S.box("keep", 70, 12, 50 - BASE_T,
                     loc=(12.5, -D / 2 + 6 - 0.001, (50 + BASE_T) / 2 - 0.001))
        md = cp.modifiers.new("k", "BOOLEAN")
        md.operation, md.solver, md.object = "INTERSECT", "EXACT", keep
        S.bake(cp)
        bpy.data.objects.remove(keep, do_unlink=True)
        cp.name = "Coupon"
        print("coupon", S.dims(cp), round(S.volume(cp)))
        write_3mf(cp, os.path.join(HERE, "coupon_wall_white.3mf"))
        bpy.data.objects.remove(cp, do_unlink=True)

    root = S.to_studio([shell, base] + extras)
    S.studio()
    out = os.path.join(HERE, "renders")
    sc = bpy.context.scene
    if "--preview" in args:
        out = os.path.join(HERE, "renders", "_preview")
        sc.cycles.samples = 16
        sc.render.resolution_x, sc.render.resolution_y = 800, 600
    os.makedirs(out, exist_ok=True)
    write_dims_json(out, box)
    m = 0.001

    if "--renders" in args:
        S.camera((-0.30, -0.42, 0.26), target=(0, 0, 0.044))
        S.render(os.path.join(out, "bin_hero.png"))
        S.camera((-0.10, -0.20, 0.55), target=(0, 0, 0.02), lens=75)
        S.render(os.path.join(out, "bin_top.png"))
        S.camera((0.0, -0.52, 0.06), target=(0, 0, 0.048), lens=85)
        S.render(os.path.join(out, "bin_front.png"))
        shell.location.z += 60
        S.camera((-0.40, -0.55, 0.32), target=(0, 0, 0.07), lens=60)
        S.render(os.path.join(out, "bin_exploded.png"))
        shell.location.z -= 60
        # section through two pins (x = +22), seen from the printer side
        cut = S.box("sec", 100, D + 20, 100, loc=(PIN_XY[2][0] + 50, 0, 40))
        cut.parent = root
        cut.hide_render = True
        for o in (shell, base):
            md = o.modifiers.new("sec", "BOOLEAN")
            md.operation, md.solver, md.object = "DIFFERENCE", "EXACT", cut
        S.camera((0.38, -0.34, 0.24), target=(0.0, 0, 0.042), lens=70)
        S.render(os.path.join(out, "bin_cutaway.png"))
        for o in (shell, base):
            o.modifiers.remove(o.modifiers["sec"])
        bpy.data.objects.remove(cut, do_unlink=True)
        root.rotation_euler = (math.pi, 0, 0)
        root.location = (0, 0, (HIGH + PIN_H) * m)
        S.camera((-0.28, -0.42, 0.26), target=(0, 0, 0.04))
        S.render(os.path.join(out, "bin_underside.png"))
        root.rotation_euler = (0, 0, 0)
        root.location = (0, 0, 0)

    if "--details" in args:
        res0 = (sc.render.resolution_x, sc.render.resolution_y)
        if "--preview" not in args:
            sc.render.resolution_x, sc.render.resolution_y = 1400, 1050
        S.camera((-0.03, -0.17, 0.065), target=(0, -D / 2 * m, LABEL_Z * m), lens=100)
        S.render(os.path.join(out, "d_label.png"))
        cx, cy = -W / 2 * m, -D / 2 * m
        S.camera((cx - 0.07, cy - 0.09, HIGH * m + 0.02), target=(cx + 0.006, cy + 0.006,
                 HIGH * m - 0.004), lens=100)
        S.render(os.path.join(out, "d_corner.png"))
        # the rim fillet on the steepest part of the S-curve (x ~ -10.5)
        xc = -10.5
        S.camera((xc * m - 0.05, cy - 0.11, rim_z(xc) * m + 0.03),
                 target=(xc * m, cy, rim_z(xc) * m - 0.002), lens=100)
        S.render(os.path.join(out, "d_curve.png"))
        S.camera((cx - 0.09, cy - 0.07, 0.012), target=(cx + 0.006, cy + 0.006, 0.003), lens=100)
        S.render(os.path.join(out, "d_shadowline.png"))
        S.camera((0.03, -0.12, 0.17), target=(0, -0.035, 0.008), lens=60)
        S.render(os.path.join(out, "d_inside.png"))
        sc.render.resolution_x, sc.render.resolution_y = res0

    if "--drawings" in args:
        S.drawing_setup()
        grey = S.material("Drawing grey", (0.86, 0.86, 0.86, 1), rough=0.9)
        sc.view_layers[0].material_override = grey
        meta = {}
        # framed so every dimension line fits (drawings are 3:2; top view is 150 mm tall)
        views = {"front": ((0, 0, HIGH / 2 + 4), 0.205), "left": ((0, 0, HIGH / 2), 0.230),
                 "top": ((0, 0, HIGH / 2), 0.270)}
        for v, (c, scale) in views.items():
            S.ortho_camera(v, tuple(k * m for k in c), scale)
            S.render(os.path.join(out, f"dwg_{v}.png"))
            meta[v] = {"view": v, "center_mm": c, "scale_mm": scale * 1000,
                       "res": [sc.render.resolution_x, sc.render.resolution_y]}
        # section at y = -40 (through two pins), seen from the front
        sc.view_layers[0].material_override = None
        sec = S.box("sec", 300, 200, 200, loc=(0, PIN_XY[0][1] - 100, 0))
        sec.parent = root
        sec.hide_render = True
        for o in (shell, base):
            md = o.modifiers.new("sec", "BOOLEAN")
            md.operation, md.solver, md.object = "DIFFERENCE", "EXACT", sec
        c = (0, 0, HIGH / 2 + 4)
        cam = S.ortho_camera("front", tuple(k * m for k in c), 0.205)
        cam.location.y = PIN_XY[0][1] * m - 0.5      # 0.5 m in front of the cut plane
        cam.data.clip_start, cam.data.clip_end = 0.4998, 0.7
        S.render(os.path.join(out, "dwg_section.png"))
        meta["section"] = {"view": "front", "center_mm": c, "scale_mm": 205.0,
                           "res": [sc.render.resolution_x, sc.render.resolution_y]}
        with open(os.path.join(out, "dwg_cameras.json"), "w") as f:
            json.dump(meta, f, indent=1)


if __name__ == "__main__":
    main()
