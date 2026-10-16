---
name: model-from-blueprint
description: Model a real-world object in KherveCAD from its true dimensions and a blueprint found on the web — look up the size, find a multi-view drawing, ask before downloading it, cut it into views with khervecad.tools.refsheet, place each view at true size with set_reference_image, then build and check the model against it. Use whenever the user asks to model a real object (a car, aircraft, ship, train, tank, building, product, tool, piece of furniture) in KherveCAD, or says to find a blueprint or reference first.
---

# Model a real object from its blueprint

A model built from memory gets the proportions roughly right; one built
over a true-size drawing gets them right. This skill finds the real
dimensions and, where one exists, a multi-view drawing, and turns it
into KherveCAD reference images before any geometry is made.

The KherveCAD MCP tools (`mcp__khervecad__*`) drive the user's live
window. Web search and fetch are needed for steps 2-3; without them,
ask the user for the dimensions and a drawing of their own.

## 1. Pin down the object

The exact variant matters: "a Mini" is 3.05 m, a 2024 Mini is 3.88 m.
Name the make, model, year or generation, and body style (or ask, if
the user's words leave it open). Decide the model's axes now — for
vehicles KherveCAD's convention in this repo has been X = length with
the nose at +X, Y = width, Z = up, ground at z = 0.

## 2. Find the real dimensions

Search for them first — they matter more than any picture:

- **Vehicles:** length, width (without mirrors), height, wheelbase,
  track, tyre size. Spec sites (conceptcarz, automobile-catalog, the
  maker's spec sheet) or the Wikipedia infobox.
- **Aircraft / ships:** length, span / beam, height.
- **Products and furniture:** the maker's product page or spec sheet;
  IKEA-style assembly PDFs carry dimensioned drawings.
- **Mechanisms and tools:** patents (Google Patents) have drawings that
  are usually free to use; standard parts have datasheets.

Write the numbers down with their source, and convert to millimetres.
Two sources that agree beat one.

## 3. Find a drawing

Search for a multi-view drawing: `"<object> blueprint"`,
`"<object> side front top view"`, `"<object> technical drawing"`.
Good sources: the-blueprints.com (cars, aircraft, ships, trains, tanks),
drawingdatabase.com, Wikimedia Commons, Google Patents, makers' spec
sheets. The user may already have one — ask; it is the best source of
all (the user supplied the Mini and G-Class sheets this way).

No blueprint exists for most characters and creatures, one-off designs
or new products: fall back to photos or model sheets as loose
references, or design by eye with real sizes of comparable things.

## 4. Ask before downloading

Downloading needs the user's go-ahead every time. Say what, from where
and how big, e.g. *"Download mini-cooper-s-1966.png (≈120 KB) from
the-blueprints.com as a private modelling reference?"* Then:

```bash
curl -L --fail -o "<scratchpad>/<name>.png" "<image url>"
```

(WebFetch turns pages into text; it cannot fetch the image itself.)
Blueprints are usually copyrighted: they are a **private reference**.
Never ship one in `khervecad/parts/`, attach it to a Printables upload,
or commit it anywhere.

## 5. Cut the sheet into views

Look at the sheet (Read the image) and note a rough pixel box around
each view — side, front, back, top — that holds no other view or
caption. Then, from the KherveCAD repo root:

```bash
.venv/bin/python -m khervecad.tools.refsheet "<sheet.png>" \
    --length 3054 --width 1410 --height 1346 \
    --view side=12,8,380,210:mirror --view front=400,8,560,210 \
    --view top=12,230,380,400
```

`:mirror` flips a view left-right — a side view drawn nose-left, for a
model whose nose points to +X. The tool trims each box to the drawing,
saves `sheet-side.png` etc. beside the sheet and prints, per view, the
`set_reference_image` arguments for true size plus a `check`: the
height (or width) the picture implies against the real one. More than
~3 % out means a loose crop (a caption or shadow inside the box) or a
sheet not drawn to scale — fix the box, or trust the dimensions over
the drawing.

## 6. Place the views

New document (offer to save the user's work first), then one call per
view with the printed arguments:

```
set_reference_image(path=..., plane="Front", width=3054, x=-1527, y=0,
                    opacity=0.45)
```

Planes: **Front = XZ** (the side view of a vehicle), **Side = YZ** (its
front or back view), **Top = XY**. Use `offset` to push a picture
behind the model if it hides it. Render `orientations=["Front", "Right",
"Top"]` with `projection="Orthographic"` and confirm each picture sits
where the model will — nose at +X, wheels on the ground.

## 7. Build over the drawing

Block the big masses first (body, cabin, wheels at the real wheelbase
and track), then details. What works in KherveCAD:

- Hulls of spheres/boxes and plain primitives: exact in the built-in
  preview and fast in OpenSCAD. Heavy `difference`/`intersection`
  stacks are only exact once OpenSCAD's render lands — fast on the
  Manifold backend, minutes on old CGAL (`get_document_info` →
  `openscad.backend` says which).
- In `apply_code`, give every module a parameter (`module wheel(s=1)`):
  a zero-parameter module imports as an Object plus linked copies.
- `text()` loses `halign`/`valign` on import: centre it with a
  translate, measuring the width with the OpenSCAD CLI if needed.
- A comment on the line **above** a statement names it.

## 8. Check against the drawing and the numbers

- Orthographic `render_view` from Front, Right and Top with the
  references showing: silhouettes should sit on the drawing's lines.
  Fix what is off, re-render, repeat.
- `get_document_info` → `bounds_mm` against the real length, width and
  height; `get_node_bounds` for the wheelbase and track.

## 9. Finish

Keep the reference images (saved in the document, handy for later
edits) or `set_reference_image(clear=true)` — ask. Save the document,
and tell the user where the dimensions and drawing came from (sources
as links).
