"""Home Assistant hub enclosure for a Raspberry Pi 5 with the official Active Cooler.

Run:  python hub.py [--renders] [--turntable]
Writes hub.blend, stl/*.stl and (optionally) renders/*.png + renders/turntable.mp4.

Three printed parts, one colour each (no AMS needed):
  shell  - white PLA, printed upside-down (top face on the plate)
  base   - black PLA, printed flat
  pipe   - red PLA light pipe for the Pi's status LED
Hardware: 4x M3 heat-set inserts + 4x M3x8 countersunk screws, 4x M2.5x6 screws for the Pi.
"""
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import bpy  # noqa: E402
import studio as S  # noqa: E402

# ---------------------------------------------------------------- dimensions (mm)
W, D = 106.0, 78.0          # outer footprint
R = 12.0                    # plan corner radius
BASE_T = 3.0                # black base plate
SHELL_H = 27.0              # white shell height
WALL, ROOF = 2.0, 2.0
TOP = BASE_T + SHELL_H      # 30 mm overall
STANDOFF_H = 4.0
BOARD_Z = BASE_T + STANDOFF_H        # underside of the Pi PCB
PCB_T = 1.6
BOSS = [(sx * 45.0, sy * 32.0) for sx in (-1, 1) for sy in (-1, 1)]


def pi_xy(u, v):
    """Raspberry Pi 5 board coords (u along 85 mm edge from the SD end,
    v along 56 mm from the USB-C edge) -> enclosure XY. The board is rotated so
    Ethernet/USB face -X and USB-C faces +Y (back)."""
    return 35.0 - u, 28.0 - v


PI_HOLES = [pi_xy(u, v) for u in (3.5, 61.5) for v in (3.5, 52.5)]
FAN_C = pi_xy(30.0, 30.0)
USBC = pi_xy(11.2, 0)
LED_Y = 0.0   # status LED height along the SD end; confirm against the real board


def build():
    S.reset()
    white, black, red = S.pla("white"), S.pla("black"), S.pla("red")

    # ------------------------------------------------ shell
    shell = S.rounded_box("Shell", W, D, SHELL_H, r=R, r_top=S.EDGE_R, r_bot=0.4,
                          loc=(0, 0, BASE_T))
    S.bake(shell)
    cavity = S.rounded_box("cavity", W - 2 * WALL, D - 2 * WALL, SHELL_H - ROOF + 1,
                           r=R - WALL, loc=(0, 0, BASE_T - 1))
    S.cut(shell, cavity)

    bosses = []
    for x, y in BOSS:
        b = S.cylinder("boss", 7, TOP - ROOF - BASE_T + 0.5,
                       loc=(x, y, (BASE_T + TOP - ROOF + 0.5) / 2))
        bosses.append(b)
    S.union(shell, bosses)

    cutters = []
    # heat-set insert holes in the bosses
    for x, y in BOSS:
        cutters.append(S.cylinder("insert", 4.2, 12, loc=(x, y, BASE_T + 5)))
    # Ethernet + 2x USB opening on the -X end
    cutters.append(S.slot("ports", 54, 18, 10, loc=(-W / 2, 0.5, BOARD_Z + PCB_T + 8.4),
                          axis="X", r=3))
    # USB-C power on the back
    cutters.append(S.slot("usbc", 12, 7, 10, loc=(USBC[0], D / 2, BOARD_Z + PCB_T + 1.8),
                          axis="Y"))
    # light-pipe hole on the +X end (SD-card end, where the Pi's LEDs sit)
    cutters.append(S.cylinder("pipe_hole", 4.2, 10, loc=(W / 2, LED_Y, BOARD_Z + 4),
                              rot=(0, math.pi / 2, 0)))
    # dot-grid vent over the fan
    pitch, rad = 4.6, 17.5
    n = int(rad // pitch) + 1
    vents = []
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            x, y = i * pitch, j * pitch
            if math.hypot(x, y) <= rad:
                vents.append(S.cylinder("vent", 2.4, 6, loc=(FAN_C[0] + x, FAN_C[1] + y, TOP),
                                        seg=20))
    cutters.append(S.join(vents, "vents"))
    # debossed label, front-right of the roof
    lbl = S.text("label", "HOME / 01", 3.6, 1.2, loc=(W / 2 - 14, -D / 2 + 9, TOP - 0.5),
                 align="RIGHT")
    cutters.append(lbl)
    S.cut(shell, cutters)
    S.assign(shell, white)
    S.smooth(shell)

    # ------------------------------------------------ base
    g = S.SHADOW_GAP
    base = S.rounded_box("Base", W - 2 * g, D - 2 * g, BASE_T, r=R - g, r_bot=0.8)
    stand = [S.cylinder("standoff", 6, STANDOFF_H + 0.5,
                        loc=(x, y, BASE_T + STANDOFF_H / 2 - 0.25)) for x, y in PI_HOLES]
    # a locating lip that keys into the shell cavity
    lip = S.rounded_box("lip", W - 2 * WALL - 0.4, D - 2 * WALL - 0.4, 1.6,
                        r=R - WALL - 0.2, loc=(0, 0, BASE_T - 0.01))
    lip_in = S.rounded_box("lip_in", W - 2 * WALL - 3.6, D - 2 * WALL - 3.6, 3,
                           r=R - WALL - 1.8, loc=(0, 0, BASE_T - 0.5))
    S.cut(lip, lip_in)
    S.union(base, stand + [lip])
    holes = []
    for x, y in PI_HOLES:
        holes.append(S.cylinder("m25", 2.3, 10, loc=(x, y, BASE_T + 3)))
    for x, y in BOSS:
        holes.append(S.cylinder("m3", 3.4, 10, loc=(x, y, 0)))
        bpy.ops.mesh.primitive_cone_add(vertices=40, radius1=3.4, radius2=1.7, depth=1.7,
                                        location=(x, y, 0.85 - 0.01))
        holes.append(bpy.context.active_object)
    # lip must clear the bosses
    for x, y in BOSS:
        holes.append(S.cylinder("boss_clear", 8, 4, loc=(x, y, BASE_T + 1)))
    S.cut(base, holes)
    S.assign(base, black)
    S.smooth(base)

    # ------------------------------------------------ light pipe (red)
    pipe = S.cylinder("Pipe", 4.0, WALL + 2.0, loc=(W / 2 - (WALL + 2.0) / 2 + 0.3, LED_Y,
                                                     BOARD_Z + 4), rot=(0, math.pi / 2, 0))
    collar = S.cylinder("collar", 6.0, 0.8, loc=(W / 2 - WALL - 0.4, LED_Y, BOARD_Z + 4),
                        rot=(0, math.pi / 2, 0))
    S.union(pipe, collar)
    S.assign(pipe, S.material("PLA red lit", S.PLA["red"], rough=0.4,
                              emission=(1, 0.02, 0.01, 1), strength=0.35))
    S.smooth(pipe)

    return shell, base, pipe


def pi_mock():
    """Rough Raspberry Pi 5 + Active Cooler, for fit checks and the exploded view."""
    pcb = S.material("PCB", (0.02, 0.18, 0.08, 1), rough=0.35, coat=0.6)
    metal = S.material("Steel", (0.75, 0.75, 0.76, 1), rough=0.25)
    S.material("Steel", (0.75, 0.75, 0.76, 1), rough=0.25).node_tree.nodes[
        "Principled BSDF"].inputs["Metallic"].default_value = 1.0
    fan = S.material("Fan", (0.03, 0.03, 0.035, 1), rough=0.4)
    z = BOARD_Z
    parts = []
    b = S.rounded_box("pcb", 85, 56, PCB_T, r=3, loc=(*pi_xy(42.5, 28), z))
    parts.append(S.assign(b, pcb))
    for v, w, h, nm in ((9, 13.5, 15.6, "usb"), (27, 13.5, 15.6, "usb"), (45.75, 16, 13.5, "eth")):
        x, y = pi_xy(85 - 21 / 2 + 2.2, v)
        p = S.box(nm, 21, w, h, loc=(x, y, z + PCB_T + h / 2))
        parts.append(S.assign(p, metal))
    x, y = USBC
    parts.append(S.assign(S.box("usbc", 9, 7.5, 3.2, loc=(x, y - 3, z + PCB_T + 1.6)), metal))
    for u in (25.8, 39.2):
        x, y = pi_xy(u, 0)
        parts.append(S.assign(S.box("hdmi", 6.5, 7.5, 3, loc=(x, y - 3, z + PCB_T + 1.5)), metal))
    hs = S.rounded_box("cooler", 52, 38, 7, r=1.5, loc=(FAN_C[0] - 2, FAN_C[1], z + PCB_T + 2.5))
    parts.append(S.assign(hs, S.material("Alu", (0.55, 0.57, 0.6, 1), rough=0.35)))
    f = S.cylinder("fan", 28, 2.5, loc=(FAN_C[0], FAN_C[1], z + PCB_T + 10.6))
    parts.append(S.assign(f, fan))
    return S.join(parts, "Pi5 (reference)")


def main():
    args = sys.argv[1:]
    shell, base, pipe = build()
    os.makedirs(os.path.join(HERE, "stl"), exist_ok=True)
    S.export_stl(shell, os.path.join(HERE, "stl", "hub_shell_white.stl"))
    S.export_stl(base, os.path.join(HERE, "stl", "hub_base_black.stl"))
    S.export_stl(pipe, os.path.join(HERE, "stl", "hub_lightpipe_red.stl"))
    pi = pi_mock()

    root = S.to_studio([shell, base, pipe, pi])
    S.studio()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "hub.blend"))
    if "--renders" not in args and "--turntable" not in args:
        return

    out = os.path.join(HERE, "renders")
    os.makedirs(out, exist_ok=True)
    sc = bpy.context.scene
    if "--renders" in args:
        pi.hide_render = True
        S.camera((0.25, -0.33, 0.18))
        S.render(os.path.join(out, "hub_hero.png"))
        S.camera((-0.30, 0.27, 0.15), lens=85)
        pi.hide_render = False
        S.render(os.path.join(out, "hub_ports.png"))
        pi.hide_render = True
        S.camera((0.10, -0.16, 0.50), target=(0.0, 0.0, 0.02), lens=80)
        S.render(os.path.join(out, "hub_top.png"))
        # exploded
        pi.hide_render = False
        shell.location.z += 42
        pipe.location.z += 42
        pipe.location.x += 14
        pi.location.z += 16
        S.camera((0.42, -0.58, 0.36), target=(0, 0, 0.04), lens=70)
        S.render(os.path.join(out, "hub_exploded.png"))
        shell.location.z -= 42
        pipe.location.z -= 42
        pipe.location.x -= 14
        pi.location.z -= 16
        pi.hide_render = True
    if "--turntable" in args:
        pi.hide_render = True
        frames = 96
        sc.frame_start, sc.frame_end = 1, frames
        root.rotation_euler = (0, 0, 0)
        root.keyframe_insert("rotation_euler", index=2, frame=1)
        root.rotation_euler = (0, 0, 2 * math.pi)
        root.keyframe_insert("rotation_euler", index=2, frame=frames + 1)
        for fc in root.animation_data.action.layers[0].strips[0].channelbag(
                root.animation_data.action.slots[0]).fcurves:
            for k in fc.keyframe_points:
                k.interpolation = "LINEAR"
        S.camera((0.0, -0.56, 0.22), target=(0, 0, 0.014))
        sc.cycles.samples = 32
        sc.render.resolution_x, sc.render.resolution_y = 1200, 800
        frames_dir = os.path.join(out, "_frames")
        os.makedirs(frames_dir, exist_ok=True)
        sc.render.image_settings.file_format = "PNG"
        sc.render.filepath = os.path.join(frames_dir, "f_")
        bpy.ops.render.render(animation=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "24", "-i",
                        os.path.join(frames_dir, "f_%04d.png"), "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart",
                        os.path.join(out, "hub_turntable.mp4")], check=True)


if __name__ == "__main__":
    main()
