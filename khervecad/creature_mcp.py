"""The MCP bodies of the creature tools (mcp_tools.py is past its size):
scatter_on_surface and the tools the other creature nodes add.

Each function takes the live window and the call's params and returns
the result dict, raising CreatureError with a message that says what to
change. Points an assistant gives are WORLD millimetres (what
probe_surface and sample_surface return); they are mapped into the
node's own frame here, so a part inside a moved Object works the way
the client means.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations


class CreatureError(Exception):
    """The call cannot be done; the message says what to change."""


def _vec(value, name):
    try:
        out = [float(v) for v in value]
    except (TypeError, ValueError):
        raise CreatureError(f"'{name}' must be [x, y, z] numbers.")
    if len(out) != 3:
        raise CreatureError(f"'{name}' must be [x, y, z].")
    return out


def _find(model, node_id):
    for n in model.root.walk():
        if n.id == node_id:
            return n
    raise CreatureError(f"No node with id {node_id}.")


def to_local(node, points, stop=None):
    """World points into the frame *node*'s CHILDREN are drawn in (the
    node's own placement included when it has one)."""
    from . import mesh
    m = mesh.mat_mul(mesh.ancestor_matrix(node, stop=stop),
                     mesh.node_matrix(node))
    inv = _inverse(m)
    out = []
    for p in points:
        out.append([round(sum(inv[r][k] * p[k] for k in range(3))
                          + inv[r][3], 4) for r in range(3)])
    return out


def _inverse(m):
    import numpy as np
    return np.linalg.inv(np.asarray(m, dtype=float)).tolist()


def _scope(window):
    root = window._render_scope()[0]
    return root if root is not window.model.root else None


# ----------------------------------------------------------- scatter

def scatter_on_surface(window, params) -> dict:
    """Wrap a piece and a surface in a scatter node (or update one)."""
    from . import scatter
    from .model import validate
    model = window.model
    d = scatter.NODE_TYPES["scatter"]["params"]
    node = None
    if params.get("scatter_id") is not None:
        node = _find(model, int(params["scatter_id"]))
        if node.type != "scatter":
            raise CreatureError(f"'{node.name}' is a {node.type}, not a "
                                "scatter.")
    else:
        if params.get("piece_id") is None or \
                params.get("surface_id") is None:
            raise CreatureError(
                "Give 'piece_id' (the spike, wart, scale or tooth, "
                "modelled at the origin pointing up +Z) and 'surface_id' "
                "(the body), or 'scatter_id' to change one.")
        piece = _find(model, int(params["piece_id"]))
        surface = _find(model, int(params["surface_id"]))
        if piece is surface or surface.parent is None or \
                piece.parent is None:
            raise CreatureError("The piece and the surface must be two "
                                "different nodes below the document.")
        if any(a is piece for a in model._ancestors(surface)) or \
                any(a is surface for a in model._ancestors(piece)):
            raise CreatureError("One of them holds the other — pick two "
                                "separate nodes.")
        if piece.parent is not surface.parent:
            model.move_node(piece, surface.parent, surface.index())
        node = model.wrap_nodes([piece, surface], "scatter")
        node.name = str(params.get("name") or "Scatter")
    for key in d:
        if key in ("within", "path") or params.get(key) is None:
            continue
        value = params[key]
        if key in scatter._CHOICE and value not in scatter._CHOICE[key]:
            raise CreatureError(f"'{key}' is one of "
                                f"{', '.join(scatter._CHOICE[key])}.")
        node.params[key] = value
    stop = _scope(window)
    if params.get("path") is not None:
        pts = [_vec(p, "path") for p in params["path"]]
        if len(pts) < 2:
            raise CreatureError("'path' needs at least two points.")
        node.params["path"] = to_local(node, pts, stop)
        node.params["mode"] = params.get("mode") or "path"
    if params.get("within") is not None:
        box = params["within"]
        lo, hi = _vec(box.get("min"), "within.min"), \
            _vec(box.get("max"), "within.max")
        a, b = to_local(node, [lo, hi], stop)
        node.params["within"] = [[min(a[k], b[k]) for k in range(3)],
                                 [max(a[k], b[k]) for k in range(3)]]
    model.node_changed.emit(node)
    errors = validate(model.root)
    if node.id in errors:
        raise CreatureError(errors[node.id])
    from . import bake
    _ops, mats = scatter.compute(node, bake._codegen_env(node))
    return {"scatter": node.id, "name": node.name, "placed": len(mats),
            "mode": node.params["mode"],
            "note": ("The first child is the piece, the rest the surface. "
                     "Fewer were placed than asked when the surface is "
                     "full at that spacing.")
            if len(mats) < int(node.params.get("count", 0)) else ""}


# ----------------------------------------------------------- armature

def _armature_of(model, node):
    if node.type == "armature":
        return node
    return next((n for n in node.walk() if n.type == "armature"), None)


def rig_armature(window, params) -> dict:
    """Give a part an armature (or change one): bones in WORLD mm,
    automatic weights, an optional pose."""
    from . import armature
    from .model import validate
    model = window.model
    if params.get("node_id") is None:
        raise CreatureError("Give 'node_id': the body to rig (a sculpt, "
                            "blend, mesh — or an armature to change).")
    target = _find(model, int(params["node_id"]))
    node = _armature_of(model, target)
    if node is None:
        if target.parent is None:
            raise CreatureError("The document root cannot be rigged.")
        node = model.wrap_nodes([target], "armature")
        node.name = str(params.get("name") or "Armature")
    stop = _scope(window)
    if params.get("from_skin") is not None:
        skin_node = _find(model, int(params["from_skin"]))
        if skin_node.type != "skin":
            raise CreatureError(f"'{skin_node.name}' is not a skin node.")
        node.params["bones"] = armature.bones_from_skin(
            skin_node.params.get("nodes") or [])
    if params.get("bones") is not None:
        rows = []
        for b in params["bones"]:
            if not isinstance(b, dict) or not b.get("name"):
                raise CreatureError("Each bone is {name, parent, head: "
                                    "[x, y, z], tail: [x, y, z]} in world "
                                    "mm.")
            head, tail = to_local(node, [_vec(b.get("head"), "head"),
                                         _vec(b.get("tail"), "tail")], stop)
            rows.append([str(b["name"]), str(b.get("parent") or "")]
                        + head + tail)
        node.params["bones"] = rows
    for key in ("falloff", "smooth", "detail"):
        if params.get(key) is not None:
            node.params[key] = params[key]
    if params.get("pose") is not None:
        set_armature_pose(node, params["pose"])
    model.node_changed.emit(node)
    errors = validate(model.root)
    if node.id in errors:
        raise CreatureError(errors[node.id])
    return armature_report(node)


def set_armature_pose(node, wanted):
    """Merge {bone: {rx, ry, rz}} into the armature's pose rows."""
    from . import armature
    if not isinstance(wanted, dict):
        raise CreatureError("'pose' is {\"<bone>\": {\"rx\": deg, \"ry\": "
                            "deg, \"rz\": deg}}.")
    names = [str(r[0]) for r in node.params.get("bones") or []
             if isinstance(r, list) and r]
    rows = armature.parse_pose(node.params.get("pose"))
    for name, angles in wanted.items():
        if name not in names:
            raise CreatureError(f"No bone named {name!r}. Bones: "
                                f"{', '.join(names) or 'none'}.")
        if not isinstance(angles, dict) or set(angles) - {"rx", "ry", "rz"}:
            raise CreatureError(f"The pose for {name} is an object of rx / "
                                "ry / rz degrees.")
        current = rows.get(name, [0.0, 0.0, 0.0])
        for axis, value in angles.items():
            try:
                current["rx ry rz".split().index(axis)] = float(value)
            except (TypeError, ValueError):
                raise CreatureError(f"{name}.{axis} must be a number.")
        rows[name] = current
    node.params["pose"] = [[n] + a for n, a in rows.items() if any(a)]


def armature_report(node) -> dict:
    return {"armature": node.id, "name": node.name,
            "bones": [{"name": r[0], "parent": r[1], "head": r[2:5],
                       "tail": r[5:8]}
                      for r in node.params.get("bones") or []
                      if isinstance(r, list) and len(r) == 8],
            "pose": node.params.get("pose") or [],
            "note": ("Bones are in the part's own frame. A pose turns a "
                     "bone about its head in the part's axes (rx, ry, rz "
                     "like rotate([x, y, z])) and carries every bone below "
                     "it; the skin follows by automatic weights. Name bones "
                     "Head, Tail, Left wing, Front left leg … and "
                     "send_to_planetcraft walks it. reach (IK) takes a bone "
                     "name as its effector.")}
