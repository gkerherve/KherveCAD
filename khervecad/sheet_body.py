"""Sheet metal bodies (2026-10-27, the user: "SolidCraft can do sheet
metal and has a whole tab on the ribbon about it — introduce the same").

SolidCraft's SHEET METAL tab, in our own Python: a body is a FLAT
OUTLINE (the base flange, or a contour of bends) plus, on its edges,
flanges, hems and folds, with one rule for thickness, bend radius and
K-factor. Everything is a panel — a flat polygon in a 3D frame, the
sheet from its bottom face (n = 0) to its top (n = t) — and every bend
joins a panel's edge to the next panel through a cylindrical strip, so
the folded part and the flat pattern come from the SAME frames:

* a flange on edge E of panel P: its height is measured to the OUTER
  VIRTUAL SHARP (so a 100 x 60 outline with four 20 mm flanges is a box
  100 x 60 x 20 outside); the parent's edge is set back by
  (r + t) tan(angle / 2) and the flange's flat leg is height - that;
  past 150 degrees (a hem) the bend starts on the edge itself;
* a hem is a flange bent 180 degrees with an inner radius half the hem
  gap;
* a fold bends the base along a line, the outline being the BLANK: the
  bend allowance is centred on the line;
* the flat pattern unrolls every bend by its allowance
  angle x (r + K t), and lists the bend lines (the bend table).

The node bakes like the other kit nodes (`kcad_sheet_body(..., points,
faces)`): the polyhedron is the part, so OpenSCAD draws exactly what
the preview shows, and the parameters re-import losslessly.

Panel numbers (for a flange's parent): 0 the base, then the contour's
segments, then each flange in order. Edge numbers: on the base, the
outline's edges (edge i runs from point i to point i + 1; on a contour
base 0 = the side by the start, 1 = the far end, 2 = the other side);
on a flange 0 = the bend, 1 and 3 its sides, 2 the far edge.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from . import bakedkit

KIND = "sheet_body"
LABEL = "Sheet metal body"
HEM_ANGLE = 150.0          # past it a bend starts on the edge itself
FOLD_TAG = "fold"

_DEFAULTS = dict(
    outline=[[0.0, 0.0], [100.0, 0.0], [100.0, 60.0], [0.0, 60.0]],
    contour=[], width=60.0,
    thickness=2.0, radius=2.0, k_factor=0.44, hem_gap=1.0, rule="",
    flanges=[], hems=[], folds=[], perforate=[], flat=False)


# ======================================================== small vectors
def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _unit(a):
    n = math.sqrt(_dot(a, a)) or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


def _area2(poly):
    return sum(p[0] * q[1] - q[0] * p[1]
               for p, q in zip(poly, poly[1:] + poly[:1])) / 2


# ============================================================ the panels
class Frame:
    """A panel's frame: origin, in-plane U and V, normal N (= U x V)."""

    def __init__(self, o, u, v, n):
        self.o, self.u, self.v, self.n = o, u, v, n

    def at(self, p, d=0.0):
        """(u, v) in the panel, d along the normal -> world."""
        return _add(_add(_add(self.o, _mul(self.u, p[0])),
                         _mul(self.v, p[1])), _mul(self.n, d))


class Panel:
    """A flat piece: a CCW polygon with one tag per edge (edge i from
    point i to i + 1), in a 3D frame and in the flat pattern's 2D one."""

    def __init__(self, poly, tags, frame, flat):
        self.poly, self.tags = list(poly), list(tags)
        self.frame = frame                   # 3D Frame
        self.flat = flat                     # 2D (o, u, v)

    def edge(self, tag):
        """The longest edge carrying *tag*: (a, b) in panel coordinates."""
        best = None
        n = len(self.poly)
        for i in range(n):
            if self.tags[i] != tag:
                continue
            a, b = self.poly[i], self.poly[(i + 1) % n]
            ln = math.hypot(b[0] - a[0], b[1] - a[1])
            if ln > 1e-9 and (best is None or ln > best[2]):
                best = (a, b, ln)
        return best

    def flat_point(self, p):
        o, u, v = self.flat
        return (o[0] + u[0] * p[0] + v[0] * p[1],
                o[1] + u[1] * p[0] + v[1] * p[1])


def _line_meet(p1, d1, p2, d2):
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-12:
        return None
    t = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / den
    return (p1[0] + d1[0] * t, p1[1] + d1[1] * t)


def set_back(poly, tags, amounts):
    """Move each edge whose tag is in *amounts* inward by that much,
    every corner re-found where the neighbouring edges' lines meet."""
    n = len(poly)
    if not any(amounts.get(t) for t in tags):
        return list(poly)
    lines = []
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        d = (b[0] - a[0], b[1] - a[1])
        ln = math.hypot(*d) or 1.0
        s = amounts.get(tags[i], 0.0)
        inward = (-d[1] / ln, d[0] / ln)          # left of a CCW edge
        lines.append(((a[0] + inward[0] * s, a[1] + inward[1] * s), d))
    out = []
    for i in range(n):
        prev, cur = lines[i - 1], lines[i]
        hit = _line_meet(prev[0], prev[1], cur[0], cur[1])
        out.append(hit if hit is not None else cur[0])
    return out


def clip(poly, tags, point, normal, new_tag):
    """The part of the polygon where (q - point) . normal >= 0
    (Sutherland-Hodgman), the cut edge tagged *new_tag*."""
    def side(q):
        return (q[0] - point[0]) * normal[0] + (q[1] - point[1]) * normal[1]
    out, out_tags = [], []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        sa, sb = side(a), side(b)
        if sa >= 0:
            out.append(a)
            out_tags.append(tags[i])
        if (sa >= 0) != (sb >= 0):
            t = sa / (sa - sb)
            q = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            out.append(q)
            out_tags.append(tags[i] if sa < 0 else new_tag)
    # the edge leaving a point that lies on the cut and heading along it
    # is the cut edge: fix the tag of each crossing that starts it
    fixed = []
    m = len(out)
    for i in range(m):
        a, b = out[i], out[(i + 1) % m]
        if abs(side(a)) < 1e-9 and abs(side(b)) < 1e-9:
            fixed.append(new_tag)
        else:
            fixed.append(out_tags[i])
    return out, fixed


def bend_child(parent, a, b, angle, r, t, offset=0.0):
    """The frame of a panel bent off the parent's edge a -> b by
    *angle* degrees (positive toward the parent's top), inner radius r.
    The child's u runs back along the edge from a (u = -distance from
    a), its v away from the bend. *offset* moves the bend start away
    from the edge (in the flat, too). Returns (Frame, flat (o, u, v),
    axis point, e, w)."""
    f = parent.frame
    a3, b3 = f.at(a), f.at(b)
    e = _unit(_sub(b3, a3))
    w = _cross(e, f.n)                        # outward, in the plane
    a3 = _add(a3, _mul(w, offset))
    th = math.radians(angle)
    c = t + r if angle > 0 else -r
    axis = _add(a3, _mul(f.n, c))
    v = _add(_mul(w, math.cos(th)), _mul(f.n, math.sin(th)))
    n = _sub(_mul(f.n, math.cos(th)), _mul(w, math.sin(th)))
    o = _sub(axis, _mul(n, c))
    frame = Frame(o, _mul(e, -1.0), v, n)
    # flat: the same edge in the pattern, one bend allowance further out
    fa, fb = parent.flat_point(a), parent.flat_point(b)
    ln = math.hypot(fb[0] - fa[0], fb[1] - fa[1]) or 1.0
    fe = ((fb[0] - fa[0]) / ln, (fb[1] - fa[1]) / ln)
    fw = (fe[1], -fe[0])
    return frame, fe, fw, fa, axis, e, w


# ============================================================ the build
class Body:
    """Everything one sheet metal body is made of."""

    def __init__(self):
        self.panels = []            # Panel, by number (None: not addressable)
        self.extra = []             # panels with no number (fold sides, hems)
        self.bends = []             # dicts: the bend table + their strips
        self.t = 2.0
        self.k = 0.44
        self.errors = []

    def all_panels(self):
        return [p for p in self.panels if p is not None] + self.extra


def _num(v, env, default=0.0):
    from . import mesh
    return mesh.rv(v, env, default)


def _setback(angle, r, t):
    a = abs(angle)
    if a >= HEM_ANGLE or a < 1e-9:
        return 0.0
    return (r + t) * math.tan(math.radians(a) / 2)


def _allowance(angle, r, t, k):
    return math.radians(abs(angle)) * (r + k * t)


def build(params, env=None):
    """The panels, bends and errors of a body from its parameters."""
    env = env or {}
    body = Body()
    t = max(_num(params.get("thickness", 2.0), env, 2.0), 1e-3)
    r0 = max(_num(params.get("radius", 2.0), env, 2.0), 0.0)
    k = _num(params.get("k_factor", 0.44), env, 0.44)
    gap = max(_num(params.get("hem_gap", 1.0), env, 1.0), 0.0)
    body.t, body.k = t, k

    def rows(key, width):
        out = []
        for row in params.get(key) or []:
            if isinstance(row, (list, tuple)) and len(row) >= width:
                out.append([_num(v, env, 0.0) for v in row])
        return out

    # ---- every bend as a flange row: [parent, edge, height, angle, r,
    #      inset_a, inset_b, kind, numbered]
    specs = []
    contour = rows("contour", 2)
    if len(contour) >= 2:
        width = max(_num(params.get("width", 60.0), env, 60.0), 1e-3)
        pts = [tuple(p[:2]) for p in contour]
        segs = [math.hypot(q[0] - p[0], q[1] - p[1])
                for p, q in zip(pts, pts[1:])]
        dirs = [math.degrees(math.atan2(q[1] - p[1], q[0] - p[0]))
                for p, q in zip(pts, pts[1:])]
        base_poly = [(0.0, 0.0), (segs[0], 0.0), (segs[0], width),
                     (0.0, width)]
        base_tags = [0, 1, 2, 3]
        start = pts[0]
        heading = math.radians(dirs[0])
        # the base lies along the first segment, in the XZ plane's
        # direction: x along it, y across the contour's width
        frame = Frame((start[0], 0.0, start[1]),
                      (math.cos(heading), 0.0, math.sin(heading)),
                      (0.0, 1.0, 0.0),
                      (math.sin(heading), 0.0, -math.cos(heading)))
        frame.n = _cross(frame.u, frame.v)
        parent_edge = 1
        for i in range(1, len(segs)):
            turn = dirs[i] - dirs[i - 1]
            turn = (turn + 180) % 360 - 180
            # a counter-clockwise turn in (x, z) bends toward +n
            specs.append([i - 1, parent_edge, segs[i], turn, r0, 0.0, 0.0, "contour", True])
            parent_edge = 2
    else:
        outline = [tuple(p[:2]) for p in rows("outline", 2)]
        if len(outline) < 3:
            body.errors.append("the outline needs three points or more")
            return body
        if _area2(outline) < 0:
            outline.reverse()
        base_poly = outline
        base_tags = list(range(len(outline)))
        frame = Frame((0.0, 0.0, 0.0), (1, 0, 0), (0, 1, 0), (0, 0, 1))
    for row in rows("flanges", 4):
        row = row + [0.0] * (7 - len(row))
        specs.append([int(row[0]), int(row[1]), row[2], row[3],
                      row[4] if row[4] > 0 else r0, row[5], row[6],
                      "flange", True])
    for row in rows("hems", 3):
        flip = len(row) > 3 and row[3] >= 0.5
        specs.append([int(row[0]), int(row[1]), row[2],
                      -180.0 if flip else 180.0, gap / 2, 0.0, 0.0,
                      "hem", False])

    # ---- the base, folds clipped out of it
    base = Panel(base_poly, base_tags, frame,
                 ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)))
    folds = rows("folds", 5)
    fold_sides = []
    for j, row in enumerate(folds):
        x1, y1, x2, y2, ang = row[:5]
        r = row[5] if len(row) > 5 and row[5] > 0 else r0
        d = (x2 - x1, y2 - y1)
        ln = math.hypot(*d)
        if ln < 1e-9 or abs(ang) < 1e-9:
            continue
        nrm = (-d[1] / ln, d[0] / ln)
        ba = _allowance(ang, r, t, k)
        p = (x1, y1)
        left, lt = clip(base.poly, base.tags, p, nrm, FOLD_TAG + str(j))
        right, rt = clip(base.poly, base.tags, p, (-nrm[0], -nrm[1]),
                         FOLD_TAG + str(j))
        if not left or not right:
            body.errors.append(f"fold {j + 1}: its line misses the sheet")
            continue
        keep_n = nrm if abs(_area2(left)) >= abs(_area2(right)) \
            else (-nrm[0], -nrm[1])
        # the moving side starts half an allowance past the line
        q2 = (p[0] - keep_n[0] * ba / 2, p[1] - keep_n[1] * ba / 2)
        move_poly, _mt = clip(base.poly, base.tags, q2,
                              (-keep_n[0], -keep_n[1]), FOLD_TAG + str(j))
        if len(move_poly) < 3:
            body.errors.append(f"fold {j + 1}: nothing moves")
            continue
        # the fixed side ends half an allowance short of the line
        q = (p[0] + keep_n[0] * ba / 2, p[1] + keep_n[1] * ba / 2)
        poly, tags = clip(base.poly, base.tags, q, keep_n,
                          FOLD_TAG + str(j))
        if len(poly) < 3:
            body.errors.append(f"fold {j + 1}: nothing stays fixed")
            continue
        base.poly, base.tags = poly, tags
        fold_sides.append((j, ang, r, ba, move_poly, keep_n, p))
    body.panels.append(base)

    # ---- set-backs: every bend on an edge pulls that edge in
    trims = {}
    for spec in specs:
        parent, edge, _h, ang, r = spec[:5]
        if spec[7] == "contour":
            continue
        trims.setdefault(parent, {})
        s = _setback(ang, r, t)
        trims[parent][edge] = max(trims[parent].get(edge, 0.0), s)
    # contour bends: the segment lengths are virtual sharps too
    csb = {}
    for i, spec in enumerate(specs):
        if spec[7] == "contour":
            s = _setback(spec[3], spec[4], t)
            csb[i] = s

    def trim(index):
        panel = body.panels[index]
        amounts = dict(trims.get(index, {}))
        if index == 0 and csb:
            amounts[1] = amounts.get(1, 0.0) + csb.get(0, 0.0)
        panel.poly = set_back(panel.poly, panel.tags, amounts)

    trim(0)
    _fold_panels(body, fold_sides, t)

    for i, spec in enumerate(specs):
        parent_i, edge, height, ang, r, ia, ib, kind, numbered = spec
        parent = body.panels[parent_i] if 0 <= parent_i < len(body.panels) \
            else None
        if parent is None:
            body.errors.append(f"{kind} {i + 1}: panel {parent_i} does "
                               "not exist (yet)")
            if numbered:
                body.panels.append(None)
            continue
        found = parent.edge(edge)
        if found is None:
            body.errors.append(f"{kind} {i + 1}: panel {parent_i} has "
                               f"no edge {edge}")
            if numbered:
                body.panels.append(None)
            continue
        a, b, ln = found
        s_own = _setback(ang, r, t)
        if kind == "contour":
            leg = height - s_own - csb.get(i + 1, 0.0)
        elif kind == "hem":
            leg = height - r - t
        else:
            leg = height - (s_own if abs(ang) < HEM_ANGLE else r + t)
        lo, hi = ia, ln - ib
        if leg <= 1e-6 or hi - lo <= 1e-6:
            body.errors.append(f"{kind} {i + 1}: too short for its bend "
                               f"(radius {r:g}, thickness {t:g})")
            if numbered:
                body.panels.append(None)
            continue
        frame, fe, fw, fa, axis, e, w = bend_child(parent, a, b, ang, r, t)
        ba = _allowance(ang, r, t, k)
        flat_o = (fa[0] + fw[0] * ba, fa[1] + fw[1] * ba)
        poly = [(-hi, 0.0), (-lo, 0.0), (-lo, leg), (-hi, leg)]
        tags = [0, 1, 2, 3]
        child = Panel(poly, tags, frame, (flat_o, (-fe[0], -fe[1]), fw))
        body.bends.append(dict(
            kind=kind, parent=parent_i, edge=edge, angle=ang, radius=r,
            length=hi - lo, allowance=ba, frame=parent.frame, e=e, w=w,
            axis=axis, a=_add(parent.frame.at(a), _mul(e, lo)),
            span=hi - lo, flat=(fa, fe, fw, lo, hi)))
        if numbered:
            body.panels.append(child)
            if kind == "flange" or kind == "contour":
                trim(len(body.panels) - 1)
        else:
            body.extra.append(child)
    return body


def _fold_panels(body, fold_sides, t):
    """The moving side of every fold, as a panel bent off the base."""
    base = body.panels[0]
    for j, ang, r, ba, move_poly, keep_n, p in fold_sides:
        # the bend edge runs along the line with w = e x N (in 2D
        # (e_y, -e_x)) pointing at the moving side, -keep_n
        e2 = (keep_n[1], -keep_n[0])
        start = (p[0] + keep_n[0] * ba / 2, p[1] + keep_n[1] * ba / 2)
        a = start
        b = (start[0] + e2[0], start[1] + e2[1])
        frame, fe, fw, fa, axis, e, w = bend_child(base, a, b, ang, r, t)
        # the moving polygon in the child's (u, v): u = -along, v = past
        # the bend's far side (the line + half an allowance)
        poly = []
        for q in move_poly:
            dx, dy = q[0] - start[0], q[1] - start[1]
            along = dx * e2[0] + dy * e2[1]
            out = dx * -keep_n[0] + dy * -keep_n[1] - ba
            poly.append((-along, max(out, 0.0)))
        if _area2(poly) < 0:
            poly.reverse()
        flat_o = (fa[0] + fw[0] * ba, fa[1] + fw[1] * ba)
        child = Panel(poly, [FOLD_TAG] * len(poly), frame,
                      (flat_o, (-fe[0], -fe[1]), fw))
        body.extra.append(child)
        # the bend spans the fixed side's cut edge
        found = base.edge(FOLD_TAG + str(j))
        if found is None:
            continue
        ea, eb, _ln = found
        da = (ea[0] - start[0]) * e2[0] + (ea[1] - start[1]) * e2[1]
        db = (eb[0] - start[0]) * e2[0] + (eb[1] - start[1]) * e2[1]
        lo, hi = min(da, db), max(da, db)
        body.bends.append(dict(
            kind="fold", parent=0, edge=FOLD_TAG + str(j), angle=ang,
            radius=r, length=hi - lo, allowance=ba, frame=base.frame, e=e,
            w=w, axis=axis, a=_add(base.frame.at(a), _mul(e, lo)),
            span=hi - lo, flat=(fa, fe, fw, lo, hi)))


# ========================================================= 3D triangles
def _closed(tris):
    """Turn a closed piece outward (positive signed volume)."""
    vol = sum(_dot(a, _cross(b, c)) for a, b, c in tris)
    if vol < 0:
        return [(a, c, b) for a, b, c in tris]
    return tris


def panel_tris(panel, t):
    from . import mesh
    poly = panel.poly
    if len(poly) < 3 or abs(_area2(poly)) < 1e-9:
        return []
    f = panel.frame
    out = []
    for tri in mesh.triangulate(poly):
        a, b, c = (f.at(p) for p in tri)
        out.append((a, c, b))                            # bottom: -n
        a, b, c = (f.at(p, t) for p in tri)
        out.append((a, b, c))                            # top: +n
    n = len(poly)
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        p0, q0, p1, q1 = f.at(p), f.at(q), f.at(p, t), f.at(q, t)
        out.append((p0, q0, q1))
        out.append((p0, q1, p1))
    return _closed(out)


def bend_tris(bend, t, segments):
    """The strip of one bend: a cylindrical shell sector."""
    f, e, w = bend["frame"], bend["e"], bend["w"]
    axis, a0, span = bend["axis"], bend["a"], bend["span"]
    th = math.radians(bend["angle"])
    n = max(2, int(math.ceil(abs(bend["angle"]) / 360.0 * segments)))

    def rot(p, phi):
        v = _sub(p, axis)
        al, be, ga = _dot(v, e), _dot(v, w), _dot(v, f.n)
        c, s = math.cos(phi), math.sin(phi)
        return _add(axis, _add(_add(_mul(e, al),
                                    _mul(_add(_mul(w, c), _mul(f.n, s)),
                                         be)),
                               _mul(_sub(_mul(f.n, c), _mul(w, s)), ga)))
    ends = (a0, _add(a0, _mul(e, span)))
    rings = []
    for k in range(n + 1):
        phi = th * k / n
        rings.append([rot(p, phi) for p in
                      (ends[0], ends[1], _add(ends[1], _mul(f.n, t)),
                       _add(ends[0], _mul(f.n, t)))])
    out = []
    for k in range(n):
        r0, r1 = rings[k], rings[k + 1]
        for i in range(4):
            j = (i + 1) % 4
            out.append((r0[i], r1[i], r1[j]))
            out.append((r0[i], r1[j], r0[j]))
    # the caps run each ring edge the other way round from the sides
    for ring, flip in ((rings[0], False), (rings[-1], True)):
        a, b, c, d = ring
        if flip:
            out += [(a, c, b), (a, d, c)]
        else:
            out += [(a, b, c), (a, c, d)]
    return _closed(out)


def _union(pieces):
    """One solid from the touching pieces (Manifold), else all of them."""
    from . import csg
    if not csg.available():
        return [t for p in pieces for t in p]
    import numpy as np
    m = csg._m
    solids = []
    for tris in pieces:
        if not tris:
            continue
        pts, index, faces = [], {}, []
        for tri in tris:
            row = []
            for v in tri:
                key = (round(v[0], 6), round(v[1], 6), round(v[2], 6))
                if key not in index:
                    index[key] = len(pts)
                    pts.append(key)
                row.append(index[key])
            if len(set(row)) == 3:
                faces.append(row)
        solid = m.Manifold(m.Mesh(
            vert_properties=np.asarray(pts, dtype=np.float32),
            tri_verts=np.asarray(faces, dtype=np.uint32)))
        if solid.status() != m.Error.NoError or solid.is_empty():
            return [t for p in pieces for t in p]
        solids.append(solid)
    if not solids:
        return []
    whole = m.Manifold.batch_boolean(solids, m.OpType.Add) \
        if len(solids) > 1 else solids[0]
    return csg.to_triangles(whole)


def folded_tris(body, segments=32):
    pieces = [panel_tris(p, body.t) for p in body.all_panels()]
    pieces += [bend_tris(b, body.t, segments) for b in body.bends]
    return _union(pieces)


# ========================================================= flat pattern
def flat_pattern(body, perforate=None):
    """The blank: outline loops (unioned when Manifold is there), bend
    lines with their table, perforation holes and the size."""
    loops = []
    for p in body.all_panels():
        if len(p.poly) >= 3:
            loops.append([p.flat_point(q) for q in p.poly])
    table, strips = [], []
    for i, b in enumerate(body.bends):
        fa, fe, fw, lo, hi = b["flat"]
        ba = b["allowance"]
        p0 = (fa[0] + fe[0] * lo, fa[1] + fe[1] * lo)
        p1 = (fa[0] + fe[0] * hi, fa[1] + fe[1] * hi)
        strip = [p0, p1, (p1[0] + fw[0] * ba, p1[1] + fw[1] * ba),
                 (p0[0] + fw[0] * ba, p0[1] + fw[1] * ba)]
        if _area2(strip) < 0:
            strip.reverse()
        strips.append(strip)
        mid = ba / 2
        line = ((p0[0] + fw[0] * mid, p0[1] + fw[1] * mid),
                (p1[0] + fw[0] * mid, p1[1] + fw[1] * mid))
        table.append(dict(
            bend=i + 1, kind=b["kind"], angle_deg=round(b["angle"], 4),
            included_angle_deg=round(180 - abs(b["angle"]), 4),
            radius=round(b["radius"], 4), length=round(b["length"], 4),
            allowance=round(ba, 4),
            direction="up" if b["angle"] > 0 else "down",
            start=[round(c, 4) for c in line[0]],
            end=[round(c, 4) for c in line[1]], line=line))
    outlines = loops + strips
    holes = []
    from . import csg
    if csg.available():
        m = csg._m
        region = m.CrossSection([[list(q) for q in lp] for lp in outlines
                                 if abs(_area2(lp)) > 1e-12],
                                m.FillRule.Positive)
        polys = [list(map(tuple, lp)) for lp in region.to_polygons()]
        if perforate:
            holes = _perforation(m, region, strips, perforate)
        outlines = polys
    outlines = [[(float(x), float(y)) for x, y in lp] for lp in outlines]
    xs = [q[0] for lp in outlines for q in lp] or [0.0]
    ys = [q[1] for lp in outlines for q in lp] or [0.0]
    return dict(outlines=outlines, bend_table=table, holes=holes,
                thickness=body.t, k_factor=body.k,
                width=max(xs) - min(xs), height=max(ys) - min(ys),
                min=(min(xs), min(ys)))


def _inside(loops, x, y):
    hit = False
    for lp in loops:
        n = len(lp)
        for i in range(n):
            (ax, ay), (bx, by) = lp[i], lp[(i + 1) % n]
            if (ay > y) != (by > y) and \
                    x < ax + (y - ay) * (bx - ax) / (by - ay):
                hit = not hit
    return hit


def _perforation(m, region, strips, spec):
    """Hole centres over the flat sheet: *spec* = [diameter, pitch,
    margin (0 = the diameter), pattern 0 staggered 60 deg / 1 square],
    kept the margin from every edge and every bend."""
    d, pitch = spec[0], spec[1]
    margin = spec[2] if len(spec) > 2 and spec[2] > 0 else d
    square = len(spec) > 3 and spec[3] >= 0.5
    if d <= 0 or pitch <= d:
        return []
    keep = margin + d / 2
    area = region.offset(-keep, m.JoinType.Miter)
    if strips:
        bends = m.CrossSection([[list(q) for q in s] for s in strips],
                               m.FillRule.Positive).offset(
                                   keep, m.JoinType.Miter)
        area = area - bends
    loops = [list(map(tuple, lp)) for lp in area.to_polygons()]
    if not loops:
        return []
    xs = [q[0] for lp in loops for q in lp]
    ys = [q[1] for lp in loops for q in lp]
    dy = pitch if square else pitch * math.sqrt(3) / 2
    out = []
    j = 0
    y = min(ys)
    while y <= max(ys) + 1e-9 and len(out) < 20000:
        x = min(xs) + (0.0 if square or j % 2 == 0 else pitch / 2)
        while x <= max(xs) + 1e-9:
            if _inside(loops, x, y):
                out.append((round(x, 4), round(y, 4), d))
            x += pitch
        y += dy
        j += 1
    return out


def flat_tris(pattern, t, segments=24):
    """The flat blank as a solid (holes cut when Manifold is there)."""
    from . import csg
    if csg.available():
        m = csg._m
        sec = m.CrossSection([[list(q) for q in lp]
                              for lp in pattern["outlines"]],
                             m.FillRule.Positive)
        if pattern["holes"]:
            circles = [m.CrossSection.circle(h[2] / 2, 12).translate(
                (h[0], h[1])) for h in pattern["holes"]]
            sec = sec - m.CrossSection.batch_boolean(circles, m.OpType.Add)
        return csg.to_triangles(m.Manifold.extrude(sec, t))
    out = []
    for lp in pattern["outlines"]:
        frame = Frame((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1))
        out += panel_tris(Panel(lp if _area2(lp) > 0 else lp[::-1],
                                [0] * len(lp), frame, None), t)
    return out


# ============================================================== exports
def bend_table_csv(pattern) -> str:
    rows = ["bend,kind,direction,angle_deg,included_angle_deg,radius_mm,"
            "length_mm,allowance_mm,start_x,start_y,end_x,end_y"]
    for b in pattern["bend_table"]:
        rows.append(",".join(str(v) for v in (
            b["bend"], b["kind"], b["direction"], b["angle_deg"],
            b["included_angle_deg"], b["radius"], b["length"],
            b["allowance"], *b["start"], *b["end"])))
    return "\n".join(rows) + "\n"


def flat_dxf(pattern, path, bend_notes=True, note_height=3.0):
    """The flat pattern as DXF R12 in mm: CUT outlines and holes, BEND
    centre lines (up and down on their own layers), ETCH notes."""
    out = ["0", "SECTION", "2", "ENTITIES"]

    def line(a, b, layer):
        out.extend(["0", "LINE", "8", layer, "10", f"{a[0]:.4f}", "20",
                    f"{a[1]:.4f}", "30", "0", "11", f"{b[0]:.4f}", "21",
                    f"{b[1]:.4f}", "31", "0"])
    for lp in pattern["outlines"]:
        for a, b in zip(lp, lp[1:] + lp[:1]):
            line(a, b, "CUT")
    for x, y, d in pattern["holes"]:
        out.extend(["0", "CIRCLE", "8", "CUT", "10", f"{x:.4f}", "20",
                    f"{y:.4f}", "30", "0", "40", f"{d / 2:.4f}"])
    for b in pattern["bend_table"]:
        a, c = b["line"]
        line(a, c, "BEND_UP" if b["direction"] == "up" else "BEND_DOWN")
        if bend_notes:
            mx, my = (a[0] + c[0]) / 2, (a[1] + c[1]) / 2
            text = (f"{b['direction'].upper()} {abs(b['angle_deg']):g}"
                    f"deg R{b['radius']:g}")
            out.extend(["0", "TEXT", "8", "ETCH", "10", f"{mx:.4f}", "20",
                        f"{my:.4f}", "30", "0", "40", f"{note_height:g}",
                        "1", text])
    out.extend(["0", "ENDSEC", "0", "EOF"])
    with open(path, "w", encoding="ascii") as fh:
        fh.write("\n".join(out) + "\n")
    return str(path)


# ============================================================== the node
def _segments():
    from . import mesh
    from . import model as model_mod
    fn = mesh._FN_OVERRIDE or model_mod._FN_OVERRIDE
    return max(int(fn or 32), 8)


def _resolved(node):
    return {k: node.params.get(k, v) for k, v in _DEFAULTS.items()}


def compute(node, env):
    params = _resolved(node)
    body = build(params, env)
    if params.get("flat"):
        perf = None
        for row in params.get("perforate") or []:
            if isinstance(row, list) and len(row) >= 2:
                perf = [_num(v, env, 0.0) for v in row]
        return flat_tris(flat_pattern(body, perf), body.t)
    return folded_tris(body, _segments())


def _check(node, env):
    body = build(_resolved(node), env)
    if body.errors:
        return "Sheet metal: " + body.errors[0]
    return None


KIT = bakedkit.make(
    KIND, LABEL, "mdi.page-layout-sidebar-left", _DEFAULTS,
    [("outline", "Base outline (flat, mm)", "rows", ["X", "Y"], None),
     ("contour", "Contour (X, Z; empty = use the outline)", "rows",
      ["X", "Z"], None),
     ("width", "Contour width", "float", 0.1, 10000.0),
     ("thickness", "Thickness", "float", 0.01, 100.0),
     ("radius", "Bend radius (inside)", "float", 0.0, 1000.0),
     ("k_factor", "K-factor", "float", 0.0, 1.0),
     ("hem_gap", "Hem gap", "float", 0.0, 100.0),
     ("rule", "Sheet metal rule", "str", None, None),
     ("flanges", "Flanges (panel, edge, height, angle, radius 0 = "
      "rule, inset start, inset end)", "rows",
      ["Panel", "Edge", "Height", "Angle", "Radius", "Inset A",
       "Inset B"], None),
     ("hems", "Hems (panel, edge, length, flip 0/1)", "rows",
      ["Panel", "Edge", "Length", "Flip"], None),
     ("folds", "Folds (x1, y1, x2, y2, angle, radius)", "rows",
      ["X1", "Y1", "X2", "Y2", "Angle", "Radius"], None),
     ("perforate", "Perforation (diameter, pitch, margin, 0 staggered "
      "/ 1 square)", "rows", ["Ø", "Pitch", "Margin", "Square"], None),
     ("flat", "Unfolded (show the flat pattern)", "bool", None, None)],
    compute, leaf=True, text=("rule",), check=_check)
