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

#: what the kept outline is called (2026-11-01, the user did not know
#: what "Part section" was): the model's edges the sketch closes with
NAME = "Model edges"
NAMES = (NAME, "Part section")          # older files

#: what selecting it says, in 3D and in Properties (2026-11-01, the
#: user: "it needs to be extra clear what it is")
LABEL = "Model edges: the part's outline on this sketch plane"
EXPLAIN = (
    "The outline of the part where this sketch's plane cuts it, kept so "
    "your lines can close an area against the model (a line alone "
    "encloses nothing). The Regions beside it keeps the area between "
    "your lines and these edges — that area is what is extruded.\n\n"
    "It is construction geometry: never part of the solid, never edited "
    "by hand. It is rebuilt from the model, so the feature follows when "
    "the part changes. Deleting it leaves the Regions nothing to close "
    "its area with.")


class drawn:
    """``with drawn(node):`` the construction mark is lifted for the
    block, so the outline code sees the shape (no signal, no undo)."""

    def __init__(self, node):
        self.node = node

    def __enter__(self):
        self.mod = self.node.params.pop("modifier", None) \
            if is_section(self.node) else None
        return self.node

    def __exit__(self, *exc):
        if self.mod is not None:
            self.node.params["modifier"] = self.mod
        return False


def is_section(node):
    """The model's outline kept in a sketch (`keep`): not drawn by the
    user, never moved by hand — it follows the part (model_refs)."""
    return node is not None and node.type == "polygon" and \
        node.name in NAMES
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


def section_shape(window, container, grow=GROW):
    """{points, paths} of the parts' section at *container*'s plane (the
    part the sketch itself builds left out), or None."""
    from . import section, section_outline
    try:
        tris = built_before(window, container)
    except Exception:
        return None
    if not tris or len(tris) > MAX_TRIS:
        return None
    o, r, u, n = _frame(container)
    segs = section_outline.plane_segments(tris, o, n, r, u)
    if not segs:
        return None
    loops = [pts for pts, closed in section.chain(segs)
             if closed and len(pts) >= 3]
    loops = _grown(loops, grow)
    points, paths = [], []
    for pts in loops:
        paths.append(list(range(len(points), len(points) + len(pts))))
        points.extend([[round(p[0], 4), round(p[1], 4)] for p in pts])
    if not paths:
        return None
    return {"points": points, "paths": paths}


def built_before(window, container, own=True):
    """World triangles of what was built BEFORE *container*'s feature:
    the earlier siblings at every level up to the scope, each whole and
    alone. A later feature is never in it (2026-11-01, the user: a slot
    cut in the rib afterwards came back in the rib's own section and cut
    a rectangle right through it), nor is a Difference's later cut."""
    from . import anchors, mesh
    from .model import SHAPE_2D
    root = window._render_scope()[0]
    iso = root if root is not window.model.root else None
    env = anchors.doc_env(window.model)
    fn = window.model.effective_fn()
    # (*own* False: without what *container* itself holds — its extrude)
    nodes = [c for c in container.children if c.category != SHAPE_2D] \
        if own else []
    probe = container
    while probe is not root and probe.parent is not None:
        kids = probe.parent.children
        nodes += kids[:kids.index(probe)]
        probe = probe.parent
    tris = []
    with window._isolated_frame(iso):
        for node in nodes:
            if not node.visible or node.type in ("assign", "variables"):
                continue
            m = mesh.ancestor_matrix(node, env, stop=iso)
            tris += mesh.transform_mesh(m, mesh.tessellate(node, env, fn=fn))
    return tris


def _grown(loops, grow=GROW):
    """*loops* (outlines CCW, holes CW) grown *grow* outward, holes
    shrunk by as much (a negative *grow* shrinks); as they are without
    Manifold."""
    try:
        import manifold3d as m
        cs = m.CrossSection([[(float(p[0]), float(p[1])) for p in lp]
                             for lp in loops], m.FillRule.Positive)
        out = [list(lp) for lp in
               cs.offset(grow, m.JoinType.Miter).to_polygons()]
        return [lp for lp in out if len(lp) >= 3] or loops
    except Exception:
        return loops


def with_section(window, container, shapes):
    """*shapes* plus a transient construction polygon of the section, or
    *shapes* alone when the plane cuts nothing. The section is grown, so
    a cut's area reaches past the part's side and leaves no wall; a boss
    is pushed back into the part afterwards (regions2d `fuse`) — a
    shrunk section changed which areas there are where a circle met the
    part's edge exactly (the pivot guide's arm)."""
    grow = GROW
    params = section_shape(window, container, grow)
    if params is None:
        return list(shapes), None
    from .model import CadNode
    ghost = CadNode("polygon", NAME, dict(params, modifier="%",
                                          section_grow=grow))
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
