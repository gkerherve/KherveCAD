"""The MCP ``edit_mesh`` tool: Edit Mode for an assistant.

What a user does with the mouse in Edit Mode (meshedit_ui.py) an
assistant does by vertex index: open a part as an editable polyhedron
(converting it if needed) and read its vertices in WORLD millimetres,
then move / set / subdivide / extrude / merge / dissolve / smooth /
split an edge / poke a face. Every call is one edit of the node's
``points`` and ``faces`` — one undo step — and is refused, unchanged, if
it would leave the solid open.

Vertices are chosen by index (``vertices``), by a world box
(``within``), or ``all``. Moves are world vectors, mapped into the
node's own frame, so a polyhedron inside a rotated or scaled Object
moves the way the client means.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from . import meshedit

OPERATIONS = ("open", "move", "set", "subdivide", "extrude", "merge",
              "dissolve", "smooth", "split_edge", "poke", "inset",
              "loop_cut", "knife", "bridge", "spin")
#: past this many vertices `open` lists none unless asked
LIST_LIMIT = 3000


class EditError(Exception):
    """The call cannot be done; the message says what to change."""


def _vec(value, name):
    if value is None:
        return None
    try:
        out = [float(v) for v in value]
    except (TypeError, ValueError):
        raise EditError(f"'{name}' must be [x, y, z] numbers.")
    if len(out) != 3:
        raise EditError(f"'{name}' must be [x, y, z].")
    return out


def _state(node):
    pts = [[float(v) for v in (list(row) + [0.0, 0.0, 0.0])[:3]]
           for row in node.params.get("points") or []]
    faces = [[int(v) for v in f] for f in node.params.get("faces") or []]
    return pts, faces


def _selection(params, points, world):
    if params.get("all"):
        return list(range(len(points)))
    chosen = []
    if params.get("vertices") is not None:
        try:
            chosen = [int(v) for v in params["vertices"]]
        except (TypeError, ValueError):
            raise EditError("'vertices' is a list of vertex indices.")
        bad = [v for v in chosen if not 0 <= v < len(points)]
        if bad:
            raise EditError(f"vertex {bad[0]} does not exist (the mesh has "
                            f"{len(points)}: 0..{len(points) - 1}).")
    box = params.get("within")
    if box is not None:
        lo, hi = _vec(box.get("min"), "within.min"), \
            _vec(box.get("max"), "within.max")
        if lo is None or hi is None:
            raise EditError("'within' is {\"min\": [x, y, z], "
                            "\"max\": [x, y, z]} in world mm.")
        chosen += [i for i, w in enumerate(world)
                   if all(lo[k] <= w[k] <= hi[k] for k in range(3))]
    return sorted(set(chosen))


def _round(v):
    return [round(float(c), 4) for c in v]


def _more(op, params, points, faces, sel, matrix, inverse, to_local_point):
    """The box-modelling operations (meshedit_more.py)."""
    from . import meshedit_more as more
    try:
        if op == "inset":
            return more.inset(points, faces, sel,
                              float(params.get("thickness", 1.0)),
                              float(params.get("depth", 0.0)),
                              bool(params.get("individual", False)))
        if op == "loop_cut":
            edge = params.get("edge")
            try:
                a, b = (int(v) for v in edge)
            except (TypeError, ValueError):
                raise EditError("'loop_cut' needs 'edge' [a, b]: any edge "
                                "of the ring of quads to cut across.")
            return more.loop_cut(points, faces, a, b,
                                 float(params.get("t", 0.5)),
                                 int(params.get("cuts", 1)))
        if op == "knife":
            at = _vec(params.get("at"), "at")
            normal = _vec(params.get("normal"), "normal")
            if at is None or normal is None:
                raise EditError("'knife' needs 'at' (a point on the cut) "
                                "and 'normal' (the cutting plane's "
                                "normal), world mm.")
            # a plane's normal maps by the transpose of the linear part
            n_local = [sum(matrix[r][c] * normal[r] for r in range(3))
                       for c in range(3)]
            only = None
            if sel:
                only = meshedit.selected_faces(faces, sel) or None
            return more.knife(points, faces, to_local_point(at), n_local,
                              only)
        if op == "bridge":
            return more.bridge(points, faces, sel)
        if op == "spin":
            origin = _vec(params.get("origin"), "origin")
            axis = _vec(params.get("axis"), "axis")
            if origin is None or axis is None:
                raise EditError("'spin' needs 'origin' (a point on the "
                                "axis) and 'axis' (its direction), world "
                                "mm.")
            return more.spin(points, faces, sel, to_local_point(origin),
                             list(meshedit.local_delta(inverse, axis)),
                             float(params.get("angle", 90.0)),
                             int(params.get("steps", 8)),
                             float(params.get("taper", 1.0)))
    except more.EditFailed as exc:
        raise EditError(f"'{op}': {exc}")
    raise EditError(f"unknown operation {op!r}")       # pragma: no cover


def edit_mesh(window, node, params) -> dict:
    """Run one ``edit_mesh`` call on *node* (any part)."""
    model = window.model
    op = str(params.get("operation", "open"))
    if op not in OPERATIONS:
        raise EditError(f"Unknown operation {op!r}. Choose one of: "
                        + ", ".join(OPERATIONS) + ".")
    existing = meshedit.find_editable(node)
    poly, why = meshedit.convert(model, node, fn=model.effective_fn())
    if poly is None:
        raise EditError(f"{node.name} cannot be edited by vertex: {why}.")
    converted = existing is None
    matrix = meshedit.frame(poly)
    inverse = meshedit.linear_inverse(matrix)
    points, faces = _state(poly)
    world = [meshedit.apply(matrix, p) for p in points]

    def to_local_point(w):
        t = (matrix[0][3], matrix[1][3], matrix[2][3])
        return list(meshedit.local_delta(
            inverse, (w[0] - t[0], w[1] - t[1], w[2] - t[2])))

    sel = _selection(params, points, world)
    new_sel = sel
    note = ""
    if op == "open":
        pass
    elif op in ("move", "set", "smooth", "merge", "dissolve", "subdivide",
                "extrude", "inset", "bridge", "spin") and not sel:
        raise EditError(f"'{op}' needs vertices: give 'vertices' "
                        "(indices from operation open), 'within' (a world "
                        "box) or 'all': true.")
    if op == "move":
        delta = _vec(params.get("delta"), "delta")
        if delta is None:
            raise EditError("'move' needs 'delta' [dx, dy, dz] in world mm.")
        local = meshedit.local_delta(inverse, delta)
        points = meshedit.move(points, sel, local,
                               float(params.get("proportional") or 0.0),
                               str(params.get("mirror", "none")),
                               str(params.get("falloff", "smooth")))
    elif op == "set":
        to = _vec(params.get("to"), "to")
        if to is None or len(sel) != 1:
            raise EditError("'set' puts ONE vertex at 'to' [x, y, z] "
                            "(world mm).")
        old = world[sel[0]]
        delta = [to[k] - old[k] for k in range(3)]
        points = meshedit.move(points, sel,
                               meshedit.local_delta(inverse, delta),
                               float(params.get("proportional") or 0.0),
                               str(params.get("mirror", "none")),
                               str(params.get("falloff", "smooth")))
    elif op == "smooth":
        points = meshedit.smooth(points, faces, sel,
                                 float(params.get("factor", 0.5)),
                                 int(params.get("passes", 1)))
    elif op == "subdivide":
        if not meshedit.selected_faces(faces, sel):
            raise EditError("'subdivide' cuts the faces whose EVERY corner "
                            "is selected — none are.")
        points, faces, new_sel = meshedit.subdivide(
            points, faces, sel, int(params.get("cuts", 1)))
    elif op == "extrude":
        result = meshedit.extrude(points, faces, sel)
        if result is None:
            raise EditError("'extrude' needs some faces selected (every "
                            "corner of each), and not every face.")
        points, faces, new_sel, normal = result
        distance = float(params.get("distance", 0.0))
        if distance:
            wn = [sum(matrix[r][c] * normal[c] for c in range(3))
                  for r in range(3)]
            length = math.sqrt(sum(v * v for v in wn)) or 1.0
            step = [v / length * distance for v in wn]
            points = meshedit.move(points, new_sel,
                                   meshedit.local_delta(inverse, step))
        note = "extruded along the faces' mean normal"
    elif op == "merge":
        if len(sel) < 2:
            raise EditError("'merge' needs two or more vertices.")
        at = _vec(params.get("to"), "to")
        points, faces, new_sel = meshedit.merge(
            points, faces, sel, to_local_point(at) if at else None)
    elif op == "dissolve":
        points, faces, new_sel = meshedit.dissolve(points, faces, sel)
    elif op == "split_edge":
        edge = params.get("edge")
        try:
            a, b = (int(v) for v in edge)
        except (TypeError, ValueError):
            raise EditError("'split_edge' needs 'edge' [a, b] (two vertex "
                            "indices joined by an edge).")
        points, faces, new = meshedit.split_edge(
            points, faces, a, b, float(params.get("t", 0.5)))
        if new is None:
            raise EditError(f"vertices {a} and {b} are not joined by an "
                            "edge.")
        new_sel = [new]
    elif op == "poke":
        try:
            face = int(params.get("face"))
        except (TypeError, ValueError):
            raise EditError("'poke' needs 'face' (a face index from "
                            "operation open with include_faces).")
        if not 0 <= face < len(faces):
            raise EditError(f"face {face} does not exist ({len(faces)} "
                            "faces).")
        at = _vec(params.get("at"), "at")
        points, faces, new = meshedit.poke(
            points, faces, face, to_local_point(at) if at else None)
        new_sel = [new]
    if op in ("inset", "loop_cut", "knife", "bridge", "spin"):
        points, faces, new_sel = _more(op, params, points, faces, sel,
                                       matrix, inverse, to_local_point)
    if op != "open":
        why = meshedit.check(points, faces)
        if why:
            raise EditError(f"'{op}' refused — it would leave the solid "
                            f"broken: {why}. Nothing was changed.")
        poly.params["points"] = [list(p) for p in points]
        model.set_param(poly, "faces", [list(f) for f in faces])
    world = [meshedit.apply(matrix, p) for p in points]
    out = {"node_id": poly.id, "name": poly.name, "operation": op,
           "converted": converted, "vertex_count": len(points),
           "face_count": len(faces), "selection": list(new_sel)}
    if note:
        out["note"] = note
    if converted:
        out["converted_note"] = (
            f"{node.name} was converted into an editable polyhedron; "
            "Ctrl+Z restores the original.")
    listing = params.get("include_points")
    if listing or (listing is None and op == "open"
                   and len(points) <= LIST_LIMIT):
        out["points"] = [_round(w) for w in world]
    elif op == "open":
        out["points_note"] = (f"{len(points)} vertices — pass "
                              "include_points: true to list them, or "
                              "pick by 'within'.")
    if params.get("include_faces") or (op == "open"
                                       and len(faces) <= LIST_LIMIT):
        out["faces"] = faces
    if new_sel and op != "open":
        out["selected_points"] = [_round(world[i]) for i in new_sel
                                  if i < len(world)][:200]
    return out
