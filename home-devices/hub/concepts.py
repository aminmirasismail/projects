"""Lighting concepts for the hub: a perimeter light following the rounded top face.

Run:  python concepts.py [--preview] [--only=A,B]
Writes renders/concept_<X>_dark.png and concept_<X>_room.png.

These are look-and-feel studies: exterior, light path and diffuser, ray-traced with
a blue-to-orange gradient. Mounting and wiring get engineered once one is picked.

LED strips bend through their thickness, not sideways, so a strip can't lie flat
(LEDs up) around a rounded rectangle. In every concept the strip stands on edge
around the inside of a wall; its light is modelled as small sources along that path.

  A  Hidden halo   - roof thinned to 0.6 mm along the perimeter; glows through solid white.
                     Air enters through the shadow line under the shell.
  B  Light seam    - frosted translucent insert in a perimeter slot; the hairline gaps
                     either side of it are the vents.
  C  Floating lid  - a glowing seam runs round the sides just under the top edge; the
                     seam is also the vent. Visible from eye level.
  D  Underglow     - wildcard: light washes onto the table from under a floating shell.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import bpy  # noqa: E402
import studio as S  # noqa: E402

W, D, R = 106.0, 80.0, 12.0
BASE_T, TOP, WALL, ROOF = 3.0, 40.0, 2.0, 2.0
PREVIEW = "--preview" in sys.argv
OUT = os.path.join(HERE, "renders")
BLUE, ORANGE = (0.08, 0.32, 1.0), (1.0, 0.42, 0.03)


def gradient(t):
    """Seamless blue -> orange -> blue around the loop."""
    k = 0.5 - 0.5 * math.cos(2 * math.pi * t)
    return tuple(b + (o - b) * k for b, o in zip(BLUE, ORANGE))


def path(inset, n):
    """n evenly spaced points (x, y, nx, ny) around the rounded rectangle inset from the
    outer edge; (nx, ny) is the outward normal."""
    a, b = W / 2 - inset, D / 2 - inset
    rc = max(R - inset, 1.0)
    dense = []
    for cx, cy, a0 in ((a - rc, b - rc, 0), (-a + rc, b - rc, 90), (-a + rc, -b + rc, 180),
                       (a - rc, -b + rc, 270)):
        for k in range(60):
            t = math.radians(a0 + 90 * k / 59)
            dense.append((cx + rc * math.cos(t), cy + rc * math.sin(t), math.cos(t),
                          math.sin(t)))
    pts = dense + [dense[0]]
    seg = [math.dist(pts[i][:2], pts[i + 1][:2]) for i in range(len(pts) - 1)]
    total = sum(seg)
    out, acc, i = [], 0.0, 0
    for k in range(n):
        target = total * k / n
        while acc + seg[i] < target:
            acc += seg[i]
            i += 1
        f = (target - acc) / seg[i] if seg[i] else 0
        p, q = pts[i], pts[i + 1]
        out.append(tuple(p[j] + (q[j] - p[j]) * f for j in range(4)))
    return out, total


def band(name, inset, width, z0, z1):
    """Solid that follows the perimeter: a rounded-rectangle ring."""
    outer = S.rounded_box(name, W - 2 * inset, D - 2 * inset, z1 - z0,
                          r=max(R - inset, 1.0), loc=(0, 0, z0))
    S.bake(outer)
    i2 = inset + width
    inner = S.rounded_box(name + "_in", W - 2 * i2, D - 2 * i2, z1 - z0 + 2,
                          r=max(R - i2, 0.5), loc=(0, 0, z0 - 1))
    S.cut(outer, inner)
    return outer


def scattering_white():
    m = S.material("PLA white (scattering)", S.PLA["white"], rough=0.5)
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Subsurface Weight"].default_value = 1.0
    b.inputs["Subsurface Radius"].default_value = (1.0, 1.0, 1.0)
    b.inputs["Subsurface Scale"].default_value = 0.0012
    return m


def frosted():
    """Translucent white filament: lets most light through but scatters it."""
    m = S.material("Translucent white (frosted)", (0.95, 0.95, 0.95, 1), rough=0.55)
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Transmission Weight"].default_value = 0.85
    b.inputs["Subsurface Weight"].default_value = 0.4
    b.inputs["Subsurface Radius"].default_value = (1.0, 1.0, 1.0)
    b.inputs["Subsurface Scale"].default_value = 0.003
    b.inputs["IOR"].default_value = 1.5
    return m


def shell_body(name, z0, z1, roof=True):
    sh = S.rounded_box(name, W, D, z1 - z0, r=R, r_top=S.EDGE_R if roof else 0.4,
                       r_bot=0.4, loc=(0, 0, z0))
    S.bake(sh)
    cav_top = z1 - ROOF if roof else z1 + 1
    cav = S.rounded_box("cav", W - 2 * WALL, D - 2 * WALL, cav_top - z0 + 1, r=R - WALL,
                        loc=(0, 0, z0 - 1))
    S.cut(sh, cav)
    return sh


def label(z):
    return S.text("label", "HOME / 01", 4.2, 1.6, loc=(W / 2 - 18, -D / 2 + 18, z),
                  align="RIGHT")


def base_plate(inset=S.SHADOW_GAP, z0=0.0, t=BASE_T):
    b = S.rounded_box("Base", W - 2 * inset, D - 2 * inset, t, r=R - inset, r_bot=0.8,
                      loc=(0, 0, z0))
    S.assign(b, S.pla("black"))
    S.smooth(b)
    return b


def leds(points, z, out_offset=0.0, power=0.004, soft=1.0):
    obs = []
    for k, (x, y, nx, ny) in enumerate(points):
        li = bpy.data.lights.new(f"led{k:03d}", "POINT")
        li.energy = power
        li.color = gradient(k / len(points))
        li.shadow_soft_size = soft / 1000
        ob = bpy.data.objects.new(li.name, li)
        bpy.context.collection.objects.link(ob)
        ob.location = (x + nx * out_offset, y + ny * out_offset, z)
        obs.append(ob)
    return obs


def chamber(inset, width, z0, z1):
    """Black light chamber under a perimeter band, so light can't spill inside the shell."""
    black = S.pla("black")
    walls = band("chamber", inset - 1.2, width + 2.4, z0, z1)
    hollow = band("hollow", inset, width, z0 + 1.2, z1 + 1)
    S.cut(walls, hollow)
    return S.assign(walls, black)


# ---------------------------------------------------------------- concepts
def concept_A():
    """Hidden halo through a 0.6 mm skin; vents in the shadow line."""
    ins, w, skin = 7.0, 6.0, 0.6
    sh = shell_body("Shell", BASE_T + 1.0, TOP)
    S.cut(sh, [band("groove", ins, w, TOP - ROOF - 1, TOP - skin), label(TOP)])
    S.assign(sh, scattering_white())
    S.smooth(sh)
    base = base_plate()
    ch = chamber(ins, w, TOP - skin - 9, TOP - ROOF)
    pts, L = path(ins + w / 2, 48)
    lights = leds(pts, TOP - skin - 6, power=0.0025)
    return [sh, base, ch], lights, "Hidden halo", L


def concept_B():
    """Frosted insert in a perimeter slot; the gaps beside it are the vents."""
    ins, slot_w, insert_w = 7.0, 4.6, 3.0
    sh = shell_body("Shell", BASE_T, TOP)
    S.cut(sh, [band("slot", ins, slot_w, TOP - ROOF - 1, TOP + 1), label(TOP)])
    S.assign(sh, S.pla("white"))
    S.smooth(sh)
    gap = (slot_w - insert_w) / 2
    ins_part = band("Insert", ins + gap, insert_w, TOP - ROOF - 3, TOP - 0.3)
    S.assign(ins_part, frosted())
    base = base_plate()
    ch = chamber(ins, slot_w, TOP - 12, TOP - ROOF - 0.01)
    pts, L = path(ins + slot_w / 2, 48)
    lights = leds(pts, TOP - 8, power=0.006)
    return [sh, ins_part, base, ch], lights, "Light seam", L


def concept_C():
    """Glowing seam round the sides under the top edge; the seam is the vent."""
    seam_z0, seam_z1 = TOP - 9.0, TOP - 6.0
    body = shell_body("Body", BASE_T, seam_z0, roof=False)
    lid = shell_body("Lid", seam_z1, TOP)
    S.cut(lid, [label(TOP)])
    white = S.pla("white")
    for o in (body, lid):
        S.assign(o, white)
        S.smooth(o)
    diff = band("Diffuser", 2.2, 1.6, seam_z0 - 1.0, seam_z1 + 1.0)
    S.assign(diff, frosted())
    base = base_plate()
    pts, L = path(6.0, 52)
    lights = leds(pts, (seam_z0 + seam_z1) / 2, out_offset=0.0, power=0.008)
    return [body, lid, diff, base], lights, "Floating lid", L


def concept_D():
    """Wildcard: shell floats on a small inset base; light washes onto the table."""
    lift = 5.0
    sh = shell_body("Shell", lift, TOP)
    S.cut(sh, [label(TOP)])
    S.assign(sh, S.pla("white"))
    S.smooth(sh)
    base = base_plate(inset=14.0, z0=0.0, t=lift + 1.0)
    pts, L = path(4.0, 52)
    lights = leds(pts, lift + 0.8, power=0.02)
    return [sh, base], lights, "Underglow", L


CONCEPTS = {"A": concept_A, "B": concept_B, "C": concept_C, "D": concept_D}
CAMS = {   # (location, target, lens)
    "A": ((0.19, -0.25, 0.25), (0.0, 0.0, 0.034), 62),
    "B": ((0.19, -0.25, 0.25), (0.0, 0.0, 0.034), 62),
    "C": ((0.22, -0.31, 0.13), (0.0, 0.0, 0.022), 62),
    "D": ((0.22, -0.31, 0.13), (0.0, 0.0, 0.018), 62),
}


def room(dim):
    k = 0.03 if dim else 1.0
    for ob in bpy.data.objects:
        if ob.type == "LIGHT" and ob.data.type == "AREA":
            ob.data.energy = ob["base"] * k
    bpy.context.scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = (
        0.08 * k)


def run(key):
    S.reset()
    objs, lights, title, length = CONCEPTS[key]()
    S.to_studio(objs)
    for li in lights:
        li.location = tuple(c / 1000 for c in li.location)
    S.studio(samples=20 if PREVIEW else 96, res=(800, 600) if PREVIEW else (1280, 960))
    sc = bpy.context.scene
    sc.cycles.max_bounces = 16
    sc.cycles.transmission_bounces = 16
    for ob in bpy.data.objects:
        if ob.type == "LIGHT" and ob.data.type == "AREA":
            ob["base"] = ob.data.energy
    loc, tgt, lens = CAMS[key]
    S.camera(loc, target=tgt, lens=lens)
    os.makedirs(OUT, exist_ok=True)
    suffix = "_preview" if PREVIEW else ""
    for name, dim, on in (("dark", True, True), ("room", False, True), ("off", False, False)):
        if PREVIEW and name != "dark":
            continue
        for li in lights:
            li.hide_render = not on
        room(dim)
        S.render(os.path.join(OUT, f"concept_{key}_{name}{suffix}.png"))
    print(f"CONCEPT {key} {title}: light path {length:.0f} mm, {len(lights)} LEDs")


if __name__ == "__main__":
    only = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")]
    keys = only[0].split(",") if only else list(CONCEPTS)
    for k in keys:
        run(k)
