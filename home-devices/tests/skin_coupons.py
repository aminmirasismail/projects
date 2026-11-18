"""Thin-skin light test coupons: how much light gets through white PLA at each thickness.

Run:  python skin_coupons.py
Writes stl/coupon_H_white.stl, stl/coupon_V_white.stl, skin_test_plate.3mf, and renders.

Coupon H (horizontal): a tile printed flat. Five pockets from the top leave skins of
  0.4 / 0.6 / 0.8 / 1.0 / 1.2 mm against the bed, the way the hub's roof would print.
Coupon V (vertical): an upright wall on a foot. Five pockets from the back leave skins of
  0.5 / 0.6 / 0.8 / 1.0 / 1.2 mm as part of a vertical wall, the way side lighting would print.
  Vertical skins are made of extrusion lines, so the thinnest is 0.5 mm, not 0.4: a 0.4 mm wall
  is right at a 0.4 mm nozzle's limit and the slicer can drop it.
Labels (skin in tenths of a mm) are engraved on the back so the lit side stays clean.

Print both in your white PLA, 0.2 mm layers, so each skin is a whole number of layers.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import bpy  # noqa: E402
import studio as S  # noqa: E402

SKINS_H = (0.4, 0.6, 0.8, 1.0, 1.2)    # whole 0.2 mm layers
SKINS_V = (0.5, 0.6, 0.8, 1.0, 1.2)    # extrusion lines; >= 0.5 with a 0.4 nozzle
WIN_W, WIN_H, PITCH = 10.0, 14.0, 13.0
L = PITCH * len(SKINS_H) + 6.0         # 71 mm
H_T, H_D, H_FILLET = 4.0, 28.0, 0.6    # coupon H thickness, depth, top-edge fillet
H_POCKET_Y = 1.0                       # pockets span y -6..8
V_T, V_H, FOOT_D, FOOT_T = 3.0, 22.0, 14.0, 2.0
CLEAR = 1.0                            # min gap from text to fillets, edges and pockets
ENGRAVE = 0.6


def xs():
    x0 = -PITCH * (len(SKINS_H) - 1) / 2
    return [x0 + i * PITCH for i in range(len(SKINS_H))]


def label(body, size, centre, top_z):
    """Engraved text centred on its real bounding box (Blender places text by its baseline)."""
    ob = S.text("lab", body, size, 2 * ENGRAVE, loc=(0, 0, top_z), align="CENTER")
    S.bake(ob)
    vs = [v.co for v in ob.data.vertices]
    bx = (min(v.x for v in vs), max(v.x for v in vs)); by = (min(v.y for v in vs), max(v.y for v in vs))
    dx, dy = centre[0] - sum(bx) / 2, centre[1] - sum(by) / 2
    for v in ob.data.vertices:
        v.co.x += dx
        v.co.y += dy
    return ob, (bx[0] + dx, by[0] + dy, bx[1] + dx, by[1] + dy)


def assert_clear(name, box, flat, keepouts=()):
    """Text box must sit inside the flat face by CLEAR and stay CLEAR away from cut features."""
    x0, y0, x1, y1 = box
    fx0, fy0, fx1, fy1 = flat
    assert x0 >= fx0 + CLEAR and x1 <= fx1 - CLEAR and y0 >= fy0 + CLEAR and y1 <= fy1 - CLEAR,         f"{name}: {box} not {CLEAR} mm inside flat face {flat}"
    for k in keepouts:
        gap = max(k[0] - x1, x0 - k[2], k[1] - y1, y0 - k[3])
        assert gap >= CLEAR, f"{name}: only {gap:.2f} mm from feature {k}"


def coupon_h():
    tile = S.rounded_box("Coupon H", L, H_D, H_T, r=3.0, r_top=H_FILLET, loc=(0, 0, 0))
    S.bake(tile)
    flat = (-L / 2 + H_FILLET, -H_D / 2 + H_FILLET, L / 2 - H_FILLET, H_D / 2 - H_FILLET)
    pockets = [(x - WIN_W / 2, H_POCKET_Y - WIN_H / 2, x + WIN_W / 2, H_POCKET_Y + WIN_H / 2)
               for x in xs()]
    pocket_lo, pocket_hi = H_POCKET_Y - WIN_H / 2, H_POCKET_Y + WIN_H / 2
    cuts = []
    for x, sk in zip(xs(), SKINS_H):
        cuts.append(S.rounded_box("pocket", WIN_W, WIN_H, H_T, r=1.5, loc=(x, H_POCKET_Y, sk)))
        lab, box = label(f"{int(round(sk * 10))}", 3.2, (x, (flat[1] + pocket_lo) / 2), H_T)
        assert_clear(f"label {sk}", box, flat, pockets)
        cuts.append(lab)
    # the "light side" is the bottom (bed side)
    side, box = label("LIGHT SIDE DOWN", 2.6, (0, (pocket_hi + flat[3]) / 2), H_T)
    assert_clear("LIGHT SIDE DOWN", box, flat, pockets)
    cuts.append(side)
    S.cut(tile, cuts)
    return tile


def coupon_v():
    # all sharp edges: a rounded foot meeting a square wall leaves a fillet that stops dead
    wall = S.box("Coupon V", L, V_T, V_H, loc=(0, 0, FOOT_T + V_H / 2))
    foot = S.box("foot", L, FOOT_D, FOOT_T, loc=(0, FOOT_D / 2 - V_T / 2, FOOT_T / 2))
    S.union(wall, [foot])
    flat = (-L / 2, V_T / 2, L / 2, FOOT_D - V_T / 2)        # foot top behind the wall
    cuts = []
    zc = FOOT_T + V_H / 2 + 1.0
    for x, sk in zip(xs(), SKINS_V):
        # pocket from the back (+Y) leaving `sk` of wall at the front face (-Y),
        # rounded in XZ so the window reads as a rounded rectangle from the front
        depth = V_T - sk
        cuts.append(S.slot("pocket_v", WIN_W, WIN_H, depth + 1,
                           loc=(x, -V_T / 2 + sk + (depth + 1) / 2, zc), axis="Y", r=1.5))
        lab, box = label(f"{int(round(sk * 10))}", 3.2, (x, (flat[1] + flat[3]) / 2), FOOT_T)
        assert_clear(f"V label {sk}", box, flat)
        cuts.append(lab)
    S.cut(wall, cuts)
    return wall


def write_3mf(objs, path, bed=(180.0, 180.0)):
    """Plain 3MF with each part placed on the A1 Mini plate (Bambu Studio opens it)."""
    import trimesh
    scene = trimesh.Scene()
    for ob, (dx, dy) in objs:
        me = ob.data
        v = [(p.co.x + dx + bed[0] / 2, p.co.y + dy + bed[1] / 2, p.co.z) for p in me.vertices]
        # Blender's own triangulation: a naive fan from the first vertex folds concave ngons
        # (e.g. a top face wrapped around pockets and engraved text) back over themselves.
        me.calc_loop_triangles()
        f = [tuple(t.vertices) for t in me.loop_triangles]
        scene.add_geometry(trimesh.Trimesh(vertices=v, faces=f, process=True), node_name=ob.name,
                           geom_name=ob.name)
    scene.export(path, file_type="3mf")


def main():
    S.reset()
    white = S.pla("white")
    h = coupon_h()
    v = coupon_v()
    for o in (h, v):
        S.assign(o, white)
        S.smooth(o, 30)
    os.makedirs(os.path.join(HERE, "stl"), exist_ok=True)
    S.export_stl(h, os.path.join(HERE, "stl", "coupon_H_white.stl"))
    S.export_stl(v, os.path.join(HERE, "stl", "coupon_V_white.stl"))
    write_3mf([(h, (0.0, -20.0)), (v, (0.0, 22.0))], os.path.join(HERE, "skin_test_plate.3mf"))

    if "--renders" in sys.argv:
        # show both coupons lit from behind by a phone-torch-like light, in a dim room
        h.location = (0, -22, 0)
        v.location = (0, 22, 0)
        m = S.material("PLA white (scattering)", S.PLA["white"], rough=0.5)
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Subsurface Weight"].default_value = 1.0
        b.inputs["Subsurface Radius"].default_value = (1.0, 1.0, 1.0)
        b.inputs["Subsurface Scale"].default_value = 0.0012
        for o in (h, v):
            S.assign(o, m)
        S.to_studio([h, v])
        S.studio(samples=96, res=(1400, 1050))
        out = os.path.join(HERE, "renders")
        os.makedirs(out, exist_ok=True)
        S.camera((0.10, -0.20, 0.17), target=(0, 0, 0.006), lens=60)
        S.render(os.path.join(out, "coupons_plate.png"))


if __name__ == "__main__":
    main()
