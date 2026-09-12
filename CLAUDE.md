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
                       the document globals **plus the modules of every
                       Object it instances** — `_referenced_modules()`
                       + `emit_module()` (definition only, no placed
                       call): an instance emits a bare `Part();` and
                       OpenSCAD renders *nothing* for a module it can't
                       find, so those parts used to vanish from the
                       isolated exact render), so the program reads as
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
                       **Comments name nodes**: a trailing `// Body`
                       labels the innermost statement starting on that
                       line, and a lone comment line directly above
                       labels the next statement (comment blocks, long
                       prose and commented-out code don't), giving
                       "Cube [Body]" (`model.name_tag`/`with_tag`).
                       Codegen writes the label back as a trailing
                       comment, so it round-trips; the chat prompt and
                       MCP instructions ask assistants to label every
                       part this way.
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
                       are for-loops. The dialog **inserts each part as
                       a single visible Object** (`enclose_as_part`), so
                       it lists as one opaque row in Main and its
                       construction is edited in the Object tab. The
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
  - `library_lego.py`— **Lego**: bricks, plates, tiles, 45° slopes and
                       baseplates at the real dimensions (8 mm pitch,
                       9.6 mm brick, 3.2 mm plate, 0.1 mm clearance a
                       side — the same as the hand-built
                       `lego_bricks.kcad`) in the official colours
                       (`COLORS`; clear ones get the Glass material, the
                       strongly tinted `VIVID` ones a denser alpha — at
                       glass opacity a flame read pastel pink). Slopes
                       face all four ways: the ±X ones are the ±Y piece
                       turned a quarter, stud indices mirrored. Library
                       parts pass `round_=True`: rounded vertical
                       corners (quarter-round posts, walls shortened),
                       a bevelled top edge (`_slab`, the hull of the
                       rounded footprint and an inset top face — convex,
                       so exact in the preview) and bevelled studs; the
                       brick-built models stay sharp for their triangle
                       budget.
                       Boolean-free: the hollow underside is walls + top,
                       tubes are revolved rings, a slope is an extruded
                       profile. Origin at the part's grid corner, not
                       its centre, so bricks snap stud to stud on an
                       8 mm grid. A spec may carry `colors`: the Part
                       Library dialog then shows a colour combo and
                       `insert_part` takes `color` (passed to the
                       builder as `dims["_color"]`); `COUNT_FIELDS`
                       get integer spin boxes.
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
  - `examples_lego.py` — the **Lego** category (Minecraft tower, house,
                       church, apartment building, dragon, Steve-style
                       man, Alex-style woman), built from `library_lego`
                       bricks. `gable_roof` lays slope courses + ridge
                       tiles (house, church); `blob`/`sweep`/`box_mm`
                       sculpt curved shapes in millimetres (every cell
                       whose centre falls inside becomes a voxel — the
                       dragon's body, neck, tail, head); floors seen
                       through glass and pavements are `kind="tile"`
                       voxels, whose absent studs keep the building
                       light. The figures are at ONE
                       stud per Minecraft pixel (8x8x8 head, 8x4x12
                       body, ~31 cm tall, the face 8x8 bricks of pixel
                       art painted by `_paint`); the first 2-pixels-a-
                       stud versions stay as "small" — at 4x4 bricks a
                       face was too coarse. A model is sketched as
                       voxels `{(i, j, k): (colour, group)}`; `pack()`
                       covers each layer with standard bricks (2x8 ..
                       1x1, one colour each), the long axis alternating
                       by layer so joints do not stack; a colour tuple
                       packs as one material and each brick draws one
                       name (seeded: cobblestone, leaves). Slopes, tiles
                       and plates are added directly. `Scene.to_node`
                       drops studs another piece covers and the hidden
                       undersides, which is what keeps a 171-piece tower
                       at 17k triangles.
  - `library_lego_sets.py` — the **Lego sets** category: every Lego
                       example as a library part (`sizes={}`), built by
                       the example's own function and lifted out of its
                       root, so a set drops into an assembly as one
                       Object. `examples` is imported lazily (it imports
                       the library).
  - `legoize.py`     — **Object ↔ Lego** (Qt-free). `column_hits` casts
                       a ray up each grid column and records every
                       surface as an entry (+1, facing down) or an exit
                       (-1); `_intervals` counts **winding**, not parity
                       (a brick's top and the bottom of the one on it
                       share a height — dropping one as a duplicate once
                       painted a house's walls baseplate-green), and a
                       cell takes the colour of the last solid entered
                       below it. `to_lego` scales the part to N studs
                       across (bricks or plates a layer), matches
                       colours to the palette (`nearest_colour`) and
                       packs with `examples_lego.Scene`; `to_solid`
                       voxelizes a brick build at plate resolution
                       (`COVER` 75% so studs drop out, `HOLLOW` closes a
                       brick's underside) and merges cells into boxes
                       per colour (`boxes`). `MAX_CELLS` caps it.
  - `lego_convert.py`— Library ▸ Convert Selection to Lego… (dialog:
                       studs across, bricks/plates, colours) and Fuse
                       Lego into One Solid; also on the tree's right
                       click. The result is a new Object beside the
                       source, which is never touched.
  - `lego_builder.py`— Library ▸ **Lego Builder…**: a non-modal panel
                       (piece, studs, colour, turn, Place/Erase) that
                       keeps `view3d.start_pick` armed on the build's
                       pieces. A piece is a Group at its grid corner
                       with `params["lego"]` = {kind, nx, ny, h, colour,
                       bare}; `target` drops a new piece onto the
                       highest top under its footprint (a top click,
                       stud sides included) or sets it beside a side
                       face; `refresh_studs` rebuilds only pieces whose
                       uncovered studs changed. Picks carry the raw
                       `point` and face `normal` (`View3D._pick_at`).
  - `chat.py`        — **Assistant chat box** (family assistant, docked
                       right, **hidden by default**, opened from AI ▸ ChatBox or
                       Ctrl+/): Claude/Mistral/Ollama
                       Cloud via urllib, keys in QSettings or env vars,
                       slash commands, and `scad` reply blocks applied to
                       the tree via scadparse. The reply lands in the
                       scope the user is working in (`active_object()`):
                       **inside the Object** while the Object tab is
                       open, so the part's construction shows step by
                       step in the Object tree, else in the document.
                       Every message states the mode and ships that
                       scope's program (`_scope_context`); a
                       module-plus-call answer is unwrapped
                       (`_object_contents`) or the part would nest
                       inside itself.
  - `git_backend.py` — **per-document Git** (pygit2, ported from the
                       Kherve family): init/commit/push/pull, remotes and
                       history for the folder holding the current
                       `.kcad`. Degrades to no-ops if pygit2 is absent.
                       Wired to the **Git menu** (Commit Ctrl+K, Push,
                       Pull, Connect to GitHub); the status bar shows the
                       current file path, File > Show in File Explorer
                       reveals it.
  - `objecttab.py`   — the **Object tab**, where parts are **defined**
                       and edited (the part/assembly split — anchors and
                       mates are a Main-tab concern, not here):
                       `ObjectTab` (dropdown of the document's Objects +
                       "New", Rename, and **To Main** = insert an
                       instance into the assembly) and `ComponentTree`
                       (the same tree widget rooted at the **active
                       Object**; `SHOWS_INSERT_OBJECT = False`, since an
                       instance belongs to the assembly, not inside a
                       definition). The active Object is tracked by node
                       id with a name fallback so it survives renames
                       AND undo restores (which rebuild the tree with
                       fresh ids). While the Object tab is current,
                       `BuilderPanel.isolated_component()` is non-None
                       and **both viewers isolate to that Object**
                       (scene `isolation_resolver`, `_render_scope()` in
                       the main window); drawn shapes and Insert-menu
                       primitives land inside it. New Objects are
                       created hidden, so they stay definitions until an
                       instance places them in Main. The Object is shown
                       in its **own local frame** — `subtree_scad` and
                       `MainWindow._isolated_frame` zero its Main
                       placement (`x/y/z/rx/ry/rz`, set by an assembly
                       mate) and force it visible, so a part mated high
                       up in the assembly still edits at its own origin.
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
                       child part's params (`parent`, two anchor
                       names, `offset` mm along the axis, `spin` deg
                       about it) solved by `solve_mate()` into the
                       ordinary placement params — anchors coincide,
                       directions anti-aligned (BOSL2 attach() model,
                       no constraint solver). The record may carry the
                       other common mates, all still deterministic:
                       `align` "same" (flush), `kind` "concentric" (the
                       part slides along the axis — `slide_to` measures
                       a 2D drag along it and keeps the mate instead of
                       detaching) or "angle" (a hinge: `angle` deg about
                       `hinge_axis`, the anchor's horizontal edge),
                       `ratio` (gear: spin = -ratio x the parent mate's
                       spin, absolute) and `min`/`max` (limit:
                       `clamp_offset`). `attach()` stores only the
                       non-default extras, so a plain mate reads as
                       before. A mate's parent is a
                       **sibling** (`_mate_siblings`): at the assembly
                       root an Object mates to another Object; inside an
                       Object a **group mates to a sibling group** (the
                       "secondary" anchors that build a part). `parts(
                       model, scope)` enumerates the mateable parts —
                       Objects+instances when `scope is None`, the
                       the Object's own sub-parts when `scope` is that
                       Object — every child that renders geometry, not
                       just groups (a part built from library Objects
                       holds nothing but **instances**; one built by
                       Make Object is a single group holding **Moves**,
                       and `_object_parts` looks inside that lone body
                       group). Whatever moves must be able to hold a
                       mate, so `ensure_part()` wraps a Move (which
                       emits `translate([x,y,z])` and would drop the
                       rotation) in a Group first. A **colour wrapper is
                       seen through**
                       (`unwrap`) on both paths — colouring a part used
                       to drop it out of the assembly entirely; a
                       transform wrapper is deliberately not, since the
                       mate would solve as if it were absent.
                       `refresh(model)`
                       re-solves every mated node at any depth in
                       dependency order (cycle-guarded; called from
                       `MainWindow._model_edited`) so chains follow a
                       moved parent; `AttachDialog` is the context-menu
                       UI. Renames propagate
                       (`DocumentModel.rename`), drags detach, typing a
                       placement (x/y/z/rx/ry/rz) in Properties detaches
                       too (`set_param` — the mate would re-solve over
                       the typed value; `mate_released` reports it in
                       the status bar), and
                       dropping a part outline in the assembly view
                       snaps anchor-to-anchor (`_anchor_snap`). The
                       **two-click Snap tool** (toolbar magnet, J, or
                       "Snap by clicking faces") is the Fusion-joint
                       front end: click a face/edge on the Object to
                       move, then the target face on another — the
                       face/edge under the cursor **pre-highlights**
                       while aiming, labelled with the anchor a click
                       would reuse ("Base · Top" — `_snap_labeler`,
                       anchor lists cached per part), the first click
                       stays pinned in orange, each step shows as a
                       banner across the 3D view, and Esc cancels.
                       Completing the snap opens **`SnapTweakPopup`**
                       (non-modal: offset/spin applied live, Flip
                       180°, Detach) so the final nudge needs no
                       context menu. `AttachDialog` **previews live**
                       (every change applies at once; Cancel restores
                       the original mate and placement) and has the
                       same Flip 180° —
                       `MainWindow._start_snap` picks per-Object mesh
                       groups (`view3d.start_pick(..., groups=...)`),
                       `_anchor_for_pick` reuses a matching bbox/user
                       anchor (never litters duplicates) or persists a
                       custom one on the part's **definition** (shared
                       by every instance), and the mate solves
                       immediately. Assembly anchors mate whole Objects
                       in the **Main tab**; **secondary anchors** in the
                       **Object tab** snap the `union` groups that build
                       an Object to each other (`_snap_scope` =
                       `isolated_component()`, stored on the group). An
                       Object shows as **one opaque row** in Main
                       (`ObjectTree._is_opaque`); its construction tree
                       lives in the Object tab, whose visibility walk
                       stops at the active Object (`_visibility_root`)
                       so a definition's hidden-in-Main flag doesn't
                       grey its contents.
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
                       whole structure is visible. A **placed part**
                       (Object, instance, or mated group) additionally
                       shows synthetic **Position/Rotation/Color child
                       rows** mirroring the params it carries — the
                       translate/rotate a snap, drag or Properties edit
                       wrote, so the tree matches the
                       `translate(...) rotate(...)` the code emits, and
                       its own colour (with a painted swatch as the
                       icon, `_swatch_icon`, and the opacity when
                       translucent). They carry `ROLE_PLACEMENT`,
                       share the part's node id (clicking selects the
                       part), are read-only/undraggable, refresh live
                       on every mate re-solve, and their tooltip names
                       the mate parent.
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
  - `toolbars.py`    — both toolbars and their tool tables (`TOOLS`,
                       `PRIMITIVES`, `OPERATION_GROUPS`). The twenty
                       operations sit in six **`GroupButton`** families
                       (Extrude, Move & transform, Combine, Deform &
                       sculpt, Character, Repeat & logic): a click runs
                       the family's last-used tool (QSettings
                       `toolbar/<family>`), the chevron opens the rest.
                       A shortcut a menu already owns is shown in the
                       tip but not bound (`bind=False`) — two actions on
                       one key make Qt fire neither.
  - `userguide.py`   — Help ▸ User Guide (F1, non-modal): chapter
                       list + search + one HTML document. Screenshots
                       come from `khervecad/help/*.png` via `figure()`
                       (a missing one is dropped, and
                       `test_userguide` fails on it); the **Tool
                       reference** chapter is generated from
                       `tooltips.TIPS` with each tool's real icon, so
                       manual and tooltips cannot drift.
  - `userguide_content.py` — the 22 chapters, `(anchor, title, html)`.
                       After a UI change re-run
                       `packaging/make_help_screenshots.py`: it drives
                       the real window offscreen, stages each scene
                       (the plate-with-a-hole tutorial, every tab, the
                       dialogs, render styles) and paints numbered
                       call-outs. The help folder ships via the spec's
                       `datas`. Never screenshot the Connect-to-Claude
                       dialog — its config snippet shows local paths.
  - `viewnav.py`     — the floating **navigation bars** in the top-right
                       corner of the 2D sketch and the 3D preview: pan
                       arrows and zoom (auto-repeat while held),
                       **Focus** (frame the selection — the 3D one uses
                       `View3D.highlight_mesh` — else everything) and Fit
                       all; the 3D bar also orbits. Children of the
                       views placed by an event filter, attached once by
                       `MainWindow` (`attach_2d`/`attach_3d`, stored as
                       `view.nav_bar`); pick mode hides the 3D one like
                       the lighting bar. Snapshot twins get none.
  - `tooltips.py`    — what every toolbar icon does and how to use it:
                       `TIPS[key] = (title, what, steps, tip)`, rendered
                       by `rich()` as a fixed-width HTML tooltip and by
                       `summary()` as the status-bar line. A new tool
                       with no entry falls back to its node label.
  - `view2d.py`      — top-right sketch view: Y-up QGraphicsScene,
                       draw tools (line/rect/circle/polygon/text),
                       select/move, resize handles, grid + snap, zoom.
                       Doubles as the **assembly view**: pick a plane
                       (Top XY / Front XZ / Side YZ) and every
                       top-level 3D part shows as a draggable
                       projected outline — its **real** silhouette
                       (`_projected_path`, a winding-fill union of the
                       projected triangles at `OUTLINE_DETAIL`), not a
                       convex hull, so a cross tube reads as a cross
                       and the 2D view matches the 3D one. A soup path
                       is **filled, never stroked** — a pen traces
                       every internal facet and the part reads as
                       hatching (`PartItem`); dropping
                       commits into a
                       translate node ("Position (...)"). A **selected
                       part is draggable at any depth** when it carries
                       its own position (`MOVABLE_TYPES`: Move/Group/
                       Object/instance) — highlight a Move and drag it
                       in the plane; the world delta is mapped into the
                       node's own frame (`_local_move`, the inverse of
                       the ancestor chain's linear part) so a Move under
                       a rotated group follows the cursor instead of
                       shooting off sideways. Drawing and mapping share
                       ONE frame: `scope_frame()` force-shows the active
                       Object (a definition is hidden, and tessellating
                       a hidden node falls back to drawing the selection
                       with no ancestor transforms at all) with its
                       assembly placement zeroed, and `_world_matrix`
                       stops at the same scope root — when the two
                       disagreed, dragging left moved the part right. The drop is committed on
                       the **next event-loop turn** (`queue_commit`):
                       committing rebuilds the scene, and deleting the
                       item mid-release crashed the process
                       (0xC0000409). Dragging a mated part detaches it.
                       The plane's two axes are named and
                       colour-coded with the **3D gizmo's colours**
                       (`AXIS_COLORS`: X red, Y green, Z blue) — tinted
                       axis lines, corner letters, and a labelled arrow
                       gizmo at the origin (`_draw_origin_gizmo`, screen
                       space, skipped when the origin is off view).
                       Everything
                       reads in mm: scale bar, live size while
                       drawing, zoom indicator, Fit Sketch / Zoom to
                       Selection. Middle-mouse drag pans; wheel zooms.
  - `bsp.py`         — **BSP tree** for the 3D preview's painter's
                       algorithm: built once per mesh (on a worker
                       thread, see `View3D.set_mesh`), it splits
                       straddling triangles and `Tree.order()` walks
                       them back-to-front from any eye — exact, where a
                       centroid sort painted a big face over a small
                       feature 1 mm in front of it (a pupil vanished into
                       a head). Splitters are facet planes, or an
                       axis-median plane when facets balance badly
                       (convex bodies would chain O(n²)). `build()`
                       returns None past `MAX_TRIS`, the time budget or
                       the growth cap (curved petals shred) and the view
                       falls back to the centroid sort. Past
                       `SMALL_MESH` (12k) a mesh up to `MAX_TRIS` (40k)
                       gets a tree only if it grows by `BIG_GROWTH`
                       (2.5x) at most: block models (a 28k-triangle Lego
                       house splits 1.2x, 0.7 s) get the exact order,
                       threads give up in well under a second — the
                       centroid sort let a baseplate's one big face
                       paint over the studs in front of it. The budget is
                       the worker's **CPU** time (`time.thread_time`):
                       a wall-clock budget ran out while the GUI thread
                       held the GIL, so the exact order only ever landed
                       after a manual Redraw. A newer mesh `cancel`s a
                       stale build, and only the current serial's tree
                       may be posted to the view.
  - `glrender.py`    — **OpenGL faces** for the 3D preview: one
                       offscreen 2.1-compatibility context (GLSL 1.20,
                       `QOpenGLFunctions_2_1` via `versionFunctions` —
                       no PyOpenGL), a 4x multisampled FBO with a depth
                       buffer, the mesh packed once per (mesh, style,
                       cavity) into an interleaved VBO (`STRIDE` floats:
                       position, normal, rgb, alpha, material params,
                       cavity), a shader reproducing `_style_color`'s
                       lighting (`material()`), translucent faces in a
                       second back-to-front pass with depth writes off,
                       crease lines in a line VBO under `glPolygonOffset`
                       (no clip-space bias: 0.0005 at the far end of a
                       perspective depth buffer was ~200 mm). Blending is
                       `glBlendFuncSeparate(SRC_ALPHA, 1-SRC_ALPHA, ONE,
                       1-SRC_ALPHA)` because `toImage()` is premultiplied
                       — the plain blend gave glass alpha a² and painted
                       as saturated noise. The projection reproduces
                       `View3D._project` exactly so the image lines up
                       with the QPainter overlays. `render()` returns a
                       QImage or None; any failure sets `ok=False` and
                       the view falls back to the painter for good.
  - `view3d.py`      — bottom-right preview: `View3D.hardware` (View ▸
                       3D Hardware Rendering, QSettings `render_gl`,
                       MCP `set_render_options opengl`, default on) lays
                       `glrender`'s image under the overlays at the top
                       of the face pass (`_gl_drew`; the painter loop
                       then only collects the selection outline); the
                       BSP tree is built only when the painter will need
                       it (`_gl_active()`, `_start_bsp_build`). Otherwise
                       software-rendered shaded
                       mesh viewer (orbit/pan/zoom, painter's algo in
                       BSP order via `bsp.py` — centroid sort only for
                       the interaction draft and meshes too big to
                       partition; no OpenGL dependency); render styles (shaded,
                       brushed metal with specular, matte, wireframe,
                       x-ray) selectable in View > 3D Render Style and
                       persisted via QSettings. A floating **`LightingBar`**
                       (top-left of the frame, hidden during a pick)
                       carries **brightness / contrast** sliders that
                       adjust the finished face colours only — value
                       offset + gain about mid-grey (`_light()` returns
                       None when centred, so the per-face hot path pays
                       nothing), also persisted, plus a **Redraw**
                       button (`refresh_requested` ->
                       `MainWindow.force_refresh`: drop the mesh caches
                       and rebuild both views). Backface-culls, hoists
                       the projection constants out of the per-vertex
                       loop, and — past `DRAFT_ABOVE` triangles — draws a
                       decimated **draft mesh while orbiting/zooming**
                       (OpenSCAD's preview/render split on the CPU),
                       snapping back to the full mesh on release/idle.
                       Draws the selected Object's **anchor markers**
                       (colour-coded per kind) and has a **pick mode**
                       (`start_pick`) where a left click hits a face or
                       edge via `anchors.pick`/`describe_pick`
                       (`describe_pick` returns the grown face's
                       triangles / the edge run, which pick mode uses
                       to pre-highlight the target under the cursor —
                       throttled, with a facet-only fallback past
                       `HOVER_DESCRIBE_LIMIT`); an instruction banner,
                       a pinned first-pick marker
                       (`set_pick_pinned`) and Esc-to-cancel complete
                       the pick-mode feedback. With `stage` on (View ▸
                       3D Platform & Shadow, QSettings `render_stage`,
                       MCP `set_render_options stage`) `_draw_stage`
                       paints `stage.py`'s platform + shadow instead of
                       the grid, a whole-model `fit()` frames the
                       platform too, and `snapshot()` copies it.
  - `stage.py`       — the **platform & shadow** stage (Qt only, no
                       view import at module level): a round slab whose
                       top is the mesh's lowest Z, centred under the XY
                       bbox (radius 0.7 x diagonal, more for a tall
                       model so its shadow lands on it), coloured to
                       suit the background, and a soft shadow from a
                       light **tied to the camera** — up, to the
                       viewer's left, a little behind (`light_dir`) —
                       so it always falls bottom-right on screen. Drawn
                       before the model and never depth-sorted against
                       it (the model stands inside the disc, on top);
                       skipped from below the plane. Cheap: the shadow
                       is cast from a **vertex-clustered** copy (≤
                       `SHADOW_TARGET` tris, closed, so no holes —
                       unlike the strided draft), light-facing faces
                       projected in ground coords into ONE winding-fill
                       path cached per yaw; a projective `QTransform`
                       (Qt near-clips) maps it to a low-res mask that
                       is box-blurred and scaled up smoothly. ~2-7 ms a
                       frame on a 36k-triangle model whose own paint is
                       ~115 ms.
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
  - `printables.py`  — **File ▸ Publish to Printables…** and the
                       `publish_to_printables` MCP tool share one
                       builder: STL / 3MF / .scad / .kcad exports,
                       preview stills of **every side** — `STILL_VIEWS`
                       (mcp_schema): front-right isometric, back-left
                       isometric, front, back, left, right, top,
                       bottom, all by default — the front-right
                       isometric first and larger since Printables
                       makes the first image the cover. OpenSCAD
                       renders them (`engine.export_png`); without it
                       the built-in renderer does (`pngexport.render`,
                       an offscreen snapshot, never the user's camera).
                       Both aim from ONE table, `engine.CAMERA_ROTATIONS`
                       (`engine.view_angles`: yaw = rz - 90, pitch =
                       90 - rx). The fallback used to aim with
                       `View3D.VIEWS`, whose "Isometric" (35, 25) looked
                       from the BACK-right while OpenSCAD's (55,0,25)
                       looks from the front-right, so a bundle built
                       without OpenSCAD led with the back of the model;
                       the preset is now (-65, 35) and a test pins the
                       two tables together. Each still is **cropped to
                       the model** by `trim_to_content` (`--viewall`
                       frames the bounding *sphere*, so a long diagonal
                       part renders correct and tiny); a generated or
                       assistant-written **plain-text**
                       `description.txt` (Markdown pasted into
                       Printables' box reads back as literal hashes),
                       `upload-form.txt` — every field of the
                       add-a-model form (name, the 120-char summary,
                       main category, tags, origin, licence,
                       overridable print settings) already answered,
                       none of them left as a note telling the author
                       to fill it in (`opening()` writes the first
                       paragraph from the model's own size, structure
                       and named dimensions) — and
                       `printables.json`, and `<stem>-source.zip`
                       holding whichever of the .scad, .kcad and .3mf
                       were written (one download for a remixer).
                       Printables has **no upload
                       API** — this prepares the folder and opens the
                       upload page; the user does the last click, and
                       the tool result says `published: false` so an
                       assistant cannot claim otherwise. The credit
                       block naming KherveCAD / khervetools.com /
                       Claude is appended to whatever description
                       comes in, once, and names only the source files
                       actually shipped.
  - `drawing.py`     — **2D engineering drawings** (Qt-free): `VIEWS`
                       (third-angle Front/Top/Right/…, an isometric)
                       as (right, up, forward); `view_lines` takes the
                       mesh's creases + borders + that view's
                       silhouette, dedupes edges that project onto the
                       same line (front-most wins), and finds hidden
                       runs with a `DepthGrid` — a pure-Python
                       z-buffer at `GRID` cells across the model —
                       sampling `SAMPLES` points per edge (one-sample
                       runs are grid flicker, folded away); `layout`
                       places the views in the third-angle arrangement
                       on an A4/A3/Letter sheet at the largest `SCALES`
                       entry that fits, with `overall_dimensions` and
                       an optional `section.section`. Hidden lines can
                       be left out (`hidden_lines`): a threaded part's
                       facets give tens of thousands of dashes.
  - `drawing_export.py` — paints a layout (dashed hidden lines,
                       arrowed dimensions, hatched section, title
                       block) through QPainter to PDF (`QPdfWriter`),
                       SVG (`QSvgGenerator`), PNG, and writes a minimal
                       DXF R12 by hand (LINE/TEXT on VISIBLE, HIDDEN,
                       DIM, SECTION, TEXT layers, sheet mm).
  - `drawing_dialog.py` — File ▸ Make Drawing… (Ctrl+Shift+D): title,
                       sheet, views, dimensions, hidden lines, section
                       axis, scale, a live preview; `make_layout` is
                       what the `export_drawing` MCP tool calls too
                       (the selection, else the render scope).
  - `pngexport.py`   — **File ▸ Export PNG…** (Ctrl+Alt+E): pictures
                       of the 3D view from the built-in renderer via
                       `View3D.snapshot(..., clean=True)` — the model
                       alone (no grid, axes, badge, selection tint or
                       anchors) in the user's colours, materials, style
                       and lighting, from an offscreen twin so the
                       user's camera never moves. **Current view**
                       keeps the on-screen camera exactly; **All
                       standard views** writes `<stem>-<n>-<view>.png`
                       per `STILL_VIEWS` entry, framed, cover first —
                       the same set and cameras as the Printables
                       stills (`printables` falls back to `render`).
                       Size presets up to 4K plus window size × 2 (the
                       on-screen framing); **transparent** is a
                       snapshot flag, not post-processing (skip the
                       background fill AND pass `render()` DrawChildren
                       only, or Qt paints the palette colour under it).
                       Last choices in QSettings `png_export/*`.
                       `export_request` is the `export_document` MCP
                       tool's `.png` branch (`view` current / a preset /
                       all, `width`, `height`, `transparent`).
  - `organic.py`     — **organic nodes** for characters: `capsule`,
                       `ellipsoid`, `rounded_box`, `symmetry` (its
                       children plus their mirror image — edit one
                       half) and `joint` (rotate children about a
                       pivot; joints nest, so the tree is the
                       armature — `set_pose` MCP tool). Each compiles
                       to ONE call of a `kcad_*` helper module whose
                       definition `preamble()` puts at the top of any
                       program using it (`to_scad_map`), so exported
                       .scad stays standalone OpenSCAD; `BUILDERS`
                       teach scadparse the `kcad_*` names, so import
                       rebuilds the same node (lossless, and an
                       assistant can write the calls directly). No
                       package imports at module level: registered
                       from the BOTTOM of model.py (`register()`
                       updates NODE_TYPES and CONTAINER_TYPES in
                       place).
  - `geom3d.py`     — 3D **convex hull** (quickhull with conflict
                       lists, Qt-free): the capsule and rounded box
                       are hulls of spheres, so they preview as
                       what they are.
  - `bake.py`        — **mesh nodes**, aggregated into the registry by
                       organic.py: `polyhedron` (OpenSCAD's own points +
                       faces; validation names the edge that is open or
                       wound the wrong way; faces are clockwise from
                       outside, reversed for the preview) and
                       `to_polyhedron()`, which welds counter-clockwise
                       triangles into OpenSCAD points/faces for the
                       nodes that bake a computed surface.
  - `loft.py`        — **loft** geometry (Qt-free): sections [x, y, z,
                       w, h] joined by a Catmull-Rom path, rings in a
                       rotation-minimising frame (no self-twist),
                       round or flat ends. The `loft` node (bake.py)
                       compiles to `kcad_loft(...)`, whose OpenSCAD
                       helper runs the SAME formulas at render time —
                       so loop variables/expressions work and nothing
                       is baked; this module is the preview's copy.
                       Keep the two in step (rounding: floor(x+0.5),
                       never Python's round-half-even); the engine
                       parity test compares extent and volume.
  - `sweep.py`       — **sweep along a path** geometry (Qt-free): any
                       2D outline(s) driven along a 3D polyline —
                       pipes, handrails, cable runs, springs, chain
                       links (Blender's curve + bevel object; OpenSCAD
                       has nothing native, the hull-chain idiom
                       convexifies). Catmull-Rom `densify` (given
                       points stay on the curve; closed loops wrap),
                       a rotation-minimising `frames` (double
                       reflection, holonomy spread round a closed
                       loop so the seam matches), mitred rings at
                       corners, `twist`/`scale` over the arc length,
                       `wall` > 0 hollows it (inner outline from
                       `mesh.offset_outline`, annulus caps — a pipe
                       without a 2D difference), `closed` drops the
                       caps. Profile axes follow linear_extrude: path
                       towards you, Z up → x right, y up. The `sweep`
                       node (bake.py, in `_BAKED`: `kcad_sweep(path=,
                       smooth=, twist=, scale=, wall=, closed=,
                       points=, faces=) { 2D profile }`) BAKES the
                       polyhedron like `blend`, so it is refused
                       inside a loop and its profile cannot hold a 2D
                       difference (use wall). Extrude toolbar group;
                       Examples ▸ Mechanical ▸ Pipe run & handrail.
  - `fillet.py`      — **fillet / chamfer chosen edges** (SolidWorks'
                       Fillet; Qt-free). `crease_edges` finds the
                       edges of the children's preview mesh where two
                       faces meet at > `MIN_ANGLE` (facets of a
                       cylinder are not edges), each convex or
                       concave; `chain` propagates a picked edge along
                       tangent-continuous creases (one click takes a
                       whole rim, stops at a box corner); `profile` is
                       the kite between the edge and the circle
                       tangent to both faces (chamfer: the setback
                       triangle); `strip` sweeps it along the chain,
                       mitred, capped. Convex chains become **cuts**,
                       concave **adds**, and codegen writes both as
                       polyhedra into `kcad_fillet(radius=, kind=,
                       detail=, edges=, cuts=, adds=) { children }`
                       whose helper does the boolean — so the exact
                       render and STL are truly filleted while the
                       preview shows children + adds (it cannot cut;
                       `fillet` is in `mesh.APPROXIMATED`). Edges are
                       stored as the seed segment's endpoints in the
                       part's LOCAL frame and re-found by nearest
                       match (`find_edge`); a vanished edge is a
                       validation error, never a guess. Registered
                       from bake.py (statement/build/check/tess
                       dispatch); baked and cached like blend, so it
                       is refused inside loops. Limitation: an edge
                       exists only where one shape has it — the
                       preview never merges a union, so two overlapping
                       boxes have no inside-corner edge (extrude an L
                       profile instead).
  - `fillet_pick.py` — the click flow: `start(window, node)` arms
                       `View3D.start_pick` on the fillet's part
                       (groups=[(node, world tris)]) and re-arms after
                       every click; a picked world edge/face maps to
                       the local frame by index (`meshes()` gives the
                       world and local tessellations in the same order,
                       `seeds_from_pick` turns an edge into one seed and
                       a face into every crease edge bounding it). The
                       toolbar's Fillet edges (Finish group) wraps the
                       selection and starts the pick; right-click ▸
                       Pick edges re-enters it. MCP: `list_edges`
                       (chains with seed/ends/length/convex/closed) and
                       `fillet_edges` (by seed rows or chain indices).
  - `shell.py`       — **shell / hollow** (Blender Solidify; Qt-free):
                       `inner_surface` moves every welded vertex inward
                       along its area-weighted normal by the wall
                       thickness with the even-thickness 1/cos stretch
                       (capped `MAX_STRETCH`), faces reversed; `shell`
                       adds it to the outer surface or, with `open`
                       (top/bottom/±x/±y within `open_angle`), drops
                       the faces looking that way from both and bridges
                       the rims — always one closed outward solid. A
                       folded inner surface (no room) returns the solid;
                       validation refuses `2·thickness ≥` the part's
                       smallest extent first. Baked like the other
                       `_BAKED` wrappers (`kcad_shell(thickness=, open=,
                       open_angle=, detail=, points=, faces=)`), in the
                       Deform & sculpt group; Examples ▸ Mechanical ▸
                       Hollow cup.
  - `shading.py`     — Blender-solid-view **cavity shading and edge
                       lines** (Qt-free): `analyse(tris)` → `MeshInfo`
                       with per-face normals, a signed `cavity` term
                       (edge-neighbours bending towards the normal =
                       valley, one ring smoothed), `creases` (edges
                       over `EDGE_ANGLE`, per owning face) and
                       `neighbours` for the per-frame `silhouette`.
                       View3D keeps it per mesh serial (`_mesh_info`),
                       the painter reaches it from a tree piece via
                       `bsp.Tree.parents`, applies the value multiplier
                       after the lighting sliders and strokes a face's
                       creases + silhouette right after its polygon
                       (occlusion without a depth buffer); skipped on
                       the orbit draft and in Wireframe/X-ray. View ▸
                       3D Cavity Shading / 3D Edge Lines
                       (`render_cavity`/`render_edges`,
                       `look_toggled`), `set_render_options` `cavity`/
                       `edges`; the snapshot twin copies both.
  - `analysis.py`    — **checking a part** (Qt-free): `mass_properties`
                       (divergence-theorem volume, area, centroid,
                       box), `mass`/`cost`/`print_time` (material table,
                       a rough mm³/s model), `print_check` (watertight
                       by edge pairing; overhang faces beyond the angle,
                       plate faces excluded; thin walls by a ray from
                       sampled face centroids through a `_Grid`, only
                       as far as min_wall; footprint vs height) each
                       pass/warn/fail with the faulting triangles, and
                       `interference` (box reject, grid, edge-crosses-
                       triangle via Möller-Trumbore, containment by ray
                       parity: intersect / contains / inside / clear).
  - `analysis_dialog.py` — the three non-modal **Analyse** windows
                       (menu + tree context menu): `part_tris` gives
                       the world mesh the views show (exact per-part
                       meshes where rendered, `approximate` when
                       booleans are uncut); the print check can tint
                       the faulting faces through
                       `View3D.set_highlight_mesh` and restores the
                       selection highlight on close. MCP:
                       `mass_properties`, `check_printability`,
                       `check_interference` (read-only).
  - `sdf.py`         — **smooth blend** geometry (Qt-free): the
                       primitives under a `blend` (sphere, cube,
                       cylinder, capsule, ellipsoid, rounded box —
                       through transforms, groups, loops, joints and
                       symmetry) become signed distance functions; a
                       polynomial smooth-min merges them (a part out of
                       the blend's reach is skipped unevaluated);
                       marching tetrahedra (Kuhn 6-tet split:
                       conforming, no ambiguous cases, shared edge
                       vertices -> watertight) extracts the surface.
                       The `blend` node (bake.py) BAKES it:
                       `kcad_blend(radius, detail, points=, faces=)
                       { children }` — the helper renders only the
                       polyhedron; import ignores the arrays and
                       rebuilds from the children (lossless); bakes
                       are cached by content (`bake._CACHE`). A blend
                       inside a loop/if is refused (one mesh cannot
                       vary per iteration). `get_code` summarises baked
                       arrays (`bake.ELIDE`) unless `full`, and a
                       statement may span lines (`CadNode.emit` splits
                       it so the line spans stay exact).
  - `deform.py`      — **deformers and subdivision** (Qt-free): `bend`
                       (neutral-axis arc, base fixed), `twist`, `taper`,
                       `lattice` (trilinear FFD of the bounding box's 8
                       corners) and Loop `subdivide`. Deformers first
                       `split_long_edges` — decided per EDGE, so both
                       triangles split alike: no T-junctions, the
                       surface stays closed. The nodes (bake.py) bake
                       like `blend` (one `_BAKED` table drives helper,
                       codegen, builder, cache, validation) and read
                       the children's PREVIEW mesh, so a boolean inside
                       one is refused (it would bake a wrong shape).
  - `rowsedit.py`    — property editors for the `rows` schema kind (a
                       table: fixed columns, or free-length index lists
                       typed `0, 1, 2`; a non-numeric cell is kept as an
                       expression) and the `choice` kind (drop-down).
  - `section.py`     — planar **cross-sections** of a mesh (Qt-free):
                       `cut()` orients every segment with the solid
                       on its left, so outer outlines run CCW, holes
                       CW and signed areas sum to the net area;
                       `chain()` joins them (an outline that cannot
                       close = the mesh leaks there); `draw()` paints
                       the hatched section. Behind the `section` tool.
  - `meshimport.py`  — **imported meshes** (`stl_import`, Qt-free):
                       paths stay absolute in memory (preview,
                       validation and the engine's temp-folder render
                       all need that) but `relative_for_save` writes
                       them relative to the `.kcad` when inside its
                       folder, and `resolve_paths` (load_kcad, and
                       import_scad — OpenSCAD reads import() beside the
                       .scad) makes them absolute again, finding a
                       missing file — even a Windows path read on a Mac
                       — by name beside the document. `place` centres
                       the mesh or stands it on the floor from its own
                       bbox (rotation + scale applied); `set_scale` /
                       `UNITS` fix a file drawn in cm, m or inches; the
                       import shows `size_text` so wrong units are
                       obvious. `mesh.stl_mesh` caches
                       `STL_CACHE_FILES` parsed files (it used to keep
                       one, so two imports re-parsed each other on every
                       redraw).
  - `refimage.py`    — **reference images**: a picture on an axis plane
                       (lower-left (x, y), width mm, height from the
                       aspect, offset along the normal, opacity),
                       stored in `DocumentModel.reference_images`
                       (undoable, saved in .kcad as "references").
                       The sketch view draws it under the grid while
                       its plane shows (flipped: the scene is Y-up);
                       the 3D view draws it on its plane behind the
                       model via a projective `quadToQuad`. View >
                       Add Reference Image…, and the
                       `set_reference_image` MCP tool (file access).
  - `mcp_schema.py`  — the **MCP tool table**: 40 JSON-Schema tool
                       definitions. Qt-free and import-free — it is the
                       contract, so it can be inspected and tested
                       without a window, and the stdio server never
                       drags PyQt5 into the host's subprocess.
  - `mcp_tools.py`   — `McpToolExecutor`: runs one named tool against
                       the live `MainWindow`. Nodes are addressed by
                       `CadNode.id` (no parallel identity scheme), and
                       nothing here re-implements an editing operation
                       — everything goes through `DocumentModel`,
                       `scadparse`, `library` and `mates`, so an MCP
                       edit and a mouse edit are the same edit.
                       Parameter names are checked against `NODE_TYPES`
                       (a typo would otherwise sit in the node doing
                       nothing), `apply_code` **refuses a parse that
                       yielded no objects** (the parser skips bad
                       statements by design — right for importing
                       someone else's file, wrong for a program a
                       client just wrote), and an approximated STL
                       export says so loudly.
  - `mcp_bridge.py`  — `McpBridge`: loopback JSON server on 127.0.0.1
                       exposing those tools, token-authenticated from
                       the endpoint file, off until AI ▸ Connect to
                       Claude (Simple).
                       Forces the model's deferred undo snapshot around
                       each mutating call (`_flush_snapshot`) so one
                       call is one Ctrl+Z. Access levels read/edit/**full**
                       (the default — the narrower levels send the
                       user back to the File menu between steps)
                       — the edit→full line is the **filesystem**
                       (`_names_a_path`: `save_document` with no path is
                       Ctrl+S and stays at edit).
  - `mcp_server.py`  — the half an MCP host launches: JSON-RPC over
                       stdio, no Qt, no third-party imports. Forwards
                       each `tools/call` over the bridge socket and
                       reconnects on its own, so either side may
                       restart. `tool_content` turns a result carrying
                       `IMAGE_KEY` into a real MCP **image block**.
  - `mcp_http.py`    — the same bridge over Streamable HTTP at
                       `http://127.0.0.1:<port>/mcp`, for clients that
                       only take a URL. Same token, same access level;
                       validates `Origin` (a local server needs no CORS
                       preflight, so a web page could otherwise drive
                       the model).
  - `mcp_hosts.py`   — writes KherveCAD's entry into an MCP host's own
                       config (Claude Desktop, Claude Code via its CLI,
                       Cursor, Windsurf, VS Code, Cline, LM Studio).
                       Backs up, writes atomically, touches no other
                       key; Zed is refused because its settings hold
                       comments.
  - `mcp_dialog.py`  — AI ▸ Connect to Claude (Simple)…:
                       enable/disable, access
                       level, one-click host connect, hand-config
                       snippets and a live activity log.
  - `updater.py`     — **automatic updates from the GitHub releases**
                       (Help ▸ Check for Updates… and the checkable
                       Help ▸ Check for Updates Automatically). A
                       `CheckWorker` QThread asks the releases API
                       (urllib, 10 s timeout) for the newest published
                       release **for this platform** — Windows `v0.1.N`
                       + `KherveCAD-Setup-0.1.N.exe`, macOS
                       `macos-v0.1.N` + the arm64 DMG; drafts,
                       prereleases and releases missing the asset are
                       skipped — and compares on **N, the commit
                       count** (`_version.py`). "What changed" is the
                       release notes of every newer release (plus the
                       main-line `v` notes on macOS, whose own bodies
                       are install boilerplate) and the commit subjects
                       from the compare API (`running sha...tag`),
                       grouped feat → New, fix → Fixed,
                       perf/style/refactor → Improved, docs/test
                       dropped. Dialog: Download and install / Later /
                       Skip this version (`update_skip_version`). The
                       `DownloadWorker` streams to a temp dir (cancellable,
                       size-checked); then `install_mode()` decides:
                       **Windows** (an Inno install — `unins*.exe` beside
                       the exe) closes every window and runs the
                       installer detached with `/SILENT
                       /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS`,
                       and `khervecad.iss`'s `Check: WizardSilent`
                       `[Run]` entry relaunches the app; **macOS** mounts
                       the DMG (`hdiutil attach -nobrowse`) and a
                       detached `/bin/sh` script (`mac_install_script`)
                       waits for this PID, `ditto`s the new bundle beside
                       the old one, swaps them by rename, detaches,
                       strips quarantine and `open`s it — or, when the
                       bundle's folder is not writable / translocated,
                       opens the DMG in Finder. A source checkout or a
                       portable copy just gets the release page. The
                       automatic check runs 5 s after startup **only
                       when frozen**, at most once a day
                       (`update_last_check`, `update_auto`), and fails
                       silently; workers are C++-owned (`_launch`) so
                       closing the window mid-check cannot destroy a
                       running QThread.
  - `pattern.py`     — the **Pattern** wrapper (Blender's Array,
                       SolidWorks' linear/circular pattern; Repeat &
                       logic family): `kind` linear (`count` copies at
                       step `dx dy dz`), polar (`count` copies about
                       `axis` through the origin over `angle` — 360 or
                       more spreads them at `angle·i/count` so the last
                       never lands on the first, below 360 they SPAN it
                       at `angle·i/(count-1)`; `dz` is the rise per copy
                       along the axis, so a spring or spiral stair is
                       one pattern) or grid (`count_x/y/z` at the step).
                       Registered from organic.py like bake.py; compiles
                       to ONE `kcad_pattern(kind=, count=, step=, angle=,
                       axis=, rise=, counts=) { children }` call whose
                       helper is real OpenSCAD (`children()` + for
                       loops, nothing baked), so every number may be an
                       expression or loop variable and `build` re-imports
                       it losslessly. `matrices()` is the preview's copy
                       of the helper's rules (keep in step — the engine
                       parity test compares extent and volume); `tess`
                       unrolls the children's mesh per copy, `outlines`
                       does the same for 2D content inside an extrude
                       (hooked from `mesh.collect_outlines`). `check`
                       caps a pattern at `MAX_COPIES` (1000) and needs
                       every count ≥ 1. Examples ▸ Mechanical ▸ Bolt
                       circle & stair (pattern).
- `docs/MCP.md` — how to connect an assistant, what the 40 tools do,
  access levels, security, troubleshooting.
- `tests/` — pytest suite (offscreen Qt; run `python -m pytest tests/`).
- `requirements.txt`, `LICENSE` (GPL-3.0).

## Architecture

**The tree is the single source of truth.** Node categories:

- 2D shapes (`line`, `rect`, `circle`, `polygon`, `text`) — `line`
  compiles to `hull()` of two circles so it is a real extrudable
  solid; `circle` has an `angle` param (90 = quarter, 180 = semi)
  that compiles to a polygon fan when partial.
- 3D primitives (`cube`, `sphere`, `cylinder`), `polyhedron`
  (bake.py) and `stl_import`.
- Operations wrap their children (`linear_extrude`,
  `rotate_extrude`, `translate`, `rotate`, `scale`, `mirror`,
  `offset` for corner rounding).
- Booleans/grouping (`union` = group, `difference`, `intersection`,
  `hull`, `minkowski`; `round_edges()` = minkowski + small sphere,
  the post-extrusion rounding idiom).
- `component` ("Object") — a **part definition** that compiles to its
  own OpenSCAD `module`. This is the part/assembly split (SolidWorks
  part-vs-assembly, Onshape part-studio-vs-assembly): an Object is
  **defined** in the Object tab and, while it lives only there, is
  kept **hidden** so it does not appear as geometry in the Main
  assembly (`ObjectTree._top_nodes` filters hidden components).
  The **Main tab is an assembly of instances**: right-click > Insert
  Object (`DocumentModel.add_instance`) drops a `reference` whose
  `ref` is the Object's name; that instance compiles to **one placed
  module call** (`translate(...) Part();`, see
  `CadNode._emit_reference`) and carries its own placement, `mate`
  **and colour** (Main lists instances, so without `color`/`alpha` on
  the instance there was no way to colour a part there at all).
  The same Object can be instanced many times, each placed, mated and
  coloured independently. Anchors/mates operate on the instance but resolve
  the Object **definition** for the anchor geometry
  (`mates.definition_of`), so a picked anchor stored on the
  definition is shared by every instance. `mesh._set_refs` indexes
  from the document root so an instance tessellated alone (Snap pick
  meshes, 2D outlines) still resolves its definition. **Everything
  added to Main arrives as one part row**: imported meshes and
  library parts wrap into a visible component
  (`DocumentModel.enclose_as_part`); a primitive or 2D shape created
  while Main is current becomes a new visible Object and the Object
  tab opens on it (`MainWindow._geometry_created_in_main`); a `.scad`
  import's loose top-level geometry is gathered into ONE part named
  after the file (`enclose_import_as_part` — module-defined Objects
  and instances keep their structure; the tested scadparse round-trip
  API is untouched). See `objecttab.py`/`anchors.py`/`mates.py`.
- `scad_raw` — a leaf holding **verbatim OpenSCAD** (`code` param,
  multi-line `text` editor). Emitted straight into the program, so
  library calls the built-in tessellator can't model (BOSL2, ...) still
  render **through the OpenSCAD engine**; the built-in preview shows
  nothing for it (`mesh._tess` returns `[]`). Hidden ⇒ emits nothing
  (raw code can't take the `*` modifier). Insert via Insert > OpenSCAD
  code.
- Organic nodes (`capsule`, `ellipsoid`, `rounded_box`,
  `symmetry`, `joint`) — see `organic.py`: they compile to
  `kcad_*` helper-module calls with the helpers emitted once at the
  top of the program, and re-import losslessly.
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
selected object's **geometry** is highlighted in both viewers —
`mesh.selected_world_tris()` tags the selected subtree's world-space
triangles (ancestor transforms applied), which the 3D view paints
the way **OpenSCAD's `#` debug modifier** looks, and the 2D view
projects to an accent outline in the current plane (works at any
tree depth). The `#` is **imitated, never emitted**: OpenSCAD's
modifiers only affect its own GUI preview and the engine hands back
a colourless STL, so a real `#` in the program would change nothing
here (and would leak into exported `.scad`).

The 3D tint (`View3D._tint_selection`) fills the selection's
silhouette into an offscreen mask and composites it with
**Multiply**, rather than drawing highlight faces into the depth
sort. This is not cosmetic — the highlight always comes from the
built-in tessellator while `mesh` may be **OpenSCAD's exact render**
(and for a `difference()` the built-in only approximates: first
operand, holes uncut). Those are different triangulations of one
surface, so sorting them together let model faces win over highlight
faces in radial bands and **striped the selection ("zebra")** — no
depth bias can fix that. Multiplying a flat mask over the finished
render is immune to the mismatch, keeps the shading, facet edges and
cut holes underneath (dark pixels stay dark), and cannot stack into
a darker patch where faces overlap. Guarded by
`test_selection_does_not_stripe_on_a_mismatched_mesh`.

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
it) open/import it; imported files land in Open Recent. The mesh node
carries its own `rx/ry/rz` and uniform `scale` (compiled to
`translate() rotate() scale() import()`, folded back by scadparse);
paths are absolute in memory but saved relative to the `.kcad` when
inside its folder, and right-click ▸ Imported mesh centres it, stands
it on the floor or fixes its units — see `meshimport.py`.

**Render pipeline**: any model change re-tessellates instantly
(built-in preview) and schedules a debounced exact OpenSCAD render
that replaces the preview when it lands.

**Exact meshes are rendered per PART**, not per document
(`engine.request_part_render(key, code)` -> `part_ready` ->
`mesh.set_exact_mesh`). An assembly is parts placed side by side, not
booleaned together, so each Object is rendered alone
(`subtree_scad`) and `_component_mesh` uses that mesh in place of its
own tessellation. This is what makes an exact preview affordable and
correct: bolt holes are really cut, **every part keeps its own colour**
(one STL of the whole document could carry only one, which is why a
coloured document used to stay approximate), parts pop in
progressively (the badge reads "n/m parts exact"), and the key is the
part's *content* — moving, snapping or colouring it re-renders
nothing. `mesh.exact_key(node, env, fn)` must be given the same `fn`
the preview tessellates with, or the key never matches. Port
Tube.kcad: 55 s for the whole document, 0.2-16 s per part, and only
once each. A render only lands if it
still matches what is on screen: `ScadEngine` carries a **generation
counter** bumped by `request_render()` and `cancel()`, and `_finished`
drops the mesh when the running generation is stale. Without it a
render requested moments before a change (colouring the document,
switching to the Object tab) arrived afterwards and silently repainted
the view with the *previous* model — the "3D forgot my colours" bug.
The 3D view's **Redraw** button (`MainWindow.force_refresh`) is the
manual escape hatch: clear the mesh caches, rebuild both views.
A part is only sent for an exact render when `mesh.needs_exact` says
so: the preview cannot show it right (`uses_booleans`) AND it has at
most one colour inside (`part_colours`). The STL is colourless: it
wears that single colour, and a multi-coloured part keeps its preview
(before, a red library brick turned grey and a Lego set lost every
colour when its exact mesh landed).

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
  primitives; horizontal toolbar = file | undo | operation families
  (drop-down `GroupButton`s) | Snap objects | grid/snap/plane | Render
  (F5), Fit 3D | assistant, **Vibe Model** — see `toolbars.py`. Every
  icon gets a how-to tooltip from `tooltips.py`; add one when adding a
  tool.
- **Vibe Model** (Ctrl+Shift+M, `MainWindow.set_vibe_model`) folds away
  the left column (tree + Properties), the 2D sketch and the drawing
  toolbar so the 3D view fills the window while an assistant builds;
  not persisted, so the app always starts with every panel.
- Every command that acts on the **selection** (operations, group/
  ungroup, delete, duplicate, clipboard, reorder) goes through
  `BuilderPanel.active_tree()` — the Object tab's tree while that tab
  is current, else Main. Reading `builder.tree` directly finds nothing
  selected in the Object tab and the command silently does nothing.
- Status bar: cursor position in sketch coordinates + engine badge
  (OpenSCAD found / built-in preview).
- **Window style**: Fusion as default; themes shared with the family
  (View > Theme).
- **Analyse menu**: Mass properties, Check for 3D printing, Check
  interference — on the selection, else the whole document / every
  part in Main (`analysis_dialog.open_analysis`).
- **Help menu**: User Guide (F1), **Check for Updates…**, a checkable
  **Check for Updates Automatically** (on by default; only an installed
  build checks by itself), About. See `updater.py`.

## Packaging / installer

**Windows installer, one command** — from the project root, with the
interpreter that has PyInstaller:

```
python packaging/build_installer.py
```

It writes `khervecad/VERSION` (a frozen build has no `.git` and would
otherwise report the `0.1.0` fallback), freezes with PyInstaller
one-folder, unpacks the official **OpenSCAD portable ZIP** into an
`openscad/` subfolder so the engine is guaranteed present, then makes
the portable zip, the per-user Inno installer, and the stable-name
`KherveCAD-Setup.exe` the website links to — all in `dist/`.

`engine.bundled_openscad()` finds that subfolder beside the executable;
`find_openscad()` still lets Edit > Locate OpenSCAD win over it.
Shipping OpenSCAD's binary is a redistribution: its licence installs
alongside and its **source archive must be attached to the release**.
Full detail, and why each step exists, in `docs/INSTALLER.md`.

**macOS (Apple Silicon), one command** — on a Mac:

```
python packaging/build_macos.py
```

Same first step (write `khervecad/VERSION`), then the platform's own
container: the spec ends in `BUNDLE` so PyInstaller yields
`dist/KherveCAD.app`, OpenSCAD is mounted from its disk image into
`Contents/Resources/openscad/OpenSCAD.app`, the finished tree is ad-hoc
signed (Apple Silicon will not run an unsigned Mach-O, and dropping
OpenSCAD in invalidates PyInstaller's signature, so signing goes last)
and sealed into a DMG. **arm64 only** — stable OpenSCAD 2021.01 has no
Apple Silicon binary, so the engine comes from a snapshot the build
discovers at run time. `.github/workflows/macos-build.yml` does the
whole thing on a `macos-14` runner and publishes a `macos-v<ver>`
release with `--latest=false`, so `releases/latest` stays on the Windows
release the website links to. See `README.macos.md`.

## MCP (Model Context Protocol)

KherveCAD is drivable by **any local MCP assistant** — Claude Desktop,
Claude Code, Cursor, Cline, VS Code, LM Studio — not just the built-in
chat. The chat answers with a program the user then applies; an MCP
client gets the whole app as **40 tools**: the object tree, OpenSCAD in
and out, the part library, Objects/instances/mates, the document, and
`render_view`, which hands back a **PNG of the 3D preview** from any of
the seven camera presets.

Two halves, because they run in different processes:

```
 host ──stdio──▶ khervecad.mcp_server ──loopback TCP──▶ McpBridge ──▶ window
 host ──HTTP POST──────────────────────────────────────▶ McpHttpServer ──┘
```

The stdio server is the subprocess the host owns (no Qt, no deps, so it
starts instantly and works from any Python); the bridge lives in the
app, where the tools can touch the live model on the GUI thread. Either
side may restart without the other noticing. `--mcp-server` on the
frozen executable takes the same path, checked **before** any GUI work.

Load-bearing details:

- **`apply_code` is the headline tool.** It parses an OpenSCAD program
  into real nodes through `scadparse`, so an assistant can write fifty
  lines and the user can still drag one corner afterwards. It reuses
  `ChatPanel._object_contents` to unwrap a module-plus-call program, or
  a part applied into an Object would nest inside itself.
- **One call is one undo step, and two calls are two.**
  `DocumentModel` captures snapshots on a 0 ms timer, so a QUndoStack
  macro around a tool call wraps *nothing* and pushes an empty
  do-nothing step — the user presses Ctrl+Z and sees nothing happen.
  The bridge forces the capture instead (`_flush_snapshot`), with
  `UNDO_MERGE_S` neutralised on the way out so two tool calls do not
  fold together the way a drag's scrubs should.
- **Access levels** (AI ▸ Connect to Claude (Simple), persisted in
  QSettings):
  read / edit / full, defaulting to **full**. The edit→full line is the
  filesystem, not the
  model — at *edit* a client can do anything to the open document
  (worst case: you undo it), while naming a path to read or write waits
  for *full*.
- **127.0.0.1 only**, random per-session token in the endpoint file
  (`mcp-bridge.json` in the platform state dir), bridge off until the
  user turns it on, endpoint removed when the window closes.

Adding a tool: define it in `mcp_schema.TOOLS`, implement `_t_<name>`
on `McpToolExecutor`, and decide whether it belongs in
`_READ_ONLY_TOOLS` / `_NO_SNAPSHOT_TOOLS` / `_FILE_TOOLS`. The two test
modules assert the schema and the implementations stay in step, so a
half-added tool fails the suite.

## Roadmap

**Tool queue** (asked for 2026-09-11; **all six landed 2026-09-12** —
fillet.py, shell.py, pattern.py, analysis.py, shading.py — kept here as
the record of what each was for and where it would grow next):

1. **Fillet / chamfer by clicking an edge** — SolidWorks' Fillet
   ("round objects"): pick an edge or a face in the 3D view (the Snap
   tool's `anchors.pick`/`describe_pick` already find edges), give a
   radius, and only that edge is rounded. `round_edges` (Minkowski +
   sphere) rounds *every* edge alike and stays as the whole-part
   option. OpenSCAD has no edge, so this bakes like `sweep`/`blend`
   (a polyhedron the importer rebuilds from parameters): the edge is
   remembered as geometry (its two endpoints in the part's local
   frame, re-found by nearest match after edits), the mesh is
   re-triangulated with a rolling-ball fillet along it. Hardest and
   highest-value item.
2. **Shell / hollow** (Blender Solidify): "make this 2 mm thick" for
   printing — an offset surface of an arbitrary mesh; the SDF/marching
   tetrahedra in `sdf.py` are the starting point.
3. **Pattern** (Blender Array): linear / polar / grid copies as a UI
   over `for_loop`.
4. **3D-print check** (Blender 3D-Print Toolbox): watertight, overhangs
   > 45°, thinnest wall, volume, time/cost estimate — `section.py` and
   the mesh helpers do most of it.
5. **Mass properties & interference**: volume, area, centre of mass,
   "do these parts overlap?" — what an assistant needs to check its
   own work (an MCP tool as much as a menu item).
6. Ambient occlusion / edge lines in the preview — done as cavity
   shading + edge lines (`shading.py`); true AO would need a depth
   buffer the painter does not have.

Where each would grow next: a fillet that reads the part's EXACT
OpenSCAD mesh (so edges where a union's shapes meet exist), spherical
corner blends where three fillets meet, a fillet preview that cuts;
a shell whose opening is a picked face rather than a direction; a
pattern along a path; a print check that suggests the best orientation.

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
geometry-only, so the *whole-document* exact render pauses while the
document is coloured (F5 still forces it) — but the **per-part exact
meshes carry on**, and each part is tinted as it is placed, so a
coloured assembly is still exact (see the render pipeline above).

**Materials.** A `color` node also carries a `material`
(`model.MATERIALS`: Plastic, Metal, Matte, Clay, Glass, Rubber, Skin,
Gold, Copper, Emissive; "Default" follows the render style). It rides
the preview's colour tuple as a third element — `(colour, alpha,
material)` — and the 3D view shades each such face with
`view3d.MATERIAL_STYLES[material]` (Glass is translucent), except in
Wireframe/X-ray. OpenSCAD has no materials, so codegen writes a
`kcad_material("Metal") color(...)` prefix whose helper renders its
children unchanged; the importer folds it back into the colour node
(`organic.fold_material`, only the wrapper its own builder made).
`set_color` takes a `material`. FORMAT_VERSION 6.

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
