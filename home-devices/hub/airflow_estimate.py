"""Airflow and temperature estimate for the hub (v5): a lumped model, not CFD.

Run:  python airflow_estimate.py          (plain Python; reads the geometry from hub.py's
                                           constants by parsing, no Blender needed)
Writes renders/airflow.json and prints a table.

Model
- Heat in: Pi 5 (idle Home Assistant ~3 W, busy ~6 W) + ESP32-C3 (0.3 W). The LEDs (up to
  2.5 W at the cap) sit in the channel under the floor, outside the air path, so they are left
  out of the cavity balance (they warm the plinth; see the report).
- Heat out:
  1. through the shell: U*A, with inside natural convection h_i = 4, PLA wall 2 mm
     (k = 0.13), outside convection + radiation h_o = 9 W/m2K;
  2. by air exchange: m_dot * cp * dT through intake -> plenum -> floor slots -> cavity ->
     I/O bay openings.
- Air exchange is driven by buoyancy (stack height from the intake to the exhaust centre) and,
  with the fan on, by the Active Cooler stirring the cavity. Only part of a blower's push
  becomes through-flow; it is modelled as an extra 1-3 Pa across the vents (a guess, bounded
  both ways below).
- Each opening is an orifice (Cd 0.6); openings in series add as 1/A^2.
Treat the numbers as a ranking of scenarios and an order of magnitude, then measure:
`vcgencmd measure_temp` and `vcgencmd get_throttled` during a 10 min stress test.
"""
import json
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "hub.py"), encoding="utf-8").read()


def const(name):
    """A numeric constant from hub.py, including tuple assignments like `W, D = 106.0, 80.0`."""
    for m in re.finditer(r"^([A-Z_][A-Z0-9_, ]*?)\s*=\s*([-\d., ]+?)\s*(?:#.*)?$", src, re.M):
        names = [n.strip() for n in m.group(1).split(",")]
        vals = [v.strip() for v in m.group(2).split(",")]
        if name in names and len(names) == len(vals):
            return float(vals[names.index(name)])
    raise KeyError(name)


W, D, TOP, LIFT, SKIRT, PLENUM = (const(n) for n in ("W", "D", "TOP", "LIFT", "SKIRT", "PLENUM"))
WALL, FIT, FOOT_GAP = const("WALL"), const("FIT"), const("FOOT_GAP")
INTAKE_W, INTAKE_L = const("INTAKE_W"), const("INTAKE_L")
CH_W = 12.0 + 0.3
FOOT_IN = WALL + FIT + 1.0 + CH_W
N_PLATE, N_FLOOR = 4, 5

RHO, CP, G, T0, CD = 1.2, 1005.0, 9.81, 298.0, 0.6
H_I, H_O, K_PLA = 4.0, 9.0, 0.13
mm2 = 1e-6

# ---------------------------------------------------------------- openings (m2)
slot = INTAKE_W * (INTAKE_L - INTAKE_W) + math.pi * (INTAKE_W / 2) ** 2      # stadium
A_gap = 2 * ((W - 2 * FOOT_IN) + (D - 2 * FOOT_IN)) * FOOT_GAP * mm2           # under the foot ring
A_plate = N_PLATE * slot * mm2
A_floor = N_FLOOR * slot * mm2
A_plen = 2 * (D - 2 * FOOT_IN) * PLENUM * mm2 * 3                              # sideways, ~3 paths
# I/O bay: windows 15.9+2 / 13.1+2 wide x (15.6+1+0.2) tall. The Pi's jack housings sit
# just behind the windows and fill most of them, plugged or not: the free area is the frame
# round each jack (design review v5), so the port scenarios differ very little.
win = {"eth": (17.9, 16.8), "usb3": (15.1, 16.8), "usb2": (15.1, 16.8)}
jack = {"eth": (15.9, 13.5), "usb3": (13.1, 15.6), "usb2": (13.1, 15.6)}
plug = {"eth": (0.0, 0.0), "usb3": (0.0, 0.0), "usb2": (0.0, 0.0)}   # plugs sit inside the jacks
usbc_gap = (14.0 * 8.0 - 8.9 * 3.2) * mm2 * 0.5                                  # around the cable


def exhaust(used):
    a = usbc_gap
    for k, (w, h) in win.items():
        a += (w * h - jack[k][0] * jack[k][1]) * mm2
    return a


SCEN = {"Ethernet + USB-C only (typical)": ("eth",),
        "Ethernet + Zigbee stick": ("eth", "usb3"),
        "all ports used": ("eth", "usb3", "usb2")}


def series(*areas):
    return 1 / math.sqrt(sum(1 / a ** 2 for a in areas))


# ---------------------------------------------------------------- shell conduction
A_shell = (W * D + 2 * (W + D) * (TOP - LIFT)) * mm2
U = 1 / (1 / H_I + (WALL / 1000) / K_PLA + 1 / H_O)
UA = U * A_shell

H_STACK = ((20.1 + 36.7) / 2 - (LIFT + SKIRT + PLENUM / 2)) / 1000   # intake plenum -> bay centre


def solve(P, A_eff, dp_fan):
    """Inside air rise dT (K) with heat P (W): P = UA dT + rho cp Q dT."""
    lo, hi = 0.0, 200.0
    for _ in range(80):
        dT = (lo + hi) / 2
        dp = RHO * G * H_STACK * dT / T0 + dp_fan
        Q = CD * A_eff * math.sqrt(2 * dp / RHO)
        out = UA * dT + RHO * CP * Q * dT
        lo, hi = (dT, hi) if out < P else (lo, dT)
    return dT, Q


def main():
    rows = []
    for name, used in SCEN.items():
        A_in = series(A_gap, A_plate, A_plen, A_floor)
        A_eff = series(A_in, exhaust(used))
        for load, P in (("idle", 3.3), ("busy", 6.3)):
            for fan, dp in (("fan off", 0.0), ("fan on (0.5-3 Pa)", 1.5)):
                dT, Q = solve(P, A_eff, dp)
                lo = solve(P, A_eff, 0.5)[0] if dp else dT
                hi = solve(P, A_eff, 3.0)[0] if dp else dT
                rows.append({"ports": name, "load": load, "P_W": P, "fan": fan,
                             "dT_air_K": round(dT, 1), "range_K": [round(hi, 1), round(lo, 1)],
                             "Q_L_per_s": round(Q * 1000, 3)})
    sealed = solve(3.3, 1e-12, 0.0)[0]
    out = {
        "areas_mm2": {"under_foot_ring": round(A_gap / mm2), "plate_slots": round(A_plate / mm2),
                      "plenum": round(A_plen / mm2), "floor_slots": round(A_floor / mm2),
                      "intake_effective": round(series(A_gap, A_plate, A_plen, A_floor) / mm2),
                      **{f"exhaust: {k}": round(exhaust(v) / mm2) for k, v in SCEN.items()}},
        "shell_UA_W_per_K": round(UA, 3), "stack_height_mm": round(H_STACK * 1000, 1),
        "sealed_idle_dT_K": round(sealed, 1), "rows": rows,
    }
    os.makedirs(os.path.join(HERE, "renders"), exist_ok=True)
    json.dump(out, open(os.path.join(HERE, "renders", "airflow.json"), "w"), indent=1)
    print(json.dumps(out["areas_mm2"], indent=1))
    print(f"shell UA {UA:.3f} W/K, stack {H_STACK*1000:.0f} mm, sealed box at idle: +{sealed:.0f} K")
    for r in rows:
        print(f"{r['ports']:34s} {r['load']:5s} {r['fan']:16s} air +{r['dT_air_K']:5.1f} K "
              f"(range {r['range_K']})  through-flow {r['Q_L_per_s']:.3f} L/s")


if __name__ == "__main__":
    main()
