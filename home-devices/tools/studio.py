"""Shared modeling + studio-render helpers for the home device family.

Model in millimetres (1 Blender unit = 1 mm) so STL exports are print-ready,
then call `to_studio()` which parents everything to a 0.001-scaled empty so
lights and camera work in real-world metres.
"""
import math

import bmesh
import bpy
from mathutils import Vector

# ---------------------------------------------------------------- design language
# One palette for every device: white body, black base, a single red accent.
PLA = {
    "white": (0.70, 0.70, 0.68, 1),
    "black": (0.007, 0.007, 0.008, 1),
    "red": (0.62, 0.025, 0.02, 1),
}
CORNER_R = 10.0      # plan-view corner radius on every enclosure
EDGE_R = 1.2         # small fillet on top edges
SHADOW_GAP = 0.6     # inset of the black base under the white shell


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.unit_settings.system = "METRIC"


# ---------------------------------------------------------------- materials
def material(name, color, rough=0.48, coat=0.0, emission=None, strength=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = color
    b.inputs["Roughness"].default_value = rough
    b.inputs["Coat Weight"].default_value = coat
    if emission:
        b.inputs["Emission Color"].default_value = emission
        b.inputs["Emission Strength"].default_value = strength
    return m


def pla(color):
    return material(f"PLA {color}", PLA[color], rough=0.52)


def assign(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj


# ---------------------------------------------------------------- geometry
def _link(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def rounded_box(name, sx, sy, sz, r=CORNER_R, r_top=0.0, r_bot=0.0, seg=24,
                loc=(0, 0, 0)):
    """Box with rounded vertical corners; optional fillets on top/bottom rims.
    Origin at the bottom-centre."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1)
    for v in bm.verts:
        v.co = Vector((v.co.x * sx, v.co.y * sy, (v.co.z + 0.5) * sz))
    if r > 0:
        vert = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 1e-6]
        bmesh.ops.bevel(bm, geom=vert, offset=min(r, sx / 2 - 1e-3, sy / 2 - 1e-3),
                        segments=seg, profile=0.5, affect="EDGES")
    for zt, rr in ((sz, r_top), (0.0, r_bot)):
        if rr > 0:
            rim = [e for e in bm.edges
                   if all(abs(v.co.z - zt) < 1e-6 for v in e.verts)
                   and len(e.link_faces) == 2
                   and any(abs(f.normal.z) < 0.5 for f in e.link_faces)]
            bmesh.ops.bevel(bm, geom=rim, offset=rr, segments=6, profile=0.5,
                            affect="EDGES")
    ob = _link(name, bm)
    ob.location = loc
    return ob


def cylinder(name, d, h, loc=(0, 0, 0), rot=(0, 0, 0), seg=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=seg, radius=d / 2, depth=h,
                                        location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    return ob


def box(name, sx, sy, sz, loc=(0, 0, 0)):
    """Plain box, origin at its centre."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (sx, sy, sz)
    bake(ob)
    return ob


def slot(name, w, h, depth, loc, axis="Y", r=None):
    """Rounded-rectangle cutter (stadium-ish) going through a wall along axis."""
    r = min(w, h) / 2 - 1e-3 if r is None else r
    ob = rounded_box(name, w, h, depth, r=r, seg=16)
    ob.location = (0, 0, -depth / 2)
    bake(ob)
    if axis == "Y":
        ob.rotation_euler = (math.pi / 2, 0, 0)
    elif axis == "X":
        ob.rotation_euler = (math.pi / 2, 0, math.pi / 2)
    ob.location = loc
    bake(ob)
    return ob


def text(name, body, size, depth, loc, align="LEFT"):
    bpy.ops.object.text_add(location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.data.body = body
    ob.data.size = size
    ob.data.extrude = depth / 2
    ob.data.align_x = align
    ob.data.space_character = 1.15
    bpy.ops.object.convert(target="MESH")
    return ob


def bake(ob):
    """Apply transforms and all modifiers in place."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev)
    me.transform(ob.matrix_basis)
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    ob.matrix_basis.identity()
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return ob


def _boolean(target, cutters, op):
    cutters = cutters if isinstance(cutters, (list, tuple)) else [cutters]
    for c in cutters:
        md = target.modifiers.new("b", "BOOLEAN")
        md.operation = op
        md.solver = "EXACT"
        md.object = c
        bake(target)
        bpy.data.objects.remove(c, do_unlink=True)
    return target


def cut(target, cutters):
    return _boolean(target, cutters, "DIFFERENCE")


def union(target, others):
    return _boolean(target, others, "UNION")


def join(objs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    objs[0].name = name
    return objs[0]


def smooth(ob, angle=35):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle))


def export_stl(ob, path):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True,
                          apply_modifiers=True)


# ---------------------------------------------------------------- studio
def to_studio(objs):
    """Parent the mm-scale model to an empty scaled to metres."""
    root = bpy.data.objects.new("Model", None)
    bpy.context.collection.objects.link(root)
    root.scale = (0.001, 0.001, 0.001)
    for o in objs:
        o.parent = root
    return root


def _area(name, loc, size, power, color=(1, 1, 1), target=(0, 0, 0.02), spread=180):
    li = bpy.data.lights.new(name, "AREA")
    li.spread = math.radians(spread)
    li.shape = "RECTANGLE"
    li.size, li.size_y = size
    li.energy = power
    li.color = color
    ob = bpy.data.objects.new(name, li)
    bpy.context.collection.objects.link(ob)
    ob.location = loc
    d = Vector(target) - Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return ob


def studio(backdrop=(0.013, 0.0135, 0.015, 1), samples=96, res=(1600, 1200)):
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = samples
    s.cycles.use_denoising = True
    s.cycles.max_bounces = 8
    s.render.resolution_x, s.render.resolution_y = res
    s.render.film_transparent = False
    s.view_settings.view_transform = "AgX"
    s.view_settings.look = "AgX - Medium High Contrast"
    s.view_settings.exposure = -0.45

    # cyclorama: floor sweeping up into a back wall
    bm = bmesh.new()
    prof = [(-3.0, 0.0)]
    R, y0 = 0.6, 0.35
    for i in range(25):
        a = i / 24 * math.pi / 2
        prof.append((y0 + R * math.sin(a), R - R * math.cos(a)))
    prof.append((y0 + R, 3.0))
    left = [bm.verts.new((-4, y, z)) for y, z in prof]
    right = [bm.verts.new((4, y, z)) for y, z in prof]
    for i in range(len(prof) - 1):
        bm.faces.new((left[i], left[i + 1], right[i + 1], right[i]))
    cyc = _link("Backdrop", bm)
    for p in cyc.data.polygons:
        p.use_smooth = True
    bd = material("Backdrop", backdrop, rough=1.0)
    bd.node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value = 0.0
    assign(cyc, bd)

    w = bpy.data.worlds.new("World")
    s.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.5, 0.5, 0.52, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.08

    _area("Key", (-0.45, -0.35, 0.55), (0.6, 0.6), 22, (1.0, 0.97, 0.93))
    _area("Fill", (0.55, -0.45, 0.25), (0.8, 0.5), 6, (0.92, 0.95, 1.0))
    _area("Rim", (0.15, 0.55, 0.45), (0.5, 0.2), 30)
    _area("Top", (0, 0, 0.7), (0.4, 0.4), 3)
    # Raking light: skims low across the roof so engraved text and vents cast shadows.
    _area("Rake", (-0.55, 0.12, 0.075), (0.30, 0.03), 0.6, (1.0, 0.98, 0.95),
          target=(0.0, 0.0, 0.036), spread=25)


# ---------------------------------------------------------------- technical drawings
def drawing_setup(res=(1800, 1200), samples=24):
    """Flat grey shading with black outlines, for dimensioned orthographic views."""
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = samples
    s.cycles.use_denoising = True
    s.render.resolution_x, s.render.resolution_y = res
    s.render.film_transparent = True
    s.view_settings.view_transform = "Standard"
    s.view_settings.look = "None"
    s.view_settings.exposure = 0.0
    w = bpy.data.worlds.get("Drawing") or bpy.data.worlds.new("Drawing")
    s.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    s.render.use_freestyle = True
    s.render.line_thickness_mode = "ABSOLUTE"
    s.render.line_thickness = 1.6
    vl = s.view_layers[0]
    vl.use_freestyle = True
    fs = vl.freestyle_settings
    fs.crease_angle = math.radians(140)
    ls = fs.linesets[0] if fs.linesets else fs.linesets.new("Lines")
    ls.select_by_visibility = True
    ls.visibility = "VISIBLE"
    ls.select_silhouette = ls.select_border = ls.select_crease = True
    if ls.linestyle is None:
        ls.linestyle = bpy.data.linestyles.new("Ink")
    ls.linestyle.color = (0.08, 0.08, 0.09)
    ls.linestyle.thickness = 1.6
    for ob in bpy.data.objects:
        if ob.type == "LIGHT" or ob.name == "Backdrop":
            ob.hide_render = True


ORTHO_EULER = {  # camera rotation per view; screen axes noted for dimensioning
    "front": (math.pi / 2, 0, 0),             # looks +Y; right=+X, up=+Z
    "back": (math.pi / 2, 0, math.pi),        # looks -Y; right=-X, up=+Z
    "left": (math.pi / 2, 0, -math.pi / 2),   # looks +X; right=-Y, up=+Z
    "right": (math.pi / 2, 0, math.pi / 2),   # looks -X; right=+Y, up=+Z
    "top": (0, 0, 0),                         # looks -Z; right=+X, up=+Y
    "bottom": (math.pi, 0, 0),                # looks +Z; right=+X, up=-Y
}
ORTHO_DIRS = {"front": (0, -1, 0), "back": (0, 1, 0), "left": (-1, 0, 0), "right": (1, 0, 0),
              "top": (0, 0, 1), "bottom": (0, 0, -1)}


def ortho_camera(view, center_m, scale_m, name="Ortho"):
    cam = bpy.data.cameras.new(name)
    cam.type = "ORTHO"
    cam.ortho_scale = scale_m
    cam.sensor_fit = "HORIZONTAL"
    cam.clip_start, cam.clip_end = 0.001, 2.0
    ob = bpy.data.objects.new(name, cam)
    bpy.context.collection.objects.link(ob)
    ob.location = Vector(center_m) + Vector(ORTHO_DIRS[view]) * 0.5
    ob.rotation_euler = ORTHO_EULER[view]
    bpy.context.scene.camera = ob
    return ob


def camera(loc, target=(0, 0, 0.015), lens=85, name="Camera"):
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    cam.clip_start = 0.01
    ob = bpy.data.objects.new(name, cam)
    bpy.context.collection.objects.link(ob)
    ob.location = loc
    d = Vector(target) - Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = ob
    return ob


def render(path):
    s = bpy.context.scene
    s.render.image_settings.file_format = "PNG"
    s.render.filepath = path
    bpy.ops.render.render(write_still=True)
