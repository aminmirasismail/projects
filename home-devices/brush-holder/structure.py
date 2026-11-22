"""Structural check of the Folio v2 brush stand (plain Python, no Blender).

    python structure.py            prints the report and writes renders/v2/structure.json

Hand calculations (beam theory) for every load path from a brush to the counter: clip ->
cartridge ledge -> shelf plate -> cross rib -> side rails / cheeks -> hinge stop and pin ->
panel -> stays and bottom hinge -> tray. Numbers mirror folio.py; keep them in step.

Load cases
  SUSTAINED  all 11 brushes at their upper-bound wet weight, x1.0, for months (creep: E_creep).
             This is what sets long-term sag.
  DESIGN     brushes x2.0 (wet, dropped in, heavier brushes later) + a hand pushing a brush in
             (4 N horizontal at the shelf) + a hand resting on the front edge (10 N x 1.5).
             Short-term modulus; stresses checked against strength / 2.5.

Material (printed PLA, conservative): E 3.0 GPa short-term, 1.0 GPa long-term creep modulus
(about a third, for loads held for months at room temperature); strength 45 MPa along the
layers, 25 MPa across them. Allowables: sustained 7 MPa along / 4 MPa across layers;
design 18 / 10 MPa (strength / 2.5). Steel dowels: 300 MPa allowable.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
G = 9.81e-3                                   # N per gram

# ------------------------------------------------------------------ inputs (from folio.py)
LOAD_G = {"B1": 12, "B2": 15, "B3": 20, "B4": 20, "B5": 40, "B6": 45, "B7": 40, "B8": 45,
          "B9": 65, "B10": 60, "B11": 75}
FRONT = [("B11", -64.4), ("B4", -22.0), ("B10", 11.3), ("B1", 38.0), ("B9", 68.5)]
BACK = [("B8", -72.5), ("B2", -44.5), ("B5", -17.8), ("B3", 11.4), ("B7", 39.3), ("B6", 73.5)]
Y_FRONT, Y_BACK = -57.3, -2.7                 # seat lines (mm)
W, H, T = 176.0, 152.0, 10.0
SF_Y, SB_Y = -66.0, 6.0                       # shelf front / back edge
RIB_Y = (-33.0, -27.0)
DOWN = 16.0
RAIL_W = 3.5
PF, PT = 58.0, 8.0
RAIL_Z = (130.0, 142.0)
AX = (72.0, 152.0)                            # shelf hinge pin
HINGE = (62.0, 19.0)                          # panel hinge axis (y, z)
STAY_P, STAY_Q = (14.0, 9.0), (62.0, 85.0)
STAY_SEC = (4.0, 8.0)                         # thickness (x), width
PRIB_N, PRIB_W, PRIB_D = 6, 5.0, 5.0          # panel back ribs
WIN = (80.0, 95.0, 121.0)                     # window width, z bottom, z top
PANEL_W = 160.0
E_ST, E_CR = 3000.0, 1000.0
ALLOW = {"sus_along": 7.0, "sus_across": 4.0, "des_along": 18.0, "des_across": 10.0, "steel": 300.0}
F_BRUSH = 2.0
PUSH = 4.0                                    # N horizontal, clipping a heavy brush
HAND = 10.0 * 1.5                             # N down on the front edge centre

rows = []


def check(name, value, limit, unit, note=""):
    ok = value <= limit
    rows.append(dict(item=name, value=round(value, 3), limit=limit, unit=unit, ok=ok,
                     margin=round(limit / value, 1) if value > 0 else None, note=note))
    return value


def rect_I(b, h):
    return b * h ** 3 / 12


def composite(parts):
    """parts: [(b, h, z_centroid)] -> (A, z_bar, I about z_bar, c_top, c_bot)."""
    A = sum(b * h for b, h, _ in parts)
    zb = sum(b * h * z for b, h, z in parts) / A
    I = sum(rect_I(b, h) + b * h * (z - zb) ** 2 for b, h, z in parts)
    top = max(z + h / 2 for b, h, z in parts)
    bot = min(z - h / 2 for b, h, z in parts)
    return A, zb, I, top - zb, zb - bot


# ------------------------------------------------------------------ loads
brushes = [(n, x, Y_FRONT, LOAD_G[n] * G) for n, x in FRONT] + [(n, x, Y_BACK, LOAD_G[n] * G) for n, x in BACK]
P_sus = sum(p for *_, p in brushes)
y_bar = sum(p * y for _n, _x, y, p in brushes) / P_sus
shelf_self = 45 * G                           # shelf + cartridges (g)


def case(kind):
    k = 1.0 if kind == "sus" else F_BRUSH
    pts = [(x, y, p * k) for _n, x, y, p in brushes]
    if kind == "des":
        pts.append((0.0, SF_Y, HAND))
    pts.append((0.0, -26.0, shelf_self))
    return pts


out = {"brush_total_g": sum(LOAD_G.values()), "brush_total_N": round(P_sus, 2), "y_bar": round(y_bar, 1)}

# ------------------------------------------------------------------ 1 shelf front strip (pockets) -> rib
# Front-row loads ride on the cartridges' ledges, then the plate between pockets carries them
# back to the rib: cantilever from the rib face (y -31) to the seat line, only the solid plate
# between pockets (width = shelf width - sum of pocket widths) counted.
pocket_w = [30.5, 23.3, 26.1, 21.9, 32.7]
b_web = W - sum(pocket_w) - 2 * 1.0
I_front = rect_I(b_web, T)
L_front = RIB_Y[0] - Y_FRONT
res = {}
for kind, E in (("sus", E_CR), ("des", E_ST)):
    P = sum(p for x, y, p in case(kind) if abs(y - Y_FRONT) < 1 or y == SF_Y)
    M = P * L_front
    res[kind] = dict(P=P, M=M, sigma=M * (T / 2) / I_front, defl=P * L_front ** 3 / (3 * E * I_front))
check("Shelf plate, front row to rib: stress (sustained)", res["sus"]["sigma"], ALLOW["sus_along"], "MPa")
check("Shelf plate, front row to rib: stress (design)", res["des"]["sigma"], ALLOW["des_along"], "MPa")
out["front_strip"] = res

# ------------------------------------------------------------------ 2 cross rib (T: plate web + downstand)
web = (2.4, T, H - T / 2)                   # only the 2.4 mm web between pockets is solid in the plate
dst = (RIB_Y[1] - RIB_Y[0], DOWN, H - T - DOWN / 2)
A, zb, I_rib, ct, cb = composite([web, dst])
span = W - RAIL_W
res = {}
for kind, E in (("sus", E_CR), ("des", E_ST)):
    pts = case(kind)
    # every brush load goes onto the rib (conservative: back-row share really goes to the cheeks)
    R = sum(p for x, y, p in pts) / 2
    # simply supported span, point loads at x (worst bending at mid, deflection by superposition)
    a0 = -span / 2
    Mmax, dmax = 0.0, 0.0
    for xs in [a0 + span * i / 200 for i in range(201)]:
        M = sum(p * ((xs - a0) * (span - (x - a0)) / span if xs <= x else (x - a0) * (span - (xs - a0)) / span)
                for x, y, p in pts)
        Mmax = max(Mmax, M)
        d = 0.0
        for x, y, p in pts:
            a, b = x - a0, span - (x - a0)
            xx = xs - a0
            if xx <= a:
                d += p * b * xx * (span ** 2 - b ** 2 - xx ** 2) / (6 * E * I_rib * span)
            else:
                d += p * a * (span - xx) * (span ** 2 - a ** 2 - (span - xx) ** 2) / (6 * E * I_rib * span)
        dmax = max(dmax, d)
    res[kind] = dict(R_each=R, M=Mmax, sigma=Mmax * cb / I_rib, defl=dmax)
check("Cross rib bending (sustained)", res["sus"]["sigma"], ALLOW["sus_along"], "MPa")
check("Cross rib bending (design)", res["des"]["sigma"], ALLOW["des_along"], "MPa")
out["rib"] = dict(I=round(I_rib), **{k: {kk: round(vv, 4) for kk, vv in v.items()} for k, v in res.items()})

# ------------------------------------------------------------------ 3 side rails + cheeks (cantilevers from the stop)
cheek = (7.0, T, H - T / 2)
rail = (RAIL_W, DOWN, H - T - DOWN / 2)
A, zb, I_ch, ct, cb = composite([cheek, rail])
L_ch = PF - sum(RIB_Y) / 2                    # stop edge (front of the rail top, y 60) to the rib
L_ext = sum(RIB_Y) / 2 - SF_Y                 # rib to the shelf front edge
res = {}
for kind, E in (("sus", E_CR), ("des", E_ST)):
    P = sum(p for x, y, p in case(kind)) / 2
    M = P * L_ch
    th = P * L_ch ** 2 / (2 * E * I_ch)
    res[kind] = dict(P_each=P, M=M, sigma=M * max(ct, cb) / I_ch, defl=P * L_ch ** 3 / (3 * E * I_ch), theta=th)
check("Side rail + cheek bending, at the rib end (sustained)", res["sus"]["sigma"], ALLOW["sus_along"], "MPa")
check("Side rail + cheek bending, at the rib end (design)", res["des"]["sigma"], ALLOW["des_along"], "MPa")
# at the stop edge (y 58) the downstand has tapered out: only the cheek, widened to 11 x 10, carries it
I_stop = rect_I(11.0, T)
for kind in ("sus", "des"):
    M = res[kind]["P_each"] * L_ch
    res[kind]["sigma_stop"] = M * (T / 2) / I_stop
check("Cheek at the stop edge, cheek only 11 x 10 (sustained)", res["sus"]["sigma_stop"], ALLOW["sus_along"], "MPa")
check("Cheek at the stop edge, cheek only 11 x 10 (design)", res["des"]["sigma_stop"], ALLOW["des_along"], "MPa",
      "downstand tapers into the cheek over 10 mm")
out["cheek"] = dict(I=round(I_ch), **{k: {kk: round(vv, 5) for kk, vv in v.items()} for k, v in res.items()})

# ------------------------------------------------------------------ 4 hinge stop and pin
# The cheek pivots on the front edge of the rail top (y 60); the pin at y 72 holds the tail down.
lever_pin = AX[0] - PF
res = {}
for kind in ("sus", "des"):
    pts = case(kind)
    Mstop = sum(p * (PF - y) for x, y, p in pts)            # about the stop edge
    Fpin = Mstop / lever_pin                                  # total, both pins (upward on the ear)
    Fstop = Fpin + sum(p for *_, p in pts)                    # total contact force on the rail
    res[kind] = dict(Mstop=Mstop, Fpin_each=Fpin / 2, Fstop_each=Fstop / 2)
d_pin = 3.0
tau = res["des"]["Fpin_each"] / (math.pi * d_pin ** 2 / 4)
check("Shelf hinge dowel shear (design)", tau, ALLOW["steel"] / 2, "MPa")
check("Shelf hinge: dowel bearing on cheek knuckle (design)", res["des"]["Fpin_each"] / (d_pin * 7.0),
      ALLOW["des_along"], "MPa")
ear_b, ear_L = 7.0, AX[0] - (PF + 3.0)        # ear base 7 wide, runs y 61..72 on the rail top
ecc = AX[0] - (PF + 3.0 + ear_L / 2)           # pin sits at the back end of the base
ear = lambda F: F / (ear_b * ear_L) + 6 * F * ecc / (ear_b * ear_L ** 2)  # noqa: E731
check("Shelf hinge: ear pulled up across layers, with offset (sustained)", ear(res["sus"]["Fpin_each"]),
      ALLOW["sus_across"], "MPa", "ear base 7 x 11 mm, pin at its back end")
check("Shelf hinge: ear pulled up across layers, with offset (design)", ear(res["des"]["Fpin_each"]),
      ALLOW["des_across"], "MPa")
check("Cheek bearing on the rail top (design)", res["des"]["Fstop_each"] / (6.2 * 1.5), ALLOW["des_along"], "MPa",
      "real flat contact after bevels: x 77.8-84, y 59-60.5")
out["hinge"] = {k: {kk: round(vv, 2) for kk, vv in v.items()} for k, v in res.items()}

# ------------------------------------------------------------------ 5 panel above the stay peg
# Moment entering the panel at the rail from the shelf, carried down to the stay peg (z 85).
pz = PF + PT / 2
full = composite([(PANEL_W, PT, pz)] + [(PRIB_W, PRIB_D, PF + PT + PRIB_D / 2)] * PRIB_N)
winsec = composite([(PANEL_W - WIN[0], PT, pz)] + [(PRIB_W, PRIB_D, PF + PT + PRIB_D / 2)] * PRIB_N)
I_full, I_win = full[2], winsec[2]
c_full, c_win = max(full[3], full[4]), max(winsec[3], winsec[4])
res = {}
for kind, E in (("sus", E_CR), ("des", E_ST)):
    pts = case(kind)
    Mtop = sum(p * (pz - y) for x, y, p in pts)
    Hk = PUSH if kind == "des" else 0.0
    M_win = Mtop + Hk * (RAIL_Z[1] - WIN[1])
    M_peg = Mtop + Hk * (RAIL_Z[1] - STAY_Q[1])
    # rotation of the rail relative to the peg: integrate M/EI over the three zones
    zones = [(STAY_Q[1], WIN[1], I_full), (WIN[1], WIN[2], I_win), (WIN[2], RAIL_Z[0], I_full)]
    theta = sum(Mtop * (z1 - z0) / (E * I) for z0, z1, I in zones)
    res[kind] = dict(Mtop=Mtop, sigma_win=M_win * c_win / I_win, sigma_peg=M_peg * c_full / I_full, theta=theta)
check("Panel at the window, across layers (sustained)", res["sus"]["sigma_win"], ALLOW["sus_across"], "MPa")
check("Panel at the window, across layers (design)", res["des"]["sigma_win"], ALLOW["des_across"], "MPa")
check("Panel at the stay peg, across layers (design)", res["des"]["sigma_peg"], ALLOW["des_across"], "MPa")
out["panel"] = dict(I_full=round(I_full), I_win=round(I_win),
                    **{k: {kk: round(vv, 5) for kk, vv in v.items()} for k, v in res.items()})

# ------------------------------------------------------------------ 6 stays, pegs, pivots, bottom hinge
u = (STAY_Q[0] - STAY_P[0], STAY_Q[1] - STAY_P[1])
Ls = math.hypot(*u)
u = (u[0] / Ls, u[1] / Ls)
r = (STAY_Q[0] - HINGE[0], STAY_Q[1] - HINGE[1])
arm = abs(r[0] * u[1] - r[1] * u[0])          # stay force's lever about the panel hinge
res = {}
for kind in ("sus", "des"):
    pts = case(kind)
    M_h = sum(p * (HINGE[0] - y) for x, y, p in pts) + (PUSH if kind == "des" else 0) * (H - 5 - HINGE[1])
    Fst = M_h / arm / 2                        # per stay, compression
    res[kind] = dict(M_hinge=M_h, F_stay=Fst)
I_st = STAY_SEC[1] * STAY_SEC[0] ** 3 / 12
Pcr = math.pi ** 2 * E_ST * I_st / Ls ** 2
check("Stay buckling (design force vs Euler load)", res["des"]["F_stay"], Pcr, "N", "want 3x or more")
peg_lever = 2.6 + 0.6                          # load centre on the stay, from the panel side face
Zd = math.pi * 3.0 ** 3 / 32
check("Panel peg (3 mm steel dowel) bending (design)", res["des"]["F_stay"] * peg_lever / Zd, ALLOW["steel"], "MPa")
check("Peg bore in the panel side, 8 mm deep (design)",
      res["des"]["F_stay"] * (1 + 2 * peg_lever / 8.0) / (3.0 * 8.0), ALLOW["des_along"], "MPa",
      "bearing incl. the prying couple; bore lies along the layers")
check("Stay pivot dowel, double shear clevis (design)", res["des"]["F_stay"] / 2 / (math.pi * 9 / 4), ALLOW["steel"] / 2,
      "MPa", "dowel spans clevis tab - stay - wall boss")
check("Stay pivot: bearing in clevis tab 3.3 mm (design)", res["des"]["F_stay"] / 2 / (3.0 * 3.3), ALLOW["des_along"], "MPa")
check("Stay pivot: bearing in wall boss 2.1 mm (design)", res["des"]["F_stay"] / 2 / (3.0 * 2.1), ALLOW["des_along"], "MPa")
check("Stay bore bearing, 4 mm stay (sustained)", res["sus"]["F_stay"] / (3.0 * 4.0), ALLOW["sus_along"], "MPa",
      "running fit; creep here would let the stand lean")
# bottom hinge: vertical load + stay horizontal reaction, two knuckles
for kind in ("des",):
    V = sum(p for *_, p in case(kind))
    Hh = 2 * res[kind]["F_stay"] * u[0]
    Fk = math.hypot(V, Hh) / 2
    check("Panel hinge dowel shear (design)", Fk / (math.pi * 9 / 4), ALLOW["steel"] / 2, "MPa")
    check("Panel knuckle bearing, 14 mm long (design)", Fk / (3.0 * 14.0), ALLOW["des_along"], "MPa")
    check("Tray tower bearing, 10 mm long (design)", Fk / (3.0 * 10.0), ALLOW["des_along"], "MPa")
out["stays"] = dict(length=round(Ls, 1), arm=round(arm, 1), Euler_N=round(Pcr),
                    **{k: {kk: round(vv, 2) for kk, vv in v.items()} for k, v in res.items()})

# ------------------------------------------------------------------ 7 cartridge ledge
w_max = max(LOAD_G.values()) * G * F_BRUSH
check("Cartridge on its 1 mm ledge: shear (design)", w_max / (90 * 1.0), ALLOW["des_along"], "MPa",
      "ledge runs ~90 mm round each pocket")

# ------------------------------------------------------------------ 8 sag of the shelf front edge
sag = {}
L_low = STAY_Q[1] - HINGE[1]
I_low = I_full                                  # ribs start at z 30; close enough over 85-19
for label, kind, E in (("as hung (instant)", "sus", E_ST), ("after months, 22 C (creep)", "sus", E_CR),
                       ("after months, warm bathroom 30 C", "sus", 700.0), ("design overload (short-term)", "des", E_ST)):
    f = E_CR / E if kind == "sus" else 1.0     # results above were for E_CR (sus) / E_ST (des)
    d_ch = (out["cheek"][kind]["defl"] + out["cheek"][kind]["theta"] * L_ext) * f
    th_up = out["panel"][kind]["theta"] * f
    th_low = out["panel"][kind]["Mtop"] * L_low / (3 * E * I_low)    # panel span hinge -> peg
    d_pan = (th_up + th_low) * (pz - SF_Y)
    d_rib = out["rib"][kind]["defl"] * f
    d_fr = out["front_strip"][kind]["defl"] * f
    sag[label] = dict(cheeks=round(d_ch, 3), panel=round(d_pan, 3), rib=round(d_rib, 3), front=round(d_fr, 3),
                      total=round(d_ch + d_pan + d_rib + d_fr, 3))
check("Front edge sag as she hangs the brushes", sag["as hung (instant)"]["total"], 0.3, "mm")
check("Front edge sag after months of use (creep)", sag["after months, 22 C (creep)"]["total"], 1.0, "mm",
      "1 mm over the 136 mm shelf is 0.4 deg: not visible")
check("Front edge sag after months, warm bathroom", sag["after months, warm bathroom 30 C"]["total"], 1.0, "mm")
check("Front edge sag, design overload", sag["design overload (short-term)"]["total"], 1.5, "mm")
out["sag"] = sag
# Fixed offsets from pin clearances. The shelf's own weight already pushes every joint the same
# way, so these set where the shelf rests empty; they do not change as brushes go on.
cl_shelf = (3.05 - 3.0) / 2 * 2               # diametral clearance at the cheek bore (reamed 3 mm)
cl_hook = 3.1 - 3.0
tilt_shelf = cl_shelf / (AX[0] - PF)           # tail lifts by the clearance over the stop lever
tilt_panel = cl_hook / (STAY_Q[1] - HINGE[1])
out["rest_offset_mm"] = round(tilt_shelf * (AX[0] - SF_Y) + tilt_panel * (PF + PT / 2 - SF_Y), 2)

# ------------------------------------------------------------------ 9 duty cycle: sag and grip over the years
# Chelsea's use: unfold, hang wet brushes for 24 h, take them off, fold, store unloaded 2-3 weeks.
# Creep law (Findley power law), per unit of the instant sag:  J(t)/J0 = 1 + (t / tau) ** n,  t in hours.
# Two calibrations bracket printed PLA at room temperature:
#   typical       J(24 h) = 1.3, J(3 months) = 2.0
#   conservative  J(24 h) = 1.5, J(3 months) = 3.0   (matches the E_creep = 1 GPa used above)
# Steam: one hot shower during each dry, 1 h at ~30 C running creep ~4x faster -> 27 h effective per dry.
# Stresses are tiny (frame under 1.2 MPa, <3 % of strength), so creep is linear in load.
# Two bounds:
#   REALISTIC   linear viscoelastic (Boltzmann superposition): each dry's creep recovers while stored.
#   WORST CASE  nothing ever recovers: creep runs on the total loaded time, as if one long load
#               (a strict upper bound for creep that only grows with time under load).
EFF = 27.0


def calib(j24, j3m):
    n = math.log((j3m - 1) / (j24 - 1)) / math.log(2160 / 24)
    tau = 24 / (j24 - 1) ** (1 / n)
    return n, tau


def Jf(t, n, tau):
    return 0.0 if t < 0 else 1 + (t / tau) ** n


def duty(n, tau, period_h, years=10, load_h=24.0):
    cycles = int(years * 8760 / period_h)
    ons = [k * period_h for k in range(cycles)]
    real_peak, real_rest, worst_peak = [], [], []
    for N, t0 in enumerate(ons):
        te = t0 + load_h
        tail_e = sum(Jf(te - a, n, tau) - Jf(te - a - load_h, n, tau) for a in ons[:N])
        tail_s = sum(Jf(t0 - a, n, tau) - Jf(t0 - a - load_h, n, tau) for a in ons[:N])
        real_peak.append(Jf(EFF, n, tau) + tail_e)
        real_rest.append(tail_s)
        worst_peak.append(Jf(EFF * (N + 1), n, tau))
    return ons, real_peak, real_rest, worst_peak


d0 = sag["as hung (instant)"]["total"]
duty_out = {"d0_mm": d0, "cases": {}}
for cname, (j24, j3m) in {"typical": (1.3, 2.0), "conservative": (1.5, 3.0)}.items():
    n, tau = calib(j24, j3m)
    c = {"n": round(n, 3), "tau_h": round(tau, 1)}
    for pname, days in (("every 2 weeks", 14), ("every 3 weeks", 21)):
        ons, rp, rr, wp = duty(n, tau, days * 24)
        yrs = [t / 8760 for t in ons]
        c[pname] = dict(years=[round(y, 3) for y in yrs], real_peak=[round(d0 * v, 4) for v in rp],
                        real_rest=[round(d0 * v, 4) for v in rr], worst_peak=[round(d0 * v, 4) for v in wp])
        idx = {y: min(range(len(yrs)), key=lambda i: abs(yrs[i] - y)) for y in (1, 3, 5, 10)}
        c[pname]["summary"] = {f"{y} y": dict(real_in_use=round(d0 * rp[i], 3), real_resting=round(d0 * rr[i], 3),
                                              worst_in_use=round(d0 * wp[i], 3)) for y, i in idx.items()}
    c["continuous"] = {f"{y} y": round(d0 * Jf(y * 8760, n, tau), 3) for y in (0.25, 1, 3, 5, 10)}
    c["forgot_one_week_mm"] = round(d0 * Jf(168, n, tau), 3)
    # clip fingers sit at a fixed 1.8 mm deflection: grip relaxes as 1/J. Realistic: it recovers between
    # dries. Worst case: no recovery, grip left = 1/J(total loaded time). A brush loses ~30 % of its
    # wet weight as it dries, so the end-of-dry requirement is 0.7x.
    ons, *_ = duty(n, tau, 14 * 24)
    cum = EFF * len(ons)
    g = {}
    for label, start, end in (("new", 1.0, 1 / Jf(EFF, n, tau)),
                              ("after 1 y, worst", 1 / Jf(EFF * 26, n, tau), 1 / Jf(EFF * 27, n, tau)),
                              ("after 10 y, worst", 1 / Jf(cum, n, tau), 1 / Jf(cum + EFF, n, tau))):
        g[label] = dict(grip_start=round(start, 3), grip_end=round(end, 3),
                        sf_start_wet=round(2.0 * start, 2), sf_end_dry=round(2.0 * end / 0.7, 2))
    c["grip"] = g
    duty_out["cases"][cname] = c
out["duty"] = duty_out
cons = duty_out["cases"]["conservative"]["every 2 weeks"]["summary"]["10 y"]
check("Duty cycle 10 y, realistic (conservative creep), in use", cons["real_in_use"], 0.5, "mm",
      "24 h loaded every 2 weeks, recovery while stored")
check("Duty cycle 10 y, no-recovery estimate (conservative creep), in use", cons["worst_in_use"], 1.0, "mm",
      "strain-hardening rule: as if all 260 dries were one 9-month load")
# provable bound (linear viscoelastic): any history with load <= the brushes is bounded by holding them
# continuously for the same span
for cn, c in duty_out["cases"].items():
    c["hard_bound_10y"] = c["continuous"]["10 y"]
check("Duty cycle 10 y, hard bound = brushes left on 10 years (typical creep)",
      duty_out["cases"]["typical"]["hard_bound_10y"], 1.0, "mm")
check("Duty cycle 10 y, hard bound = brushes left on 10 years (conservative creep)",
      duty_out["cases"]["conservative"]["hard_bound_10y"], 1.5, "mm", "0.54 deg over the shelf")
# steam sensitivity: a hotter, longer shower (10x for 1.5 h) on every dry
n_c, tau_c = duty_out["cases"]["conservative"]["n"], duty_out["cases"]["conservative"]["tau_h"]
duty_out["steam_10x_peak_mm"] = round(d0 * Jf(24 + 9 * 1.5, n_c, tau_c), 3)
duty_out["steam_4x_peak_mm"] = round(d0 * Jf(EFF, n_c, tau_c), 3)

out["checks"] = rows

if __name__ == "__main__":
    print(f"Brushes: {out['brush_total_g']} g upper-bound wet ({out['brush_total_N']} N), centroid y {out['y_bar']}")
    w = max(len(r_["item"]) for r_ in rows)
    for r_ in rows:
        flag = "ok " if r_["ok"] else "FAIL"
        print(f"{flag} {r_['item']:<{w}}  {r_['value']:>8.3f} / {r_['limit']:<6} {r_['unit']:<4} "
              f"x{r_['margin']}  {r_['note']}")
    for k, v in sag.items():
        print("sag", k, v)
    for cname, c in out["duty"]["cases"].items():
        print("duty", cname, "n", c["n"], "tau_h", c["tau_h"])
        for pname in ("every 2 weeks", "every 3 weeks"):
            print("   ", pname, c[pname]["summary"])
        print("    continuous", c["continuous"], "forgot a week", c["forgot_one_week_mm"])
        print("    grip", c["grip"])
    print("fixed rest offset of the front edge from pin clearances:", out["rest_offset_mm"], "mm (set once, not load-dependent)")
    os.makedirs(os.path.join(HERE, "renders", "v2"), exist_ok=True)
    json.dump(out, open(os.path.join(HERE, "renders", "v2", "structure.json"), "w"), indent=1)
