"""Sketches on a PLANE through the part follow the part (2026-11-10, the
user: a cone revolved from lines on the Front plane, drawn from the
corner of a pin, stayed in the air when the pin shrank or rose — "yes,
fix it").

A sketch on a face follows its face (model_refs). A sketch on a plane
that cuts THROUGH the part has no face: what its points were snapped to
is the part's SECTION by that plane. The whole section cannot be
followed by geometry — a boss made 10 mm taller lifts a stack of
features, and the edge nearest where the pin's top was is then the top
of the feature under it. So each reference remembers the FEATURE whose
own section it sits on (its place in the History, as face_owner does
for faces): ``row["owner"]``. After a model edit the owner's solid alone
is cut by the sketch's plane and the reference moved to its counterpart
there:

- a ``fix`` on a section corner (``model`` True, ``dirs``): the corner
  with the same edge directions;
- a ``fix`` at the middle of a section edge (``model`` "mid", ``edge``):
  the middle of that edge;
- a ``fix`` elsewhere on a section edge (``model`` "on", ``edge``): its
  foot on that edge — it rises with a top, keeps its place along it;
- an ``on_edge`` row: that edge.

Section segments run with the solid on their left, so an edge is matched
by DIRECTION, not only by being parallel: a pin's top is never taken for
its bottom.

`adopt` (when the scope opens and when a sketch is left) gives an owner
to the rows that sit on one; a point on no single feature's section (a
corner two features make together) stays as drawn.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

OWNER = "owner"
#: a point this near a section corner / edge (mm) sits on it
ON = 2e-3
#: two edge directions agree within this (radians)
ANGLE_TOL = math.radians(1.0)
SAME = 1e-6

#: {(container id, owner): the owner's section last seen}
_LAST = {}


def _node(window, k):
    from . import face_owner, feature_list
    return next((n for n in window.model.root.walk()
                 if n.params.get(feature_list.ORDER) == k
                 and n.type in face_owner._SOLIDS), None)


def _frame(window, container):
    """Origin, right, up, unit normal of the sketch plane in the scope's
    world."""
    from . import model_refs
    m = model_refs.sketch_matrix(window, container)

    def at(x, y):
        return tuple(float(m[i][0] * x + m[i][1] * y + m[i][3])
                     for i in range(3))
    o = at(0.0, 0.0)
    r = [a - b for a, b in zip(at(1.0, 0.0), o)]
    u = [a - b for a, b in zip(at(0.0, 1.0), o)]
    n = (r[1] * u[2] - r[2] * u[1], r[2] * u[0] - r[0] * u[2],
         r[0] * u[1] - r[1] * u[0])
    length = sum(c * c for c in n) ** 0.5 or 1.0
    return o, r, u, tuple(c / length for c in n)


def section(window, container, node, frame=None):
    """[((x, y), (x, y))] *node*'s own solid cut by *container*'s plane,
    in the sketch's frame; [] when it does not reach the plane."""
    from . import face_owner, section_outline, sketch_section
    tris = face_owner._world(window, node)
    if not tris or len(tris) > sketch_section.MAX_TRIS:
        return []
    o, r, u, n = frame or _frame(window, container)
    return section_outline.plane_segments(tris, o, n, r, u) or []


def _dir(a, b):
    return math.atan2(b[1] - a[1], b[0] - a[0])


def _turn(x, y):
    return abs((x - y + math.pi) % (2 * math.pi) - math.pi)


def _off(seg, p):
    """Signed distance of *p* from *seg*'s line, and where along it
    (0..1)."""
    a, b = seg
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy or 1e-18
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2
    off = (dx * (p[1] - a[1]) - dy * (p[0] - a[0])) / math.sqrt(L2)
    return off, t


def edge_at(segs, p, tol=ON):
    """The section edge *p* lies on (between its ends), or None."""
    for seg in segs:
        off, t = _off(seg, p)
        L = math.dist(seg[0], seg[1])
        if abs(off) < tol and -tol / (L or 1) <= t <= 1 + tol / (L or 1):
            return seg
    return None


def match_edge(segs, edge):
    """The edge of *segs* that *edge* (ax, ay, bx, by) became: the same
    direction, the nearest to its middle."""
    a, b = (edge[0], edge[1]), (edge[2], edge[3])
    ang = _dir(a, b)
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    best = None
    for seg in segs:
        if _turn(_dir(*seg), ang) > ANGLE_TOL:
            continue
        off, t = _off(seg, mid)
        # beside the edge counts less than beyond its ends
        along = 0.0 if 0 <= t <= 1 else \
            min(abs(t), abs(t - 1)) * math.dist(*seg)
        key = abs(off) + along
        if best is None or key < best[0]:
            best = (key, seg)
    return best[1] if best else None


def _flat(seg):
    return [round(float(v), 6) for v in (*seg[0], *seg[1])]


def _foot(seg, p):
    a, b = seg
    _o, t = _off(seg, p)
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _candidates(window, container):
    from . import face_owner, feature_list
    feature_list.stamp(window.model)
    try:
        return face_owner._before(window, container)
    except Exception:
        return []


def adopt(window, container):
    """Rows of *container* sitting on ONE earlier feature's section take
    that feature for owner. The number adopted."""
    from . import feature_list, model_refs, sketch_constraints as sc
    rows = sc.rows(container)
    want = [r for r in rows if not isinstance(r.get(OWNER), int) and (
        (r.get("kind") == "fix" and not r.get("model") and r.get("at"))
        or (r.get("kind") == "on_edge" and r.get("edge")))]
    if not want:
        _remember(window, container, rows)
        return 0
    nodes = _candidates(window, container)
    if not nodes:
        return 0
    frame = _frame(window, container)
    cache = {}

    def segs_of(node):
        if id(node) not in cache:
            try:
                cache[id(node)] = section(window, container, node, frame)
            except Exception:
                cache[id(node)] = []
        return cache[id(node)]
    n = 0
    for r in want:
        for node in nodes:                  # the latest feature first
            segs = segs_of(node)
            if not segs:
                continue
            if r["kind"] == "on_edge":
                e = r["edge"]
                hit = next((s for s in segs
                            if abs(_off(((e[0], e[1]), (e[2], e[3])),
                                        s[0])[0]) < ON
                            and abs(_off(((e[0], e[1]), (e[2], e[3])),
                                         s[1])[0]) < ON), None)
                if hit is None:
                    continue
                r["edge"] = _flat(hit)
            else:
                p = tuple(r["at"])
                dirs = model_refs._corner_dirs(segs, p, ON)
                seg = edge_at(segs, p)
                if dirs:
                    r["model"] = True
                    r["dirs"] = [round(d, 6) for d in dirs]
                elif seg is not None:
                    mid = ((seg[0][0] + seg[1][0]) / 2,
                           (seg[0][1] + seg[1][1]) / 2)
                    r["model"] = "mid" if math.dist(mid, p) < ON else "on"
                    r["edge"] = _flat(seg)
                else:
                    continue
            r[OWNER] = node.params[feature_list.ORDER]
            n += 1
            break
    if n:
        container.params[sc.KEY] = rows
    _remember(window, container, rows)
    return n


def _remember(window, container, rows):
    """Note each owner's section as it is now (what `refresh` compares
    with)."""
    frame = None
    for k in {r[OWNER] for r in rows if isinstance(r.get(OWNER), int)}:
        if (container.id, k) in _LAST:
            continue
        node = _node(window, k)
        if node is None:
            continue
        try:
            frame = frame or _frame(window, container)
            segs = section(window, container, node, frame)
        except Exception:
            segs = []
        if segs:
            _LAST[(container.id, k)] = segs


def has_refs(container):
    return any(isinstance(r.get(OWNER), int)
               for r in container.params.get("constraints") or [])


def refresh(window, container):
    """Move *container*'s owned references onto their owners' sections
    as they are now. True when anything moved."""
    from . import model_refs, sketch_constraints as sc
    rows = sc.rows(container)
    owned = [r for r in rows if isinstance(r.get(OWNER), int)]
    if not owned:
        return False
    frame = _frame(window, container)
    cache = {}
    moved = False
    for r in owned:
        k = r[OWNER]
        if k not in cache:
            node = _node(window, k)
            try:
                cache[k] = section(window, container, node, frame) \
                    if node is not None else []
            except Exception:
                cache[k] = []
        segs = cache[k]
        if not segs:
            continue                        # gone or switched off: stays
        prev = _LAST.get((container.id, k))
        if r["kind"] == "on_edge":
            seg = match_edge(segs, r["edge"])
            if seg is not None and any(
                    abs(x - y) > SAME for x, y in zip(_flat(seg), r["edge"])):
                r["edge"] = _flat(seg)
                moved = True
            continue
        p = tuple(r["at"])
        if r.get("model") is True:
            q = model_refs.match_corner(segs, p, r.get("dirs"), prev)
        else:
            seg = match_edge(segs, r.get("edge") or [0, 0, 0, 0])
            if seg is None:
                continue
            q = ((seg[0][0] + seg[1][0]) / 2, (seg[0][1] + seg[1][1]) / 2) \
                if r.get("model") == "mid" else _foot(seg, p)
            r["edge"] = _flat(seg)
        if q is None:
            continue
        if math.dist(q, p) > SAME:
            r["at"] = [round(float(q[0]), 6), round(float(q[1]), 6)]
            moved = True
    for k, segs in cache.items():
        if segs:
            _LAST[(container.id, k)] = segs
    if moved:
        container.params[sc.KEY] = rows
        try:
            sc.solve(container, rows, env=sc._env(window.model))
        except Exception:
            pass
        window.model.node_changed.emit(container)
    return moved
