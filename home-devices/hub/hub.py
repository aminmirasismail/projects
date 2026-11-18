"""Home Assistant hub enclosure for a Raspberry Pi 5 + official Active Cooler. Rev B.

Run:  python hub.py [--renders] [--details] [--drawings] [--turntable]
Writes hub.blend, stl/*.stl, and optionally renders/*.png plus drawing data.

Printed parts (one colour each, no AMS needed):
  shell  - white PLA, printed upside-down (roof on the plate)
  base   - black PLA, printed flat
  pipe   - red PLA light pipe, printed standing on its collar
Bought parts: 4x M3 heat-set inserts (M3 x 5.7, OD 4.6), 4x M3x8 countersunk screws,
4x M2.5x6 screws, 5 mm diffused red LED, 330 ohm resistor, 2-pin Dupont lead, 4x 8 mm feet.
"""
import json
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import bpy  # noqa: E402
import studio as S  # noqa: E402

REV = "B"

# ---------------------------------------------------------------- enclosure (mm)
W, D = 106.0, 80.0          # outer footprint
R = 12.0                    # plan corner radius
BASE_T = 3.0                # black base plate
TOP = 34.0                  # overall height
SHELL_H = TOP - BASE_T
WALL, ROOF = 2.0, 2.0
STANDOFF_H = 4.0
BOARD_Z = BASE_T + STANDOFF_H        # underside of the Pi PCB
PCB_T = 1.6
BOARD_TOP = BOARD_Z + PCB_T

# Heat-set inserts: CNC Kitchen / Ruthex standard M3 x 5.7 mm, OD 4.6 mm.
# Maker guidance: 4.0 mm hole, depth >= insert length + 1 mm, wall >= ~2 mm around it.
INSERT_HOLE_D, INSERT_HOLE_DEPTH = 4.0, 8.0
BOSS_D = 9.0
BOSS = [(sx * 36.0, sy * (D / 2 - WALL - BOSS_D / 2 + 0.3)) for sx in (-1, 1) for sy in (-1, 1)]

# ---------------------------------------------------------------- Raspberry Pi 5 data
# Board coords: u along the 85 mm edge from the SD-card end, v along 56 mm from the
# USB-C edge. PROVISIONAL: values from memory of the Pi 5 drawing; replace with the
# official mechanical drawing (RP-008347) before printing.
PI = {
    "source": "provisional (to verify against RP-008347)",
    "holes_u": (3.5, 61.5), "holes_v": (3.5, 52.5),
    "usbc_u": 11.2, "usbc_overhang": 1.2,
    "hdmi_u": (25.8, 39.2),
    # (name, v_centre, width along edge, height above PCB, depth into board, overhang)
    "ports": [("eth", 10.2, 15.9, 13.5, 21.3, 2.4),
              ("usb3", 29.1, 13.1, 15.6, 17.4, 2.0),
              ("usb2", 47.0, 13.1, 15.6, 17.4, 2.0)],
    "header_pin1_u": 8.37, "header_v": 52.5, "pitch": 2.54,
}


def pi_xy(u, v):
    """Board coords -> enclosure XY. Board is rotated so Ethernet/USB face -X, USB-C +Y."""
    return 35.0 - u, 28.0 - v


def header_pin_xy(n):
    """Physical pin number (1-40) -> XY. Odd pins are on the inner row."""
    col = (n - 1) // 2
    u = PI["header_pin1_u"] + col * PI["pitch"]
    v = PI["header_v"] - 1.27 if n % 2 else PI["header_v"] + 1.27
    return pi_xy(u, v)


PI_HOLES = [pi_xy(u, v) for u in PI["holes_u"] for v in PI["holes_v"]]
FAN_C = pi_xy(30.0, 27.0)
USBC = pi_xy(PI["usbc_u"], 0)

# Port window on the -X end, sized from the port list with 1 mm clearance all round.
_vs = [(v - w / 2, v + w / 2) for _, v, w, _, _, _ in PI["ports"]]
_ys = sorted([28.0 - a for a, b in _vs] + [28.0 - b for a, b in _vs])
PORT_WIN = {"y0": _ys[0] - 1.0, "y1": _ys[-1] + 1.0,
            "z0": BOARD_TOP - 1.0, "z1": BOARD_TOP + max(p[3] for p in PI["ports"]) + 1.0}
USBC_SLOT = (13.0, 7.5)      # w x h, sized for the plug's moulded grip, not just the metal

# ---------------------------------------------------------------- light pipe + LED
PIPE_X, PIPE_Z = 24.0, (BASE_T + TOP) / 2      # centred on the white face's height
PIPE_D, PIPE_HOLE_D = 4.0, 4.1
COLLAR_D, COLLAR_T = 5.0, 0.8
LED_D, LED_FLANGE_D, LED_BODY_L = 5.0, 5.8, 7.5   # standard 5 mm LED, flange 1 mm
SOCKET_ID, SOCKET_OD = 5.15, 7.6
Y_IN = -D / 2 + WALL                           # inner face of the front wall
SOCKET_L = COLLAR_T + LED_BODY_L               # LED tip meets collar, flange meets socket end
LED_PINS = {"gnd": 9, "gpio17": 11}


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

    adds = []
    for x, y in BOSS:
        h = TOP - ROOF - BASE_T + 0.5
        adds.append(S.cylinder("boss", BOSS_D, h, loc=(x, y, BASE_T + h / 2)))
    # LED socket, fused to the inside of the front wall behind the light pipe
    adds.append(S.cylinder("socket", SOCKET_OD, SOCKET_L + 0.4,
                           loc=(PIPE_X, Y_IN + (SOCKET_L - 0.4) / 2, PIPE_Z),
                           rot=(math.pi / 2, 0, 0)))
    S.union(shell, adds)

    cutters = []
    for x, y in BOSS:
        cutters.append(S.cylinder("insert", INSERT_HOLE_D, INSERT_HOLE_DEPTH + 1,
                                  loc=(x, y, BASE_T + (INSERT_HOLE_DEPTH - 1) / 2)))
    pw = PORT_WIN
    cutters.append(S.slot("ports", pw["y1"] - pw["y0"], pw["z1"] - pw["z0"], 10,
                          loc=(-W / 2, (pw["y0"] + pw["y1"]) / 2, (pw["z0"] + pw["z1"]) / 2),
                          axis="X", r=2.5))
    cutters.append(S.slot("usbc", *USBC_SLOT, 10, loc=(USBC[0], D / 2, BOARD_TOP + 1.6),
                          axis="Y"))
    cutters.append(S.cylinder("pipe_hole", PIPE_HOLE_D, WALL * 3, loc=(PIPE_X, -D / 2, PIPE_Z),
                              rot=(math.pi / 2, 0, 0)))
    cutters.append(S.cylinder("socket_bore", SOCKET_ID, SOCKET_L + 1,
                              loc=(PIPE_X, Y_IN + (SOCKET_L + 1) / 2, PIPE_Z),
                              rot=(math.pi / 2, 0, 0)))
    # hexagonal vent field over the fan
    pitch, rad, hole = 3.9, 17.0, 2.2
    vents = []
    rows = int(rad / (pitch * 0.866)) + 1
    for j in range(-rows, rows + 1):
        y = j * pitch * 0.866
        off = pitch / 2 if j % 2 else 0
        for i in range(-8, 9):
            x = i * pitch + off
            if math.hypot(x, y) <= rad:
                vents.append(S.cylinder("vent", hole, 6, loc=(FAN_C[0] + x, FAN_C[1] + y, TOP),
                                        seg=20))
    cutters.append(S.join(vents, "vents"))
    lbl = S.text("label", "HOME / 01", 4.2, 1.6, loc=(W / 2 - 15, -D / 2 + 10, TOP),
                 align="RIGHT")   # 0.8 mm deep
    cutters.append(lbl)
    S.cut(shell, cutters)
    S.assign(shell, white)
    S.smooth(shell)

    # ------------------------------------------------ base
    g = S.SHADOW_GAP
    base = S.rounded_box("Base", W - 2 * g, D - 2 * g, BASE_T, r=R - g, r_bot=0.8)
    stand = [S.cylinder("standoff", 6, STANDOFF_H + 0.5,
                        loc=(x, y, BASE_T + STANDOFF_H / 2 - 0.25)) for x, y in PI_HOLES]
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
        bpy.ops.mesh.primitive_cone_add(vertices=40, radius1=3.1, radius2=1.7, depth=1.4,
                                        location=(x, y, 0.7 - 0.01))
        holes.append(bpy.context.active_object)
        holes.append(S.cylinder("boss_clear", BOSS_D + 1.0, 4, loc=(x, y, BASE_T + 1)))
    for sx in (-1, 1):
        for sy in (-1, 1):
            holes.append(S.cylinder("foot", 8.6, 1.2, loc=(sx * 40, sy * 22, 0)))
    S.cut(base, holes)
    S.assign(base, black)
    S.smooth(base)

    # ------------------------------------------------ light pipe (red)
    pipe = S.cylinder("Pipe", PIPE_D, WALL, loc=(PIPE_X, -D / 2 + WALL / 2, PIPE_Z),
                      rot=(math.pi / 2, 0, 0))
    collar = S.cylinder("collar", COLLAR_D, COLLAR_T, loc=(PIPE_X, Y_IN + COLLAR_T / 2, PIPE_Z),
                        rot=(math.pi / 2, 0, 0))
    S.union(pipe, collar)
    S.assign(pipe, red)
    S.smooth(pipe)
    return shell, base, pipe


def _curve(name, pts, radius, mat):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 4
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts):
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    ob = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return ob


def led_harness():
    """5 mm LED in its socket, 330 ohm resistor on the anode leg, wires to pins 9 and 11."""
    led_mat = S.material("LED epoxy (diffused red)", (0.75, 0.05, 0.04, 1), rough=0.35)
    b = led_mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Subsurface Weight"].default_value = 0.6
    b.inputs["Subsurface Radius"].default_value = (1.0, 0.1, 0.1)
    b.inputs["Subsurface Scale"].default_value = 0.002
    leg = S.material("Tinned leg", (0.8, 0.8, 0.8, 1), rough=0.3)
    leg.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 1.0
    resist = S.material("Resistor body", (0.78, 0.66, 0.48, 1), rough=0.5)
    band_cols = [(0.9, 0.55, 0.05, 1), (0.9, 0.55, 0.05, 1), (0.35, 0.18, 0.08, 1),
                 (0.75, 0.6, 0.2, 1)]   # orange orange brown gold = 330 ohm
    housing = S.material("Dupont housing", (0.02, 0.02, 0.02, 1), rough=0.6)
    w_red = S.material("Wire red", (0.55, 0.03, 0.02, 1), rough=0.45)
    w_blk = S.material("Wire black", (0.02, 0.02, 0.02, 1), rough=0.45)
    parts, wires = [], []

    tip_y = Y_IN + COLLAR_T
    dome = S.cylinder("led_dome", LED_D, LED_BODY_L - LED_D / 2,
                      loc=(PIPE_X, tip_y + LED_D / 2 + (LED_BODY_L - LED_D / 2) / 2, PIPE_Z),
                      rot=(math.pi / 2, 0, 0))
    bpy.ops.mesh.primitive_uv_sphere_add(radius=LED_D / 2, location=(PIPE_X, tip_y + LED_D / 2,
                                                                     PIPE_Z))
    tip = bpy.context.active_object
    flange_y = tip_y + LED_BODY_L
    flange = S.cylinder("led_flange", LED_FLANGE_D, 1.0, loc=(PIPE_X, flange_y + 0.5, PIPE_Z),
                        rot=(math.pi / 2, 0, 0))
    S.union(dome, [tip, flange])
    S.smooth(dome)
    parts.append(S.assign(dome, led_mat))

    leg_y0 = flange_y + 1.0
    anode_x, cath_x = PIPE_X + 1.27, PIPE_X - 1.27
    parts.append(S.assign(S.box("cathode_leg", 0.5, 3.0, 0.5,
                                loc=(cath_x, leg_y0 + 1.5, PIPE_Z)), leg))
    parts.append(S.assign(S.box("anode_leg", 0.5, 2.0, 0.5,
                                loc=(anode_x, leg_y0 + 1.0, PIPE_Z)), leg))
    r0 = leg_y0 + 2.0
    body = S.cylinder("resistor", 2.3, 6.3, loc=(anode_x, r0 + 3.15, PIPE_Z),
                      rot=(math.pi / 2, 0, 0))
    S.smooth(body)
    parts.append(S.assign(body, resist))
    for k, c in enumerate(band_cols):
        y = r0 + 1.2 + k * 1.1 + (0.8 if k == 3 else 0)
        bd = S.cylinder("band", 2.36, 0.6, loc=(anode_x, y, PIPE_Z), rot=(math.pi / 2, 0, 0))
        parts.append(S.assign(bd, S.material(f"band{k}", c, rough=0.5)))
    r_end = r0 + 6.3

    gx, gy = header_pin_xy(LED_PINS["gnd"])
    sx, sy = header_pin_xy(LED_PINS["gpio17"])
    hx, hy = (gx + sx) / 2, gy
    h_z0 = BOARD_TOP + 2.5
    hous = S.box("dupont_2pin", 5.08, 2.54, 14.0, loc=(hx, hy, h_z0 + 7.0))
    parts.append(S.assign(hous, housing))
    top = h_z0 + 14.0
    wires.append(_curve("wire_gnd", [(cath_x, leg_y0 + 3.0, PIPE_Z),
                                     (cath_x - 2, leg_y0 + 8, PIPE_Z + 6),
                                     (gx, gy, top + 3.0), (gx, gy, top)], 0.55, w_blk))
    wires.append(_curve("wire_gpio", [(anode_x, r_end, PIPE_Z),
                                      (anode_x - 3, r_end + 3, PIPE_Z + 7),
                                      (sx, sy, top + 3.5), (sx, sy, top)], 0.55, w_red))
    return parts, wires


def pi_mock():
    """Raspberry Pi 5 + Active Cooler stand-in, for fit checks and renders."""
    pcb = S.material("PCB", (0.02, 0.16, 0.07, 1), rough=0.35, coat=0.6)
    metal = S.material("Steel", (0.78, 0.78, 0.8, 1), rough=0.22)
    metal.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 1.0
    dark = S.material("Port insert", (0.015, 0.015, 0.017, 1), rough=0.5)
    blue = S.material("USB3 blue", (0.02, 0.12, 0.6, 1), rough=0.45)
    gold = S.material("Pin gold", (0.85, 0.65, 0.25, 1), rough=0.2)
    gold.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 1.0
    alu = S.material("Alu", (0.6, 0.62, 0.65, 1), rough=0.3)
    alu.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 1.0
    fan = S.material("Fan", (0.03, 0.03, 0.035, 1), rough=0.4)
    z = BOARD_Z
    parts = [S.assign(S.rounded_box("pcb", 85, 56, PCB_T, r=3, loc=(*pi_xy(42.5, 28), z)), pcb)]
    for name, v, w, h, dep, ov in PI["ports"]:
        x, y = pi_xy(85 - dep / 2 + ov, v)
        parts.append(S.assign(S.box(name, dep, w, h, loc=(x, y, BOARD_TOP + h / 2)), metal))
        xf = pi_xy(85 + ov, v)[0]
        if name == "eth":
            ins = S.box("eth_hole", 1.2, 11.5, 8.5, loc=(xf + 0.5, y, BOARD_TOP + 5.5))
            parts.append(S.assign(ins, dark))
        else:
            for k in (0, 1):
                ins = S.box("usb_tongue", 1.2, 11.0, 2.2,
                            loc=(xf + 0.5, y, BOARD_TOP + 3.9 + k * 7.8))
                parts.append(S.assign(ins, blue if name == "usb3" else dark))
    x, y = USBC
    parts.append(S.assign(S.box("usbc", 8.9, 7.4, 3.2,
                                loc=(x, y - 3.7 + PI["usbc_overhang"], BOARD_TOP + 1.6)), metal))
    for u in PI["hdmi_u"]:
        x, y = pi_xy(u, 0)
        parts.append(S.assign(S.box("hdmi", 6.5, 7.5, 3, loc=(x, y - 3.2, BOARD_TOP + 1.5)),
                              metal))
    hx = (header_pin_xy(1)[0] + header_pin_xy(39)[0]) / 2
    hy = pi_xy(0, PI["header_v"])[1]
    parts.append(S.assign(S.box("header", 50.8, 5.08, 2.5, loc=(hx, hy, BOARD_TOP + 1.25)), fan))
    for n in range(1, 41):
        if n in LED_PINS.values():
            continue
        px, py = header_pin_xy(n)
        parts.append(S.assign(S.box("pin", 0.64, 0.64, 6.0, loc=(px, py, BOARD_TOP + 5.5)), gold))
    hs = S.rounded_box("cooler", 50, 36, 7, r=1.5, loc=(FAN_C[0] - 2, FAN_C[1], BOARD_TOP + 2.5))
    parts.append(S.assign(hs, alu))
    f = S.cylinder("fan", 28, 2.5, loc=(FAN_C[0], FAN_C[1], BOARD_TOP + 10.6))
    parts.append(S.assign(f, fan))
    return S.join(parts, "Pi5 (reference)")


def write_dims_json(out):
    """Every number the dimension drawings print, taken from the model."""
    data = {
        "rev": REV, "W": W, "D": D, "TOP": TOP, "BASE_T": BASE_T, "WALL": WALL, "ROOF": ROOF,
        "R": R, "shadow_gap": S.SHADOW_GAP,
        "pipe": {"x": PIPE_X, "z": PIPE_Z, "d": PIPE_D, "hole_d": PIPE_HOLE_D,
                 "collar_d": COLLAR_D, "collar_t": COLLAR_T},
        "socket": {"id": SOCKET_ID, "od": SOCKET_OD, "len": SOCKET_L},
        "port_win": PORT_WIN,
        "usbc": {"x": USBC[0], "z": BOARD_TOP + 1.6, "w": USBC_SLOT[0], "h": USBC_SLOT[1]},
        "boss": BOSS, "boss_d": BOSS_D, "insert_d": INSERT_HOLE_D,
        "insert_depth": INSERT_HOLE_DEPTH, "fan_c": FAN_C, "pi_source": PI["source"],
        "feet": [[sx * 40, sy * 22] for sx in (-1, 1) for sy in (-1, 1)],
        "led_pins": LED_PINS,
    }
    with open(os.path.join(out, "dims.json"), "w") as f:
        json.dump(data, f, indent=1)


def main():
    args = sys.argv[1:]
    shell, base, pipe = build()
    os.makedirs(os.path.join(HERE, "stl"), exist_ok=True)
    S.export_stl(shell, os.path.join(HERE, "stl", "hub_shell_white.stl"))
    S.export_stl(base, os.path.join(HERE, "stl", "hub_base_black.stl"))
    S.export_stl(pipe, os.path.join(HERE, "stl", "hub_lightpipe_red.stl"))
    # Fit test: the last 15 mm of the shell at the ports end, a ~20 min print to check
    # the window against the real Pi before printing the whole shell.
    test = shell.copy()
    test.data = shell.data.copy()
    test.name = "Fit test (ports end)"
    bpy.context.collection.objects.link(test)
    keep = S.box("keep", 15, D + 10, TOP + 10, loc=(-W / 2 + 7.5, 0, TOP / 2))
    md = test.modifiers.new("keep", "BOOLEAN")
    md.operation, md.solver, md.object = "INTERSECT", "EXACT", keep
    S.bake(test)
    bpy.data.objects.remove(keep, do_unlink=True)
    S.export_stl(test, os.path.join(HERE, "stl", "hub_fittest_portsend_white.stl"))
    bpy.data.objects.remove(test, do_unlink=True)
    pi = pi_mock()
    harness, wires = led_harness()
    root = S.to_studio([shell, base, pipe, pi] + harness + wires)
    S.studio()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "hub.blend"))
    out = os.path.join(HERE, "renders")
    if "--preview" in args:
        out = os.path.join(HERE, "renders", "_preview")
        sc = bpy.context.scene
        sc.cycles.samples = 16
        sc.render.resolution_x, sc.render.resolution_y = 800, 600
    os.makedirs(out, exist_ok=True)
    write_dims_json(out)
    inside = [pi] + harness + wires
    m = 0.001

    def show(objs, on):
        for o in objs:
            o.hide_render = not on

    if "--renders" in args:
        show(inside, False)
        S.camera((0.25, -0.33, 0.19))
        S.render(os.path.join(out, "hub_hero.png"))
        show([pi], True)
        S.camera((-0.30, 0.27, 0.15))
        S.render(os.path.join(out, "hub_ports.png"))
        show([pi], False)
        S.camera((0.10, -0.16, 0.50), target=(0.0, 0.0, 0.02), lens=80)
        S.render(os.path.join(out, "hub_top.png"))
        # exploded: base | Pi | LED kit | shell, with the pipe pulled out in front
        show([pi] + harness, True)
        moves = [(shell, (0, 0, 78)), (pipe, (0, -22, 78)), (pi, (0, 0, 30))]
        moves += [(h, (0, -8, 60)) for h in harness]
        for o, d in moves:
            o.location = tuple(a + b for a, b in zip(o.location, d))
        S.camera((0.30, -0.42, 0.25), target=(0, 0, 0.056), lens=60)
        S.render(os.path.join(out, "hub_exploded.png"))
        for o, d in moves:
            o.location = tuple(a - b for a, b in zip(o.location, d))
        # cutaway: roof removed to show the LED, resistor and wiring in place
        show(inside, True)
        cut = S.box("roof_cut", W + 10, D + 10, 20, loc=(0, 0, TOP - ROOF + 10 - 0.01))
        cut.parent = root
        cut.hide_render = True
        md = shell.modifiers.new("cut", "BOOLEAN")
        md.operation, md.solver, md.object = "DIFFERENCE", "EXACT", cut
        S.camera((0.13, -0.20, 0.25), target=(0.012, -0.012, 0.012), lens=60)
        S.render(os.path.join(out, "hub_cutaway.png"))
        shell.modifiers.remove(md)
        bpy.data.objects.remove(cut, do_unlink=True)
        # underside: flip the model over
        show(inside, False)
        root.rotation_euler = (math.pi, 0, 0)
        root.location = (0, 0, TOP * m)
        S.camera((0.22, -0.30, 0.20), target=(0, 0, 0.012))
        S.render(os.path.join(out, "hub_underside.png"))
        root.rotation_euler = (0, 0, 0)
        root.location = (0, 0, 0)

    if "--details" in args:
        show(inside, False)
        sc = bpy.context.scene
        res0 = (sc.render.resolution_x, sc.render.resolution_y)
        sc.render.resolution_x, sc.render.resolution_y = 1400, 1050
        lx, ly = (W / 2 - 15 - 12) * m, (-D / 2 + 11) * m
        S.camera((lx + 0.02, ly - 0.075, 0.105), target=(lx, ly, TOP * m), lens=100)
        S.render(os.path.join(out, "d_label.png"))
        S.camera((PIPE_X * m + 0.03, -0.14, 0.05), target=(PIPE_X * m, -D / 2 * m, PIPE_Z * m),
                 lens=100)
        S.render(os.path.join(out, "d_light.png"))
        S.camera((FAN_C[0] * m - 0.03, FAN_C[1] * m - 0.07, 0.12),
                 target=(FAN_C[0] * m, FAN_C[1] * m, TOP * m), lens=100)
        S.render(os.path.join(out, "d_vents.png"))
        S.camera((0.105, -0.085, 0.012), target=(W / 2 * m - 0.006, -D / 2 * m + 0.006, 0.004),
                 lens=100)
        S.render(os.path.join(out, "d_shadowline.png"))
        show([pi], True)
        S.camera((-0.13, -0.05, 0.035), target=(-W / 2 * m, 0, 0.016), lens=70)
        S.render(os.path.join(out, "d_ports_end.png"))
        S.camera((0.05, 0.14, 0.04), target=(USBC[0] * m, D / 2 * m, 0.010), lens=100)
        S.render(os.path.join(out, "d_usbc.png"))
        show([pi], False)
        sc.render.resolution_x, sc.render.resolution_y = res0

    if "--drawings" in args:
        show(inside, False)
        S.drawing_setup()
        grey = S.material("Drawing grey", (0.86, 0.86, 0.86, 1), rough=0.9)
        bpy.context.scene.view_layers[0].material_override = grey
        meta = {}
        for v in ("front", "left", "back", "top", "bottom"):
            c = (0, 0, TOP / 2)
            scale = 0.180 if v in ("top", "bottom") else 0.150
            S.ortho_camera(v, tuple(k * m for k in c), scale)
            S.render(os.path.join(out, f"dwg_{v}.png"))
            meta[v] = {"view": v, "center_mm": c, "scale_mm": scale * 1000,
                       "res": [bpy.context.scene.render.resolution_x,
                               bpy.context.scene.render.resolution_y]}
        # section through the light pipe and LED socket, seen from +X
        sec = S.box("sec", 200, 200, 200, loc=(PIPE_X + 100, 0, 0))
        sec.parent = root
        sec.hide_render = True
        show(harness, True)
        for o in [shell, pipe] + harness:
            md = o.modifiers.new("sec", "BOOLEAN")
            # EXACT empties the small light-pipe mesh; MANIFOLD hollows the LED. Use each where it works.
            md.operation, md.object = "DIFFERENCE", sec
            md.solver = "MANIFOLD" if o is pipe else "EXACT"
        bpy.context.scene.view_layers[0].material_override = None
        c = (PIPE_X, -D / 2 + 9, PIPE_Z)
        cam = S.ortho_camera("right", tuple(k * m for k in c), 0.032)
        # only see a thin slab at the cut plane, so it reads as a true cross-section
        cam.data.clip_start, cam.data.clip_end = 0.5 - 0.0002, 0.5 + 0.0015
        S.render(os.path.join(out, "dwg_section_led.png"))
        meta["section_led"] = {"view": "right", "center_mm": c, "scale_mm": 32.0,
                               "res": [bpy.context.scene.render.resolution_x,
                                       bpy.context.scene.render.resolution_y]}
        with open(os.path.join(out, "dwg_cameras.json"), "w") as f:
            json.dump(meta, f, indent=1)

    if "--turntable" in args:
        show(inside, False)
        sc = bpy.context.scene
        frames = 72
        sc.frame_start, sc.frame_end = 1, frames
        root.rotation_euler = (0, 0, 0)
        root.keyframe_insert("rotation_euler", index=2, frame=1)
        root.rotation_euler = (0, 0, 2 * math.pi)
        root.keyframe_insert("rotation_euler", index=2, frame=frames + 1)
        act = root.animation_data.action
        for fc in act.layers[0].strips[0].channelbag(act.slots[0]).fcurves:
            for k in fc.keyframe_points:
                k.interpolation = "LINEAR"
        S.camera((0.0, -0.40, 0.17), target=(0, 0, 0.016))
        sc.cycles.samples = 20
        sc.render.resolution_x, sc.render.resolution_y = 960, 640
        frames_dir = os.path.join(out, "_frames")
        os.makedirs(frames_dir, exist_ok=True)
        sc.render.image_settings.file_format = "PNG"
        sc.render.filepath = os.path.join(frames_dir, "f_")
        bpy.ops.render.render(animation=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "24", "-i",
                        os.path.join(frames_dir, "f_%04d.png"), "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", "-crf", "22", "-movflags", "+faststart",
                        os.path.join(out, "hub_turntable.mp4")], check=True)


if __name__ == "__main__":
    main()
