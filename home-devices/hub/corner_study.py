"""Corner study for the hub's underglow: ways to light the corners without corner LEDs.

Run:  python corner_study.py [--preview] [--only=A,B]
Writes renders/corner_<variant>_<view>.png, view in (wide, corner).

  A  v4 as built: screw posts in the channel corners, runs stop short (9 + 7 LEDs a side)
  B  no posts: screw heads flush in the plate, runs reach the corners (11 + 8 LEDs a side)
  C  B + each run's end LED tipped 35 deg toward its corner (a printed ramp under the strip)
  D  C + aluminium tape on the channel's ceiling and walls in each corner
  E  C + a 0.6 mm white PLA diffuser ring across the channel opening
  F  B + the diffuser ring, no tilt (simplest to build)

Satin wood, dark room, warm white at the 0.5 A cap (0.015 W of light per LED), the same
camera and exposure for every variant. LEDs are modelled as 5 mm emitters facing down
(Lambertian, like a 5050 package), not point lights, so tilting them means something.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
import hub as H  # noqa: E402
import studio as S  # noqa: E402
import underglow_study as U  # noqa: E402

PREVIEW = "--preview" in sys.argv
ONLY = [a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")]
VARIANTS = {"A": (True, False, False, False), "B": (False, False, False, False),
            "C": (False, True, False, False), "D": (False, True, True, False),
            "E": (False, True, False, True),
            "F": (False, False, False, True)}          # posts, tilt, foil, diffuser
TILT = 35.0
VIEWS = {"wide": ((0.22, -0.31, 0.13), (0.0, 0.0, 0.016), 58),
         "corner": ((0.15, -0.14, 0.055), (0.046, -0.033, 0.004), 70)}


def runs():
    """LED positions grouped by run, in chain order."""
    pos, out, i = H.led_positions(), [], 0
    for n in (H.N_SHORT, H.N_LONG, H.N_SHORT, H.N_LONG):
        out.append([p[:2] for p in pos[i:i + n]])
        i += n
    return out


def emitters(tilt):
    obs = []
    for run in runs():
        (x0, y0), (x1, y1) = run[0], run[-1]
        L = math.hypot(x1 - x0, y1 - y0)
        ux, uy = (x1 - x0) / L, (y1 - y0) / L
        for k, (x, y) in enumerate(run):
            n = Vector((0, 0, -1))
            if tilt and k in (0, len(run) - 1):
                s = -1 if k == 0 else 1                  # toward the nearer corner
                t = math.radians(TILT)
                n = Vector((s * ux * math.sin(t), s * uy * math.sin(t), -math.cos(t)))
            li = bpy.data.lights.new("led", "AREA")
            li.shape, li.size = "SQUARE", 0.005
            li.energy = U.LED_W
            li.color = U.WARM_LED
            ob = bpy.data.objects.new("led", li)
            bpy.context.collection.objects.link(ob)
            ob.location = (x / 1000, y / 1000, (H.Z_LED_FACE - 0.05) / 1000)
            ob.rotation_euler = n.to_track_quat("-Z", "Y").to_euler()
            obs.append(ob)
    return obs


def corner_cut():
    """Cutters that remove everything but the four corner zones beyond the run ends."""
    xe = H.N_LONG * H.PITCH / 2
    ye = H.N_SHORT * H.PITCH / 2
    return [S.box("x_mid", 2 * xe, 200, 50, loc=(0, 0, 0)),
            S.box("y_mid", 200, 2 * ye, 50, loc=(0, 0, 0))]


def foil():
    """Aluminium tape on the channel ceiling and both walls, in the corners only."""
    zt = H.Z_PLATE_BOT - 0.02
    parts = [H._ring_rect("foil_top", H.CH_IN0 - 0.01, H.FOOT_IN + 0.01, zt - 0.05, zt, H.R),
             H._ring_rect("foil_out", H.CH_IN0 - 0.01, H.CH_IN0 + 0.05,
                          H.LINING_Z + H.FLANGE_T, zt, H.R)]
    f = parts[0]
    S.union(f, parts[1:])
    S.cut(f, corner_cut())
    m = S.material("Aluminium tape", (0.9, 0.9, 0.92, 1), rough=0.18)
    m.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 1.0
    return S.assign(f, m)


def diffuser():
    """0.6 mm white PLA ring resting on the flange, spanning the channel opening."""
    z0 = H.LINING_Z + H.FLANGE_T
    d = H._ring_rect("Diffuser", H.CH_IN0 + 0.1, H.FOOT_IN - 0.1, z0, z0 + 0.6, H.R)
    m = S.material("PLA white (scattering)", S.PLA["white"], rough=0.5)
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Subsurface Weight"].default_value = 1.0
    b.inputs["Subsurface Radius"].default_value = (1.0, 1.0, 1.0)
    b.inputs["Subsurface Scale"].default_value = 0.0012           # metres, as in the coupons
    return S.assign(d, m)


def run(key):
    posts, tilt, use_foil, use_diff = VARIANTS[key]
    S.reset()
    H.configure(posts)
    shell, floor, plinth = H.build()
    extra = []
    if use_foil:
        extra.append(foil())
    if use_diff:
        extra.append(diffuser())
    S.to_studio([shell, floor, plinth] + extra)
    S.studio(samples=24 if PREVIEW else 192, res=(800, 600) if PREVIEW else (1400, 1050))
    sc = bpy.context.scene
    sc.cycles.max_bounces = 16
    sc.cycles.transmission_bounces = 16
    for ob in bpy.data.objects:
        if ob.type == "LIGHT" and ob.data.type == "AREA":
            ob["base"], ob["base_col"] = ob.data.energy, tuple(ob.data.color)
    emitters(tilt)
    t = U.table(U.wood())
    k, world, tint = U.ROOMS["dark"]          # dim the studio only, not the LED emitters
    for ob in bpy.data.objects:
        if ob.type == "LIGHT" and "base" in ob:
            ob.data.energy = ob["base"] * k
            ob.data.color = tuple(a * b for a, b in zip(ob["base_col"], tint))
    bg = sc.world.node_tree.nodes["Background"]
    bg.inputs["Strength"].default_value = world
    bg.inputs["Color"].default_value = (*(0.5 * c for c in tint), 1)
    out = os.path.join(HERE, "renders", "_preview" if PREVIEW else "")
    os.makedirs(out, exist_ok=True)
    for view, (loc, tgt, lens) in VIEWS.items():
        S.camera(loc, target=tgt, lens=lens)
        S.render(os.path.join(out, f"corner_{key}_{view}.png"))
    print(f"VARIANT {key}: {len(H.led_positions())} LEDs, posts={posts}, tilt={tilt}, "
          f"foil={use_foil}, diffuser={use_diff}")
    return t


if __name__ == "__main__":
    keys = ONLY[0] if ONLY else list(VARIANTS)
    for k in keys:
        run(k)
