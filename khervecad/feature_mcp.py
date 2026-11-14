# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""MCP `sketch_feature` (2026-11-14, Exercise 6's problem 3: an
assistant had no way to make the ribbon's Extruded Boss / Cut from a
sketch — it wrote the extrude by hand round each shape, so a U of lines
round a circle came out as thin walls). The same `cut_feature.apply`
the ribbon runs on leaving a Boss / Cut sketch: the AREA the sketch's
lines and shapes close (holes left out) becomes the profile, kept as a
Regions with the sketch's dimensions.
"""

from . import cut_feature


def _find(window, nid):
    for n in window.model.root.walk():
        if n.id == nid:
            return n
    return None


def run(window, args) -> dict:
    model = window.model
    group = _find(window, args.get("node_id"))
    if group is None:
        return {"error": "no node with id %r" % args.get("node_id")}
    kind = str(args.get("kind", "extruded_boss"))
    if kind not in cut_feature.ALL or kind == "rib":
        return {"error": "kind must be one of %s (rib: use the rib tool)"
                % ", ".join(k for k in cut_feature.ALL if k != "rib")}
    part = _find(window, args["part_id"]) if "part_id" in args else None
    if part is None and kind not in cut_feature.BOSS:
        from . import face_sketch
        part = face_sketch.part_of(group)
        if part is None:
            return {"error": "a cut needs the part: give part_id"}
    made = cut_feature.apply(model, group, part, kind)
    if made is None:
        return {"error": "nothing made: the sketch holds no shape that "
                         "closes an area (or the part is not beside it)"}
    ext = made if made.type == "linear_extrude" else next(
        (n for n in made.walk() if n.type == "linear_extrude"), None)
    if ext is not None:
        if "depth" in args:
            model.set_param(ext, "height", float(args["depth"]))
        if args.get("mid_plane"):
            model.set_param(ext, "center", True)
        if args.get("through_all"):
            model.set_param(ext, "extent", "through_all")
        if "reverse" in args:
            model.set_param(ext, "reverse", bool(args["reverse"]))
        from . import extent
        extent.refresh(model)
    return {"feature_id": made.id, "name": made.name, "kind": kind,
            "extrude_id": ext.id if ext is not None else None}


PLANES = {"front": "Front (XZ)", "top": "Top (XY)", "right": "Side (YZ)"}


def mirror(window, args) -> dict:
    """MCP `mirror_feature`: SolidWorks' Mirror — node_ids about a main
    plane (Front / Top / Right) or a plane given by point + normal (the
    scope's frame), carried into each node's own frame."""
    from . import mirror_feature
    nodes = [n for n in (_find(window, i) for i in args.get("node_ids", []))
             if n is not None]
    if not nodes:
        return {"error": "node_ids names no node"}
    if "normal" in args:
        spec = ("face", tuple(args.get("point", (0, 0, 0))),
                tuple(args["normal"]))
    else:
        key = str(args.get("plane", "Right")).split()[0].lower()
        if key not in PLANES:
            return {"error": "plane must be Front, Top or Right "
                             "(or give point + normal)"}
        spec = ("main", PLANES[key])
    made = mirror_feature.mirror(window, nodes, spec)
    if not made:
        return {"error": "nothing mirrored"}
    return {"mirror_ids": [m.id for m in made],
            "names": [m.name for m in made]}
