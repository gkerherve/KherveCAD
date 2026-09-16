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
             "Rubber", "Skin", "Gold", "Copper", "Emissive",
             "Brick", "Concrete", "Render", "Roof tiles", "Slate", "Stone",
             "Bark", "Leaves"]

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

#: The three-quarter stills: every corner from above, the classic
#: product angles and the underside — pictures of a solid, where a face
#: seen square-on reads as a flat 2D drawing.  The front-right
#: isometric leads, as the cover.
ISO_VIEWS = ("Isometric", "Isometric front-left", "Isometric back-right",
             "Isometric back", "Three-quarter front", "Bird's-eye",
             "Low angle", "Underside")

#: The square-on faces, still on offer when a listing wants them.
ORTHO_VIEWS = ("Front", "Back", "Left", "Right", "Top", "Bottom")

#: Every standard still a Printables bundle or File > Export PNG can
#: render; `engine.CAMERA_ROTATIONS` holds the camera for each.
STILL_VIEWS = ISO_VIEWS + ORTHO_VIEWS

#: Camera angles rendered unless the caller says otherwise: the
#: three-quarter set.  The upload page keeps the files in order, so the
#: front-right isometric still gets the cover.
DEFAULT_VIEWS = ISO_VIEWS

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
    "section_loft", "blend", "bend", "twist", "taper", "lattice", "subdivide",
    "pattern", "shell", "sculpt",
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


def _vec3(description: str) -> dict:
    return {"type": "array", "items": {"type": "number"},
            "minItems": 3, "maxItems": 3, "description": description}

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
            "The document as a whole: file path and unsaved state, the "
            "document UNIT (`unit`: nm, um, mm, cm, m or in — what one "
            "model unit means; every size and coordinate in every tool "
            "is in it, and keys ending _mm are true millimetres), node "
            "and Object counts, the global segment count, whether the "
            "OpenSCAD engine was found (without it booleans are only "
            "approximated in the preview), which Object the user is "
            "editing, the model's bounding box, and any validation "
            "errors. Call this first."
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
            "overlay_reference": {
                "type": "boolean",
                "description": "Compare with the photo: the reference "
                               "image is drawn OVER the model (onion "
                               "skin), square on to its plane and "
                               "orthographic unless you aim the camera "
                               "yourself, picture and model both framed. "
                               "Where the model's outline leaves the "
                               "photo is where to sculpt next.",
            },
        }),
    },
    {
        "name": "list_parts",
        "description": (
            "The parametric part library: vacuum components (CF/KF "
            "flanges, fittings, valves, pumps, analysers, "
            "manipulators), ISO-threaded fasteners, chemistry glassware, "
            "room furniture, home furniture for every room (kitchen, "
            "bathroom, bedroom, living and dining room), ready-made cars "
            "and hand tools, and LEGO-compatible bricks, plates, tiles, "
            "slopes and baseplates — with each part's standard sizes, "
            "the dimensions you may override and, where it has them, "
            "its colours. Use a library part rather than modelling a CF "
            "flange or a brick from scratch."
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
            "size and centre in the document's unit (`unit`), where the "
            "object really sits in "
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
        "name": "probe_surface",
        "description": (
            "Cast a ray at the model and read the surface it hits: the "
            "world point, the outward unit normal there, the distance "
            "and which part it is. This is how to put an eye, a knob, a "
            "boss or a label ON a curved surface (a loft, a blend, a "
            "sphere) without deriving the geometry by hand: place it at "
            "point + normal * inset, orient it along the normal. The "
            "ray runs from `from` along `direction` (or through `to`); "
            "`hits` lists every crossing nearest first, each marked "
            "entering (into the solid) or leaving, so the far side of a "
            "part is one call away too. Probes the visible parts of the "
            "scope, or only `node_ids`. Uses the built-in tessellation "
            "(booleans approximated: a difference reads as its first "
            "operand)."
        ),
        "input_schema": _obj({
            "from": _vec3("Ray origin [x, y, z] in mm."),
            "direction": _vec3("Ray direction [dx, dy, dz] (any length)."),
            "to": _vec3("A point the ray passes through, instead of "
                        "`direction`."),
            "node_ids": _IDS,
            "max_hits": {"type": "integer",
                         "description": "Keep only the nearest N hits "
                                        "(default: all)."},
        }, ["from"]),
    },
    {
        "name": "sample_surface",
        "description": (
            "Scatter N points over a part's surface, each with its "
            "outward normal — for the details that come in numbers: "
            "curls of hair over a head, tubercles along a whale, rivets "
            "on a hull, pebbles on a base. Evenly spread (random darts "
            "kept `spacing` mm apart, repeatable with `seed`), limited "
            "to faces looking within `max_angle` of `facing` (the top "
            "of a head: [0, 0, 1]) and/or to a `within` box, so the "
            "face or the front stays clear. Then add one sphere or "
            "part per point, sunk `inset` mm along the normal. Fewer "
            "points come back when the surface is full at that "
            "spacing. Built-in tessellation (booleans approximated)."
        ),
        "input_schema": _obj({
            "node_ids": _IDS,
            "count": {"type": "integer",
                      "description": "Points wanted (default 20)."},
            "spacing": {"type": "number",
                        "description": "Minimum distance between points "
                                       "in mm (default: an even spread "
                                       "of `count`)."},
            "facing": _vec3("Keep faces looking this way, e.g. [0, 0, 1] "
                            "for the top."),
            "max_angle": {"type": "number",
                          "description": "Degrees off `facing` still "
                                         "kept (default 90)."},
            "within": {"type": "object",
                       "description": "World box keeping faces whose "
                                      "centre lies inside: {\"min\": "
                                      "[x, y, z], \"max\": [x, y, z]}.",
                       "properties": {"min": _vec3("Low corner."),
                                      "max": _vec3("High corner.")}},
            "seed": {"type": "integer",
                     "description": "Random seed (default 1): the same "
                                    "seed gives the same points."},
        }, ["node_ids"]),
    },
    {
        "name": "sculpt_stroke",
        "description": (
            "Sculpt a surface with brush strokes — Blender's sculpt "
            "mode, kept as parameters: grab drags the surface along "
            "`direction` by `strength` mm, inflate pushes it out along "
            "its normals (negative pulls in), smooth relaxes it, flatten "
            "presses it onto a plane, pinch draws it to the centre; each "
            "falls off to nothing at `radius`. Give one stroke, or "
            "several in `strokes` (one undo step). `node_id` is a "
            "sculpt node, or any solid — a blend, a subdivided cage, an "
            "imported scan — which is wrapped in one. Points are WORLD "
            "coordinates from probe_surface; `mirror` repeats every "
            "stroke across the part's x, y or z plane (a face from one "
            "side). This is what turns a blob of primitives into a "
            "likeness: probe the surface, push it where the photo says, "
            "render_view, repeat."
        ),
        "input_schema": _obj({
            "node_id": _ID,
            "kind": {"type": "string",
                     "enum": ["grab", "inflate", "smooth", "flatten",
                              "pinch"]},
            "at": _vec3("Brush centre [x, y, z] in world mm."),
            "radius": {"type": "number", "description": "mm."},
            "strength": {"type": "number",
                         "description": "mm for grab/inflate; 0-1 for "
                                        "smooth (more = passes), flatten "
                                        "and pinch."},
            "direction": _vec3("grab only: which way to drag."),
            "strokes": {"type": "array",
                        "description": "Several strokes at once: "
                                       "[{kind, at, radius, strength, "
                                       "direction}].",
                        "items": {"type": "object"}},
            "mirror": {"type": "string", "enum": ["none", "x", "y", "z"],
                       "description": "Repeat strokes across this plane "
                                      "of the part (set on the node)."},
            "detail": {"type": "number",
                       "description": "Refine the surface to this max "
                                      "edge length in mm before "
                                      "sculpting (default 0: as it is — "
                                      "a blend or a scan is dense "
                                      "already; a cube needs it)."},
        }, ["node_id"]),
    },
    {
        "name": "mesh_from_photo",
        "description": (
            "Turn ONE picture into a 3D surface with an image-to-3D "
            "model and import it as a mesh part: `backend` tripo "
            "(api.tripo3d.ai) or meshy (api.meshy.ai) with the user's "
            "API key (kept in the app's settings or TRIPO_API_KEY / "
            "MESHY_API_KEY), or local — a command the user configured "
            "that takes {image} and writes {output}. The result is "
            "scaled to `size_mm` on its longest side, stood on Z = 0, "
            "and is a plausible surface (the far side is guessed): "
            "sculpt it against the photo afterwards. Takes minutes; "
            "the file access needs the full level."
        ),
        "input_schema": _obj({
            "image_path": {"type": "string",
                           "description": "Absolute path of the picture."},
            "backend": {"type": "string", "enum": ["tripo", "meshy",
                                                  "local"]},
            "size_mm": {"type": "number",
                        "description": "Longest side after import "
                                       "(default 100)."},
            "name": {"type": "string",
                     "description": "Name of the imported part."},
            "api_key": {"type": "string",
                        "description": "Only when the app has none "
                                       "stored for that backend."},
            "command": {"type": "string",
                        "description": "local only: the command template "
                                       "with {image} and {output}."},
        }, ["image_path"]),
    },
    {
        "name": "face_landmarks",
        "description": (
            "Where a human figure's face landmarks are: eye_l/r, brow_l/r, "
            "cheek_l/r, mouth_l/r, jaw_l/r, ear_l/r, nose_tip, "
            "nose_bridge, forehead, lip_top, lip_bottom, chin, head_top — "
            "in the node's own frame, in world mm, and as PIXEL positions "
            "on each reference image (so they can be compared with where "
            "the photo has them). Read this, look at the photo, then "
            "fit_face."
        ),
        "input_schema": _obj({"node_id": _ID}, ["node_id"]),
    },
    {
        "name": "fit_face",
        "description": (
            "Make a human figure's face match photographs: give where "
            "its landmarks are in a reference image (pixel positions, "
            "the names from face_landmarks) and the face sliders are "
            "solved so the model's landmarks project onto them, then a "
            "smooth warp carries each landmark the rest of the way. One "
            "photo pins the two axes of its plane; a front and a side "
            "photo pin all three. The figure may be turned (the fit "
            "reads its placement) and the head's own turn, tilt and nod "
            "are solved with it. Sets the node's `targets`, `pose` and `warp` "
            "— this is what turns the generic head into a likeness; "
            "sculpt afterwards for what landmarks cannot say."
        ),
        "input_schema": _obj({
            "node_id": _ID,
            "landmarks": {
                "type": "array",
                "description": "[{name, image, px, py}] — landmark name, "
                               "reference image index (default 0), pixel "
                               "x/y in that picture (y down). Or {name, "
                               "plane, u, v} in mm on a plane.",
                "items": {"type": "object"}},
            "sliders": {"type": "array", "items": {"type": "string"},
                        "description": "Sliders to adjust (default: the "
                                       "proportions a photo pins down)."},
            "warp": {"type": "boolean",
                     "description": "Carry the residual with a warp "
                                    "(default true)."},
            "stiffness": {"type": "number",
                          "description": "Regularisation, 0.05 loose .. 2 "
                                         "stiff (default 0.3)."},
            "fit_head": {"type": "boolean",
                         "description": "Also solve the head's turn, tilt "
                                        "and nod (the head bone's pose), "
                                        "default true — a photo is rarely "
                                        "square on."},
        }, ["node_id", "landmarks"]),
    },
    {
        "name": "section",
        "description": (
            "Cut the model with a plane and get the cross-section: a "
            "hatched PNG with a grid, plus the outlines — each "
            "closed or not, its area (holes negative; `area` in the "
            "document's unit², `area_mm2` true mm²) and extent. Shows "
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
                       "description": "Where along the axis, in the "
                                      "document's unit. Defaults to "
                                      "the model's middle."},
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
            "number of `joint` nodes, by name or id — or, with node_id "
            "and `bones`, pose a human figure's own rig (MakeHuman's "
            "163 bones with skin weights). A joint rotates "
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
            "node_id": dict(_ID, description=(
                "A human figure (or the Object holding it): pose its "
                "rig with `bones` instead of joint nodes.")),
            "bones": {
                "type": "object",
                "description": "For a human figure: {\"<bone>\": {\"rx\": "
                               "deg, \"ry\": deg, \"rz\": deg}} — "
                               "MakeHuman's rig (upperarm01/02.L/R, "
                               "lowerarm01/02, wrist, upperleg01/02, "
                               "lowerleg01/02, foot, spine01-05, "
                               "neck01-03, head, jaw, clavicle, ...); "
                               "pass {} to list the bones. Angles turn "
                               "the bone about its head in the body's "
                               "axes and carry everything below it.",
            },
        }),
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
            "Body`): the node is named \"Cube [Body]\" in the tree, and "
            "the label on a module's placed call (`Part();  // Left "
            "flipper`) names that Object."
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
            "kind": {"type": "string",
                     "enum": ["coincident", "concentric", "angle"],
                     "description": "coincident (default): the anchors "
                                    "touch. concentric: axes aligned, "
                                    "the part slides along the axis "
                                    "(offset = the slide; a drag keeps "
                                    "the mate). angle: a hinge, the "
                                    "child turned by `angle` degrees "
                                    "about the anchor's edge."},
            "align": {"type": "string", "enum": ["opposed", "same"],
                      "description": "opposed (default): face to face. "
                                     "same: flush, both anchors "
                                     "pointing the same way."},
            "angle": {"type": "number",
                      "description": "Hinge angle in degrees (kind "
                                     "angle)."},
            "ratio": {"type": "number",
                      "description": "Gear mate: the child's spin "
                                     "follows the parent's spin times "
                                     "this ratio, the opposite way."},
            "min_offset": {"type": "number",
                           "description": "Limit mate: the offset / "
                                          "slide never goes below this."},
            "max_offset": {"type": "number",
                           "description": "...nor above this."},
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
            "color": {"type": "string",
                      "description": "For parts that come in colours "
                                     "(Lego): one of the names "
                                     "list_parts gives, e.g. 'Red'."},
            "name": {"type": "string"},
        }, ["part_id"]),
    },
    {
        "name": "list_crystals",
        "description": (
            "The crystal library: 32 standard structures — FCC, BCC, "
            "HCP and simple-cubic metals, diamond and zinc-blende "
            "semiconductors, wurtzite, rock salt, CsCl, fluorite, "
            "rutile, anatase, perovskite, alpha-quartz, graphite, h-BN — "
            "each with its space group, lattice (nm, degrees), atoms per "
            "cell, density and coordination polyhedra. Pass `crystal` "
            "for one in full (every atom's fractional coordinates, the "
            "nearest distances). Use it before build_crystal; never type "
            "a crystal's atoms yourself."
        ),
        "input_schema": _obj({
            "category": {"type": "string",
                         "description": "Filter to one family."},
            "crystal": {"type": "string",
                        "description": "A key, e.g. 'quartz', 'cu', "
                                       "'rutile'."},
        }),
    },
    {
        "name": "build_crystal",
        "description": (
            "Build a crystal in nanometres as Objects: its UNIT CELL "
            "(atoms at covalent radii, lattice box, coordination "
            "polyhedra such as SiO4 tetrahedra), a SUPERCELL (for loops "
            "over na x nb x nc cells) and/or a PARTICLE — a shape filled "
            "with every cell whose centre is inside, or with blocks of "
            "N x N x N cells. build 'hierarchy' makes all three side by "
            "side. The build is counted first (cells, atoms, polyhedra, "
            "triangles) and refused past what the 3D view can draw, with "
            "what to change; dry_run returns the counts only. An empty "
            "document is switched to nm. Tunables become prefixed "
            "document variables (quartz_r, quartz_N) the user can edit."
        ),
        "input_schema": _obj({
            "crystal": {"type": "string",
                        "description": "Library key from list_crystals."},
            "custom": {"type": "object",
                       "description": "A crystal the library lacks: {name, "
                                      "a, b, c, alpha, beta, gamma, atoms: "
                                      "[[element, fx, fy, fz], ...], "
                                      "polyhedra: {centre, ligand, "
                                      "cutoff}, units: 'angstrom' | "
                                      "'nm'} — every atom of the "
                                      "conventional cell, fractional."},
            "build": {"type": "string",
                      "enum": ["hierarchy", "unit_cell", "supercell",
                               "particle", "scatter"],
                      "description": "'scatter' spreads `count` copies "
                                     "of the particle over an area, each "
                                     "sitting on the plane and turned at "
                                     "random — a dispersion on a "
                                     "substrate. One particle is built "
                                     "and instanced, so the copies are "
                                     "nearly free."},
            "count": {"type": "integer",
                      "description": "scatter: how many particles "
                                     "(default 12)."},
            "area_nm": {"type": "array", "items": {"type": "number"},
                        "description": "scatter: the patch [x, y] they "
                                       "are spread over, nm."},
            "seed": {"type": "integer",
                     "description": "scatter: the same seed gives the "
                                    "same arrangement."},
            "min_gap_nm": {"type": "number",
                           "description": "scatter: smallest gap between "
                                          "two particles (default 1)."},
            "substrate": {"type": "boolean",
                          "description": "scatter: draw a thin slab under "
                                         "the patch (default true)."},
            "random_turn": {"type": "boolean",
                            "description": "scatter: turn each particle "
                                           "at random about z (default "
                                           "true)."},
            "representation": {"type": "string",
                               "enum": ["auto", "atoms", "polyhedra",
                                        "both"],
                               "description": "How a cell is drawn. auto: "
                                              "both in the unit cell, "
                                              "polyhedra (else atoms) in "
                                              "supercells."},
            "supercell": {"type": "array", "items": {"type": "integer"},
                          "description": "[na, nb, nc], default [4, 4, 4]."},
            "shape": {"type": "string",
                      "enum": ["sphere", "hemisphere", "cube", "box",
                               "cylinder", "hexagonal_prism",
                               "octahedron"]},
            "size_nm": {"type": "number",
                        "description": "Diameter (sphere, hemisphere, "
                                       "cylinder), edge (cube), across "
                                       "corners (hexagonal prism), tip to "
                                       "tip (octahedron). Default 10."},
            "height_nm": {"type": "number",
                          "description": "Cylinder / hexagonal prism."},
            "box_nm": {"type": "array", "items": {"type": "number"},
                       "description": "Box edges [x, y, z]."},
            "fill": {"type": "string",
                     "enum": ["auto", "atoms", "polyhedra", "blocks"],
                     "description": "What fills the particle; auto keeps "
                                    "cells while light, blocks beyond."},
            "block_cells": {"type": "integer",
                            "description": "Cells per block edge (10: a "
                                           "block is 1000 cells)."},
            "gap": {"type": "number",
                    "description": "Gap between blocks, fraction of a "
                                   "block (0 = solid). Default 0.03."},
            "atom_scale": {"type": "number",
                           "description": "x the covalent radius, default "
                                          "1."},
            "cell_box": {"type": "boolean",
                         "description": "Draw the lattice boxes (default "
                                        "true)."},
            "segments": {"type": "integer",
                         "description": "Sphere segments for atoms "
                                        "(default 12)."},
            "dry_run": {"type": "boolean",
                        "description": "Count only; build nothing."},
        }),
    },
    {
        "name": "build_house",
        "description": (
            "The House Builder in one call: floors of rectangular rooms "
            "(x, y, w, d in mm — wall centre-lines, so rooms sharing an "
            "edge share ONE wall), doors and windows on each room's N/S/"
            "E/W side (see-through glass panes, openings built from solid "
            "wall pieces so the preview shows them), and furniture from "
            "the Part Library. Each floor is an Object stacked in Z; every "
            "piece of furniture is its own Object inside it. Place a piece "
            "with `wall` ('N'/'S'/'E'/'W': back flush against that wall, "
            "turned to face the room, `along` = its centre's distance "
            "from the room's W or S corner, default the middle) or with "
            "x/y from the room's corner and rz; `z` lifts it (wall and "
            "ceiling pieces default to their own height) and `on_top: "
            "true` sets it down on the furniture under it (a TV on its "
            "unit, a microwave on the worktop). A room's `surface` "
            "'garden' or 'paving' is an outdoor area (porch, patio, "
            "driveway, lawn) with no walls or roof. `roof` picks the top "
            "floor's roof (flat by default). Never assemble walls or "
            "furniture by hand."
        ),
        "input_schema": _obj({
            "floors": {
                "type": "array",
                "description": "Bottom to top.",
                "items": {"type": "object", "properties": {
                    "name": {"type": "string"},
                    "wall_height": {"type": "number"},
                    "wall_thickness": {"type": "number"},
                    "slab_thickness": {"type": "number"},
                    "rooms": {"type": "array", "items": {
                        "type": "object", "properties": {
                            "name": {"type": "string"},
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "w": {"type": "number"},
                            "d": {"type": "number"},
                            "surface": {"type": "string",
                                        "enum": ["indoor", "garden",
                                                 "paving"]},
                            "finish": {
                                "type": "string",
                                "description": "This room's own tiles or "
                                "panelling, lining its walls and floor "
                                "(White tiles, Blue tiles, Green metro "
                                "tiles, Marble, Terracotta tiles, Wood "
                                "panelling); omit for the house's."},
                            "openings": {"type": "array", "items": {
                                "type": "object", "properties": {
                                    "kind": {"type": "string",
                                             "enum": ["door", "window",
                                                      "garage door"]},
                                    "side": {"type": "string",
                                             "enum": ["N", "S", "E", "W"]},
                                    "offset": {
                                        "type": "number",
                                        "description": "From the side's "
                                        "W (N/S sides) or S (E/W sides) "
                                        "corner."},
                                    "width": {"type": "number"},
                                    "height": {"type": "number"},
                                    "sill": {"type": "number"}}}},
                            "furniture": {"type": "array", "items": {
                                "type": "object", "properties": {
                                    "part_id": {"type": "string"},
                                    "size": {"type": "string"},
                                    "color": {"type": "string"},
                                    "dims": {"type": "object"},
                                    "name": {"type": "string"},
                                    "wall": {"type": "string",
                                             "enum": ["N", "S", "E", "W"]},
                                    "along": {"type": "number"},
                                    "gap": {"type": "number"},
                                    "x": {"type": "number"},
                                    "y": {"type": "number"},
                                    "z": {"type": "number"},
                                    "rz": {"type": "number"},
                                    "on_top": {"type": "boolean"}},
                                "required": ["part_id"]}}},
                        "required": ["w", "d"]}}}},
            },
            "roof": {"type": "object",
                     "description": "The top floor's roof; omit for flat.",
                     "properties": {
                         "style": {"type": "string",
                                   "enum": ["Flat", "Gable", "Hip",
                                            "Pyramid", "Lean-to"]},
                         "pitch": {"type": "number",
                                   "description": "Degrees, 5-60."},
                         "overhang": {"type": "number"},
                         "ridge": {"type": "string",
                                   "enum": ["auto", "x", "y"]},
                         "color": {
                             "type": "string",
                             "description": "Covering: Brown tiles, Red "
                             "clay, Terracotta pantiles, Grey tiles, "
                             "Slate, Dark slate, Cedar shingles, Thatch, "
                             "Green, Green roof, Zinc, Solar panels."},
                         "wings": {
                             "type": "string",
                             "enum": ["Lean-to", "Gable", "Hip", "Flat",
                                      "Same as main"],
                             "description": "The roof over a side wing — "
                             "a part of a floor with nothing above it, "
                             "like a garage, which would stand open "
                             "otherwise. Default a lean-to on the taller "
                             "part."}}},
            "walls": {
                "type": "object",
                "description": "How the walls are finished.",
                "properties": {
                    "outside": {
                        "type": "string",
                        "description": "Painted plaster, White render, "
                        "Cream render, Red brick, Buff brick, Grey stone, "
                        "Timber cladding, Concrete."},
                    "inside": {
                        "type": "string",
                        "description": "Between rooms: Painted plaster, "
                        "Warm white, Soft grey, Sage, Clay pink, Exposed "
                        "brick."}}},
            "garden": {"type": "object",
                       "description": "Lawn beside the house; omit for "
                                      "none.",
                       "properties": {"width": {"type": "number"},
                                      "depth": {"type": "number"},
                                      "gap": {"type": "number"}}},
            "dry_run": {"type": "boolean",
                        "description": "Check and resolve placements; "
                                       "build nothing."},
        }),
    },
    {
        "name": "list_molecules",
        "description": (
            "The compound library: about 80 common compounds — gases, "
            "inorganic acids, bases and ions, VSEPR shapes (BF3, SF6, "
            "XeF4…), hydrocarbons, alcohols, carbonyls, acids, esters, "
            "nitrogen compounds and solvents, biomolecules and drugs "
            "(amino acids, glucose, caffeine, aspirin) — with formula and "
            "SMILES. Pass `compound` for one in full (3D atoms in nm, "
            "bonds). Anything else is built from its SMILES."
        ),
        "input_schema": _obj({
            "category": {"type": "string",
                         "description": "Filter to one family."},
            "compound": {"type": "string",
                         "description": "A key, name or formula, e.g. "
                                        "'caffeine', 'Water', 'CO2'."},
        }),
    },
    {
        "name": "build_molecule",
        "description": (
            "Build a molecule in 3D, in nanometres, as one Object — from "
            "the library (`compound`: key, name or formula) or from any "
            "SMILES. Every atom gets its VSEPR shape (lone pairs "
            "included: water bent, XeF4 square), rings are placed whole "
            "and the result relaxed — a faithful sketch of the shape, "
            "not a quantum-chemistry optimum. Never place atoms by hand."
        ),
        "input_schema": _obj({
            "compound": {"type": "string",
                         "description": "Library key, name or formula."},
            "smiles": {"type": "string",
                       "description": "Any SMILES, e.g. 'CCO', "
                                      "'c1ccccc1O', '[NH4+]'."},
            "name": {"type": "string"},
            "style": {"type": "string",
                      "enum": ["ball_and_stick", "space_filling",
                               "sticks"]},
            "segments": {"type": "integer",
                         "description": "Round segments (default 16)."},
            "dry_run": {"type": "boolean",
                        "description": "Formula, atoms and triangles "
                                       "only; build nothing."},
        }),
    },
    {
        "name": "build_reaction",
        "description": (
            "Write a chemical reaction in 3D: '2 H2 + O2 -> 2 H2O', 'CH4 "
            "+ 2 O2 -> CO2 + 2 H2O', 'N2 + 3 H2 <=> 2 NH3' (arrows -> <=> "
            "→ ⇌ =, spaces round them and round '+'; coefficients may be "
            "fractions; species are library keys, names, formulas with "
            "charges — NH4+, SO4^2- — or smiles:...). Checks the atom "
            "and charge balance and, with balance (default true), finds "
            "the missing coefficients. Lays the molecules out left to "
            "right with coefficients, + and the arrow in 3D, the formula "
            "under each; returns the balanced equation and the "
            "per-element table."
        ),
        "input_schema": _obj({
            "equation": {"type": "string"},
            "balance": {"type": "boolean",
                        "description": "Find missing coefficients "
                                       "(default true)."},
            "labels": {"type": "boolean",
                       "description": "Formula under each molecule "
                                      "(default true)."},
            "style": {"type": "string",
                      "enum": ["ball_and_stick", "space_filling",
                               "sticks"]},
            "segments": {"type": "integer"},
            "dry_run": {"type": "boolean",
                        "description": "Balance and count only."},
        }, ["equation"]),
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
            "the document unit, and the 3D camera. Higher segments are "
            "smoother and slower — raise it for an export, not while "
            "iterating."
        ),
        "input_schema": _obj({
            "segments": {"type": "integer",
                         "description": "Global $fn (3-512)."},
            "unit": {"type": "string",
                     "enum": ["nm", "um", "mm", "cm", "m", "in"],
                     "description": "What one model unit means — a "
                                    "LABEL for every readout (status "
                                    "bar, 2D view, Analyse, Blueprint, "
                                    "these tools); the geometry is not "
                                    "rescaled. Set it before building a "
                                    "model at another scale: a 100 nm "
                                    "particle is written 100 in a nm "
                                    "document. Saved with the file; one "
                                    "undo step."},
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
            "cavity": {"type": "boolean",
                       "description": "Cavity shading: valleys darker, "
                                      "ridges lighter (Blender's Solid "
                                      "view look)."},
            "edges": {"type": "boolean",
                      "description": "Draw crease and outline edges as "
                                     "thin lines."},
            "scale_bar": {"type": "boolean",
                          "description": "Show a scale bar in the "
                                         "document's unit in the 3D view, "
                                         "true at the orbit centre "
                                         "(everywhere in orthographic)."},
            "overlay": {"type": "boolean",
                        "description": "Draw the reference images OVER "
                                       "the model too (onion skin), to "
                                       "compare a likeness with its "
                                       "photo."},
            "smooth": {"type": "boolean",
                       "description": "Smooth shading: curved surfaces "
                                      "shade as one skin instead of "
                                      "facets (edges over 40° stay "
                                      "sharp). OpenGL only."},
            "opengl": {"type": "boolean",
                       "description": "Draw the faces with OpenGL (exact "
                                      "occlusion, anti-aliased); off "
                                      "uses the built-in painter."},
            "explode": {"type": "number",
                        "description": "Exploded view: push every part "
                                       "away from the assembly's centre, "
                                       "1 = as far again as it already "
                                       "sits; 0 puts them back. A "
                                       "display only — the model does "
                                       "not move."},
            "explode_mode": {"type": "string",
                             "enum": ["Radial", "X", "Y", "Z"],
                             "description": "Which way the parts move: "
                                            "outwards, or along one "
                                            "axis."},
            "cut": {"type": "string", "enum": ["none", "x", "y", "z"],
                    "description": "Cut Through: slice the 3D view "
                                   "across this axis and cap the cut "
                                   "face, to show the inside (holes, "
                                   "walls, threads) — also what "
                                   "render_view shows. 'none' switches "
                                   "it off. A display only: exports and "
                                   "the model stay whole."},
            "cut_position": {"type": "number",
                             "description": "Where the cut goes, 0 to 1 "
                                            "across the model's extent "
                                            "(0.5 = the middle)."},
            "cut_flip": {"type": "boolean",
                         "description": "Keep the other half."},
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
        "name": "export_drawing",
        "description": (
            "A 2D engineering drawing of the model (or the selection): "
            "third-angle Front / Top / Right views and an isometric, "
            "visible edges solid and hidden edges dashed, overall "
            "dimensions, an optional hatched section through the "
            "middle, on an A4/A3 sheet at a standard scale with a title "
            "block. Written by the path's extension: .pdf, .svg, .dxf "
            "(lines on VISIBLE / HIDDEN / DIM / SECTION layers, sheet "
            "mm) or .png. When the user has made a Blueprint for this "
            "document (File > Blueprint), that sheet is exported "
            "instead — their views, dimensions, notes and title block, "
            "re-projected from the model as it is now — unless "
            "blueprint is false; the sheet options below then do not "
            "apply."
        ),
        "input_schema": _obj({
            "path": {"type": "string",
                     "description": "Absolute path ending in .pdf, "
                                    ".svg, .dxf or .png."},
            "sheet": {"type": "string", "enum": ["A4", "A3", "Letter"],
                      "description": "Sheet size, landscape (A4)."},
            "views": {"type": "array", "items": {"type": "string"},
                      "description": "Any of Front, Top, Right, Left, "
                                     "Back, Bottom, Isometric (default "
                                     "Front, Top, Right, Isometric)."},
            "dimensions": {"type": "boolean",
                           "description": "Overall width/height "
                                          "dimensions on the three "
                                          "orthographic views (true)."},
            "section": {"type": "string", "enum": ["x", "y", "z"],
                        "description": "Add a hatched section through "
                                       "the model's middle on this axis."},
            "hidden_lines": {"type": "boolean",
                             "description": "Dashed edges behind the "
                                            "surface (true); off for "
                                            "threaded parts, whose facets "
                                            "swamp the sheet."},
            "scale": {"type": "number",
                      "description": "Drawing scale as a multiplier "
                                     "(0.5 = 1:2, 2 = 2:1); omit for "
                                     "the largest standard scale that "
                                     "fits."},
            "title": {"type": "string"},
            "blueprint": {"type": "boolean",
                          "description": "Export the document's saved "
                                         "Blueprint sheet when it has one "
                                         "(true). False draws a fresh "
                                         "sheet from the options above."},
        }, ["path"]),
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
            "exploded": {"type": "boolean",
                         "description": "PNG only: picture the assembly "
                                        "exploded — every part pulled "
                                        "away from the centre."},
            "scale_to_mm": {"type": "boolean",
                            "description": "STL/3MF of a document not in "
                                           "mm: multiply every length to "
                                           "real millimetres (a 100 nm "
                                           "part becomes 0.0001 mm). "
                                           "Default false: written 1:1, "
                                           "so a slicer reads 1 unit as "
                                           "1 mm — what printing a "
                                           "scale model wants. The "
                                           "result says which."},
        }, ["path"]),
    },
    {
        "name": "publish_to_printables",
        "description": (
            "Build a complete Printables upload bundle for the open "
            "model in one call: the mesh (STL and 3MF), the "
            "parametric .scad source, the .kcad project, preview "
            "stills painted the way the 3D view shows the model "
            "(colours, materials, lighting, platform and shadow) "
            "from three-quarter angles — every corner, the product "
            "angles and the underside, the front-right isometric "
            "first, as the cover — description.txt "
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
            "exploded": {"type": "boolean",
                         "description": "Add exploded-view stills (every "
                                        "part pulled apart). Default: "
                                        "yes for an assembly of two or "
                                        "more parts."},
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

    # ── Checking ───────────────────────────────────────────────────
    {
        "name": "mass_properties",
        "description": (
            "Volume, surface area, centre of mass and bounding box of "
            "nodes (in the document's unit; volume_mm3 / area_mm2 are "
            "true mm), plus mass at true size for a material, and — "
            "for a mm, cm or inch document only — material cost and a "
            "print-time estimate (rough). Without node_ids: the whole "
            "scope. `approximate` flags a preview mesh with uncut "
            "booleans."
        ),
        "input_schema": _obj({
            "node_ids": _IDS,
            "material": {"type": "string",
                         "description": "PLA (default), PETG, ABS, ASA, "
                                        "TPU, Nylon, Resin, Aluminium, "
                                        "Steel, Brass, Titanium."},
            "price_per_kg": {"type": "number",
                             "description": "Default 20."},
        }),
    },
    {
        "name": "check_printability",
        "description": (
            "Blender's 3D-Print Toolbox in one call: watertight, "
            "overhangs beyond overhang_deg (needs supports), walls "
            "thinner than min_wall, and the footprint on the build "
            "plate — each pass / warn / fail with a plain-language "
            "message. Run it after building anything meant to be "
            "printed and fix what it names. The part is judged at 1:1 "
            "in the document's unit (a nanometre model is flagged)."
        ),
        "input_schema": _obj({
            "node_ids": _IDS,
            "overhang_deg": {"type": "number", "description": "Default 45."},
            "min_wall": {"type": "number",
                         "description": "Real printer mm, whatever the "
                                        "document unit; default 0.8."},
        }),
    },
    {
        "name": "check_interference",
        "description": (
            "Do parts overlap? Every pair of the given nodes (default: "
            "every visible top-level part in the assembly) is reported "
            "as intersect, contains / inside, or clear, with the "
            "overlap box and crossing points. Run it after placing or "
            "mating parts."
        ),
        "input_schema": _obj({"node_ids": _IDS}),
    },
    {
        "name": "build_city",
        "description": (
            "The City Builder: a village, town or city of OUTSIDE-ONLY "
            "buildings (nothing inside, so hundreds stay light) with "
            "detailed facades — framed windows with sills, doors, "
            "plinths, balconies, curtain walls — and detailed roofs "
            "(tiles or slate, ridge caps, fascia, gutters, chimneys, "
            "dormers; flat roofs with parapets and plant), roads with "
            "pavements, street lights and modelled trees. Walls are "
            "textured brick / concrete / render / stone in the 3D view. "
            "Either `layout` ('village' | 'town' | 'city', with `blocks` "
            "and `seed`) generates one, or give the pieces yourself; both "
            "combine. All mm, Z up. roads: [{points: [[x, y], ...], kind: "
            "avenue|street|lane|path, width, sidewalk}]. buildings: [{x, "
            "y (centre), w, d, rz, style: cottage|house|terrace|shop|"
            "block|tower|round tower|L-shape|church, floors, "
            "floor_height, wall: brick|concrete|render|stone, color, "
            "roof: gable|hip|flat|cone, roof_material: tiles|slate, "
            "roof_color, name}] — the front is -Y, rz turns it to its "
            "road. lights: [{x, y, rz}, ...] or {spacing}; trees: [{x, y, "
            "kind: oak|maple|lime|birch|cherry|apple|willow|poplar|pine|"
            "spruce|cypress|palm|shrub, height}]; "
            "street_trees: {spacing, kind}; ground: {margin, color} or "
            "null. props: [{part_id, x, y, rz, color, dims}] places any "
            "Part Library piece — a park_complete, park_football, "
            "signal_traffic, light_victorian, land_hills... (list_parts "
            "categories Park & sport, Lighting & signals, Landscape, "
            "Trees). Inserts the Objects City ground / City roads / City "
            "buildings / Street lights / City trees / City props, "
            "replacing the last "
            "build's, and stores the design (Library ▸ City ▸ City "
            "Builder edits it piece by piece; it is saved in the .kcad)."
        ),
        "input_schema": _obj({
            "layout": {"type": "string",
                       "enum": ["village", "town", "city"]},
            "blocks": {"type": "integer",
                       "description": "Grid size (town 3, city 5)."},
            "seed": {"type": "integer"},
            "roads": {"type": "array", "items": {"type": "object"}},
            "buildings": {"type": "array", "items": {"type": "object"}},
            "lights": {"description": "[{x, y, rz}, ...] or {spacing}."},
            "trees": {"type": "array", "items": {"type": "object"}},
            "props": {"type": "array", "items": {"type": "object"},
                      "description": "Library pieces: {part_id, x, y, rz, "
                                     "color, dims}."},
            "street_trees": {"type": "object"},
            "ground": {"description": "{margin, color}, or null."},
            "replace": {"type": "boolean"},
            "dry_run": {"type": "boolean",
                        "description": "Count only; build nothing."},
        }),
    },
]

#: Name -> definition, for the executor and the access-level checks.
BY_NAME = {t["name"]: t for t in TOOLS}
