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
Face sketches follow: a boss standing as its own part (a rib) and a
cut in its body's Difference (`plan`); a corner, the middle of an edge
or a point on an edge.

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


def _face_group(container):
    """The face sketch's Group holding *container* (itself, or the
    Group round its extrude / Regions), or None."""
    from . import face_sketch
    node = container
    while node is not None:
        if node.params.get(face_sketch.KEY):
            return node
        node = node.parent
    return None


def _own_part(container, root):
    """The scope child the sketch belongs to."""
    node = container
    while node is not None and node.parent is not root:
        node = node.parent
    return node


def plan(container, root):
    """What the outline is made of, or None when it cannot be told:
    (face Group, part to leave out, body to put back). A BOSS sketched
    on a face stands as its own part (the rib): left out whole. A CUT
    sketched on a face sits in a Difference with the body it cuts: its
    part is left out and that body put back — the face as it was before
    the cut (2026-11-01, the user's circle on the block's top edge). A
    sketch sharing a plane's group with other features (every Front
    sketch is one "Front sketch" rotate) cannot be told apart from them
    (the pivot guide lost its arm) and keeps its references as drawn."""
    g = _face_group(container)
    if g is None:
        return None
    own = _own_part(container, root)
    if own is None:
        return None
    if own is g:
        feats = [n for n in own.walk()
                 if n.type in ("linear_extrude", "rotate_extrude")]
        return (g, own, None) if len(feats) <= 1 else None
    p = g
    while p.parent is not None and p is not own:
        d = p.parent
        if d.type == "difference" and d.children and \
                d.children[0] is not p:
            return g, own, d.children[0]
        p = d
    return None


def _has_refs(container, root):
    from . import sketch_constraints as sc, sketch_section
    if plan(container, root) is None:
        return False
    rows = sc.rows(container)
    if any(r.get("kind") == "on_edge" or
           (r.get("kind") == "fix" and r.get("model")) for r in rows):
        return True
    return any(sketch_section.is_section(n) for n in container.children)


def outline(window, container):
    """[((x, y), (x, y))] the model's face at *container*'s plane in its
    frame (`plan`), or None when unknown."""
    from . import face_outline, mesh, meshedit_ui
    root = window._render_scope()[0]
    got = plan(container, root)
    if got is None:
        return None
    g, own, body = got
    tris = [t for n, ts in meshedit_ui._parts(window) if n is not own
            for t in ts]
    if body is not None:
        iso = root if root is not window.model.root else None
        # the body ALONE, uncut: picked out of its Difference by a
        # selection pass it came back with the cut already in it, so the
        # middle of the block's top edge was not on the outline
        fn = window.model.effective_fn()
        with window._isolated_frame(iso):
            m4 = mesh.ancestor_matrix(body, stop=iso)
            tris += mesh.transform_mesh(m4, mesh.tessellate(body, fn=fn))
    if not tris:
        return None
    return face_outline.whole_face(g, tris, [])


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
    nearest = None
    for q, ds in corners.items():
        d = math.hypot(q[0] - p[0], q[1] - p[1])
        nearest = d if nearest is None else min(nearest, d)
        ok = not want or _dirs_match(want, ds)
        key = (0 if ok else 1, d)
        if best is None or key < best[0]:
            best = (key, q)
    (miss, d), q = best
    if miss or (d > 3 * nearest and d > 1.0):
        # the corner is gone (a cut ate it, the user's block made too
        # narrow for its pipe): a far corner of the same shape is NOT
        # it — the reference dangles and stays where it was
        return None
    return q


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


def _dangling(window, container):
    try:
        window.statusBar().showMessage(
            "%s: a corner it was drawn to is gone — that point stays where "
            "it was (redraw it to another corner)." % container.name, 8000)
    except Exception:                       # pragma: no cover
        pass


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
                if r["kind"] == "fix" and r.get("model") == "mid":
                    # the middle of a model edge: of that edge, now
                    e = match_edge(segs, r["edge"])
                    if e is None:
                        continue
                    q = ((e[0][0] + e[1][0]) / 2, (e[0][1] + e[1][1]) / 2)
                    p = tuple(r["at"])
                    r["edge"] = [round(v, 6) for v in (*e[0], *e[1])]
                    if math.hypot(q[0] - p[0], q[1] - p[1]) > SAME:
                        r["at"] = [round(q[0], 6), round(q[1], 6)]
                        moved = True
                elif r["kind"] == "fix":
                    p = tuple(r["at"])
                    q = match_corner(segs, p, r.get("dirs"))
                    if q is None:
                        _dangling(window, container)
                        continue
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
    got = plan(container, window._render_scope()[0])
    if got is not None and got[2] is None and \
            _update_section(window, container):
        moved = True                       # (a boss: its own outline)
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
            if node.children and _has_refs(node, root):
                try:
                    refresh_container(window, node)
                except Exception:          # never break an edit
                    import traceback
                    traceback.print_exc()
    finally:
        _BUSY = False


def adopt_container(window, container):
    """Plain fixes sitting on the model become model references: a point
    fixed where a model corner or the middle of a model edge is (drawn
    before sketches followed the model, or snapped without the pin) is
    taken to be tied to it — the user's circle at the middle of the
    block's top edge kept its place when the block narrowed.
    The number of rows adopted."""
    from . import sketch_constraints as sc
    rows = sc.rows(container)
    plain = [r for r in rows if r.get("kind") == "fix" and
             not r.get("model") and r.get("at")]
    if not plain:
        return 0
    segs = outline(window, container)
    if not segs:
        return 0
    n = 0
    for r in plain:
        p = tuple(r["at"])
        mid = next(((a, b) for a, b in segs if
                    abs((a[0] + b[0]) / 2 - p[0]) < 1e-4 and
                    abs((a[1] + b[1]) / 2 - p[1]) < 1e-4), None)
        dirs = _corner_dirs(segs, p)
        if dirs:
            r["model"] = True
            r["dirs"] = [round(d, 6) for d in dirs]
            n += 1
        elif mid is not None:
            r["model"] = "mid"
            r["edge"] = [round(v, 6) for v in (*mid[0], *mid[1])]
            n += 1
    return n



def adopt(window):
    """`adopt_container` over every sketch of the current scope (when
    the scope opens, and when a face sketch is left)."""
    global _BUSY
    if _BUSY:
        return 0
    _BUSY = True
    n = 0
    try:
        root = window._render_scope()[0]
        for node in list(root.walk()):
            if node.children and node.params.get("constraints") and \
                    plan(node, root) is not None:
                try:
                    n += adopt_container(window, node)
                except Exception:
                    import traceback
                    traceback.print_exc()
    finally:
        _BUSY = False
    return n
