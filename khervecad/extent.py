"""Extrude extents (Qt-free), 2026-10-21 — SolidWorks' end conditions
Through All and Up To Surface, from the user's "do them all".

A `linear_extrude` may carry schema-only params:

- ``extent`` "" (blind: its own height, as before), "through_all" or
  "up_to";
- ``up_to``  the NAME of the node it extrudes up to, ``up_to_side``
  "far" / "near" (that node's far or near face along the extrude) and
  ``up_to_offset`` mm beyond it.

`refresh` (called from MainWindow._model_edited, like the sketch
constraints) works the height out from the geometry and WRITES it into
``height`` (and ``center``), so codegen and the preview are untouched
and the program stays plain OpenSCAD; editing the target moves the depth
with it. Through All cuts through the body it is subtracted from (the
first child of the nearest `difference` holding it), else through the
whole scope, centred so it reaches both ways.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

EXTENTS = ("", "through_all", "up_to", "up_to_face")
SIDES = ("far", "near")
MARGIN = 1.0

SCHEMA = [("extent", "End condition", "choice", EXTENTS, None),
          ("up_to", "Up to (object name)", "str", None, None),
          ("up_to_side", "Up to its", "choice", SIDES, None),
          ("up_to_offset", "Offset beyond (mm)", "float", -1e6, 1e6)]
TEXT = {"extent", "up_to", "up_to_side"}
# "up_to_face" (2026-10-27, SolidWorks' Up To Surface by a CLICK): the
# picked face as ``up_to_face`` [x, y, z, nx, ny, nz] in world
# coordinates; the depth is where the extrude's axis, through its
# sketch's centre, meets that face's plane (+ ``up_to_offset``).


def _np():
    import numpy as np
    return np


def _world_points(node, env):
    from . import mesh
    tris = mesh.tessellate(node, env)
    if not tris:
        return None
    np = _np()
    pts = np.array([p for t in tris for p in t], float)
    m = np.array(mesh.ancestor_matrix(node, env), float)
    return pts @ m[:3, :3].T + m[:3, 3]


def _local_z(extrude, pts, env):
    """z of world points in the extrude's own frame."""
    from . import mesh
    np = _np()
    m = np.array(mesh.ancestor_matrix(extrude, env), float)
    inv = np.linalg.inv(m)
    return pts @ inv[2, :3] + inv[2, 3]


def _body_for(extrude):
    """What Through All cuts: the first child of the nearest difference
    the extrude is a cutter of, else None (the whole scope)."""
    child, probe = extrude, extrude.parent
    while probe is not None:
        if probe.type == "difference" and probe.children and \
                probe.children[0] is not child:
            return probe.children[0]
        child, probe = probe, probe.parent
    return None


def _find(model, name, extrude):
    hits = [n for n in model.root.walk()
            if n.name == name and n is not extrude
            and not _is_inside(extrude, n)]
    return hits[0] if hits else None


def _is_inside(node, ancestor):
    p = node
    while p is not None:
        if p is ancestor:
            return True
        p = p.parent
    return False


def height_for(model, extrude, env=None):
    """(height, center) the extent asks for, or raise ValueError."""
    from .anchors import doc_env
    env = doc_env(model) if env is None else env
    kind = extrude.params.get("extent") or ""
    if kind == "through_all":
        body = _body_for(extrude)
        if body is None:
            pts = [_world_points(c, env) for c in model.root.children
                   if not _is_inside(extrude, c)]
            pts = [p for p in pts if p is not None]
            if not pts:
                raise ValueError("Through all: nothing to cut through.")
            pts = _np().concatenate(pts)
        else:
            pts = _world_points(body, env)
            if pts is None:
                raise ValueError("Through all: the body is empty.")
        z = _local_z(extrude, pts, env)
        reach = max(abs(float(z.min())), abs(float(z.max()))) + MARGIN
        return round(2 * reach, 4), True
    if kind == "up_to":
        name = str(extrude.params.get("up_to") or "").strip()
        target = _find(model, name, extrude) if name else None
        if target is None:
            raise ValueError("Up to: no object named %r." % name)
        pts = _world_points(target, env)
        if pts is None:
            raise ValueError("Up to: %r has no geometry." % name)
        z = _local_z(extrude, pts, env)
        side = extrude.params.get("up_to_side") or "far"
        h = float(z.max() if side == "far" else z.min())
        h += float(extrude.params.get("up_to_offset") or 0.0)
        if h <= 0.01:
            raise ValueError("Up to: %r's %s face is not above the "
                             "sketch." % (name, side))
        return round(h, 4), False
    if kind == "up_to_face":
        return _to_face(extrude, env)
    raise ValueError("Blind extrude: no extent to work out.")


def _sketch_centre(extrude, env):
    from . import mesh
    try:
        loops = [o for o in mesh.collect_outlines(extrude, env) if o]
    except Exception:
        loops = []
    pts = [p for o in loops for p in o]
    if not pts:
        return 0.0, 0.0
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def _to_face(extrude, env):
    """Depth from the sketch to the picked face's plane along +Z."""
    from . import mesh
    np = _np()
    row = extrude.params.get("up_to_face") or []
    if len(row) < 6:
        raise ValueError("Up to face: no face picked.")
    q, n = np.array(row[:3], float), np.array(row[3:6], float)
    m = np.array(mesh.ancestor_matrix(extrude, env), float)
    cx, cy = _sketch_centre(extrude, env)
    o = m[:3, :3] @ np.array([cx, cy, 0.0]) + m[:3, 3]
    a = m[:3, 2]                       # world step for one local z
    den = float(n @ a)
    if abs(den) < 1e-9:
        raise ValueError("Up to face: the face runs along the extrude, "
                         "it never meets it.")
    h = float(n @ (q - o)) / den
    h += float(extrude.params.get("up_to_offset") or 0.0)
    if h <= 0.01:
        raise ValueError("Up to face: the face is behind the sketch "
                         "(try Reverse direction).")
    return round(h, 4), False


_BUSY = False


def refresh(model):
    """Write the height of every extent-driven extrude. Returns
    {node id: error} for the ones that could not be worked out."""
    global _BUSY
    if _BUSY:
        return {}
    _BUSY = True
    errors = {}
    try:
        from .anchors import doc_env
        env = doc_env(model)
        for node in list(model.root.walk()):
            if node.type != "linear_extrude" or \
                    not node.params.get("extent"):
                continue
            try:
                h, centre = height_for(model, node, env)
            except (ValueError, ImportError) as exc:
                errors[node.id] = str(exc)
                continue
            p = node.params
            if p.get("height") != h or bool(p.get("center")) != centre:
                p["height"], p["center"] = h, centre
                model.node_changed.emit(node)
    finally:
        _BUSY = False
    return errors


def set_extent(model, extrude, kind, up_to="", side="far", offset=0.0,
               face=None):
    if kind not in EXTENTS:
        raise ValueError("extent is one of %s." % ", ".join(
            repr(k) for k in EXTENTS))
    p = extrude.params
    for k in ("extent", "up_to", "up_to_side", "up_to_offset",
              "up_to_face"):
        p.pop(k, None)
    if kind:
        p["extent"] = kind
    if kind == "up_to":
        p["up_to"], p["up_to_side"] = up_to, side
        if offset:
            p["up_to_offset"] = float(offset)
    if kind == "up_to_face":
        if face is None or len(face) < 6:
            raise ValueError("Up to face needs the face: [x, y, z, nx, "
                             "ny, nz].")
        p["up_to_face"] = [round(float(v), 6) for v in face[:6]]
        if offset:
            p["up_to_offset"] = float(offset)
    if kind:
        p["height"], p["center"] = height_for(model, extrude)
    model.node_changed.emit(extrude)
    return p["height"]
