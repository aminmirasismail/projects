"""Ray-traced study of the rev C halo: 24 RGB LEDs glowing through 0.6 mm of white PLA.

Run:  python light_study.py [--preview] [--anim]
Writes renders/halo_*.png (status stills) and renders/halo_flow.mp4 (animation).

Each LED is a small coloured light at its real position under the roof. The white
shell uses subsurface scattering, so light really diffuses and dims as it passes
through the 0.6 mm skin; the black carrier absorbs whatever hits its walls.
Optical values are estimates; the printed light-test coupon is the real check.

Earlier rev A/B light-pipe studies produced renders/light_*.png (see git history).
"""
import colorsys
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import bpy  # noqa: E402
import hub  # noqa: E402
import studio as S  # noqa: E402

PREVIEW = "--preview" in sys.argv
OUT = os.path.join(HERE, "renders")
LED_W = 0.006       # watts of light per LED at full pattern intensity (~40% drive)


def scattering_white(shell):
    m = S.material("PLA white (scattering)", S.PLA["white"], rough=0.5)
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Subsurface Weight"].default_value = 1.0
    b.inputs["Subsurface Radius"].default_value = (1.0, 1.0, 1.0)
    b.inputs["Subsurface Scale"].default_value = 0.0012     # ~1.2 mm in PLA
    S.assign(shell, m)


def make_leds():
    lights = []
    for k in range(hub.RING_N):
        a = 360.0 * k / hub.RING_N
        x, y = hub._polar(hub.LED_R, a)
        li = bpy.data.lights.new(f"px{k:02d}", "POINT")
        li.shadow_soft_size = 0.0012
        ob = bpy.data.objects.new(f"px{k:02d}", li)
        bpy.context.collection.objects.link(ob)
        ob.location = (x / 1000, y / 1000, (hub.Z_LED_TOP + 0.3) / 1000)
        lights.append(ob)
    return lights


def apply(lights, pattern):
    """pattern: list of 24 (r, g, b, intensity 0..1)."""
    for ob, (r, g, b, i) in zip(lights, pattern):
        ob.data.color = (r, g, b)
        ob.data.energy = LED_W * i
        ob.hide_render = i <= 0.001


def comet(color, head, tail=9):
    n = hub.RING_N
    out = []
    for k in range(n):
        d = (head - k) % n
        i = max(0.0, 1.0 - d / tail) ** 1.6 if d < tail else 0.0
        out.append((*color, i))
    return out


def fill(color, i):
    return [(*color, i)] * hub.RING_N


def progress(color, frac):
    n = hub.RING_N
    return [(*color, 1.0 if k < frac * n else 0.06) for k in range(n)]


def rainbow(phase):
    n = hub.RING_N
    return [(*colorsys.hsv_to_rgb(((k / n) + phase) % 1.0, 1.0, 1.0), 0.8) for k in range(n)]


STATES = [
    ("connecting", comet((0.1, 0.35, 1.0), 6), True),
    ("allgood", fill((1.0, 0.78, 0.55), 0.22), True),
    ("laundry", progress((1.0, 0.45, 0.02), 0.66), True),
    ("alert", fill((1.0, 0.04, 0.02), 0.9), True),
    ("connecting_day", comet((0.1, 0.35, 1.0), 6), False),
    ("off_day", fill((1.0, 1.0, 1.0), 0.0), False),
]


def room(dim):
    k = 0.03 if dim else 1.0
    for ob in bpy.data.objects:
        if ob.type == "LIGHT" and ob.data.type == "AREA":
            ob.data.energy = ob["base"] * k
    bpy.context.scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = (
        0.08 * k)


def main():
    shell, base, carrier = hub.build()
    pcb, leds = hub.led_ring()
    S.to_studio([shell, base, carrier, pcb] + leds)
    S.studio(samples=24 if PREVIEW else 128, res=(800, 600) if PREVIEW else (1400, 1050))
    sc = bpy.context.scene
    sc.cycles.max_bounces = 16
    sc.cycles.transmission_bounces = 16
    for ob in bpy.data.objects:
        if ob.type == "LIGHT":
            ob["base"] = ob.data.energy
    scattering_white(shell)
    lights = make_leds()
    S.camera((0.19, -0.25, 0.25), target=(0.0, 0.0, 0.036), lens=68)
    os.makedirs(OUT, exist_ok=True)

    if "--anim" in sys.argv:
        frames_dir = os.path.join(OUT, "_halo_frames")
        os.makedirs(frames_dir, exist_ok=True)
        sc.cycles.samples = 20
        sc.render.resolution_x, sc.render.resolution_y = 960, 720
        room(True)
        n = 48                                   # two laps of a blue comet, then a colour wash
        for f in range(n):
            apply(lights, comet((0.1, 0.35, 1.0), f % hub.RING_N))
            S.render(os.path.join(frames_dir, f"f_{f:04d}.png"))
        for f in range(n, n + 36):
            apply(lights, rainbow((f - n) / 36.0))
            S.render(os.path.join(frames_dir, f"f_{f:04d}.png"))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "16", "-i",
                        os.path.join(frames_dir, "f_%04d.png"), "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart",
                        os.path.join(OUT, "halo_flow.mp4")], check=True)
        return

    states = STATES[:1] if PREVIEW else STATES
    for name, pattern, dim in states:
        apply(lights, pattern)
        room(dim)
        suffix = "_preview" if PREVIEW else ""
        S.render(os.path.join(OUT, f"halo_{name}{suffix}.png"))


if __name__ == "__main__":
    main()
