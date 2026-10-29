"""The PART'S OUTLINE where a sketch's plane cuts it, as an area-maker
(2026-10-29, the user: a line drawn across the middle of the lever on
its middle plane, then "select the top" in 3D and cut it).

A sketch of loose lines encloses nothing by itself; with the section of
the parts at its plane (section_outline.plane_segments) its lines split
that section into areas. `section_shape` gives the section as one
construction polygon (points + paths, in the sketch's own frame) — never
drawn in 3D, dashed in 2D — and `with_section` the sketch's shapes plus
a transient copy of it, which sketch_regions' arrangement takes like any
outline. When areas are picked, `keep` adds the polygon to the sketch for
real, so the Regions node built from them can always rebuild its area
from its own shapes.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

NAME = "Part section"
MAX_TRIS = 400000
#: how far the section is grown past the part's outline (mm): an area cut
#: exactly along the part's own side faces left them standing as walls
GROW = 0.05


def _frame(container):
    """Origin, right, up, unit normal of *container*'s sketch plane in
    the world (its shapes' params frame)."""
    from . import mesh
    m = mesh.ancestor_matrix(container, {})
    m = mesh.mat_mul(m, mesh.node_matrix(container, {}))

    def at(x, y):
        return tuple(m[i][0] * x + m[i][1] * y + m[i][3] for i in range(3))
    o = at(0.0, 0.0)
    r = [a - b for a, b in zip(at(1.0, 0.0), o)]
    u = [a - b for a, b in zip(at(0.0, 1.0), o)]
    n = (r[1] * u[2] - r[2] * u[1], r[2] * u[0] - r[0] * u[2],
         r[0] * u[1] - r[1] * u[0])
    length = sum(c * c for c in n) ** 0.5 or 1.0
    return o, r, u, tuple(c / length for c in n)


def _inside(node, ancestor):
    probe = node
    while probe is not None:
        if probe is ancestor:
            return True
        probe = probe.parent
    return False


def section_shape(window, container):
    """{points, paths} of the parts' section at *container*'s plane (the
    part the sketch itself builds left out), or None."""
    from . import meshedit_ui, section, section_outline
    try:
        parts = meshedit_ui._parts(window)
    except Exception:
        return None
    tris = [t for node, ts in parts if not _inside(container, node)
            for t in ts]
    for node, _ts in parts:
        if _inside(container, node):
            # the sketch shares its plane's group with features made
            # before (every Front sketch is one "Front sketch" rotate):
            # those are part of the section, only its own shapes are not
            tris += _beside(window, node, container)
    if not tris or len(tris) > MAX_TRIS:
        return None
    o, r, u, n = _frame(container)
    segs = section_outline.plane_segments(tris, o, n, r, u)
    if not segs:
        return None
    loops = [pts for pts, closed in section.chain(segs)
             if closed and len(pts) >= 3]
    loops = _grown(loops)
    points, paths = [], []
    for pts in loops:
        paths.append(list(range(len(points), len(points) + len(pts))))
        points.extend([[round(p[0], 4), round(p[1], 4)] for p in pts])
    if not paths:
        return None
    return {"points": points, "paths": paths}


def _beside(window, part, container):
    """World triangles of what *part* holds besides *container*'s own 2D
    shapes and the chain down to it."""
    from . import mesh
    from .model import SHAPE_2D
    chain = []
    probe = container
    while probe is not None:
        chain.append(probe)
        if probe is part:
            break
        probe = probe.parent
    ids = set()
    for holder in chain:
        for child in holder.children:
            if child in chain or not child.visible:
                continue
            if holder is container and child.category == SHAPE_2D:
                continue
            ids.add(child.id)
    if not ids:
        return []
    root = window._render_scope()[0]
    iso = root if root is not window.model.root else None
    try:
        with window._isolated_frame(iso):
            return mesh.selected_world_tris(
                root, ids, fn=window.model.effective_fn())
    except Exception:
        return []


def _grown(loops):
    """*loops* (outlines CCW, holes CW) grown GROW outward, holes shrunk
    by as much; as they are without Manifold."""
    try:
        import manifold3d as m
        cs = m.CrossSection([[(float(p[0]), float(p[1])) for p in lp]
                             for lp in loops], m.FillRule.Positive)
        out = [list(lp) for lp in
               cs.offset(GROW, m.JoinType.Miter).to_polygons()]
        return [lp for lp in out if len(lp) >= 3] or loops
    except Exception:
        return loops


def with_section(window, container, shapes):
    """*shapes* plus a transient construction polygon of the section, or
    *shapes* alone when the plane cuts nothing."""
    params = section_shape(window, container)
    if params is None:
        return list(shapes), None
    from .model import CadNode
    ghost = CadNode("polygon", NAME, dict(params, modifier="%"))
    ghost.parent = container
    return list(shapes) + [ghost], ghost


def keep(model, container, ghost):
    """The transient section polygon, added to the sketch for real (the
    picked areas rely on it); returns the node."""
    if ghost is None:
        return None
    ghost.parent = None
    node = model.add_node("polygon", dict(ghost.params), parent=container,
                          name=NAME)
    return node
