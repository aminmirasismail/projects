"""Home Assistant hub enclosure for a Raspberry Pi 5 + official Active Cooler. Rev D.

Rev D is lighting concept D, "underglow": the white shell floats 5 mm above the table on a
small inset black plinth, and an addressable RGBW strip under the shell's edge washes light
onto the table. No light goes through the white plastic. Rev C's halo (LED ring under a
thinned roof) is gone.

Run:  python hub.py [--renders] [--details] [--light] [--drawings] [--preview]
Writes hub.blend, stl/*.stl, and optionally renders/*.png plus drawing data.

Printed parts (one colour each, no AMS needed):
  shell   - white PLA, printed upside-down (roof on the plate)
  floor   - black PLA, printed flat: closes the shell, carries the Pi and the ESP32
  plinth  - black PLA, printed upside-down: the foot under the floor plus the downward
            LED channel round its edge
Bought parts (full list with tools in BOM.md): Pi 5 + Active Cooler, SK6812 RGBW 5 V 144/m
12 mm strip (32 LEDs used), ESP32-C3 SuperMini, 74AHCT1G125 level shifter, 4x M3 heat-set
inserts, 4x M3x12 button-head screws,
4x M2.5x6 screws, 330 ohm resistor, 1000 uF capacitor, jumper wires, 4 small rubber feet.

Why an ESP32: Home Assistant OS on a Pi 5 can't drive addressable LEDs from the GPIO
header (no integration for it, and the Pi 5's RP1 chip breaks the usual LED library).
A ESP32-C3 running ESPHome drives the strip and talks to Home Assistant over Wi-Fi;
it takes 5 V and ground from the Pi's header.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import bpy  # noqa: E402
import studio as S  # noqa: E402

REV = "v5"   # iterations are version numbers; lighting concepts are letters (CLAUDE.md)

# ---------------------------------------------------------------- enclosure (mm)
W, D = 106.0, 80.0          # outer footprint
R = 12.0                    # plan corner radius
LIFT = 5.0                  # gap from the table to the white shell's bottom edge
SHELL_Z0 = LIFT             # the shell comes all the way down: from the side it floats
TOP = 42.0                  # overall height (table to roof); +2 mm over v4 for the intake plenum
SHELL_H = TOP - SHELL_Z0
WALL, ROOF = 2.0, 2.0
ROOF_IN = TOP - ROOF        # underside of the roof
FIT = 0.2                   # clearance between the black parts and the shell's inner wall
SKIRT = 5.0                 # the black parts sit this far up inside the shell's bottom edge
PLATE_T = 1.4               # plinth top plate; the strip sticks to its underside
FLOOR_T = 2.5               # black floor plate that carries the Pi and the ESP32
Z_PLATE_BOT = LIFT + SKIRT - PLATE_T
PLENUM = 2.0                # air gap between plinth plate and floor: the intake's light trap
FLOOR_Z0 = LIFT + SKIRT + PLENUM
FLOOR_TOP = FLOOR_Z0 + FLOOR_T
STANDOFF_H = 4.0
BOARD_Z = FLOOR_TOP + STANDOFF_H    # underside of the Pi PCB
PCB_T = 1.6
BOARD_TOP = BOARD_Z + PCB_T

# Heat-set inserts: CNC Kitchen / Ruthex standard M3 x 5.7 mm, OD 4.6 mm.
# Maker guidance: 4.0 mm hole, depth >= insert length + 1 mm, wall >= ~2 mm around it.
INSERT_HOLE_D, INSERT_HOLE_DEPTH = 4.0, 8.0
BOSS_D = 9.0
BOSS_X = 40.0               # Rev C had 36; moved out so the strip ends clear the posts by 3 mm
BOSS = [(sx * BOSS_X, sy * (D / 2 - WALL - BOSS_D / 2 + 0.3)) for sx in (-1, 1)
        for sy in (-1, 1)]

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


PI_X0 = 37.0   # board's u = 0 edge: ports end 0.6 mm inside the wall, so the floor drops in


def pi_xy(u, v):
    """Board coords -> enclosure XY. Board is rotated so Ethernet/USB face -X, USB-C +Y."""
    return PI_X0 - u, 28.0 - v


def header_pin_xy(n):
    """Physical pin number (1-40) -> XY. Odd pins are on the inner row."""
    col = (n - 1) // 2
    u = PI["header_pin1_u"] + col * PI["pitch"]
    v = PI["header_v"] - 1.27 if n % 2 else PI["header_v"] + 1.27
    return pi_xy(u, v)


PI_HOLES = [pi_xy(u, v) for u in PI["holes_u"] for v in PI["holes_v"]]
FAN_C = pi_xy(30.0, 27.0)
USBC = pi_xy(PI["usbc_u"], 0)
DUPONT_TOP = BOARD_TOP + 16.0                  # inverted female header, tails soldered
HEADER_USED = {"5v": 4, "gnd": 6}              # adjacent pins: one 1x2 female header

# one window per port (ribs between them keep the printed bridges short)
# one window per port, all full height (they double as the high exhaust), inside one bay
_PORT_H = max(p[3] for p in PI["ports"]) + 1.0
PORT_WINS = [{"name": n, "y0": 28.0 - v - w / 2 - 1.0, "y1": 28.0 - v + w / 2 + 1.0,
              "z0": BOARD_TOP - 0.2, "z1": BOARD_TOP + _PORT_H}
             for n, v, w, h, _, _ in PI["ports"]]
BAY_DEPTH, BAY_MARGIN = 0.8, 0.6     # recessed I/O bay round all three windows
PORT_WIN = {"y0": min(p["y0"] for p in PORT_WINS), "y1": max(p["y1"] for p in PORT_WINS),
            "z0": BOARD_TOP - 0.2, "z1": max(p["z1"] for p in PORT_WINS)}
USBC_SLOT = (14.0, 8.0)       # the plug reaches 10.8 mm in: its overmould must pass

# ---------------------------------------------------------------- underglow plinth
# SK6812 RGBW 5 V, 144 LEDs/m, 12 mm wide, bare (IP30). Cut points every 6.94 mm.
# (60/m left separate pools of light on the table; 144/m reads as a band.)
# The strip can't bend sideways, so it lies flat (LEDs down) in straight runs along the
# four sides; short jumper wires carry 5 V / GND / data round each corner.
STRIP_W, STRIP_PCB_T, LED_SIZE, LED_H = 12.0, 0.25, 5.0, 1.6
PITCH = 1000.0 / 144
CH_W = STRIP_W + 0.3        # channel width
LEDGE, LEDGE_T = 0.8, 0.6   # lips either side that hold the strip up (no reliance on tape)
LEDGE_GAP = 0.6             # lip top to plate: strip PCB (0.25) + its adhesive tape
IN_IN = WALL + FIT           # black parts' outline, inset from the shell outline
LINING_T = 1.0              # black lining inside the skirt: no light reaches the white wall
LINING_DROP = 1.5           # the black lining hangs this far below the shell's bottom edge
LINING_Z = LIFT - LINING_DROP
FLANGE, FLANGE_T = 1.5, 0.8   # inward floor at the lining's foot (width, thickness): hides the
                            # LEDs' reflections in a glossy table from normal viewing angles
FOOT_IN = WALL + FIT + 1.0 + CH_W   # the foot (inner channel wall) inset from the outline
FOOT_R = 4.0
CH_IN0, CH_IN1 = IN_IN + LINING_T, FOOT_IN             # channel, inset from outline
CH_MID = (CH_IN0 + CH_IN1) / 2                         # strip centreline inset
Z_LED_FACE = Z_PLATE_BOT - LEDGE_GAP - LED_H        # strip PCB lies on the lips
SCREW_POST_D, SCREW_SEAT = 7.0, LIFT + 2.0   # M3 button head seats here, hidden by the skirt
SCREW_HEAD_D = 5.7
N_LONG, N_SHORT = 9, 7
WIRE_HOLE = (46.0, 28.0, 5.0)      # x, y, diameter: through the plinth, beside the +X run's end
FLOOR_HOLE = (46.0, 19.0)          # through the floor, offset: light must turn a corner
POSTS = True                       # v4: screw heads on posts in the channel corners


def configure(posts=True):
    """posts=True: v4 (screw posts in the channel corners, runs stop short of them).
    posts=False: screw heads sit flush in pockets in the plinth plate, tucked into the
    corners, so the strip runs reach the corners (11 + 8 LEDs per side pair)."""
    global POSTS, BOSS_X, BOSS, N_LONG, N_SHORT, WIRE_HOLE, FLOOR_HOLE
    POSTS = posts
    if posts:
        BOSS_X, by = 40.0, D / 2 - WALL - BOSS_D / 2 + 0.3
        N_LONG, N_SHORT = 9, 7
        WIRE_HOLE, FLOOR_HOLE = (46.0, 28.0, 5.0), (46.0, 19.0)
    else:
        BOSS_X, by = 42.0, 33.5
        N_LONG, N_SHORT = 11, 8
        WIRE_HOLE, FLOOR_HOLE = (47.3, 31.0, 4.0), (47.3, 19.0)
    BOSS = [(sx * BOSS_X, sy * by) for sx in (-1, 1) for sy in (-1, 1)]


HEAD_POCKET_D = 5.8                # M3 button head (5.7) sits flush in the plinth plate
configure(False)                   # v5: no posts, runs reach the corners
FEET = [(sx * 30.0, sy * 17.0) for sx in (-1, 1) for sy in (-1, 1)]   # on 4 pads
PAD_D = 10.0
FOOT_WALL = 1.6             # the inner channel wall is now a ring, not a solid foot
FOOT_GAP = 2.0              # ... ending 2 mm above the table: air passes under it
INTAKE_W, INTAKE_L = 3.0, 40.0
INTAKE_PLATE_X = (-21.0, -7.0, 7.0, 21.0)      # slots in the plinth plate
INTAKE_FLOOR_X = (-28.0, -14.0, 0.0, 14.0, 28.0)  # floor slots, offset (+-28 sit over the pads)
RIM_W = 2.5                 # plenum rim round the plinth plate's top edge
DIFF_T = 0.6                # white PLA diffuser ring across the channel opening
# 3M Bumpon SJ5302 (7.9 mm x 2.2 mm): 1.8 mm recess leaves 0.4 mm proud
FOOT_RECESS_D, FOOT_RECESS = 8.6, 1.8

# ---------------------------------------------------------------- ESP32-C3 SuperMini
ESP_L, ESP_W, ESP_T = 22.5, 18.0, 1.0           # PCB; parts stand ~3 mm off one face
ESP_X = 45.5                                    # board plane, standing on edge
ESP_SLOT_W, ESP_SLOT_D = 1.3, 1.5               # card slot for the antenna-end edge
CAP_Y = 25.4                                    # 470 uF capacitor saddle, beside the ESP32
ESP_PINS = {"5v": "5V", "gnd": "GND", "data": "GPIO4"}   # via 74AHCT1G125 + 330 ohm


def led_positions():
    """(x, y, run) of each LED, in chain order: +X side going -Y, -Y side going -X,
    -X side going +Y, +Y side going +X."""
    a, b = W / 2 - CH_MID, D / 2 - CH_MID
    out = []
    for k in range(N_SHORT):
        out.append((a, (N_SHORT - 1) / 2 * PITCH - k * PITCH, "+x"))
    for k in range(N_LONG):
        out.append(((N_LONG - 1) / 2 * PITCH - k * PITCH, -b, "-y"))
    for k in range(N_SHORT):
        out.append((-a, -(N_SHORT - 1) / 2 * PITCH + k * PITCH, "-x"))
    for k in range(N_LONG):
        out.append((-(N_LONG - 1) / 2 * PITCH + k * PITCH, b, "+y"))
    return out


def strip_runs():
    """(x0, y0, x1, y1) of each cut strip segment: one LED pitch per LED."""
    a, b = W / 2 - CH_MID, D / 2 - CH_MID
    hs, hl = N_SHORT * PITCH / 2, N_LONG * PITCH / 2
    return [(a, hs, a, -hs), (hl, -b, -hl, -b), (-a, -hs, -a, hs), (-hl, b, hl, b)]


def _ring_rect(name, inset0, inset1, z0, z1, r_out):
    """Rounded-rectangle band between two insets from the shell outline."""
    outer = S.rounded_box(name, W - 2 * inset0, D - 2 * inset0, z1 - z0,
                          r=max(r_out - inset0, 0.5), loc=(0, 0, z0))
    S.bake(outer)
    inner = S.rounded_box(name + "_in", W - 2 * inset1, D - 2 * inset1, z1 - z0 + 2,
                          r=max(r_out - inset1, 0.5), loc=(0, 0, z0 - 1))
    S.cut(outer, inner)
    return outer


def label_cutter(body, size, right_x, front_y, top_z, depth=0.6):
    """Engraved label in the bold mono label font, placed by its real bounding box:
    right edge at right_x, front edge at front_y."""
    ob = S.text("label", body, size, 2 * depth, loc=(0, 0, top_z), align="LEFT",
                font=S.label_font())
    S.bake(ob)
    vs = [v.co for v in ob.data.vertices]
    dx = right_x - max(v.x for v in vs)
    dy = front_y - min(v.y for v in vs)
    for v in ob.data.vertices:
        v.co.x += dx
        v.co.y += dy
    vs = [v.co for v in ob.data.vertices]
    box = (min(v.x for v in vs), min(v.y for v in vs), max(v.x for v in vs),
           max(v.y for v in vs))
    return ob, box


# The separator is a placeholder: the owner is choosing a new one (CLAUDE.md, open items).
LABEL = {"parts": ("HOME", "01"), "size": 6.0, "depth": 0.6, "right_inset": 14.0,
         "front_inset": 10.0}          # HOME · 01, house dot (S.product_label)


def build():
    S.reset()
    white, black = S.pla("white"), S.pla("black")

    # ------------------------------------------------ shell
    shell = S.rounded_box("Shell", W, D, SHELL_H, r=R, r_top=S.EDGE_R, r_bot=0.4,
                          loc=(0, 0, SHELL_Z0))
    S.bake(shell)
    cavity = S.rounded_box("cavity", W - 2 * WALL, D - 2 * WALL, SHELL_H - ROOF + 1,
                           r=R - WALL, loc=(0, 0, SHELL_Z0 - 1))
    S.cut(shell, cavity)
    adds = []
    for x, y in BOSS:      # bosses stand on the floor plate, above the skirt
        h = ROOF_IN - FLOOR_TOP + 0.5
        adds.append(S.cylinder("boss", BOSS_D, h, loc=(x, y, FLOOR_TOP + h / 2)))
    S.union(shell, adds)
    cutters = []
    for x, y in BOSS:
        cutters.append(S.cylinder("insert", INSERT_HOLE_D, INSERT_HOLE_DEPTH + 1,
                                  loc=(x, y, FLOOR_TOP + (INSERT_HOLE_DEPTH - 1) / 2)))
    pb = PORT_WIN
    bay = S.slot("io_bay", pb["y1"] - pb["y0"] + 2 * BAY_MARGIN, pb["z1"] - pb["z0"] + 2 * BAY_MARGIN,
                 2 * BAY_DEPTH, loc=(-W / 2, (pb["y0"] + pb["y1"]) / 2, (pb["z0"] + pb["z1"]) / 2),
                 axis="X", r=2.6)
    wins = []
    for pw in PORT_WINS:
        yc, zc = (pw["y0"] + pw["y1"]) / 2, (pw["z0"] + pw["z1"]) / 2
        wins.append(S.slot("port_" + pw["name"], pw["y1"] - pw["y0"], pw["z1"] - pw["z0"], 10,
                           loc=(-W / 2, yc, zc), axis="X", r=2.0))
    S.union(bay, wins)                 # one cutter: no edges where bay and windows meet
    cutters.append(bay)
    cutters.append(S.slot("usbc", *USBC_SLOT, 10, loc=(USBC[0], D / 2, BOARD_TOP + 1.6),
                          axis="Y"))
    S.cut(shell, cutters)
    # no roof vents in v5: air enters underneath and leaves through the I/O bay (CLAUDE.md)
    lab = S.product_label("label", LABEL["parts"], LABEL["size"], 2 * LABEL["depth"])
    vs = [v.co for v in lab.data.vertices]
    dx = W / 2 - LABEL["right_inset"] - max(v.x for v in vs)
    dy = -D / 2 + LABEL["front_inset"] - min(v.y for v in vs)
    for v in lab.data.vertices:
        v.co.x += dx
        v.co.y += dy
        v.co.z += TOP
    lab.data.update()
    vs = [v.co for v in lab.data.vertices]
    box = (min(v.x for v in vs), min(v.y for v in vs), max(v.x for v in vs), max(v.y for v in vs))
    flat = (-W / 2 + S.EDGE_R, -D / 2 + S.EDGE_R, W / 2 - S.EDGE_R, D / 2 - S.EDGE_R)
    assert box[2] <= flat[2] - 1 and box[1] >= flat[1] + 1, f"label {box} too near the fillet"
    S.cut(shell, [lab])
    check(shell, (W, D, SHELL_H))
    S.assign(shell, white)
    S.smooth(shell)

    # ------------------------------------------------ floor (black, printed flat)
    fw, fd, fr = W - 2 * IN_IN, D - 2 * IN_IN, R - IN_IN
    floor = S.rounded_box("Floor", fw, fd, FLOOR_T, r=fr, loc=(0, 0, FLOOR_Z0))
    S.bake(floor)
    z1 = FLOOR_TOP
    stand = [S.cylinder("standoff", 6, STANDOFF_H + 0.5,
                        loc=(x, y, z1 + STANDOFF_H / 2 - 0.25)) for x, y in PI_HOLES]
    # ESP32 cradle: a card slot that takes the board's antenna-end edge (pads stay clear);
    # the USB-C end points up for flashing with the shell off. A dab of hot glue holds it.
    cradle = S.box("esp_cradle", 4.0, ESP_W + 4.0, 2.0, loc=(ESP_X, 0, z1 + 0.99))
    # saddle for the strip's 470 uF capacitor (6.3 x 11 mm), lying along X
    saddle = [S.box("cap_saddle", 2.0, 8.0, 2.5, loc=(x, CAP_Y, z1 + 1.24)) for x in (39.5, 47.0)]
    S.union(floor, stand + [cradle] + saddle)
    holes = []
    for x, y in PI_HOLES:   # M2.5 screws from the top, through the Pi into the standoffs
        holes.append(S.cylinder("m25", 2.2, 6.0, loc=(x, y, z1 + STANDOFF_H - 2.5)))
    for x, y in BOSS:
        holes.append(S.cylinder("m3", 3.4, 10, loc=(x, y, FLOOR_Z0)))

    zs = z1 + 2.0 - ESP_SLOT_D + (ESP_SLOT_D + 1) / 2
    holes.append(S.box("esp_slot", ESP_SLOT_W, ESP_W + 0.4, ESP_SLOT_D + 1, loc=(ESP_X, 0, zs)))
    # relief in the middle: only the board's bare corners are gripped (antenna, end pads clear)
    holes.append(S.box("esp_relief", 3.6, ESP_W - 6.0, ESP_SLOT_D + 1, loc=(ESP_X, 0, zs)))
    holes.append(S.cylinder("cap_bed", 6.8, 12.0, loc=(43.25, CAP_Y, z1 + 3.4),
                            rot=(0, math.pi / 2, 0)))
    wx, wy, wd = WIRE_HOLE
    fx, fy = FLOOR_HOLE
    holes.append(S.cylinder("wire", wd, 10, loc=(fx, fy, FLOOR_Z0)))
    groove = S.box("wire_groove", wd, wy - fy, 2.4, loc=(wx, (wy + fy) / 2, FLOOR_Z0))
    holes += [groove, S.cylinder("wire_end", wd, 2.4, loc=(wx, wy, FLOOR_Z0))]
    for x in INTAKE_FLOOR_X:
        holes.append(S.slot("intake", INTAKE_W, INTAKE_L, 10, loc=(x, 0, FLOOR_Z0), axis="Z",
                            r=INTAKE_W / 2 - 0.01))
    S.cut(floor, holes)
    check(floor, (fw, fd, FLOOR_T + STANDOFF_H))
    S.assign(floor, black)
    S.smooth(floor)

    plinth = build_plinth()
    S.assign(plinth, black)
    return shell, floor, plinth


def build_plinth():
    """Top plate + black lining inside the shell's skirt + foot, with the LED channel
    between lining and foot. Printed upside-down (top plate on the bed)."""
    pw, pd, pr = W - 2 * IN_IN, D - 2 * IN_IN, R - IN_IN
    plate = S.rounded_box("Plinth", pw, pd, PLATE_T, r=pr, loc=(0, 0, Z_PLATE_BOT))
    S.bake(plate)
    lining = _ring_rect("lining", IN_IN, CH_IN0, LINING_Z, Z_PLATE_BOT + 0.01, R)
    # inward floor at the lining's foot; starts inside the lining wall and 0.05 mm above its
    # bottom face so no faces coincide (coincident faces break the EXACT boolean)
    if FLANGE > 0:
        S.union(lining, [_ring_rect("flange", IN_IN + 0.5, CH_IN0 + FLANGE, LINING_Z + 0.05,
                                    LINING_Z + FLANGE_T, R)])
    foot = S.rounded_box("foot", W - 2 * FOOT_IN, D - 2 * FOOT_IN, Z_PLATE_BOT + 0.01 - FOOT_GAP,
                         r=FOOT_R, loc=(0, 0, FOOT_GAP))
    S.bake(foot)
    S.cut(foot, [S.rounded_box("foot_in", W - 2 * (FOOT_IN + FOOT_WALL),
                               D - 2 * (FOOT_IN + FOOT_WALL), Z_PLATE_BOT + 2,
                               r=FOOT_R - 1.0, loc=(0, 0, -1))])
    pads = [S.cylinder("pad", PAD_D, Z_PLATE_BOT + 0.01, loc=(x, y, Z_PLATE_BOT / 2))
            for x, y in FEET]
    zt = LIFT + SKIRT
    rim = _ring_rect("rim", IN_IN, IN_IN + RIM_W, zt - 0.01, zt + PLENUM, R)
    spacers = [S.cylinder("spacer", SCREW_POST_D, PLENUM + 0.01, loc=(x, y, zt + PLENUM / 2))
               for x, y in BOSS]
    # inner ledge for the diffuser, on the foot ring's outer face
    zd = LINING_Z + FLANGE_T
    dled = S.rounded_box("diff_ledge", W - 2 * (FOOT_IN - 1.0), D - 2 * (FOOT_IN - 1.0),
                         zd - LINING_Z - 0.05, r=FOOT_R + 1.0, loc=(0, 0, LINING_Z + 0.05))
    S.bake(dled)
    S.cut(dled, [S.rounded_box("diff_ledge_in", W - 2 * FOOT_IN - 0.4, D - 2 * FOOT_IN - 0.4,
                               10, r=FOOT_R - 0.2, loc=(0, 0, -1))])
    posts = [S.cylinder("post", SCREW_POST_D, Z_PLATE_BOT - SCREW_SEAT + 0.01,
                        loc=(x, y, (SCREW_SEAT + Z_PLATE_BOT) / 2)) for x, y in BOSS] \
        if POSTS else []
    zl = Z_PLATE_BOT - LEDGE_GAP                   # strip PCB rests on these lips
    ledge_in = S.rounded_box("ledge_in", W - 2 * (FOOT_IN - LEDGE), D - 2 * (FOOT_IN - LEDGE),
                             LEDGE_T, r=FOOT_R + LEDGE, loc=(0, 0, zl - LEDGE_T))
    S.bake(ledge_in)
    S.cut(ledge_in, [S.rounded_box("ledge_in_in", W - 2 * FOOT_IN - 0.02,
                                   D - 2 * FOOT_IN - 0.02, LEDGE_T + 2, r=FOOT_R,
                                   loc=(0, 0, zl - LEDGE_T - 1))])
    ledges = [_ring_rect("ledge_out", CH_IN0 - 0.4, CH_IN0 + LEDGE, zl - LEDGE_T, zl, R),
              ledge_in]
    S.union(plate, [lining, foot, rim, dled] + pads + spacers + posts + ledges)
    cuts = []
    for x, y in BOSS:
        cuts.append(S.cylinder("m3", 3.4, 2 * (LIFT + SKIRT), loc=(x, y, LIFT)))
        if not POSTS:   # head pocket through the plate (and lip and flange below it);
            z0, z1 = LINING_Z - 0.5, Z_PLATE_BOT + 1.7     # head top 0.3 mm into the spacer
            cuts.append(S.cylinder("head", HEAD_POCKET_D, z1 - z0, loc=(x, y, (z0 + z1) / 2)))
    for x in INTAKE_PLATE_X:
        cuts.append(S.slot("intake", INTAKE_W, INTAKE_L, 20, loc=(x, 0, Z_PLATE_BOT), axis="Z",
                           r=INTAKE_W / 2 - 0.01))
    for x, y in FEET:
        cuts.append(S.cylinder("foot_recess", FOOT_RECESS_D, 2 * FOOT_RECESS, loc=(x, y, 0)))
    wx, wy, wd = WIRE_HOLE
    cuts.append(S.cylinder("wire", wd, 10, loc=(wx, wy, LIFT + SKIRT)))
    S.cut(plate, cuts)
    check(plate, (pw, pd, LIFT + SKIRT + PLENUM))
    S.smooth(plate)
    return plate


def build_diffuser():
    """White PLA ring across the channel opening: blends the LEDs into one band (corners too)
    and hides their reflections. Rests on the lining's flange and the foot ring's ledge.
    Printed flat, 0.6 mm (3 layers at 0.2)."""
    z0 = LINING_Z + FLANGE_T
    d = _ring_rect("Diffuser", CH_IN0 + 0.15, FOOT_IN - 0.15, z0, z0 + DIFF_T, R)
    check(d, (W - 2 * (CH_IN0 + 0.15), D - 2 * (CH_IN0 + 0.15), DIFF_T))
    S.smooth(d)
    return d


def check(ob, size):
    """Guard against a boolean quietly wrecking a part: outer size and positive volume."""
    d = S.dims(ob)
    assert all(abs(a - b) < 0.02 for a, b in zip(d, size)), f"{ob.name}: size {d} vs {size}"
    assert S.volume(ob) > 0, f"{ob.name}: volume {S.volume(ob)}"


# ---------------------------------------------------------------- reference parts
def _curve(name, pts, radius, mat):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 4
    sp = cu.splines.new("POLY")              # straight runs: no Bezier overshoot
    sp.points.add(len(pts) - 1)
    for pt, p in zip(sp.points, pts):
        pt.co = (*p, 1.0)
    ob = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return ob


def strip_mock():
    """Cut strip segments (white PCB) with 5050 LEDs facing down. Returns (pcbs, leds)."""
    pcb_mat = S.material("Strip PCB", (0.75, 0.75, 0.72, 1), rough=0.5)
    led_mat = S.material("5050 LED", (0.92, 0.92, 0.9, 1), rough=0.3)
    pcbs, leds = [], []
    z_pcb = Z_PLATE_BOT - LEDGE_GAP + STRIP_PCB_T / 2
    for k, (x0, y0, x1, y1) in enumerate(strip_runs()):
        L = math.dist((x0, y0), (x1, y1))
        b = S.box(f"strip{k}", L if y0 == y1 else STRIP_W, STRIP_W if y0 == y1 else L,
                  STRIP_PCB_T, loc=((x0 + x1) / 2, (y0 + y1) / 2, z_pcb))
        pcbs.append(S.assign(b, pcb_mat))
    for k, (x, y, _) in enumerate(led_positions()):
        b = S.box(f"led{k:02d}", LED_SIZE, LED_SIZE, LED_H,
                  loc=(x, y, Z_LED_FACE + LED_H / 2))
        leds.append(S.assign(b, led_mat))
    return pcbs, leds


def esp_mock():
    pcb = S.material("ESP PCB", (0.02, 0.02, 0.025, 1), rough=0.35, coat=0.5)
    metal = S.material("Steel", (0.78, 0.78, 0.8, 1), rough=0.22)
    metal.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 1.0
    z1 = FLOOR_TOP
    zb = z1 + 2.0 - ESP_SLOT_D                       # board edge on the slot floor
    board = S.box("esp_pcb", ESP_T, ESP_W, ESP_L, loc=(ESP_X, 0, zb + ESP_L / 2))
    usb = S.box("esp_usbc", 3.2, 8.9, 7.4, loc=(ESP_X - 2.1, 0, zb + ESP_L - 3.2))
    chip = S.box("esp_can", 1.0, 7.0, 7.0, loc=(ESP_X - 1.0, 0, zb + 11.0))
    return S.join([S.assign(board, pcb), S.assign(usb, metal), S.assign(chip, metal)],
                  "ESP32-C3 (reference)")


def harness():
    """Strip leads up through the floor to the ESP32; ESP32 power from the Pi header."""
    w_red = S.material("Wire red", (0.55, 0.03, 0.02, 1), rough=0.45)
    w_blk = S.material("Wire black", (0.02, 0.02, 0.02, 1), rough=0.45)
    w_yel = S.material("Wire yellow", (0.75, 0.6, 0.05, 1), rough=0.45)
    housing = S.material("Dupont housing", (0.02, 0.02, 0.02, 1), rough=0.6)
    cols = {"5v": w_red, "gnd": w_blk, "data": w_yel}
    wx, wy, _ = WIRE_HOLE
    fx, fy = FLOOR_HOLE
    z1 = FLOOR_TOP
    wires, parts = [], []
    for i, sig in enumerate(("5v", "gnd", "data")):
        off = (i - 1) * 1.3
        pts = [(wx + off, N_SHORT / 2 * PITCH - 1.0, Z_PLATE_BOT - 0.4),
               (wx + off, wy, Z_PLATE_BOT - 0.4), (wx + off, wy, FLOOR_Z0 - 0.6),
               (fx + off, fy, FLOOR_Z0 - 0.6), (fx + off, fy, z1 + 2.0),
               (ESP_X - 1.2, 8.0, z1 + 6.0 + i * 2.54)]
        wires.append(_curve(f"wire_strip_{sig}", pts, 0.45, cols[sig]))
    for i, (sig, pin) in enumerate(HEADER_USED.items()):
        hx, hy = header_pin_xy(pin)
        parts.append(S.assign(S.box(f"dupont_{sig}", 2.54, 2.54, 8.0,
                                    loc=(hx, hy, BOARD_TOP + 2.5 + 4.0)), housing))
        pts = [(hx, hy, DUPONT_TOP - 1.0), (hx, hy - 4.0, DUPONT_TOP - 1.0),
               (ESP_X - 6.0, hy - 6.0 - i * 1.5, DUPONT_TOP - 1.0),
               (ESP_X - 1.2, -8.0, z1 + 6.0 + i * 2.54)]
        wires.append(_curve(f"wire_pwr_{sig}", pts, 0.45, cols[sig]))
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
        if n in HEADER_USED.values():
            continue
        px, py = header_pin_xy(n)
        parts.append(S.assign(S.box("pin", 0.64, 0.64, 6.0, loc=(px, py, BOARD_TOP + 5.5)), gold))
    hs = S.rounded_box("cooler", 50, 36, 7, r=1.5, loc=(FAN_C[0] - 2, FAN_C[1], BOARD_TOP + 2.5))
    parts.append(S.assign(hs, alu))
    f = S.cylinder("fan", 28, 2.5, loc=(FAN_C[0], FAN_C[1], BOARD_TOP + 10.6))
    parts.append(S.assign(f, fan))
    return S.join(parts, "Pi5 (reference)")


# ---------------------------------------------------------------- light
BLUE, ORANGE = (0.08, 0.32, 1.0), (1.0, 0.42, 0.03)
LED_W_NIGHT = 0.015          # ~4.5 lm per LED at the 0.5 A cap (as in underglow_study.py)
LED_W_DAY = LED_W_NIGHT


def scattering_white():
    """White PLA with subsurface scattering (1.2 mm), for parts light passes through."""
    m = S.material("PLA white (scattering)", S.PLA["white"], rough=0.5)
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Subsurface Weight"].default_value = 1.0
    b.inputs["Subsurface Radius"].default_value = (1.0, 1.0, 1.0)
    b.inputs["Subsurface Scale"].default_value = 0.0012
    return m


def gradient(t):
    k = 0.5 - 0.5 * math.cos(2 * math.pi * t)
    return tuple(b + (o - b) * k for b, o in zip(BLUE, ORANGE))


def led_lights():
    obs = []
    pos = led_positions()
    for k, (x, y, _) in enumerate(pos):
        li = bpy.data.lights.new(f"glow{k:02d}", "AREA")     # 5 mm emitter facing down
        li.shape, li.size = "SQUARE", 0.005
        li.energy = LED_W_NIGHT
        li.color = gradient(k / len(pos))
        ob = bpy.data.objects.new(li.name, li)
        bpy.context.collection.objects.link(ob)
        ob.location = (x / 1000, y / 1000, (Z_LED_FACE - 0.05) / 1000)
        obs.append(ob)
    return obs


def room(dim):
    k = 0.03 if dim else 1.0
    for ob in bpy.data.objects:     # studio lights only; the LED emitters keep their output
        if ob.type == "LIGHT" and ob.data.type == "AREA" and not ob.name.startswith("glow"):
            ob.data.energy = ob["base"] * k
    bpy.context.scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = (
        0.08 * k)


def write_dims_json(out):
    """Every number the dimension drawings print, taken from the model."""
    data = {
        "rev": REV, "W": W, "D": D, "TOP": TOP, "LIFT": LIFT, "FLOOR_T": FLOOR_T, "SKIRT": SKIRT,
        "WALL": WALL, "ROOF": ROOF, "R": R, "shadow_gap": S.SHADOW_GAP,
        "port_win": PORT_WIN,
        "usbc": {"x": USBC[0], "z": BOARD_TOP + 1.6, "w": USBC_SLOT[0], "h": USBC_SLOT[1]},
        "boss": BOSS, "boss_d": BOSS_D, "insert_d": INSERT_HOLE_D,
        "insert_depth": INSERT_HOLE_DEPTH, "pi_source": PI["source"], "feet": FEET,
        "plinth": {"inset": IN_IN, "plate_t": PLATE_T, "lining_t": LINING_T, "lining_z": LINING_Z,
                   "foot_in": FOOT_IN, "ch_in0": CH_IN0, "ch_in1": CH_IN1, "ch_mid": CH_MID,
                   "z_plate_bot": Z_PLATE_BOT, "z_led_face": Z_LED_FACE,
                   "screw_seat": SCREW_SEAT, "post_d": SCREW_POST_D},
        "strip": {"w": STRIP_W, "pitch": PITCH, "n_long": N_LONG, "n_short": N_SHORT,
                  "runs": strip_runs(), "leds": [p[:2] for p in led_positions()]},
        "wire_hole": WIRE_HOLE, "floor_hole": FLOOR_HOLE, "port_wins": PORT_WINS,
        "esp": {"x": ESP_X, "w": ESP_W, "l": ESP_L},
        "fan_c": FAN_C, "label": LABEL,
    }
    with open(os.path.join(out, "dims.json"), "w") as f:
        json.dump(data, f, indent=1)


def main():
    args = sys.argv[1:]
    shell, floor, plinth = build()
    os.makedirs(os.path.join(HERE, "stl"), exist_ok=True)
    for f in ("hub_lightpipe_red.stl", "hub_lightcarrier_black.stl", "hub_base_black.stl",
              "hub_lighttest_skin_white.stl"):     # earlier revisions' parts
        p = os.path.join(HERE, "stl", f)
        if os.path.exists(p):
            os.remove(p)
    S.export_stl(shell, os.path.join(HERE, "stl", "hub_shell_white.stl"))
    S.export_stl(floor, os.path.join(HERE, "stl", "hub_floor_black.stl"))
    diff = build_diffuser()
    S.assign(diff, scattering_white())
    S.export_stl(diff, os.path.join(HERE, "stl", "hub_diffuser_white.stl"))
    S.export_stl(plinth, os.path.join(HERE, "stl", "hub_plinth_black.stl"))
    # Fit test: the last 15 mm of the shell at the ports end (~20 min print).
    test = shell.copy()
    test.data = shell.data.copy()
    bpy.context.collection.objects.link(test)
    keep = S.box("keep", 16, D + 10, TOP + 10, loc=(-W / 2 + 8.0, 0, TOP / 2))   # clear of inserts
    md = test.modifiers.new("keep", "BOOLEAN")
    md.operation, md.solver, md.object = "INTERSECT", "EXACT", keep
    S.bake(test)
    bpy.data.objects.remove(keep, do_unlink=True)
    S.export_stl(test, os.path.join(HERE, "stl", "hub_fittest_portsend_white.stl"))
    bpy.data.objects.remove(test, do_unlink=True)

    pi = pi_mock()
    pcbs, leds = strip_mock()
    esp = esp_mock()
    hparts, wires = harness()
    strip = pcbs + leds
    root = S.to_studio([shell, floor, plinth, diff, pi, esp] + strip + hparts + wires)
    S.studio()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "hub.blend"))
    out = os.path.join(HERE, "renders")
    sc = bpy.context.scene
    if "--preview" in args:
        out = os.path.join(HERE, "renders", "_preview")
        sc.cycles.samples = 16
        sc.render.resolution_x, sc.render.resolution_y = 800, 600
    os.makedirs(out, exist_ok=True)
    write_dims_json(out)
    inside = [pi, esp] + hparts + wires
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
        # exploded, bottom to top: plinth + strip | floor + ESP32 | Pi | shell
        show(inside, True)
        show(wires + hparts, False)
        moves = [(shell, (0, 0, 115)), (pi, (0, 0, 55)), (floor, (0, 0, 28)), (esp, (0, 0, 28))]
        for o, d in moves:
            shift([o], d)
        S.camera((0.36, -0.52, 0.32), target=(0, 0, 0.075), lens=55)
        S.render(os.path.join(out, "hub_exploded.png"))
        for o, d in moves:
            shift([o], tuple(-k for k in d))
        # cutaway: the shell's +Y half removed to show the stack and the wiring
        show(inside, True)
        # (cut copies with the guarded S.cut: a live EXACT modifier emptied floor and plinth)
        halves = []
        gone = [o for o in strip if max(v.co.y for v in o.data.vertices) > 2]
        gone += [w for w in wires if w.name.startswith("wire_strip")]
        show(gone + [pi], False)
        for o in (shell, floor, plinth, diff):   # (the Pi and ESP32 stand-ins are too crude to cut;
                                           #  the Pi stays out of this view)
            c = o.copy()
            c.data = o.data.copy()
            bpy.context.collection.objects.link(c)
            cut = S.box("half_cut", W + 20, D, TOP + 20, loc=(0, D / 2 + 2, TOP / 2))
            cut.parent = root
            S.cut(c, [cut])
            c.hide_render = False
            halves.append(c)
        show([shell, floor, plinth, diff], False)
        S.camera((0.20, 0.30, 0.17), target=(0.004, 0.0, 0.016), lens=60)
        S.render(os.path.join(out, "hub_cutaway.png"))
        for c in halves:
            bpy.data.objects.remove(c, do_unlink=True)
        show([shell, floor, plinth, diff] + gone, True)
        show(inside, False)
        root.rotation_euler = (math.pi, 0, 0)
        root.location = (0, 0, TOP * m)
        S.camera((0.22, -0.30, 0.20), target=(0, 0, 0.014))
        S.render(os.path.join(out, "hub_underside.png"))
        root.rotation_euler = (0, 0, 0)
        root.location = (0, 0, 0)

    if "--details" in args:
        show(inside, False)
        res0 = (sc.render.resolution_x, sc.render.resolution_y)
        if "--preview" not in args:
            sc.render.resolution_x, sc.render.resolution_y = 1400, 1050
        lx, ly = (W / 2 - LABEL["right_inset"] - 15) * m, (-D / 2 + LABEL["front_inset"] + 2) * m
        S.camera((lx + 0.02, ly - 0.075, 0.11), target=(lx, ly, TOP * m), lens=100)
        S.render(os.path.join(out, "d_label.png"))
        # the I/O bay on its own (no Pi): the recessed panel that is also the exhaust
        S.camera((-0.15, -0.07, 0.05), target=(-W / 2 * m, 0, 0.026), lens=85)
        S.render(os.path.join(out, "d_iobay.png"))
        # the float: low view of the corner, shadow line, gap and plinth
        S.camera((0.150, -0.150, 0.012), target=(W / 2 * m - 0.012, -D / 2 * m + 0.012, 0.006),
                 lens=85)
        S.render(os.path.join(out, "d_float.png"))
        show([pi], True)
        S.camera((-0.13, -0.05, 0.035), target=(-W / 2 * m, 0, 0.020), lens=70)
        S.render(os.path.join(out, "d_ports_end.png"))
        S.camera((0.05, 0.14, 0.045), target=(USBC[0] * m, D / 2 * m, 0.015), lens=100)
        S.render(os.path.join(out, "d_usbc.png"))
        show([pi], False)
        # underside close-up of the channel with the strip in it
        root.rotation_euler = (math.pi, 0, 0)
        root.location = (0, 0, TOP * m)
        S.camera((0.12, -0.11, 0.11), target=(W / 2 * m - 0.012, -D / 2 * m + 0.02, 0.040),
                 lens=85)
        S.render(os.path.join(out, "d_channel.png"))
        root.rotation_euler = (0, 0, 0)
        root.location = (0, 0, 0)
        sc.render.resolution_x, sc.render.resolution_y = res0

    if "--light" in args:
        # dark room and room light, glow on (gradient as in the concept renders), plus off
        show(inside, False)
        lights = led_lights()
        sc.cycles.max_bounces = 16
        for ob in bpy.data.objects:
            if ob.type == "LIGHT" and ob.data.type == "AREA":
                ob["base"] = ob.data.energy
        S.camera((0.22, -0.31, 0.13), target=(0.0, 0.0, 0.018), lens=62)
        for name, dim, on in (("dark", True, True), ("room", False, True)):
            for li in lights:
                li.hide_render = not on
                li.data.energy = LED_W_NIGHT if dim else LED_W_DAY
            room(dim)
            S.render(os.path.join(out, f"hub_light_{name}.png"))
        room(False)
        for li in lights:
            li.hide_render = True

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
                       "res": [sc.render.resolution_x, sc.render.resolution_y]}
        # section through the channel at y = 0, seen from the front, +X end
        bpy.context.scene.view_layers[0].material_override = None
        # cut copies with the guarded S.cut; the strip needs no cut, the camera's near clip
        # plane (at y = 0) hides everything in front of the section
        show(strip, True)
        for o in (shell, floor, plinth):
            c = o.copy()
            c.data = o.data.copy()
            bpy.context.collection.objects.link(c)
            sec = S.box("sec", 300, 100, 200, loc=(0, -50.0 - 0.5, 0))   # section plane at y = -0.5
            sec.parent = root
            S.cut(c, [sec])
            o.hide_render = True
        c = (W / 2 - 12.0, 0, 9.0)
        cam = S.ortho_camera("front", tuple(k * m for k in c), 0.030)
        cam.data.clip_start, cam.data.clip_end = 0.5 - 0.0007, 0.5 + 0.004
        S.render(os.path.join(out, "dwg_section_channel.png"))
        meta["section_channel"] = {"view": "front", "center_mm": c, "scale_mm": 30.0,
                                   "res": [sc.render.resolution_x, sc.render.resolution_y]}
        with open(os.path.join(out, "dwg_cameras.json"), "w") as f:
            json.dump(meta, f, indent=1)


if __name__ == "__main__":
    main()
