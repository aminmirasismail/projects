"""Underglow study for the hub (v4, no corner LEDs): how the light looks on real surfaces.

Run:  python underglow_study.py [--preview] [--gradient] [--nohang] [--only=wood:dim,...]
Writes renders/glow_<surface>_<room>[_grad][_nohang].png for surface in (wood, quartz) and
room in (dark, dim, bright).

Same LED output in every image: about 4.5 lm per LED at the 0.5 A power cap, modelled as
0.015 W of light per LED. Warm white (~3000 K) by default; --gradient programs each LED
with its own colour, orange -> blue -> orange round the chain, as the firmware would.
--nohang renders without the lining's hang and inward floor, for comparison.
Same camera and exposure in every image, so brightness compares honestly between rooms.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import bpy  # noqa: E402
import hub as H  # noqa: E402
import studio as S  # noqa: E402

PREVIEW = "--preview" in sys.argv
GRADIENT = "--gradient" in sys.argv
NOHANG = "--nohang" in sys.argv
ONLY = [a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")]
BLUE, ORANGE = (0.08, 0.32, 1.0), (1.0, 0.42, 0.03)
LED_W = 0.015
WARM_LED = (1.0, 0.71, 0.42)            # ~3000 K
ROOMS = {   # studio light scale, world strength, light tint
    "dark": (0.02, 0.004, (1.0, 0.85, 0.7)),
    "dim": (0.15, 0.03, (1.0, 0.72, 0.45)),       # evening lamps, ~2700 K
    "bright": (1.0, 0.25, (1.0, 0.98, 0.95)),     # ordinary bright room
}


def wood():
    """Lacquered light-oak veneer: banded grain with fine noise, satin clear coat."""
    m = bpy.data.materials.new("Oak veneer")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (0.6, 14.0, 1.0)         # long, fine grain along X
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type, wave.bands_direction = "BANDS", "Y"
    wave.inputs["Scale"].default_value = 6.0
    wave.inputs["Distortion"].default_value = 14.0
    wave.inputs["Detail"].default_value = 4.0
    wave.inputs["Detail Scale"].default_value = 1.5
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 400.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.36, 0.24, 0.14, 1)
    ramp.color_ramp.elements[1].color = (0.46, 0.33, 0.21, 1)
    mix = nt.nodes.new("ShaderNodeMath")
    mix.operation = "MULTIPLY_ADD"
    mix.inputs[1].default_value = 0.55
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], wave.inputs["Vector"])
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    nt.links.new(wave.outputs["Fac"], mix.inputs[0])
    nt.links.new(noise.outputs["Fac"], mix.inputs[2])
    nt.links.new(mix.outputs[0], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.6           # satin lacquer, not piano gloss
    b.inputs["Coat Weight"].default_value = 0.25
    b.inputs["Coat Roughness"].default_value = 0.45
    return m


def quartz():
    """Cream engineered quartz: fine grey and amber flecks, polished."""
    m = bpy.data.materials.new("Cream quartz")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 350.0
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 18.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.55, 0.52, 0.47, 1)     # flecks
    ramp.color_ramp.elements[1].position = 0.12
    ramp.color_ramp.elements[1].color = (0.82, 0.78, 0.69, 1)     # cream body
    mix = nt.nodes.new("ShaderNodeMath")
    mix.operation = "MULTIPLY_ADD"
    mix.inputs[1].default_value = 0.08
    nt.links.new(tc.outputs["Object"], vor.inputs["Vector"])
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    nt.links.new(vor.outputs["Distance"], mix.inputs[0])
    nt.links.new(noise.outputs["Fac"], mix.inputs[2])
    nt.links.new(mix.outputs[0], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.4           # honed, as most counters age to
    return m


def table(mat):
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0.05, 0.00002))
    t = bpy.context.active_object
    t.name = "Table"
    t.scale = (0.9, 0.6, 1)
    S.bake(t)
    t.data.materials.append(mat)
    return t


def gradient(t):
    """Seamless orange -> blue -> orange round the loop: what each LED is programmed to."""
    k = 0.5 - 0.5 * math.cos(2 * math.pi * t)
    return tuple(o + (b - o) * k for o, b in zip(ORANGE, BLUE))


def leds():
    obs = []
    pos = H.led_positions()
    for k, (x, y, _) in enumerate(pos):
        li = bpy.data.lights.new(f"glow{k:02d}", "POINT")
        li.energy = LED_W
        li.color = gradient(k / len(pos)) if GRADIENT else WARM_LED
        li.shadow_soft_size = 0.002
        ob = bpy.data.objects.new(li.name, li)
        bpy.context.collection.objects.link(ob)
        ob.location = (x / 1000, y / 1000, (H.Z_LED_FACE - 0.3) / 1000)
        obs.append(ob)
    return obs


def room(name):
    k, world, tint = ROOMS[name]
    for ob in bpy.data.objects:
        if ob.type == "LIGHT" and ob.data.type == "AREA":
            ob.data.energy = ob["base"] * k
            ob.data.color = tuple(a * b for a, b in zip(ob["base_col"], tint))
    bg = bpy.context.scene.world.node_tree.nodes["Background"]
    bg.inputs["Strength"].default_value = world
    bg.inputs["Color"].default_value = (*(0.5 * t for t in tint), 1)


def main():
    if NOHANG:
        H.LINING_Z, H.FLANGE = H.LIFT + 0.3, 0.0
    shell, floor, plinth = H.build()
    S.to_studio([shell, floor, plinth])
    S.studio(samples=24 if PREVIEW else 160, res=(800, 600) if PREVIEW else (1400, 1050))
    sc = bpy.context.scene
    sc.cycles.max_bounces = 12
    for ob in bpy.data.objects:
        if ob.type == "LIGHT" and ob.data.type == "AREA":
            ob["base"], ob["base_col"] = ob.data.energy, tuple(ob.data.color)
    leds()
    out = os.path.join(HERE, "renders", "_preview" if PREVIEW else "")
    os.makedirs(out, exist_ok=True)
    S.camera((0.22, -0.31, 0.13), target=(0.0, 0.0, 0.016), lens=58)
    for surf, mat in (("wood", wood()), ("quartz", quartz())):
        t = table(mat)
        for name in ROOMS:
            if ONLY and f"{surf}:{name}" not in ONLY[0]:
                continue
            room(name)
            tag = ("_grad" if GRADIENT else "") + ("_nohang" if NOHANG else "")
            S.render(os.path.join(out, f"glow_{surf}_{name}{tag}.png"))
        bpy.data.objects.remove(t, do_unlink=True)


if __name__ == "__main__":
    main()
