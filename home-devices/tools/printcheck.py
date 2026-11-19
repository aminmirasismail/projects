"""Print-readiness checks for home-devices parts (plain Python, no Blender needed).

  python printcheck.py mesh  part.3mf|part.stl      mesh health per object
  python printcheck.py slice part.3mf [--out DIR] [--set key=value ...]
                                                    slice for the A1 Mini with Bambu Studio's CLI
                                                    and print time, filament and per-object extents
  python printcheck.py paths sliced.gcode            dump extrusion paths to paths.json for
                                                    per-layer checks of thin features

mesh: counts non-manifold edges and finds folded or overlapping triangles on every flat
level (signed vs unsigned area). A hand-written fan triangulation of concave faces shows up
here; slicers often hide it, but Bambu Studio draws it as triangle fans.
slice: defaults are 0.4 mm nozzle, Bambu PLA Basic, Textured PEI Plate, 0.20 mm Standard @BBL A1M; pass process
overrides with --set (e.g. --set wall_loops=3 --set sparse_infill_density=15%).
Slicing never prints anything; sending to the printer needs the owner's explicit yes.
"""
import json
import math
import os
import re
import struct
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter, defaultdict

BAMBU = r"C:\Program Files\Bambu Studio\bambu-studio.exe"
PROFILES = r"C:\Program Files\Bambu Studio\resources\profiles\BBL"
MACHINE = "Bambu Lab A1 mini 0.4 nozzle"
PROCESS = "0.20mm Standard @BBL A1M"
FILAMENT = "Bambu PLA Basic @BBL A1M"
BED = "Textured PEI Plate"        # the owner's A1 Mini plate; the CLI default is Cool Plate


# ------------------------------------------------------------------ mesh
def load(path):
    """Return [(name, verts, tris)] from a 3MF (one entry per object) or an STL."""
    if path.lower().endswith(".3mf"):
        z = zipfile.ZipFile(path)
        out = []
        for n in z.namelist():
            if not n.endswith(".model"):
                continue
            t = z.read(n).decode("utf-8")
            for o in re.split(r"<object ", t)[1:]:
                V = [tuple(map(float, m)) for m in
                     re.findall(r'<vertex x="([^"]+)" y="([^"]+)" z="([^"]+)"', o)]
                F = [tuple(map(int, m)) for m in
                     re.findall(r'<triangle v1="(\d+)" v2="(\d+)" v3="(\d+)"', o)]
                if F:
                    nm = re.search(r'name="([^"]*)"', o)
                    out.append((nm.group(1) if nm else n, V, F))
        return out
    data = open(path, "rb").read()
    V, F, idx = [], [], {}
    if data[:5] == b"solid" and b"facet" in data[:400]:
        pts = [tuple(map(float, m)) for m in re.findall(rb"vertex\s+(\S+)\s+(\S+)\s+(\S+)", data)]
    else:
        n = struct.unpack("<I", data[80:84])[0]
        pts = []
        for i in range(n):
            f = struct.unpack("<12f", data[84 + 50 * i: 84 + 50 * i + 48])
            pts += [f[3:6], f[6:9], f[9:12]]
    for i in range(0, len(pts), 3):
        tri = []
        for p in pts[i:i + 3]:
            k = tuple(round(c, 5) for c in p)
            if k not in idx:
                idx[k] = len(V)
                V.append(k)
            tri.append(idx[k])
        F.append(tuple(tri))
    return [(os.path.basename(path), V, F)]


def mesh_report(path):
    ok = True
    for name, V, F in load(path):
        edges = Counter()
        for a, b, c in F:
            for e in ((a, b), (b, c), (c, a)):
                edges[tuple(sorted(e))] += 1
        nonman = sum(1 for n in edges.values() if n != 2)
        vol, levels = 0.0, defaultdict(lambda: [0.0, 0.0])
        degenerate = 0
        for a, b, c in F:
            (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = V[a], V[b], V[c]
            vol += (x1 * (y2 * z3 - y3 * z2) - x2 * (y1 * z3 - y3 * z1) + x3 * (y1 * z2 - y2 * z1)) / 6
            cr = ((y2 - y1) * (z3 - z1) - (z2 - z1) * (y3 - y1),
                  (z2 - z1) * (x3 - x1) - (x2 - x1) * (z3 - z1),
                  (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1))
            if math.sqrt(sum(c * c for c in cr)) < 1e-9:
                degenerate += 1
            if abs(z1 - z2) < 1e-4 and abs(z1 - z3) < 1e-4:
                A = cr[2] / 2
                lv = levels[round(z1, 3)]
                lv[0] += A
                lv[1] += abs(A)
        # on a flat level, up- and down-facing faces may both be real (an overhang above a
        # floor); report the down-facing area so a reviewer can decide
        flat = {z: (round((u + s) / 2, 2), round((u - s) / 2, 2)) for z, (s, u) in levels.items()}
        xs = [v[0] for v in V]; ys = [v[1] for v in V]; zs = [v[2] for v in V]
        print(f"{name}: {len(F)} tris, size {max(xs)-min(xs):.2f} x {max(ys)-min(ys):.2f} x "
              f"{max(zs)-min(zs):.2f} mm, volume {vol:.0f} mm3, non-manifold edges {nonman}, "
              f"degenerate tris {degenerate}")
        for z in sorted(flat):
            up, down = flat[z]
            if up > 0.01 and down > 0.01:
                print(f"   z={z}: {up} mm2 facing up AND {down} mm2 facing down on the same level"
                      f" -> folded/overlapping faces, or a real overhang there; check it")
        if nonman or vol <= 0:
            ok = False
    return ok


# ------------------------------------------------------------------ slice
def slice_part(path, out=None, sets=()):
    out = out or tempfile.mkdtemp(prefix="slice_")
    os.makedirs(out, exist_ok=True)
    proc = {"type": "process", "name": "printcheck", "from": "User", "inherits": PROCESS,
            "compatible_printers": [MACHINE], "print_settings_id": "printcheck",
            "curr_bed_type": BED, "version": "2.0.0.0"}
    for s in sets:
        k, v = s.split("=", 1)
        proc[k] = v
    pj = os.path.join(out, "process.json")
    json.dump(proc, open(pj, "w"), indent=1)
    cmd = [BAMBU, "--arrange", "1", "--orient", "0",
           "--load-settings", f"{PROFILES}\\machine\\{MACHINE}.json;{pj}",
           "--load-filaments", f"{PROFILES}\\filament\\{FILAMENT}.json",
           "--slice", "0", "--export-3mf", "sliced.gcode.3mf", "--outputdir", out,
           os.path.abspath(path)]
    subprocess.run(cmd, cwd=out, capture_output=True)
    res = json.load(open(os.path.join(out, "result.json")))
    print("slicer:", res.get("error_string"))
    g = os.path.join(out, "plate_1.gcode")
    if os.path.exists(g):
        for l in open(g):
            if re.match(r"; (model printing time|total filament length|total filament volume|"
                        r"total layer number)", l):
                print(l.strip("; \n").replace("[cm^3]", "[mm^3]"))
            if l.startswith("; CONFIG_BLOCK_END"):
                break
        vol = next((float(l.split(":")[1]) for l in open(g)
                    if l.startswith("; total filament volume")), 0)
        print(f"filament weight ~{vol / 1000 * 1.26:.1f} g (PLA 1.26 g/cm3)")
        for p in res.get("sliced_plates", []):
            for o in p.get("objects", []):
                b = o["bbox"]
                print(f"  {o['name']}: {b['width']:.1f} x {b['depth']:.1f} x {b['height']:.1f} mm")
    print("output:", out)
    return out


# ------------------------------------------------------------------ paths
def dump_paths(gcode):
    """Extrusion segments per object: [z, x0, y0, x1, y1, feature] -> paths.json."""
    X = Y = Z = 0.0
    obj = feat = None
    segs = defaultdict(list)
    for l in open(gcode):
        if l.startswith("; Z_HEIGHT:"):
            Z = float(l.split(":")[1])
        elif l.startswith("; FEATURE:"):
            feat = l[10:].strip()
        elif l.startswith("M624"):
            obj = l.split()[1]
        elif l.startswith("M625"):
            obj = None
        elif l.startswith(("G1 ", "G2 ", "G3 ")):
            d = {m[0]: float(m[1:]) for m in l.split(";")[0].split()[1:] if m[0] in "XYZE"}
            nx, ny = d.get("X", X), d.get("Y", Y)
            if d.get("E", 0) > 0 and obj and (nx, ny) != (X, Y):
                segs[obj].append([Z, X, Y, nx, ny, feat])
            X, Y = nx, ny
    out = os.path.join(os.path.dirname(os.path.abspath(gcode)), "paths.json")
    json.dump(segs, open(out, "w"))
    for o, s in segs.items():
        xs = [p for q in s for p in (q[1], q[3])]; ys = [p for q in s for p in (q[2], q[4])]
        print(f"object {o}: x {min(xs):.1f}-{max(xs):.1f}  y {min(ys):.1f}-{max(ys):.1f}  "
              f"z max {max(q[0] for q in s):.2f}  {len(s)} segments")
    print("wrote", out)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd, path = sys.argv[1], sys.argv[2]
    if cmd == "mesh":
        sys.exit(0 if mesh_report(path) else 1)
    elif cmd == "slice":
        a = sys.argv[3:]
        out = a[a.index("--out") + 1] if "--out" in a else None
        sets = [a[i + 1] for i, x in enumerate(a) if x == "--set"]
        slice_part(path, out, sets)
    elif cmd == "paths":
        dump_paths(path)
    else:
        sys.exit(__doc__)
