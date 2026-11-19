"""Purge bin for the Bambu A1 Mini. Rev A.

A slim side bin that sits against the left side of the printer, under the end of the
X gantry where the nozzle wiper flicks off the purged filament. Same family as the hub:
white shell, black base inset 0.6 mm as a shadow line, 10 mm plan corners, 1.2 mm top edge,
a small engraved mono label, nothing else.

Run (bpy via uv):
  uv run --no-project --python 3.13 --with bpy --with trimesh --with networkx --with lxml \
      python purge_bin.py [--renders] [--details] [--drawings] [--preview]
Writes stl/*.stl, purge_bin_shell_white.3mf, purge_bin_base_black.3mf, and renders/.

Printed parts (one colour each, no AMS):
  shell - white PLA, printed upright (open top up), no supports
  base  - black PLA, printed flat; four pins locate the shell so the shadow line is even
Join: a drop of CA glue on each pin, or leave loose (the pins are a snug fit).

Coordinates: X across (printer on the +X side), Y front-to-back (front is -Y), Z up.
Heights are multiples of 0.6 mm, so they land on whole layers at 0.12 and 0.20 mm.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import bpy  # noqa: E402
import studio as S  # noqa: E402

REV = "A"

# ---------------------------------------------------------------- size (mm)
W, D = 72.0, 150.0          # footprint: narrow across, long along the printer's side
R = 10.0                    # plan corner radius (design language: 10-12)
EDGE = S.EDGE_R             # 1.2 top edge fillet
BASE_T = 3.0                # black base
SHELL_H = 49.2              # white shell; total height 52.2
TOP = BASE_T + SHELL_H
WALL = 2.5                  # ~6 lines with a 0.4 nozzle
FLOOR = 3.6                 # leaves 1.2 mm over the pin holes
FLOOR_R = 6.0               # inside floor fillet: purge slides out when you tip it
GAP = S.SHADOW_GAP          # base inset under the shell

# base-to-shell locating pins
PIN_D, PIN_H = 3.0, 2.2
HOLE_D, HOLE_H = 3.2, 2.4   # 0.1 mm a side: snug; printed holes come out a touch small
PIN_XY = [(sx * (W / 2 - 14), sy * (D / 2 - 22)) for sx in (-1, 1) for sy in (-1, 1)]

# label on the front end
LABEL = "PURGE / A1"
LABEL_SIZE = 6.0            # bold mono at 6 mm: strokes ~0.65 mm, wider than the nozzle
ENGRAVE = 0.6
LABEL_Z = TOP - 9.0         # centre height of the text
CLEAR = 1.0                 # min gap from text to any fillet tangent line


def check(ob, size):
    d = S.dims(ob)
    assert all(abs(a - b) < 0.02 for a, b in zip(d, size)), f"{ob.name}: size {d}, expected {size}"
    assert S.volume(ob) > 0, f"{ob.name}: volume {S.volume(ob)}"


def front_label():
    """Engraved text on the front (-Y) face, centred on its real bounding box."""
    ob = S.text("label", LABEL, LABEL_SIZE, 2 * ENGRAVE, loc=(0, 0, 0), align="CENTER",
                font=S.label_font())
    S.bake(ob)
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
    box = (bx[0] + dx, bz[0] + dz, bx[1] + dx, bz[1] + dz)
    # flat part of the front face: between the plan-corner tangents, above the base,
    # below the top-edge fillet
    flat = (-W / 2 + R, BASE_T, W / 2 - R, TOP - EDGE)
    assert (box[0] >= flat[0] + CLEAR and box[2] <= flat[2] - CLEAR
            and box[1] >= flat[1] + CLEAR and box[3] <= flat[3] - CLEAR), \
        f"label {box} not {CLEAR} mm inside flat face {flat}"
    return ob, box


def build():
    S.reset()
    white, black = S.pla("white"), S.pla("black")

    shell = S.rounded_box("Shell", W, D, SHELL_H, r=R, r_top=EDGE, loc=(0, 0, BASE_T))
    S.bake(shell)
    cav = S.rounded_box("cavity", W - 2 * WALL, D - 2 * WALL, SHELL_H, r=R - WALL,
                        r_bot=FLOOR_R, loc=(0, 0, BASE_T + FLOOR))
    holes = [S.cylinder("hole", HOLE_D, 2 * HOLE_H, loc=(x, y, BASE_T)) for x, y in PIN_XY]
    S.cut(shell, [cav] + holes)
    lab, box = front_label()
    v0 = S.volume(shell)
    S.cut(shell, [lab])
    assert S.volume(shell) < v0 - 5, "label cut removed no material"
    check(shell, (W, D, SHELL_H))
    S.assign(shell, white)
    S.smooth(shell, 35)

    base = S.rounded_box("Base", W - 2 * GAP, D - 2 * GAP, BASE_T, r=R - GAP)
    S.bake(base)
    pins = [S.cylinder("pin", PIN_D, PIN_H, loc=(x, y, BASE_T + PIN_H / 2)) for x, y in PIN_XY]
    S.union(base, pins)
    check(base, (W - 2 * GAP, D - 2 * GAP, BASE_T + PIN_H))
    S.assign(base, black)
    S.smooth(base, 35)

    cap_l = (W - 2 * WALL) * (D - 2 * WALL) * (SHELL_H - FLOOR) / 1e6
    print(f"label box {box}; capacity ~{cap_l:.2f} L")
    return shell, base, box


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
    data = {"rev": REV, "W": W, "D": D, "TOP": TOP, "BASE_T": BASE_T, "SHELL_H": SHELL_H,
            "WALL": WALL, "FLOOR": FLOOR, "FLOOR_R": FLOOR_R, "R": R, "EDGE": EDGE, "GAP": GAP,
            "pins": PIN_XY, "pin_d": PIN_D, "pin_h": PIN_H, "hole_d": HOLE_D, "hole_h": HOLE_H,
            "label": LABEL, "label_box": box, "label_size": LABEL_SIZE, "engrave": ENGRAVE}
    with open(os.path.join(out, "dims.json"), "w") as f:
        json.dump(data, f, indent=1)


def main():
    args = sys.argv[1:]
    shell, base, box = build()
    os.makedirs(os.path.join(HERE, "stl"), exist_ok=True)
    S.export_stl(shell, os.path.join(HERE, "stl", "purge_bin_shell_white.stl"))
    S.export_stl(base, os.path.join(HERE, "stl", "purge_bin_base_black.stl"))
    # long side diagonal-free: 150 mm runs along the plate's Y, fits the 180 mm bed
    write_3mf(shell, os.path.join(HERE, "purge_bin_shell_white.3mf"))
    write_3mf(base, os.path.join(HERE, "purge_bin_base_black.3mf"))

    root = S.to_studio([shell, base])
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
        S.camera((-0.26, -0.40, 0.25), target=(0, 0, 0.024))
        S.render(os.path.join(out, "bin_hero.png"))
        S.camera((-0.10, -0.20, 0.50), target=(0, 0, 0.012), lens=75)
        S.render(os.path.join(out, "bin_top.png"))
        S.camera((0.0, -0.46, 0.10), target=(0, 0, 0.024), lens=85)
        S.render(os.path.join(out, "bin_front.png"))
        shell.location.z += 55
        S.camera((-0.36, -0.50, 0.30), target=(0, 0, 0.050), lens=60)
        S.render(os.path.join(out, "bin_exploded.png"))
        shell.location.z -= 55
        # section through two pins (x = +22), seen from the printer side
        cut = S.box("sec", 100, D + 20, 100, loc=(PIN_XY[2][0] + 50, 0, 40))
        cut.parent = root
        cut.hide_render = True
        for o in (shell, base):
            md = o.modifiers.new("sec", "BOOLEAN")
            md.operation, md.solver, md.object = "DIFFERENCE", "EXACT", cut
        S.camera((0.34, -0.30, 0.20), target=(0.02, 0, 0.022), lens=70)
        S.render(os.path.join(out, "bin_cutaway.png"))
        for o in (shell, base):
            o.modifiers.remove(o.modifiers["sec"])
        bpy.data.objects.remove(cut, do_unlink=True)
        root.rotation_euler = (math.pi, 0, 0)
        root.location = (0, 0, (TOP + PIN_H) * m)
        S.camera((-0.24, -0.38, 0.24), target=(0, 0, 0.02))
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
        S.camera((cx - 0.07, cy - 0.09, 0.075), target=(cx + 0.006, cy + 0.006, TOP * m - 0.004),
                 lens=100)
        S.render(os.path.join(out, "d_corner.png"))
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
        views = {"front": ((0, 0, TOP / 2), 0.120), "left": ((0, 0, TOP / 2), 0.200),
                 "top": ((0, 0, TOP / 2), 0.200)}
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
        c = (0, 0, TOP / 2)
        cam = S.ortho_camera("front", tuple(k * m for k in c), 0.120)
        cam.location.y = PIN_XY[0][1] * m - 0.5      # 0.5 m in front of the cut plane
        cam.data.clip_start, cam.data.clip_end = 0.4998, 0.7
        S.render(os.path.join(out, "dwg_section.png"))
        meta["section"] = {"view": "front", "center_mm": c, "scale_mm": 120.0,
                           "res": [sc.render.resolution_x, sc.render.resolution_y]}
        with open(os.path.join(out, "dwg_cameras.json"), "w") as f:
            json.dump(meta, f, indent=1)


if __name__ == "__main__":
    main()
