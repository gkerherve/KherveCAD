# KherveCAD

An easy-to-use CAD GUI with **OpenSCAD as the engine**, in the Kherve
family (KherveFitting, KherveSheet, KhervePaint, KherveBook, ...),
built with Python + PyQt5.

Build parts the visual way — draw 2D profiles, extrude them, combine
with booleans — while KherveCAD writes the OpenSCAD program for you:

- **Objects tree** (top-left) — every shape and operation is a node;
  right-click to hide/show, group/ungroup, apply operations, rename,
  duplicate or delete; drag to restructure.
- **Code tab** — the OpenSCAD program generated live from the tree,
  syntax-highlighted, exportable as `.scad`.
- **Properties** (bottom-left) — X/Y/radius/width/height, extrusion
  height/twist/scale, rotation angles... every parameter of the
  selected object, editable live.
- **2D sketch view** (top-right) — draw lines, rectangles, circles,
  polygons and text; move shapes and drag resize handles; grid with
  snap.
- **3D preview** (bottom-right) — orbit/pan/zoom shaded view. With
  the [OpenSCAD](https://openscad.org) binary installed you see the
  exact rendered mesh (booleans included); without it a built-in
  tessellator previews extrusions and primitives.
- **KherveAI chat box** (Ctrl+/) — the family assistant panel:
  Claude, Mistral or Ollama Cloud behind one chat. It sees the live
  OpenSCAD program, answers questions, runs slash commands
  (`/part cf40 tee`, `/code`, `/render`, …) and its `scad` replies
  apply straight into the object tree.

Going further:

- **Control flow** — for loops, while loops (unrolled to valid
  OpenSCAD), if/else and variables; any numeric field accepts
  expressions like `i * 10 + 2`.
- **Rounding** — `offset()` rounds 2D corners before extrusion;
  Apply > Round edges wraps a solid in `minkowski()` + sphere for
  post-extrusion edge rounding. Circles take an angle for quarter
  and semi circles.
- **Import/export** — full `.scad` import (lossless round-trip of
  everything KherveCAD generates; graceful warnings elsewhere) and
  export; STL import as tree nodes and STL export.
- **Parts library** (Ctrl+L, non-modal) — parametric CF16-CF160
  flanges built from the manufacturer cross-section drawings
  (recessed sealing face, knife edge, gasket seat), KF16-KF50
  flanges, blanks, nipples, tees and crosses in conventional sizes
  (every dimension editable, so any size), M3-M20 hex bolts, socket
  head cap screws and hex nuts with real helical ISO threads,
  VAT-style gate valves and right-angle valves, and turbo pump
  shells in three inlet classes (DN63 / DN100 / DN160 CF).
- **Assembly mode** — pick a view plane (Top XY / Front XZ /
  Side YZ) in the 2D viewer: every part shows as a draggable
  outline; drop it to position it along the chosen axes and build
  whole systems (a chamber + gate valve + turbo, say). Everything
  is millimetres: scale bar, live size readout while drawing, zoom
  indicator, Fit Sketch / Zoom to Selection. Middle-mouse drag pans;
  the wheel zooms.
- **Selection highlight & isolate** — select any object (even a
  sub-part deep in an assembly) and its geometry lights up amber in
  the 3D view; the 2D view shows *only* that object, as its true
  projected shape in the current plane. Tab / Shift+Tab (or Q / A)
  step through objects.
- **Render styles** — View > 3D Render Style: shaded, brushed metal
  (with specular highlights), matte, wireframe or x-ray.
- **Undo/redo** (Ctrl+Z / Ctrl+Y) for every edit; drags collapse to
  a single step.
- **Colors** — right-click > Color... wraps objects in OpenSCAD's
  `color()`; the built-in preview shows per-face colours.

Documents save as `.kcad` (JSON object tree) and export as `.scad`
programs or `.stl` meshes.

## Run

```
pip install -r requirements.txt
python KherveCAD.py
```

Installing OpenSCAD is optional but recommended — KherveCAD finds it
on PATH or via Edit > Locate OpenSCAD.

## Tools

| Key | Tool |
| --- | --- |
| V | Select (move / resize handles / rubber-band) |
| L | Line (extrudable stroke) |
| R | Rectangle |
| C | Circle |
| P | Polygon (click points, double-click or Enter to close) |
| T | Text |

One-click 3D primitives: cube, sphere, cylinder. Operations applied
to the selection: linear extrude, rotate extrude, translate, rotate,
scale, mirror, group (union), difference, intersection. F5 forces an
OpenSCAD render; wheel zooms both views; themes under View > Theme.

## Tests

```
python -m pytest tests/
```

## License

GPL-3.0 — Gwilherm Kerherve.
