"""MCP `reference_geometry` (2026-10-27): the body, kept out of
mcp_tools.py (past its size). See refgeom / refgeom_ui.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from . import refgeom, refgeom_ui


def _vec(params, key, n=3):
    v = params.get(key)
    if not isinstance(v, (list, tuple)) or len(v) < n:
        raise ValueError(f"{key}: give {n} numbers.")
    return [float(c) for c in v[:n]]


def _row(window, node):
    kind, o, d = refgeom_ui.world(node, window)
    return dict(id=node.id, name=node.name, kind=kind,
                origin=[round(c, 4) for c in o],
                direction=[round(c, 6) for c in d])


def run(ex, params):
    win = ex._w
    action = params.get("action", "list")
    size = params.get("size")
    if action == "list":
        return dict(reference=[_row(win, n)
                               for n in refgeom_ui.ref_nodes(win)],
                    main_planes=[dict(name=n, origin=list(o), normal=list(d))
                                 for n, _p, o, d in refgeom.MAIN_PLANES])
    if action == "plane":
        if params.get("offset_from"):
            names = [n for n, *_r in refgeom.MAIN_PLANES]
            _n, _p, o, d = refgeom.MAIN_PLANES[
                names.index(params["offset_from"])]
            o, d = refgeom.offset_plane(o, d, float(
                params.get("distance") or 0.0))
        elif params.get("points"):
            pts = params["points"]
            if len(pts) != 3:
                raise ValueError("points: three [x, y, z].")
            o, d = refgeom.plane_three_points(*pts)
        else:
            o, d = refgeom.offset_plane(
                _vec(params, "origin"), _vec(params, "normal"),
                float(params.get("distance") or 0.0))
        return _row(win, refgeom_ui.add_plane(win, o, d, size))
    if action == "axis":
        if params.get("planes"):
            ids = params["planes"]
            if len(ids) != 2:
                raise ValueError("planes: two ref_plane ids.")
            a, b = (ex._node(i) for i in ids)
            _k, o1, n1 = refgeom_ui.world(a, win)
            _k, o2, n2 = refgeom_ui.world(b, win)
            p, d = refgeom.axis_of_planes(o1, n1, o2, n2)
        elif params.get("points"):
            p, d = refgeom.axis_two_points(*params["points"][:2])
        else:
            p, d = _vec(params, "point"), refgeom.unit(
                _vec(params, "direction"))
        return _row(win, refgeom_ui.add_axis(win, p, d, size))
    if action == "point":
        return _row(win, refgeom_ui.add_point(win, _vec(params, "at")))
    if action == "sketch":
        if params.get("node_id") is not None:
            node = ex._node(params["node_id"])
            if node.type != "ref_plane":
                raise ValueError("node_id: a Plane (ref_plane).")
            g = refgeom_ui.sketch_on(win, node, open_2d=False)
        else:
            g = refgeom_ui.sketch_on(win, origin=_vec(params, "origin"),
                                     normal=_vec(params, "normal"),
                                     open_2d=False)
        return dict(sketch_id=g.id, name=g.name, note=(
            "Add rect / circle / line / polygon nodes inside it (parent = "
            "sketch_id), in its own x, y; then wrap it in a "
            "linear_extrude."))
    from . import extent
    node = ex._node(params.get("node_id"))
    if node.type != "linear_extrude":
        raise ValueError("node_id: a Linear extrude.")
    if action == "up_to_face":
        h = extent.set_extent(win.model, node, "up_to_face",
                              face=_vec(params, "face", 6))
        return dict(id=node.id, height=h)
    if action == "two_way":
        node.params["height2"] = float(params.get("depth") or 0.0)
        win.model.node_changed.emit(node)
        return dict(id=node.id, height=node.params["height"],
                    height2=node.params["height2"])
    raise ValueError(f"Unknown action {action!r}.")
