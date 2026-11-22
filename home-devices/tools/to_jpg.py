"""Convert render PNGs to JPEGs for review pages (inside Blender: no Pillow needed).

    blender --background --factory-startup --python to_jpg.py -- <renders_dir> [quality]

Converts every *.png in the folder (not subfolders, not files starting with "_" or "dwg_").
"""
import os
import sys

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
folder = args[0]
quality = int(args[1]) if len(args) > 1 else 88
s = bpy.context.scene
s.render.image_settings.file_format = "JPEG"
s.render.image_settings.quality = quality
s.view_settings.view_transform = "Standard"     # the PNGs already carry the AgX look
s.view_settings.look = "None"
for f in sorted(os.listdir(folder)):
    if not f.endswith(".png") or f.startswith(("_", "dwg_")):
        continue
    im = bpy.data.images.load(os.path.join(folder, f))
    im.save_render(os.path.join(folder, f[:-4] + ".jpg"), scene=s)
    bpy.data.images.remove(im)
    print("jpg", f)
