"""Print-readiness checks for home-devices parts (plain Python, no Blender needed).

  python printcheck.py mesh  part.3mf|part.stl      mesh health per object
  python printcheck.py slice part.3mf [--out DIR] [--process NAME] [--filament NAME]
                                                    [--machine NAME] [--set k=v ...]
                                                    slice for the A1 Mini with Bambu Studio's CLI
                                                    and print time, filament and per-object extents
  python printcheck.py paths sliced.gcode            dump extrusion paths to paths.json for
                                                    per-layer checks of thin features

mesh: counts non-manifold edges and finds folded or overlapping triangles on every flat
level (signed vs unsigned area). A hand-written fan triangulation of concave faces shows up
here; slicers often hide it, but Bambu Studio draws it as triangle fans.
slice: the filament defaults to the one synced from the owner's printer in Bambu Studio
(--filament NAME to override); 0.4 mm nozzle, Textured PEI Plate, 0.20 mm Standard @BBL A1M; pass process
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
FILAMENT = None                   # None: whatever filament the owner's printer has synced to
                                  # Bambu Studio (see synced()); never assume PLA Basic
CONF = os.path.join(os.environ.get("APPDATA", ""), "BambuStudio", "BambuStudio.conf")
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
def _conf():
    t = open(CONF, encoding="utf-8").read()
    return json.loads(t[:t.rfind("}") + 1])       # the file ends with an MD5 comment line


def synced():
    """The filament(s) Bambu Studio has synced from the owner's printer: [(preset, colour)].
    Read from BambuStudio.conf (presets/filaments + filament_colors, which Studio fills from
    the printer's spool on sync), cross-checked against the printer's reported filament id.
    Reads only preset names and colours, nothing from the account."""
    c = _conf()
    pre = c.get("presets", {})
    names = pre.get("filaments") or []
    names = names if isinstance(names, list) else [names]
    cols = str(pre.get("filament_colors", "")).split(";")
    ids = set((c.get("ams_filament_ids") or {}).values())
    out = []
    for i, n in enumerate(names):
        fid = resolve("filament", n).get("filament_id")
        fid = fid[0] if isinstance(fid, list) else fid
        if ids and fid not in ids:
            print(f"warning: Studio's filament {n!r} ({fid}) is not what the printer last "
                  f"reported ({', '.join(sorted(ids))}); sync the printer in Studio")
        out.append((n, cols[i] if i < len(cols) else "?"))
    if not out:
        raise SystemExit("no synced filament in Bambu Studio; sync the printer there first")
    return out


def _presets(kind):
    """System presets, plus the owner's own (user/<id>/<kind>), by name."""
    folders = [os.path.join(PROFILES, kind)]
    try:
        uf = _conf().get("app", {}).get("preset_folder")
        if uf:
            folders.append(os.path.join(os.path.dirname(CONF), "user", uf, kind))
    except (OSError, ValueError):
        pass
    by_name = {}
    for folder in folders:
        if not os.path.isdir(folder):
            continue
        for f in os.listdir(folder):
            if f.endswith(".json"):
                try:
                    d = json.load(open(os.path.join(folder, f), encoding="utf-8"))
                except ValueError:
                    continue
                if "name" in d:
                    by_name[d["name"]] = d
    return by_name


def resolve(kind, name):
    """A system preset with its whole 'inherits' chain merged in (child wins).
    The CLI does NOT do this reliably: given 'Bambu PLA Basic @BBL A1M' it sliced at 200 C,
    2 mm3/s and 500 mm/s2 (generic fallbacks) instead of 220 C, 21 mm3/s, 6000 mm/s2."""
    by_name = _presets(kind)
    chain, n = [], name
    while n:
        if n not in by_name:
            raise SystemExit(f"{kind} preset {n!r} not found")
        chain.append(by_name[n])
        n = by_name[n].get("inherits")
    merged = {}
    for d in reversed(chain):
        merged.update(d)
    merged.pop("inherits", None)
    merged["name"] = name
    merged["from"] = "system"
    merged["instantiation"] = "true"
    return merged


def _diff(a, b):
    """Keys whose values differ between two resolved presets (Studio's 'modified' list)."""
    skip = {"name", "from", "instantiation", "inherits", "setting_id", "base_id", "filament_id",
            "print_settings_id", "printer_settings_id", "compatible_printers", "version",
            "is_custom_defined", "type", "updated_time", "user_id", "sync_info"}
    return sorted(k for k in set(a) | set(b) if k not in skip and a.get(k) != b.get(k))


def keep_preset_names(gcode3mf, process, proc, machine_name, filament):
    """Rewrite the sliced file's project settings so Bambu Studio sees the real presets
    ('0.08mm Extra Fine @BBL A1M' + modified keys), not an unknown 'printcheck' preset.
    Without this Studio opened the file showing the wrong settings (2026-11-19)."""
    sys_proc = resolve("process", process)
    m = _presets("machine")[machine_name]
    m_parent = m.get("inherits") if m.get("from", "").lower() == "user" else None
    m_diff = _diff(resolve("machine", machine_name), resolve("machine", m_parent)) if m_parent else []
    tmp = gcode3mf + ".tmp"
    with zipfile.ZipFile(gcode3mf) as zi, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zo:
        for it in zi.infolist():
            data = zi.read(it.filename)
            if it.filename == "Metadata/project_settings.config":
                c = json.loads(data)
                c["print_settings_id"] = process
                c["printer_settings_id"] = machine_name
                c["filament_settings_id"] = [filament]
                c["different_settings_to_system"] = [";".join(_diff(proc, sys_proc)), "",
                                                     ";".join(m_diff)]
                c["inherits_group"] = ["", "", m_parent or ""]
                c["from"], c["name"] = "project", "project_settings"
                data = json.dumps(c, indent=4).encode("utf-8")
            zo.writestr(it, data)
    os.replace(tmp, gcode3mf)


def slice_part(path, out=None, sets=(), process=PROCESS, filament=FILAMENT, machine_name=MACHINE):
    out = out or tempfile.mkdtemp(prefix="slice_")
    os.makedirs(out, exist_ok=True)
    print(f"printer: {machine_name}, process: {process}")
    machine = resolve("machine", machine_name)
    proc = resolve("process", process)
    if filament is None:
        filament, colour = synced()[0]
        print(f"filament: {filament} {colour} (synced from the printer)")
    else:
        print(f"filament: {filament} (given with --filament)")
    fil = resolve("filament", filament)
    proc.update({"name": process, "print_settings_id": process,
                 "compatible_printers": sorted({MACHINE, machine_name}), "curr_bed_type": BED})
    for s in sets:
        k, v = s.split("=", 1)
        proc[k] = v
    files = {}
    for key, d in (("machine", machine), ("process", proc), ("filament", fil)):
        files[key] = os.path.join(out, key + ".json")
        json.dump(d, open(files[key], "w", encoding="utf-8"), indent=1)
    cmd = [BAMBU, "--arrange", "1", "--orient", "0",
           "--load-settings", f"{files['machine']};{files['process']}",
           "--load-filaments", files["filament"],
           "--slice", "0", "--export-3mf", "sliced.gcode.3mf", "--outputdir", out,
           os.path.abspath(path)]
    subprocess.run(cmd, cwd=out, capture_output=True)
    res = json.load(open(os.path.join(out, "result.json")))
    print("slicer:", res.get("error_string"))
    if os.path.exists(os.path.join(out, "sliced.gcode.3mf")):
        keep_preset_names(os.path.join(out, "sliced.gcode.3mf"), process, proc, machine_name,
                          filament)
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
        dens = fil.get("filament_density", ["1.26"])
        dens = float(dens[0] if isinstance(dens, list) else dens)
        print(f"filament weight ~{vol / 1000 * dens:.1f} g (density {dens} g/cm3)")
        for p in res.get("sliced_plates", []):
            for o in p.get("objects", []):
                b = o["bbox"]
                print(f"  {o['name']}: {b['width']:.1f} x {b['depth']:.1f} x {b['height']:.1f} mm")
    print("output:", out)
    return out


# ------------------------------------------------------------------ paths
def _arc(x0, y0, x1, y1, i, j, cw, step=0.5):
    """Points along a G2/G3 arc (centre at x0+i, y0+j), excluding the start."""
    cx, cy = x0 + i, y0 + j
    r = math.hypot(i, j)
    a0, a1 = math.atan2(y0 - cy, x0 - cx), math.atan2(y1 - cy, x1 - cx)
    sweep = a1 - a0
    if cw and sweep >= 0:
        sweep -= 2 * math.pi
    if not cw and sweep <= 0:
        sweep += 2 * math.pi
    n = max(1, int(abs(sweep) * r / step))
    pts = [(cx + r * math.cos(a0 + sweep * k / n), cy + r * math.sin(a0 + sweep * k / n))
           for k in range(1, n)]
    return pts + [(x1, y1)]


def dump_paths(gcode):
    """Extrusion segments per object: [z, x0, y0, x1, y1, feature] -> paths.json.
    Arcs (G2/G3) are split into short chords. G-code without M624 object markers (the CLI's
    single-object plates) goes under object "0"."""
    X = Y = Z = 0.0
    feat = None
    has_markers = any(l.startswith("M624") for l in open(gcode))
    obj = None if has_markers else "0"
    segs = defaultdict(list)
    for l in open(gcode):
        if l.startswith("; Z_HEIGHT:"):
            Z = float(l.split(":")[1])
        elif l.startswith("; FEATURE:"):
            feat = l[10:].strip()
        elif has_markers and l.startswith("M624"):
            obj = l.split()[1]
        elif has_markers and l.startswith("M625"):
            obj = None
        elif l.startswith(("G1 ", "G2 ", "G3 ")):
            d = {m[0]: float(m[1:]) for m in l.split(";")[0].split()[1:] if m[0] in "XYZEIJ"}
            nx, ny = d.get("X", X), d.get("Y", Y)
            if d.get("E", 0) > 0 and obj and (nx, ny) != (X, Y):
                pts = ([(nx, ny)] if l[1] == "1" else
                       _arc(X, Y, nx, ny, d.get("I", 0), d.get("J", 0), l[1] == "2"))
                px, py = X, Y
                for qx, qy in pts:
                    segs[obj].append([Z, px, py, qx, qy, feat])
                    px, py = qx, qy
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
        proc = a[a.index("--process") + 1] if "--process" in a else PROCESS
        fil = a[a.index("--filament") + 1] if "--filament" in a else FILAMENT
        mach = a[a.index("--machine") + 1] if "--machine" in a else MACHINE
        slice_part(path, out, sets, proc, fil, mach)
    elif cmd == "paths":
        dump_paths(path)
    else:
        sys.exit(__doc__)
