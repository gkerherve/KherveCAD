# KherveCAD — notes for Claude

KherveCAD is an easy-to-use CAD GUI built on PyQt5 with **OpenSCAD as
the engine** — a native desktop app in the Kherve family
(KherveFitting, KherveSheet, KhervePDF, KherveDOC, KhervePlot,
KherveDraw, KhervePaint, KherveBook). The document is a tree of
objects (2D shapes, 3D primitives, extrusions, transforms, booleans)
that maps 1:1 to an OpenSCAD program: every tool just creates or
edits nodes, and the program shown in the Code tab is regenerated
from the tree, so the two can never disagree.

## Build / run

- Python 3.11+ with PyQt5 (+ qtawesome for icons).
- Run via `python KherveCAD.py` or `python -m khervecad`.
- The **OpenSCAD binary is optional but recommended**: when found
  (PATH, common install dirs, or Edit > Locate OpenSCAD) the 3D view
  and STL export use exact OpenSCAD renders, booleans included.
  Without it the built-in tessellator (`mesh.py`) previews
  extrusions/primitives and approximates booleans (first operand).
- Crash log: `%TEMP%/khervecad_crash.log`.
- **Version string** is derived at runtime in `_version.py` from
  `git rev-list --count HEAD` and `git rev-parse --short HEAD`,
  cached with `lru_cache`. Falls back to `_FALLBACK = "0.1.0"`
  outside a git checkout. Title bar reads `KherveCAD v0.1.N+sha`.
  The version bumps automatically on every commit — never edit a
  version constant by hand.

## File size policy

Every module in `khervecad/` should stay near **1500 lines**. If a
change would push a file meaningfully past that, split the new code
into a new module and import.

## Project layout

- `KherveCAD.py` — entry script.
- `khervecad/` — package; `python -m khervecad` is the alternative entry.
  - `__init__.py`    — `APP_NAME`, version import.
  - `__main__.py`    — module entry point.
  - `_version.py`    — git-based version string.
  - `app.py`         — `main()`, crash log, Fusion style + theme.
  - `style.py`       — token-driven QSS themes (same template family
                       as KhervePaint; theme persists via QSettings).
  - `icons.py`       — qtawesome MDI icon wrapper with fallback.
  - `model.py`       — **the core**: `CadNode` tree, `NODE_TYPES`
                       registry (params + property schema + icon per
                       type), OpenSCAD codegen in `to_scad()`,
                       `DocumentModel` with change signals and all
                       editing operations (wrap/group/ungroup/move/
                       duplicate/round_edges/make_component). The
                       **`component` ("Object")** node type is a group
                       that compiles to its own zero-arg OpenSCAD
                       `module` plus one placed call (`module_name()`
                       sanitises/dedupes; `to_scad_map(only=...)` /
                       `subtree_scad()` emit one Object standalone with
                       the document globals), so the program reads as
                       an assembly of named parts and re-imports
                       losslessly (zero-param modules come back as
                       components, their placement wrappers folded into
                       params by `scadparse._fold_container`).
  - `expr.py`        — safe evaluator for OpenSCAD-style expressions
                       (whitelisted AST, trig in degrees); numeric
                       params may hold expression strings like
                       `i * 10` so loop variables work everywhere.
  - `document.py`    — `.kcad` JSON (de)serialisation, `.scad` export.
  - `scadparse.py`   — **.scad import**: tokenizer + recursive-descent
                       parser for the generated subset plus common
                       variations (d= diameters, scalar rotate/scale,
                       positional args, modifiers, for/if/assigns,
                       vector variables + `.x/.y/.z` swizzles and `[i]`
                       indexing, ranges `[a:s:b]`, ternary `c?a:b`,
                       **list comprehensions** `[for (i=r) let(..) if(c)
                       expr]`, `concat`, **user `module` definitions**
                       (each call *inlined* as a union with the arguments
                       bound to assign nodes, then the body re-parsed) and
                       **user `function` definitions** (evaluated with
                       recursion + cross-calls, so a `polygon` fed a
                       variable / comprehension / function — e.g. a NACA
                       airfoil — imports as concrete points). Import never
                       crashes a file: an unparseable statement is skipped
                       with a warning and parsing resumes.
                       `expr.py` evaluates the extra syntax (a scalar
                       reads as `[s,s,s]` so `cube(size)` works either
                       way). Constructs still outside the subset
                       (`function` definitions, `children()`, list
                       comprehensions, recursion) are skipped with
                       warnings. When a file
                       leans on those and imports **empty**, `import_scad`
                       offers to load it as a single **`scad_raw`** node
                       so the OpenSCAD engine still renders it (editable
                       as text in the Code tab, not as objects). Round-
                       trip (export -> import -> export) is lossless and
                       tested.
  - `library.py`     — parametric vacuum parts + fasteners + the
                       Insert > Part Library dialog (non-modal, so
                       it stays open while editing). CF flanges
                       (CF16-CF160) are one revolved cross-section
                       per the Lesker/VACGen drawings: recessed
                       sealing face, **knife edge** at the gasket
                       seal diameter, seat wall, chamfers; also KF
                       flanges, blank/nipple/tee/cross, a simplified
                       turbo shell, and M3-M20 hex bolts / socket
                       screws / hex nuts with **real helical ISO
                       threads** (thread-form polygon + twist extrude;
                       nuts subtract the thread with clearance). The
                       fasteners use the BOSL2 dimensional tables
                       (`BOLT_SIZES`): **chamfered** hex heads (DIN 933)
                       and hex nuts chamfered both faces (DIN 934), a
                       socket cap at the true ISO 4762 diameter with the
                       standard drive depth, and a lead-in chamfer at the
                       thread tip — all boolean-free where possible so
                       they preview. Also VAT-style **gate valves** and
                       right-angle valves, and turbo pump shells in
                       three inlet classes (DN63/DN100/DN160 CF); plus
                       CF/KF elbows, KF nipples/tees (`kf_fitting`),
                       CF/KF electrical feedthroughs, a hemispherical
                       electron energy analyser (dome + concentric inner
                       shell closed by a large **equatorial bolt flange**
                       with hex bolt heads, a stepped lens column to a
                       tapered entrance nozzle, and CF side ports), an
                       **XYZ(R1) manipulator** (edge-welded
                       `bellows` whose length is the Z-travel size),
                       and **rotary vane / dry scroll backing pumps**.
                       Parts are ordinary node subtrees; bolt circles
                       are for-loops. The
                       dialog groups parts by **category**; other
                       modules register parts by adding a `build`
                       callable to `PARTS`, which `build_part`
                       dispatches to.
  - `library_chem.py`— **Chemistry** parts: beaker, graduated
                       cylinder, test tube, Erlenmeyer / round-bottom
                       flasks, funnel, burette, Petri dish, watch
                       glass, test-tube rack, retort stand. Glassware
                       is a **revolved thin-wall profile** so it is
                       hollow without a boolean (renders in the
                       built-in preview), tinted glass via `color`.
  - `library_room.py`— **Room & furniture**: table, lab workbench,
                       chair, stool, monitor, TV, door (with frame),
                       wall panel, and coloured **carpet** squares
                       (colour chosen from the size list). Multi-colour
                       unions with no booleans, so each component keeps
                       its colour in the preview.
  - `examples.py`    — ready-made **example models** for the Examples
                       menu: each `build()` returns a fresh `root` that
                       replaces the document. A **Learn** category of 21
                       numbered tutorials, basic → advanced, one
                       technique each (primitives, 2D shapes, text,
                       translate/rotate/scale/mirror, linear & rotate
                       extrude, union/difference/intersection/hull/
                       minkowski, for loops incl. polar & nested,
                       variables, if/else, while, masters). A dozen
                       **Mechanical**
                       examples (parametric box, L-bracket, bolt & nut,
                       bolted flange joint, pillow block, spur gear,
                       meshing gear pair, ball bearing, V-belt pulley,
                       threaded rod, fan impeller, a **Masters +
                       Linked-copy bolt circle**) — several placing
                       library fasteners round a bolt circle by for-loop
                       — plus **Showcase** examples (orientation cubes,
                       2D boolean regions, a recursively-built fractal
                       tree, and a raw-OpenSCAD BOSL2 passthrough), a
                       **Flowers** category (layered bloom, phyllotaxis
                       sunflower, tulip, rose, daisy, lily, daffodil,
                       calla lily, poppy, hibiscus, orchid, cherry
                       blossom) and a **Trees** category (fir/conifer,
                       oak, palm, weeping willow, silver birch, cherry
                       blossom tree) — all procedural, petals/seeds/
                       fronds/branches unrolled from Python loops into the
                       tree; the named species live in
                       `examples_flowers.py` / `examples_trees.py`), a
                       vacuum starter and a desk setup. A **Projects**
                       category rebuilds one finished part per chapter of
                       the "Mastering OpenSCAD in 10 projects" course
                       (wall anchor, window stopper, clock movement, pen
                       holder, rubber stamp, flame sculpture, recursive
                       tree, parabolic reflector, fan wheel) natively, so
                       each previews and teaches that chapter's technique
                       (extrude taper, hull lever, coloured parts, polar
                       rotate_extrude arches, mirrored text, twist+scale,
                       recursion, a computed rotate_extrude curve, twisted
                       blades). `load_example()`
                       swaps it in; `EXAMPLES` is grouped by category.
                       Gears use trapezoidal teeth stamped by a for-loop;
                       bearings/pulleys use revolved rings so they
                       preview without a boolean; the fractal tree
                       recurses in the Python builder (the node tree has
                       no recursion) and unrolls into the object tree.
  - `examples_flowers.py` — the **Flowers** category's named species
                       (tulip, rose, daisy, lily, daffodil, calla lily,
                       poppy, hibiscus, orchid, cherry blossom), each a
                       procedural coloured-solids bloom.
  - `examples_trees.py` — the **Trees** category (fir/conifer, oak,
                       palm, weeping willow, silver birch, cherry blossom
                       tree), each a procedural coloured-solids tree.
                       Both flower/tree modules import the primitive
                       helpers from `examples.py` and extend
                       `examples.EXAMPLES` in place on import (a
                       side-effect import from the bottom of `examples.py`
                       so neither load order deadlocks).
  - `chat.py`        — **Assistant chat box** (family assistant, docked
                       right, toggled Ctrl+/): Claude/Mistral/Ollama
                       Cloud via urllib, keys in QSettings or env vars,
                       slash commands, and `scad` reply blocks applied to
                       the tree via scadparse.
  - `git_backend.py` — **per-document Git** (pygit2, ported from the
                       Kherve family): init/commit/push/pull, remotes and
                       history for the folder holding the current
                       `.kcad`. Degrades to no-ops if pygit2 is absent.
                       Wired to the **Git menu** (Commit Ctrl+K, Push,
                       Pull, Connect to GitHub); the status bar shows the
                       current file path, File > Show in File Explorer
                       reveals it.
  - `objecttab.py`   — the **Object tab**: `ObjectTab` (dropdown of the
                       document's Objects + "New") and `ComponentTree`
                       (the same tree widget rooted at the **active
                       Object**). The active Object is tracked by node
                       id with a name fallback so it survives renames
                       AND undo restores (which rebuild the tree with
                       fresh ids). While the Object tab is current,
                       `BuilderPanel.isolated_component()` is non-None
                       and **both viewers isolate to that Object**
                       (scene `isolation_resolver`, `_render_scope()` in
                       the main window); drawn shapes and Insert-menu
                       primitives land inside it.
  - `anchors.py`     — **anchors & origins**: auto bounding-box anchors
                       per Object (origin, 6 face centres, 12 edge
                       midpoints, 8 corners) computed from the LOCAL
                       mesh (`local_tris` zeroes the placement), plus
                       user anchors persisted in `params["anchors"]`.
                       World/local transforms (`anchor_world`,
                       `to_local`), `set_origin()` re-bases an Object
                       onto any anchor without moving it in the scene
                       (contents shift -p, placement shifts +R·p), and
                       the **3D face/edge picking** geometry: `pick()`
                       ray-hits the front-most projected triangle,
                       `describe_pick()` grows the coplanar face and
                       snaps to a boundary edge within tolerance.
  - `mates.py`       — **attach/snap**: a mate is a live record on the
                       child Object's params (`parent`, two anchor
                       names, `offset` mm along the axis, `spin` deg
                       about it) solved by `solve_mate()` into the
                       ordinary placement params — anchors coincide,
                       directions anti-aligned (BOSL2 attach() model,
                       no constraint solver). `refresh(model)` re-solves
                       every mate in dependency order (cycle-guarded;
                       called from `MainWindow._model_edited`) so
                       chains follow a moved parent; `AttachDialog` is
                       the context-menu UI. Renames propagate
                       (`DocumentModel.rename`), drags detach, and
                       dropping a part outline in the assembly view
                       snaps anchor-to-anchor (`_anchor_snap`).
  - `treepanel.py`   — `BuilderPanel`: Main tab (assembly) tree — **no visibility
                       checkboxes**: hidden objects read greyed + italic
                       and toggle with **Space** or right-click Hide/Show;
                       hiding a node **dims its whole subtree** (effective
                       visibility walks model ancestors) and only the
                       explicitly-hidden row shows a "(hidden)" tag
                       (painted by `_RowDelegate`, so the item text stays
                       clean for renaming). Connecting **guide lines**
                       (custom `drawBranches`) and a tight indent keep
                       deep trees readable. One row per node — colour and
                       transform wrappers show as their own rows so the
                       whole structure is visible.
                       `node_of` is the geometry (selection/properties);
                       `_root_of` is the chain root (delete/drag/duplicate
                       move the whole part); right-click **Modifiers**
                       jumps to a wrapped modifier's properties.
                       Context menu: hide/show, Apply operation, group/
                       ungroup, rename, duplicate, delete, **Make
                       Object**, **Make Master**, and for a single
                       Object: Edit in Object tab (also double-click),
                       Anchors (add-by-pick / set origin / remove) and
                       Attach/Detach; drag & drop reparent/reorder.
                       Tab order: **Main | Object | Masters | Variables
                       | Code**. The **Variables** sheet is scoped
                       (Global vs per-Object, following the active
                       Object); the Code tab — an editable OpenSCAD view
                       with syntax highlighting, a **line-number
                       gutter**, a text-editor toolbar (undo/redo,
                       cut/copy/paste, indent/dedent) and Tab/Shift+Tab
                       indentation — has a scope combo (**Whole program
                       / Active object**); edits apply back to the tree
                       via **Apply code** (object scope swaps just that
                       Object and writes edited globals back by name).
  - `properties.py`  — bottom-left panel; editors generated from each
                       node type's schema, polygon points table.
  - `view2d.py`      — top-right sketch view: Y-up QGraphicsScene,
                       draw tools (line/rect/circle/polygon/text),
                       select/move, resize handles, grid + snap, zoom.
                       Doubles as the **assembly view**: pick a plane
                       (Top XY / Front XZ / Side YZ) and every
                       top-level 3D part shows as a draggable
                       projected outline; dropping commits into a
                       translate node ("Position (...)"). Everything
                       reads in mm: scale bar, live size while
                       drawing, zoom indicator, Fit Sketch / Zoom to
                       Selection. Middle-mouse drag pans; wheel zooms.
  - `view3d.py`      — bottom-right preview: software-rendered shaded
                       mesh viewer (orbit/pan/zoom, painter's algo,
                       no OpenGL dependency); render styles (shaded,
                       brushed metal with specular, matte, wireframe,
                       x-ray) selectable in View > 3D Render Style and
                       persisted via QSettings. Backface-culls, hoists
                       the projection constants out of the per-vertex
                       loop, and — past `DRAFT_ABOVE` triangles — draws a
                       decimated **draft mesh while orbiting/zooming**
                       (OpenSCAD's preview/render split on the CPU),
                       snapping back to the full mesh on release/idle.
                       Draws the selected Object's **anchor markers**
                       (colour-coded per kind) and has a **pick mode**
                       (`start_pick`) where a left click hits a face or
                       edge via `anchors.pick`/`describe_pick`.
  - `mesh.py`        — pure-Python fallback tessellator (primitives,
                       linear/rotate extrude with twist/scale/angle,
                       transforms, ear-clipping triangulation). Objects
                       get a **two-level mesh cache** (`_component_mesh`):
                       the local tessellation keyed by subtree content +
                       env + $fn + mesh mtimes, and the placed world
                       mesh keyed by placement + colour — dragging one
                       part re-transforms only that part (~11x faster on
                       a 12-part assembly, ~25x when nothing changed).
                       Objects containing Linked copies skip the cache;
                       selection passes bypass it.
  - `engine.py`      — OpenSCAD integration: binary discovery,
                       debounced background renders via QProcess,
                       STL parse (binary + ASCII) and STL write.
- `tests/` — pytest suite (offscreen Qt; run `python -m pytest tests/`).
- `requirements.txt`, `LICENSE` (GPL-3.0).

## Architecture

**The tree is the single source of truth.** Node categories:

- 2D shapes (`line`, `rect`, `circle`, `polygon`, `text`) — `line`
  compiles to `hull()` of two circles so it is a real extrudable
  solid; `circle` has an `angle` param (90 = quarter, 180 = semi)
  that compiles to a polygon fan when partial.
- 3D primitives (`cube`, `sphere`, `cylinder`) and `stl_import`.
- Operations wrap their children (`linear_extrude`,
  `rotate_extrude`, `translate`, `rotate`, `scale`, `mirror`,
  `offset` for corner rounding).
- Booleans/grouping (`union` = group, `difference`, `intersection`,
  `hull`, `minkowski`; `round_edges()` = minkowski + small sphere,
  the post-extrusion rounding idiom).
- `component` ("Object") — a group that compiles to its own OpenSCAD
  module + placed call; the unit of the Main/Object tabs, anchors and
  mates (see `objecttab.py`/`anchors.py`/`mates.py` above). Imported
  meshes arrive wrapped in one.
- `scad_raw` — a leaf holding **verbatim OpenSCAD** (`code` param,
  multi-line `text` editor). Emitted straight into the program, so
  library calls the built-in tessellator can't model (BOSL2, ...) still
  render **through the OpenSCAD engine**; the built-in preview shows
  nothing for it (`mesh._tess` returns `[]`). Hidden ⇒ emits nothing
  (raw code can't take the `*` modifier). Insert via Insert > OpenSCAD
  code.
- Control flow (`for_loop`, `while_loop`, `if_else`, `assign`).
  `while` has no OpenSCAD equivalent, so codegen unrolls it into a
  value-list `for` (capped at 1000 iterations); it re-imports as a
  list-form for loop. `if_else` keeps its else branch in a child
  union named "Else" (auto-created).
- Organisational groups: `variables` (leading assignments, transparent
  in codegen) and `masters` (a **definitions store**). A `masters`
  group holds reusable **masters**; it renders **no geometry of its own**
  (skipped in `emit()` and `mesh._tess()`) but is still walked to index
  its masters as reference targets. Masters appear in their own Masters
  tab, not the Objects tree. A `reference` ("Linked copy") inlines a
  master's geometry by name (its own move/rotate applied), so editing a
  master updates every copy. `make_master()` promotes a scene object
  into the store and leaves a Linked copy behind; `instance_master()`
  drops a copy into the scene.

Hidden objects are emitted with OpenSCAD's `*` disable modifier, so
visibility round-trips through the generated program. New node types
go into `model.NODE_TYPES` (params, schema, icon, codegen branch in
`_statement()`, tessellation branch in `mesh.tessellate()`); the
properties panel and tree pick them up automatically.

**Selection** is coordinated by `MainWindow` (`_syncing` guard):
tree <-> 2D view <-> properties always show the same objects, the
Code tab highlights the selected object's lines (codegen emits
per-node line spans via `CadNode.emit()` / `to_scad_map()`), and the
selected object's **geometry** is highlighted in amber in both
viewers — `mesh.selected_world_tris()` tags the selected subtree's
world-space triangles (ancestor transforms applied), which the 3D
view draws glowing over the model and the 2D view projects to an
accent outline in the current plane (works at any tree depth).

**Errors turn red.** `model.validate()` runs on every change (bad
expressions, empty extrusions, 3D inside extrude, axis-crossing
revolve, non-terminating while, missing STL, ...) and OpenSCAD
compiler errors are mapped back to nodes through the line spans;
broken nodes are painted red in the tree (tooltip = message) and
their lines tinted red in the code.

**Clipboard**: Ctrl+X/C/V on the tree (and the 2D view) cut/copy/
paste subtrees as JSON via the system clipboard — works across app
instances. Ctrl+Up/Down reorders within the parent; arrow keys walk
the tree.

**Opening files**: `MainWindow.open_any(path)` routes by extension —
`.kcad` opens, `.scad` imports (as objects or a raw block), and a mesh
(`.stl`/`.obj`/`.off`/`.3mf`, `engine.MESH_EXTS`) imports as an
`stl_import` node. `engine.parse_mesh()` dispatches by extension to STL
(binary/ASCII), OBJ, OFF and 3MF (zip+XML) parsers for the built-in
preview; the OpenSCAD engine's `import()` renders STL/OFF/3MF directly,
while **OBJ is converted to a sibling `<stem>_from_obj.stl`** on import
(OpenSCAD can't read OBJ) so the exact render works too. File > Open and
**dragging** a file onto the window (or the Objects tree, which forwards
it) open/import it; imported files land in Open Recent.

**Render pipeline**: any model change re-tessellates instantly
(built-in preview) and schedules a debounced exact OpenSCAD render
that replaces the preview when it lands.

## Document format

`.kcad` is JSON: `{"format": "kcad", "version": 1, "tree": {...}}`
where each node dict has `"type"`, `"name"`, `"visible"`, `"params"`
and nested `"children"`. When a node gains new persisted properties,
bump `FORMAT_VERSION` in `document.py` and keep loading backward
compatible.

## UI conventions

- Left column: Objects/Code tabs on top, Properties below. Right
  column: 2D sketch view on top, 3D preview below.
- Vertical toolbar = shape tools (exclusive checkable group) + 3D
  primitives; horizontal toolbar = file ops, operations applied to
  the selection, grid/snap, Render (F5), Fit 3D.
- Status bar: cursor position in sketch coordinates + engine badge
  (OpenSCAD found / built-in preview).
- **Window style**: Fusion as default; themes shared with the family
  (View > Theme).

## Roadmap

- Undo/redo on a shared `QUndoStack` (node add/remove/move/param
  changes), mirroring KherveSheet's `undo_commands.py`.
- OpenSCAD `$fn`/`$fa`/`$fs` global settings panel.
- DXF reference geometry import; STEP export via external tools.
- Dimensions/constraints in the 2D sketch; edge snapping.
- Per-object color/material; section view in the 3D preview.
- Chat: streaming responses, image input (screenshot the 3D view),
  more library parts on request (gate valves, viewports, bellows).

## Undo / redo

Undo is **whole-document snapshots** on `DocumentModel.undo_stack`
(QUndoStack): every `structure_changed`/`node_changed` schedules a
capture on a 0 ms owned timer (one step per event-loop cycle), and
consecutive captures within `UNDO_MERGE_S` merge, so drags and
spinbox scrubs stay one Ctrl+Z. Restores go through
`restore_state()` with the `_restoring` guard. New mutations are
automatically undoable — nothing to register.

## Colors

Per-object colour is OpenSCAD's own `color()` node (picker in the
tree context menu and properties). The **built-in preview renders
per-face colours** (`mesh.tessellate_colored`); engine STL is
geometry-only, so the exact-render swap pauses while the document
is coloured (F5 still forces it).

## Persistence policy

**All node properties must round-trip through `.kcad`.** When adding
a property, keep `node_to_dict()`/`node_from_dict()` in
`document.py` symmetric and extend the round-trip test in `tests/`.

## Commit / push policy

**Every change must land as a commit and be pushed immediately.**
No batching. No exceptions. No `Co-Authored-By:` trailer.

Commit subjects under 70 chars; body explains *why*, not what.

**Commit message prefix** — every subject line must start with one of:

- `fix:` — bug fix
- `feat:` — new feature or option
- `refactor:` — code restructuring, no behavior change
- `style:` — formatting, UI tweaks
- `docs:` — documentation only
- `perf:` — performance improvement

## Licensing

GPL-3.0. New source files must carry the short GPL notice at the top.
