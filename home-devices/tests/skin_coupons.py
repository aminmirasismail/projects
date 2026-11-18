"""Thin-skin light test coupons: how much light gets through white PLA at each thickness.

Run:  python skin_coupons.py
Writes stl/coupon_H_white.stl, stl/coupon_V_white.stl, skin_test_plate.3mf, and renders.

Coupon H (horizontal): a tile printed flat. Five pockets from the top leave skins of
  0.4 / 0.6 / 0.8 / 1.0 / 1.2 mm against the bed, the way the hub's roof would print.
Coupon V (vertical): an upright wall on a foot. Five pockets from the back leave the same
  five skins as part of a vertical wall, the way side lighting would print.
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

SKINS = (0.4, 0.6, 0.8, 1.0, 1.2)
WIN_W, WIN_H, PITCH = 10.0, 14.0, 13.0
L = PITCH * len(SKINS) + 6.0           # 71 mm
H_T = 4.0                              # coupon H thickness
V_T, V_H, FOOT_D, FOOT_T = 3.0, 22.0, 14.0, 2.0


def xs():
    x0 = -PITCH * (len(SKINS) - 1) / 2
    return [x0 + i * PITCH for i in range(len(SKINS))]


def coupon_h():
    tile = S.rounded_box("Coupon H", L, 24.0, H_T, r=3.0, r_top=0.6, loc=(0, 0, 0))
    S.bake(tile)
    cuts = []
    for x, sk in zip(xs(), SKINS):
        cuts.append(S.rounded_box("pocket", WIN_W, WIN_H, H_T, r=1.5, loc=(x, 1.5, sk)))
        lab = S.text("lab", f"{int(round(sk * 10))}", 3.2, 1.2, loc=(x, -8.6, H_T),
                     align="CENTER")
        cuts.append(lab)
    # orientation notch: the "light side" is the bottom (bed side)
    cuts.append(S.text("side", "LIGHT SIDE DOWN", 2.6, 1.2, loc=(0, 10.4, H_T), align="CENTER"))
    S.cut(tile, cuts)
    return tile


def coupon_v():
    wall = S.box("Coupon V", L, V_T, V_H, loc=(0, 0, FOOT_T + V_H / 2))
    foot = S.rounded_box("foot", L, FOOT_D, FOOT_T, r=2.0, loc=(0, FOOT_D / 2 - V_T / 2, 0))
    S.union(wall, [foot])
    cuts = []
    zc = FOOT_T + V_H / 2 + 1.0
    for x, sk in zip(xs(), SKINS):
        # pocket from the back (+Y) leaving `sk` of wall at the front face (-Y)
        depth = V_T - sk
        p = S.rounded_box("pocket", WIN_W, depth + 1, WIN_H, r=1.5,
                          loc=(x, -V_T / 2 + sk + (depth + 1) / 2, zc - WIN_H / 2))
        S.bake(p)
        # the rounded_box rounds in plan (XY); for a vertical window round it in XZ instead
        p2 = S.slot("pocket_v", WIN_W, WIN_H, depth + 1,
                    loc=(x, -V_T / 2 + sk + (depth + 1) / 2, zc), axis="Y", r=1.5)
        bpy.data.objects.remove(p, do_unlink=True)
        cuts.append(p2)
        lab = S.text("lab", f"{int(round(sk * 10))}", 3.2, 1.2,
                     loc=(x, FOOT_D - V_T / 2 - 4.5, FOOT_T), align="CENTER")
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
