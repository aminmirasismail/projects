"""Quick part sheets for the engineering report: each printed part on its own, from four
angles, plus how it sits on the A1 Mini's bed for printing. Low-fidelity on purpose (Cycles at
24 samples, plain grey sky and one sun): the aim is to show what you are printing, not to sell it.

    uv run ... --with bpy --with pillow python part_views.py      (after hub.py exported stl/)

Writes renders/parts/<part>_views.jpg (2 x 2 sheet) and renders/parts/<part>_print.jpg.
"""
import math
import os

import bpy
from mathutils import Vector
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
STL = os.path.join(HERE, "stl")
OUT = os.path.join(HERE, "renders", "parts")
BED = 180.0                          # A1 Mini build plate, mm

WHITE = (0.80, 0.80, 0.78)          # (studio.py's PLA white, brightened for flat light)
BLACK = (0.10, 0.10, 0.11)           # lifted from true black so edges and holes still read
# name, file, colour, print rotation (euler, rad) and a one-line orientation note
PARTS = [
    ("shell", "hub_shell_white.stl", WHITE, (math.pi, 0, 0), "Upside down: roof on the bed"),
    ("plinth", "hub_plinth_black.stl", BLACK, (math.pi, 0, 0),
     "Upside down: top plate on the bed"),
    ("frame", "hub_frame_black.stl", BLACK, (0, 0, 0), "Flat, as fitted"),
    ("floor", "hub_floor_black.stl", BLACK, (0, 0, 0), "Flat, plate on the bed, standoffs up"),
    ("diffuser", "hub_diffuser_white.stl", WHITE, (math.pi, 0, 0),
     "Flat, visible (lower) face up"),
    ("fittest", "hub_fittest_portsend_white.stl", WHITE, (math.pi, 0, 0),
     "Upside down, like the shell"),
]
# view name, direction from the part centre to the camera, ortho?
VIEWS = [("Iso, from above", (1.0, -1.25, 0.95), False),
         ("Iso, from below", (-1.0, 1.25, -0.9), False),
         ("Top", (0, 0, 1), True),
         ("Side (I/O end, -X)", (-1, 0, 0), True)]
RES = (900, 680)


def scene_setup():
    """Plain grey sky + one sun, Cycles at low samples: holes and insides read dark, which
    Workbench's flat shading lost (the I/O windows vanished in the straight-on view)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = 24
    s.cycles.use_denoising = True
    s.cycles.max_bounces = 4
    s.render.resolution_x, s.render.resolution_y = RES
    s.view_settings.view_transform = "Standard"
    s.view_settings.exposure = -0.2
    w = bpy.data.worlds.new("W")
    s.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.92, 0.92, 0.93, 1)
    bg.inputs["Strength"].default_value = 0.75
    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy = 2.2
    sun.angle = math.radians(12)
    so = bpy.data.objects.new("Sun", sun)
    bpy.context.collection.objects.link(so)
    so.rotation_euler = (math.radians(40), math.radians(-25), math.radians(-35))
    return s


def mat(colour):
    m = bpy.data.materials.new("m")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*colour, 1)
    b.inputs["Roughness"].default_value = 0.55
    return m


def load(fname, colour):
    bpy.ops.wm.stl_import(filepath=os.path.join(STL, fname))
    ob = bpy.context.selected_objects[0]
    ob.data.materials.append(mat(colour))
    bpy.ops.object.shade_auto_smooth(angle=math.radians(35))
    return ob


def bbox(ob):
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def camera(direction, center, size, ortho):
    cam = bpy.data.cameras.new("C")
    cam.clip_start, cam.clip_end = 1, 5000
    ob = bpy.data.objects.new("C", cam)
    bpy.context.collection.objects.link(ob)
    d = Vector(direction).normalized()
    ob.location = center + d * size * 4
    up = "Y" if abs(d.z) < 0.99 else "Y"
    ob.rotation_euler = (-d).to_track_quat("-Z", up).to_euler()
    if abs(d.z) > 0.99:                  # straight down/up: keep +X to the right
        ob.rotation_euler = (0, 0, 0) if d.z > 0 else (math.pi, 0, 0)
    if ortho:
        cam.type = "ORTHO"
        cam.ortho_scale = size * 1.25
    else:
        cam.lens = 85
        cam.sensor_width = 36
        ob.location = center + d * size * 3.4
    bpy.context.scene.camera = ob
    return ob


def render(path):
    s = bpy.context.scene
    s.render.image_settings.file_format = "PNG"
    s.render.filepath = path
    bpy.ops.render.render(write_still=True)


def font(size, bold=False):
    for f in (("consolab.ttf" if bold else "consola.ttf"), "DejaVuSansMono.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def caption(img, text, sub=None):
    d = ImageDraw.Draw(img)
    d.text((22, 16), text, fill=(30, 30, 34), font=font(30, True))
    if sub:
        d.text((22, 54), sub, fill=(95, 95, 100), font=font(22))


def views(name, ob):
    lo, hi = bbox(ob)
    c, size = (lo + hi) / 2, max(hi - lo)
    tiles = []
    for i, (label, d, ortho) in enumerate(VIEWS):
        cam = camera(d, c, size, ortho)
        p = os.path.join(OUT, f"_{name}_{i}.png")
        render(p)
        bpy.data.objects.remove(cam, do_unlink=True)
        im = Image.open(p).convert("RGB")
        caption(im, label)
        tiles.append(im)
        os.remove(p)
    w, h = RES
    g = 6
    sheet = Image.new("RGB", (2 * w + g, 2 * h + g), (200, 200, 204))
    for i, im in enumerate(tiles):
        sheet.paste(im, ((i % 2) * (w + g), (i // 2) * (h + g)))
    sheet.save(os.path.join(OUT, f"{name}_views.jpg"), quality=88)


def bed():
    """The A1 Mini plate: 180 x 180, dark textured-PEI grey, with a 10 mm grid."""
    bpy.ops.mesh.primitive_plane_add(size=BED, location=(0, 0, -0.6))
    p = bpy.context.active_object
    p.scale.z = 1
    p.data.materials.append(mat((0.05, 0.05, 0.05)))
    objs = [p]
    grid = mat((0.14, 0.14, 0.14))
    for i in range(-8, 9):
        for axis in ("x", "y"):
            bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, -0.55))
            ln = bpy.context.active_object
            ln.scale = (BED, 0.25, 1) if axis == "x" else (0.25, BED, 1)
            if axis == "x":
                ln.location.y = i * 10
            else:
                ln.location.x = i * 10
            ln.data.materials.append(grid)
            objs.append(ln)
    return objs


def print_view(name, ob, rot, note):
    ob.rotation_euler = rot
    bpy.context.view_layer.update()
    lo, hi = bbox(ob)
    ob.location -= Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))   # centred, on the bed
    bpy.context.view_layer.update()
    lo, hi = bbox(ob)
    plate = bed()
    c = Vector((0, 0, 8))
    cam = camera((0.95, -1.3, 1.05), c, BED * 0.62, False)
    render(os.path.join(OUT, "_p.png"))
    im = Image.open(os.path.join(OUT, "_p.png")).convert("RGB")
    os.remove(os.path.join(OUT, "_p.png"))
    sz = hi - lo
    caption(im, f"Print: {note}",
            f"on the A1 Mini plate (180 x 180) · {sz.x:.1f} x {sz.y:.1f} x {sz.z:.1f} mm")
    im.save(os.path.join(OUT, f"{name}_print.jpg"), quality=88)
    for o in plate + [cam]:
        bpy.data.objects.remove(o, do_unlink=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fname, colour, rot, note in PARTS:
        scene_setup()
        ob = load(fname, colour)
        views(name, ob)
        print_view(name, ob, rot, note)
        print("done", name)


if __name__ == "__main__":
    main()
