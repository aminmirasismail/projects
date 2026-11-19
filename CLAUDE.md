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
- **Review every printed part before presenting it.** Run the `mech-design-review` agent
  (`.claude/agents/mech-design-review.md`) on each new or changed part, fix what it finds,
  then present. Check meshes and slices with `home-devices/tools/printcheck.py`.

## Branches

Each project has its own base branch; topic branches come off it and merge back into it, and
the base branch merges into `main` at milestones.

```
main                              stable; milestone merges only
home-devices/dev                  base branch for the home-devices project
home-devices/design/<topic>       modelling, renders, review pages
home-devices/print/<topic>        print tests, coupons, slicing
home-devices/feat/<topic>         firmware, Home Assistant, software
home-devices/fix/<topic>          corrections
home-devices/docs/<topic>         notes and docs only
dexter/dev, dexter/feat/<topic>   same pattern for the voice agent
```

Topics are short kebab-case names (`hub-concept-d`, `skin-coupons`). Start new work from the
project's `dev` branch, not from `main`. Never push to `main` without the owner's go-ahead.

## Repo layout

- `dexter/`: push-to-talk voice agent (Python, uv).
- `home-devices/`: a family of 3D-printed smart-home devices around a Home Assistant hub.
  - `tools/studio.py`: shared modelling helpers, design rules and the render studio.
  - `tools/dims.py`: turns orthographic renders into dimensioned SVG drawings.
  - `tools/printcheck.py`: mesh health, A1 Mini slicing via Bambu Studio's CLI, toolpath dump.
  - `hub/`: the hub enclosure (`hub.py` model, `concepts.py` lighting concepts,
    `light_study.py`, `review.html` and `concepts.html` review pages, `stl/`, `renders/`).
  - `tests/`: print-test coupons (`skin_coupons.py`, `skin_test_plate.3mf`).
- `ideas.html`: the project idea list (published as the "Idea Bench" artifact).

## Naming

- **Concepts are letters** (concept A, B, C...): alternative design directions.
- **Iterations are version numbers** (v1, v2, v3...): successive builds of the chosen design.
  Never use letters for iterations. The hub's old "Rev A–D" are v1–v4 (v4 is concept D);
  the next hub iteration is v5.

## Venting and light rules (owner, 2026-11-19)

- Keep good ventilation: an inlet/exhaust low (bottom or side) and another high.
- Hide vents, or make them a deliberate design feature, never a plain grating on top.
- Every visible opening has light shining through it; no unlit visible seam next to a lit one.
- At most one visible continuous seam of light (on the hub: the underglow).

## Design language (home devices)

- White PLA body, black PLA base and internal parts, at most one accent. Printed on a Bambu
  A1 Mini (180 × 180 mm bed), one colour per part, no AMS.
- Rounded-rectangle plan, 10–12 mm corners, 1.2 mm top edge fillet.
- Black base inset 0.6 mm under the shell, so it reads as a shadow line.
- Small engraved mono labels, e.g. `HOME · 01`. No logos. Screws only on the underside.
- Label words are split by the house dot: a modelled round dot (0.22 × text size, Ø1.3 at
  6 mm) centred on the cap height like a dot-product dot, cut 1.2 mm deep (twice the letters)
  so it reads a shade darker. Never a `/` or a font glyph. Build labels with
  `S.product_label()` in `tools/studio.py`; `dot` is the default. (`ring`, `pair` and a red
  filament `inlay` exist, but the owner chose the plain dot.) In text (pages, captions)
  write the separator as `·`.
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
- Engineering reports also show every printed part on its own: a quick 4-view sheet (above,
  below, top, side) plus a render of it on the A1 Mini plate in its print orientation, with a
  line on why that way up. Low fidelity is fine (see `hub/part_views.py`).

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
- Engraved text goes on flat faces only, >= 1 mm from where a fillet starts. Blender places
  text by its baseline, so centre it on its real bounding box (see `label()` in
  `tests/skin_coupons.py`).
- No fillet that stops dead in a sharp corner where bodies meet: match radii or drop them.
- Vertical walls are extrusion lines: >= 0.5 mm with a 0.4 nozzle (0.4 mm got dropped).
  Check thin features on every layer of the slice.
- Export meshes with Blender's `loop_triangles`; a hand-written fan folds concave faces.
- Engraved strokes must be wider than the nozzle (aim >= 0.6 mm): use `S.label_font()` (bold
  mono) at ~6 mm. Don't thicken text with the curve `offset`: it self-intersects and wrecks
  booleans (it emptied a whole part once; `S.cut` now raises if that happens).
- Slice with the filament the owner's printer has synced to Bambu Studio, never an assumed
  "PLA Basic": `printcheck.py slice` reads it from BambuStudio.conf by default (white Bambu
  PLA Matte as of 2026-11-19). If a part needs a colour the printer hasn't synced (e.g. black),
  ask the owner to load and sync it, or which preset to use.
- Never launch Bambu Studio yourself (not even `bambu-studio.exe file.3mf`): a second instance
  signed in to the same account knocks the printer connection off ("failed to connect to
  server") until the owner signs out and back in. Slice with the CLI, put the sliced
  `.gcode.3mf` in `home-devices/<device>/print/` (git-ignored), and let the owner open it with
  File > Open in their own Studio window.
- Bambu Studio's CLI does not resolve preset `inherits` chains reliably: it once sliced
  "Bambu PLA Basic" at 200 C and 2 mm3/s. `printcheck.py` flattens the chains itself; always
  check temps, volumetric speed and acceleration in the G-code header, and cross-check the
  estimate against the Studio GUI before sending a print.

## Open items

- Pi 5 port positions in `hub/hub.py` are provisional until checked against RP-008347.
- Hub lighting direction: **concept D (underglow)**, the owner's choice (2026-11-18). The shell
  floats on a small inset black base and an LED strip washes light onto the table; no light
  through the white shell. Light-through-plastic (concept F, thin skins) is tabled.
- Light diffusion experiments are a separate later project: the skin coupons (printed
  2026-11-18) plus a jig with pin-located LED carriers on interchangeable spacer pins and
  black walls. See the "Light diffusion test rig" idea on the Idea Bench.
- `README.md` links to `dexter_handheld_mobile_agent/`, but the folder is `dexter/`.
