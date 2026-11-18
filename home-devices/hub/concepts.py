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
DAY_W = 0.02        # watts of light per LED in room-light renders, same for every concept


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


LIFT = 5.0          # D-style float: shell 5 mm off the table on a small hidden base
SKIN_V = 0.8        # vertical thin skin (two extrusion lines); the coupon test will confirm


def skin_band(name, skin, z0, z1, outer=0.0):
    """Cutter that thins the side wall from the inside to `skin`, leaving the outside
    surface (at inset `outer`) intact."""
    return band(name, outer + skin, WALL - outer - skin + 0.6, z0, z1)


def liner(z0, z1, window=None):
    """Black lining against the inside of the white wall, so the strip's light only
    leaves through the intended window (z range) and not through the whole wall."""
    lin = band("liner", WALL + 0.05, 0.8, z0, z1)
    if window:
        S.cut(lin, [band("liner_win", WALL - 0.5, 2.0, window[0], window[1])])
    return S.assign(lin, S.pla("black"))


def baffle(inset, z0, z1, cap_top=None, cap_bot=None):
    """Black inner wall plus horizontal caps, boxing the strip in against the side wall."""
    black = S.pla("black")
    parts = [band("baffle", inset, 1.2, z0, z1)]
    if cap_top is not None:
        parts.append(band("cap_t", WALL - 0.2, inset + 1.2 - WALL + 0.2, cap_top - 1.2, cap_top))
    if cap_bot is not None:
        parts.append(band("cap_b", WALL - 0.2, inset + 1.2 - WALL + 0.2, cap_bot, cap_bot + 1.2))
    b = parts[0]
    if len(parts) > 1:
        S.union(b, parts[1:])
    return S.assign(b, black)


def under_channel():
    """Black channel boxing in the underglow strip: open only downward, so the light
    reaches the table but not the inside of the white shell."""
    b = baffle(7.0, LIFT - 0.5, LIFT + 5.2, cap_top=LIFT + 5.2)
    S.union(b, [liner(LIFT + 0.6, LIFT + 5.2)])      # open only at the very bottom edge
    return b


def concept_E():
    """Glow hem: the lowest 8 mm of the wall thins to a skin; one strip behind it lights
    the skin and spills out under the floating shell onto the table."""
    sh = shell_body("Shell", LIFT, TOP)
    S.cut(sh, [skin_band("hem", SKIN_V, LIFT + 1.5, LIFT + 9.5), label(TOP)])
    S.assign(sh, scattering_white())
    S.smooth(sh)
    base = base_plate(inset=14.0, z0=0.0, t=LIFT + 1.0)
    bf = baffle(8.0, LIFT - 1.0, LIFT + 11.0, cap_top=LIFT + 11.0)
    pts, L = path(5.0, 52)
    lights = leds(pts, LIFT + 4.5, power=0.0035)
    return [sh, base, bf], lights, "Glow hem", L


def concept_F():
    """Reveal line + underglow: C's floating-lid line made as a shallow groove whose
    floor is a thin skin (no translucent filament), plus D's underglow."""
    z0, z1, groove = TOP - 9.0, TOP - 6.0, 0.8
    sh = shell_body("Shell", LIFT, TOP)
    S.cut(sh, [band("reveal", -1.0, 1.0 + groove, z0, z1),                 # outside groove
               skin_band("reveal_skin", SKIN_V, z0 - 1.0, z1 + 1.0, outer=groove),
               label(TOP)])
    S.assign(sh, scattering_white())
    S.smooth(sh)
    base = base_plate(inset=14.0, z0=0.0, t=LIFT + 1.0)
    bf = baffle(8.0, z0 - 4.0, TOP - ROOF, cap_top=TOP - ROOF, cap_bot=z0 - 4.0)
    S.union(bf, [liner(z0 - 4.0, TOP - ROOF, window=(z0, z1))])
    uc = under_channel()
    top_pts, L = path(5.0, 52)
    lights = leds(top_pts, (z0 + z1) / 2, power=0.005)
    low_pts, _ = path(4.0, 52)
    lights += leds(low_pts, LIFT + 0.8, power=0.02)
    return [sh, base, bf, uc], lights, "Reveal line + underglow", L


def concept_G():
    """Floating lid (translucent ring, as C) + underglow (as D)."""
    seam_z0, seam_z1 = TOP - 9.0, TOP - 6.0
    body = shell_body("Body", LIFT, seam_z0, roof=False)
    lid = shell_body("Lid", seam_z1, TOP)
    S.cut(lid, [label(TOP)])
    white = scattering_white()
    for o in (body, lid):
        S.assign(o, white)
        S.smooth(o)
    diff = band("Diffuser", 2.2, 1.6, seam_z0 - 1.0, seam_z1 + 1.0)
    S.assign(diff, frosted())
    base = base_plate(inset=14.0, z0=0.0, t=LIFT + 1.0)
    bf = baffle(8.0, seam_z0 - 3.0, TOP - ROOF, cap_top=TOP - ROOF, cap_bot=seam_z0 - 3.0)
    S.union(bf, [liner(seam_z0 - 3.0, TOP - ROOF, window=(seam_z0 - 0.5, seam_z1 + 0.5))])
    uc = under_channel()
    top_pts, L = path(6.0, 52)
    lights = leds(top_pts, (seam_z0 + seam_z1) / 2, power=0.008)
    low_pts, _ = path(4.0, 52)
    lights += leds(low_pts, LIFT + 0.8, power=0.02)
    return [body, lid, diff, base, bf, uc], lights, "Floating lid + underglow", L


CONCEPTS = {"A": concept_A, "B": concept_B, "C": concept_C, "D": concept_D,
            "E": concept_E, "F": concept_F, "G": concept_G}
LOW = ((0.22, -0.31, 0.13), (0.0, 0.0, 0.020), 62)
CAMS = {   # (location, target, lens)
    "A": ((0.19, -0.25, 0.25), (0.0, 0.0, 0.034), 62),
    "B": ((0.19, -0.25, 0.25), (0.0, 0.0, 0.034), 62),
    "C": ((0.22, -0.31, 0.13), (0.0, 0.0, 0.022), 62),
    "D": ((0.22, -0.31, 0.13), (0.0, 0.0, 0.018), 62),
    "E": LOW, "F": LOW, "G": LOW,
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
    states = (("dark", True, True), ("room", False, True), ("off", False, False))
    pick = [a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--states=")]
    night = [li.data.energy for li in lights]
    for name, dim, on in states:
        if PREVIEW and name != "dark" or pick and name not in pick[0]:
            continue
        for li, e in zip(lights, night):
            li.hide_render = not on
            # dark room: per-concept night level (software dims to suit each diffuser);
            # room light: the same realistic daytime output (~40% drive) for every concept
            li.data.energy = e if dim else DAY_W
        room(dim)
        S.render(os.path.join(OUT, f"concept_{key}_{name}{suffix}.png"))
    print(f"CONCEPT {key} {title}: light path {length:.0f} mm, {len(lights)} LEDs")


if __name__ == "__main__":
    only = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")]
    keys = only[0].split(",") if only else list(CONCEPTS)
    for k in keys:
        run(k)
