"""Purge deflector for the Bambu A1 Mini: clips onto the nozzle wiper and turns purge that the
toolhead flicks sideways into a straight drop, onto the low end of the purge bin.

The mount and the hood's envelope follow a proven community design ("Poop deflector (A1,
A1 mini, AMS)", MakerWorld), measured from its STEP: a C-clip that wraps the two round ends
of the wiper's 34.4 x 16 mm oval, and a hood beside it - open on the side the purge comes
from, a roof with a 45-degree lip, and a floor ramp that ends in a 22 x 14 mm drop opening.
Staying inside that envelope keeps clear of printer parts we have not measured.

House style on top: one black part, 3 mm plan corners, the 1.2 mm top edge, the clip block
hollowed (it carried 9 cm3 of solid plastic), no logo.

Heat: the air there stays well under PLA's ~55 C softening point, but fresh purge lands on
the ramp at ~220 C and can weld to PLA. Print it in PETG if you have it (PLA does not stick
to PETG), or line the ramp with kapton or aluminium tape.

Coordinates (the reference's): X along the wiper's long axis, purge travels +Y into the
hood, Z up (the clip's top face is the hood's top face). Printed on its -Y face (flat), so the
clip's hooks and the 45-degree lip need no supports.

  uv run --no-project --python 3.13 --with bpy --with trimesh --with networkx --with lxml \
      python deflector.py [--renders] [--preview]
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import bpy  # noqa: E402
import bmesh  # noqa: E402
import studio as S  # noqa: E402

REV = "A"

# ---------------------------------------------------------------- reference geometry (mm)
# wiper oval the clip wraps (from the reference clip's cavity)
OVAL_X = (4.7, 39.1)        # 34.4 long
OVAL_Y = (0.0, 16.0)        # 16 deep, round ends r 8
CLIP_T = 2.4                # clip wall
MOUTH_X = (8.4, 35.4)       # hook tips leave this opening on +Y
CLIP_Z = (14.0, 28.0)       # clip height band
BACK_Y = -17.0              # rear face (print face)
# hood
HOOD_X = (39.5, 65.0)       # outer; walls 1.6
HOOD_WALL = 1.6
HOOD_Y1 = 14.0              # front of the hood (lip edge)
ROOF_T = 1.6
RAMP = ((-17.0, 7.4), (0.0, 1.6))   # (y, z) top of the floor ramp, high at the back
OUTLET_Y = (0.0, 14.0)      # open floor: purge drops through here
LIP = ((9.0, 28.0 - ROOF_T), (14.0, 21.4))   # 45-degree lip under the roof's front edge

CORNER = 3.0                # plan corners
EDGE = S.EDGE_R             # 1.2 top edge


def prism_yz(name, pts, x0, x1):
    """A prism from a (y, z) polygon, extruded along X from x0 to x1."""
    bm = bmesh.new()
    a = [bm.verts.new((x0, y, z)) for y, z in pts]
    b = [bm.verts.new((x1, y, z)) for y, z in pts]
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[j], a[i], b[i], b[j]))
    bmesh.ops.triangulate(bm, faces=bm.faces[:])         # concave caps: no ngons for EXACT
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return S._link(name, bm)


def round_top(ob, z, r):
    """Fillet the whole top outline in one pass, after every cut, so the clip and the hood
    share one continuous rounded edge (no half fillets meeting in a groove)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.5), verts=bm.verts, edges=bm.edges)
    edges = [e for e in bm.edges
             if all(abs(v.co.z - z) < 1e-4 for v in e.verts) and len(e.link_faces) == 2
             and sorted(abs(f.normal.z) for f in e.link_faces)[0] < 0.5
             and sorted(abs(f.normal.z) for f in e.link_faces)[1] > 0.99]
    bmesh.ops.bevel(bm, geom=edges, offset=r, segments=S.arc_segments(r), profile=0.5,
                    affect="EDGES", clamp_overlap=True)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return len(edges)


def build():
    S.reset()
    black = S.pla("black")
    cx = (OVAL_X[0] + OVAL_X[1]) / 2
    cy = (OVAL_Y[0] + OVAL_Y[1]) / 2
    ow, od = OVAL_X[1] - OVAL_X[0], OVAL_Y[1] - OVAL_Y[0]
    zc, hc = (CLIP_Z[0] + CLIP_Z[1]) / 2, CLIP_Z[1] - CLIP_Z[0]

    # clip: a block behind the wiper plus an oval collar around it
    x0 = OVAL_X[0] - CLIP_T
    # the block runs 5 mm into the hood so its corner hides inside (no notch at the joint)
    blk = S.rounded_box("clip", HOOD_X[0] + 5 - x0, cy - BACK_Y, hc, r=CORNER,
                        loc=((x0 + HOOD_X[0] + 5) / 2, (BACK_Y + cy) / 2, CLIP_Z[0]))
    # fill where the right hook meets the hood's front corner (else a 0.9 mm notch)
    fill = S.box("fill", 4.5, HOOD_Y1 - 4, hc,
                 loc=(HOOD_X[0] + 1.75, (4 + HOOD_Y1) / 2, zc))
    collar = S.rounded_box("collar", ow + 2 * CLIP_T, od + 2 * CLIP_T, hc, r=od / 2 + CLIP_T - 0.05,
                           loc=(cx, cy, CLIP_Z[0]))
    hood = S.rounded_box("Deflector", HOOD_X[1] - HOOD_X[0], HOOD_Y1 - BACK_Y, CLIP_Z[1],
                         r=CORNER,
                         loc=((HOOD_X[0] + HOOD_X[1]) / 2, (BACK_Y + HOOD_Y1) / 2, 0))
    for o in (blk, collar, hood):
        S.bake(o)
    S.union(hood, [blk, collar, fill])

    cutters = []
    # the wiper and the mouth between the hook tips
    cutters.append(S.rounded_box("oval", ow, od, 40, r=od / 2 - 0.05, loc=(cx, cy, 0)))
    cutters.append(S.box("mouth", MOUTH_X[1] - MOUTH_X[0], 20, 40,
                         loc=((MOUTH_X[0] + MOUTH_X[1]) / 2, OVAL_Y[1] + 2, 20)))
    # hook tips end where the reference's do (y 15.7): nothing new in front of the wiper
    cutters.append(S.box("tips", HOOD_X[0] - x0 + 2, 10, 40,
                         loc=((x0 + HOOD_X[0]) / 2, 15.7 + 5, 20)))
    # hollow the clip block from below (prints as a pocket in the -Y-down orientation)
    px0, px1 = x0 + 1.6, HOOD_X[0] - 0.2
    cutters.append(S.box("pocket", px1 - px0, (OVAL_Y[0] - 1.6) - (BACK_Y + 1.6), hc - 1.6 + 1,
                         loc=((px0 + px1) / 2, (BACK_Y + 1.6 + OVAL_Y[0] - 1.6) / 2,
                              CLIP_Z[0] - 1 + (hc - 1.6 + 1) / 2)))
    # the reference leaves the hood's inner wall off beside the wiper below the clip (the
    # wiper's own mount is there); do the same
    cutters.append(S.box("notch", HOOD_WALL + 1, OVAL_Y[1] + 1, CLIP_Z[0] + 1,
                         loc=(HOOD_X[0] + HOOD_WALL / 2 - 0.5, (OVAL_Y[1] + 1) / 2,
                              (CLIP_Z[0] - 1) / 2)))
    # hood channel: open at the back (purge comes in), roof with a 45-degree lip, floor ramp,
    # open floor at the front (the drop)
    (ry0, rz0), (ry1, rz1) = RAMP
    roof = CLIP_Z[1] - ROOF_T
    (ly0, lz0), (ly1, lz1) = LIP
    k = (rz1 - rz0) / (ry1 - ry0)
    chan = [(BACK_Y - 2, rz0 + k * -2), (ry1, rz1), (OUTLET_Y[0], -1), (HOOD_Y1 + 2, -1),
            (HOOD_Y1 + 2, lz1 - 2), (ly0, lz0), (BACK_Y - 2, roof)]
    cutters.append(prism_yz("channel", chan, HOOD_X[0] + HOOD_WALL, HOOD_X[1] - HOOD_WALL))
    for c in cutters:
        S.bake(c)
    v0 = S.volume(hood)
    S.cut(hood, cutters)
    assert S.volume(hood) < v0 - 1000, "channel cut removed too little"
    round_top(hood, CLIP_Z[1], EDGE)
    S.assign(hood, black)
    S.smooth(hood, 35)
    print(f"deflector: {S.dims(hood)} mm, {S.volume(hood) / 1000:.1f} cm3, "
          f"~{S.volume(hood) / 1000 * 1.24:.0f} g PLA")
    return hood


def write_3mf(ob, path):
    """Printed on its -Y face: rotate -Y to -Z (a +90 deg turn about X)."""
    import trimesh
    me = ob.data
    v = [(p.co.x, -p.co.z, p.co.y) for p in me.vertices]      # (x, y, z) -> (x, -z, y)
    z0 = min(p[2] for p in v)
    xs = [p[0] for p in v]
    ys = [p[1] for p in v]
    ox, oy = 90 - (min(xs) + max(xs)) / 2, 90 - (min(ys) + max(ys)) / 2
    v = [(x + ox, y + oy, z - z0) for x, y, z in v]
    me.calc_loop_triangles()
    f = [tuple(t.vertices) for t in me.loop_triangles]
    sc = trimesh.Scene()
    sc.add_geometry(trimesh.Trimesh(vertices=v, faces=f, process=True), node_name=ob.name,
                    geom_name=ob.name)
    sc.export(path, file_type="3mf")


def main():
    args = sys.argv[1:]
    ob = build()
    os.makedirs(os.path.join(HERE, "stl"), exist_ok=True)
    S.export_stl(ob, os.path.join(HERE, "stl", "deflector_black.stl"))
    write_3mf(ob, os.path.join(HERE, "deflector_black.3mf"))
    if "--renders" not in args:
        return
    out = os.path.join(HERE, "renders", "_preview" if "--preview" in args else "")
    os.makedirs(out, exist_ok=True)
    ob.location = (-34, 0, 0.5)        # centre it for the camera, just off the floor
    S.to_studio([ob])
    S.studio(samples=16 if "--preview" in args else 128,
             res=(800, 600) if "--preview" in args else (1400, 1050))
    views = {"defl_back": (-0.10, -0.14, 0.10), "defl_front": (0.10, 0.14, 0.10),
             "defl_top": (0.02, 0.03, 0.20)}
    for n, v in views.items():
        S.camera(v, target=(-0.0, 0.0, 0.012), lens=70)
        S.render(os.path.join(out, n + ".png"))
    ob.rotation_euler = (math.pi, 0, 0)          # upside down for the underside view
    ob.location = (-34, 0, 28.5)
    S.camera((0.10, -0.14, 0.10), target=(0, 0, 0.012), lens=70)
    S.render(os.path.join(out, "defl_under.png"))


if __name__ == "__main__":
    main()
