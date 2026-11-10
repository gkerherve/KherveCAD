"""WHICH feature a face sketch stands on (2026-11-10, the user: a boss
on a boss on a boss, "look if all is kept integral").

A face sketch followed its face by geometry alone (model_refs.follow):
after a model change, the flat face of the same facing nearest where
the old one was. Stacked features break that: the second boss made
10 mm taller lifts the hexagon's top from 47 to 57 — and its own top to
45, two millimetres from where the cut's sketch stood. The cut moved
DOWN onto the boss and the pin after it; the tower came apart.

So the sketch also remembers the feature whose face it was drawn on, by
that feature's place in the History (``feature_list.ORDER`` — node ids
do not outlive an undo, and names repeat): ``params["face_owner"]``.
Following then looks only at THAT feature's own solid — a cut's turned
inside out, since the face a sketch stands on in a pocket is the cut
tool's wall or floor seen from inside.

A sketch from before, or one on a face no single feature owns (a
fillet's, an imported part's), has no owner and follows by geometry as
it did.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

OWNER = "face_owner"
#: a point this near a triangle's plane (mm) lies on it
ON_PLANE = 2e-3
#: types whose own solid can own a face
_SOLIDS = ("linear_extrude", "rotate_extrude", "cube", "cylinder",
           "sphere", "sweep", "section_loft", "polyhedron")


def _world(window, node):
    """*node*'s own solid in the scope's world; a cut's inside out."""
    from . import anchors, extrude_panel, mesh
    root = window._render_scope()[0]
    iso = root if root is not window.model.root else None
    env = anchors.doc_env(window.model)
    fn = window.model.effective_fn()
    with window._isolated_frame(iso):
        m = mesh.ancestor_matrix(node, env, stop=iso)
        tris = mesh.transform_mesh(m, mesh.tessellate(node, env, fn=fn))
    if extrude_panel.is_cut(node):
        tris = [(t[0], t[2], t[1]) + tuple(t[3:]) for t in tris]
    return tris


def _normal(t):
    u = [t[1][i] - t[0][i] for i in range(3)]
    v = [t[2][i] - t[0][i] for i in range(3)]
    c = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
         u[0] * v[1] - u[1] * v[0]]
    length = sum(x * x for x in c) ** 0.5
    return [x / length for x in c] if length > 1e-12 else None


def _holds(t, p, n):
    """Is *p* on triangle *t* (facing *n*)?"""
    nt = _normal(t)
    if nt is None or sum(a * b for a, b in zip(nt, n)) < 0.999:
        return False
    if abs(sum((p[i] - t[0][i]) * nt[i] for i in range(3))) > ON_PLANE:
        return False
    for i in range(3):
        a, b = t[i], t[(i + 1) % 3]
        e = [b[k] - a[k] for k in range(3)]
        w = [p[k] - a[k] for k in range(3)]
        c = [e[1] * w[2] - e[2] * w[1], e[2] * w[0] - e[0] * w[2],
             e[0] * w[1] - e[1] * w[0]]
        if sum(c[k] * nt[k] for k in range(3)) < -1e-6:
            return False
    return True


def _before(window, group):
    """The solids built before *group*, latest first."""
    from . import feature_list
    root = window._render_scope()[0]
    out, probe = [], group
    while probe is not root and probe.parent is not None:
        kids = probe.parent.children
        for sib in kids[:kids.index(probe)]:
            out += [n for n in sib.walk() if n.type in _SOLIDS
                    and isinstance(n.params.get(feature_list.ORDER), int)]
        probe = probe.parent
    out.sort(key=lambda n: -n.params[feature_list.ORDER])
    return out


def remember(window, group, point, normal):
    """Note the feature whose face holds *point* (facing *normal*) on
    the sketch *group*. Returns it, or None."""
    from . import feature_list
    feature_list.stamp(window.model)
    group.params.pop(OWNER, None)
    try:
        for node in _before(window, group):
            if any(_holds(t, point, normal) for t in _world(window, node)):
                group.params[OWNER] = node.params[feature_list.ORDER]
                return node
    except Exception:                       # never stop a sketch
        pass
    return None


def owner(window, group):
    from . import feature_list
    k = group.params.get(OWNER)
    if not isinstance(k, int):
        return None
    return next((n for n in window.model.root.walk()
                 if n.params.get(feature_list.ORDER) == k
                 and n.type in _SOLIDS), None)


def tris(window, group):
    """The owner's solid for model_refs.follow, or None (no owner, it
    is gone, or switched off)."""
    node = owner(window, group)
    if node is None:
        return None
    try:
        got = _world(window, node)
    except Exception:
        return None
    return got or None
