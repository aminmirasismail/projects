# Home devices

A family of small home gadgets that report to a Home Assistant hub, designed to print on a Bambu A1 Mini in white, black and red PLA.

| # | Device | Status |
|---|--------|--------|
| 01 | [Hub](hub/) — Raspberry Pi 5 running Home Assistant | Concept, rev A |
| 02 | Laundry pods | Next |
| 03 | Air quality station | Planned |
| 04 | Bed-to-bathroom path lights | Planned |
| 05 | Kitchen timer | Planned |
| 06 | Leaving-home panel | Planned |
| 07 | Doorbell | Planned |

## Folder layout

Each device folder has:

- `<device>.py`: the model, written as a Blender Python script. It is the source of truth.
- `<device>.blend`: the generated Blender file. Open it in Blender to look around.
- `stl/`: print-ready parts, one file per part. The filename says which PLA colour to use.
- `renders/`: images and turntable video.
- `review.html`: the design review page.

`tools/studio.py` holds the shared design rules (colours, corner radii, shadow gap) and the render studio, so every device looks like part of the same set.

## Rebuilding

The scripts run with Blender's Python module (`pip install bpy`, which needs the matching Python version), or inside Blender itself:

```bash
python hub/hub.py                 # model + STL + .blend
python hub/hub.py --renders       # plus still renders
python hub/hub.py --turntable     # plus turntable video (needs ffmpeg)
```

The `.blend` files are saved from Blender 5.2. Older versions can usually open them but may warn.
