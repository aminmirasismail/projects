"""Ray-traced study of how the red light pipe would actually glow.

Run:  python light_study.py [--preview]
Writes renders/light_*.png. Uses Cycles subsurface scattering so light really
travels through (and gets absorbed by) the plastic, rather than faking a glow.

Rev A's study (Pi's own LED vs a dedicated LED vs translucent filament) produced
renders/light_a_*, light_b_*, light_c_*; that geometry is in git history. The current
script renders rev B: the dedicated LED in its socket, in a dim room and in room light.

Optical values are estimates: regular pigmented PLA scatters and absorbs light
within roughly 1 mm; translucent filament lets most of it through. A 10-minute
test print photographed in a dark room is the way to calibrate these.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import bpy  # noqa: E402
import hub  # noqa: E402
import studio as S  # noqa: E402

PREVIEW = "--preview" in sys.argv
OUT = os.path.join(HERE, "renders")


def principled(mat):
    return mat.node_tree.nodes["Principled BSDF"]


def set_white_translucent(shell):
    m = S.material("PLA white (scattering)", S.PLA["white"], rough=0.5)
    b = principled(m)
    b.inputs["Subsurface Weight"].default_value = 1.0
    b.inputs["Subsurface Radius"].default_value = (1.0, 1.0, 1.0)
    b.inputs["Subsurface Scale"].default_value = 0.0012   # ~1.2 mm, scene is in metres
    S.assign(shell, m)


def red_opaque():
    m = S.material("PLA red (pigmented)", (0.62, 0.025, 0.02, 1), rough=0.45)
    b = principled(m)
    b.inputs["Subsurface Weight"].default_value = 1.0
    b.inputs["Subsurface Radius"].default_value = (1.0, 0.08, 0.06)
    b.inputs["Subsurface Scale"].default_value = 0.0012
    return m


def red_translucent():
    m = S.material("PLA red (translucent)", (0.9, 0.06, 0.04, 1), rough=0.25)
    b = principled(m)
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["IOR"].default_value = 1.46
    return m


def led(name, loc_mm, power_w, kind="POINT", aim=None, radius_mm=0.4, spot_deg=30):
    li = bpy.data.lights.new(name, kind)
    li.energy = power_w
    li.color = (1.0, 0.05, 0.02)
    li.shadow_soft_size = radius_mm / 1000
    if kind == "SPOT":
        li.spot_size = math.radians(spot_deg)
        li.spot_blend = 0.6
    ob = bpy.data.objects.new(name, li)
    bpy.context.collection.objects.link(ob)
    ob.location = tuple(c / 1000 for c in loc_mm)
    if aim:
        from mathutils import Vector
        ob.rotation_euler = Vector(aim).to_track_quat("-Z", "Y").to_euler()
    return ob


def room(dim):
    """Scale the studio lights: dim = an evening room with one lamp across the room."""
    k = 0.03 if dim else 1.0
    for ob in bpy.data.objects:
        if ob.type == "LIGHT" and ob.data.type == "AREA":
            ob.data.energy = ob["base"] * k
    bpy.context.scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = (
        0.08 * k)


def main():
    """Rev B: a 5 mm LED in the printed socket, tip against the pipe's collar."""
    shell, base, pipe = hub.build()
    S.to_studio([shell, base, pipe])
    S.studio(samples=24 if PREVIEW else 128, res=(800, 600) if PREVIEW else (1400, 1050))
    sc = bpy.context.scene
    sc.cycles.max_bounces = 16
    sc.cycles.transmission_bounces = 16
    for ob in bpy.data.objects:
        if ob.type == "LIGHT":
            ob["base"] = ob.data.energy
    set_white_translucent(shell)
    S.assign(pipe, red_opaque())

    m = 0.001
    S.camera((hub.PIPE_X * m + 0.045, -0.15, 0.055),
             target=(hub.PIPE_X * m, -hub.D / 2 * m, hub.PIPE_Z * m), lens=70)
    # light leaves the LED's dome about 1.5 mm behind its tip, aimed out through the pipe
    own_led = led("5 mm LED", (hub.PIPE_X, hub.Y_IN + hub.COLLAR_T + 1.5, hub.PIPE_Z), 0.03,
                  kind="SPOT", aim=(0, -1, 0), radius_mm=2.0)
    variants = [("revb_lit", [own_led], True), ("revb_room", [own_led], False)]
    if PREVIEW:
        variants = variants[:1]
    os.makedirs(OUT, exist_ok=True)
    for name, lights, dim in variants:
        own_led.hide_render = own_led not in lights
        room(dim)
        suffix = "_preview" if PREVIEW else ""
        S.render(os.path.join(OUT, f"light_{name}{suffix}.png"))


if __name__ == "__main__":
    main()
