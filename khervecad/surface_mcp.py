"""MCP `surface_edit` — Trim, Knit, Planar, Boundary, Thicken, Fillet and
Mirror of surface bodies (the body of the tool; surface_edit.py does the
work, surface_tool.py is the same thing by mouse).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from . import surface_edit, surface_tool

KEYS = ("mutual", "keep", "remove", "points", "fillets", "solid",
        "thickness", "radius", "plane", "offset")


def run(window, args, find) -> dict:
    """*find(id)* gives a node or None. `action` make (default) wraps
    node_ids in a surface_edit of `op`; pieces lists the numbered pieces
    a trim of node_ids would leave to choose from, each with a point ON
    it (the node's frame), so `remove` can be filled without guessing."""
    op = str(args.get("op", "trim"))
    if op not in surface_edit.OPS:
        return {"error": "op must be one of " + ", ".join(surface_edit.OPS)}
    nodes = [n for n in (find(i) for i in args.get("node_ids", []))
             if n is not None]
    nodes = [n for n in nodes if n.type in surface_tool.SURFACE_TYPES
             or n.type == "curve"]
    if not nodes:
        return {"error": "node_ids must name surfaces (curve_surface or "
                         "surface_edit nodes) or closed curves"}
    model = window.model
    parent = nodes[0].parent
    if any(n.parent is not parent for n in nodes):
        return {"error": "the surfaces must sit side by side in the tree"}
    node = model.wrap_nodes(nodes, "surface_edit")
    node.params.update(surface_edit._DEFAULTS, op=op)
    node.name = surface_tool._name(model, surface_tool.OPS.get(
        op, ("", "Surface-" + op))[1]) if op in surface_tool.OPS \
        else "Surface-" + op
    for k in KEYS:
        if k in args:
            node.params[k] = args[k]
    if str(args.get("action", "make")) == "pieces":
        from . import cadexchange
        shapes = surface_edit.child_shapes(node, {})
        pcs = surface_edit.pieces_of(shapes)
        rows = []
        for i, f in enumerate(pcs):
            rows.append({"piece": i,
                         "area": round(surface_edit.area_of(f), 2),
                         "point": [round(v, 3)
                                   for v in surface_edit.point_on(f)]})
        model.ungroup(node)
        return {"pieces": rows}
    model.node_changed.emit(node)
    from .model import validate
    out = {"created": node.id, "name": node.name, "op": op}
    problem = validate(model.root).get(node.id)
    if problem:
        out["problem"] = problem
    return out
