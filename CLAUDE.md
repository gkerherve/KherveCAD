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
                       `install_excepthook`: PyQt turns an exception
                       escaping a Qt callback into qFatal, which aborted
                       the app with the document; the hook appends the
                       traceback to the crash log, warns once (via a
                       0 ms timer, never inside a paint) and carries on.
                       The log now APPENDS per session (it was truncated
                       at every launch, so a crash was gone by the time
                       it was reported), rotating past `CRASH_LOG_LIMIT`.
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
                       OpenSCAD semantics (2026-09-17): vector maths
                       (element-wise +/-, scalar x vector, dot, matrix x
                       vector/matrix), "strings" (masked before the
                       syntax rewrites), `$fn`/`$t`… (`SPECIAL_DEFAULTS`),
                       expression-level `let`/`assert`/`echo`, function
                       literals, and lookup, rands (seeded from their
                       arguments so the preview never flickers), str,
                       chr, ord, cross, search, is_*, min/max of a list;
                       round() rounds halves away from zero like
                       OpenSCAD (Python's banker's rounding made
                       round(2.5) 2). Parsed ASTs are cached (`_compile`).
  - `scadlang.py`    — OpenSCAD statements that are not shapes, as tree
                       nodes (registered from organic.py): `resize`,
                       `multmatrix` (rows param; every .csg uses it),
                       `render`, `intersection_for` (preview = first
                       iteration, in `mesh.APPROXIMATED`), `let`
                       (bindings text; `organic.child_scope` gives the
                       children its variables in validation and preview),
                       `echo` and `assert` (a false assert paints the node
                       red with its message). They compile to OpenSCAD's
                       own statements (no helper module) and scadparse
                       reads them back (`parse_statement`, raw argument
                       text so `b = a * 2` stays an expression).
  - OpenSCAD fidelity (2026-09-17): **text()** takes font ("Family:style=
                       Bold Italic"), halign, valign, spacing, direction
                       (`mesh.text_path` lays them out; view2d's
                       TextShapeItem uses it too); **polygon** takes
                       `paths` (rows of point indices, nested = holes);
                       both are schema-only params, omitted when default,
                       so older documents stay byte-identical (MCP accepts
                       schema keys). The importer picks segments like
                       OpenSCAD (`scadparse._segments`: $fn, else scope
                       $fn, else $fa/$fs fragments; an expression $fn
                       stays one). **Debug modifiers** `#` `%` `!` are
                       `params["modifier"]` (`model.MODIFIERS`,
                       `CadNode.modifier_prefix`, set from the tree's
                       right-click ▸ Debug modifier, painted as a row tag
                       via ROLE_MODIFIER): the preview tints # and %
                       (`mesh.MODIFIER_TINT`) and `!` draws that node alone
                       where it sits (`mesh.show_only`). Distinct from the
                       selection highlight, which imitates # and never
                       writes it.
  - **Parametric import** (same day): `Parser.bound` holds the names
                       the TREE defines where the parser stands (variable
                       nodes, module arguments, let bindings, loop
                       variables — `Parser.scoped`); `_keeps_link` keeps
                       an expression over them as written (`cube(w)`,
                       `h = w * 2`) and still folds what only the parser
                       knows (a user function, a library's variable).
                       `_components` splits a vector variable
                       (`translate(pos)` -> pos[0..2]); centred squares of
                       expression sizes centre by expression.
  - `features.py`    — registry of the parametric FEATURE nodes (the
                       libraries' gears, threads, holes…): each module in
                       `MODULES` has the organic contract (NODE_TYPES,
                       LEAVES, preamble helper, statement, BUILDERS, check,
                       tess, outlines for 2D) and organic.py hooks
                       `features` once. Shared preview helpers: `extrude`
                       (loops through a transient linear_extrude node, so
                       twist/scale/caps are the tessellator's own),
                       `stations_solid` (one closed wall through (z, turn,
                       scale) stations — no cap-to-cap seams),
                       `polygon_node` (loops as polygon paths).
  - `gears.py`       — `gear` node: involute spur / helical / herringbone
                       / internal / rack / bevel / worm by module, teeth,
                       pressure angle, backlash, clearance, bore
                       (`outline` = the helper's kcad_gear_outline: flanks
                       off the base circle, a pointed tip trimmed by
                       bisection). `kcad_gear(...)` helper is real
                       OpenSCAD; `test_gears` checks the preview volume
                       against OpenSCAD's render (within 1 %) when the
                       binary is installed. Insert ▸ Mechanical features.
  - `threads.py`     — `thread` node: metric / trapezoidal / square /
                       buttress / pipe (tapered) / bottle, starts, hand,
                       internal (+ clearance, the tap to subtract), bore.
                       The section at z = 0 follows the axial profile at u
                       = θ · lead / 360 (`section`, `profile`) and is
                       twisted 360° a lead — an exact helicoid, no boolean
                       (`kcad_thread`). Preview through
                       `features.stations_solid`, capped at
                       `PREVIEW_SLICES`; within 1 % of OpenSCAD.
  - `holes.py`       — `hole` node, the solid to subtract, top at z = 0
                       going down: plain, counterbore, countersink,
                       nut_trap, heat_insert, slot, teardrop (along X,
                       point up); `extra` above the face. A union of
                       cylinders / cones / prisms (`pieces`, `kcad_hole`).
  - `solids.py`      — `polyhedron_solid` (12 Platonic / Archimedean
                       solids by circumradius: vertex rules from signed
                       cyclic permutations and φ, hull in both preview and
                       helper — hull of 0.001 cubes) and `star` (2D regular
                       polygon or star). `curves2d.py`: `rounded_polygon`
                       (rows [x, y, r], tangent arcs shrunk to half an
                       edge) and `bezier_shape` (closed cubic curves, rows
                       in threes). `textures.py`: `knurl` (intersection of
                       two opposite twisted toothed sections in OpenSCAD;
                       the preview builds r = min(both) directly, closed)
                       and `honeycomb` (2D, whole hexagonal cells as holes,
                       `NESTED_2D`). view2d draws every feature 2D shape
                       with OutlineShapeItem. All within 1 % of OpenSCAD.
  - `library_print.py` — Parts for 3D printing (Library ▸ 3D printing):
                       sliding dovetail, cantilever snap-fit, print-in-place
                       hinge (each leaf cut round the other's knuckles by
                       the clearance, knuckles bored round the pin), living
                       hinge, heat-set insert boss, threaded bottle cap
                       (knurl minus an internal bottle thread), cable clip,
                       Gridfinity bin (42 mm pitch, 7 mm units, stepped
                       feet as hulls of thin slabs) and baseplate, divided
                       tray, electronics enclosure (standoffs with insert
                       holes, port opening, honeycomb-vented lid). Built
                       from the feature nodes; `_vbox` rounds only
                       vertical edges (a rounded_box thinned the rims).
                       Every part renders in OpenSCAD.
  - `library_vitamins.py` — Motion & electronics (NopSCADlib's
                       "vitamins", published dimensions, for designing
                       around): NEMA 17/23 steppers (31 / 47.14 mm tapped
                       pattern, boss, D-flat shaft), T-slot extrusions
                       (2020/2040/3030, bored cells), MGN rails with
                       counterbored holes + carriage, GT2 pulleys (OD =
                       teeth·2/π − 0.508), 608/625/6001 and LM8UU bearings,
                       40–120 mm fans (polar pattern of twisted blades),
                       Raspberry Pi 4 and Arduino Uno boards with their
                       connectors. `library_generative.py`: Lego Technic
                       beam / axle / pin / module-1 gear with a cross hole,
                       and seeded Voronoi panel (Bowyer–Watson `delaunay`,
                       cells by half-plane clipping, inset by the wall),
                       maze (backtracker spanning tree) and Hilbert plate.
  - `textured.py`    — `textured` node: a cylinder or panel whose surface
                       carries ribs / waves / diamonds / bricks / hexes /
                       dimples / checkers (`height` 0..1 over u, v mm),
                       relief deep; the cylinder's period rounds so the
                       pattern closes. The helper builds the same
                       polyhedron (points then faces) in OpenSCAD —
                       volumes agree exactly. `curves2d` also has
                       `svg_path` (a 2D shape typed as an SVG path, y up,
                       inner subpaths holes; the call carries the flattened
                       points for OpenSCAD, the importer rebuilds from d).
  - `split.py`       — Split for printing (tree right-click, `split_ui`
                       dialog, MCP `split_part`): two Objects, each
                       `difference() { intersection() { <clone of the
                       part>; <side box> } <dowel holes> }`, the dowels
                       where the section (`section.cut`) is solid and far
                       from its edges (`dowel_points`), a pin Object, the
                       second half moved `gap` along the axis, the
                       original hidden. Editable nodes, exact in OpenSCAD.
  - `animate.py`     — View ▸ Animate ($t): `set_time` puts OpenSCAD's
                       animation time in `expr.SPECIAL_DEFAULTS["$t"]`
                       (every expression reads it), `engine.DEFINES`
                       (`-D $t=…` on every OpenSCAD run) and the exact-mesh
                       key of parts whose params mention $t
                       (`mesh._component_key`); the document never changes.
                       Panel: play/pause, scrub, FPS, steps, Export frames
                       (PNG per step via pngexport). MCP
                       `set_render_options time`. scadparse never folds an
                       expression reading $t / $preview / $vp* (`_LIVE`).
  - `customizer.py`  — OpenSCAD Customizer annotations on variables:
                       `// [10:5:200]`, `// [a, b]`, `// [1:Thin, 2:Thick]`,
                       `// 12` (text length), the description line above
                       and `/* [Group] */` tabs (`[Hidden]` hides) become
                       optional assign params options / description /
                       group (Properties edits them), `annotate` reads them
                       after the parse, `lines_before`/`trailing` write
                       them in `CadNode.emit`, and `widget` gives the
                       Variables sheet's Adjust column its slider,
                       drop-down, checkbox or text box
                       (`VariablesSheet._control`; a moved control sets
                       the value without rebuilding under the drag).
  - `customizer_panel.py` — View ▸ Customizer: the annotated global
                       variables as a dock of grouped controls (one box
                       per `/* [Group] */`, description, live value), opened
                       by itself once per document that has any; each
                       slider has a ▶ that sweeps it back and forth
                       (`PLAY_INTERVAL_MS`) so a motor angle turns a gear
                       train on screen. Object caches key only on the
                       variables a part READS (`mesh._component_key`), so a
                       moving slider re-tessellates / re-renders only the
                       parts that use it. Speed (a crank mechanism: 650 ms
                       -> 34 ms a tick): `features.tess` caches feature
                       meshes by resolved params (a gear that only turns
                       keeps its mesh), capsules hull once along +Z and are
                       turned into place (`organic._capsule_along_z`), the
                       panel coalesces a drag's values into one redraw
                       (`_emit_pending`), and the Variables sheet updates
                       only the changed row.
                       **Second pass** (2026-09-17, the user: "why is it
                       so slow for the motion? we had it done for the gears
                       with opengl"). OpenGL only DRAWS — the triangle list
                       is rebuilt in Python every tick — and most of a tick
                       was not geometry at all. What was wrong, worst
                       first: (1) the **BSP tree** (`view3d.BSP_SETTLE_MS`)
                       was rebuilt for every mesh the painter was handed
                       and thrown away a frame later, its worker fighting
                       the GUI for the GIL — now `set_mesh` (and the paint
                       that finds no tree after OpenGL gives up, which runs
                       every frame) only ARMS a single-shot timer, so the
                       exact order is built once the model stands still;
                       `wait_for_bsp` forces it for snapshots, and a style
                       or hardware toggle still builds at once. Without
                       OpenGL a crank tick went 56 ms -> 3 ms of app work,
                       the same as with it. (2) The **Code
                       tab** regenerated the whole program and re-syntax-
                       highlighted it on every change even when hidden
                       (`treepanel.refresh_code`: mark `_code_dirty`, still
                       refresh the error marks the Main tree paints, and
                       build the text when the tab is looked at). (3) The
                       **Customizer panel** tore down and recreated every
                       control whenever a variable changed from outside —
                       an MCP call, the Variables sheet, undo — now
                       `_sync_row` moves that one control with its signals
                       blocked, rebuilding only if the annotation itself
                       changed. (4) `mesh._component_key` matched the env
                       against the WHOLE key text, so a part depended on
                       any variable sharing a name with a param or a node
                       type: a circle's `angle=` made every moon of an
                       orrery re-tessellate on a tick. It now scans only
                       the strings inside param VALUES (`_expr_strings`),
                       which is also far less text — a polyhedron's points
                       are numbers, and they are most of a key. Ints and
                       floats in the env compare equal, so a slider first
                       writing 10 where 10.0 stood does not invalidate
                       everything. (5) A chain of single-child transform
                       nodes is now ONE matrix (`_TRANSFORM_MATS` in
                       `mesh._tess`): `translate · rotate · scale` over a
                       part walked the whole mesh once per link. It stops
                       at anything `_tess` must see itself (several
                       children, hidden, a modifier) and carries the
                       selection flag down. (6) `transform_mesh` and
                       `_transform_colored` spell the arithmetic out over
                       the list instead of calling per point and zipping
                       three passes (2x and 1.3x). Orrery globes also got
                       cheaper: an orrery's Earth is millimetres across, so
                       its coastline simplifies to 1.2° with no relief
                       (19k -> 4k triangles of a 76k-triangle orrery).
                       End-to-end ticks: crank 56 -> 3 ms, Jupiter's moons
                       120 -> 42 ms, the whole Solar System 454 -> 280 ms
                       (31 moving bodies, 76k triangles — still the
                       tessellator's own cost, which only a 1-pass
                       compose-through-Objects would cut further).
                       `tests/test_motion_speed.py` pins every one.
  - `scadinclude.py` — what reaches beyond one file: `use <>` / `include
                       <>` tokens become **scad_use** nodes (emit the same
                       line; an unresolvable one is red) and the library
                       file is read for its modules and functions (an
                       include also its variables), cached per file +
                       mtime; a library module keeps its FILE's scope
                       (`Module.scope`). A library call that does not
                       inline cleanly (new warnings, or no geometry) is
                       kept verbatim as **scad_raw**, as is any call
                       nothing defines — they used to be dropped
                       (`raw_statement` dedents continuation lines so a
                       nested block does not re-indent every round trip).
                       `children()` / `children(i)` / `children([..])`
                       in an inlined body stand for the call's own
                       children (`call_children`, originals first then
                       clones). scad_raw is in `mesh.APPROXIMATED`, so a
                       part holding code gets an exact per-part render,
                       and `to_scad_map(only=)` writes every scad_use of
                       the document first so that render finds the
                       library; `enclose_import_as_part` leaves scad_use
                       at the top level.
  - `scadfiles.py`   — geometry read from files, as nodes: **surface**
                       (a .dat matrix or a picture's sRGB luminance ×100,
                       `invert`; a closed solid down to min(0, lowest-1),
                       preview sampled to `PREVIEW_CELLS` a side) and
                       **import_2d** (SVG/DXF outlines via svgdxf.py, x/y
                       folded from a translate, center/dpi/layer/id/$fn;
                       nested loops are holes like a glyph's,
                       `mesh._oriented`). OpenSCAD's own calls both ways;
                       paths save relative (`meshimport.PATH_PARAMS`).
                       File ▸ Import 2D Drawing (a 3 mm extrusion in a new
                       Object) / Import Height Map, drag and drop, and MCP
                       open_document; view2d draws import_2d with
                       `OutlineShapeItem`. `.csg` opens through scadparse
                       (`group()` = union, multmatrix), `.amf` is a mesh
                       (`engine._parse_amf`), and export_document writes
                       .off/.amf/.csg/.svg/.dxf through OpenSCAD.
  - `svgdxf.py`      — Qt-free SVG (paths with every command incl. arcs,
                       rect/circle/ellipse/polygon, nested transforms,
                       viewBox + physical size or dpi, y flipped, hidden
                       elements skipped, Inkscape layer or id) and DXF
                       (LWPOLYLINE/POLYLINE bulges, LINE, ARC, CIRCLE,
                       ELLIPSE, SPLINE by de Boor; loose pieces `chain`ed
                       into loops) -> outlines in mm.
  - `scadlib.py`     — where libraries resolve, in OpenSCAD's order: the
                       including file's folder, the document's folder
                       (`DOCUMENT_DIR`, set in `_update_title`), imported
                       files' folders, OPENSCADPATH, the user library
                       folder, the installation's (MCAD in OpenSCAD.app).
                       `engine._process` gives every OpenSCAD run that
                       OPENSCADPATH (renders run in a temp folder).
                       `KNOWN` = BOSL2, MCAD, NopSCADlib, Round-Anything,
                       dotSCAD, threads.scad, Catch'n'Hole, Gridfinity
                       Rebuilt; `install` unpacks a GitHub archive into the
                       user library folder (injectable opener).
                       `scadlib_dialog.py` is Library ▸ OpenSCAD Libraries
                       (install on click, open folder, insert the include
                       line) and the MCP `list_scad_libraries` /
                       `install_scad_library` bodies (install counts as a
                       file tool: full access).
  - `document.py`    — `.kcad` JSON (de)serialisation, `.scad` export.
  - `units.py`       — the **document unit** (Qt-free):
                       `DocumentModel.unit` ("nm", "um", "mm", "cm",
                       "m", "in"; default "mm"; Edit ▸ Document Units…,
                       MCP `set_render_options unit`) says what one model
                       unit means. A LABEL, never a rescale — OpenSCAD is
                       unitless, and a 100 nm quartz particle of 0.4913 nm
                       lattice cells is written 100 and 0.4913. Every
                       readout uses `symbol()` (status bar, 2D scale bar /
                       live size / measure / auto dimensions, Cut Through,
                       Blueprint UNITS cell, Analyse, Printables text);
                       what is physically dimensioned goes through
                       `to_mm()`: mass via true cm³, print time and cost
                       only for `PRINTABLE` units (mm, cm, in), the print
                       check converts its printer-mm thresholds (a
                       minimum wall wider than the part fails without
                       probing), and STL/3MF — which slicers read as mm —
                       are written 1:1 unless the user (Export STL's
                       question) or `export_document scale_to_mm` asks;
                       `scale_mesh_file` scales the written file (3MF by
                       rewriting its vertex attributes). MCP keys ending
                       `_mm`/`_mm2`/`_mm3` are always TRUE millimetres
                       (`significant` figures, so 1e-13 survives); plain
                       keys are document units. The unit is in the undo
                       snapshot (one Ctrl+Z); new documents and examples
                       are mm.
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
                       part this way. A label on an **Object's placed
                       call names the Object** (`Throat_and_belly();
                       // Throat and belly`): an Object has no tag, and
                       codegen writes that comment whenever the name is
                       not the identifier (spaces, a deduped `Wheel_2`),
                       so such names survive export -> import instead of
                       coming back as identifiers.
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
  - `library_fasteners.py` — the rest of the **fastener drawer**
                       (2026-09-17, the user's request), 43 parts on
                       library.py's `BOLT_SIZES`, so an M6 washer, nut and
                       bolt belong together: part-threaded hex bolt,
                       countersunk / button socket screws, slotted and
                       cross-recessed pan heads, slotted countersunk, grub
                       screw, shoulder screw, thumb screw, eye bolt,
                       U-bolt, carriage bolt, coach screw, wood screw,
                       self-tapper, studding, hanger bolt; nyloc / wing /
                       dome / square / flanged / castle / thin / coupling
                       nuts, T-slot nut, rivet nut, heat-set insert; flat,
                       penny, split spring, star and Belleville washers;
                       dowel, clevis, split and R-clip pins, internal and
                       external circlips, solid and blind rivets; hex
                       standoff and round spacer. Threads are the real
                       helix (`thread_solid`), rings are REVOLVED profiles
                       (`_rev`/`_ring`: an annulus with no boolean), a
                       slot or cross recess is the union of the sectors it
                       leaves standing (`_sector`, the `circle` node's
                       angle) and a bent bar is `_torus` — so most preview
                       exactly; only a real recess (hex socket, tapped
                       hole) is a difference, finished by the per-part
                       exact render. A dome's profile starts at the APEX
                       (started at the base, every dome head rendered as a
                       cup).
  - `library_chem.py`— **Chemistry** parts: beakers, flasks
                       (Erlenmeyer, round-bottom, volumetric), test
                       tube, graduated cylinder, funnel, burette,
                       pipette, dropper, Petri dish, watch glass,
                       separating funnel, condenser, plus the bench
                       hardware (rack, stand, burner, hotplate...).
                       Glassware is ONE revolved wall profile: the
                       outer outline drawn, the inner one offset along
                       its normals (`_offset_in`, an even wall round
                       every heel and shoulder), a rolled rim bead —
                       hollow without a boolean, so the preview is
                       right. Glass pieces carry the **Glass material**
                       (`_col` adds it to the GLASS tint); joints are
                       frosted. Graduations sit where the volume really
                       reaches (`_z_for_volume` integrates the inner
                       outline), printed white with numbers and the
                       nominal volume one character per tangent plane
                       (`_curved_text`, tilted with a sloping wall);
                       Griffin spout (`_spout`, a polyhedron lip),
                       volumetric calibration ring (bulb sized by
                       bisection so the ring lands in the neck),
                       burette Schellbach stripe, glass stopcocks with
                       PTFE keys. An optional liquid (`fill` %, colour
                       from `LIQUIDS` via the Part Library colour combo
                       `dims["_color"]`, "Empty" for none) has a
                       meniscus; the separating funnel holds two layers.
  - `library_room.py`— **Room & furniture**: table, lab workbench,
                       chair, stool, monitor, TV, door (with frame),
                       wall panel, and coloured **carpet** squares
                       (colour chosen from the size list). Multi-colour
                       unions with no booleans, so each component keeps
                       its colour in the preview.
  - `library_home.py`— **Home furniture**, 18 parts for every room:
                       dining table + chair, sofa, armchair, coffee
                       table, bookcase (with books), sideboard, floor
                       lamp, made-up bed, bedside table (with lamp),
                       wardrobe, chest of drawers, a kitchen run (drawers,
                       sink + tap, oven + hob + hood, wall units),
                       fridge-freezer, toilet, washbasin on a vanity, bath
                       and shower. Same rule as library_room: boxes,
                       rounded boxes, cylinders and capsules, NO booleans
                       (a bath or basin is walls around a floor). Wood /
                       fabric / front colours via `colors` +
                       `dims["_color"]`; counts (seats, shelves, doors,
                       drawers, units) are `COUNT_FIELDS`, merged into
                       `library._COUNT_FIELDS`. Front faces -Y.
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
  - `examples.py`    — ready-made **example models** (in the Library
                       menu, see EXAMPLE_PLACES): each `build()` returns a fresh `root` that
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
                       threaded rod, fan impeller, an **Object +
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
  - Vacuum revision (2026-09-13, `library.py`): `build_part` makes every
                       Vacuum part **metal** (`metallic`: an uncoloured
                       part wrapped in one stainless Metal colour, so its
                       exact render still tints; painted parts keep their
                       paint with a Metal finish, Glass stays glass).
                       Multi-port fittings take a **knuckle** (a tube-size
                       ball + a bore-size ball) where ports meet at an
                       angle — an elbow's corner was open and its bores ran
                       out through it — and `fitting_reach` keeps the
                       dialog's 60 mm (30 for KF) from running a CF63+
                       tee's or cross's flanges into each other. Ports may
                       be explicit rotations (`_port_turn`).
  - `library_vacuum.py` — 28 more Vacuum parts on library.py's flange
                       geometry: 5/6-way crosses, CF cube, zero-length and
                       conical reducers, viewport, flexible bellows,
                       CF→KF adapter, spherical and cylindrical chambers
                       (`_ported`: ports start at the wall, never inside,
                       so a Cut Through shows an empty chamber), nude ion
                       gauge (helix grid = twisted extrude of an offset
                       circle), Pirani, capacitance manometer, RGA, ion
                       pump, TSP, cryopump, diaphragm pump, leak valve,
                       wobble stick, transfer arm, linear shift, KF clamp /
                       centering ring / blank / cross / reducer / bellows
                       hose. Multi-material parts are a union of OBJECTS
                       (`_object`), one per material, each rendered exact
                       on its own. Size tables are looked up by `_size`
                       (the dialog passes only field values).
  - `library_uhv.py` / `library_manip.py` / `library_xps.py` —
                       **surface science** (2026-09-17, the user's request):
                       sample holders (flag plate 18 x 21, PTS puck,
                       parking carousel), prep and analysis tools (sputter
                       ion gun, 4-grid rear-view LEED, e-beam evaporator,
                       hot-cathode gauge head, lens-mounted hemispherical
                       analyser with its mu-metal dome, mu-metal liner,
                       load-lock fast-entry door) — every port-mounted part
                       to ONE convention: the CF sealing face at z = 0
                       looking DOWN, air side +z, vacuum side -z, `reach`
                       = face to sample, so the Chamber Designer can drop
                       any of them on any port. library_manip: the
                       commercial manipulator families (Omniax style —
                       hinged flange, XY bellows, cross-roller stage, two
                       columns, ball screw, DPRF; Transax style — two
                       bellows and a side column; HPT style — three rods
                       and micrometers; UHV Design XYZT — steppers, profile
                       rail on an extrusion spine, MagiDrive), each ending
                       in a flag / PTS / LN2 sample head (`_sample_head`),
                       plus the detailed transfer arm (port aligner, mm
                       scale, carriage with bearing housings and rotation
                       ring, bake-out port, fork / bayonet / pincer) and
                       the detailed RGA (quadrupole rods on ceramic
                       spacers, open ion source, Faraday cup + multiplier,
                       finned electronics head). library_xps: the twin-anode
                       source (retraction, HV and water) and the Rowland-
                       circle **monochromator** (XM1000 / uFOCUS 600 /
                       MX650 class: quartz crystal drum, exit tube, anode
                       housing with ion pump; `geometry()` places crystal
                       and anode from the Bragg angle). Parts sorted by
                       material into Objects by `_bag`/`_objects`.
  - `chamber_design.py` / `chamber_bench.py` / `chamber_dialog.py` — the
                       **Chamber Designer** (Library ▸ Vacuum & UHV ▸
                       Chamber Designer…): a chamber as JSON — body
                       (sphere/cylinder/cube), wall, mu-metal liner,
                       orientation (rx, ry, rz), focal-point height above
                       the floor, bench — and ports, each aimed at a FOCAL
                       POINT on the chamber axis (`focus` mm from the
                       centre: a tall chamber gets a preparation level and
                       an analysis level), with a flange, length measured
                       from that point, an accessory, the accessory's size
                       row (`variant`) and its `spin` about the port axis.
                       `problems()` checks collisions in 3D (each port's
                       tube and flange sampled as cylinders), ports too
                       short to clear the body and accessories on the wrong
                       flange family. Everything on the chamber turns with
                       it; the bench (`chamber_bench`: frame, castors,
                       breadboard table, frame + 19" rack, tripod) stays
                       level and stands on z = 0. The dialog draws an
                       unfolded map of port directions (drag to aim,
                       double-click to add) beside top and side views.
  - `library_cards.py` — **Playing cards**, one card at a time: a part
                       per suit (size = rank) + Joker + back. Paper body
                       = hull of four corner circles (rounded, convex);
                       raised ink: the index in the top-left AND turned
                       half round in the bottom-right, standard pip
                       layouts (`PIPS`, lower pips upside down), court
                       cards framed with the letter and a crown / tiara /
                       cap mirrored top and bottom, a diamond-lattice
                       back. Text has no alignment param: `_text` centres
                       by estimated width.
  - `library_pots.py` — **Pots**: 14 parametric pots in 7 colours
                       (`colors`, terracotta = Clay, glazes, concrete...).
                       Round pots are one revolved wall profile (hollow
                       without a boolean, drainage hole); hex / octagon /
                       low-poly = the same revolved in 6 / 8 / 7 segments;
                       square, trough and twisted star = a 2D ring
                       (outline minus inset) extruded with a flare or
                       twist over a floor — exact in the preview since the
                       2D-hole fix above.
  - `library_kcad.py` sections: a subfolder of `parts/` is a library
                       **section** (`shipped`, `category_of`): Brackets
                       (the 15 of KCAD Projects/Brackets + two older),
                       Minecraft, Pots (merged with library_pots'),
                       **Cars** (Ferrari 288 GTO / F8 / SF90, Mercedes
                       G-Class, Mini Cooper S — its baked body meshes
                       ride along in `Cars/Mini Cooper S parts/`) and
                       **Tools** (57 hand tools, built by
                       `tools/hand_tools.py`). The loose top-level
                       "KCAD files" section was **retired** (Sep 2026,
                       the user's request; Vase Elwen dropped from Pots
                       too): `parts/` holds sections only, and a test
                       enforces it. The sync tool takes `--into SECTION`
                       (always pass it) and keeps a relative mesh's
                       subfolder when copying.
  - `examples.py` Showcase: `_showcase(stem)` loads a finished model from
                       `khervecad/showcase/` (the Ferrari 288 GTO, 1138
                       objects; the spec ships the folder).
  - `library_lego_parts.py` — **every Lego piece its own Library item**
                       (2026-09-18, the user's request): ~100 parts
                       ("Brick 2 × 4", "Slope 33° 3 × 2", "Arch 1 × 6",
                       "Technic brick 1 × 8"), no size field, each with its
                       usual colour first. Beyond library_lego's shapes:
                       33°/65°/inverted/curved/cheese slopes (`wedge` + a
                       side profile), round bricks/plates/tiles/cones (one
                       revolved outline: hollow open stud, open underside),
                       arches (opening drawn into the side outline), windows
                       (2D-holed frame + Trans-clear pane), Technic bricks
                       (pin holes as 2D holes — exact in the preview),
                       jumpers, corners, side-stud brick, baseplates to
                       32 × 32. `library_menu.GROUPED_CATEGORIES["Lego"] =
                       group_of` splits Lego ▸ Bricks & plates into
                       Bricks / Plates / … / Any size (customise), the last
                       being library_lego's five sized parts (kept: MCP,
                       tests and the dialog use them).
  - `library_lego_sets.py` — the **Lego sets** category: every Lego
                       example as a library part (`sizes={}`), built by
                       the example's own function and lifted out of its
                       root, so a set drops into an assembly as one
                       Object. `examples` is imported lazily (it imports
                       the library).
  - `crystal.py`     — **crystal structures** (Qt-free): `Crystal` = a
                       lattice (a, b, c Å, α, β, γ — any system; a along
                       x, b in xy) + EVERY atom of the conventional cell
                       (fractional), optional coordination `polyhedra`
                       {centre, ligand, cutoff, sites} and the reference
                       `density` / `bonds` the tests pin. `ELEMENTS`:
                       covalent radii (Cordero 2008), Jmol colours,
                       masses. `nearest`, `computed_density`,
                       `polyhedra_sites` (ligands through the periodic
                       images), `polyhedron` (convex hull -> OpenSCAD
                       points/faces, clockwise outside) and `custom(dict)`
                       for a crystal an assistant brings from a paper.
  - `crystal_library.py` — 32 standard structures in five families
                       (metals FCC/BCC/HCP/SC, semiconductors, ionic
                       salts, oxides incl. rutile/anatase/perovskite/
                       α-quartz, carbon & nitrides); prototypes written
                       once (`fcc`, `diamond`, `rock_salt`, `wurtzite`,
                       `rutile`…), quartz's O the P3₂21 orbit.
                       `test_crystal` pins every density (2.5 %) and
                       nearest distance (1.5 %).
  - `crystal_build.py` — the **Crystal Builder**'s program writer: unit
                       cell (atoms incl. face/edge/corner repeats, lattice
                       box, translucent polyhedra) -> supercell (for i,
                       j, k over na×nb×nc of ONE tiling cell) -> particle
                       (sphere, hemisphere, cube, box, cylinder, hexagonal
                       prism, octahedron; every cell or N³ block whose
                       centre is inside; spheres/hemispheres on an upright
                       c-axis stack each column with a `while`, else `for`
                       + `if`); `build: "hierarchy"` = all three side by
                       side; `build: "scatter"` = `count` instances of ONE
                       particle dart-thrown over an `area` (footprints +
                       `min_gap` apart, resting on z = 0, turned at
                       random, seeded; optional substrate slab) — the
                       budget is shared across the copies.
                       NANOMETRES; tunables are prefixed document
                       variables (`quartz_r`, `quartz_N`; a second build
                       gets `quartz2_`). Counts cells/atoms/polyhedra/
                       triangles with the program's own loops (by volume
                       past `MAX_ITERATIONS`) — a test pins estimate ==
                       tessellation — refuses past `BUDGET` (800k tris),
                       and `fill: auto` switches to blocks past `COMFORT`.
                       `apply` (empty document -> nm, else scaled into its
                       unit with a note; sphere segments lowered) and the
                       MCP `list_crystals` / `build_crystal` bodies live
                       here (mcp_tools.py is past its size).
  - `crystal_surface.py` — **crystal surfaces** (Qt-free): a slab of any
                       crystal cut along any (hkl) — Si(111), quartz
                       (0001), rutile (110); four hexagonal indices read
                       too (`parse_miller`). `centerings` finds the I/F/C
                       translations hidden in the conventional cell (else
                       Si(111) came out a 2x2 of its real cell);
                       `in_plane_basis` takes the shortest in-plane lattice
                       pair whose area is primitive-volume / spacing, and w
                       the shortest step to the next plane. Atoms are
                       wrapped per layer into the in-plane cell (a straight
                       prism, not sheared), normal +z, top at z = 0; the
                       cut falls in the widest gap between planes
                       (`widest_gap`: Si(111) ends on a whole bilayer)
                       unless `termination` is given. Bulk-terminated, no
                       reconstruction. Program = one cell module + a for
                       over nx × ny (no scalar*vector: the preview's expr
                       cannot multiply a list). MCP `build_surface`;
                       Library ▸ Surfaces ▸ Surface Builder…
                       (`crystal_surface_dialog.py`, presets). Tests pin
                       the cells, spacings and that a layer holds the bulk
                       density for any orientation.
  - `crystal_dialog.py` — Library ▸ Crystal Builder…: a non-modal panel
                       over crystal_build with a live count; a refused
                       build disables Build and says why.
  - `library_crystal.py` — every library crystal as Part Library parts:
                       `crystal_<key>` ("Crystals (unit cells)") and
                       `supercell_<key>` ("Crystals (supercells)", sizes
                       2x2x2..6x6x6, "cells" count field), built with
                       `Spec.inline` — the counts written in as numbers,
                       because a library part lands inside an enclosing
                       Object and OpenSCAD modules only see top-level
                       variables. A part spec may carry `prepare(model)`:
                       `library.prepare_document` runs it from every
                       insert path (menu, dialog, MCP) — crystals switch
                       an empty document to nm and drop to 12 segments.
  - `molecule.py`    — **molecules** (Qt-free): SMILES in, 3D atoms out.
                       `parse_smiles` (organic subset, aromatic, bracket
                       atoms with H and charge, bond orders, branches,
                       ring closures, '.'; chirality ignored),
                       `add_hydrogens` (valences; an aromatic atom takes
                       its lowest), `embed`: VSEPR domains (neighbours +
                       lone pairs; `ideal_angle` squeezes for lone pairs —
                       water 104.5°), rings (`find_rings`) placed WHOLE as
                       regular polygons (sp3 rings puckered, a fused ring
                       on its shared edge — walked as chains they came out
                       zig-zags the relaxation could not close), the rest
                       in free template slots turned anti/planar (the
                       frame takes the first slot NOT opposite slot 0: the
                       linear and octahedral templates collapsed), then
                       `_relax` (bonds, 1-3 distances, a non-bonded
                       floor). Bonds = covalent radii × 1 / 0.93 / 0.87 /
                       0.79. `formula_counts` ("Ca(OH)2", "CuSO4·5H2O"),
                       `hill_formula` ("O4S 2-").
  - `molecule_library.py` — ~240 compounds as name + SMILES + the formula
                       they must give (the tests build every one), in
                       9 families (gases, inorganic acids/bases/ions,
                       salts/oxides/minerals, VSEPR shapes, hydrocarbons,
                       alcohols/ethers/carbonyls, acids & esters, nitrogen
                       compounds & solvents, biomolecules & drugs — amino
                       acids, nucleobases and sugars included).
                       `molecule_library_more.py` (2026-09-18, the user's
                       request) merges in ~250 more: benzene derivatives,
                       polycyclic & fused aromatics, and the common
                       medicines in six "Medicines: …" families (pain,
                       anti-infectives, heart, brain, stomach/allergy/
                       breathing, diabetes/hormones/vitamins). Bridged and
                       small-ring drugs needed two embedder fixes in
                       molecule.py: a 3- or 4-ring's 1-3 terms use the
                       ring's own 60° / 88° (the VSEPR angle stretched
                       cyclopropane bonds to 1.7 Å), and `best_embedding`
                       re-embeds from up to `RETRIES` other atoms when the
                       first shape's `strain` exceeds `SOUND` (morphinans
                       tangled from atom 0). An unknown compound key falls
                       back to `carbon_nano.get` (c60 …).
  - `carbon_nano.py` — carbon nanostructures (Qt-free) as Molecules on
                       their LATTICE, not SMILES: graphene flakes (AB /
                       ABA / ABC / AA stacks, twisted bilayer), H-capped
                       armchair/zigzag nanoribbons and quantum dot,
                       vacancy and N-doped sheets, the graphite (0001)
                       surface (+ step); (n, m) nanotubes rolled from the
                       strip 0 <= u < |C| (seam exact, axis kept on z —
                       centring on the centroid tilted it), multi-walled;
                       fullerenes C20, C60 (truncated icosahedron, 6-6
                       bonds double), and C60 + 10k (C70, C80, capped
                       (5, 5) tubes): C60 along its five-fold axis IS the
                       (5, 5) ring pattern, so 10-atom belts are let in at
                       the equator (the top half turned 36° for an odd
                       count) and `relax` settles bonds/ring angles.
                       `library_carbon.py` makes them Part Library parts —
                       Surfaces ▸ Graphene & graphite, Crystals ▸ Carbon
                       nanotubes (width, depth, layers, (n, m), length
                       fields; the dialog takes per-field `suffixes`,
                       " nm" / " °") and Molecules ▸ Fullerenes — drawn in
                       the new `lattice` style (0.17 × vdW balls: full
                       balls hid the honeycomb), cages ball and stick.
  - `graphene_build.py` — graphene / stacks / twisted bilayer / graphite
                       (0001) as a PARAMETRIC program (the user: "a for
                       loop with angles and steps"), not an atom list:
                       variables a, cc, nx, ny, layers, gap (+ twist,
                       top_nx) and one loop nest — rows j of A/B atoms,
                       A's bond at 90°, B's up-bonds `for (t = [30 : 120
                       : 150])`, `if`s dropping the side bonds and the two
                       sharp corners (ny even), so every C has 2-3
                       neighbours; `sites` is the same rules in Python
                       (counts, tests). Editing nx in the Object regrows it.
  - `library_surfaces.py` — Library ▸ **Surfaces** (its own menu, Surface
                       Builder on top): every library crystal but graphite
                       cut along its usual faces (cubic 100/110/111, hex
                       0001/10-10/11-20, tetragonal 001/100/110/101), one
                       part per face in "Surfaces: <family>", submenu per
                       crystal (`library_menu.GROUPED_CATEGORIES`,
                       `crystal_of`), built with `SurfaceSpec(inline=True)`
                       (counts in the loop: a part's module cannot see
                       top-level variables); an over-budget size drops
                       cells rather than failing.
  - `molecule_build.py` — the **Compound Builder**: `molecule_program`
                       (ball and stick with half-bonds in each atom's
                       colour, double/triple bonds as parallel sticks, an
                       aromatic bond plus a thin stick toward its ring;
                       space filling; sticks) and `reaction_program`:
                       "2 H2 + O2 -> 2 H2O" (-> <=> → ⇌ =, fractions;
                       species by key, name, formula — a charge magnitude
                       only after ^ or a space, so NH4+ is +1 — or
                       smiles:…), `balance` (exact RREF null space,
                       smallest whole numbers), `balance_check`, and a
                       left-to-right XZ layout (each molecule built once
                       and instanced, coefficients / + / formulas as
                       upright 3D text, a shaft + cone arrow, two half
                       arrows for ⇌). `apply` and the MCP bodies
                       (`list_molecules`, `build_molecule`,
                       `build_reaction`) live here.
  - `molecule_dialog.py` — Library ▸ Compound Builder…: Molecule,
                       Reaction and Protein tabs with a live formula /
                       balance / residue preview; a bad SMILES, reaction
                       or sequence disables Build.
  - `library_molecule.py` — every compound as a Part Library part
                       `molecule_<key>` ("Molecules: <family>"), ball and
                       stick, the crystals' `prepare` reused; every
                       protein preset as `protein_<key>` ("Molecules:
                       Proteins & peptides", cartoon + side chains).
  - `protein.py`     — **proteins** (Qt-free, 2026-09-17). BUILT:
                       `build_peptide(sequence, secondary)` places every
                       heavy atom by NeRF from Engh & Huber internal
                       coordinates, the backbone on the (phi, psi) of a
                       letter per residue (H, G, E, P, L, C; a run of T
                       steps through `TURN`, grid-searched so two E
                       strands pair at 3.8-5.4 Å — the textbook type I'
                       angles left them 10 Å apart), backbone first, then
                       each side chain on the first of its `ROTAMERS`
                       that clears everything placed (fixed rotamers put
                       aromatics into O(i-4) in a helix). L chirality
                       pinned by N-C-CA-CB = +122.7 (PeptideBuilder's).
                       Local structure, NOT a fold: `clashes` says so.
                       READ: `parse_pdb` / `parse_mmcif` (`cif_tables`, a
                       small loop/quote/;-field tokenizer), first model,
                       altloc A, hydrogens dropped; HELIX/SHEET or
                       struct_conf/struct_sheet_range, else
                       `assign_secondary` from CA distances (P-SEA-like);
                       bonds by covalent radii through a grid (ligands,
                       disulfides, metals, no dictionary). `fetch` = RCSB
                       mmCIF by ID or the AlphaFold API by UniProt,
                       cached in the temp folder, opener injectable (the
                       tests are offline). `to_pdb` writes PDB with
                       HELIX/SHEET, and round-trips exactly.
  - `protein_build.py` — the program: styles cartoon (a Catmull-Rom
                       ribbon through CA, width along C=O flipped to stay
                       consistent — so a helix ribbon lies along the axis
                       and a strand's in its sheet — flat for helices,
                       arrows for strands, a tube for coil; seams at half
                       residues step the cross-section; each colour
                       stretch is ONE closed INDEXED polyhedron: unwelded
                       triangles fail `_check_polyhedron`'s edge pairing),
                       cartoon_sticks, trace, ball_and_stick, sticks,
                       space_filling — atoms as one for-loop per (colour,
                       radius) with `translate([p[0], p[1], p[2]])`:
                       `translate(p)` with a vector variable put every
                       atom at the origin in the coloured preview.
                       Colours structure / chain / rainbow / residue /
                       hydropathy / element; ligands ball and stick.
                       `PRESETS` (helices, strand, Trpzip hairpin, PPII,
                       collagen, melittin, magainin, GCN4, amyloid beta),
                       `BUDGET` 800k, apply = `molecule_build.apply`. MCP
                       `list_proteins` and `build_protein` (a file tool
                       for `path`; pdb_id / uniprot download).
  - `protein_dialog.py` — the Compound Builder's Protein tab: preset,
                       sequence + structure, PDB ID / AlphaFold (Fetch on
                       a thread polled by a QTimer), file; style, colour,
                       chains, ligands, water; Save PDB….
  - `house.py`       — the **House Builder**'s geometry (Qt-free): a
                       `House` is `Floor`s stacked in Z, each a set of
                       rectangular `Room`s (footprint only — wall height
                       and thickness are the FLOOR's, so two rooms
                       sharing an edge never get a double-thickness wall
                       between them) with `Opening`s (door/window) cut
                       into their walls and `Furniture` placed from the
                       Part Library, plus a `Garden`. `collect_walls`
                       finds every distinct wall segment of a floor (two
                       rooms' shared edge dedupes to ONE wall, canonical
                       key rounded to 0.1 mm, `house_items.GRID` snapping
                       keeps rooms drawn edge-to-edge exact) and gathers
                       whichever room(s) put an opening on it; every
                       wall is axis-aligned (rooms are rectangles) so
                       it is always purely horizontal or vertical — no
                       rotation is ever needed, `_wall_node` just emits
                       a box or, when it has openings, a union of SOLID
                       pieces (full-height piers between openings, a
                       sill under and a lintel over each) — NOT a
                       `difference()`: the built-in preview draws a
                       difference as its uncut first operand, so walls
                       looked solid until OpenSCAD finished. Every
                       opening gets a see-through `Glass` pane
                       (`GLASS_ALPHA`): a window's glazing or a door's
                       glazed leaf — the door clearer (`DOOR_GLASS_ALPHA`
                       0.15, glrender's floor): the Glass style lifts
                       alpha with its highlight, and at 0.3 a near-white
                       door read as a solid frosted panel in 3D. `_opening_spans` clamps openings
                       into the wall and makes overlapping ones
                       disjoint. `build_floor` returns one group per
                       floor (slabs, walls, a flat roof + eave on the
                       top floor, and each piece of furniture from
                       `library.build_part` as its OWN nested Object —
                       a "component" carrying x/y/z/rz, names unique
                       across the house, so "Ground floor" calls
                       "Toilet", "Sofa", "Chair 2"...); `apply`
                       inserts each floor as its OWN visible Object
                       (`enclose_as_part`, stacked by setting the
                       group's own `z` before wrapping — a "union"'s
                       placement params survive `make_component`'s
                       in-place type change to "component" unmodified)
                       plus one "Garden" Object beside the house's
                       footprint, and stores the design as
                       `model.house` (`house_to_spec` + "objects", the
                       names it built; saved in the .kcad, FORMAT_VERSION
                       10, and IN the undo snapshots). A later apply
                       `remove_built`s those Objects first, so building
                       again UPDATES the house. `house_from_spec` /
                       `house_to_spec` round-trip (saved furniture
                       `dims` are used verbatim) — one Python call, one undo step, no
                       flush needed (a dialog button's `clicked` slot
                       already returns to the event loop before the
                       0 ms snapshot timer fires). `FURNITURE_CATALOG`
                       groups `library_room`/`library_home` part ids by
                       room type (living room, bedroom, kitchen, ...)
                       for the picker, minus the fixtures (door, wall
                       panel) the House Builder itself provides.
  - House Builder, second pass (2026-09-15): **roofs** — `house.Roof`
                       (style Flat/Gable/Hip/Pyramid/Lean-to, pitch 5-60°,
                       overhang, ridge auto/x/y, covering from
                       `ROOF_COLORS`) on the top floor's INDOOR rooms,
                       built by `build_roof` from `hull()`s of thin boxes
                       (sloped boards over a wall-coloured gable/wedge
                       infill; one convex hull for hip/pyramid) — no
                       boolean, so the preview is exact; a spec with no
                       "roof" stays Flat (older saved houses rebuild
                       unchanged); `roof_outline` feeds the plan's dashed
                       `RoofItem`. **Outdoor areas**: `Room.surface`
                       "garden"/"paving" (porch, patio, driveway) get
                       ground only — no walls (`collect_walls` skips
                       them), no slab, not under the roof
                       (`Floor.indoor_bounds`). **Garage door** is a third
                       opening kind (`OPENING_KINDS`, `opening_size`): a
                       solid Metal panel, drawn with its up-and-over
                       travel on the plan. **Room presets** `ROOM_TYPES`
                       (corridor, reception, entrance, garage, stairwell,
                       porch, garden…) behind the builder's Room menu.
                       **Furniture height**: `Furniture.z` is edited in
                       the builder ("Height above floor" + "Sit on what's
                       below"); `surface_below` ray-casts the other pieces'
                       own triangles (`part_tris`, cached) under the
                       piece's centre and takes the highest UPWARD face
                       within `STACK_REACH` with room above it for the
                       piece — so a microwave lands on the worktop, not
                       on the wall cupboards; pieces with a part-spec
                       `on_top` (lamp, laptop, microwave, plant; plus
                       `ON_TOP_PARTS` TV/monitor) do it by themselves on
                       add and drop, `rest_z` pieces (pendant, wall shelf,
                       mirror cabinet, wall light) start at their height
                       and hold nothing. MCP: furniture `on_top`, room
                       `surface`, `roof`. The plan draws raised pieces
                       over lower ones (z value from `Furniture.z`).
  - House Builder, third pass (2026-09-16, from a picture of a house
                       whose garage stood open): **side wings get their own
                       roof** — `wing_roofs(house, i)` takes the parts of
                       floor i that no floor above covers
                       (`uncovered_rects`: coordinate-compressed cells
                       merged back into rectangles, `_clusters` lumps the
                       touching ones) and the side the taller part stands
                       on, and `build_roof(..., bounds=, style=, attach=)`
                       roofs each one; `Roof.wings` (WING_STYLES) picks the
                       shape, a **lean-to** by default, which leans on that
                       wall (`_roof_frame` turns the ridge along it and
                       returns `high_v0`, and the overhang on that side is
                       dropped so it does not poke through). **Outer vs
                       inner walls**: `collect_walls` now returns
                       (p1, p2, openings, INTERIOR) — a segment two rooms
                       share — and `build_floor(walls=(outside, inside))`
                       finishes them from `WALL_STYLES` /
                       `INNER_WALL_STYLES` (`House.outer_wall/inner_wall`).
                       **A room's own finish**: `Room.finish`
                       (`ROOM_FINISHES`: tiles, marble, panelling) lines
                       ITS side of every wall with `FINISH_THICKNESS`
                       panels around the openings (`room_finish_nodes`,
                       `_solid_runs`) and tiles its floor — bathrooms and
                       kitchens. `ROOF_COLORS` now has 12 coverings. All in
                       the spec (`walls`, room `finish`, roof `wings`), the
                       MCP tool and the builder (Floor section, Roof row,
                       room Finish).
  - House Builder, realism pass (2026-09-17, the user's request: "the
                       red bricks where the outside wall is simply just a
                       bit", open corners, flat roofs and tiles). Split out
                       of house.py into three modules:
                       `house_walls.py` — walls from the PLAN:
                       `wall_segments` splits every room edge where another
                       starts or stops and classifies each piece by what
                       lies either side (partition, `Floor.
                       inner_wall_thickness` default 100, or outside wall
                       with an `outside` sign), merged into runs; an
                       outside wall is two leaves, the facing and a plaster
                       lining, each ONE extruded elevation outline
                       (`region_loops`: rectilinear union minus openings ->
                       outlines + holes, doors as notches) — no seams on a
                       facade, real reveals, no boolean. The facing wraps a
                       CONVEX corner by the other wall's half thickness
                       (`_corner_wraps`; never a reflex one — its end face
                       would z-fight the plaster inside) and runs down past
                       the slab (storeys meet like masonry); a ground floor
                       gets a proud plinth. Joinery per opening: window
                       frame + mullions/transom + glass + sill + board +
                       lintel (brick/stone/timber per `OUTSIDE_DETAIL`),
                       front door (panelled leaf, glazing, letter plate,
                       step, canopy), inside doors (lining, architraves,
                       4-panel leaf), sectional garage doors. `room_nodes`:
                       floor covering, skirting, and tile linings where
                       they belong — `coverage_of`: bathroom "wet" (half
                       height + full behind bath/shower, found from the
                       furniture footprints `_fixture_ranges`), kitchen
                       "splash" band behind worktops/sinks, shower room
                       full — around every opening on the line, whichever
                       room drew it. `house_finishes.py` — tables
                       (16 outside finishes, 9 inside, JOINERY, 13 wall
                       finishes, 17 FLOORINGS) and the automatic choices by
                       room name (`room_kind`, `finish_of`, `flooring_of`,
                       crc32-picked so a street varies but a house is
                       stable; Room.finish "" = automatic, "None" = none;
                       Room.flooring). `house_roof.py` — a pitched roof is
                       its slopes as vertical-depth `polyhedron`s whose
                       plans tile the roof (gable 2, hip 4, pyramid 4,
                       lean-to 1), measured from a DATUM over the centre
                       line (`RoofShape.H` = wall head + hw·tan + 20) so the
                       planes sit on the wall's outer edge — from the wall
                       head the facing's top showed through every eave;
                       a pyramid on a rectangle lifts its eave until the
                       shallower faces clear it too. Hollow attic over a
                       12 mm ceiling, gable triangles in the facing, fascia,
                       soffit, half-round gutters (a polygon profile
                       extruded) with downpipes to the ground, bargeboards,
                       half-round ridge and hip tiles. `chimneys` (Roof.
                       chimney auto / ridge / none): every `home_fireplace`
                       gets a stack outside an outside wall from the ground,
                       or a breast through the floors above an inside wall,
                       ending CHIMNEY_CLEAR over the roof covering it (main
                       or wing) with corbel, cap and pots.
                       `build_house_floors` builds every floor at
                       `floor_levels` with its chimneys. House.joinery.
                       **Shader surfaces** added for it (glrender.SURFACES
                       9-27, `SURFACE_LOOK` gloss/saturation, the gloss
                       slot's strength now used by surfaces): Wall tiles,
                       Metro tiles, Mosaic, Hex tiles, Marble, Floor tiles,
                       Checker tiles, Terrazzo, Zellige, Floorboards,
                       Parquet, Carpet, Plaster, Cladding, Shingles, Thatch,
                       Standing seam, Solar panels, Panelling — also in
                       model/mcp_schema MATERIALS; roof ones course up the
                       slope (`ROOF_SURFACES`).
  - Cut Through levels (`cut_ui.py`, same day): quarters were too coarse
                       for a two-storey house — View ▸ Cut Through ▸ Where
                       lists every tenth, **Cut at a Storey** is filled from
                       `model.house` and the mesh height
                       (`storey_positions`, rebuilt on `aboutToShow`),
                       Ctrl+Alt+Up/Down nudge 2 % (`step_cut`), and the
                       CutBar gained − / + buttons and a % readout.
  - `library_home_more.py` / `library_home_extra.py` — ~60 more pieces
                       for every room (`FURNITURE_CATALOG` now has 15
                       sections incl. Kids' room, Hallway / corridor,
                       Entrance / porch, Reception, Stairs, Garage,
                       Utility, Garden / outdoor): corner sofa, piano,
                       fireplace, pendant, bunk bed, cot, island, bar
                       stool, microwave, dishwasher, towel radiator, desk,
                       office chair, washing machine…; straight and spiral
                       stairs (a storey high), car, bicycle, wheelie bin,
                       reception desk, waiting chairs, trees (broadleaf in
                       4 looks, conifer, birch), shrub, hedge, flower bed,
                       patio set, barbecue. Same rules as library_home
                       (no booleans, front -Y, on z = 0, true size);
                       `_disc_y` / `_disc_x` make portholes and wheels via
                       translate+rotate. Tested in
                       `tests/test_library_home_more.py`. The vertical
                       toolbar ends with a House Builder button
                       (`toolbars.build_tool_bar`, tip `house_builder`).
  - `house_designs.py` — **finished houses** (2026-09-17, the user's
                       request): bungalows and two-storey houses with 1, 2
                       and 3 bedrooms and a ten-storey block of flats (two
                       2-bed flats a floor round a core with a lift shaft
                       and switchback stairs — odd floors climb the other
                       column), as build_house specs in six brick styles
                       (`BRICKS` also picks the roof and joinery). Library
                       parts in House & home ▸ Finished houses (category
                       "Finished houses"; colour combo = brick; sizes
                       Furnished / Empty (shell) — the block defaults to the
                       shell, furnished it is ~750k triangles) and House
                       Builder templates (`house_templates.TEMPLATES`, the
                       build_house `template` enum). Built on two House
                       Builder rules added for them (`house_walls.
                       wall_segments`): rooms with the SAME NAME are one
                       open space (no wall between them, so a landing can
                       wrap a stairwell), and a room with surface "void"
                       has no slab or covering — a stairwell open over a
                       `balustrade` towards a hall/landing/corridor
                       (`Segment.rail`), walled towards anything else (a
                       lift shaft). Inserting one (menu, dialog, MCP
                       insert_part) does NOT add a sealed part: the spec's
                       `insert` hook (`library.insert_hook`, honoured by all
                       three paths) runs `house.apply(replace=False)`, so it
                       lands as one Object per floor named "<design> ·
                       <floor>" and the House Builder edits it. Every build
                       keeps its design on its first Object
                       (`params["house"]`); `house.design_of` finds the one
                       the selection belongs to, so with several houses in a
                       document the builder opens on the selected one and
                       Build replaces only it (apply dedupes top-level
                       names — two "Ground floor"s made a rebuild take both).
                       Tested in `tests/test_house_designs.py`.
                       **Finished labs** (2026-09-18, the user: a lab is
                       not a house): `LABS` — Chemistry lab (the user's
                       own saved design, `house_saved/chemistry_lab.json`
                       via `saved()`, keeps its walls and roof) and Physics
                       lab (house_templates.physics_lab) — category
                       "Finished labs", Library ▸ House & home ▸ Finished labs
                       (beside Finished houses, not in it);
                       no brick combo. The saved Chemistry lab also
                       replaces the built-in template.
  - Library & Examples menus (`library_menu.py`, reorganised 2026-09-17
                       — the user found the Library "all over the place"
                       and asked what Examples was for): **Library = parts
                       you ADD**, in four headed sections from
                       `library_groups.SECTIONS` (Engineering, Buildings &
                       places, Science, Toys & models; every PARTS category
                       placed exactly once — tested), each subject menu
                       with its builder on top (House, City, Lego, Crystal
                       + Surface, Compound); House & home is a submenu per
                       room from `house.FURNITURE_CATALOG`. The Part
                       Library dialog lists categories in the same order
                       (`category_order`). **Examples = whole documents
                       that REPLACE yours**: Learn, Techniques (the
                       Mechanical category), Course projects, Showcase
                       (+ vacuum starter, desk setup). Models that are
                       really parts left the Examples menu:
                       `library_examples.py` makes the flowers and the
                       stylised trees Library parts (built by the
                       example's own function, like `library_lego_sets`);
                       `examples.EXAMPLES` itself is unchanged, so MCP
                       load_example still offers them. `library_kcad.label`
                       splits CamelCase stems ("Minecraft Cat").
                       **Examples merged into Library** (2026-09-17, the
                       user's request): no Examples menu any more;
                       `library_menu.EXAMPLE_PLACES` puts each example
                       category where it belongs (Mechanical → Engineering
                       ▸ Mechanical examples, Vacuum → Vacuum & UHV, Room →
                       House & home, Learn / Projects / Showcase → a closing
                       LEARN section), every such submenu headed by
                       `EXAMPLE_NOTE`; they still load as documents
                       (`_load_example`).
  - `motion_play.py` — setting a model MOVING (2026-09-18, the user:
                       "if we say make it move / rotate / action, start
                       the play"): the body of MCP `play_motion`
                       (mcp_tools.py is past its size). `pick` finds the
                       motion slider — a slider in a Motion / Time group
                       (every mechanism and orrery puts its driver there),
                       else one named angle / days / time / spin…, else the
                       only one; `add_spin` makes a still part (Object,
                       instance or group) turn: a `<part>_spin` slider
                       (0:2:360, Motion group) added to its rz, reused if
                       it already spins. `play` shows the Customizer dock
                       and presses the row's ▶ (`CustomizerPanel.play`,
                       `stop`, `playing_node`), returning the range and the
                       seconds a sweep takes (notches × `PLAY_INTERVAL_MS`).
                       Any structural edit stops play (the panel rebuilds).
                       The MCP instructions' Motion section tells clients
                       to finish every "make it move / rotate / animate"
                       with it.
  - `library_motion.py` — **Mechanisms & motion** (Engineering): gear
                       pair, crank & piston, rack & pinion, cam & follower,
                       four-bar, planetary, XY platform, scissor lift,
                       robot arm — OpenSCAD programs with Customizer-
                       annotated drivers. The `insert` hook ADDS one:
                       variables renamed `<prefix>_name` (`prefixed`:
                       strings, comments and named arguments untouched —
                       `kcad_gear(m = m)` once lost its module),
                       `free_prefix` gives a second copy `crank2_`, groups
                       named after the mechanism, Objects placed right of
                       the document's bbox. Moving parts are gears /
                       capsules / boxes (no booleans); the lead screw is
                       static (a turning 52k-triangle thread cost 200 ms a
                       tick). Planet phase: `180 - 180/P + (θ - sun)·S/P`,
                       ring turned 180/R — `test_library_motion` checks the
                       gears clear. MCP insert_part honours the hook
                       (`insert_note`).
  - **Car Builder** (2026-09-17): `car_models.py` is the catalogue — 40
                       classic and super cars from their PUBLISHED figures
                       (length, width, height, wheelbase, factory tyre sizes
                       front and rear) plus a body SHAPE preset (`SHAPES`:
                       mid, wedge, front, longnose, rear-engine, sedan — the
                       side profile as fractions of L and H) and the details
                       that make a marque read (lights, grille, tail lights,
                       wing, factory rim, paint). No blueprint is traced or
                       shipped: proportions are hand-fitted to the published
                       dimensions. `car_build.py` lofts the body through
                       cross-sections every ~30 mm (`car_wheels.closed_grid`,
                       which picks the winding by signed volume): the section
                       rises to the wheel ARCH in the outer band, so a wheel
                       shows under a fender instead of a slab, and the top
                       bulges over it where the shape has fenders; a dark tub
                       closes the wheel wells; the greenhouse is three stacked
                       slabs (shoulder / window band / roof) so glass and body
                       meet face to face instead of fighting for one surface.
                       No booleans anywhere, so the preview is exact.
                       `car_wheels.py` builds a wheel axis-up: a revolved
                       tyre (a style changes only the sidewall ratio, so the
                       rolling diameter — and the ride height — never moves),
                       barrel, well, brake disc and caliper, hub, and spokes
                       as convex hulls in nine `RIMS` (five-spoke, Fuchs,
                       mesh, turbine, centre lock, steel with hubcap...).
                       Library ▸ Toys & models ▸ Cars: the **Car Builder**
                       (`car_dialog.py`, non-modal — make, model, paint,
                       wheels, tyres, finish, calipers, size; a build lands
                       right of the document and keeps its choices in
                       `params["car"]`, so **Update selected** rebuilds that
                       car in place) and every car as a one-click part
                       (`car_build.PARTS`, sizes 1:18 / full-size / 1:43 /
                       1:10, colour combo = paint). The hand-built .kcad cars
                       in `parts/Cars` stay as they are.
  - `library_minecraft.py` — Minecraft characters & mobs in the
                       Minecraft section (2026-09-17): Steve, Alex, zombie,
                       skeleton (drawing a bow), wither skeleton, creeper,
                       enderman, witch, piglin, spider (knees), iron golem
                       (holding a poppy), snow golem, slime, ghast, blaze,
                       chicken, sheep, bee, axolotl. Boxes in GAME PIXELS
                       (a block is 16), scaled by the size's pixel length.
                       Every part wears a `Skin` like the game's textures:
                       each pixel of each face is a letter of pixel art
                       (face, hair, sleeve, shoe, stripes, cracks — rows or
                       a callable) or a seeded shade of the base colour, and
                       a pixel unlike the base is a thin tile `TILE` proud
                       of the box; tiles merge along their row and go, with
                       the box, into one polyhedron per colour
                       (`landmark_kit.Kit`), so a figure is ~100 nodes and a
                       few thousand triangles, not thousands of cubes. A
                       part may be turned about a pivot (a zombie's arms, a
                       ghast's tentacles): its corners rotate before the
                       piece is written, so the skin turns with it. Eyes and
                       particles are Emissive. No booleans; front -Y, on
                       z = 0.
  - `library_prusa.py` — the **Prusa** section (2026-09-15, the user's
                       request): "Little Prusa man", an original chibi
                       figure in the spirit of the Little Josef Prusa
                       character (ellipsoid head, hair and beard, glasses
                       as a dark rim disc behind a clear lens, orange
                       T-shirt, jeans; built at 100 mm and scaled to the
                       size's height), and an Original Prusa MINI+ at its
                       real 380 × 330 × 380 mm (Z column left, cantilevered
                       X arm, sliding PEI bed, orange parts, front display)
                       printing a 40 mm Prusa man; 1:4 desk size too.
                       Nothing from the Printables files is used — modelled
                       from scratch. Tested in `tests/test_library_prusa.py`.
  - `library_music.py` / `library_music_more.py` — **Musical
                       instruments** (2026-09-18, the user's request),
                       Library ▸ EVERYDAY THINGS, submenus by `group_of`
                       (Keyboards, Strings, Winds & brass, Tuned percussion,
                       Drums & cymbals, Hand percussion, Accessories).
                       Tuned by their physics: a bar is a free-free beam,
                       `bar_length` L ∝ f^-e (e 0.33-0.36, not ½: real bars
                       are arched underneath), laid out by `keyboard_layout`
                       (naturals in front, accidentals behind and raised) on
                       rails at the 22.4 % nodes; resonators and pan pipes
                       are closed pipes `closed_pipe` = c / 4f − 0.6 r; frets
                       `fret_position` = S(1 − 2^(−n/12)), the neck joining
                       the body at the cfg's `joint` fret, so the bridge
                       lands where the scale says; chimes L ∝ 1/√f. Marimba,
                       xylophone, vibraphone, glockenspiel, toy xylophone,
                       keyboard (49-88 keys), grand piano (`grand_outline`:
                       spine, smoothstep bentside, elliptical tail; lid on
                       its prop stick; rim a 2D ring), drum kit (drummer at
                       +Y, left = +X) and its pieces, cymbals (one thin
                       bell-and-bow revolve); guitars / ukulele / violin
                       family lying on their backs, neck +Y, bass strings
                       −X (`body_outline`: two circular bouts, smoothstep
                       waist, optional cutaway); a violin body is ONE closed
                       polyhedron lofted through arched rings
                       (`arched_body`) — stacked extrusions left the ribs'
                       top face under the arch and the software painter drew
                       it through the walls — and `arch_z` sits the f-holes
                       and chinrest on it. Recorder, flute, trumpet (every
                       bend a half torus, Bessel-horn bell), pan pipes,
                       harmonica, triangle, tambourine, bongos, cajón,
                       maracas, wind chimes, music stand, metronome. Repeated
                       pieces (bars, tubes, keys, frets, lugs) are ONE
                       for-loop over value rows each; the helpers (`paint`,
                       `cyl`, `box`, `loop`…) take expression strings.
  - `library_kitchen.py` — **Kitchen & tableware** (same day): every
                       vessel is ONE revolved wall (`wall`: the outside from
                       the axis to the rim, the inside `library_chem.
                       _offset_in` a wall in, a round lip) so it is hollow
                       without a boolean; `liquid` fills the inside to a
                       height 0.4 mm clear of the glass (drinks are the
                       glassware's colour combo, "Empty" for none).
                       Handles are half tori stood on end (`loop_handle`),
                       spouts hulls of spheres (`spout`), a jug's lip a hull
                       from the rim to a tip. Plates, bowls, mug, teacup,
                       teapot, jug, cake stand, egg cup, stemware, tumblers,
                       carafe, wine bottle, mason jar, saucepan, stock pot /
                       casserole, frying pan, wok, kettle, baking tray,
                       cutlery, chef's knife, utensils, mills, a place
                       setting (diner at −Y, fork −X) and a tea set.
                       **Revolve seam** (found here): `mesh.
                       rotate_extrude_mesh` built its last ring at 2π, where
                       sin is −2.4e−16, so every full revolve was open by a
                       hair and the edge lines drew the seam across flat
                       floors; the last ring now IS the first
                       (`test_a_full_revolve_closes_its_seam_exactly`).
  - `library_electronics.py` — **Electronics** (2026-09-18, the user's
                       request), its own Library ▸ Engineering ▸
                       Electronics menu (`library_groups`; "Motion &
                       electronics" became Motion & motors). Boards
                       ("Electronics boards", beside library_vitamins' Uno
                       / Pi 4, built by its `_board`) at the makers'
                       published outlines: Arduino Nano and Mega 2560,
                       ESP32-DevKitC V4, NodeMCU (LoLin V3), Pi Pico, Zero
                       2 W, Pi 5, Teensy 4.0, Blue Pill, micro:bit V2 —
                       `test_library_electronics` pins each PCB's outline.
                       Components (resistor with its colour code from the
                       value — `bands`, capacitors, LEDs, TO-92, TO-220,
                       DIP-8..40, breadboards, pot, switch, headers, relay
                       module, 7-segment, buzzer, cells, SG90, LCD 16x2,
                       OLED, perfboard, terminal) true size, leads down
                       from z = 0. Lab equipment ("Electronics lab"): ESD
                       bench with shelf, soldering / hot-air stations, fume
                       extractor, meters, spectrum analyser, load, logic
                       analyser, microscope, helping hands, ESD mat,
                       drawer cabinet — `library_lab` helpers, `on_top`.
                       `house_templates.electronics_lab` (6 benches, store,
                       entrance with coats, office) is a template and a
                       Finished lab; FURNITURE_CATALOG / ROOM_TYPES have an
                       "Electronics lab" room.
  - `library_lab.py` — **labs and companies** (2026-09-16): 35 pieces in
                       the home catalogue (registered from the bottom of
                       `library_home_extra`, so library.py is untouched):
                       chemistry (island bench with reagent shelf and gas
                       taps, sink bench, fume hood, safety shower +
                       eyewash, safety cabinets, lab fridge, drying oven,
                       centrifuge, rotavap, glassware tray, stool,
                       extinguisher, first aid), physics (optical table,
                       laser, optics on posts, scope, supply, signal
                       generator, 19" rack, UHV chamber on its frame, LN2
                       dewar, electronics bench, whiteboard) and company
                       (bench desks, cubicle, meeting table, light task
                       chair, printer, server rack, lockers, coffee and
                       vending machines, phone booth, partition). Local
                       `_box`/`_cyl`/`_rod`/`_disc_y` keep small rounds
                       square and small cylinders at 8 sides: under the
                       document's $fn 45 a bench desk of rounded boxes and
                       detailed chairs was 60k triangles, a company floor
                       640k. FURNITURE_CATALOG sections + ROOM_TYPES:
                       Chemistry lab, Physics lab, Open-plan office,
                       Meeting room, Server room, Break room.
  - `house_templates.py` — whole furnished buildings as build_house specs:
                       Chemistry lab, Physics lab, Company office
                       (reception, open plan, meeting, manager, break,
                       server, toilets, corridor). The House Builder's
                       **Template** button (`load_template`) and build_house
                       `template` (`expand`: the caller's keys win). Bench
                       instruments are `on_top` and tested to land > 500 mm.
  - `city.py`        — the **City Builder** (Qt-free): villages, towns
                       and cities of OUTSIDE-ONLY buildings, so hundreds
                       stay light. A spec of explicit lists — roads
                       (polylines, kind avenue/street/lane/path), buildings,
                       lights `{x, y, rz}`, trees — or a `layout` + seed
                       that `generate` expands; `resolve` makes everything
                       explicit and is what `apply` stores as `model.city`
                       (.kcad "city", FORMAT_VERSION 11, in the undo
                       snapshots) and what the window edits. `apply`
                       inserts five Objects (City ground / roads /
                       buildings / Street lights / City trees) and
                       `remove_built`s the last build's first. Repeated
                       things are for-loops over value lists (every light
                       is ONE loop). Built for the SOFTWARE painter too,
                       which sorts whole faces by centre: pavements lie
                       BESIDE the tarmac (never under it), a pavement tile
                       on another road is dropped, and the grass is tiles
                       (`ground_tiles`: 20 m, 5 m beside roads) that leave
                       the roads out — one big ground slab, or tarmac on a
                       pavement slab, painted grass wedges over the roads.
                       `along_roads` skips points on another road.
                       MCP `get_city` (catalogue of every valid style,
                       species, terrain and prop id + the current design,
                       read back) and `build_city` (`mode` replace — the
                       default, the spec IS the city — or add); the MCP
                       instructions tell assistants to call get_city first
                       (Claude could not build a city from the tool
                       description alone). insert_part takes x/y/z/rz.
  - `city_buildings.py` — a building's outside, detailed: punched windows
                       (frame, glass, mullion, transom, sill — one loop body
                       per facade), curtain walls / glass ribbons + fins,
                       balconies, plinth, string courses, door with step and
                       canopy, shop front; pitched roofs (tiled slopes,
                       gable walls, ridge cap, fascia, gutters, bargeboards,
                       chimney with pots, dormer), flat roofs (parapet,
                       coping, stair housing, plant, water tank), church
                       tower + spire. `STYLES` style -> floors, roof,
                       glazing, wall; `WALLS` brick/concrete/render/stone,
                       `ROOFS` tiles/slate, each a surface material + palette.
                       Window glass is opaque Plastic: the Glass material
                       caps alpha at 0.45 and a dark pane vanished into brick.
  - `city_buildings_world.py` — world building styles merged into
                       `city_buildings.STYLES` (imported from the bottom of
                       city_buildings, whose `build_building` dispatches to
                       `BUILDERS`): mosque (drum + onion domes, minarets,
                       arched portal), Arabic (crenellated parapet,
                       mashrabiya, wind tower), Chinese (platform, red
                       columns, swept hip roof, ridge beasts), Japanese
                       (raised, timber frame, shoji, engawa, irimoya),
                       American (clapboard, shutters, porch), Indian
                       (jharokha, chhatris) and Pakistani (boundary wall +
                       gate, car porch, roof tank) houses; `PALETTES` give
                       each its own wall/roof colours. Same no-boolean rule.
  - **Map import** (2026-09-16, the user's request after hand-pasting
                       Dornden Drive through tool calls timed out):
                       `geo.py` (local tangent projection lat/lon <-> mm,
                       bbox from center + radius, slippy tiles, `urlopen`
                       with certifi — python.org's macOS Python has no CA
                       bundle), `geotiff.py` (pure-Python one-band GeoTIFF:
                       strips/tiles, none/Deflate/LZW/PackBits, predictors,
                       ModelTransformation or scale+tiepoint, GDAL nodata),
                       `osm_import.py` (Overpass fetch; roads clipped
                       Liang-Barsky; buildings keep their REAL outline as
                       `footprint` in the frame of their minimum-area
                       rectangle, so x/y/w/d/rz still drive the plan, pads
                       and dragging; style from tags; height from
                       height/building:levels; roof from roof:shape),
                       `lidar.py` (Environment Agency 1 m DTM + first-return
                       DSM over WCS, reprojected by the service via
                       subsettingCrs=EPSG:4326 so no OSGB maths;
                       `ground_grid`, `building_shape` = eaves as the median
                       DSM-DTM within 1.5 m of the outline and ridge as the
                       90th percentile — the roof pitch comes from both;
                       `detect_trees` = canopy local maxima >= 4 m off
                       building masks, crowns measured, suppressed by
                       crown), `aerial.py` (Esri tiles stitched and cropped
                       with QImage -> a Top reference image), `map_import.py`
                       (the pipeline + `save_spec`/`load_spec`). MCP
                       `import_map`; `build_city` gained `path` (load a spec
                       file), `save_to` and `detail`; both are file tools.
                       Every downloader is injectable, so
                       `tests/test_map_import.py` is offline (fake Overpass,
                       a fake WCS writing real GeoTIFFs).
  - `city_footprint.py` — buildings from an outline: walls = the polygon
                       extruded (counter-clockwise, so each edge's outside is
                       -y in its own frame, where window loops and the door
                       go); a pitched roof over the rectangle only when the
                       outline fills >= 80 % of it (a hull over an L
                       overhangs the inside corner), else a flat slab;
                       `roof_pitch` honoured. **Detail**: spec `detail`
                       auto/low/full, auto = low past 150
                       (`LOW_DETAIL_ABOVE`): low buildings are walls + roof
                       (`build_low`, any style), low trees a trunk + crown
                       (`city_trees.low_tree`, ~60 tris vs ~1500) — a
                       100-house import went from ~1M to ~110k triangles.
                       Measured ground is terrain kind `heights` (`rows`,
                       x0/y0/length/width) in `city_ground.Ground`
                       (`_init_measured`), surfaces grass/scree only.
  - `planetcraft.py` / `planetcraft_dialog.py` — **Send to PlanetCraft**
                       (File menu, MCP `send_to_planetcraft`, 2026-09-16):
                       the model or one node as a walking creature in the
                       KhervePlanet game — `creatures/<slug>.json` +
                       `index.json` (format `kherveCAD-creature` v1: kind
                       `kc_<slug>`, height/speed/health/wild, parts with
                       role, pivot, size, positions about the pivot, per-vertex
                       colours). Parts by NAME (`role_of`: head, tail,
                       wing L/R, leg front/back left/right — whole words, so
                       "Legend" is not a leg); unnamed legs by `_auto_legs`
                       (triangle CENTROIDS under 38 % of the height, split by
                       quadrant, only if the middle underneath is clear).
                       Axes game = (-x, z, y) — a proper rotation, so winding
                       survives; KherveCAD +x is the creature's LEFT. Joints:
                       leg top, head back-bottom (neck), tail front-top.
                       Real size (1 block = 1 m) unless `height`. The game side
                       is documented in KhervePlanet's CLAUDE.md.
  - `city_trees.py`  — trees (broadleaf, conifer, round, birch, poplar:
                       tapered Bark trunk, branches, Leaves clumps in two
                       greens; one loop per kind) and street lights. A
                       single-row loop value list is bracketed once more —
                       a lone vector is iterated element by element.
  - `city_items.py` / `city_dialog.py` — Library ▸ City ▸ **City
                       Builder…**: a 2D plan (Y-up, 0.5 m grid) to Generate
                       a layout, then place / drag / turn (R) / delete every
                       road (clicked point by point, vertex handles),
                       building, tree and light, with a side editor (style,
                       floors, size, walls + colour, roof + covering +
                       colour); Build = `city.apply`. Items set `_syncing`
                       BEFORE their flags: itemChange runs inside setPos in
                       the constructor, and an exception there aborted.
  - `treegen.py`     — **grown trees** (Qt-free, 2026-09-16): 13 species
                       (`SPECIES`: oak, maple, lime, birch, cherry, apple,
                       willow, poplar, pine, spruce, cypress, palm, shrub) as
                       a branching skeleton — bending tapered polylines,
                       children along the parent turned by the golden angle,
                       per-species depth/angle/ratio/gravity/crown envelope,
                       scaled so the top meets the height (`_fit_height`) —
                       each branch ONE closed tube (`Mesh.tube`, parallel
                       transport), leaves as closed flat diamonds (8 tris)
                       or tetrahedra (4) in a CLOUD round every twig
                       (`_foliage`; needles in sprays or tufts, willow
                       strands hanging, palm fronds of leaflets, fruit).
                       Written as `polyhedron` nodes point by point, NEVER
                       welded (coincident vertices of two pieces would pair
                       an edge three times and fail validation). `DETAIL`
                       high / medium / city: city grows foliage CLUMPS
                       (`Mesh.clump`, a jittered split octahedron,
                       `CITY_CLUMPS` max) with a few loose leaves — sparse
                       big leaves read as a bare tree at town scale.
                       `SEASONS` recolour deciduous leaves (Winter = bare).
                       Nothing grows below z = 0. `library_trees.py`: every
                       species as a Trees part (Young/Mature/Old, Variation
                       seed, season as the colour combo).
  - `library_lighting.py` — **Lighting & signals**: Victorian lamp (fluted
                       column, hexagonal lantern), LED single/double arm,
                       park globe lamp, bollard, wall lantern, floodlight
                       mast, traffic light on a pole / mast arm (open
                       visors — a solid hood hid the lens; the colour combo
                       picks the lit aspect, Emissive), pedestrian signal,
                       Belisha beacon, stop sign.
  - `library_park.py` — **Park & sport**: football pitch (mown stripes, every
                       marking as 2D polygons under ONE linear_extrude,
                       goals with nets of looped threads, corner flags),
                       tennis (surfaces, net, chain-link fence of loops),
                       basketball (markings scale with the court: a 15 m
                       court with full-size arcs crossed itself), lake /
                       pond (seeded shore, opaque glossy water — translucent
                       water showed the bed's fan triangles as streaks —
                       reeds, lily pads, jetty), playground, bench, picnic
                       table, bin, fountain, gazebo (`ring` = revolved
                       rectangle: a solid disc covered the water), and
                       `build_park`: facilities kept clear of the lake loop
                       and promenade, trees kept off everything (`keep`).
  - `terrain.py` / `library_landscape.py` — **Landscape**: `height_field`
                       (seeded value-noise fBm / ridged, per kind: hills,
                       mountain, cliff, valley, mesa, island, canyon, dunes;
                       noise in 70 m units) -> per-cell SURFACE by height and
                       slope (grass, woodland, scree, rock strata, snow,
                       sand, desert, riverbed) -> one closed COLUMN per
                       surface (`_column`: top tris, their shadow on the
                       base, walls down every boundary edge). A surface
                       touching itself at a corner only would pinch (one
                       vertical edge in four walls): `_unpinch` hands such
                       cells to a neighbour first. `from_heights` takes an
                       edited field (the city levels it). Boulders and
                       outcrops are `Mesh.clump`s.
  - `city_ground.py` — **a city ON a landscape**: spec `terrain` {kind,
                       height, seed, cells}. `Ground` builds the field over
                       the city's extent + margin and EDITS it: each road's
                       centre-line profile (smoothed along it) levels the
                       ground across its width, blending out over
                       `ROAD_BLEND`; each building gets a levelled pad at the
                       mean ground under its footprint (`pads`, a stone
                       foundation added by `city._stand_on_pad`); graded
                       cells are grassed (`paved`). `z(x, y)` places lights
                       (a 4th loop value), trees and props; roads are DRAPED
                       closed ribbons (`_ribbon`, rectangular tube wound
                       like `Mesh.tube`) — tarmac between two pavements —
                       and dash prisms. Terrain `roughness` 0..1
                       (`terrain.height_field`: 0.5 is the old ground exactly;
                       below it the features spread and the field is relaxed,
                       above it they tighten and hummocks are added); the
                       Ground section's Roughness % sets it and lists a map
                       import's ground as "Measured". The builder's Ground section picks
                       it and `CityCanvas.show_relief` shades it under the
                       plan.
  - City Builder, second pass (2026-09-16): any click on a piece SELECTS it
                       whatever the tool (Shift+click still places — placing
                       over a house was how it got lost), a `RotateHandle`
                       turns the selected piece through 0-360° (5°, Shift
                       15°; `city_items.wrap`), Shift+drag on empty ground
                       rubber-bands several (move / R / Delete act on all),
                       spec `props` places any Park / Lighting / Landscape /
                       Trees library part (`PropItem` = its real top view;
                       `planview` skips the merged outline past
                       `OUTLINE_FACES` — a whole park's took minutes) built
                       into a "City props" Object, and `city.sync_from_
                       document` reads back buildings/props moved or turned
                       in the main window (matched by their unique names;
                       every placed piece has a Turn, even at 0°).
  - `library_city_buildings.py` — Library ▸ City ▸ **Buildings**: every
                       `city_buildings.STYLES` style as a Part Library piece
                       (Small / Standard / Large footprint and floors from
                       `DEFAULT_SIZE` and the style's floor range; the look
                       combo picks the wall material), also offered by the
                       City Builder's library-piece tool.
  - `library_landmarks_world.py` — ten more Landmarks (2026-09-16): CN
                       Tower, Space Needle (hourglass leg pairs as paths),
                       Gateway Arch (the published weighted catenary in feet,
                       equilateral section hulled segment to segment), London
                       Eye (rim truss, cable spokes, 32 egg capsules, A-frame),
                       Atomium (cube on its vertex; spheres are sphere nodes —
                       Kit.sphere is a lumpy clump), Brandenburg Gate,
                       Parthenon (as it stands, unroofed), Stonehenge (fallen
                       stones), Sydney Opera House (`_shell`: hull of an arch
                       and a back point) and St Basil's (onion domes banded in
                       two colours by slicing `_onion`'s profile). The same
                       day Burj Khalifa (rounded Y wings round a hex core,
                       spiral setbacks, fins, terraces, glass top, sectioned
                       spire), Taipei 101 (segments with floor bands,
                       mullions, corner ornaments, ruyi) and the Shard (eight
                       shards to different heights, fractures, floor lines,
                       open spire lattice) were rebuilt in
                       library_skyscrapers.py. The vertical toolbar has a
                       City Builder button after House Builder
                       (`city_builder` tip). Light trees
                       (`city_trees.low_tree`) are a forked trunk with
                       foliage clumps / tiered cones, ~220 tris; a cone
                       ring must stay planar or the fan base winds wrong.
  - `landmark_kit.py` — `Kit`: bars, cable paths, boxes, turned boxes,
                       frustums, cones/pyramids, convex prisms and hulls
                       (`solid`, via `geom3d.convex_hull`), trusses and
                       braced faces, all appended into ONE closed
                       polyhedron per (colour, material) — a 2.7 km bridge
                       with thousands of members is a few nodes.
  - `library_bridges.py` / `library_landmarks.py` /
    `library_skyscrapers.py` — famous structures from their PUBLISHED
                       dimensions (the user's choice, 2026-09-16: no
                       reference blueprints), at true size with model
                       scales (`_scaled` wraps a scale node): Golden Gate,
                       Tower, Brooklyn and Sydney Harbour bridges; Eiffel
                       Tower, Statue of Liberty, Big Ben, Great Pyramid,
                       Pisa, Arc de Triomphe, Colosseum, Taj Mahal (onion
                       domes are revolved profiles, `_onion`); Empire State,
                       Chrysler, One WTC (square-to-rotated-square hull),
                       Burj Khalifa, Petronas, Taipei 101, Shanghai Tower
                       (nine twisted, tapering linear_extrude zones kept
                       continuous by rotating each zone's base) and the
                       Shard. Library ▸ City sections, and City Builder
                       props.
  - **Surface materials** (`glrender.SURFACES`, 2026-09-16): Brick,
                       Concrete, Render, Roof tiles, Slate, Stone, Bark,
                       Leaves are `model.MATERIALS` drawn by the fragment
                       shader from world millimetres (`surface()`: stretcher
                       bond, board-marked concrete, pantiles, Voronoi stone,
                       ...) — zero triangles. The id rides the gloss-power
                       slot as a negative number; joints are antialiased
                       over a pixel (`joint`) and the pattern fades to its
                       mean once finer than ~a pixel (moire). The painter
                       draws them as Matte (`view3d.SURFACE_STYLES`).
  - `house_items.py` — the floor-plan canvas's QGraphicsItems, drawn
                       like an architect's plan (Sep 2026 rework — the
                       first canvas had 400 mm tan squares for every
                       piece, no doors or windows, and read as noise):
                       `RoomItem` (draggable floor painted INSIDE the
                       walls, `inset` = half the wall; moving it shifts
                       its furniture too; eight `Handle`s, shown on the
                       selected room only, that resize it, both snapped
                       to `GRID` so adjacent rooms stay wall-exact;
                       roles are COMPASS sides in the Y-up frame,
                       `HANDLE_ROLES`: naming them from Qt's y-down
                       `topLeft()` once put the handle drawn at the
                       bottom in charge of the top edge; the selected
                       room is raised so a shared corner grabs ITS
                       handle; its caption — name, size, m² — is a
                       separate top-level `Label` at the centre, z above
                       the furniture, since a child label hid under
                       whatever stood against its wall), `WallsItem`
                       (every `collect_walls` wall at its thickness, the
                       openings' `_opening_spans` left as gaps —
                       `wall_pieces`; under the rooms, click-through,
                       recomputed each paint so it follows drags),
                       `OpeningItem` (a door's leaf + swing arc or a
                       window's frame + glass line, in a local frame set
                       by `setTransform`: x along the side, y INWARD;
                       dragging slides it along its wall and hops to the
                       room's nearest side, `nearest_side`),
                       `FurnitureItem` (the part's REAL top view —
                       `planview.part_view`, a cached coloured picture
                       plus outline — turned by `setRotation(rz)`, which
                       is CCW in the Y-up scene like OpenSCAD's rz;
                       double-click turns 90°, Shift the other way,
                       `rotate_by` keeps (-180, 180]; its name `Label`
                       shows only when it fits) and `GardenItem`.
                       Self-contained: every drag writes straight back
                       into the `house` dataclass it represents and
                       reports via callbacks, no CadNode/DocumentModel
                       coupling, unlike view2d.py's handle-drag items
                       which are tied to the document tree.
  - `planview.py`    — **coloured projected faces** for 2D views:
                       `plan_faces(colored, plane, cut)` turns
                       `mesh.tessellate_colored` (now with a `detail`
                       cap) into painter-ordered (polygon, QColor) pairs
                       — edge-on faces dropped, shaded by how squarely
                       they face the viewer, sorted far -> near along
                       the viewing axis (`DEPTH`); `paint_faces` draws
                       them (a same-colour hairline hides seams);
                       `part_view` renders a library part's top view once
                       (`lru_cache`) for the House Builder.
  - `house_dialog.py` — Library ▸ **House Builder…**: a non-modal
                       window (one per main window, `open_builder`) with
                       its OWN 2D floor-plan canvas (`FloorCanvas`, Y-up
                       like view2d, an adaptive grid painted in
                       `drawBackground`, drag on empty space pans) —
                       separate from the document's own 2D
                       sketch/assembly view. The left side is the steps
                       in order, in a scroll area: **1 Floor** (combo +
                       ceiling height / wall / slab), **2 Rooms** (list
                       captioned with sizes + name, size, position),
                       **3 In <room>** (one list of its doors, windows
                       and furniture) and **4 Selected item** (a stacked
                       editor: an opening's type/wall/offset/size/sill,
                       a piece's size and colour combos from the Part
                       Library spec — `_fill_look_combos`, dims rebuilt
                       by `house.part_dims` — its position IN the room
                       and rotation with ±90° buttons). Lengths are
                       `MetreSpin`s: metres on screen, mm in the model,
                       keyboard tracking off. A toolbar + hint line sit
                       over the plan; Delete removes, R turns. The list
                       and the plan follow each other (`_pick_*` from a
                       click, `_*_dragged` from a drag, `canvas.select`
                       back) with `quiet()` stopping echoes; a piece
                       dropped in another room moves to that room's list
                       (`_furniture_released`). Add furniture… is a
                       searchable catalogue opened on the section the
                       room's name suggests (`_guess_category`). The
                       garden (checkbox + width/depth/gap) is drawn where
                       Build puts it. The window opens on the document's
                       house (`load_from_document`: `model.house`, from
                       an earlier Build, the build_house MCP tool —
                       which also refreshes an open builder — or a
                       saved .kcad), framed by `canvas.fit`; reopening
                       skips the reload when that design is already the
                       one shown, so unbuilt edits survive. **Build**
                       (`house.apply`) replaces the house built last
                       time, so hand edits update it in place.
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
  - `lego_builder.py`— Library ▸ **Lego Builder…** (reworked
                       2026-09-18, the user: placing by clicking in 3D
                       was "not user friendly"): a window with a palette
                       of EVERY piece (Brick / Plate / Tile of any size +
                       every `library_lego_parts` item, quarter turns —
                       `piece_node(part=, turn=)` rotates about the group
                       origin and shifts by `_TURN_SHIFT` so the turned
                       footprint still starts at (i, j)), colour, a LEVEL
                       (one plate a level above `ground`: the top of a
                       baseplate lying at z = 0) and the **plan**
                       (`lego_plan.py`): the stud grid at that level —
                       pieces starting there in colour, cells a lower
                       piece still fills grey-hatched (`layer`), studs to
                       build on as circles, air tinted by what is below
                       (`beneath`); the piece follows the cursor green /
                       red (`can_place`: no collision, and studs beneath,
                       a piece above or the ground), a 3D highlight ghost
                       too. Left click places, right click erases, wheel /
                       ▲▼ level, R turns. "Click in 3D view" keeps the
                       old pick mode (`target`). A piece is a Group at its
                       grid corner with `params["lego"]` = {kind, nx, ny,
                       h, colour, i, j (+ part, turn)}; `refresh_studs`
                       drops covered studs of bricks/plates only (Library
                       pieces stay as made). `library_lego_parts.shape`
                       gives each piece's footprint and height.
                       **Toolbar** (same day, the user: "icons like mouse
                       icons"): Select / Move / Rotate / Add piece / Erase
                       down the plan's left edge, Turn / Copy / Delete,
                       level ▼▲, Zoom in / out / Fit across the top; wheel
                       zooms about the cursor, middle drag pans, arrows
                       move the selected piece, Shift+PgUp/PgDn lift it.
                       Moves go through `replace_piece` (rebuilt at its
                       index, `can_place(ignore=)`). Baseplates 16-96
                       studs (`BASEPLATE_SIZES`) live in their OWN Object
                       beside the build (`BASE_KEY`, `base_object`; the
                       build carries `keep_empty`, which `validate`
                       honours for an Object), studs one nested loop of
                       8-sided cylinders, never culled — so the plate's
                       mesh never changes: a click on 96 x 96 went 1.5 s
                       -> 0.3 s. Two general fixes came with it: the mesh
                       cache keeps one slot per (Object, $fn, detail) —
                       the 2D view's detail pass and the 3D pass evicted
                       each other every change — and view2d caches a
                       part's projected outline + faces by content
                       (`_PART_SHAPES`, `_fingerprint`): one edit rebuilds
                       the 2D scene several times.
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
  - `explode.py`     — **exploded views**, a display only (the tree is
                       untouched): `plan` picks what comes apart — the
                       nearest assembly holding the SELECTION, else the
                       scope's parts, looking through a lone Group /
                       Object / colour (a library part or Make Object
                       wraps a whole assembly in one; such a document
                       used to have "one part" and the view silently did
                       nothing). Only `STRUCTURAL` containers are opened
                       — never a boolean or loop. Each part is
                       tessellated alone through the normal path (NOT a
                       selection pass: those bypass the Object cache and
                       exact meshes) and placed by `mesh.node_matrix` of
                       the containers above; the rest is drawn with the
                       group hidden. `highlight` moves the tint with its
                       part; the status bar says when nothing can come
                       apart; `showing()` (pictures) ignores the
                       selection. `offsets` moves each along
                       assembly-centre -> part-centre times `amount`
                       (Radial, or one axis X/Y/Z), `exploded_colored`
                       is what `_refresh_preview` draws while
                       View ▸ Exploded View is on (Ctrl+Shift+X; the
                       whole-document OpenSCAD render is cancelled
                       then, it would land un-exploded). `showing(window)`
                       switches it on for a picture: Export PNG's
                       Exploded box, the Printables bundle's exploded
                       stills (default for >= 2 parts), MCP
                       `set_render_options explode/explode_mode` and
                       `export_document exploded`.
  - `objecttab.py`   — the **Object tab**, where parts are **defined**
                       and edited (the part/assembly split — anchors and
                       mates are a Main-tab concern, not here):
                       `ObjectTab` (dropdown of the document's Objects +
                       "New", Rename, and **To Main** = insert an
                       instance into the assembly) and `ComponentTree`
                       (the same tree widget rooted at the **active
                       Object**; the dropdown lists **every** Object via
                       `model.all_components()`, nested ones included —
                       an imported `color(...) Pot();` wraps its module
                       — and the toolbar is icons only: New, Rename,
                       Delete (`model.delete_component`: the definition
                       and every instance, one undo step) and To Main; `SHOWS_INSERT_OBJECT = False`, since an
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
                       Object**, and for a single
                       Object: Edit in Object tab (also double-click),
                       Anchors (add-by-pick / set origin / remove) and
                       Attach/Detach; drag & drop reparent/reorder.
                       Tab order: **Main | Object | Variables | Code**
                       (the Masters tab was retired 2026-09-19 — see
                       `retire_masters`). The **Variables** sheet is scoped
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
                       `build_insert_menu` lays every tool of both bars
                       out as the Insert menu (2D Shapes, 3D Solids, one
                       submenu per family, Measure, Assembly, Code &
                       files) from these same tables.
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
  - `userguide_content.py` — the 23 chapters, `(anchor, title, html)`.
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
                       The 3D bar also carries **Exploded View** and
                       **Cut Through** as `MenuButton`s
                       (`add_menu_button`, added by
                       `MainWindow._add_view_toggles`): a click on the
                       icon switches the feature, the painted chevron
                       opens a menu of the View menu's OWN actions, so
                       ticks never disagree; the buttons follow the
                       state whoever changes it.
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
                       hatching (`PartItem`). An overview part is
                       painted in its **own colours**, faces far ->
                       near (`planview.plan_faces`, `PartItem._faces`;
                       the path stays its shape and hit area) — one
                       flat translucent fill made a house a single tan
                       rectangle — and a House Builder floor is cut at
                       its slab + `house.PLAN_CUT` in the Top view
                       (`_plan_cut`, found by name in `model.house`),
                       so its rooms show, not its roof. The scene rect
                       is NOT fixed: `fit_scene_rect` (after every
                       rebuild, zoom and fit) grows it to the drawing
                       plus its own span and the visible area — a fixed
                       4 m square left most of a 14 m house off-scene,
                       so Fit could not frame it. The grid coarsens by
                       5x until lines are 6 px apart (it coarsened once
                       and took 1.6 s a frame zoomed out). Dropping
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
  - **Real scale** (2026-09-18, the user: "the scale bar has to be
                       adjusted for planets or maps"): `DocumentModel.
                       real_scale` is the N of 1 : N — how many times
                       smaller than life the model is (a 60 mm Earth is
                       1 : 212 600 000; 1 = life size, < 1 enlarged). A
                       LABEL like the unit: saved (.kcad v12), in the undo
                       snapshot, reset by New, `scale_changed` signal, Edit
                       ▸ Document Scale (1 : N)… (`units_ui.choose_scale`,
                       "1:250000000", "25:1"), MCP `set_render_options
                       real_scale` and `get_document_info` `scale`. Every
                       planet / moon part's `prepare(model, dims)` sets it
                       from the chosen diameter in an EMPTY document
                       (`library_solar.prepare_scale`) and leaves a
                       document that holds something alone, with a note —
                       like crystals switching an empty document to nm.
                       `library.prepare_document` now hands a two-argument
                       prepare the dims (default size's when none).
                       `units.readable` says a length in the largest metric
                       unit that keeps it >= 1, never smaller than the
                       document's (a true-size map's 200000 mm reads 200 m,
                       a planet's 5e9 mm 5000 km, 0.5 µm stays); `grouped`
                       writes thin-space thousands; `ratio_text` /
                       `parse_ratio` the ratio. (`tidy(x, 0)` strips an
                       integer's own trailing zeros — 212600000 came out
                       2126 — so `grouped` writes whole numbers itself.)
  - `scalebar.py`    — the 3D view's **scale bar** (View ▸ 3D Scale Bar,
                       QSettings `render_scale_bar`, default on, MCP
                       `set_render_options scale_bar`): the shortest 1-2-5
                       × 10^k length drawn 60-170 px long bottom-left, in
                       the document's unit (`View3D.unit`, kept in step by
                       `units_ui.changed`). Pixels per unit are `_focal() /
                       distance` — true at the ORBIT CENTRE in perspective
                       (a perspective picture has no single scale) and
                       everywhere in orthographic; a test pins it to
                       `_project`. Not drawn in clean pictures; the
                       snapshot twin copies it.
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
  - `mesh.py` 2D content (fixed 2026-09-13): `collect_outlines` maps
                       outlines through every 2D **translate / rotate /
                       scale / mirror** (`_transformed_outlines`, the same
                       `mat_*` builders as 3D) — before, all four were
                       dropped between an extrude and its shapes (only
                       translates the importer folded into x/y survived),
                       so a card's index turned for the opposite corner
                       landed on the first. Outlines arrive as SOLIDS
                       (CCW) and HOLES (CW): `_oriented` normalises shapes
                       and makes a glyph's counters holes, a 2D
                       `difference` turns its subtrahends round
                       (`_difference_outlines`), `outline_regions` gives
                       each solid its holes and both extruders build walls
                       for both and cap with `cutaway.fill` (even-odd) —
                       an O and an outline-minus-inset pot were extruded
                       filled. Hole-free shapes keep the ear-clip caps;
                       union pieces stay separate solids.
  - `csg.py`         — **exact preview booleans** (2026-09-19, the
                       first of the Blender-inspired tools the user
                       picked): `difference` / `intersection` /
                       `minkowski` and a fillet's convex cuts go
                       through **Manifold** (`manifold3d`, Apache 2.0 —
                       the library OpenSCAD itself renders with), so the
                       preview cuts holes at once instead of showing the
                       first operand. Each operand's rows are welded
                       (`WELD`), split into solids and unioned (two
                       overlapping cubes are edge-manifold but not a
                       solid); colour index + selection flag ride as
                       vertex properties, so a cut face wears the tool's
                       colour like OpenSCAD's. An operand that is not a
                       closed solid (a flat 2D shape, an open scan) makes
                       `boolean` return None: the old approximation, and
                       the node goes in `FAILED`. `mesh.approximates`
                       (not `uses_booleans`) is what the warnings, the
                       badge and `needs_exact` ask — a part Manifold cut
                       is no longer sent to OpenSCAD for an exact mesh.
                       Optional: absent, everything is as before. The
                       spec keeps numpy for it.
  - `decimate.py`    — **Decimate** (Blender's Decimate ▸ Collapse,
                       2026-09-19): the `decimate` wrapper (Deform
                       family, baked in `_BAKED`: `kcad_decimate(ratio=,
                       tolerance=, points=, faces=) { children }`) keeps
                       `ratio` of the triangles, or collapses whatever
                       moves the surface less than `tolerance` mm.
                       Quadric edge collapse (Garland-Heckbert, the
                       algorithm behind Blender's), unweighted quadrics
                       so a cost is mm²; the **link condition** and a
                       **fold** check keep a closed solid closed, open
                       borders are locked. Past `PREPASS_ABOVE` triangles
                       Manifold's `simplify` (C++) takes it to 3x the
                       target first and the Python collapse finishes
                       (135k -> 13.5k in 1.5 s, 99.95 % of the volume;
                       Manifold alone kept less); a tolerance request is
                       Manifold's alone when it is there. With csg.py
                       the deformers now also accept the booleans
                       Manifold cuts (`bake._inexact`), so a threaded
                       part can be decimated.
  - `shrinkwrap.py`  — **Shrinkwrap** (Blender's modifier, 2026-09-19):
                       the `shrinkwrap` wrapper (Deform family, baked:
                       `kcad_shrinkwrap(mode=, axis=, keep=, offset=,
                       detail=, show_target=, points=, faces=) { piece;
                       target... }`) moves its FIRST child's vertices onto
                       the rest — `nearest` point or `project` (own normal
                       or ±x/y/z, ray both ways unless signed) — then
                       `offset` out along the target's normal; `keep`
                       outside (default: only what sinks in or sits nearer
                       than the offset moves — clothes, caps, decals),
                       all, inside. The target is drawn too by default
                       (the helper ends `children([1 : $children - 1])`),
                       as Blender leaves it in the scene. Closest points:
                       a grid of the target's triangles searched per cell
                       ring by ring (outside ring r is >= r cells away, so
                       a hit that near is final), Ericson's closest point
                       on a triangle in numpy; inside = ray parity; rays
                       are Manifold's `ray_cast` (distance = FRACTION of
                       the segment) or numpy Moller-Trumbore. Vertices are
                       welded first, so a closed piece stays closed.
  - `bevel.py`       — **Bevel** (Blender's Bevel modifier, 2026-09-19;
                       Finish family beside Fillet, baked:
                       `kcad_bevel(width=, segments=, profile=, angle=,
                       which=, points=, faces=) { children }`): EVERY
                       crease sharper than `angle` — convex, concave or
                       both — no picking. Reuses fillet.py's creases,
                       chains and strips (`strip(section=)`), with
                       Blender's superellipse `profile` (e = 2^(1 + (p -
                       0.5)/0.25): 0.5 the true rolling-ball arc, 0.25 a
                       chamfer) in the affine frame of the two tangent
                       points. **Corners** where three bevelled creases of
                       one kind meet: the slab between the faces and their
                       offset planes minus the ball tangent to all three
                       (round: exactly the rolling-ball blend — 20 mm box,
                       r 2: 7804.8 vs 7804.7 analytic) or the affine
                       superellipsoid (chamfer: Blender's corner triangle
                       x+y+z = 2w); the slab is grown about the BALL
                       CENTRE (grown about its middle it cut slivers off
                       what stays). A vertex where exactly two creases of
                       one kind meet is chained THROUGH (`fillet.chain
                       through=`, `HAIRPIN`), so a pocket's rim is one
                       mitred loop; a concave filler is trimmed a setback
                       short of an end where bevelled convex creases meet
                       it (`_trim_ends`), and fills go on before cuts, so
                       no post stands up through the rim. Manifold does
                       the booleans; without it validation says so. A
                       morphological opening (erode + dilate by a ball)
                       was tried first: 64 s and 9M triangles for a plate
                       with four holes — Manifold's minkowski of a
                       non-convex solid scales with the face product.
  - `remesh.py`      — **Voxel remesh** (Blender's Remesh, 2026-09-19;
                       Deform family, baked `kcad_remesh(voxel=, snap=,
                       points=, faces=) { children }`): any soup back to
                       ONE closed solid. Inside = WINDING number up each
                       grid column (overlaps union, inner walls cancel, a
                       small hole in a scan does not flood), numpy
                       (triangle, column) pairs; occupancy averaged over
                       2x2x2 and meshed by `sdf.mesh_values` (split out of
                       `polygonize`); `snap` moves each vertex to the
                       nearest original point (shrinkwrap.Target) within
                       1.5 cells. check_printability's watertight failure
                       now names it as the fix.
  - `heatmap.py` / `heatmap_ui.py` — **heat maps** (2026-09-19): the
                       print check painted ON the part — `thickness` (a
                       ray from each face centre straight in, Manifold
                       ray_cast ~4 µs, else the print check's grid
                       sampled; red < min wall, orange < 2x, yellow, green,
                       teal, blue; grey = never came out) and `overhang`
                       (red past the limit, yellow within 10°, blue on
                       the plate). Analyse ▸ Heat Map; state on the window
                       (`_heatmap`, `_heat_stats`), painted in
                       `_refresh_preview` AND `_engine_mesh` (a whole-
                       document render would wipe it). MCP
                       `set_render_options heatmap / heat_min_wall /
                       heat_overhang` returns the stats; render_view shows
                       it.
  - `ik.py` / `ik_ui.py` — **inverse kinematics** (2026-09-19): CCD
                       (each joint, last to first, turns the effector
                       toward the target, <= `MAX_STEP`°), the world
                       rotation written back as the joint's own Euler
                       angles R' = P^-1 Q P R and decomposed like
                       rotate([x,y,z]) = Rz Ry Rx. `HumanRig` (bones of
                       the `human` rig; effectors left_hand = wrist joint
                       over upperarm01 + lowerarm01, feet, head, or a bone;
                       world point = bone matrix · joint, then the rest
                       frame's stand/scale, then the node's placement) and
                       `JointRig` (the `joint` nodes above a part, within
                       min/max). `reach` writes pose rows / rx ry rz. Tree
                       right-click ▸ Reach (IK)… then click targets; MCP
                       `reach` (target, target_node, offset, effector,
                       chain, point; `miss` — never "error", which means a
                       failed call). `mesh.node_matrix` now knows `joint`
                       (ancestor_matrix ignored joints before).
  - `wireframe.py`   — **Wireframe** (Blender's modifier, 2026-09-19;
                       Deform family, baked `kcad_wireframe(thickness=,
                       sides=, angle=, joints=)`): every REAL edge (faces
                       meeting past `angle`°, so a flat face's diagonal is
                       skipped) a Manifold cylinder, a ball per corner
                       (radius / cos(π/segments) so the faceted ball holds
                       every cap), one batch union. Where many struts cross
                       symmetrically the union leaves 0.0007 µm edges:
                       each strut's radius varies by < 0.1 % and the result
                       is welded at 4 digits (`weld_tiny`, what codegen
                       writes anyway) — watertight. `MAX_STRUTS` 20000.
  - `physics.py`     — **drop & settle** (2026-09-19; no pybullet
                       wheel for Python 3.14): lowest part first, it TIPS
                       quasi-statically (support = convex hull points at
                       the floor; COM outside that footprint -> roll over
                       the nearest support edge by the angle that brings
                       the next hull vertex down; a COM balanced exactly
                       over a point or line still tips — unstable), then
                       falls until Manifold rays (down from it, up from
                       the parts placed) meet something. The move becomes
                       the part's placement L' = A^-1 M A L
                       (`mates.ensure_part` makes it movable). Tree ▸
                       Drop (gravity); MCP `drop_parts`. Tipping is on the
                       floor only — a part resting on another does not
                       slide or roll off it.
  - `cloth.py`       — **Cloth** (Blender's Cloth, 2026-09-19; Character
                       family, baked `kcad_cloth(lift=, detail=,
                       thickness=, steps=, substeps=, offset=, friction=,
                       floor=, pins=, show_target=) { 2D shape; colliders
                       }`). The cloth is the FIRST child as a 2D shape,
                       meshed as ONE sheet (`sheet`: grid triangles inside
                       the outline, border vertices snapped onto it) — a
                       thin 3D plate failed: its skins meet only at the
                       rim and the top one fell through the bottom — and
                       thickened after (`thicken`: both skins + rim,
                       watertight). Position-based dynamics with SMALL
                       STEPS (each frame `substeps` substeps of one pass;
                       many passes of one step let a sheet hang 2-6x
                       long), constraints Gauss-Seidel by EDGE COLOUR
                       (`colour_edges`: each colour one exact numpy pass;
                       Jacobi stretched 4x), collisions against a
                       winding-number voxel grid grown by the offset
                       (`Colliders.close`, one lookup) then pushed back
                       along the vertex's OWN PATH (Manifold ray, the face
                       it came through — the nearest face threw a vertex
                       by a table's edge sideways and the cloth slid off),
                       velocity capped at half an edge per substep, and
                       Macklin's position-based static/kinetic friction
                       with a contact band (a resting vertex a hair above
                       the surface missed its friction and the cloth
                       crept). `SMOOTH_PASSES` Laplacian passes settle
                       the crumple. No self-collision, and collision is
                       per vertex: a sharp collider edge can show between
                       two cloth vertices (finer `detail` or larger
                       `offset`). Table drape ~3 s, baked + cached.
  - `faceedit.py` / `faceedit_ui.py` — **direct face editing**
                       (2026-09-19, the roadmap's push/pull; Finish
                       family). `push_pull` (baked; `pushes` rows [x, y, z,
                       distance, inset] — NOT `faces`, every baked helper
                       already has a faces argument): the flat face at the
                       point (nearest triangle grown over coplanar
                       neighbours, found by geometry so it survives edits)
                       -> Manifold CrossSection (holes kept), offset for the
                       inset, extruded out (union) or in (cut). Rows apply
                       IN ORDER on the running result, so a raised top can
                       be raised again. `bisect` (the knife): split_by_plane,
                       keep above / below / both pulled `gap` apart.
                       Toolbar Push / pull wraps and starts a face pick
                       (world click -> the node's frame); MCP
                       `push_pull_face` (world point from probe_surface).
                       `csg.to_triangles` now welds at 10 nm: Manifold
                       leaves nanometre edges where a solid overlaps a face
                       by a hair. The baked-node importer reads node-
                       specific choices BEFORE the generic x/y/z one — it
                       had reset bevel `which`, shrinkwrap `keep`/`mode`.
  - Subdivide with creases (2026-09-19): `subdivide` gained `sharp`
                       (default 0 = as before): `deform.crease_keys` marks
                       edges whose faces meet past it, `_loop_once` treats
                       them like borders (Hoppe 1994: midpoint edge
                       points, a two-crease vertex moves along them, a
                       three-crease corner stays) and hands each crease's
                       halves on — a cube stays exactly a cube, a
                       cylinder's sides round while its rims stay flat.
                       Manifold's smooth_out was tried first: it shrinks
                       even its own cube with every edge "sharp" (6667 of
                       8000 mm³).
  - `photoreal.py` / `photoreal_ui.py` — **photoreal renders** through
                       Blender Cycles when installed (2026-09-19; nothing
                       bundled — found via KHERVECAD_BLENDER, PATH, the
                       usual folders): the view's coloured rows -> one GLB
                       (metres, Y up; a PBR material per colour from
                       `MATERIALS`: Metal metallic, Glass
                       KHR_materials_transmission, Emissive strength), a
                       generated bpy script (the view's yaw / pitch /
                       distance / target and its 45° FOV — view3d's focal
                       is 1.2 x the short side — or a framed preset; sun +
                       sky, a studio floor or shadow catcher, AgX, Cycles
                       denoised or EEVEE), `blender -b --factory-startup`.
                       File ▸ Render Photo (Blender)…; MCP `render_photo`
                       (read-only; a file tool when given `path`);
                       get_document_info reports `blender`. Tested with a
                       stand-in blender that checks the GLB and writes a
                       PNG — the bpy script itself is only compile-checked
                       here (no Blender on the dev Mac).
  - `engine.py`      — OpenSCAD integration: binary discovery,
                       debounced background renders via QProcess,
                       STL parse (binary + ASCII) and STL write.
                       **Every run is on the Manifold backend** when the
                       binary has it: `openscad_args` builds all three
                       launches (document render, per-part render,
                       export) and `backend_args` reads the switch off
                       `--help` once per binary — `--backend=Manifold`
                       (recent builds), `--enable=manifold` (2024-era
                       snapshots), nothing on 2021.01 (an unknown flag
                       would fail every render). CGAL had taken 2 min
                       43 s over the Mini's intersected body that
                       Manifold renders in 0.8 s, so its exact preview
                       never arrived. `KHERVECAD_OPENSCAD_BACKEND=cgal`
                       forces the old backend; `ScadEngine.backend` and
                       get_document_info's `openscad.backend` report it
                       (the note warns when only CGAL is there). Tests
                       with a fake sleeping binary set that variable, so
                       the `--help` probe never waits on them.
  - `printables.py`  — **File ▸ Publish to Printables…** and the
                       `publish_to_printables` MCP tool share one
                       builder: STL / 3MF / .scad / .kcad exports
                       (plus `<stem>-<object>.stl` per part at its
                       own origin, via `subtree_scad` /
                       `anchors.local_tris`, when there are 2+ —
                       `print_parts` finds them: the outermost Object
                       at any depth, since an imported `color(...)
                       Pot();` nests it, and the definition behind an
                       instance, once however often it is placed),
                       preview stills from **three-quarter angles** —
                       `DEFAULT_VIEWS` = `ISO_VIEWS` (mcp_schema): the
                       isometric from all four corners, three-quarter
                       front, bird's-eye, low angle, underside; the
                       square-on `ORTHO_VIEWS` stay askable by name —
                       the front-right isometric first and larger since
                       Printables makes the first image the cover.
                       **Every still is painted by the 3D view**
                       (`pngexport.render`, an offscreen snapshot, never
                       the user's camera) with the user's colours,
                       materials, style, lighting, platform & shadow,
                       cavity and edges — OpenSCAD's own `--render`
                       PNG (one flat colour scheme) looked nothing like
                       the screen. The geometry is still exact: the
                       bundle first waits for the engine to go idle
                       (`engine.wait_until_idle`, `RENDER_WAIT_S`), so
                       every part's exact mesh is in the view. Pictures
                       render at `pngexport.pixel_ratio` (the pane's
                       size × ratio, Retina-style: `View3D.snapshot(
                       pixel_ratio=)` scales the painter and grows the
                       GL framebuffer) so lines, shadow and platform
                       keep the screen's proportions. Cameras come from
                       ONE table, `engine.CAMERA_ROTATIONS`
                       (`engine.view_angles`: yaw = rz - 90, pitch =
                       90 - rx); a test pins `View3D.VIEWS` to it (its
                       "Isometric" once looked from the back-right). A
                       generated or
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
                       actually shipped. Every fixed sentence (summary,
                       opening, parameter intro, print notes, credit)
                       comes in several phrasings picked per model by
                       `variant_for(title)` (crc32 — the same model
                       always reads the same, different models differ,
                       each section hashed with its own salt in `_pick`);
                       the dialog's Regenerate steps to the next variant.
                       The `MADE WITH` heading and the tools URL never
                       vary: they are how the credit is found once.
  - `drawing.py`     — **2D engineering drawings** (Qt-free): `VIEWS`
                       (third-angle Front/Top/Right/…, an isometric)
                       as (right, up, forward); `view_lines` takes the
                       mesh's creases + borders + that view's
                       silhouette, dedupes edges that project onto the
                       same line (front-most wins), and finds hidden
                       runs with a `DepthGrid` — a pure-Python
                       z-buffer at `GRID` cells across the model —
                       sampling `SAMPLES` points per edge (one-sample
                       runs are grid flicker, folded away, and runs
                       under 0.2 % of the model join their neighbour).
                       The grid also records the NEAREST TRIANGLE per
                       cell: an edge is never hidden by its own faces,
                       their neighbours or the smooth surface around
                       them (`surroundings`, crease-free rings) — at a
                       curved silhouette the facets are seen edge-on
                       and the cell beside the edge lands a facet or
                       two round, a whole tolerance in front, which
                       drew cylinder sides dashed or dropped them.
                       Hidden stretches lying on a visible line are
                       dropped (`_uncovered` — an odd-segment rim's
                       back half is no mirror of its front, so it
                       survived the dedupe as dashes over a solid line).
                       Also Qt-free helpers the Blueprint stands on:
                       `find_circles` (round edges seen end-on: chains
                       of equal chords, `MAX_TURN` rejects a hex nut),
                       `merge_collinear`, `clip_to_circle`,
                       `hatch_segments` (even-odd), `title_block_cells`
                       / `TITLE_FIELDS` and `projection_symbol`; `layout`
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
  - `drawing_dialog.py` — `make_layout`, the quick sheet the
                       `export_drawing` MCP tool draws when the
                       document has no Blueprint (the selection, else
                       the render scope). Its dialog is gone: File ▸
                       Blueprint replaced it.
  - `blueprint.py`   — **File ▸ Blueprint… (Ctrl+Shift+D, toolbar)**:
                       the 2D engineering drawing in its own non-modal
                       window (one per main window, `open_blueprint`).
                       `Geometry` = the 3D view's mesh (after
                       `engine.wait_until_idle`, so exact parts), each
                       view's lines/circles projected once and cached.
                       `BlueprintScene` (usable offscreen:
                       `export_saved` is the MCP path) holds frame,
                       title block, views and notes; `state()` /
                       `load_state()` is the dict saved as
                       `DocumentModel.drawing` (.kcad "drawing",
                       FORMAT_VERSION 8; kept OUT of the model's undo
                       snapshots — the window has its own QUndoStack of
                       whole-sheet states, `_StateCommand`). Nothing
                       may be lost or half-applied: `restore` (undo/
                       redo) sets `_restoring` so no commit is pushed
                       mid-undo, drops a pending Properties edit and
                       resets the tool (a tool once kept clicking into
                       a replaced view); `flush_pending` applies typed
                       text before every save (main window, MCP
                       save_document, Printables) and on close; a moved
                       free item (text, sketch, parts list) commits on
                       release; views are not pixmap-cached (a 60x zoom
                       made each cache hundreds of MB).
                       `tests/test_blueprint_tools.py` drives every tool
                       with real mouse events — create, edit each
                       Properties editor, double-click, drag, Delete,
                       undo/redo — under an exception collector. First
                       open: `new_layout` (Front/Top/Right/Isometric)
                       + `arrange` (third-angle, largest standard
                       scale fitting `usable_rect`) + `auto_dimension`
                       (overall sizes; holes grouped "3× Ø6" with
                       leaders pointing off the part, `_leader`; centre
                       marks; re-running replaces only `auto` notes).
                       Top/Bottom share Front's x, Right/Left/Back its
                       y (`constrain_view`, `view_moved` carries them).
                       Sections draw a `CuttingLineItem` on their
                       parent view, details a `DetailMarkItem`.
                       Title block mass = volume × `analysis.MATERIALS`
                       density unless typed; material/company/author
                       remembered in QSettings `blueprint/*` (tests
                       neutralise those keys in conftest).
  - `blueprint_items.py` — the sheet's QGraphicsItems. Every note is
                       PRIMITIVES (line/poly/circle/arc/text in item
                       coordinates) painted by `paint_prims` and
                       written by the DXF exporter — one source, so
                       screen, PDF and DXF agree. Text is drawn as
                       outlines (`text_path`, cap height in mm), not
                       fonts. Anchored notes are CHILDREN of their
                       `ViewItem` and store MODEL (u, v) points, so a
                       dimension's number is the model's distance at
                       any scale; dragging moves the label (`drag_to`),
                       never the anchor. `DimensionItem` (horizontal /
                       vertical / aligned / diameter / radius / angle,
                       ± or stacked tolerances), leader, balloon,
                       datum, `FcfItem` (ISO 1101 symbols drawn as
                       vectors, `gdt_symbol`), surface finish, centre
                       mark/line, text, sketch, `BomItem`, plus
                       `FrameItem` (zones, centring marks) and
                       `TitleBlockItem`. `Look` holds the style (white
                       paper / blueprint blue) and ISO line weights.
  - `blueprint_tools.py` — snapping (`ViewSnap`: endpoints, midpoints,
                       centres, quadrants, nearest edge, round edges,
                       cell grid) with an on-screen `SnapMarker`, and
                       the click-sequence tools (smart / H / V /
                       aligned / Ø / R / angle dimensions, tagged
                       notes, finish, centre mark/line, text, sketch,
                       detail). A tool previews the real item half
                       transparent and hands its data to
                       `BlueprintWindow.add_note` (one undo step).
                       Prompts go through `ask_text` / `ask_choice` /
                       `ask_fcf` so tests can answer them.
  - `blueprint_export.py` — PDF / SVG / PNG through `scene.render`
                       inside `scene.exporting()` (no selection, marker
                       or preview), a DXF R12 with LTYPE/LAYER tables
                       (HIDDEN and CENTER linetypes) from the same
                       primitives (arrowheads as SOLID, Ø as %%c), and
                       printing.
  - `pngexport.py`   — **File ▸ Export PNG…** (Ctrl+Alt+E): pictures
                       of the 3D view from the built-in renderer via
                       `View3D.snapshot(..., clean=True)` — the model
                       alone (no grid, axes, badge, selection tint or
                       anchors) in the user's colours, materials, style
                       and lighting, from an offscreen twin so the
                       user's camera never moves. **Current view**
                       keeps the on-screen camera exactly; **All
                       standard views** writes `<stem>-<n>-<view>.png`
                       per `DEFAULT_VIEWS` entry, framed, cover first —
                       the same set and cameras as the Printables
                       stills (`printables` paints them through `render`).
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
  - `section_loft.py`— **loft through sections** (Qt-free): the
                       node's 2D children are the cross-sections, one
                       per `heights` row, joined in order — so a body
                       keeps its corners (flat sides, a shoulder
                       crease, a flat hood: car bodies, boat hulls),
                       which the elliptical `loft` cannot. Sections
                       with the same point count join point to point
                       (every corner a sharp edge along the solid);
                       different counts are `resample`d to one count
                       keeping every original vertex. `align` shifts
                       each ring to its neighbour so nothing twists;
                       `smooth` adds Catmull-Rom rings, the given
                       sections staying put; both ends are capped.
                       Each child gives its largest outline
                       (`child_sections`). The `section_loft` node
                       (bake.py, in `_BAKED`: `kcad_section_loft(
                       heights=, smooth=, points=, faces=) { 2D
                       sections }`) bakes like `sweep` — refused in a
                       loop, no 2D booleans inside, one height per
                       section. Extrude toolbar group.
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
  - `sculpt.py`      — **sculpting** (Blender's sculpt mode as
                       parameters; Qt-free): a `sculpt` node wraps a
                       solid (a blend, a subdivided cage, an imported
                       scan) and holds `strokes` rows `[kind, x, y, z,
                       radius, strength, dx, dy, dz]` in the children's
                       LOCAL frame — kinds grab (drag along a direction,
                       mm), inflate (along the vertex normals, negative
                       pulls in), smooth (relax, passes = ceil
                       strength), flatten (press onto the patch's mean
                       plane), pinch (towards the centre) — each with a
                       smoothstep falloff to zero at the radius, and
                       `mirror` repeating every stroke across the x/y/z
                       plane so a face is sculpted from one side. The
                       mesh is welded once (`Mesh`) so vertices moving
                       never open it. Baked like the deformers (in
                       `_BAKED`; `detail` > 0 first refines with
                       `split_long_edges`, default 0 = the mesh as it
                       is — a blend or a scan is dense already, and
                       1.5 mm on a human figure made 360k triangles).
                       `to_local` maps a world point + direction the
                       view picked back into the node's frame: nearest
                       vertex twin (same tessellation, same order) plus
                       the linear part read off that triangle. Why
                       strokes and not a mesh: a likeness needs a
                       free-form surface, and this keeps it editable,
                       undoable and re-importable.
  - `sculpt_ui.py`   — the click flow: `SculptPanel` (brush, radius,
                       strength, mirror, undo last) keeps
                       `view3d.start_pick` armed on the sculpt's CURRENT
                       baked surface (`meshes`, re-fetched after every
                       stroke since the surface moved); a click lands one
                       stroke at the hit, direction = the face normal.
                       Toolbar Deform ▸ Sculpt wraps the selection and
                       opens it; right-click ▸ Sculpt… re-enters. MCP
                       `sculpt_stroke` (one stroke or a `strokes` batch,
                       world coordinates from `probe_surface`, wraps any
                       solid) is the assistant's brush.
  - Smooth shading (2026-09-14): `shading.vertex_normals` gives each
                       triangle three normals — the area-weighted mean
                       of the faces meeting at that vertex within
                       `SMOOTH_ANGLE` (40°) of this face's, so a sphere,
                       a loft or a sculpted head shades as one skin and
                       a box edge stays hard. `glrender.build_vertices`
                       packs them when `View3D.smooth` is on (View ▸ 3D
                       Smooth Shading, QSettings `render_smooth`, MCP
                       `set_render_options smooth`, default on; a
                       translucent entry then carries three tails,
                       `translucent_tails`). OpenGL only — the painter
                       fills a polygon with one colour.
  - `photo3d.py`     — **Mesh from a photo** (Qt-free): one picture
                       -> a generated surface through an image-to-3D
                       model — `generate_tripo` (api.tripo3d.ai v2:
                       multipart upload -> `image_to_model` task -> poll
                       -> pbr_model/model URL), `generate_meshy`
                       (api.meshy.ai `/openapi/v1/image-to-3d` with the
                       picture as a data URI -> poll SUCCEEDED ->
                       model_urls.glb) and `generate_local` (a command
                       template with `{image}` and `{output}`, for
                       Hunyuan3D / TripoSR / TRELLIS run locally; a
                       stale output is unlinked first). urllib only, an
                       injectable `opener` so the tests fake the wire.
                       `parse_glb` reads glTF binaries (JSON + BIN
                       chunks, triangle primitives, node matrix/TRS
                       transforms), `write_glb` writes one; `.glb` is in
                       `engine.MESH_EXTS` (parse_mesh turns it Z-up) and
                       imports through a sibling `_from_glb.stl` like
                       OBJ. `to_stl` scales the longest side to
                       `size_mm`, centres X/Y and stands it on Z = 0.
                       Keys: QSettings `photo3d/keys/<backend>` or
                       `TRIPO_API_KEY` / `MESHY_API_KEY`; command
                       `photo3d/command`. The far side of a one-view
                       surface is guessed — the sculpt node and the
                       reference overlay are what fix it.
  - `photo3d_dialog.py` — AI ▸ Mesh from Photo… (picture, generator,
                       key or command, longest side; a `Worker` QThread,
                       log, import on success) and `run_blocking`, the
                       MCP `mesh_from_photo` path: the worker runs while
                       the GUI thread pumps events, results stored over
                       direct connections (a queued one could land after
                       the pump stopped). Tests use the local backend
                       with a script that writes a GLB.
  - `human.py`       — the **`human` node**: MakeHuman's CC0 base mesh
                       (`khervecad/human/base_body.obj.gz`, the closed
                       13,380-vertex "body" group, re-indexed) blended
                       with its macro targets (`*.target.gz`: caucasian
                       female/male × young/old, universal weight and
                       height per gender — sparse decimetre offsets,
                       re-indexed; LICENSE.txt records the CC0 origin,
                       ~1 MB, in the spec's `datas`). `weights()` is the
                       macro blend (gender × age over the four ethnic
                       targets, |weight| and |height| per gender on top),
                       `build()` turns Y-up decimetres into Z-up mm facing
                       -Y, stood on Z = 0, centred, scaled to `stature`.
                       A baked LEAF (`bake.LEAVES` + `_BAKED`:
                       `kcad_human(gender=, age=, weight=, height=,
                       stature=, points=, faces=)`), a toolbar
                       primitive, and the base a Sculpt shapes a face on.
                       Why: correct anatomy under the clothes, which
                       capsules and lofts never give.
                       **Face** (2026-09-14): `khervecad/human/face/`
                       holds 182 MakeHuman face targets (nose, mouth,
                       eyes, chin, cheeks, forehead, head shape, neck,
                       brows — re-indexed, gzipped); `sliders()` pairs
                       them by suffix (decr/incr, in/out, down/up,
                       backward/forward, concave/convex) into 102
                       sliders, `eye-scale` moving both `l-`/`r-`
                       targets, a shape (`head-oval`) 0..1 only. The
                       node's `targets` rows `[[slider, weight]]` add
                       them after the macro blend; `warp` rows
                       `[x, y, z, dx, dy, dz]` (its own frame) are a
                       Gaussian RBF field (`rbf_warp`, coefficients
                       solved so each centre lands exactly; radius
                       `warp_radius`). `landmarks.json` names 19 face
                       landmarks by body vertex (from the rig's joints
                       and the base geometry); `landmark_points()` gives
                       their positions for any parameters. `skeleton.
                       json.gz` (bones with head/tail, parents, skin
                       weights re-indexed) is shipped for the rig.
                       **Rig** (same day): `skeleton.json.gz` carries
                       MakeHuman's default rig — 163 bones (parent,
                       head/tail joint names), every joint's 8 helper
                       vertices in the raw frame, `joint_offsets` (how
                       each macro target moves those helpers, so joints
                       follow a heavier or longer-limbed body the way
                       MakeHuman moves them) and skin weights re-indexed
                       to the body. `pose` rows `[[bone, rx, ry, rz]]`
                       (degrees about the bone's head, in the body's
                       axes, carried down the hierarchy —
                       `bone_matrices`) drive linear blend skinning
                       (`pose_points`) in the raw frame, BEFORE the
                       standing/scaling/centring transform, which is
                       taken from the rest pose so a raised arm moves
                       nothing below it; warp comes after. MCP
                       `set_pose` with `node_id` + `bones` poses a
                       figure (`{}` lists the bones). Clothes built round
                       the figure do not follow: pose first, dress after.
  - `library_characters.py` — **People & characters** (2026-09-18, the
                       user's request; Library ▸ Toys & models ▸ People &
                       characters): a plain Human figure (Man / Woman /
                       Child / Senior), an everyday Man and Woman, a Caped
                       superhero and a Dark knight — each `paint`(colour
                       map) > `sculpt` > `human`, plus hair / cape / cowl /
                       crest nodes, all editable. Clothes are front colour
                       maps from `RULES` (x, z -> rgb) rasterised by
                       `png_bytes` into shipped `khervecad/characters/
                       *.png` (`python -m khervecad.library_characters`
                       rewrites them; a test pins them). Lessons: arms
                       must hang AWAY from the hips (upperarm01 ry 24, not
                       40) or a front projection paints hands and hips
                       alike; upperarm rz swings the arm FORWARD, ry
                       lowers it; the base mesh has no muscle target
                       ("weight" is fat), so heroes are sculpted — one
                       broad flattened pec stroke, two round inflates read
                       as a woman's chest; traps above the collar line
                       show as skin. Heroes carry an original "K" crest:
                       no studio's logo (a swept-wing crest read as a bat
                       and was dropped).
  - `outfit.py`      — the **`outfit`** wrapper (2026-09-19, feature
                       module in `features.MODULES`, `COLORED` so
                       `features.tess` never caches it colourless):
                       clothes a `human` BY BODY PART. `PARTS` groups the
                       rig's bones (head, neck, chest = spine01/02 +
                       clavicle/breast/shoulder01, waist = spine03/04,
                       hips = spine05 + pelvis, shoulder = upperarm01,
                       upper_arm = upperarm02, forearm, hand, upper_thigh
                       = upperleg01, thigh = upperleg02, shin, ankle,
                       foot), `GROUPS` (torso, arm, leg, body, all),
                       ".L"/".R" for one side. Each face takes the part of
                       the POSED body's nearest vertex (`face_parts`,
                       40 mm hashed grid, cached) — position-based, so a
                       sleeve stays on the arm in any pose and a sculpted
                       body still finds its parts. `garments` rows
                       [part, colour, material], later wins; `skin` for
                       the rest. `kcad_outfit(...) { children }` helper
                       renders children unchanged; the importer unquotes
                       nested strings (`_text`).
  - `human_design.py` — the **Human Builder**'s model (Qt-free): a spec
                       (gender, age, build, stature, skin, gesture,
                       stance, hair, beard, glasses, hat, top, bottom,
                       coat, shoes, gloves + colours, `garments`) ->
                       `build` = outfit(human) + loose solids fitted from
                       `measure` (posed landmarks + part extents): hair
                       (11 styles), beards, hats (7), glasses, skirts and
                       dresses (closed cones from `waist_half` flaring past
                       `hip_half`), coat tails (a 300° `rotate_extrude`
                       shell OPEN at the front — a closed cone read as a
                       dress), hood, cape. GESTURES (13) and STANCES (4)
                       were checked from front and side: upperarm ry
                       lowers/raises, rz swings forward, lowerarm rx lifts
                       the forearm; arms-crossed was not reachable.
                       ~26 `PRESETS` (also Library parts via
                       library_characters). `insert` keeps the spec on the
                       Object (`params["character"]`) for Update selected.
                       MCP `list_character_options` / `build_character`
                       (bodies here; instructions have a People section).
  - `human_dialog.py` / `human_views.py` — Library ▸ People & characters
                       ▸ **Human Builder…**: combo boxes (item + colour
                       pairs) and Front / Side / Back views at one scale,
                       painted by `planview` (Back = the figure turned
                       half round); builds on a worker QThread (newest
                       request wins, ~2 s a figure), Random, Insert, Update
                       selected.
  - `library_animals.py` / `library_animals_real.py` — **Animals**
                       (2026-09-19, the user's request), Library ▸ Toys &
                       models ▸ Animals. **Cartoon animals** (30 chibi
                       toys, ~10 cm, v2 after "most animals look like 2
                       spheres, no details"): a `Toy` kit (ell, cap,
                       cone, disc, ring, hull, chain, blend) and a `Face`
                       kit (eyes = white + iris + pupil + 2 emissive
                       sparkles + lashes/brows/lids, cheeks, muzzle,
                       heart/button nose, open/smile/buck mouth,
                       whiskers, 7 ear styles) on body plans (`sit`,
                       `stand`, `ape`, `bird`, snake, frog, turtle,
                       crocodile), plus per-species extras and props
                       (bone, honey pot, bamboo, carrot, crown, bows,
                       collars, stripes/spots, manes, socks). Four
                       render-critique rounds; lessons: a detail must sit
                       on the surface it covers — a flat patch on a round
                       head pokes through the eyes (the ape mask is a
                       smaller ellipsoid of its own and the eyes go ON
                       it); a sock/patch must follow the limb's AXIS and
                       be ≥ 0.8 mm fatter or it flickers. Toy.scale
                       wraps a small plan in scale(). **Realistic
                       animals** are HIDDEN (the user: "bad"):
                       `library_animals_real` is not imported by
                       `library`, but is kept and tested — start there
                       next time (its docstring lists what to do next).
                       What it holds (23, LIFE
                       SIZE, mm): a RIG from published withers height H,
                       body length L, chest depth D, width W — ribcage,
                       belly, haunch, chest and shoulder/thigh masses,
                       tapered neck at its angle, head at its pitch, legs
                       as joint chains bent like the animal's (hind hock
                       BACKWARD; hoof / paw / pillar / knuckle), all ONE
                       blend. Markings follow the real skin: `surface`
                       casts a ray from the body axis through every mass
                       and takes the outermost hit (stripes on one
                       ellipsoid were buried under the others); zebra
                       `rings` go per leg SEGMENT (a straight stifle-to-
                       fetlock line floats off a bent leg). **Canine plan**
                       (the user: "real animals are very poor", with a
                       Labrador photo): `LAB` is a Labrador TRACED from a
                       side photograph scaled to the standard's 570 mm
                       withers — ribs, chest, back and keel masses (one
                       barrel: separate masses read as a caterpillar),
                       loin raised for the tuck-up, croup, thighs, a
                       two-capsule square muzzle with flews, eyes put on
                       the real head surface (`surface`), hull-triangle
                       pendant ears, a thick smooth otter tail (chains
                       subdivided: beads showed). `canine` stretches it
                       (size, long, wide, leg, head, snout, bone) for the
                       wolf and fox. The loop that got it right: render
                       side-on at the photo's mm/px, overlay at 55 %,
                       fix where the outlines part. Nothing below
                       z = 0: chains lift each joint by its radius and
                       `_on_ground` lifts the finished animal (a blend
                       bulges past its primitives).
  - `deform.py` `split_long_edges(region=)` refines only edges whose
                       midpoint lies in a box: the sculpt's `region`
                       rows (two corners) refine the head of a 1.6 m
                       figure at 4 mm without the 575k triangles a
                       whole-body refinement made.
  - `facefit.py`     — **fitting a face to photos** (Qt-free): the face
                       is linear in the slider weights, so `fit()` takes
                       one difference per slider as the exact Jacobian
                       and `least_squares()` solves ridge-regularised
                       normal equations with the weights pinned at ±1
                       (a few rounds); `residual_warp()` turns what the
                       sliders could not reach into warp rows.
                       `DEFAULT_SLIDERS` are the proportions a photo pins
                       down. Regularisation is RELATIVE (`lam` × the mean
                       diagonal of JᵀJ, default 0.3: with 14 landmarks and
                       28 sliders the absolute 0.05 pinned everything at
                       ±1 and made the fit worse); bounds are per
                       parameter (a shape slider 0..1). The tool also
                       fits the head bone's turn / tilt / nod
                       (`fit_head`, ±45°, step 5°) as three more
                       parameters, since a photo is rarely square on and
                       a wrong angle would otherwise be forced into the
                       face; `fit_face` writes `targets`, `pose` and
                       `warp`. The Queen fit: rms 6.2 -> 5.2 (sliders) ->
                       0.2 mm (warp), every landmark within a pixel. MCP `face_landmarks` (local, world and the
                       PIXEL position on every reference image, so an
                       assistant compares with the photo it can see) and
                       `fit_face` (landmark pixels on a reference image
                       -> plane mm via `paint.PLANES`; the node's world
                       placement from `mesh.ancestor_matrix`; sets
                       `targets` and `warp`, reports rms before / after
                       sliders / after warp). One photo pins its plane's
                       two axes; a front and a side pin three.
  - `hair.py`        — **hair cap** (Qt-free; the `hair_cap` wrapper,
                       Character family, baked in `_BAKED`): the faces
                       of the children inside a `within` box and not
                       looking within `clear_angle` of `clear` (the
                       face, `-y`) are lifted outward by `thickness`
                       plus `noise` × a smooth seeded bump field of
                       `curl` size (`bumps`: four sine waves in seeded
                       directions), the originals reversed as the
                       inside and the rim bridged — a shell turned
                       outward, one closed solid that hugs the head.
                       Vertices are canonicalised through `_key`
                       (neighbouring tessellation faces differ at
                       1e-16) so the cap is closed. Why: spheres are
                       not hair; a bumpy skin at curl size reads as a
                       set.
  - `paint.py`       — **Paint from photo** (Qt-free): the `paint`
                       wrapper (organic.py registers it; Character
                       family) gives every face of its children the
                       colour of a picture projected onto an axis plane
                       — the same placement as a reference image
                       (plane, lower-left `x`/`y`, `width`, `height` 0 =
                       aspect); faces outside keep their own, alpha and
                       material are kept. `sides` "front" (default)
                       paints only faces looking towards the camera the
                       photo was taken from (`VIEW_SIGN` per plane, a
                       `GRAZE` cutoff so a face seen edge-on keeps its
                       colour rather than smeared texels) — the far side
                       of a head must not wear the photo's background;
                       "both" projects straight through. A **second
                       picture** (`image2`, `plane2`, `x2`/`y2`/`width2`/
                       `height2` — a side photo beside the front one) is
                       blended per face by how squarely the face looks
                       at each (`paint_many`: weight = facing minus the
                       cutoff), so a cheek turns from the front photo to
                       the side photo without a seam. Both paths save
                       relative (`meshimport.PATH_PARAMS` now lists
                       several per type). `region` rows (two corners in
                       the children's frame) keep the paint to the face:
                       without it the hat in the portrait painted the
                       forehead magenta. `read_png` is a pure-Python 8-bit PNG
                       decoder (filters 0-4, RGB/RGBA/grey/palette),
                       QImage the fallback for JPEG; `Picture.at(s, t)`
                       samples t-up; `load` caches by mtime. Compiles to
                       `kcad_paint(...) { children }` (helper renders
                       children unchanged, like kcad_material) and
                       re-imports. The picture path saves relative and
                       resolves like a mesh path
                       (`meshimport.PATH_PARAMS`). Why: OpenSCAD has
                       one colour per solid and no textures; a colour
                       per face is what the preview has, and it is
                       enough to put a face's skin, eyes and lips where
                       the photo has them.
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
  - `cutaway.py`     — **Cut Through** (View ▸ Cut Through, Ctrl+Alt+X,
                       toolbar scissors; Qt-free): `clip` keeps one side
                       of an axis plane (straddling triangles split,
                       winding kept), `caps` closes the opening from
                       `section.cut`/`chain` outlines tiled by `fill` — a
                       trapezoid sweep, even-odd so holes stay open,
                       linear where ear clipping went quadratic on a
                       thread — facing the removed side, in `CAP_COLOR`
                       (Matte). Clipped surface + caps is a closed solid
                       again (a halved box measures exactly half).
                       `View3D` keeps the whole model in `model_mesh` and
                       shows the cut copy in `mesh` (`set_cut`, `cut`
                       {axis, position 0..1, flip, offset}, `cut_changed`
                       syncs the menu and toolbar). The Qt side —
                       `CutBar` along the bottom of the 3D view and the
                       View ▸ Cut Through menu — is `cut_ui.py`, so
                       view3d/mainwindow only hold thin wrappers. Changing axis picks the half whose cap
                       faces the usual camera (the back half for Y).
                       Everything that must see the whole part reads
                       `model_mesh`: Blueprint geometry and pictures,
                       MCP `section`, and Printables stills
                       (`pngexport.render(uncut=True)` →
                       `snapshot(uncut=True)`). MCP: set_render_options
                       `cut` / `cut_position` / `cut_flip`.
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
                       **Compare to reference** (2026-09-14): with
                       `View3D.overlay` on (View ▸ Compare to Reference
                       Image, QSettings `render_overlay`,
                       `set_render_options overlay`) the pictures are
                       drawn OVER the model too, after the faces and the
                       selection tint — an onion skin. `render_view
                       overlay_reference: true` makes the comparison
                       picture: square on to the first visible
                       reference's plane (`_PLANE_VIEWS`), orthographic,
                       the model and the picture's corners both framed,
                       overlay forced on the offscreen twin
                       (`snapshot(overlay=)`). Where the outline leaves
                       the photo is where the next sculpt stroke goes.
  - `tools/refsheet.py` — cuts a blueprint sheet (one picture, 3–4
                       orthographic views) into single views: each rough
                       `--view NAME=x0,y0,x1,y1[:mirror]` box is trimmed
                       to the drawing (vs the border's commonest colour),
                       optionally mirrored, saved as `SHEET-NAME.png`,
                       and reported as true-size `set_reference_image`
                       arguments from the real `--length/--width/
                       --height` (side/top span the length, front/back
                       the width) plus a `check` of the other dimension.
                       QImage only (no Pillow in the venv). Driven by
                       the **model-from-blueprint** skill
                       (`.claude/skills/`): find real dimensions, find a
                       drawing, ask before downloading (private
                       reference, never shipped), cut, place, build,
                       check orthographically. The MCP `_INSTRUCTIONS`
                       carry the same rule ("Modelling a real object")
                       to every connected client.
  - `tools/hand_tools.py` — the **Hand tools as real assemblies**
                       (2026-09-17, the user's request: a plier "should be
                       made of at least 3 parts"). Every tool in
                       `parts/Tools/` was one Object, so nothing could be
                       coloured, mated or exploded apart. Each tool is now
                       one `component` per MANUFACTURED piece: the pliers
                       are two crossing levers (each jaw full thickness on
                       its own side of y = 0, lapped to half thickness at
                       the pivot so the levers cross, handle leg to the far
                       side), a peened rivet and two grips; the adjustable
                       wrench a body with the fixed jaw, a sliding jaw with
                       its rack shank, a knurled worm and its pin; the
                       hammer head / shaft / grip / eye wedge; a chisel
                       blade / handle / ferrule / striking cap; a
                       screwdriver handle / grip cap / ferrule / blade; the
                       saw blade, handle and three brass screws; each hex
                       key; the level's body, two end caps and two vials;
                       and `split_socket_set` takes a socket set apart into
                       the rail, EVERY socket (named from the rail's own
                       size marks), the extension bar and the ratchet's
                       body, drive anvil, reverse lever and grip. What is
                       really one forging stays one Object — the 35
                       combination spanners and the cold chisel. Tools are
                       authored as OpenSCAD (one zero-argument `module` per
                       part) and parsed back through `scadparse`, so the
                       shipped `.kcad` is an ordinary editable tree;
                       `test_hand_tools` pins the file to the generator,
                       the part list of each tool, that the plier jaws meet
                       on y = 0 from opposite sides, and that a one-piece
                       tool is not split. A subtrahend that reaches past
                       its solid draws a phantom wall in the built-in
                       preview (it shows a difference as its uncut first
                       operand), so the wrench's jaw opening is a polygon
                       following the head's arc, not an overhanging square.
  - `tools/butt_hinge.py` — writes `parts/Brackets/Butt Hinge.kcad` and
                       `Butt Hinge 2.kcad` (`python -m
                       khervecad.tools.butt_hinge` for both, `--style
                       screw|slide OUT` for one): a
                       butt hinge in THREE printable Objects, each at its
                       own origin in its print pose — Leaf A (knuckles 1,
                       3, 5; the last one tapped and blind), Leaf B
                       (knuckles 2, 4) and a removable Ø10 bolt (coarse
                       2 mm thread, hex socket, round head) printed lying
                       on a flat, since stood up a hinge pin shears
                       between layers. Clearances are named (FIT bolt ↔
                       bores/thread, GAP between knuckles, SWING round the
                       other leaf's knuckles, which each leaf is scooped
                       for); bores are truncated teardrops; the tap is the
                       bolt's own helix grown by FIT (same start and slice
                       spacing, so in phase). Nothing may touch exactly —
                       a plate edge on a knuckle's tangent line, a fillet
                       ending on a chamfer ring, a cone crossing a thread
                       root on a slice plane each gave doubled edges.
                       `test_butt_hinge` pins the shipped file to the
                       builder and, with OpenSCAD, watertightness, bed
                       contact and a clear 0-180° swing.
                       **Butt Hinge 2** (`style="slide"`): the same
                       Leaf B, Leaf A's end knuckle a plain blind bore
                       with a groove, and a **Pin** that slides in — its
                       tip slit into two prongs whose side lugs (only
                       |z| < LUG_HALF: the prongs flex sideways) stand
                       0.3 mm proud of the bore and click into the
                       groove; sloped back faces let a firm pull take it
                       out. The test also checks the pin 6 mm short of
                       home DOES press on the bore — or it would never
                       hold.
  - `mcp_schema.py`  — the **MCP tool table**: 74 JSON-Schema tool
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
                       export says so loudly. `probe_surface` casts a
                       ray at the scope's parts (`analysis.surface_hits`,
                       Möller-Trumbore over each part's world mesh, bbox
                       pre-reject, shared-edge hits merged) and returns
                       the hit point, outward normal, distance and part,
                       every crossing nearest first — how an assistant
                       puts an eye or a tubercle ON a loft without
                       re-deriving its geometry outside the app (the
                       whale needed a side script for that);
                       `sample_surface` (`analysis.surface_samples`:
                       area-weighted darts kept `spacing` apart, seeded,
                       filtered by `facing`/`max_angle` and a `within`
                       box) scatters N points + normals over a part for
                       the details that come in numbers — the Queen's
                       hair curls were placed by a formula in a side
                       script before it. The
                       offscreen `render_view` fit frames the MODEL
                       (`_model_frame`), where the on-screen fit takes
                       the platform in and left the model small.
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
                       `macos-v0.1.N` + the DMG for this Mac's
                       architecture (family `macos` = arm64,
                       `macos-intel` = x86_64, same tags); drafts,
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
  - `sheetmetal.py`  — **Sheet metal** (Insert ▸ Sheet metal part; Qt-
                       free, registered from organic.py like pattern):
                       a `sheet_metal` leaf — base plate, thickness,
                       inside bend radius, K-factor, and a flange
                       length + angle on each edge (n/e/s/w; a negative
                       angle bends down). Compiles to ONE `kcad_sheet(
                       size=, t=, r=, k=, flanges=[[len, angle] x4])`
                       call whose helper is real OpenSCAD (the bend
                       profile — outer arc, leg, inner arc — as a
                       polygon, `rotate([90,0,0]) linear_extrude` along
                       the edge, then the SAME per-edge translate/rotate
                       the preview uses; a parity test pins the two).
                       `flat_pattern` unfolds with the bend allowance
                       `(r + K t)·θ` and the outer setback `(r + t)
                       tan(θ/2)`, one cross-shaped outline plus bend
                       lines; `flat_dxf` writes CUT/BEND layers.
                       `sheetmetal_ui.py` is the tree's right-click
                       Unfold (a flat blank Object beside the part) and
                       Export flat pattern DXF. One bend per edge, no
                       reliefs or hems — by design.
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
  - **Solar System** (2026-09-17, Library ▸ Science ▸ Solar System;
                       the user asked for the known planets, their moons
                       and motion round the Sun, "good enough" rather than
                       precise): `solar_data.py` (Qt-free) is the table —
                       the Sun, 8 planets, 5 dwarf planets and 25 moons
                       with real equatorial/polar radii (irregular moons
                       as three radii), obliquity and where the pole leans
                       (`pole_lon`, ecliptic longitude), sidereal rotation
                       (negative = retrograde), JPL J2000 orbital elements
                       (a, period, e, i, node, longitude of perihelion,
                       mean longitude) and colour; `orbit_expressions` /
                       `position` are the SAME Kepler formula (equation of
                       the centre to e³, inclined at the node) as OpenSCAD
                       text and as Python, so a test pins the program to
                       the maths. `solar_surface.py` — features stood ON a
                       sphere, no boolean: `band` (a revolved arc slice:
                       belts, polar caps), `hemisphere`, `patch` (an
                       ellipsoid sunk to its rim), `crater` (a revolved
                       circle half sunk), `mountain`, `arc_line` (capsules
                       along a great circle), `rings` (annuli), `haze`
                       (a Glass shell), `map_shells` (a character map ->
                       one polyhedron per class, each run of like cells a
                       closed curved slab; the EAST end face once reused
                       the west's normal and wound wrong past a few cells)
                       and `poly_sphere` (a baked low-poly sphere whose
                       facets are its own — the document's $fn made every
                       1 mm orrery moon 1890 triangles). `solar_maps.py`
                       — the Earth at 5° (36 rows × 72 columns, ocean /
                       green / taiga / desert / ice, hand-drawn).
                       `solar_earth.py` (same day — the user wanted "a lot
                       more details" than 5° cells, then "the mountains
                       and hills should show the landscape in 3D"): the
                       Earth's land from REAL coastlines and a REAL height
                       model. Data in `khervecad/solar/` (shipped via the
                       spec's datas, provenance in its README): Natural
                       Earth 1:50m land / lakes / glaciated areas (public
                       domain) simplified to 0.1°, Antarctica's -90° edge
                       clamped to -89° (a polar cap band closes it) and
                       ear-clipped ONCE by `khervecad.tools.earth_coast`
                       into `earth_coast.json.gz` (the clipper's unchecked
                       last ear and Natural Earth's duplicate Lake Volta
                       dropped there); ETOPO 2022 (NOAA, public domain)
                       resampled to 0.25° by NOAA's DEM_global_mosaic image
                       service — the DEM_all mosaic is NOT global — into
                       `earth_elevation.bin.gz` (int16 metres, ocean 0,
                       `khervecad.tools.earth_elevation`). At build, per
                       ring in the (lon·cos lat, lat) plane: Delaunay edge
                       flips (`_flip_delaunay`; the fold test must check
                       the NEW triangles' orientation — reversed, it never
                       flipped and bisecting the ear-clip slivers made 600k
                       triangles), then midpoint refinement interleaved
                       with flips (`_refine`, conforming: the edge decides)
                       to 0.08 r everywhere and 0.03 r where the ground
                       climbs (`RELIEF_STEP`: the ends differ by 200 m — a
                       plateau stays coarse), then onto the sphere. Each
                       triangle is classed by the 5° map plus snow above
                       4500 m and bare rock above 2200 m, and every class
                       is ONE closed polyhedron (`_shell`: outer, mirrored
                       inner, walls along its boundary; pinch vertices
                       split by `_split_pinches`, seam-folded triangles
                       dropped, a wall vertex keyed by the ORIGINAL sphere
                       point). Both surfaces are lifted by `relief` × the
                       elevation (default 50×: Everest 7 % of the radius;
                       the Earth part's "Relief exaggeration" field), so a
                       lake on the Tibetan plateau rides up with it. Lakes
                       and ice fields are thinner slabs on top. Fine ≈ 115k
                       triangles in ~2.5 s; coarse (orreries, 0.6°) ≈ 19k.
                       The 5° map stays as the climate classifier.
                       `solar_raster.py` (same day — "the Moon and Mars
                       and others with the same details"): REAL maps for
                       20 bodies, one `khervecad/solar/<key>.kmap.gz`
                       each (format in the docstring: palette, optional
                       int16 elevation, uint8 albedo class per 0.5° cell),
                       built by `khervecad.tools.planet_maps` from NASA /
                       USGS public-domain data — the Moon's LOLA DEM and
                       LROC colour (NASA SVS CGI Moon Kit; a plain float
                       TIFF, read by the tool's own strip reader since
                       geotiff.py wants a georeference), Mars' MOLA MEGDR
                       (PDS; the grid STARTS AT 0° E, roll it half a turn
                       or Olympus Mons is 530 m) and Viking colour, and the
                       USGS Astrogeology map server (planetarymaps.usgs.gov
                       WMS, map paths under the PARENT planet: /maps/earth/
                       moon, /maps/jupiter/io, /maps/saturn/titan…) for
                       Mercury, Venus, Pluto, Charon, the Galileans,
                       Saturn's moons, Triton, Phobos, Deimos. The tool
                       fills a mosaic's black no-data (Io's poles, Pluto's
                       unseen half) from the nearest mapped cell, k-means
                       the colours into 3–6 classes (greyscale ones tinted
                       with the body's colour), and majority-filters the
                       classes — speckle made every triangle an island
                       needing walls (Iapetus was 80k triangles).
                       `globe_nodes` builds the globe like the Earth's
                       land: a (lon, lat) grid to ±86°, Delaunay flips and
                       `_refine` where the ground climbs, one closed shell
                       per class (`solar_earth._shell`) lifted by the
                       body's `RELIEF` (Moon 10×, Mars 8×; the Part Library
                       field appears for bodies with a height model), polar
                       cap bands, an irregular moon squashed to its radii
                       afterwards, over a base sphere (a shell alone had
                       no volume). `build_body` dispatches to it for a FINE
                       globe with a map; the hand-placed features stay for
                       the unmapped (Uranus' moons, Ceres, Haumea…) and
                       for every orrery globe — mapped coarse globes made
                       a slider tick 1.4 s for moons millimetres across.
                       Orrery details (2026-09-18): the Earth system's days
                       step 0.01 (`DAYS_STEP`; the automatic 0.07 was 25°
                       of spin a notch, too coarse to watch it turn) and no
                       system's step may round to 0 (Mars' did: its slider
                       fell back to whole days). A globe's spin is a
                       `rotate` ABOVE the globe Object, not its rz: the
                       globe then has no placement, its cached mesh comes
                       back untouched, and scale · spin join the transforms
                       above into ONE matrix — as the globe's rz it cost a
                       pass of its own every frame (whole system 289 -> 209
                       ms a tick, Earth's 39 -> 24).
                       Fine Moon ≈ 100k triangles, Mars ≈ 80k, a moon
                       ≈ 25k. ~1.2 MB of maps shipped.
                       `solar_bodies.py` — `build_body(key, diameter,
                       fine)`: every body's recognisable features (Earth's
                       map + atmosphere, Mars' albedo regions, Tharsis
                       volcanoes, Valles Marineris and caps, Jupiter's 14
                       belts and the Great Red Spot, Saturn's C/B/A/F
                       rings, Uranus' and Neptune's rings, the Moon's 18
                       maria, 26 named craters and Tycho's rays, Io's
                       Pele ring, Europa's lineae, Callisto's Valhalla,
                       Iapetus' Cassini Regio and ridge, Enceladus' tiger
                       stripes, Titan's haze, Triton's pink cap…) at IAU
                       lat / east lon, so a synchronous moon's 0° faces its
                       planet; `fine=False` (orreries) drops the seeded
                       crater scatters and lines, uses 8-sided blobs and
                       rims (what `keeps_segments` leaves alone) and bakes
                       bodies under 3000 km. `library_solar.py` — Part
                       Library categories Planets / Moons (Ø 30 / 60 / 120
                       mm and 1:250 000 000 to scale) and **Solar System
                       models**: orreries driven by a Customizer `days`
                       slider like `library_motion` (whole system, inner
                       planets, dwarf planets, each planet & its moons).
                       Every body is an Object whose OWN variables solve
                       its orbit (`translate([px, py, pz]) rotate([0,
                       tilt, pole]) scale(size / 20) rotate([0, 0, spin])
                       Earth_globe();`), moons circle in the planet's
                       equatorial frame facing it; sliders for Earth's
                       diameter, the Sun's, Earth's orbit radius, orbit
                       `compression` (1 = true spacing, 0.5 = square
                       root), `size_compression`, moon spread and the
                       smallest moon. A globe Object reads NO variable —
                       nested modules are HOISTED to the top of the
                       program, so a moon or globe cannot read its
                       planet's locals; the scale stands outside it and
                       each moon recomputes its planet's size from the
                       globals. `library_motion.place(model, root)` is the
                       shared insert (assigns become prefixed globals,
                       Objects land beside the model). Full orrery: ~120k
                       triangles, ~0.5 s a tick in the pure-Python
                       preview; a planet system ~0.1 s.
- The MCP instructions (`mcp_server._INSTRUCTIONS`) carry a **Motion**
  section, so an assistant builds moving models the fast way: one
  annotated variable for the slider, every moving piece its own Object,
  the variable reaching it only through PLACEMENT, and NEVER into the
  geometry of a part (a cube's size, a gear's teeth, a polygon's
  points) — that re-cuts the solid every frame.
- `docs/MCP.md` — how to connect an assistant, what the 74 tools do,
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
  `while` has no OpenSCAD statement, so codegen writes it as a `for`
  over a C-style list comprehension — `for (x = [for (x = s, _w = 0;
  (cond) && _w < 1000; x = upd, _w = _w + 1) x])` — which OpenSCAD
  evaluates per iteration, so the condition may read document variables
  and enclosing loop variables (a dome's layers per column); `_w` caps it
  at 1000 like the preview. scadparse reads that form back as a
  `while_loop` (`_parse_c_for`). It used to be unrolled with no
  environment at all, exporting any loop that read a variable as
  `for (x = [0])`. `if_else` keeps its else branch in a child
  union named "Else" (auto-created).
- Organisational groups: `variables` (leading assignments, transparent
  in codegen). A `reference` ("Linked copy") places a node by NAME: a
  copy of an Object is one placed call of its module, a copy of
  anything else inlines it (its own move/rotate applied), so editing
  the original updates every copy.
- **Masters were retired** (2026-09-19, the user: "is it of any use?"):
  an Object did the same "define once, place many" and also takes a
  colour, anchors, mates, the exploded view and its own module. There
  is no Masters tab or Make Master item any more. `model.
  retire_masters` turns an old document's `masters` store into hidden
  Objects where it stood (on `load_kcad` and undo restores), so its
  Linked copies call those Objects and the scene is unchanged;
  `_definition` wraps anything but a plain Group (a Group's own move /
  colour would be dropped from the module — it goes on the call) as
  "<name> body". `make_master()` (kept for MCP `make_master`) now does
  the same to one node: hidden Object at the top, Linked copy in its
  place, even inside a loop. The `masters` node type stays registered
  so old files parse.

The document-wide `$fn` (Edit ▸ common segments, on by default at 45)
replaces every round object's own segment count **except an intended
polygon** — `model.keeps_segments`: 8 or fewer (a hex head, a hex
socket, an octagonal pot) keeps its sides in both the codegen (`_fn`)
and the preview (`mesh.rp`). It used to turn every hex socket round, so
no key could turn a library bolt or the butt hinge's.

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
compatible. Version 9 adds the top-level `"unit"` (units.py); a file
without it, or with a unit it does not know, opens as millimetres. Version 12 adds `"real_scale"` — the N of 1 : N the scale bar measures (absent = 1, life size).

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

**macOS (Apple Silicon and Intel), one command** — on a Mac:

```
python packaging/build_macos.py
```

Same first step (write `khervecad/VERSION`), then the platform's own
container: the spec ends in `BUNDLE` so PyInstaller yields
`dist/KherveCAD.app`, OpenSCAD is mounted from its disk image into
`Contents/Resources/openscad/OpenSCAD.app`, the finished tree is ad-hoc
signed (Apple Silicon will not run an unsigned Mach-O, and dropping
OpenSCAD in invalidates PyInstaller's signature, so signing goes last)
and sealed into a DMG for the build Mac's own architecture. Stable
OpenSCAD 2021.01 has no Apple Silicon binary, so the engine comes from a
snapshot the build discovers at run time — a universal binary, which is
what lets both architectures ship. `.github/workflows/macos-build.yml`
builds on `macos-14` (arm64) and `macos-15-intel` (x86_64) and publishes
both DMGs in one `macos-v<ver>` release with `--latest=false`, so
`releases/latest` stays on the Windows release the website links to. See
`README.macos.md`.

## MCP (Model Context Protocol)

KherveCAD is drivable by **any local MCP assistant** — Claude Desktop,
Claude Code, Cursor, Cline, VS Code, LM Studio — not just the built-in
chat. The chat answers with a program the user then applies; an MCP
client gets the whole app as **74 tools**: the object tree, OpenSCAD in
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

**SolidWorks gap list** (asked 2026-09-12). Landed the same day: the
OpenGL viewer (`glrender.py`), the other mates (flush / concentric /
angle / gear / limit, `mates.py`), 2D drawings (`drawing.py`) and sheet
metal (`sheetmetal.py`). Still open, in the order they would pay off:
**sketch constraints** (a 2D solver: parallel / tangent / equal /
driven dimensions — the biggest remaining gap), **feature rollback and
suppress** (the node tree is already the history; add roll-to-here and
a suppressed flag), **extrude up-to-face / through-all**,
**configurations** (named sets of the Variables sheet), **direct
face push/pull** on primitive faces. **Drawings with more** landed
2026-09-13 as the Blueprint window (user dimensions, notes, GD&T,
detail and section views, a parts list); what it lacks next is a
revision table, ordinate/baseline dimension chains, and dimensions that
re-attach to a moved edge instead of keeping their model points.

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
