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
    if args.get("regions") and cut_feature.ALL[kind][1] == "linear_extrude":
        return _regions(window, group, kind, args)
    part = _find(window, args["part_id"]) if "part_id" in args else None
    if part is None and kind not in cut_feature.BOSS:
        from . import face_sketch
        part = face_sketch.part_of(group)
        if part is None:
            return {"error": "a cut needs the part: give part_id"}
    made = None
    if kind in ("extruded_boss", "extruded_cut"):
        made = _with_model_edges(window, group, kind, args.get("region"))
    if made is None:
        made = cut_feature.apply(model, group, part, kind)
    if made is None:
        return {"error": "nothing made: the sketch holds no shape that "
                         "closes an area (or the part is not beside it)"}
    # the extrude made FROM the sketch (a cut's Difference holds the
    # part first — its own extrude must not be the one given the depth)
    ext = made if made.type == "linear_extrude" else next(
        (n for n in group.walk() if n.type == "linear_extrude"), None)
    _size(model, ext, args)
    return {"feature_id": made.id, "name": made.name, "kind": kind,
            "extrude_id": ext.id if ext is not None else None}


def _regions(window, group, kind, args) -> dict:
    """SolidWorks' Selected Contours (2026-11-14, Exercise 52): only the
    areas holding the `regions` points (sketch x, y) are extruded — the
    region pick's own `sketch_regions.extrude`, so a sketch a feature
    already used offers its areas again (one sketch, several features),
    and a cut is the Extrude window's Operation ▸ Cut."""
    from . import sketch_regions, extrude_panel
    model = window.model
    try:
        sketch_regions.tidy(window, group)
    except Exception:
        pass
    # an extruded sketch: its Regions (or plain extrude) holds the shapes
    source = None
    for n in group.walk():
        if n is not group and (n.type == "regions" and not
                               n.params.get("sketch_of")):
            source = sketch_regions._regions_of(n)
            if source is not None:
                break
    container = source or group
    shapes = sketch_regions.shapes_of(container)
    face_list = sketch_regions.faces(shapes) if shapes else []
    picked = []
    for p in args["regions"]:
        i = sketch_regions.face_at(face_list, (float(p[0]), float(p[1])))
        if i is None:
            return {"error": "regions: no area of the sketch holds %r "
                             "(sketch x, y)" % (list(p),)}
        picked.append(i)
    ext = sketch_regions.extrude(model, container, face_list, picked,
                                 hide=None if source else shapes)
    if ext is None:
        return {"error": "nothing made from those regions"}
    label = cut_feature.ALL[kind][0]
    ext.name = label
    if kind not in cut_feature.BOSS:
        if not extrude_panel.set_operation(model, ext, "cut"):
            return {"error": "no part before the sketch to cut"}
        if not args.get("through_all"):
            model.set_param(ext, "extent", "")
            model.set_param(ext, "reverse", True)
    _size(model, ext, args)
    top = ext
    while top.parent is not None and top.parent.type not in (
            "difference", "component", "root"):
        top = top.parent
    made = top.parent if top.parent is not None and \
        top.parent.type == "difference" else ext
    return {"feature_id": made.id, "name": made.name, "kind": kind,
            "extrude_id": ext.id, "regions": len(picked)}


def _size(model, ext, args):
    """Depth / Mid Plane / Through All / Reverse on the made extrude."""
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


def _with_model_edges(window, group, kind, region=None):
    """SolidWorks' "close the sketch with model edges" for MCP (Exercise
    51's Cut-Extrude2: ONE line across a face; the ribbon offers the
    areas it makes with the face's edges, MCP extruded the line as a
    0.2 mm strip). The area holding *region* (a sketch point), else —
    two areas, as the ribbon — the smaller one. None when the sketch
    closes its own area (or holds no thin line): the usual path."""
    from . import extrude_panel, sketch_regions, sketch_section, slot2d
    shapes = [s for s in cut_feature._shapes(group)
              if s.params.get("modifier") != "%"]

    def thin(s):
        try:
            return float(s.params.get("width", 0.2) or 0.2) \
                <= cut_feature.THIN_LINE
        except (TypeError, ValueError):
            return False
    if not any(s.type == "line" and not slot2d.is_slot(s) and thin(s)
               for s in shapes):
        return None
    try:
        if sketch_regions.solid_faces(shapes, sketch_regions.faces(shapes)):
            return None                  # they close an area themselves
    except Exception:
        pass
    model = window.model
    with_part, ghost = sketch_section.with_section(
        window, group, sketch_regions.shapes_of(group))
    if ghost is None:
        return None
    face_list = sketch_regions.faces(with_part)
    if not face_list:
        return None
    if region is not None:
        key = sketch_regions.face_at(face_list, tuple(region[:2]))
        if key is None:
            raise ValueError("region %r lies in none of the %d areas the "
                             "sketch closes with the part's edges"
                             % (list(region), len(face_list)))
    else:
        key = min(range(len(face_list)),
                  key=lambda i: face_list[i][0].area())
    real = sketch_section.keep(model, group, ghost)
    with_part = [real if s is ghost else s for s in with_part]
    ext = sketch_regions.extrude(model, group, face_list, {key},
                                 hide=with_part)
    if ext is None:
        return None
    if kind == "extruded_cut":
        if not extrude_panel.set_operation(model, ext, "cut"):
            return None
        model.set_param(ext, "extent", "")
        model.set_param(ext, "center", False)
        model.set_param(ext, "reverse", True)
        node = ext.parent
        while node is not None and not node.params.get(
                extrude_panel.CUT_KEY):
            node = node.parent
        return node or ext
    reg = next((n for n in ext.walk() if n.type == "regions"), None)
    if reg is not None:
        reg.params["fuse"] = True        # a boss joins the part it closes on
        model.node_changed.emit(reg)
    return ext


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


def _cut_tool(node):
    """A Cut-Extrude's Difference (what sketch_feature returns for a cut)
    stands for its CUT, as the History row does: patterning it must copy
    the hole, not the part with its hole (2026-11-14, the pattern
    exercise's Ø24 holes came out as three whole bodies)."""
    if node.type == "difference" and len(node.children) == 2:
        tool = node.children[1]
        if tool.name == "Cut sketch" or tool.name.endswith(
                "(to the part's frame)"):
            return tool
    return node


def pattern(window, args) -> dict:
    """MCP `pattern_feature`: SolidWorks' Circular / Linear Pattern —
    the same `pattern_feature.make` its window's OK runs."""
    from . import pattern_feature as pf
    nodes = [_cut_tool(n) for n in
             (_find(window, i) for i in args.get("node_ids", []))
             if n is not None]
    if not nodes:
        return {"error": "node_ids names no node"}
    kind = str(args.get("kind", pf.CIRCULAR))
    if kind not in (pf.CIRCULAR, pf.LINEAR):
        return {"error": "kind must be circular or linear"}
    st = pf._defaults(kind)
    count = int(args.get("count", 3 if kind == pf.CIRCULAR else 2))
    st.update(count=max(1, count), reverse=bool(args.get("reverse")))
    if kind == pf.CIRCULAR:
        st.update(axis=tuple(args.get("axis", (0, 0, 1))),
                  centre=tuple(args.get("centre", (0, 0, 0))),
                  angle=float(args.get("angle", 360.0)),
                  equal=bool(args.get("equal", True)))
    else:
        st.update(dir=tuple(args.get("direction", (1, 0, 0))),
                  spacing=float(args.get("spacing", 20.0)))
        if args.get("direction2") is not None:
            st.update(use2=True, dir2=tuple(args["direction2"]),
                      spacing2=float(args.get("spacing2", 20.0)),
                      count2=max(1, int(args.get("count2", 2))))
    made = pf.make(window, nodes, st)
    if not made:
        return {"error": "nothing patterned"}
    return {"pattern_ids": [m.id for m in made],
            "names": [m.name for m in made]}
