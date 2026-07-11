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
