"""More Edit Mode tools (Qt-free) — the box-modelling kit for a creature
from a cube: Inset, Loop Cut, Knife, Bridge and Spin, Blender's.

Same rules as meshedit.py: points and faces as in a polyhedron node
(faces CLOCKWISE from outside), every operation returns new lists and
leaves its input alone, and the caller refuses a result meshedit.check
calls open.

* ``inset`` — the selected faces (one region, or each face on its own)
  get a border ``thickness`` mm wide, the inner part pushed ``depth``
  mm along the region's normal: the start of a horn, an eye socket, a
  spike.
* ``loop_cut`` — an edge loop round a limb: from one edge across every
  quad in turn, split at ``t`` (or ``cuts`` evenly), each quad into two.
* ``knife`` — every face the plane crosses (or only the ones given) is
  split along it; neighbours that share a cut edge take the new vertex
  too, so nothing opens.
* ``bridge`` — two selected face regions with rims of the same length
  are removed and their rims joined by a tube of quads: a handle, a
  tunnel, an arm joined to a body.
* ``spin`` — the selected faces extruded ``steps`` times, each copy
  turned about an axis (and scaled by ``taper`` overall): a curving
  horn, a tusk, a coiled tail.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from .meshedit import (_add, _copy, _cross, _dot, _norm, _round, _scale,
                       _sub, _unit, compact, extrude, face_normal,
                       selected_faces)


class EditFailed(ValueError):
    """The operation cannot be done here; the message says why."""


def _region_rim(faces, region):
    """The rim of a face region as directed edges (a, b) — the way the
    region's own faces run along it — chained into loops."""
    directed = {}
    for i in region:
        f = faces[i]
        n = len(f)
        for k in range(n):
            directed[(f[k], f[(k + 1) % n])] = i
    rim = [(a, b) for (a, b) in directed if (b, a) not in directed]
    nxt = {}
    for a, b in rim:
        if a in nxt:
            raise EditFailed("the selection's rim crosses itself — select "
                             "one simple region")
        nxt[a] = b
    loops, seen = [], set()
    for a, _b in rim:
        if a in seen:
            continue
        loop, v = [], a
        while v not in seen:
            seen.add(v)
            loop.append(v)
            v = nxt.get(v)
            if v is None:
                raise EditFailed("the selection's rim does not close")
        loops.append(loop)
    return loops


def _region_normal(points, faces, region):
    n = (0.0, 0.0, 0.0)
    for i in region:
        n = _add(n, face_normal(points, faces[i]))
    return _unit(n)


# --------------------------------------------------------------- inset

def inset(points, faces, selection, thickness, depth=0.0,
          individual=False):
    """Blender's Inset Faces (I). Returns ``(points, faces, selection)``
    with the selection on the inner faces."""
    region = selected_faces(faces, selection)
    if not region:
        raise EditFailed("select whole faces to inset (all their corners)")
    if len(region) == len(faces):
        raise EditFailed("an inset needs a rim: not every face")
    if individual and len(region) > 1:
        pts, fcs = _copy(points, faces)
        inner = []
        for i in region:
            corners = set(fcs[i])
            pts, fcs, sel = inset(pts, fcs, list(corners), thickness,
                                  depth, False)
            inner += [pts[v] for v in sel]
        keys = {tuple(p) for p in inner}
        return pts, fcs, [i for i, p in enumerate(pts) if tuple(p) in keys]
    pts, fcs = _copy(points, faces)
    normal = _region_normal(points, faces, region)
    loops = _region_rim(faces, region)
    if len(loops) != 1:
        raise EditFailed("inset one region at a time (the selection has "
                         f"{len(loops)} separate rims)")
    loop = loops[0]
    m = len(loop)
    centre = [sum(points[v][k] for v in loop) / m for k in range(3)]
    new = {}
    for j, v in enumerate(loop):
        a, b = points[loop[j - 1]], points[loop[(j + 1) % m]]
        p = points[v]
        e1, e2 = _unit(_sub(p, a)), _unit(_sub(b, p))
        # inward in the region's plane, perpendicular to each rim edge
        p1, p2 = _unit(_cross(normal, e1)), _unit(_cross(normal, e2))
        if _dot(p1, _sub(centre, p)) < 0:
            p1, p2 = _scale(p1, -1.0), _scale(p2, -1.0)
        d = _unit(_add(p1, p2))
        cos = max(_dot(d, p1), 0.25)
        reach = min(thickness / cos, 0.95 * _norm(_sub(centre, p)))
        new[v] = len(pts)
        pts.append(_round(_add(_add(p, _scale(d, reach)),
                               _scale(normal, depth))))
    inner = set(v for i in region for v in faces[i]) - set(loop)
    for v in inner:
        pts[v] = _round(_add(points[v], _scale(normal, depth)))
    for i in region:
        fcs[i] = [new.get(v, v) for v in faces[i]]
    for j, v in enumerate(loop):
        w = loop[(j + 1) % m]
        fcs.append([v, w, new[w], new[v]])
    sel = [new[v] for v in loop] + sorted(inner)
    return compact(pts, fcs, sel)


# ------------------------------------------------------------ loop cut

def _edge_faces(faces):
    out = {}
    for i, f in enumerate(faces):
        n = len(f)
        for k in range(n):
            a, b = f[k], f[(k + 1) % n]
            out.setdefault(frozenset((a, b)), []).append(i)
    return out


def edge_ring(faces, a, b):
    """The quads an edge loop through edge a-b crosses: ``[(face,
    entering edge (u, v), opposite edge (u', v'))]`` with u-u' and v-v'
    the quad's sides, and every ring edge oriented the same way."""
    by_edge = _edge_faces(faces)
    if frozenset((a, b)) not in by_edge:
        raise EditFailed(f"{a}-{b} is not an edge")
    ring, used = [], set()

    def walk(u, v, face_list):
        while True:
            nxt = [f for f in face_list if f not in used
                   and len(faces[f]) == 4]
            if not nxt:
                return
            f = nxt[0]
            used.add(f)
            q = faces[f]
            k = next(i for i in range(4)
                     if {q[i], q[(i + 1) % 4]} == {u, v})
            if q[k] == u:            # q = u, v, v', u'
                uu, vv = q[(k + 3) % 4], q[(k + 2) % 4]
            else:                    # q = v, u, u', v'
                uu, vv = q[(k + 2) % 4], q[(k + 3) % 4]
            ring.append((f, (u, v), (uu, vv)))
            if frozenset((uu, vv)) == frozenset((a, b)):
                return
            u, v = uu, vv
            face_list = by_edge.get(frozenset((u, v)), [])

    start = by_edge[frozenset((a, b))]
    walk(a, b, start[:1])
    if len(start) > 1 and (not ring or start[1] not in used):
        walk(a, b, start[1:])
    if not ring:
        raise EditFailed("no quad on that edge — a loop cut runs across "
                         "quads")
    return ring


def loop_cut(points, faces, a, b, t=0.5, cuts=1):
    """Blender's Loop Cut (Ctrl+R) through edge a-b. Returns ``(points,
    faces, selection)`` with the new loop(s) selected."""
    ring = edge_ring(faces, a, b)
    cuts = max(1, int(cuts))
    ts = [t] if cuts == 1 else [(k + 1) / (cuts + 1) for k in range(cuts)]
    pts, fcs = _copy(points, faces)
    mids = {}

    def mid(u, v):
        key = (u, v)
        if key not in mids:
            if (v, u) in mids:
                return mids[(v, u)][::-1]
            out = []
            for tk in ts:
                out.append(len(pts))
                pts.append(_round(_add(points[u], _scale(
                    _sub(points[v], points[u]), tk))))
            mids[key] = out
        return mids[key]

    split = {}
    for f, (u, v), (uu, vv) in ring:
        m1, m2 = mid(u, v), mid(uu, vv)
        q = faces[f]
        k = next(i for i in range(4) if {q[i], q[(i + 1) % 4]} == {u, v})
        flip = q[k] != u
        side_u = [u] + m1 + [v]
        side_uu = [uu] + m2 + [vv]
        pieces = []
        for s in range(len(side_u) - 1):
            a0, a1 = side_u[s], side_u[s + 1]
            b0, b1 = side_uu[s], side_uu[s + 1]
            # keep the quad's own winding
            pieces.append([a1, a0, b0, b1] if flip else [a0, a1, b1, b0])
        split[f] = pieces
    out = []
    for i, face in enumerate(fcs):
        if i in split:
            out.extend(split[i])
            continue
        ring_face = []                  # a triangle at the loop's end
        n = len(face)
        for k in range(n):
            u, v = face[k], face[(k + 1) % n]
            ring_face.append(u)
            if (u, v) in mids:
                ring_face += mids[(u, v)]
            elif (v, u) in mids:
                ring_face += mids[(v, u)][::-1]
        out.append(ring_face)
    sel = sorted({m for ms in mids.values() for m in ms})
    return pts, out, sel


# --------------------------------------------------------------- knife

def knife(points, faces, point, normal, only=None):
    """Split the faces the plane (through *point*, along *normal*)
    crosses — all, or only the face indices in *only*. Returns
    ``(points, faces, selection)`` with the cut's vertices selected."""
    nrm = _unit(normal)
    if _norm(nrm) < 0.5:
        raise EditFailed("the knife needs a direction")
    eps = 1e-6
    dist = [_dot(_sub(p, point), nrm) for p in points]
    pts, _ = _copy(points, [])
    allowed = set(range(len(faces))) if only is None else set(only)
    cut_edge = {}
    for i in allowed:
        f = faces[i]
        n = len(f)
        for k in range(n):
            u, v = f[k], f[(k + 1) % n]
            du, dv = dist[u], dist[v]
            if (du > eps and dv < -eps) or (du < -eps and dv > eps):
                key = frozenset((u, v))
                if key not in cut_edge:
                    t = du / (du - dv)
                    cut_edge[key] = len(pts)
                    pts.append(_round(_add(points[u], _scale(
                        _sub(points[v], points[u]), t))))
    out, made = [], set(cut_edge.values())
    split = 0
    for i, f in enumerate(faces):
        ring = []
        n = len(f)
        for k in range(n):
            u, v = f[k], f[(k + 1) % n]
            ring.append(u)
            c = cut_edge.get(frozenset((u, v)))
            if c is not None:
                ring.append(c)
        if i not in allowed:
            out.append(ring)
            continue
        on = [j for j, v in enumerate(ring)
              if v in made or abs(dist[v] if v < len(dist) else 0) <= eps]
        if len(on) == 2 and (on[1] - on[0]) not in (1, len(ring) - 1):
            j0, j1 = on
            out.append(ring[j0:j1 + 1])
            out.append(ring[j1:] + ring[:j0 + 1])
            split += 1
            made.update((ring[j0], ring[j1]))
        else:
            out.append(ring)
    if not split:
        raise EditFailed("the knife crosses no face there")
    return pts, out, sorted(made)


# -------------------------------------------------------------- bridge

def bridge(points, faces, selection):
    """Blender's Bridge Edge Loops between two face regions: both are
    removed and their rims joined by quads. Returns ``(points, faces,
    selection)`` with the new tube's vertices selected."""
    region = set(selected_faces(faces, selection))
    if not region:
        raise EditFailed("select two face regions (all their corners)")
    # split the selected faces into two connected regions
    by_edge = _edge_faces(faces)
    groups, seen = [], set()
    for start in sorted(region):
        if start in seen:
            continue
        group, todo = [], [start]
        seen.add(start)
        while todo:
            f = todo.pop()
            group.append(f)
            n = len(faces[f])
            for k in range(n):
                key = frozenset((faces[f][k], faces[f][(k + 1) % n]))
                for g in by_edge[key]:
                    if g in region and g not in seen:
                        seen.add(g)
                        todo.append(g)
        groups.append(group)
    if len(groups) != 2:
        raise EditFailed(f"select exactly two separate face regions (the "
                         f"selection holds {len(groups)})")
    rims = []
    for g in groups:
        loops = _region_rim(faces, g)
        if len(loops) != 1:
            raise EditFailed("each region needs one simple rim")
        rims.append(loops[0])
    a, b = rims
    if len(a) != len(b):
        raise EditFailed(f"the rims have {len(a)} and {len(b)} edges — "
                         "bridge needs them equal (subdivide or loop cut "
                         "one side)")
    m = len(a)
    # the rims run opposite ways round the tube: walk b backwards and
    # pick the turn that pairs the nearest vertices
    rb = b[::-1]
    best, shift = None, 0
    for s in range(m):
        cost = sum(_norm(_sub(points[a[i]], points[rb[(i + s) % m]]))
                   for i in range(m))
        if best is None or cost < best:
            best, shift = cost, s
    rb = [rb[(i + shift) % m] for i in range(m)]
    keep = [f for i, f in enumerate(faces) if i not in region]
    tube = []
    for i in range(m):
        j = (i + 1) % m
        # region faces ran a[i] -> a[j]; the tube runs its rim back
        tube.append([a[j], a[i], rb[i], rb[j]])
    from .meshedit import check
    pts, fcs, sel = compact(points, keep + tube, a + b)
    if check(pts, fcs) is not None:
        tube = [f[::-1] for f in tube]
        pts, fcs, sel = compact(points, keep + tube, a + b)
    return pts, fcs, sel


# ---------------------------------------------------------------- spin

def _rotate(p, origin, axis, angle):
    """*p* turned *angle* degrees about the line through *origin*."""
    k = _unit(axis)
    v = _sub(p, origin)
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    rot = _add(_add(_scale(v, c), _scale(_cross(k, v), s)),
               _scale(k, _dot(k, v) * (1.0 - c)))
    return _add(origin, rot)


def spin(points, faces, selection, origin, axis, angle=90.0, steps=8,
         taper=1.0):
    """Blender's Spin on the selected faces: extruded *steps* times, each
    copy turned *angle*/steps degrees about the axis through *origin*
    and scaled about its own centre so the last is *taper* times the
    first. Returns ``(points, faces, selection)``."""
    steps = max(1, int(steps))
    if _norm(_unit(axis)) < 0.5:
        raise EditFailed("spin needs an axis direction")
    pts, fcs = _copy(points, faces)
    sel = list(selection)
    step_scale = float(taper) ** (1.0 / steps) if taper > 0 else 1.0
    for _ in range(steps):
        out = extrude(pts, fcs, sel, 0.0)
        if out is None:
            raise EditFailed("select whole faces to spin (all their "
                             "corners), not every face")
        pts, fcs, sel, _normal = out
        n = float(len(sel))
        centre = [sum(pts[v][k] for v in sel) / n for k in range(3)]
        for v in sel:
            p = _add(centre, _scale(_sub(pts[v], centre), step_scale))
            pts[v] = list(_round(_rotate(p, origin, axis, angle / steps)))
    return pts, fcs, sel
