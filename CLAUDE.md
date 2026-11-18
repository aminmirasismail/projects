# CLAUDE.md

Guidance for Claude Code sessions in this repo. Read it at the start of every session.

## How to work (the owner's standing preferences)

- **Default to a local session.** The owner's working copy is at `C:\git\projects` on their
  Windows PC, which also runs Bambu Studio connected to their Bambu A1 Mini. Do the work there,
  on the branch that's checked out locally.
- **If you're running in a cloud session** (a container with the repo cloned from GitHub),
  say so at the start and point out what it can't do: it can't reach the owner's PC, files,
  apps or printer. Suggest continuing in a local session for anything that needs those.
  Rendering and modelling work fine in the cloud.
- **Commit and push as you go.** Commit each meaningful step with a clear message and push to
  `origin` straight away, so local and cloud sessions always see the latest work. Don't batch
  everything up to the end.
- **Never start a print without an explicit yes.** Prepare and slice, show the plate,
  time and filament estimate, then wait for the owner to approve before sending to the printer.
- Present designs visually: renders, close-ups, dimensioned drawings, and a review page,
  rather than describing them in text.

## Repo layout

- `dexter/`: push-to-talk voice agent (Python, uv).
- `home-devices/`: a family of 3D-printed smart-home devices around a Home Assistant hub.
  - `tools/studio.py`: shared modelling helpers, design rules and the render studio.
  - `tools/dims.py`: turns orthographic renders into dimensioned SVG drawings.
  - `hub/`: the hub enclosure (`hub.py` model, `concepts.py` lighting concepts,
    `light_study.py`, `review.html` and `concepts.html` review pages, `stl/`, `renders/`).
  - `tests/`: print-test coupons (`skin_coupons.py`, `skin_test_plate.3mf`).
- `ideas.html`: the project idea list (published as the "Idea Bench" artifact).

## Design language (home devices)

- White PLA body, black PLA base and internal parts, at most one accent. Printed on a Bambu
  A1 Mini (180 × 180 mm bed), one colour per part, no AMS.
- Rounded-rectangle plan, 10–12 mm corners, 1.2 mm top edge fillet.
- Black base inset 0.6 mm under the shell, so it reads as a shadow line.
- Small engraved mono labels, e.g. `HOME / 01`. No logos. Screws only on the underside.
- Inspiration: Apple, Teenage Engineering. Clean, quiet, deliberate.

## Render style (keep every render consistent)

Everything is set in `tools/studio.py`; reuse `S.studio()` and `S.camera()` instead of
building new lighting.

- Blender via the `bpy` Python module (Cycles, CPU), models in millimetres, scaled to metres
  by `S.to_studio()` for lighting.
- Dark studio: near-black matte cyclorama (albedo ~0.013, no specular), AgX
  "Medium High Contrast", exposure −0.45.
- Lights: warm key, cool fill, rim, soft top, plus a low raking light with a 25° spread at
  low power, so engraved text and small details cast shadows.
- PLA colours: white `(0.70, 0.70, 0.68)`, black `(0.007, 0.007, 0.008)`, red `(0.62, 0.025, 0.02)`.
- For light simulations, give white PLA subsurface scattering (scale ~1.2 mm). Render
  "dark room" (studio lights at 3%) and "room light" versions, and use the same realistic LED
  output across options when comparing them.
- Standard set per design: hero, ports, top, exploded, cutaway, underside, close-ups
  (1400×1050), and dimensioned drawings via `--drawings` plus `tools/dims.py`.

## Lessons learned

- LED strips bend through their thickness, not sideways: mount them on edge around a channel.
- Light behind 2 mm white PLA makes the whole shell glow. Box every LED in a black channel
  with an opening only where light should exit.
- Through-plastic light washes out in daylight; compare options at equal LED output.
- Blender's EXACT boolean can empty small meshes; MANIFOLD can hollow others. Check
  section cuts.
- Cloud sessions here allow `datasheets.raspberrypi.com` and `pip.raspberrypi.com` (for the
  official Pi 5 drawing, RP-008347), but GitHub release downloads are blocked, so slicers
  can't be installed in the cloud. Slice on the owner's PC.

## Open items

- Pi 5 port positions in `hub/hub.py` are provisional until checked against RP-008347.
- Hub lighting direction: concept F (thin-skin reveal line + underglow) recommended, pending
  the thin-skin coupon test.
- `README.md` links to `dexter_handheld_mobile_agent/`, but the folder is `dexter/`.
