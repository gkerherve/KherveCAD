"""Anchors and origins on Objects — the attachment points parts snap by.

Every Object (component) carries a coordinate frame of **anchors**:

- automatic anchors derived from its local bounding box (the origin,
  6 face centres, 12 edge midpoints and 8 corners — the BOSL2 /
  mate-connector idea), recomputed on demand so they always match the
  geometry;
- user anchors picked on a real face or edge in the 3D view, stored in
  the component's ``params["anchors"]`` (a list of dicts) so they
  round-trip through ``.kcad``.

An anchor is ``{"name", "kind", "pos", "dir"}`` in the Object's LOCAL
frame (before its placement x/y/z/rx/ry/rz). ``kind`` is one of
``origin | face | edge | corner | custom``. The mate system (attach/
snap) aligns two anchors' frames; **Set origin** re-bases an Object so
a chosen anchor becomes its local origin without moving it in the
scene.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from . import mesh
from .model import CadNode

#: placement param keys an Object carries.
_PLACEMENT = ("x", "y", "z", "rx", "ry", "rz")


def doc_env(model) -> dict:
    """Global variables resolved in order — the environment anchors
    (and their bounding boxes) are computed under."""
    from . import expr
    env = {}
    for node in model.global_assigns():
        if not node.visible:
            continue
        var = str(node.params.get("variable", "")).strip()
        if var:
            env[var] = expr.resolve(node.params.get("value", 0), env, 0.0)
    return env


# ------------------------------------------------------------ local frame

def local_tris(comp, env=None, fn=None):
    """Triangles of *comp*'s subtree in its LOCAL frame — the Object's
    own placement params are not applied, and neither is its Main-tab
    visibility (a hidden Object still has anchors and can be mated)."""
    saved = {k: comp.params.get(k, 0.0) for k in _PLACEMENT}
    saved_visible = comp.visible
    try:
        for k in _PLACEMENT:
            comp.params[k] = 0.0
        comp.visible = True
        return mesh.tessellate(comp, env=env, fn=fn)
    finally:
        comp.params.update(saved)
        comp.visible = saved_visible


def bbox(tris):
    """((x0, y0, z0), (x1, y1, z1)) of *tris*, or None when empty."""
    if not tris:
        return None
    xs = [v[0] for t in tris for v in t]
    ys = [v[1] for t in tris for v in t]
    zs = [v[2] for t in tris for v in t]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def _norm(v):
    length = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return [v[0] / length, v[1] / length, v[2] / length]


#: face name -> (axis index, which side, outward direction)
_FACES = [
    ("Right", 0, 1, (1, 0, 0)), ("Left", 0, 0, (-1, 0, 0)),
    ("Back", 1, 1, (0, 1, 0)), ("Front", 1, 0, (0, -1, 0)),
    ("Top", 2, 1, (0, 0, 1)), ("Bottom", 2, 0, (0, 0, -1)),
]


def auto_anchors(comp, env=None, fn=None):
    """Anchors derived from the local bounding box: the origin, the 6
    face centres, 12 edge midpoints and 8 corners."""
    anchors = [dict(name="Origin", kind="origin",
                    pos=[0.0, 0.0, 0.0], dir=[0.0, 0.0, 1.0])]
    box = bbox(local_tris(comp, env=env, fn=fn))
    if box is None:
        return anchors
    lo, hi = box
    mid = [(lo[i] + hi[i]) / 2.0 for i in range(3)]

    def corner_pos(sides):
        """sides: {axis: 0|1} — bbox coordinate per constrained axis,
        the centre elsewhere."""
        return [(lo, hi)[sides[a]][a] if a in sides else mid[a]
                for a in range(3)]

    for name, axis, side, direction in _FACES:
        anchors.append(dict(name=name, kind="face",
                            pos=corner_pos({axis: side}),
                            dir=list(map(float, direction))))
    face_by_axis_side = {(axis, side): (name, direction)
                         for name, axis, side, direction in _FACES}
    # 12 edges: every pair of orthogonal constrained axes
    for a in range(3):
        for b in range(a + 1, 3):
            for sa in (0, 1):
                for sb in (0, 1):
                    na, da = face_by_axis_side[(a, sa)]
                    nb, db = face_by_axis_side[(b, sb)]
                    anchors.append(dict(
                        name=f"{na}-{nb}", kind="edge",
                        pos=corner_pos({a: sa, b: sb}),
                        dir=_norm([da[i] + db[i] for i in range(3)])))
    # 8 corners
    for sx in (0, 1):
        for sy in (0, 1):
            for sz in (0, 1):
                names = [face_by_axis_side[(2, sz)][0],
                         face_by_axis_side[(1, sy)][0],
                         face_by_axis_side[(0, sx)][0]]
                anchors.append(dict(
                    name="-".join(names), kind="corner",
                    pos=corner_pos({0: sx, 1: sy, 2: sz}),
                    dir=_norm([(-1, 1)[sx], (-1, 1)[sy], (-1, 1)[sz]])))
    return anchors


def user_anchors(comp):
    """The Object's own picked anchors (stored on the node)."""
    return [dict(a) for a in comp.params.get("anchors", [])]


def anchors_of(comp, env=None, fn=None):
    """Every anchor of *comp*: automatic bounding-box ones plus the
    user's picked ones — all in the local frame."""
    return auto_anchors(comp, env=env, fn=fn) + user_anchors(comp)


# ------------------------------------------------------- world transforms

def _resolve_placement(comp, env=None):
    from . import expr
    return [expr.resolve(comp.params.get(k, 0.0), env, 0.0)
            for k in _PLACEMENT]


def placement_matrix(comp, env=None):
    """The Object's placement (translate * rotate), as a 4x4 matrix."""
    x, y, z, rx, ry, rz = _resolve_placement(comp, env)
    return mesh.mat_mul(mesh.mat_translate(x, y, z),
                        mesh.mat_rotate(rx, ry, rz))


def _apply(m, p):
    return [m[i][0] * p[0] + m[i][1] * p[1] + m[i][2] * p[2] + m[i][3]
            for i in range(3)]


def _apply_dir(m, d):
    return [m[i][0] * d[0] + m[i][1] * d[1] + m[i][2] * d[2]
            for i in range(3)]


def to_world(comp, point, env=None):
    return _apply(placement_matrix(comp, env), point)


def dir_to_world(comp, direction, env=None):
    x, y, z, rx, ry, rz = _resolve_placement(comp, env)
    return _apply_dir(mesh.mat_rotate(rx, ry, rz), direction)


def to_local(comp, point, env=None):
    """World point -> the Object's local frame (inverse placement)."""
    x, y, z, rx, ry, rz = _resolve_placement(comp, env)
    r = mesh.mat_rotate(rx, ry, rz)
    d = (point[0] - x, point[1] - y, point[2] - z)
    # rotation inverse = transpose
    return [r[0][i] * d[0] + r[1][i] * d[1] + r[2][i] * d[2]
            for i in range(3)]


def dir_to_local(comp, direction, env=None):
    _x, _y, _z, rx, ry, rz = _resolve_placement(comp, env)
    r = mesh.mat_rotate(rx, ry, rz)
    return [r[0][i] * direction[0] + r[1][i] * direction[1]
            + r[2][i] * direction[2] for i in range(3)]


def anchor_world(comp, anchor, env=None):
    """(position, direction) of *anchor* in world coordinates."""
    return (to_world(comp, anchor["pos"], env),
            dir_to_world(comp, anchor["dir"], env))


def world_markers(comp, env=None, fn=None, definition=None):
    """Every anchor of *comp* as a world-space marker dict — what the
    3D view draws. For an assembly instance, pass the Object it
    references as *definition*: the anchors come from the definition's
    local frame, the placement from the instance."""
    markers = []
    for anchor in anchors_of(definition if definition is not None
                             else comp, env=env, fn=fn):
        pos, direction = anchor_world(comp, anchor, env)
        markers.append(dict(name=anchor["name"], kind=anchor["kind"],
                            pos=pos, dir=direction))
    return markers


# ------------------------------------------------------------- model ops

def add_user_anchor(model, comp, pos, direction, name="", kind="custom"):
    """Persist a picked anchor on the Object (local coordinates)."""
    items = [dict(a) for a in comp.params.get("anchors", [])]
    taken = {a.get("name") for a in items}
    base = name or "Anchor"
    candidate, i = base, 2
    while candidate in taken:
        candidate = f"{base} {i}"
        i += 1
    items.append(dict(name=candidate, kind=kind,
                      pos=[round(float(v), 4) for v in pos],
                      dir=[round(float(v), 6) for v in _norm(direction)]))
    comp.params["anchors"] = items
    model.node_changed.emit(comp)
    return items[-1]


def remove_user_anchor(model, comp, name):
    items = [dict(a) for a in comp.params.get("anchors", [])
             if a.get("name") != name]
    comp.params["anchors"] = items
    model.node_changed.emit(comp)


def set_origin(model, comp, pos, env=None):
    """Re-base *comp* so local *pos* becomes its origin — the contents
    shift by -pos and the placement moves by +R·pos, so nothing moves
    in the scene but the Object now rotates/attaches about that point."""
    px, py, pz = (float(v) for v in pos)
    if abs(px) < 1e-9 and abs(py) < 1e-9 and abs(pz) < 1e-9:
        return
    # shift the contents (reuse a previous origin shift when present)
    shift = comp.children[0] if (
        len(comp.children) == 1 and comp.children[0].type == "translate"
        and comp.children[0].name == "Origin shift") else None
    if shift is not None:
        from . import expr
        for key, delta in (("x", -px), ("y", -py), ("z", -pz)):
            shift.params[key] = round(
                expr.resolve(shift.params.get(key, 0.0), env, 0.0)
                + delta, 4)
    else:
        shift = CadNode("translate", "Origin shift",
                        dict(x=round(-px, 4), y=round(-py, 4),
                             z=round(-pz, 4)))
        for child in list(comp.children):
            comp.remove(child)
            shift.add(child)
        comp.add(shift)
    # keep the Object where it was: move the placement by R·pos
    x, y, z, rx, ry, rz = _resolve_placement(comp, env)
    d = _apply_dir(mesh.mat_rotate(rx, ry, rz), (px, py, pz))
    comp.params["x"] = round(x + d[0], 4)
    comp.params["y"] = round(y + d[1], 4)
    comp.params["z"] = round(z + d[2], 4)
    # user anchors live in the local frame: shift them too
    if comp.params.get("anchors"):
        comp.params["anchors"] = [
            dict(a, pos=[round(a["pos"][0] - px, 4),
                         round(a["pos"][1] - py, 4),
                         round(a["pos"][2] - pz, 4)])
            for a in comp.params["anchors"]]
    model.structure_changed.emit()


# ---------------------------------------------------------------- picking

def pick(tris, projector, x, y):
    """The front-most triangle under screen point (x, y). *projector*
    maps a world vertex to (sx, sy, depth) or None. Returns
    ``(index, world_point)`` or ``(None, None)``."""
    best, best_depth, best_point = None, None, None
    for i, (a, b, c) in enumerate(tris):
        pa, pb, pc = projector(a), projector(b), projector(c)
        if pa is None or pb is None or pc is None:
            continue
        # barycentric coordinates of the click in the projected triangle
        d = ((pb[1] - pc[1]) * (pa[0] - pc[0])
             + (pc[0] - pb[0]) * (pa[1] - pc[1]))
        if abs(d) < 1e-9:
            continue
        w0 = ((pb[1] - pc[1]) * (x - pc[0])
              + (pc[0] - pb[0]) * (y - pc[1])) / d
        w1 = ((pc[1] - pa[1]) * (x - pc[0])
              + (pa[0] - pc[0]) * (y - pc[1])) / d
        w2 = 1.0 - w0 - w1
        eps = -1e-6
        if w0 < eps or w1 < eps or w2 < eps:
            continue
        depth = w0 * pa[2] + w1 * pb[2] + w2 * pc[2]
        if best_depth is None or depth < best_depth:
            best, best_depth = i, depth
            best_point = [w0 * a[k] + w1 * b[k] + w2 * c[k]
                          for k in range(3)]
    return best, best_point


def _tri_normal(tri):
    a, b, c = tri
    u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    return _norm([u[1] * v[2] - u[2] * v[1],
                  u[2] * v[0] - u[0] * v[2],
                  u[0] * v[1] - u[1] * v[0]])


def _vkey(v):
    return (round(v[0], 5), round(v[1], 5), round(v[2], 5))


def _seg_dist(p, a, b):
    ab = [b[i] - a[i] for i in range(3)]
    ap = [p[i] - a[i] for i in range(3)]
    denom = sum(c * c for c in ab) or 1e-12
    t = max(0.0, min(1.0, sum(ap[i] * ab[i] for i in range(3)) / denom))
    closest = [a[i] + t * ab[i] for i in range(3)]
    return math.sqrt(sum((p[i] - closest[i]) ** 2 for i in range(3)))


def describe_pick(tris, index, point, tol):
    """Classify a picked triangle as a planar **face** or one of its
    **edges**: the coplanar connected face is grown around the hit,
    then a click within *tol* (world units) of a face boundary snaps
    to that edge (its full straight run), otherwise the face centre.
    Returns ``{"kind", "pos", "dir", "name"}`` in the same (world)
    coordinates as *tris*."""
    normal = _tri_normal(tris[index])
    # edge map over the whole mesh: (vkey, vkey) -> [tri indices]
    edges = {}
    for i, tri in enumerate(tris):
        keys = [_vkey(v) for v in tri]
        for k in range(3):
            e = tuple(sorted((keys[k], keys[(k + 1) % 3])))
            edges.setdefault(e, []).append(i)
    normals = [_tri_normal(t) for t in tris]

    def coplanar(i):
        n = normals[i]
        return (n[0] * normal[0] + n[1] * normal[1]
                + n[2] * normal[2]) > 0.999

    # grow the connected coplanar face around the hit triangle
    face = {index}
    frontier = [index]
    while frontier:
        i = frontier.pop()
        keys = [_vkey(v) for v in tris[i]]
        for k in range(3):
            e = tuple(sorted((keys[k], keys[(k + 1) % 3])))
            for j in edges.get(e, ()):
                if j not in face and coplanar(j):
                    face.add(j)
                    frontier.append(j)
    # area-weighted centroid of the face
    total, cx, cy, cz = 0.0, 0.0, 0.0, 0.0
    for i in face:
        a, b, c = tris[i]
        u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        v = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
        area = 0.5 * math.sqrt(
            (u[1] * v[2] - u[2] * v[1]) ** 2
            + (u[2] * v[0] - u[0] * v[2]) ** 2
            + (u[0] * v[1] - u[1] * v[0]) ** 2)
        total += area
        cx += area * (a[0] + b[0] + c[0]) / 3.0
        cy += area * (a[1] + b[1] + c[1]) / 3.0
        cz += area * (a[2] + b[2] + c[2]) / 3.0
    centroid = [cx / total, cy / total, cz / total] if total > 1e-12 \
        else list(point)

    # boundary edges of the face: shared with a non-coplanar triangle
    # (a real 3D edge) or with nothing (an open border)
    boundary = []
    for e, owners in edges.items():
        ours = [i for i in owners if i in face]
        if not ours:
            continue
        others = [i for i in owners if i not in face]
        if others or len(owners) == 1:
            other_n = normals[others[0]] if others else normal
            boundary.append((e, other_n))

    hit_edge, hit_dist, hit_other = None, None, None
    for (ka, kb), other_n in boundary:
        dist = _seg_dist(point, ka, kb)
        if hit_dist is None or dist < hit_dist:
            hit_edge, hit_dist, hit_other = (ka, kb), dist, other_n
    if hit_edge is not None and hit_dist is not None and hit_dist <= tol:
        # extend the hit segment along collinear boundary neighbours so
        # the anchor sits mid-edge, not mid-facet
        def direction(a, b):
            return _norm([b[i] - a[i] for i in range(3)])
        d0 = direction(*hit_edge)
        ends = list(hit_edge)
        changed = True
        used = {tuple(sorted(hit_edge))}
        while changed:
            changed = False
            for (ka, kb), _n in boundary:
                key = tuple(sorted((ka, kb)))
                if key in used:
                    continue
                for end in (0, 1):
                    for near, far in ((ka, kb), (kb, ka)):
                        if near == ends[end]:
                            d1 = direction(near, far)
                            sign = -1.0 if end == 0 else 1.0
                            if sign * sum(d0[i] * d1[i]
                                          for i in range(3)) > 0.999:
                                ends[end] = far
                                used.add(key)
                                changed = True
        mid = [(ends[0][i] + ends[1][i]) / 2.0 for i in range(3)]
        return dict(kind="edge", pos=mid,
                    dir=_norm([normal[i] + hit_other[i]
                               for i in range(3)]),
                    name="Edge")
    return dict(kind="face", pos=centroid, dir=list(normal),
                name="Face")
