# KherveCAD — Copyright (C) 2026 Gwilherm Kerherve
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License v3 or later.
"""Relations a new sketch shape gets by where it was drawn (2026-10-31,
the user: a slot's end drawn on a rectangle's side came off it at the
first Smart Dimension). As SolidWorks does: a point drawn ON another
shape's point becomes Coincident, a point drawn on its side, line or
circle becomes Point on curve ("On Edge")."""
import math

from . import sketch_constraints as sc

TOL = 1e-4                              # mm: snapped points are exact


def _points(node):
    t = node.type
    if t == "line":
        return ["p1", "p2"]
    if t == "circle":
        return ["c"]
    if t == "rect":
        return ["v0", "v1", "v2", "v3"]
    if t == "polygon":
        return ["v%d" % i for i in range(len(node.params.get("points")
                                              or []))]
    return []


def _curves(node):
    t = node.type
    if t == "line":
        if node.params.get("bulge"):    # an arc: not a straight line
            return []
        return ["l"]
    if t == "circle":
        return [] if node.params.get("angle", 360) not in (360, 360.0) \
            else ["o"]
    if t == "rect":
        return ["e0", "e1", "e2", "e3"]
    if t == "polygon":
        return ["e%d" % i for i in range(len(node.params.get("points")
                                              or []))]
    return []


def _on_segment(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    n2 = dx * dx + dy * dy
    if n2 < 1e-12:
        return False
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / n2
    if t < -1e-6 or t > 1 + 1e-6:
        return False
    return abs(dx * (p[1] - a[1]) - dy * (p[0] - a[0])) / math.sqrt(n2) \
        < TOL


def found(container, node):
    """[(kind, refs)] the drawing shows for ``node``'s points."""
    if node.type not in sc.SHAPES or node.parent is not container:
        return []
    have = set()
    for r in sc.rows(container):
        have.add((r["kind"], tuple(sorted(r["refs"]))))
    out = []
    for name in _points(node):
        me = sc.ref_of(container, node, name)
        p = sc._point(node, name, {})
        for other in container.children:
            if other is node or other.type not in sc.SHAPES or \
                    other.params.get("modifier") == "*":
                continue
            hit = None
            for on in _points(other):
                try:
                    q = sc._point(other, on, {})
                except (KeyError, ValueError, IndexError):
                    continue
                if math.hypot(p[0] - q[0], p[1] - q[1]) < TOL:
                    hit = ("coincident", [me, sc.ref_of(container,
                                                        other, on)])
                    break
            if hit is None:
                for cn in _curves(other):
                    try:
                        if cn == "o":
                            c, r = sc._circle(other, cn, {})
                            ok = abs(math.hypot(p[0] - c[0], p[1] - c[1])
                                     - r) < TOL
                        else:
                            ok = _on_segment(p, *sc._line(other, cn, {}))
                    except (KeyError, ValueError, IndexError):
                        continue
                    if ok:
                        hit = ("point_on", [me, sc.ref_of(container,
                                                          other, cn)])
                        break
            if hit and (hit[0], tuple(sorted(hit[1]))) not in have:
                have.add((hit[0], tuple(sorted(hit[1]))))
                out.append(hit)
    return out


def relate(model, node):
    """Add what ``found`` sees for a new shape (or the shapes of a new
    group, e.g. a Polyline). Returns how many relations were added."""
    shapes = [node] if node.type in sc.SHAPES else \
        [c for c in node.children if c.type in sc.SHAPES]
    added = 0
    for shape in shapes:
        container = shape.parent
        if container is None:
            continue
        for kind, refs in found(container, shape):
            try:
                sc.add(model, container, kind, refs)
                added += 1
            except (ValueError, KeyError):   # a conflict: leave it
                pass
    return added
