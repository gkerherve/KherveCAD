"""Sketches that follow the MODEL (2026-11-01, the user: a rib drawn
from the block's corner to the plate's, closed with the model's edges,
must move when a Smart Dimension changes the block — "they all move
together", as in SolidWorks).

A sketch drawn on a part keeps three kinds of reference to it:

- a point snapped onto a model CORNER: a ``fix`` row marked ``model``
  (face_outline.pin), at the corner's place;
- a point snapped onto a model EDGE: an ``on_edge`` row holding the edge;
- the part's outline the sketch's lines closed areas with: the "Part
  section" polygon sketch_section.keep stored (its ``section_grow``).

`refresh` runs on every model edit (MainWindow._model_edited, before the
sketch constraints solve). For each sketch holding any of them it takes
the part's outline at the sketch's plane NOW — the whole face for a face
sketch, else the section — and moves each reference to its counterpart:
a corner to the outline corner with the same edge directions nearest
where it was, an edge to the parallel outline edge nearest it, the
section polygon to the new section. The constraints then solve the
sketch onto them and the Regions re-track, so the feature follows.

Matching is by geometry, like the fillet's edges: a change that turns a
corner into something else entirely leaves that reference where it was.
Only sketches that BUILD something (a boss, a rib) follow so far: a
cut's sketch sits inside the body it cuts (`_in_cut`).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

#: two edge directions agree within this (radians)
ANGLE_TOL = math.radians(1.0)
#: a reference closer than this to its counterpart has not moved (mm)
SAME = 1e-6

_BUSY = False


def _in_cut(container):
    """A cut's sketch lives inside the body it cuts: its part cannot be
    left out of the outline without losing the body (the clevis's
    pockets went wrong), so cuts keep their references as drawn."""
    node = container
    while node is not None:
        if node.type == "difference":
            return True
        node = node.parent
    return False


def _has_refs(container):
    from . import sketch_constraints as sc, sketch_section
    if _in_cut(container):
        return False
    rows = sc.rows(container)
    if any(r.get("kind") == "on_edge" or
           (r.get("kind") == "fix" and r.get("model")) for r in rows):
        return True
    return any(sketch_section.is_section(n) for n in container.children)


def _own_part(container, root):
    """The scope child the sketch itself builds (left out of the
    outline: the rib must not close with its own faces)."""
    node = container
    while node is not None and node.parent is not root:
        node = node.parent
    return node


def outline(window, container):
    """[((x, y), (x, y))] the model's outline at *container*'s plane in
    its frame, the container's own feature left out; None when unknown."""
    from . import face_outline, face_sketch, meshedit_ui
    root = window._render_scope()[0]
    own = _own_part(container, root)
    parts = [(n, t) for n, t in meshedit_ui._parts(window) if n is not own]
    if not parts:
        return None
    if container.params.get(face_sketch.KEY):
        tris = [t for _n, ts in parts for t in ts]
        segs = face_outline.whole_face(container, tris, [])
        if segs:
            return segs
    from . import sketch_section
    shape = sketch_section.section_shape(window, container, 0.0)
    if not shape:
        return None
    pts = shape["points"]
    segs = []
    for path in shape["paths"]:
        for i, a in enumerate(path):
            b = path[(i + 1) % len(path)]
            segs.append((tuple(pts[a]), tuple(pts[b])))
    return segs


def _angle(a, b):
    return math.atan2(b[1] - a[1], b[0] - a[0])


def _corners(segs):
    """{(x, y): [edge directions out of it]}"""
    out = {}
    for a, b in segs:
        a, b = tuple(a), tuple(b)
        out.setdefault(a, []).append(_angle(a, b))
        out.setdefault(b, []).append(_angle(b, a))
    return out


def _dirs_match(d1, d2):
    if len(d1) != len(d2):
        return False
    used = set()
    for x in d1:
        hit = None
        for j, y in enumerate(d2):
            if j in used:
                continue
            diff = abs((x - y + math.pi) % (2 * math.pi) - math.pi)
            if diff < ANGLE_TOL:
                hit = j
                break
        if hit is None:
            return False
        used.add(hit)
    return True


def _corner_dirs(segs, p, tol=1e-4):
    return [d for q, ds in _corners(segs).items()
            if math.hypot(q[0] - p[0], q[1] - p[1]) < tol for d in ds]


def match_corner(new_segs, p, want=None):
    """Where the corner at *p*, whose edges leave it in the directions
    *want*, is in *new_segs*: the nearest corner with the same edge
    directions, else the nearest."""
    corners = _corners(new_segs)
    if not corners:
        return None
    best = None
    for q, ds in corners.items():
        d = math.hypot(q[0] - p[0], q[1] - p[1])
        ok = not want or _dirs_match(want, ds)
        key = (0 if ok else 1, d)
        if best is None or key < best[0]:
            best = (key, q)
    return best[1]


def match_edge(new_segs, edge):
    """The outline edge that *edge* (ax, ay, bx, by) became: parallel,
    the nearest to its middle."""
    a, b = (edge[0], edge[1]), (edge[2], edge[3])
    ang = _angle(a, b)
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    best = None
    for p, q in new_segs:
        diff = abs((_angle(p, q) - ang + math.pi / 2) % math.pi
                   - math.pi / 2)
        if diff > ANGLE_TOL:
            continue
        L = math.hypot(q[0] - p[0], q[1] - p[1]) or 1e-12
        off = abs((q[0] - p[0]) * (mid[1] - p[1]) -
                  (q[1] - p[1]) * (mid[0] - p[0])) / L
        if best is None or off < best[0]:
            best = (off, (p, q))
    return best[1] if best else None


def _update_section(window, container):
    """The kept "Part section" polygons redrawn from the part now."""
    from . import sketch_section
    model = window.model
    changed = False
    for node in list(container.children):
        if not sketch_section.is_section(node):
            continue
        grow = node.params.get("section_grow", sketch_section.GROW)
        shape = sketch_section.section_shape(window, container, grow)
        if not shape:
            continue
        if shape["points"] != node.params.get("points") or \
                shape["paths"] != node.params.get("paths"):
            node.params["points"] = shape["points"]
            node.params["paths"] = shape["paths"]
            model.node_changed.emit(node)
            changed = True
    return changed


def refresh_container(window, container):
    """Move *container*'s model references onto the model as it is.
    True when anything moved."""
    from . import sketch_constraints as sc
    rows = sc.rows(container)
    refs = [r for r in rows if r.get("kind") == "on_edge" or
            (r.get("kind") == "fix" and r.get("model"))]
    moved = False
    if refs:
        segs = outline(window, container)
        if segs:
            for r in refs:
                if r["kind"] == "fix":
                    p = tuple(r["at"])
                    q = match_corner(segs, p, r.get("dirs"))
                    if q is not None and math.hypot(
                            q[0] - p[0], q[1] - p[1]) > SAME:
                        r["at"] = [round(q[0], 6), round(q[1], 6)]
                        moved = True
                else:
                    e = match_edge(segs, r["edge"])
                    if e is not None:
                        new = [round(v, 6) for v in (*e[0], *e[1])]
                        if any(abs(x - y) > SAME
                               for x, y in zip(new, r["edge"])):
                            r["edge"] = new
                            moved = True
    if _update_section(window, container):
        moved = True
    if moved:
        try:
            sc.solve(container, rows, env=sc._env(window.model))
        except Exception:
            pass
        window.model.node_changed.emit(container)
    return moved


def refresh(window):
    """Every sketch's model references, after a model edit."""
    global _BUSY
    if _BUSY:
        return
    _BUSY = True
    try:
        root = window._render_scope()[0]
        for node in list(root.walk()):
            if node.children and _has_refs(node):
                try:
                    refresh_container(window, node)
                except Exception:          # never break an edit
                    import traceback
                    traceback.print_exc()
    finally:
        _BUSY = False
