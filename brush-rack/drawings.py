"""Dimensioned drawings for the brush rack (SVG over orthographic renders).

    python brush_rack.py --drawings && python drawings.py
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "home-devices", "tools"))
from dims import ACCENT, Sheet, fmt  # noqa: E402


def main():
    rd = os.path.join(HERE, "renders")
    d = json.load(open(os.path.join(rd, "dims.json")))
    cams = json.load(open(os.path.join(rd, "dwg_cameras.json")))
    L, D, H, Z0, PZ = d["L"], d["D"], d["H_TRAY"], d["Z0"], d["PZ"]
    rev = d["rev"]
    t, lf, lb = (math.radians(d[k]) for k in ("TILT", "LEAN_F", "LEAN_B"))
    out = {}

    def sheet(name):
        return Sheet(os.path.join(rd, f"dwg_{name}.png"), cams[name])

    # OPEN, from the side (screen right = +Y = back, up = +Z)
    s = sheet("open_side")
    y0, y1 = -D / 2, D / 2
    z_bf = Z0 + PZ + (d["UF"] + d["BAR_ABOVE"]) * math.cos(lf)
    z_bb = Z0 + PZ + (d["UB"] + d["BAR_ABOVE"]) * math.cos(lb)
    y_bb = d["YB"] + (d["UB"] + d["BAR_ABOVE"]) * math.sin(lb)
    s.dim_h(y0, y1, 0, -9, f"{fmt(round(D, 1))}")
    s.dim_v(0, z_bb, y1, y1 + 14, f"{fmt(round(z_bb, 1))}")
    s.dim_v(0, z_bf, y0, y0 - 9, f"{fmt(round(z_bf, 1))}")
    # brush axis through the large-groove bottoms
    yn, zn = d["YNF"], Z0 + d["HN"]
    s.line(yn - 70 * math.cos(t), zn - 70 * math.sin(t), yn + 95 * math.cos(t),
           zn + 95 * math.sin(t), w=1.6, color=ACCENT, dash="10 6")
    s.text(yn - 60, zn + 6, f"brush axis {fmt(d['TILT'])}° down", color=ACCENT, anchor="start",
           size=22)
    s.dim_h(yn, yn + d["SPAN"], zn + d["SPAN"] * math.tan(t), zn + 30,
            f"{fmt(d['SPAN'])} between supports", color=ACCENT)
    s.leader(d["YF"], Z0 + PZ, d["YF"] - 6, -20, f"front frame leans {fmt(d['LEAN_F'])}° fwd",
             anchor="end")
    s.leader(d["YB"], Z0 + PZ, d["YB"] - 8, -20, f"back frame leans {fmt(d['LEAN_B'])}° back")
    out["open_side"] = s.svg(f"OPEN  ·  SIDE  ·  REV {rev}  ·  mm",
                             "Both frames stop on a heel against the floor; gravity keeps them up")

    # OPEN, from the front: slot layout
    s = sheet("open_front")
    sl = d["slots"]
    s.dim_h(-L / 2, L / 2, 0, -9, f"{fmt(L)}")
    big = [q for q in sl if q["k"] == "L"]
    sm = [q for q in sl if q["k"] == "S"]
    zt = z_bf
    s.dim_h(sl[0]["x"], sl[-1]["x"], zt, zt + 30,
            f"10 slots, {fmt(round(sl[-1]['x'] - sl[0]['x'], 1))} c/c")
    q = big[0]
    s.leader(q["x"], zt - 10, q["x"] - 4, zt + 14,
             f"4× large V {fmt(q['angle'])}°, {fmt(q['depth'])} deep", color=ACCENT, anchor="start")
    q = sm[-1]
    s.leader(q["x"], zt - 6, q["x"] + 4, zt + 14,
             f"6× small V {fmt(q['angle'])}°, {fmt(q['depth'])} deep", color=ACCENT, anchor="end")
    out["open_front"] = s.svg(f"OPEN  ·  FRONT  ·  REV {rev}  ·  mm",
                              "Small slots: eye brushes (handles 5–9). Large: face brushes "
                              "(handles to ~14, heads to ~28 wide)")

    # FOLDED, top
    s = sheet("folded_top")
    s.dim_h(-L / 2, L / 2, -D / 2, -D / 2 - 9, f"{fmt(L)}")
    s.dim_v(-D / 2, D / 2, -L / 2, -L / 2 - 9, f"{fmt(round(D, 1))}")
    s.leader(L / 2 - 3, D / 2 - 3, L / 2 + 2, D / 2 + 7, "R10", anchor="end")
    s.leader(0, d["YB"] - d["UB"] - 4 + 5, 30, -D / 2 - 4, "finger holes: push up to lift a frame",
             anchor="start")
    out["folded_top"] = s.svg(f"FOLDED  ·  TOP  ·  REV {rev}  ·  mm")

    # FOLDED, side
    s = sheet("folded_side")
    s.dim_v(0, H, D / 2, D / 2 + 6, f"{fmt(H)}")
    s.dim_h(-D / 2, D / 2, 0, -6, f"{fmt(round(D, 1))}")
    out["folded_side"] = s.svg(f"FOLDED  ·  SIDE  ·  REV {rev}  ·  mm",
                               "Both frames lie flat inside the walls")

    for k, v in out.items():
        with open(os.path.join(rd, f"dwg_{k}.svg"), "w") as f:
            f.write(v)
    print(list(out))


if __name__ == "__main__":
    main()
