"""Home Assistant hub enclosure for a Raspberry Pi 5 + official Active Cooler. Rev C.

Rev C replaces the single red light with a "halo": a 24-LED addressable RGB ring
under the roof that glows through a 0.6 mm skin of the white shell.

Run:  python hub.py [--renders] [--details] [--drawings] [--preview]
Writes hub.blend, stl/*.stl, and optionally renders/*.png plus drawing data.

Printed parts (one colour each, no AMS needed):
  shell    - white PLA, printed upside-down (roof on the plate)
  base     - black PLA, printed flat
  carrier  - black PLA light carrier that holds the LED ring, printed floor-down
Bought parts: see review.html (Pi 5, cooler, inserts, screws, 24-LED WS2812B ring,
1N4001 diode, 330 ohm resistor, 470 uF capacitor, three female jumper wires, feet).
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import bpy  # noqa: E402
import studio as S  # noqa: E402

REV = "C"

# ---------------------------------------------------------------- enclosure (mm)
W, D = 106.0, 80.0          # outer footprint
R = 12.0                    # plan corner radius
BASE_T = 3.0                # black base plate
TOP = 40.0                  # overall height
SHELL_H = TOP - BASE_T
WALL, ROOF = 2.0, 2.0
ROOF_IN = TOP - ROOF        # underside of the roof
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
DUPONT_TOP = BOARD_TOP + 2.5 + 14.0            # top of a female jumper on a header pin

_vs = [(v - w / 2, v + w / 2) for _, v, w, _, _, _ in PI["ports"]]
_ys = sorted([28.0 - a for a, b in _vs] + [28.0 - b for a, b in _vs])
PORT_WIN = {"y0": _ys[0] - 1.0, "y1": _ys[-1] + 1.0,
            "z0": BOARD_TOP - 1.0, "z1": BOARD_TOP + max(p[3] for p in PI["ports"]) + 1.0}
USBC_SLOT = (13.0, 7.5)

# ---------------------------------------------------------------- halo light
# LED ring: Adafruit NeoPixel Ring 24 (product 1586) or equivalent WS2812B 24-LED ring.
# Clones run 66-68 mm across; the channel fits either.
RING_N = 24
RING_OD, RING_ID, RING_PCB_T = 66.0, 52.5, 1.6
LED_SIZE, LED_H = 5.0, 1.6                     # 5050 package
LED_R = (RING_OD + RING_ID) / 4                # radius of the LED centres, ~29.6
CH_R0, CH_R1 = 25.5, 34.0                      # light channel = groove in the roof
SKIN = 0.6                                     # white PLA left over the LEDs
GAP = 6.0                                      # LED top to the underside of the skin
Z_SKIN_IN = TOP - SKIN
Z_LED_TOP = Z_SKIN_IN - GAP
Z_RING_TOP = Z_LED_TOP - LED_H
Z_RING_BOT = Z_RING_TOP - RING_PCB_T
FLOOR_T, CAR_WALL = 1.2, 1.6
Z_CAR_BOT = Z_RING_BOT - FLOOR_T
CAR_TAB_R, CAR_TAB_ANG = 38.5, (0.0, 120.0, 240.0)   # M2.5 screws into roof posts
CAR_TAB_TOP = ROOF_IN - 5.0
WIRE_ANG = -68.0                               # where the wires leave the carrier
VENT_PITCH, VENT_RAD, VENT_HOLE = 3.9, 20.0, 2.2
# wiring: 5 V on pin 2, ground on pin 6, data on pin 19 (GPIO10, SPI MOSI)
RING_PINS = {"5v": 2, "gnd": 6, "data": 19}


def _ring(name, r0, r1, z0, z1, seg=128):
    outer = S.cylinder(name, 2 * r1, z1 - z0, loc=(0, 0, (z0 + z1) / 2), seg=seg)
    S.bake(outer)
    inner = S.cylinder(name + "_in", 2 * r0, z1 - z0 + 2, loc=(0, 0, (z0 + z1) / 2), seg=seg)
    S.cut(outer, inner)
    return outer


def _polar(r, deg):
    a = math.radians(deg)
    return r * math.cos(a), r * math.sin(a)


def build():
    S.reset()
    white, black = S.pla("white"), S.pla("black")

    # ------------------------------------------------ shell
    shell = S.rounded_box("Shell", W, D, SHELL_H, r=R, r_top=S.EDGE_R, r_bot=0.4,
                          loc=(0, 0, BASE_T))
    S.bake(shell)
    cavity = S.rounded_box("cavity", W - 2 * WALL, D - 2 * WALL, SHELL_H - ROOF + 1,
                           r=R - WALL, loc=(0, 0, BASE_T - 1))
    S.cut(shell, cavity)

    adds = []
    for x, y in BOSS:
        h = ROOF_IN - BASE_T + 0.5
        adds.append(S.cylinder("boss", BOSS_D, h, loc=(x, y, BASE_T + h / 2)))
    for a in CAR_TAB_ANG:          # short posts under the roof for the carrier screws
        x, y = _polar(CAR_TAB_R, a)
        h = ROOF_IN - CAR_TAB_TOP + 0.5
        adds.append(S.cylinder("car_post", 6.0, h, loc=(x, y, CAR_TAB_TOP + h / 2)))
    S.union(shell, adds)

    cutters = []
    for x, y in BOSS:
        cutters.append(S.cylinder("insert", INSERT_HOLE_D, INSERT_HOLE_DEPTH + 1,
                                  loc=(x, y, BASE_T + (INSERT_HOLE_DEPTH - 1) / 2)))
    for a in CAR_TAB_ANG:
        x, y = _polar(CAR_TAB_R, a)
        cutters.append(S.cylinder("car_post_hole", 2.2, 4.2, loc=(x, y, CAR_TAB_TOP + 2.0)))
    pw = PORT_WIN
    cutters.append(S.slot("ports", pw["y1"] - pw["y0"], pw["z1"] - pw["z0"], 10,
                          loc=(-W / 2, (pw["y0"] + pw["y1"]) / 2, (pw["z0"] + pw["z1"]) / 2),
                          axis="X", r=2.5))
    cutters.append(S.slot("usbc", *USBC_SLOT, 10, loc=(USBC[0], D / 2, BOARD_TOP + 1.6),
                          axis="Y"))
    # the halo groove: thins the roof to SKIN above the LEDs, from the inside
    cutters.append(_ring("groove", CH_R0, CH_R1, ROOF_IN - 1.0, Z_SKIN_IN))
    vents = []
    rows = int(VENT_RAD / (VENT_PITCH * 0.866)) + 1
    for j in range(-rows, rows + 1):
        y = j * VENT_PITCH * 0.866
        off = VENT_PITCH / 2 if j % 2 else 0
        for i in range(-8, 9):
            x = i * VENT_PITCH + off
            if math.hypot(x, y) <= VENT_RAD - VENT_HOLE / 2:
                vents.append(S.cylinder("vent", VENT_HOLE, 6, loc=(x, y, TOP), seg=20))
    cutters.append(S.join(vents, "vents"))
    cutters.append(S.text("label", "HOME / 01", 4.2, 1.6, loc=(W / 2 - 15, -D / 2 + 10, TOP),
                          align="RIGHT"))   # 0.8 mm deep
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

    carrier = build_carrier()
    S.assign(carrier, black)
    return shell, base, carrier


def build_carrier():
    """Black ring-shaped channel: holds the LED ring and keeps its light inside the groove."""
    r_in0, r_out1 = CH_R0 - CAR_WALL, CH_R1 + CAR_WALL
    floor = _ring("Carrier", r_in0, r_out1, Z_CAR_BOT, Z_RING_BOT)
    inner = _ring("car_inner", r_in0, CH_R0, Z_RING_BOT - 0.01, ROOF_IN)
    outer = _ring("car_outer", CH_R1, r_out1, Z_RING_BOT - 0.01, ROOF_IN)
    tabs = []
    for a in CAR_TAB_ANG:
        x, y = _polar(CAR_TAB_R, a)
        post = S.cylinder("tab", 6.0, CAR_TAB_TOP - Z_CAR_BOT,
                          loc=(x, y, (Z_CAR_BOT + CAR_TAB_TOP) / 2))
        x2, y2 = _polar((CAR_TAB_R + r_out1) / 2 - 0.5, a)
        web = S.box("web", 5.0, 5.0, CAR_TAB_TOP - Z_CAR_BOT,
                    loc=(x2, y2, (Z_CAR_BOT + CAR_TAB_TOP) / 2))
        web.rotation_euler = (0, 0, math.radians(a))
        S.bake(web)
        tabs += [post, web]
    S.union(floor, [inner, outer] + tabs)
    cuts = []
    for a in CAR_TAB_ANG:
        x, y = _polar(CAR_TAB_R, a)
        cuts.append(S.cylinder("tab_hole", 2.8, 20, loc=(x, y, Z_CAR_BOT + 5)))
    x, y = _polar(LED_R, WIRE_ANG)                       # wire exit under the ring's pads
    slot = S.box("wire_slot", 8.0, 4.0, 6.0, loc=(x, y, Z_CAR_BOT))
    slot.rotation_euler = (0, 0, math.radians(WIRE_ANG + 90))
    S.bake(slot)
    cuts.append(slot)
    S.cut(floor, cuts)
    S.smooth(floor)
    return floor


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


def led_ring():
    """24-LED WS2812B ring: black PCB, white 5050 LEDs facing up. Returns (pcb, [leds])."""
    pcb = _ring("LED ring PCB", RING_ID / 2, RING_OD / 2, Z_RING_BOT, Z_RING_TOP)
    S.assign(pcb, S.material("Ring PCB", (0.01, 0.01, 0.012, 1), rough=0.4, coat=0.5))
    led_mat = S.material("5050 LED", (0.92, 0.92, 0.9, 1), rough=0.3)
    leds = []
    for k in range(RING_N):
        a = 360.0 * k / RING_N
        x, y = _polar(LED_R, a)
        b = S.box(f"led{k:02d}", LED_SIZE, LED_SIZE, LED_H, loc=(x, y, Z_RING_TOP + LED_H / 2))
        b.rotation_euler = (0, 0, math.radians(a))
        S.bake(b)
        leds.append(S.assign(b, led_mat))
    return pcb, leds


def ring_harness():
    """Three wires from the ring's pads to the Pi header, with the diode, resistor and
    capacitor in line. Returns (parts, wires)."""
    w_red = S.material("Wire red", (0.55, 0.03, 0.02, 1), rough=0.45)
    w_blk = S.material("Wire black", (0.02, 0.02, 0.02, 1), rough=0.45)
    w_yel = S.material("Wire yellow", (0.75, 0.6, 0.05, 1), rough=0.45)
    housing = S.material("Dupont housing", (0.02, 0.02, 0.02, 1), rough=0.6)
    shrink = S.material("Heat-shrink", (0.04, 0.04, 0.045, 1), rough=0.55)
    cap_mat = S.material("Capacitor", (0.05, 0.12, 0.35, 1), rough=0.35)
    parts, wires = [], []
    px, py = _polar(LED_R, WIRE_ANG)
    pad = (px, py, Z_CAR_BOT - 0.5)
    mid = (13.0, -33.0, 22.0)                     # in-line parts sit in the gap by the wall
    cols = {"5v": w_red, "gnd": w_blk, "data": w_yel}
    for i, (sig, pin) in enumerate(RING_PINS.items()):
        hx, hy = header_pin_xy(pin)
        parts.append(S.assign(S.box(f"dupont_{sig}", 2.54, 2.54, 14.0,
                                    loc=(hx, hy, BOARD_TOP + 2.5 + 7.0)), housing))
        off = (i - 1) * 1.6
        pts = [(pad[0] + off, pad[1], pad[2]), (pad[0] + off, pad[1] - 2, pad[2] - 3),
               (mid[0] + off, mid[1], mid[2] + 3), (mid[0] + off, mid[1], mid[2] - 4),
               (hx, hy - 3, DUPONT_TOP + 3.5), (hx, hy, DUPONT_TOP)]
        wires.append(_curve(f"wire_{sig}", pts, 0.55, cols[sig]))
    # heat-shrunk diode (5 V) and resistor (data) on their wires, capacitor across 5 V/GND
    for sig, dz in (("5v", 0.0), ("data", 0.0)):
        i = list(RING_PINS).index(sig)
        sl = S.cylinder(f"shrink_{sig}", 3.2, 9.0, loc=(mid[0] + (i - 1) * 1.6, mid[1],
                                                       mid[2] - 0.5 + dz))
        S.smooth(sl)
        parts.append(S.assign(sl, shrink))
    cap = S.cylinder("cap_470uF", 6.3, 11.0, loc=(mid[0] + 6.5, mid[1] - 0.5, mid[2] - 1.0))
    S.smooth(cap)
    parts.append(S.assign(cap, cap_mat))
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
        if n in RING_PINS.values():
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
        "port_win": PORT_WIN,
        "usbc": {"x": USBC[0], "z": BOARD_TOP + 1.6, "w": USBC_SLOT[0], "h": USBC_SLOT[1]},
        "boss": BOSS, "boss_d": BOSS_D, "insert_d": INSERT_HOLE_D,
        "insert_depth": INSERT_HOLE_DEPTH, "pi_source": PI["source"],
        "feet": [[sx * 40, sy * 22] for sx in (-1, 1) for sy in (-1, 1)],
        "halo": {"ch_r0": CH_R0, "ch_r1": CH_R1, "skin": SKIN, "gap": GAP,
                 "ring_od": RING_OD, "ring_id": RING_ID, "led_r": LED_R,
                 "z_skin_in": Z_SKIN_IN, "z_led_top": Z_LED_TOP, "z_ring_bot": Z_RING_BOT,
                 "z_car_bot": Z_CAR_BOT, "car_wall": CAR_WALL, "roof_in": ROOF_IN,
                 "tab_r": CAR_TAB_R, "tab_ang": CAR_TAB_ANG, "dupont_top": DUPONT_TOP},
        "vents": {"pitch": VENT_PITCH, "rad": VENT_RAD, "hole": VENT_HOLE},
        "ring_pins": RING_PINS,
    }
    with open(os.path.join(out, "dims.json"), "w") as f:
        json.dump(data, f, indent=1)


def main():
    args = sys.argv[1:]
    shell, base, carrier = build()
    os.makedirs(os.path.join(HERE, "stl"), exist_ok=True)
    for f in ("hub_lightpipe_red.stl",):          # rev B part, no longer used
        p = os.path.join(HERE, "stl", f)
        if os.path.exists(p):
            os.remove(p)
    S.export_stl(shell, os.path.join(HERE, "stl", "hub_shell_white.stl"))
    S.export_stl(base, os.path.join(HERE, "stl", "hub_base_black.stl"))
    S.export_stl(carrier, os.path.join(HERE, "stl", "hub_lightcarrier_black.stl"))
    # Fit test: the last 15 mm of the shell at the ports end (~20 min print).
    test = shell.copy()
    test.data = shell.data.copy()
    bpy.context.collection.objects.link(test)
    keep = S.box("keep", 15, D + 10, TOP + 10, loc=(-W / 2 + 7.5, 0, TOP / 2))
    md = test.modifiers.new("keep", "BOOLEAN")
    md.operation, md.solver, md.object = "INTERSECT", "EXACT", keep
    S.bake(test)
    bpy.data.objects.remove(keep, do_unlink=True)
    S.export_stl(test, os.path.join(HERE, "stl", "hub_fittest_portsend_white.stl"))
    bpy.data.objects.remove(test, do_unlink=True)
    # Light test: a 14 x 20 mm piece of roof across the groove, to hold over the lit ring.
    test = shell.copy()
    test.data = shell.data.copy()
    bpy.context.collection.objects.link(test)
    keep = S.box("keep", 14, 20, 2.4, loc=(0, LED_R, TOP - 1.0))
    md = test.modifiers.new("keep", "BOOLEAN")
    md.operation, md.solver, md.object = "INTERSECT", "EXACT", keep
    S.bake(test)
    bpy.data.objects.remove(keep, do_unlink=True)
    S.export_stl(test, os.path.join(HERE, "stl", "hub_lighttest_skin_white.stl"))
    bpy.data.objects.remove(test, do_unlink=True)

    pi = pi_mock()
    pcb, leds = led_ring()
    harness, wires = ring_harness()
    ring = [pcb] + leds
    root = S.to_studio([shell, base, carrier, pi] + ring + harness + wires)
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
    inside = [pi, carrier] + ring + harness + wires
    m = 0.001

    def show(objs, on):
        for o in objs:
            o.hide_render = not on

    def shift(objs, d):
        for o in objs:
            o.location = tuple(a + b for a, b in zip(o.location, d))

    if "--renders" in args:
        show(inside, False)
        S.camera((0.25, -0.33, 0.21), target=(0, 0, 0.018))
        S.render(os.path.join(out, "hub_hero.png"))
        show([pi], True)
        S.camera((-0.30, 0.27, 0.16), target=(0, 0, 0.018))
        S.render(os.path.join(out, "hub_ports.png"))
        show([pi], False)
        S.camera((0.10, -0.16, 0.52), target=(0.0, 0.0, 0.02), lens=80)
        S.render(os.path.join(out, "hub_top.png"))
        # exploded, bottom to top: base | Pi + wires | LED ring | carrier | shell
        show(inside, True)
        show(wires + harness, False)
        moves = [(shell, (0, 0, 120)), (carrier, (0, 0, 72)), (pi, (0, 0, 8))]
        moves += [(o, (0, 0, 42)) for o in ring]
        for o, d in moves:
            shift([o], d)
        S.camera((0.36, -0.52, 0.32), target=(0, 0, 0.082), lens=55)
        S.render(os.path.join(out, "hub_exploded.png"))
        for o, d in moves:
            shift([o], tuple(-k for k in d))
        # cutaway: roof cut off just under the carrier top to show ring, carrier and wiring
        show(inside, True)
        cut = S.box("roof_cut", W + 10, D + 10, 30, loc=(0, 0, ROOF_IN - 3 + 15))
        cut.parent = root
        cut.hide_render = True
        for o in (shell, carrier):
            md = o.modifiers.new("cut", "BOOLEAN")
            md.operation, md.solver, md.object = "DIFFERENCE", "EXACT", cut
        S.camera((0.12, -0.20, 0.26), target=(0.006, -0.008, 0.02), lens=58)
        S.render(os.path.join(out, "hub_cutaway.png"))
        for o in (shell, carrier):
            o.modifiers.remove(o.modifiers["cut"])
        bpy.data.objects.remove(cut, do_unlink=True)
        show(inside, False)
        root.rotation_euler = (math.pi, 0, 0)
        root.location = (0, 0, TOP * m)
        S.camera((0.22, -0.30, 0.20), target=(0, 0, 0.014))
        S.render(os.path.join(out, "hub_underside.png"))
        root.rotation_euler = (0, 0, 0)
        root.location = (0, 0, 0)

    if "--details" in args:
        show(inside, False)
        sc = bpy.context.scene
        res0 = (sc.render.resolution_x, sc.render.resolution_y)
        if "--preview" not in args:
            sc.render.resolution_x, sc.render.resolution_y = 1400, 1050
        lx, ly = (W / 2 - 15 - 12) * m, (-D / 2 + 11) * m
        S.camera((lx + 0.02, ly - 0.075, 0.11), target=(lx, ly, TOP * m), lens=100)
        S.render(os.path.join(out, "d_label.png"))
        S.camera((0.02, -0.09, 0.13), target=(0, 0, TOP * m), lens=90)
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
        # the carrier with the ring in it, on its own
        show([carrier] + ring, True)
        show([shell, base], False)
        S.camera((0.09, -0.13, 0.15), target=(0, 0, 0.032), lens=75)
        S.render(os.path.join(out, "d_carrier.png"))
        show([shell, base], True)
        show(inside, False)
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
        # section through the halo at y = 0, seen from the front
        bpy.context.scene.view_layers[0].material_override = None
        sec = S.box("sec", 300, 200, 200, loc=(0, -100 + 0.0, 0))
        sec.parent = root
        sec.hide_render = True
        show([carrier] + ring, True)
        for o in [shell, carrier] + ring:
            md = o.modifiers.new("sec", "BOOLEAN")
            md.operation, md.object = "DIFFERENCE", sec
            md.solver = "EXACT"
        c = (LED_R, 0, (Z_CAR_BOT + TOP) / 2)
        cam = S.ortho_camera("front", tuple(k * m for k in c), 0.032)
        cam.data.clip_start, cam.data.clip_end = 0.5 - 0.0002, 0.5 + 0.004
        S.render(os.path.join(out, "dwg_section_halo.png"))
        meta["section_halo"] = {"view": "front", "center_mm": c, "scale_mm": 32.0,
                                "res": [bpy.context.scene.render.resolution_x,
                                        bpy.context.scene.render.resolution_y]}
        with open(os.path.join(out, "dwg_cameras.json"), "w") as f:
            json.dump(meta, f, indent=1)


if __name__ == "__main__":
    main()
