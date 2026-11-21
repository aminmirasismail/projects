"""Convert renders/*.png to .jpg (quality 90) for the review page. Run: blender -b --python tojpg.py"""
import glob
import os

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
s = bpy.context.scene
s.render.image_settings.file_format = "JPEG"
s.render.image_settings.quality = 90
# PNGs already carry the AgX look; save them through a neutral transform so it isn't applied twice
s.view_settings.view_transform = "Standard"
s.view_settings.look = "None"
s.view_settings.exposure = 0.0
s.view_settings.gamma = 1.0
for p in glob.glob(os.path.join(HERE, "renders", "*.png")):
    im = bpy.data.images.load(p)
    im.save_render(p[:-4] + ".jpg", scene=s)
    bpy.data.images.remove(im)
    print("jpg", os.path.basename(p))
