"""Split a part to fit the print bed (BOSL2's partitions): cut an Object
with a plane into two Objects, each the part intersected with its side
of the plane, joined back by dowels.

The halves are ordinary nodes — ``difference() { intersection() {
<the part's contents>; <a box on one side> } <dowel holes> }`` — so the
cut stays editable (move the plane, resize the dowels) and renders
exactly in OpenSCAD. Dowel holes are placed where the section is solid
and farthest from its edges (`dowel_points`, from `section.cut`), the
same holes in both halves, ``dowel_depth`` deep in total, widened by
``clearance``; a matching pin Object is added so the pins print too.
The original is hidden, never deleted, and the second half is moved
``gap`` along the axis so both can be seen.

Qt-free.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from .model import CadNode

AXES = ("x", "y", "z")


def _inside(point, loops):
    """Even-odd inside test over every outline (holes count)."""
    x, y = point
    inside = False
    for loop in loops:
        n = len(loop)
        for i in range(n):
            (x1, y1), (x2, y2) = loop[i], loop[(i + 1) % n]
            if (y1 > y) != (y2 > y) and \
                    x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
    return inside


def _edge_distance(point, loops):
    best = math.inf
    px, py = point
    for loop in loops:
        n = len(loop)
        for i in range(n):
            (x1, y1), (x2, y2) = loop[i], loop[(i + 1) % n]
            dx, dy = x2 - x1, y2 - y1
            length2 = dx * dx + dy * dy
            t = 0.0 if length2 == 0 else max(0.0, min(1.0, (
                (px - x1) * dx + (py - y1) * dy) / length2))
            best = min(best, math.hypot(px - x1 - t * dx, py - y1 - t * dy))
    return best


def section_loops(tris, axis, position):
    from . import section
    return [pts for pts, closed in section.chain(
        section.cut(tris, axis, position)) if closed and len(pts) >= 3]


def dowel_points(loops, count, diameter, samples=28):
    """Up to *count* (u, v) points inside the section, each at least a
    dowel diameter from every edge, spread as far apart as possible."""
    if not loops or count <= 0:
        return []
    us = [u for loop in loops for u, _v in loop]
    vs = [v for loop in loops for _u, v in loop]
    candidates = []
    for i in range(samples):
        for j in range(samples):
            p = (min(us) + (max(us) - min(us)) * (i + 0.5) / samples,
                 min(vs) + (max(vs) - min(vs)) * (j + 0.5) / samples)
            if _inside(p, loops):
                room = _edge_distance(p, loops)
                if room >= diameter:
                    candidates.append((room, p))
    if not candidates:
        return []
    candidates.sort(reverse=True)
    chosen = [candidates[0][1]]
    while len(chosen) < count:
        best = max(candidates, key=lambda c: min(math.dist(c[1], q)
                                                  for q in chosen))
        if min(math.dist(best[1], q) for q in chosen) < 2 * diameter:
            break
        chosen.append(best[1])
    return chosen


def _clone(node):
    from .scadinclude import clone
    return clone(node)


def _point3(axis, position, u, v):
    from . import section
    k, (iu, iv), _names = section.PLANES[axis]
    p = [0.0, 0.0, 0.0]
    p[k], p[iu], p[iv] = position, u, v
    return p


def _along(axis, point, radius, length, name):
    """A cylinder of *length* centred on *point* along *axis*."""
    cyl = CadNode("cylinder", name, dict(
        x=0.0, y=0.0, z=-length / 2, height=length, radius_bottom=radius,
        radius_top=radius, segments=32, center=False))
    node = cyl
    if axis != "z":
        turn = CadNode("rotate", "Along the cut", dict(
            x=0.0 if axis == "x" else -90.0, y=90.0 if axis == "x" else 0.0,
            z=0.0))
        turn.add(node)
        node = turn
    move = CadNode("translate", name, dict(x=point[0], y=point[1],
                                           z=point[2]))
    move.add(node)
    return move


def split_part(model, part, axis="z", position=None, dowels=2,
               dowel_diameter=5.0, dowel_depth=10.0, clearance=0.15,
               gap=10.0):
    """Split *part* (an Object, or any node) across ``axis = position``
    (in its own frame; None = the middle). Returns (first half, second
    half, pin or None, dowel points)."""
    from . import anchors, mesh
    if axis not in AXES:
        raise ValueError("axis must be x, y or z")
    source = part
    if part.type == "reference":
        from .mates import definition_of
        source = definition_of(model, part) or part
    # the document's variables: a part sized by expressions (m, teeth)
    # tessellated without them came out at zero size
    env = anchors.doc_env(model)
    tris = anchors.local_tris(source, env=env, fn=model.effective_fn()) \
        if source.type == "component" else mesh.tessellate(
            source, env=env, fn=model.effective_fn())
    box = anchors.bbox(tris)
    if box is None:
        raise ValueError("the part has no geometry to split")
    lo, hi = box
    k = AXES.index(axis)
    if position is None:
        position = (lo[k] + hi[k]) / 2
    if not lo[k] < position < hi[k]:
        raise ValueError(f"the plane {axis} = {position:g} misses the part "
                         f"({lo[k]:g} to {hi[k]:g})")
    loops = section_loops(tris, axis, position)
    points = dowel_points(loops, int(dowels), dowel_diameter)
    contents = list(source.children) if source.type == "component" \
        else [source]
    margin = 1.0 + max(hi[i] - lo[i] for i in range(3))
    name = part.name
    halves = []
    for side in (0, 1):
        comp = model.new_component(f"{name} (part {side + 1})")
        cut = CadNode("difference", "Cut with dowel holes")
        keep = CadNode("intersection", f"Side {side + 1} of the cut")
        body = CadNode("union", f"{name}")
        for child in contents:
            body.add(_clone(child))
        keep.add(body)
        start = [lo[i] - margin for i in range(3)]
        size = [hi[i] - lo[i] + 2 * margin for i in range(3)]
        if side == 0:
            size[k] = position - start[k]
        else:
            start[k] = position
            size[k] = hi[k] + margin - position
        keep.add(CadNode("cube", "Side box", dict(
            x=start[0], y=start[1], z=start[2], width=size[0],
            depth=size[1], height=size[2], center=False)))
        cut.add(keep)
        for j, (u, v) in enumerate(points):
            cut.add(_along(axis, _point3(axis, position, u, v),
                           dowel_diameter / 2 + clearance,
                           dowel_depth + 1.0, f"Dowel hole {j + 1}"))
        comp.add(cut)
        if side == 1 and gap:
            comp.params[AXES[k]] = float(gap)
        halves.append(comp)
    pin = None
    if points:
        pin = model.new_component(f"{name} dowel pin")
        pin.add(CadNode("cylinder", "Dowel pin", dict(
            x=0.0, y=0.0, z=0.0, height=dowel_depth,
            radius_bottom=dowel_diameter / 2,
            radius_top=dowel_diameter / 2, segments=32, center=False)))
        pin.params["x"] = hi[0] + 10.0
    model.set_visible(part, False)
    model.structure_changed.emit()
    return halves[0], halves[1], pin, points
