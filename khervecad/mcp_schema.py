"""The tool table KherveCAD offers MCP clients — schemas only.

Deliberately Qt-free and import-free: this is the contract, and
`mcp_tools.py` is the implementation.  Keeping them apart means the
tool list can be inspected (and tested) without a running window, and
the stdio server never drags PyQt5 into the host's subprocess.

Every tool answers with JSON.  ``render_view`` additionally returns a
PNG under `mcp_server.IMAGE_KEY`, which the stdio/HTTP servers turn
into a real MCP image block.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

#: Camera presets `render_view` accepts (View3D.VIEWS).
ORIENTATIONS = ["Isometric", "Top", "Bottom", "Front", "Back", "Right",
                "Left"]

#: colour materials (model.MATERIALS — repeated for the same reason).
MATERIALS = ["Default", "Plastic", "Metal", "Matte", "Clay", "Glass",
             "Rubber", "Skin", "Gold", "Copper", "Emissive"]

#: 3D projections (view3d.PROJECTIONS — repeated here because this
#: module must not import Qt).
PROJECTIONS = ["Perspective", "Orthographic"]

#: `publish_to_printables` choices.  They live here rather than in
#: `printables.py` because that module imports PyQt5 and this one must
#: not — the stdio server reads this table in a bare interpreter.
LICENSES = [
    "CC BY-SA 4.0", "CC BY 4.0", "CC0 1.0", "CC BY-NC 4.0",
    "CC BY-NC-SA 4.0", "CC BY-ND 4.0", "CC BY-NC-ND 4.0",
    "GPL-3.0", "Standard Digital File License",
]
DEFAULT_LICENSE = "CC BY-SA 4.0"

#: Printables' add-a-model form asks for a main category, a one-line
#: summary and where the design came from, and none of those are in the
#: geometry — so the bundle answers them and the tool takes them.
CATEGORIES = [
    "3D Printing", "Art & Design", "Costumes & Accessories", "Fashion",
    "Gadgets", "Healthcare", "Hobby & Makers", "Household", "Learning",
    "Models", "Seasonal Designs", "Sports & Outdoor", "Tools",
    "Toys & Games", "World & Scans",
]
DEFAULT_CATEGORY = "Hobby & Makers"
ORIGINS = ["My own design", "A remix", "A scan",
           "Someone else's design"]
DEFAULT_ORIGIN = ORIGINS[0]

#: Printables caps the summary field.
SUMMARY_LIMIT = 120

#: What the bundle can contain, by extension.
FORMATS = ("stl", "3mf", "scad", "kcad")

#: Every standard still — what a Printables bundle renders and what
#: File > Export PNG > All standard views writes — cover first: the
#: front-right isometric, then the opposite corner, then the six faces.
#: `engine.CAMERA_ROTATIONS` holds the camera for each.
STILL_VIEWS = ("Isometric", "Isometric back", "Front", "Back", "Left",
               "Right", "Top", "Bottom")

#: Camera angles rendered unless the caller says otherwise: all of
#: them.  Someone deciding whether to print a part wants to see every
#: side of it, and the upload page keeps the files in order, so the
#: front-right isometric still gets the cover.
DEFAULT_VIEWS = STILL_VIEWS

#: A PNG of a named view, when no size is given (File > Export PNG,
#: export_document).
PNG_DEFAULT_SIZE = (1920, 1080)


#: Operations `wrap_nodes` can apply.  Every one of them wraps the
#: nodes it is given — that is how an extrude, a transform or a
#: boolean is applied in this app.
WRAP_TYPES = [
    "union", "difference", "intersection", "hull", "minkowski",
    "linear_extrude", "rotate_extrude", "translate", "rotate", "scale",
    "mirror", "offset", "projection", "color", "for_loop",
    "while_loop", "if_else", "component", "symmetry", "joint", "sweep",
    "blend", "bend", "twist", "taper", "lattice", "subdivide",
    "pattern", "shell",
]


def _obj(properties: dict, required=()) -> dict:
    return {"type": "object", "properties": properties,
            "required": list(required)}


_IDS = {
    "type": "array",
    "items": {"type": "integer"},
    "description": "Node ids from list_tree.",
}

_ID = {"type": "integer", "description": "A node id from list_tree."}

#: Parameter values are numbers, booleans, strings — or expression
#: strings, which is the point of the app.
_PARAMS = {
    "type": "object",
    "description": (
        "Parameter values by name, from list_node_types. A numeric "
        "parameter also accepts an EXPRESSION STRING — \"wall * 2\", "
        "\"i * 10\", \"cos(a) * r\" — which is how a loop variable or a "
        "document variable reaches it, and what makes the model "
        "parametric."
    ),
}


TOOLS = [
    # ── Inspection ─────────────────────────────────────────────────
    {
        "name": "get_document_info",
        "description": (
            "The document as a whole: file path and unsaved state, node "
            "and Object counts, the global segment count, whether the "
            "OpenSCAD engine was found (without it booleans are only "
            "approximated in the preview), which Object the user is "
            "editing, the model's bounding box in mm, and any "
            "validation errors. Call this first."
        ),
        "input_schema": _obj({}),
    },
    {
        "name": "list_node_types",
        "description": (
            "Every node type this app can build, with its category, its "
            "parameters and their ranges. Call it once at the start — "
            "add_node, set_params and wrap_nodes all speak these names, "
            "and guessing one wastes a call."
        ),
        "input_schema": _obj({
            "category": {
                "type": "string",
                "enum": ["2d", "3d", "op", "bool", "ctl"],
                "description": "Filter: 2D shapes, 3D primitives, "
                               "operations, booleans, control flow.",
            },
        }),
    },
    {
        "name": "list_tree",
        "description": (
            "The object tree: id, type, name, visibility, parameters and "
            "children. Ids are stable while a node lives, but undo and "
            "open rebuild the tree — re-read them afterwards."
        ),
        "input_schema": _obj({
            "node_id": dict(_ID, description=(
                "Start from this node instead of the document root.")),
            "depth": {
                "type": "integer",
                "description": "How deep to go (default 4; -1 for the "
                               "whole tree).",
            },
            "params": {
                "type": "boolean",
                "description": "Include each node's parameters "
                               "(default true).",
            },
        }),
    },
    {
        "name": "get_node",
        "description": (
            "One node in full: every parameter with its label and "
            "range, its path from the root, its children, its mate if "
            "it has one, and its error if it has one."
        ),
        "input_schema": _obj({"node_id": _ID}, ["node_id"]),
    },
    {
        "name": "get_code",
        "description": (
            "The generated OpenSCAD program. The whole document by "
            "default, or one Object/subtree standalone with node_id — "
            "which is what an Object's own view renders, in its own "
            "local frame. Read this before apply_code."
        ),
        "input_schema": _obj({
            "full": {"type": "boolean",
                     "description": "Write baked meshes (a blend's points and faces) out in full. Off by default: they are summarised, since only the node's parameters matter to read or re-apply it."},
            "node_id": dict(_ID, description=(
                "Emit just this Object/subtree as a standalone "
                "program.")),
        }),
    },
    {
        "name": "render_view",
        "description": (
            "A PNG of the 3D preview, returned as an image you can look "
            "at. Do this after building anything non-trivial — a part "
            "that is wrong is obvious in the picture and invisible in "
            "the tree. By default it first WAITS for OpenSCAD to finish "
            "the exact render, so booleans are really cut in what you "
            "see; `render_complete` says whether it finished in time. "
            "Camera parameters (azimuth, elevation, distance, zoom, "
            "target, target_node, projection, region, orientations) "
            "render from an offscreen camera and leave the user's view "
            "alone — `orientation` and `fit` alone move the user's own "
            "camera, as before. Pass the returned `camera` back to "
            "reproduce or adjust a view."
        ),
        "input_schema": _obj({
            "orientation": {
                "type": "string",
                "enum": ORIENTATIONS,
                "description": "Camera preset. On its own (or with "
                               "fit) it moves the USER'S camera; with "
                               "any camera parameter it only aims the "
                               "offscreen one. Omit to leave their view "
                               "alone.",
            },
            "view": {
                "type": "string",
                "enum": ["3d", "2d"],
                "description": "'2d' grabs the sketch/assembly view "
                               "instead. Default '3d'.",
            },
            "fit": {
                "type": "boolean",
                "description": "Frame the whole model first.",
            },
            "max_width": {
                "type": "integer",
                "description": "Scale the picture down to at most this "
                               "many pixels wide (default 900).",
            },
            "wait_for_exact": {
                "type": "boolean",
                "description": "Wait for OpenSCAD's exact render before "
                               "taking the picture (default true). "
                               "False takes whatever is on screen now.",
            },
            "timeout": {
                "type": "number",
                "description": "Seconds to wait for the exact render "
                               "(default 30, max 300). On timeout you "
                               "still get the picture, with "
                               "render_complete false.",
            },
            "azimuth": {
                "type": "number",
                "description": "Camera angle around Z, degrees: 0 looks "
                               "from +X, -90 from the front (-Y), 90 "
                               "from the back, 180 from -X.",
            },
            "elevation": {
                "type": "number",
                "description": "Camera height above the XY plane, "
                               "degrees: 90 looks straight down, "
                               "negative looks up from below.",
            },
            "distance": {
                "type": "number",
                "description": "Camera distance from the target in mm "
                               "(the scale, in orthographic). Usually "
                               "leave it to target_node/fit and use "
                               "zoom.",
            },
            "zoom": {
                "type": "number",
                "description": "After framing, move in (2 = twice as "
                               "close) or out (0.5).",
            },
            "target": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 3, "maxItems": 3,
                "description": "World point [x, y, z] in mm the camera "
                               "looks at.",
            },
            "target_node": {
                "type": "integer",
                "description": "Frame this node from list_tree: aim at "
                               "it and fit it to the picture — a "
                               "close-up of one part.",
            },
            "projection": {
                "type": "string",
                "enum": PROJECTIONS,
                "description": "Orthographic shows true proportions (no "
                               "perspective shrink) — best for checking "
                               "alignment and symmetry.",
            },
            "region": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 4, "maxItems": 4,
                "description": "Crop to [x0, y0, x1, y1] as fractions "
                               "of the picture (0-1, origin top-left). "
                               "Rendered at a higher resolution, so a "
                               "small detail comes back sharp.",
            },
            "orientations": {
                "type": "array",
                "items": {"type": "string", "enum": ORIENTATIONS},
                "description": "Several presets in ONE picture: a "
                               "labelled contact sheet, each view "
                               "framed on its own. One call instead of "
                               "one per angle.",
            },
        }),
    },
    {
        "name": "list_parts",
        "description": (
            "The parametric part library: vacuum components (CF/KF "
            "flanges, fittings, valves, pumps, analysers, "
            "manipulators), ISO-threaded fasteners, chemistry glassware "
            "and room furniture — with each part's standard sizes and "
            "the dimensions you may override. Use a library part rather "
            "than modelling a CF flange from scratch."
        ),
        "input_schema": _obj({
            "category": {"type": "string",
                         "description": "Filter to one category."},
            "part_id": {"type": "string",
                        "description": "Full detail for one part, "
                                       "including its size table."},
        }),
    },
    {
        "name": "list_examples",
        "description": (
            "The built-in example models, by category — a graded Learn "
            "series, mechanical parts, procedural flowers and trees, "
            "and the course projects. load_example replaces the "
            "document with one, fully editable."
        ),
        "input_schema": _obj({}),
    },
    {
        "name": "list_anchors",
        "description": (
            "The parts that can be mated at a given scope, and the "
            "anchors of one of them. Every part has automatic "
            "bounding-box anchors — Origin, 6 face centres, 12 edge "
            "midpoints, 8 corners — plus any the user picked. These are "
            "the names attach_parts takes."
        ),
        "input_schema": _obj({
            "node_id": dict(_ID, description=(
                "The part whose anchors you want. Omit to just list the "
                "mateable parts.")),
            "scope_id": dict(_ID, description=(
                "List the parts inside this Object instead of the Main "
                "assembly.")),
        }),
    },

    # ── Building ───────────────────────────────────────────────────
    {
        "name": "get_node_bounds",
        "description": (
            "World-space bounding box of one or more nodes — min, max, "
            "size and centre in mm, where the object really sits in "
            "the assembly (every ancestor transform applied). Use it to "
            "check a part's size or position without reading the tree "
            "by hand. `approximate` flags a subtree whose booleans the "
            "built-in tessellator only approximates."
        ),
        "input_schema": _obj({"node_ids": _IDS}, ["node_ids"]),
    },
    {
        "name": "measure",
        "description": (
            "Distance between two points — explicit coordinates, a "
            "node's centre / min / max corner, or a named anchor on an "
            "Object. Between two nodes it also gives the per-axis `gap` "
            "between their boxes (> 0 clearance, < 0 overlap), "
            "`overlap` and `clearance`: is this pin clear of that wall?"
        ),
        "input_schema": _obj({"a": {
                "type": "object",
                "description": "{\"point\": [x, y, z]} or {\"node\": "
                               "id, \"at\": \"center\" | \"min\" | "
                               "\"max\" | <anchor name>}. Anchor names "
                               "(Objects/instances) come from "
                               "list_anchors.",
                "properties": {
                    "point": {"type": "array",
                              "items": {"type": "number"},
                              "minItems": 3, "maxItems": 3},
                    "node": {"type": "integer"},
                    "at": {"type": "string"},
                },
            }, "b": {
                "type": "object",
                "description": "{\"point\": [x, y, z]} or {\"node\": "
                               "id, \"at\": \"center\" | \"min\" | "
                               "\"max\" | <anchor name>}. Anchor names "
                               "(Objects/instances) come from "
                               "list_anchors.",
                "properties": {
                    "point": {"type": "array",
                              "items": {"type": "number"},
                              "minItems": 3, "maxItems": 3},
                    "node": {"type": "integer"},
                    "at": {"type": "string"},
                },
            }}, ["a", "b"]),
    },
    {
        "name": "section",
        "description": (
            "Cut the model with a plane and get the cross-section: a "
            "hatched PNG with a mm grid, plus the outlines — each "
            "closed or not, its area (holes negative) and extent. Shows "
            "what a shaded render cannot: wall thickness, whether a "
            "bore goes through, what is inside a closed shell. By "
            "default it cuts what the 3D view shows after waiting for "
            "the exact render; with node_id it cuts that node's "
            "built-in tessellation. An outline that does not close "
            "means the mesh leaks on that plane."
        ),
        "input_schema": _obj({
            "axis": {"type": "string", "enum": ["x", "y", "z"],
                     "description": "The plane's normal: 'z' cuts "
                                    "horizontally (a plan), 'y' a "
                                    "front section, 'x' a side one."},
            "offset": {"type": "number",
                       "description": "Where along the axis, in mm. "
                                      "Defaults to the model's middle."},
            "node_id": {"type": "integer",
                        "description": "Cut just this node instead of "
                                       "the whole view."},
            "include_points": {"type": "boolean",
                               "description": "Also return each "
                                              "outline's (u, v) points."},
            "max_width": {"type": "integer",
                          "description": "Picture width (default 700)."},
            "wait_for_exact": {"type": "boolean",
                               "description": "Wait for OpenSCAD's "
                                              "exact render first "
                                              "(default true)."},
            "timeout": {"type": "number",
                        "description": "Seconds to wait (default 30)."},
        }, ["axis"]),
    },
    {
        "name": "check_code",
        "description": (
            "Dry-run an OpenSCAD program: parse and validate it exactly "
            "as apply_code would, WITHOUT touching the model. Returns "
            "what it would create (node types and counts), every "
            "statement the importer skipped (`warnings`) and every "
            "node that would turn red (`problems`). Use it before a "
            "big apply_code, or to learn whether a construct is in the "
            "importable subset."
        ),
        "input_schema": _obj({
            "code": {"type": "string",
                     "description": "The OpenSCAD program."},
        }, ["code"]),
    },
    {
        "name": "add_node",
        "description": (
            "Create a node. Without a parent it lands in the scope the "
            "user is working in — inside the Object they have open, "
            "else at the assembly root. Returns the new node's id."
        ),
        "input_schema": _obj({
            "type": {"type": "string",
                     "description": "A type from list_node_types."},
            "params": _PARAMS,
            "name": {"type": "string",
                     "description": "Shown in the tree; auto-named if "
                                    "omitted. Say what it is, in the "
                                    "form \"Cube [Body]\"."},
            "parent_id": dict(_ID, description="Where to put it."),
            "index": {"type": "integer",
                      "description": "Position among the parent's "
                                     "children."},
        }, ["type"]),
    },
    {
        "name": "set_params",
        "description": (
            "Change parameters, name or visibility on existing nodes. "
            "Only the keys you pass are touched. Typing a placement "
            "(x/y/z/rx/ry/rz) onto a mated part releases the mate — "
            "the mate would otherwise overwrite what you set."
        ),
        "input_schema": _obj({
            "changes": {
                "type": "array",
                "description": "One entry per node.",
                "items": _obj({
                    "id": {"type": "integer"},
                    "params": _PARAMS,
                    "name": {"type": "string"},
                    "visible": {"type": "boolean"},
                }, ["id"]),
            },
        }, ["changes"]),
    },
    {
        "name": "set_pose",
        "description": (
            "Pose a character in one call: set the bend angles of any "
            "number of `joint` nodes, by name or id. A joint rotates "
            "everything inside it about its pivot, and joints nest — a "
            "hand in a forearm in an upper arm — so the tree IS the "
            "armature and a pose is a handful of angles. Angles past a "
            "joint's min/max limits are clamped (and reported). The "
            "result lists every joint with its pivot and angles; pass "
            "{} to just list them."
        ),
        "input_schema": _obj({
            "joints": {
                "type": "object",
                "description": "{\"<joint name or id>\": {\"rx\": deg, "
                               "\"ry\": deg, \"rz\": deg}, ...}. An "
                               "axis left out keeps its angle.",
            },
        }, ["joints"]),
    },
    {
        "name": "wrap_nodes",
        "description": (
            "Apply an operation to existing nodes by wrapping them in "
            "it — this is how an extrude, a transform or a boolean is "
            "applied here. For a difference, the FIRST node stays the "
            "solid and the rest are subtracted, so order matters. The "
            "nodes must share a parent. Returns the wrapper's id."
        ),
        "input_schema": _obj({
            "ids": _IDS,
            "operation": {"type": "string", "enum": WRAP_TYPES},
            "params": _PARAMS,
            "name": {"type": "string"},
        }, ["ids", "operation"]),
    },
    {
        "name": "move_node",
        "description": (
            "Reparent or reorder a node — how you put a shape inside an "
            "extrude, or a part into a group."
        ),
        "input_schema": _obj({
            "node_id": _ID,
            "parent_id": dict(_ID, description="The new parent."),
            "index": {"type": "integer",
                      "description": "Position among its children "
                                     "(default last)."},
        }, ["node_id", "parent_id"]),
    },
    {
        "name": "duplicate_node",
        "description": "Copy a node and its subtree next to itself.",
        "input_schema": _obj({"node_id": _ID}, ["node_id"]),
    },
    {
        "name": "delete_nodes",
        "description": "Remove nodes and their subtrees.",
        "input_schema": _obj({"ids": _IDS}, ["ids"]),
    },
    {
        "name": "ungroup_node",
        "description": (
            "Replace a container by its children — the inverse of "
            "wrap_nodes."
        ),
        "input_schema": _obj({"node_id": _ID}, ["node_id"]),
    },
    {
        "name": "set_color",
        "description": (
            "Colour nodes. Reuses an existing colour wrapper rather "
            "than stacking a new one. A colour makes the whole-document "
            "exact render pause (an STL carries no colour), but each "
            "part is still rendered exactly on its own."
        ),
        "input_schema": _obj({
            "ids": _IDS,
            "color": {"type": "string",
                      "description": "#rrggbb, or an OpenSCAD colour "
                                     "name."},
            "alpha": {"type": "number",
                      "description": "0 (clear) to 1 (opaque)."},
            "material": {"type": "string", "enum": MATERIALS,
                         "description": "How the surface shades in the "
                                        "3D view: Metal, Glass, Rubber, "
                                        "Skin... (OpenSCAD itself has no "
                                        "materials; the choice is kept "
                                        "in the file)."},
        }, ["ids", "color"]),
    },
    {
        "name": "round_edges",
        "description": (
            "Round the edges of nodes after extrusion — wraps them in "
            "minkowski() with a small sphere, the OpenSCAD idiom. "
            "Expensive to render; keep the radius small."
        ),
        "input_schema": _obj({
            "ids": _IDS,
            "radius": {"type": "number", "description": "mm."},
        }, ["ids"]),
    },
    {
        "name": "apply_code",
        "description": (
            "Parse an OpenSCAD program and apply it as REAL NODES — not "
            "pasted text. For anything with structure this beats a "
            "dozen add_node calls, and the result is an ordinary "
            "editable tree. It lands in the scope the user is working "
            "in unless you name one. Constructs outside the importable "
            "subset come back as warnings; for a library the parser "
            "cannot read (BOSL2…), add a scad_raw node instead. End "
            "each statement with a `// Label` comment (`cube(10);  // "
            "Body`): the node is named \"Cube [Body]\" in the tree."
        ),
        "input_schema": _obj({
            "code": {"type": "string",
                     "description": "The OpenSCAD program."},
            "mode": {
                "type": "string",
                "enum": ["append", "replace"],
                "description": "'append' (default) adds it alongside "
                               "what is there; 'replace' swaps the "
                               "scope's contents for it.",
            },
            "into_id": dict(_ID, description=(
                "Apply inside this Object/container instead of the "
                "scope the user is in.")),
        }, ["code"]),
    },

    # ── Parts and assemblies ───────────────────────────────────────
    {
        "name": "make_object",
        "description": (
            "Promote nodes into an Object — a part definition that "
            "compiles to its own OpenSCAD module, so the program reads "
            "as an assembly of named parts. A Group converts in place; "
            "anything else is wrapped."
        ),
        "input_schema": _obj({
            "ids": _IDS,
            "name": {"type": "string"},
        }, ["ids"]),
    },
    {
        "name": "add_instance",
        "description": (
            "Place another instance of an Object into the assembly: one "
            "placed call of its module, with its own position, rotation "
            "and colour. Build a part once and instance it rather than "
            "duplicating its geometry."
        ),
        "input_schema": _obj({
            "node_id": dict(_ID, description="The Object to instance."),
            "params": _PARAMS,
        }, ["node_id"]),
    },
    {
        "name": "make_master",
        "description": (
            "Move a node into the Masters store and leave a Linked copy "
            "where it was. Editing the master then updates every copy — "
            "the other kind of reuse, for repeated geometry rather than "
            "named parts."
        ),
        "input_schema": _obj({"node_id": _ID}, ["node_id"]),
    },
    {
        "name": "add_linked_copy",
        "description": (
            "Add another Linked copy of a master, with its own "
            "placement."
        ),
        "input_schema": _obj({
            "node_id": dict(_ID, description="The master to copy."),
            "params": _PARAMS,
        }, ["node_id"]),
    },
    {
        "name": "attach_parts",
        "description": (
            "Mate one part to another, anchor to anchor: the two "
            "anchors coincide and their directions oppose (the BOSL2 "
            "attach() model — no constraint solver). The mate is live, "
            "so moving the parent moves the child. The parent must be a "
            "SIBLING of the child. Pass detach:true to release one."
        ),
        "input_schema": _obj({
            "node_id": dict(_ID, description="The part that moves."),
            "parent": {"type": "string",
                       "description": "Name of the part to attach to."},
            "anchor": {"type": "string",
                       "description": "Anchor on the moving part "
                                      "(list_anchors)."},
            "parent_anchor": {"type": "string",
                              "description": "Anchor on the parent."},
            "offset": {"type": "number",
                       "description": "mm along the mate axis."},
            "spin": {"type": "number",
                     "description": "Degrees about the mate axis."},
            "detach": {"type": "boolean",
                       "description": "Release the mate instead."},
        }, ["node_id"]),
    },
    {
        "name": "insert_part",
        "description": (
            "Insert a parametric part from the library as one finished "
            "Object. Dimensions default to the chosen standard size; "
            "override only what the user asked to change."
        ),
        "input_schema": _obj({
            "part_id": {"type": "string",
                        "description": "From list_parts."},
            "size": {"type": "string",
                     "description": "A size name from that part's "
                                    "table, e.g. 'CF40' or 'M6'."},
            "dims": {"type": "object",
                     "description": "Dimension overrides in mm."},
            "name": {"type": "string"},
        }, ["part_id"]),
    },
    {
        "name": "select_nodes",
        "description": (
            "Select nodes in the window, so the user sees what you mean "
            "and the geometry is highlighted in both viewers. Pass no "
            "ids to clear the selection."
        ),
        "input_schema": _obj({"ids": _IDS}),
    },

    # ── Document ───────────────────────────────────────────────────
    {
        "name": "set_reference_image",
        "description": (
            "Put a reference picture — a photo, a sketch, a character "
            "sheet — on one of the axis planes, to model against it "
            "(Blender's reference images). It shows in the 2D view "
            "while that plane is shown and in the 3D view on its plane, "
            "behind the model, and is saved with the document. Pass "
            "clear to remove them all, or remove with an index."
        ),
        "input_schema": _obj({
            "path": {"type": "string",
                     "description": "Absolute path of a PNG/JPEG."},
            "plane": {"type": "string", "enum": ["Top", "Front", "Side"],
                      "description": "Top = XY (default), Front = XZ, "
                                     "Side = YZ."},
            "x": {"type": "number",
                  "description": "The picture's lower-left corner along "
                                 "the plane's horizontal axis, mm "
                                 "(default: centred on the origin)."},
            "y": {"type": "number",
                  "description": "... along the plane's vertical axis."},
            "width": {"type": "number",
                      "description": "Width in mm (default 100); the "
                                     "height follows the picture."},
            "offset": {"type": "number",
                       "description": "The plane's distance along its "
                                      "normal, mm — e.g. a Front picture "
                                      "set behind the model."},
            "opacity": {"type": "number",
                        "description": "0-1 (default 0.5)."},
            "remove": {"type": "integer",
                       "description": "Remove the picture at this index "
                                      "instead."},
            "clear": {"type": "boolean",
                      "description": "Remove every reference picture."},
        }),
    },
    {
        "name": "set_render_options",
        "description": (
            "The document-wide segment count ($fn) for round objects, "
            "and the 3D camera. Higher segments are smoother and slower "
            "— raise it for an export, not while iterating."
        ),
        "input_schema": _obj({
            "segments": {"type": "integer",
                         "description": "Global $fn (3-512)."},
            "segments_on": {"type": "boolean",
                            "description": "False lets each object keep "
                                           "its own $fn."},
            "orientation": {"type": "string", "enum": ORIENTATIONS},
            "fit": {"type": "boolean",
                    "description": "Frame the whole model."},
            "projection": {"type": "string", "enum": PROJECTIONS,
                           "description": "The user's 3D projection: "
                                          "perspective or orthographic."},
            "stage": {"type": "boolean",
                      "description": "Stand the model on a round "
                                     "platform with a soft shadow from "
                                     "a top-left light, instead of the "
                                     "ground grid (also what "
                                     "render_view shows)."},
        }),
    },
    {
        "name": "load_example",
        "description": (
            "Replace the document with a built-in example. Like "
            "new_document this discards the current model, so it "
            "refuses unsaved work unless discard_unsaved_changes is "
            "set."
        ),
        "input_schema": _obj({
            "name": {"type": "string",
                     "description": "Example name from list_examples."},
            "discard_unsaved_changes": {"type": "boolean"},
        }, ["name"]),
    },
    {
        "name": "new_document",
        "description": (
            "Start an empty document. The user's unsaved work is real: "
            "this refuses unless discard_unsaved_changes is set. Offer "
            "to save instead."
        ),
        "input_schema": _obj({
            "discard_unsaved_changes": {"type": "boolean"},
        }),
    },
    {
        "name": "open_document",
        "description": (
            "Open a .kcad document, import a .scad program as objects, "
            "or import a mesh (.stl/.obj/.off/.3mf) as one part. "
            "Refuses to discard unsaved work unless "
            "discard_unsaved_changes is set."
        ),
        "input_schema": _obj({
            "path": {"type": "string", "description": "Absolute path."},
            "discard_unsaved_changes": {"type": "boolean"},
        }, ["path"]),
    },
    {
        "name": "save_document",
        "description": (
            "Save the document. With no path it saves over the file the "
            "user already has open."
        ),
        "input_schema": _obj({
            "path": {"type": "string",
                     "description": "Absolute path ending in .kcad. "
                                    "Omit to save in place."},
        }),
    },
    {
        "name": "export_document",
        "description": (
            "Export by the path's extension: .scad writes the program, "
            ".stl writes the mesh, .png writes a picture of the 3D "
            "view. An STL goes through OpenSCAD when it is installed "
            "(exact, booleans really cut) and through the built-in "
            "tessellator otherwise — the result says which, and an "
            "approximated export is not one to send to a printer. A "
            "big model can take a while. A PNG is the model alone (no "
            "grid or badge) in the user's render style, colours and "
            "lighting: `view` 'current' keeps the user's camera, a "
            "preset name frames the whole model from that side, and "
            "'all' writes one numbered file per standard view beside "
            "the path, the front-right isometric first."
        ),
        "input_schema": _obj({
            "path": {"type": "string",
                     "description": "Absolute path ending in .scad, "
                                    ".stl, .3mf (3MF needs OpenSCAD) "
                                    "or .png."},
            "view": {"type": "string",
                     "enum": ["current", *STILL_VIEWS, "all"],
                     "description": "PNG only: which camera. Default "
                                    "'current'."},
            "width": {"type": "integer",
                      "description": "PNG only: pixels wide. Default "
                                     "twice the 3D view's width for "
                                     "'current', else %d." %
                                     PNG_DEFAULT_SIZE[0]},
            "height": {"type": "integer",
                       "description": "PNG only: pixels high. Default "
                                      "twice the 3D view's height for "
                                      "'current', else %d." %
                                      PNG_DEFAULT_SIZE[1]},
            "transparent": {"type": "boolean",
                            "description": "PNG only: leave the "
                                           "background transparent."},
        }, ["path"]),
    },
    {
        "name": "publish_to_printables",
        "description": (
            "Build a complete Printables upload bundle for the open "
            "model in one call: the mesh (STL and 3MF), the "
            "parametric .scad source, the .kcad project, preview "
            "renders of every side (the front-right isometric "
            "first, as the cover), description.txt "
            "and upload-form.txt (every field of Printables' add-a-"
            "model form, already answered). "
            "Printables has NO upload API, so this does not and "
            "cannot post the model — it prepares everything and the "
            "user drops the folder into printables.com themselves. "
            "Say that plainly rather than claiming the model is "
            "published.\n"
            "WRITE THE DESCRIPTION YOURSELF and pass it in: look at "
            "the model first (get_document_info, list_tree, "
            "render_view) and describe what the thing actually is, "
            "what it is for, its size in mm, which variables are "
            "worth changing, and suggested print settings. PLAIN "
            "TEXT, not Markdown — Printables' description box shows "
            "hashes and backticks back as literal characters. "
            "Leaving `description` out falls back to a generated "
            "skeleton, which is worse. Whatever you write, the "
            "bundle appends a credit naming KherveCAD "
            "(khervetools.com), OpenSCAD and Claude — do not strip "
            "or duplicate that, and do not claim the model is human-"
            "designed if you designed it."
        ),
        "input_schema": _obj({
            "title": {"type": "string",
                      "description": "Listing title, also the file "
                                     "stem."},
            "description": {"type": "string",
                            "description": "The listing body, in "
                                           "plain text. Write this."},
            "summary": {"type": "string",
                        "description": "Printables' required one-line "
                                       "summary, max %d characters. "
                                       "Write this too." %
                                       SUMMARY_LIMIT},
            "category": {"type": "string", "enum": CATEGORIES,
                         "description": "Printables' required main "
                                        "category. Defaults to %s." %
                                        DEFAULT_CATEGORY},
            "origin": {"type": "string", "enum": ORIGINS,
                       "description": "Where the model came from. "
                                      "Defaults to %s." %
                                      DEFAULT_ORIGIN},
            "tags": {"type": "array", "items": {"type": "string"},
                     "description": "Printables tags, lowercase."},
            "license": {"type": "string", "enum": LICENSES,
                        "description": "Defaults to %s." %
                                       DEFAULT_LICENSE},
            "folder": {"type": "string",
                       "description": "Absolute path for the bundle "
                                      "folder. Defaults to a folder "
                                      "beside the document."},
            "formats": {"type": "array",
                        "items": {"type": "string", "enum": list(FORMATS)},
                        "description": "Defaults to all four."},
            "views": {"type": "array",
                      "items": {"type": "string", "enum": list(STILL_VIEWS)},
                      "description": "Camera angles to render. "
                                     "Defaults to every one: %s — the "
                                     "front-right Isometric is always "
                                     "first, as the cover." %
                                     ", ".join(DEFAULT_VIEWS)},
            "open_browser": {"type": "boolean",
                             "description": "Open the Printables "
                                            "upload page and reveal "
                                            "the folder. Off by "
                                            "default — turn it on "
                                            "when the user has said "
                                            "they want to upload "
                                            "now."},
        }, ["title"]),
    },

    # ── Fillet ─────────────────────────────────────────────────────
    {
        "name": "list_edges",
        "description": (
            "The edges of a node's solid that a fillet can round — "
            "every crease where two faces meet at more than min_angle, "
            "grouped into tangent-continuous chains (a cylinder's rim "
            "is ONE chain; a box has 12). Each chain gives its `seed` "
            "(6 numbers: a segment's start and end, in the node's own "
            "frame — what fillet_edges takes), its ends, length, "
            "dihedral angle, convex (outside corner) or not, closed, "
            "and centre, longest first. Coordinates are local to the "
            "node, not the assembly."
        ),
        "input_schema": _obj({
            "node_id": _ID,
            "min_angle": {"type": "number",
                          "description": "Degrees; default 20. Facets "
                                         "below it are one surface."},
        }, ["node_id"]),
    },
    {
        "name": "fillet_edges",
        "description": (
            "Round (or chamfer) chosen edges of a node — SolidWorks' "
            "Fillet. Wraps the node in a fillet (or adds to the fillet "
            "it already is / sits in) and records the edges as seed "
            "segments from list_edges, by `edges` rows or by `chains` "
            "indices into list_edges(node_id). A convex edge is cut "
            "round, a concave one filled. The result shows in the "
            "exact OpenSCAD render (render_view after a moment); the "
            "built-in preview cannot cut. Radius is in mm (the "
            "chamfer's setback along each face)."
        ),
        "input_schema": _obj({
            "node_id": _ID,
            "edges": {"type": "array",
                      "items": {"type": "array",
                                "items": {"type": "number"}},
                      "description": "Seed rows [x1, y1, z1, x2, y2, "
                                     "z2] from list_edges."},
            "chains": {"type": "array", "items": {"type": "integer"},
                       "description": "Indices into list_edges' list "
                                      "for the same node, instead of "
                                      "or as well as `edges`."},
            "radius": {"type": "number", "description": "mm; default 2."},
            "kind": {"type": "string", "enum": ["round", "chamfer"]},
            "detail": {"type": "integer",
                       "description": "Segments across a round; "
                                      "default 6."},
        }, ["node_id"]),
    },
]

#: Name -> definition, for the executor and the access-level checks.
BY_NAME = {t["name"]: t for t in TOOLS}
