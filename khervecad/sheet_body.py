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
import sys

from . import bakedkit

KIND = "sheet_body"
LABEL = "Sheet metal body"
HEM_ANGLE = 150.0          # past it a bend starts on the edge itself
FOLD_TAG = "fold"

_DEFAULTS = dict(
    outline=[[0.0, 0.0], [100.0, 0.0], [100.0, 60.0], [0.0, 60.0]],
    contour=[], width=60.0,
    thickness=2.0, radius=2.0, k_factor=0.44, hem_gap=1.0, rule="",
    flanges=[], hems=[], folds=[], jogs=[], holes=[], slots=[],
    perforate=[], pholes=[], corners=[], tabs=[], tabjogs=[], gussets=[],
    flat=False)


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
        self.holes = []                      # cut-outs: CCW loops, (u, v)
        self.tabs = []                       # (loop, hole loop or None)
        self.cuts = []                       # loops taken away (a jog)
        self.frame = frame                   # 3D Frame
        self.flat = flat                     # 2D (o, u, v)
        self.cuts = []                       # holes / slots (panel coords)

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
        self.solids = []            # extra closed solids (gussets)
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
        row = row + [0.0] * (8 - len(row))
        specs.append([int(row[0]), int(row[1]), row[2], row[3],
                      row[4] if row[4] > 0 else r0, row[5], row[6],
                      "flange", True, int(row[7])])
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
    from . import sheet_jog
    this = sys.modules[__name__]
    jog_pieces = sheet_jog.jogs(body, base, rows("jogs", 5), t, k, r0, this)
    body.panels.append(base)

    # ---- set-backs: every bend on an edge pulls that edge in
    trims = {}
    for spec in specs:
        parent, edge, _h, ang, r = spec[:5]
        if spec[7] == "contour" or _partial(spec):
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
    if jog_pieces:
        sheet_jog.panels(body, base, jog_pieces, t, k, this)
    if rows("holes", 3) or rows("slots", 5):
        sheet_jog.place_cuts(body, base, jog_pieces, rows("holes", 3),
                             rows("slots", 5), this)

    for i, spec in enumerate(specs):
        parent_i, edge, height, ang, r, ia, ib, kind, numbered = spec[:9]
        shape = spec[9] if len(spec) > 9 else 0
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
        if _partial(spec) and kind == "flange":
            # a flange on part of an edge (an ear) bends where the sheet
            # ends under it: a notch the width of the flange, as deep as
            # the bend's set-back, is taken out of the parent; the rest of
            # the edge (and the facets that run on from it) stays
            e2 = ((b[0] - a[0]) / ln, (b[1] - a[1]) / ln)
            nrm2 = (-e2[1], e2[0])
            lo_pt = (a[0] + e2[0] * lo, a[1] + e2[1] * lo)
            hi_pt = (a[0] + e2[0] * hi, a[1] + e2[1] * hi)
            parent.cuts.append([
                lo_pt, hi_pt,
                (hi_pt[0] + nrm2[0] * s_own, hi_pt[1] + nrm2[1] * s_own),
                (lo_pt[0] + nrm2[0] * s_own, lo_pt[1] + nrm2[1] * s_own)])
            a = (a[0] + nrm2[0] * s_own, a[1] + nrm2[1] * s_own)
            b = (b[0] + nrm2[0] * s_own, b[1] + nrm2[1] * s_own)
        frame, fe, fw, fa, axis, e, w = bend_child(parent, a, b, ang, r, t)
        ba = _allowance(ang, r, t, k)
        flat_o = (fa[0] + fw[0] * ba, fa[1] + fw[1] * ba)
        poly = [(-hi, 0.0), (-lo, 0.0), (-lo, leg), (-hi, leg)]
        tags = [0, 1, 2, 3]
        if shape == 1:                     # an ear: a round far end
            poly, tags = _ear_outline(lo, hi, leg)
            if poly is None:
                body.errors.append(f"{kind} {i + 1}: the ear is too short "
                                   "for its round end")
                body.panels.append(None)
                continue
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
    _break_corners(body, rows("corners", 4))
    _cut_holes(body, rows("pholes", 4), params)
    _add_tabs(body, rows("tabs", 6))
    _apply_jogs(body, rows("tabjogs", 7), r0, k)
    _add_gussets(body, rows("gussets", 5))
    return body


def gusset_points(bend, t, offset, d1, d2, width, draft):
    """The corner points of a gusset rib in the inside of *bend*: a
    tapered wedge standing on both faces, *d1* up the parent's face and
    *d2* up the child's, *width* along the bend at the corner, its
    free ends narrower by the *draft* of its sides. Returns the hull's
    points (each end embedded 0.05 mm in the sheet so it fuses)."""
    f, e, w = bend["frame"], bend["e"], bend["w"]
    ang = bend["angle"]
    th = math.radians(ang)
    sgn = 1.0 if ang > 0 else -1.0
    r = bend["radius"]
    n = f.n
    nc = _sub(_mul(n, math.cos(th)), _mul(w, math.sin(th)))   # child's n
    vc = _add(_mul(w, math.cos(th)), _mul(n, math.sin(th)))   # child's v
    base = _add(bend["a"], _mul(e, offset))
    # the inside faces' virtual corner
    corner = _add(base, _mul(w, r * math.tan(abs(th) / 2)))
    if sgn > 0:
        corner = _add(corner, _mul(n, t))
    inner_p = _mul(n, sgn)                  # out of the parent's inner face
    inner_c = _mul(nc, sgn)
    emb = 0.05
    v0 = _sub(_sub(corner, _mul(inner_p, emb)), _mul(inner_c, emb))
    b1 = _sub(_add(corner, _mul(w, -d1)), _mul(inner_p, emb))
    b2 = _sub(_add(corner, _mul(vc, d2)), _mul(inner_c, emb))
    wc = max(width - 2 * min(d1, d2) * math.tan(math.radians(draft)) * 0.5,
             0.3 * width)
    pts = []
    for sx in (-1.0, 1.0):
        pts.append(_add(v0, _mul(e, sx * width / 2)))
        for q in (b1, b2):
            pts.append(_add(q, _mul(e, sx * wc / 2)))
    return pts


def _add_gussets(body, rows):
    """Sheet Metal Gusset: rows [bend, offset along the bend from its
    start, d1, d2, width, draft degrees] — a stamped rib across the
    inside of a bend (bends are numbered as in the bend table, from 0)."""
    from . import geom3d
    for j, row in enumerate(rows):
        bi = int(row[0])
        if not 0 <= bi < len(body.bends):
            body.errors.append(f"gusset {j + 1}: bend {bi + 1} does not "
                               "exist")
            continue
        bend = body.bends[bi]
        offset, d1, d2, width = row[1:5]
        draft = row[5] if len(row) > 5 else 20.0
        if min(d1, d2, width) <= 0:
            body.errors.append(f"gusset {j + 1}: its depths and width "
                               "must be more than 0")
            continue
        if not 0 <= offset <= bend["span"]:
            body.errors.append(f"gusset {j + 1}: it lies off its bend "
                               f"({bend['span']:.1f} mm long)")
            continue
        tris = geom3d.convex_hull(gusset_points(bend, body.t, offset, d1,
                                                d2, width, draft))
        if not tris:
            body.errors.append(f"gusset {j + 1}: no rib fits there")
            continue
        body.solids.append(tris)


def _partial(spec):
    """A flange that covers only part of its edge (inset, or an ear)."""
    return spec[7] == "flange" and (spec[5] > 1e-9 or spec[6] > 1e-9
                                    or (len(spec) > 9 and spec[9] == 1))


def jog_geometry(offset, angle, r, t):
    """(straight leg length, reach along the sheet) of a jog: two bends
    of *angle* with inner radius *r*, the sheet's bottom face stepping up
    by *offset*. The first bend has the bottom face outside (R = r + t),
    the second inside (r)."""
    a = math.radians(angle)
    sa, ca = math.sin(a), math.cos(a)
    leg = (offset - (2 * r + t) * (1 - ca)) / sa
    reach = (r + t) * sa + leg * ca + r * sa
    return leg, reach


def _components(region):
    """A CrossSection's connected pieces as lists of (outer loop, [hole
    loops]) in its coordinates."""
    out = []
    for part in region.decompose():
        loops = [list(map(tuple, lp)) for lp in part.to_polygons()]
        outers = [lp for lp in loops if _area2(lp) > 0]
        if not outers:
            continue
        outers.sort(key=lambda lp: -_area2(lp))
        out.append((outers[0], [lp for lp in loops if _area2(lp) < 0]))
    return out


def _apply_jogs(body, rows, r0, k):
    """Jog: rows [panel, x1, y1, x2, y2, offset, angle, radius (0 = the
    body's), fixed x, fixed y] — two bends of *angle* along the sketched
    line (x1, y1)-(x2, y2) step the part of the panel beyond it *offset*
    mm up (angle > 0) or down; the piece holding (fixed x, fixed y) —
    else the biggest — stays put. The line must cross only what moves
    (a tab): the band it bends is cut out of the panel between its ends.
    The moved piece keeps its place in the view square on to the sheet
    (SolidWorks' Fix projected length), the blank grows by the bends."""
    from . import csg
    t = body.t
    for j, row in enumerate(rows):
        row = list(row) + [0.0] * (10 - len(row))
        panel_i, x1, y1, x2, y2, h, ang, r, fx, fy = row[:10]
        panel_i = int(panel_i)
        panel = body.panels[panel_i] if 0 <= panel_i < len(body.panels) \
            else None
        if panel is None:
            body.errors.append(f"jog {j + 1}: panel {panel_i} does not "
                               "exist")
            continue
        if not csg.available():
            body.errors.append(f"jog {j + 1}: needs Manifold")
            continue
        if abs(ang) < 1e-6 or abs(ang) >= HEM_ANGLE or abs(h) < 1e-9 \
                or (ang > 0) != (h > 0):
            body.errors.append(f"jog {j + 1}: give an offset and an angle "
                               f"of the same sign (under {HEM_ANGLE:g} "
                               "degrees)")
            continue
        r = r if r > 0 else r0
        up = ang > 0
        a_abs, h_abs = abs(ang), abs(h)
        leg, reach = jog_geometry(h_abs, a_abs, r, t)
        length = math.hypot(x2 - x1, y2 - y1)
        if leg <= 1e-6 or length < 1e-6:
            body.errors.append(f"jog {j + 1}: the offset {h_abs:g} is too "
                               f"small for bends of radius {r:g}")
            continue
        m_ = csg._m
        pos = m_.FillRule.Positive
        region = panel_region(panel)
        d = ((x2 - x1) / length, (y2 - y1) / length)
        nrm = (-d[1], d[0])
        comps = _components(region)
        fixed = None
        for c in comps:
            if _inside([c[0]] + c[1], fx, fy):
                fixed = c
        if fixed is None and comps:
            fixed = max(comps, key=lambda c: _area2(c[0]))
        if fixed is None:
            body.errors.append(f"jog {j + 1}: panel {panel_i} is empty")
            continue
        # the moving side: the side where a piece is left that the
        # fixed one does not reach (a tab's free end)
        m_ = csg._m
        pos = m_.FillRule.Positive
        s0 = -reach / 2.0          # the line sits mid-jog (folded view)
        s1 = reach / 2.0
        mover, mdir = [], nrm
        for cand in (nrm, (-nrm[0], -nrm[1])):
            def at(tt, s, c=cand):
                return (x1 + d[0] * tt + c[0] * s,
                        y1 + d[1] * tt + c[1] * s)
            box = [at(0, s0), at(length, s0), at(length, s1), at(0, s1)]
            left = region - m_.CrossSection([[list(q) for q in _ccw(box)]],
                                            pos)
            found = []
            for c in _components(left):
                lo_s = min((q[0] - x1) * cand[0] + (q[1] - y1) * cand[1]
                           for q in c[0])
                if lo_s >= s1 - 1e-6:
                    found.append(c)
            # (the fixed piece must not be one of them)
            found = [c for c in found
                     if not _inside([c[0]] + c[1], fx, fy)]
            if found:
                mover, mdir = found, cand
                break

        def at(tt, s):
            return (x1 + d[0] * tt + mdir[0] * s,
                    y1 + d[1] * tt + mdir[1] * s)
        box = [at(0, s0), at(length, s0), at(length, s1), at(0, s1)]
        if not mover:
            body.errors.append(f"jog {j + 1}: the line cuts nothing off "
                               "that can move (it must cross a tab)")
            continue
        # the bend edge: where the panel meets the near side of the box
        strip = [at(0, s0 - 1e-3), at(length, s0 - 1e-3),
                 at(length, s0 + 1e-3), at(0, s0 + 1e-3)]
        meet = region ^ m_.CrossSection([[list(q) for q in _ccw(strip)]],
                                        pos)
        ts = [(q[0] - x1) * d[0] + (q[1] - y1) * d[1]
              for lp in meet.to_polygons() for q in lp]
        if not ts:
            body.errors.append(f"jog {j + 1}: the line does not reach the "
                               "panel")
            continue
        tmin, tmax = min(ts), max(ts)
        # e runs so that the outward normal e x n is the moving side
        left_n = (mdir[0] * nrm[0] + mdir[1] * nrm[1]) > 0
        if left_n:
            a_pt, b_pt = at(tmax, s0), at(tmin, s0)
        else:
            a_pt, b_pt = at(tmin, s0), at(tmax, s0)
        width = tmax - tmin
        sign = 1.0 if up else -1.0
        # first bend: off the panel's edge a -> b
        frame, fe, fw, fa, axis, e, w = bend_child(
            panel, a_pt, b_pt, sign * a_abs, r, t)
        ba = _allowance(a_abs, r, t, k)
        flat_o = (fa[0] + fw[0] * ba, fa[1] + fw[1] * ba)
        mid = Panel([(-width, 0.0), (0.0, 0.0), (0.0, leg), (-width, leg)],
                    [0, 1, 2, 3], frame, (flat_o, (-fe[0], -fe[1]), fw))
        body.bends.append(dict(
            kind="jog", parent=panel_i, edge=0, angle=sign * a_abs,
            radius=r, length=width, allowance=ba, frame=panel.frame, e=e,
            w=w, axis=axis, a=panel.frame.at(a_pt), span=width,
            flat=(fa, fe, fw, 0.0, width)))
        body.panels.append(mid)
        # second bend: back to parallel, off the leg's far edge
        a2, b2 = (0.0, leg), (-width, leg)
        frame3, fe3, fw3, fa3, axis3, e3, w3 = bend_child(
            mid, a2, b2, -sign * a_abs, r, t)
        flat_o3 = (fa3[0] + fw3[0] * ba, fa3[1] + fw3[1] * ba)
        body.bends.append(dict(
            kind="jog", parent=len(body.panels) - 1, edge=2,
            angle=-sign * a_abs, radius=r, length=width, allowance=ba,
            frame=mid.frame, e=e3, w=w3, axis=axis3,
            a=mid.frame.at(a2), span=width,
            flat=(fa3, fe3, fw3, 0.0, width)))
        # the moved piece, in the last panel's own coordinates
        def to3(q):
            dv = _sub(panel.frame.at(q), frame3.o)
            return (_dot(dv, frame3.u), _dot(dv, frame3.v))
        for ci, (outer, holes) in enumerate(mover):
            poly = [to3(q) for q in outer]
            child = Panel(poly, [0] * len(poly), frame3,
                          (flat_o3, (-fe3[0], -fe3[1]), fw3))
            child.holes = [[to3(q) for q in hl] for hl in holes]
            body.panels.append(child)
            panel.cuts.append(list(outer))
        panel.cuts.append(box)


def tab_loop(cx, cy, width, length, angle, sides=12):
    """A tab: a strip *width* wide whose round end is centred (cx, cy),
    running *length* from that centre toward *angle* degrees."""
    r = width / 2.0
    ang = math.radians(angle)
    d = (math.cos(ang), math.sin(ang))
    nrm = (-d[1], d[0])
    n = sides * 2
    pts = [(cx + r * math.cos(ang + math.pi / 2 + math.pi * i / n),
            cy + r * math.sin(ang + math.pi / 2 + math.pi * i / n))
           for i in range(n + 1)]
    pts.append((cx + d[0] * length - nrm[0] * r,
                cy + d[1] * length - nrm[1] * r))
    pts.append((cx + d[0] * length + nrm[0] * r,
                cy + d[1] * length + nrm[1] * r))
    return pts


def _add_tabs(body, rows):
    """Base Flange/Tab: rows [panel, cx, cy, width, length, angle, hole
    diameter] — a round-ended strip merged into the panel (holes the
    panel already has are cut first, so a tab may stand in an opening),
    with an optional hole through its round end."""
    for j, row in enumerate(rows):
        panel_i = int(row[0])
        panel = body.panels[panel_i] if 0 <= panel_i < len(body.panels) \
            else None
        if panel is None:
            body.errors.append(f"tab {j + 1}: panel {panel_i} does not "
                               "exist")
            continue
        cx, cy, width, length, angle = row[1:6]
        hole_d = row[6] if len(row) > 6 else 0.0
        if width <= 0 or length <= 0:
            body.errors.append(f"tab {j + 1}: its width and length must "
                               "be more than 0")
            continue
        loop = tab_loop(cx, cy, width, length, angle)
        if not any(_inside([panel.poly], px, py) for px, py in loop):
            body.errors.append(f"tab {j + 1}: it does not touch panel "
                               f"{panel_i}")
            continue
        panel.tabs.append((loop, circle_loop(cx, cy, hole_d)
                           if hole_d > 0 else None))


CORNER_SIDES = 12            # segments on a 90 degree round
CORNER_TAG = 100             # new edges: CORNER_TAG + the row's number


def corner_cut(a, p, b, size, round_=True, sides=CORNER_SIDES):
    """The points that replace corner *p* (between *a* before and *b*
    after it, the polygon running CCW): a round of radius *size* tangent
    to both sides, or a chamfer *size* along each. None when the corner
    is not convex or the sides are too short."""
    ua = _unit((a[0] - p[0], a[1] - p[1], 0.0))
    ub = _unit((b[0] - p[0], b[1] - p[1], 0.0))
    la = math.hypot(a[0] - p[0], a[1] - p[1])
    lb = math.hypot(b[0] - p[0], b[1] - p[1])
    cross = ub[0] * ua[1] - ub[1] * ua[0]
    dot = max(-1.0, min(1.0, ua[0] * ub[0] + ua[1] * ub[1]))
    if cross <= 1e-9:                      # straight or reflex
        return None
    theta = math.acos(dot)                 # the corner's interior angle
    reach = size / math.tan(theta / 2) if round_ else size
    if reach > min(la, lb) + 1e-9 or reach <= 0:
        return None
    t1 = (p[0] + ua[0] * reach, p[1] + ua[1] * reach)
    t2 = (p[0] + ub[0] * reach, p[1] + ub[1] * reach)
    if not round_:
        return [t1, t2]
    bis = _unit((ua[0] + ub[0], ua[1] + ub[1], 0.0))
    dist = size / math.sin(theta / 2)
    c = (p[0] + bis[0] * dist, p[1] + bis[1] * dist)
    a0 = math.atan2(t1[1] - c[1], t1[0] - c[0])
    a1 = math.atan2(t2[1] - c[1], t2[0] - c[0])
    sweep = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
    n = max(2, int(math.ceil(abs(sweep) / (math.pi / 2) * sides)))
    return [(c[0] + size * math.cos(a0 + sweep * i / n),
             c[1] + size * math.sin(a0 + sweep * i / n))
            for i in range(n + 1)]


def _break_corners(body, rows):
    """Break Corner: rows [panel, u, v, size, 0 round / 1 chamfer] — the
    polygon vertex of that panel nearest (u, v) is rounded (or cut). The
    new edges carry their own tags, so a flange can still be put on the
    straight ones."""
    for j, row in enumerate(rows):
        panel_i, u, v, size = int(row[0]), row[1], row[2], row[3]
        kind = row[4] if len(row) > 4 else 0
        panel = body.panels[panel_i] if 0 <= panel_i < len(body.panels) \
            else None
        if panel is None:
            body.errors.append(f"corner {j + 1}: panel {panel_i} does not "
                               "exist")
            continue
        n = len(panel.poly)
        i = min(range(n), key=lambda k: (panel.poly[k][0] - u) ** 2
                + (panel.poly[k][1] - v) ** 2)
        cut = corner_cut(panel.poly[i - 1], panel.poly[i],
                         panel.poly[(i + 1) % n], size, kind < 0.5)
        if cut is None:
            body.errors.append(f"corner {j + 1}: the size {size:g} does "
                               "not fit that corner (it must be convex "
                               "and the sides long enough)")
            continue
        tag = CORNER_TAG + j
        poly, tags = [], []
        for k in range(n):
            if k != i:
                poly.append(panel.poly[k])
                tags.append(panel.tags[k])
                continue
            for idx, pt in enumerate(cut):      # edge k leaves cut[-1]
                poly.append(pt)
                tags.append(tag if idx < len(cut) - 1 else panel.tags[k])
        panel.poly, panel.tags = poly, tags


def _ear_outline(lo, hi, leg, sides=16):
    """A flange profile with a full round far end (radius = half the
    width): the straight sides and a half circle. Edge tags: 0 the bend,
    1 and 3 the sides, 2 the round end."""
    rad = (hi - lo) / 2.0
    if leg < rad + 1e-6:
        return None, None
    cx, cy = -(lo + hi) / 2.0, leg - rad
    poly = [(-hi, 0.0), (-lo, 0.0)]
    tags = [0, 1 if cy > 1e-9 else 2]       # (edge leaving each point)
    if cy > 1e-9:
        poly.append((-lo, cy))
        tags.append(2)
    for i in range(1, sides):
        a = math.pi * i / sides
        poly.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
        tags.append(2)
    poly.append((-hi, cy))
    tags.append(3 if cy > 1e-9 else 2)
    return poly, tags


HOLE_SIDES = 48


def circle_loop(x, y, d, sides=HOLE_SIDES):
    r = d / 2.0
    return [(x + r * math.cos(2 * math.pi * i / sides),
             y + r * math.sin(2 * math.pi * i / sides))
            for i in range(sides)]


def _cut_holes(body, rows, params):
    """Holes [panel, u, v, diameter] cut through a panel, in its own
    (u, v) coordinates — the Simple Hole / the opening of a base flange.
    A hole that misses its panel is an error, not a silent no-op."""
    for j, (panel_i, x, y, d) in enumerate(r[:4] for r in rows):
        panel_i = int(panel_i)
        panel = body.panels[panel_i] if 0 <= panel_i < len(body.panels) \
            else None
        if panel is None:
            body.errors.append(f"hole {j + 1}: panel {panel_i} does not "
                               "exist")
            continue
        if d <= 0:
            body.errors.append(f"hole {j + 1}: its diameter must be "
                               "more than 0")
            continue
        loop = circle_loop(x, y, d)
        if not any(_inside([panel.poly], px, py) for px, py in loop) \
                and not _inside([panel.poly], x, y):
            body.errors.append(f"hole {j + 1}: it lies off panel "
                               f"{panel_i}")
            continue
        panel.holes.append(loop)


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
    if panel.holes or panel.tabs or panel.cuts:
        cut = _panel_with_holes(panel, t)
        if cut is not None:
            return cut
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


def _ccw(loop):
    return loop if _area2(loop) >= 0 else loop[::-1]


def panel_region(panel):
    """The panel's 2D shape as a Manifold CrossSection in its own (u, v):
    outline, less its holes, plus its tabs (each less its own hole), less
    what a jog took away. None without Manifold."""
    from . import csg
    if not csg.available():
        return None
    m = csg._m
    pos = m.FillRule.Positive
    sec = m.CrossSection([[list(q) for q in _ccw(panel.poly)]], pos)
    if panel.holes:
        sec = sec - m.CrossSection([[list(q) for q in _ccw(h)]
                                    for h in panel.holes], pos)
    for loop, hole in panel.tabs:
        tab = m.CrossSection([[list(q) for q in _ccw(loop)]], pos)
        if hole:
            tab = tab - m.CrossSection([[list(q) for q in _ccw(hole)]], pos)
        sec = sec + tab
    if panel.cuts:
        sec = sec - m.CrossSection([[list(q) for q in _ccw(c)]
                                    for c in panel.cuts], pos)
    return sec


def _panel_with_holes(panel, t):
    """The panel as a slab with its holes / tabs / cuts applied
    (Manifold); None without it — they then stay out of the solid."""
    from . import csg
    sec = panel_region(panel)
    if sec is None:
        return None
    if sec.is_empty():
        return []
    m = csg._m
    f = panel.frame
    tris = csg.to_triangles(m.Manifold.extrude(sec, t))
    return _closed([tuple(f.at((v[0], v[1]), v[2]) for v in tri)
                    for tri in tris])


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
    pieces += list(body.solids)
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
    cuts = []
    for p in body.all_panels():
        for lp in p.cuts:
            cuts.append([p.flat_point(q) for q in lp])
    holes = []
    from . import csg
    if csg.available():
        m = csg._m
        pos = m.FillRule.Positive
        secs = []
        for panel in body.all_panels():
            if panel.holes or panel.tabs or panel.cuts:
                sec = panel_region(panel)
                polys_p = [[panel.flat_point(q) for q in lp]
                           for lp in sec.to_polygons()]
                if polys_p:
                    secs.append(m.CrossSection(
                        [[list(q) for q in lp] for lp in polys_p],
                        m.FillRule.EvenOdd))
            elif len(panel.poly) >= 3:
                lp = [panel.flat_point(q) for q in panel.poly]
                if abs(_area2(lp)) > 1e-12:
                    secs.append(m.CrossSection([[list(q) for q in lp]], pos))
        for lp in strips:
            if abs(_area2(lp)) > 1e-12:
                secs.append(m.CrossSection([[list(q) for q in lp]], pos))
        region = m.CrossSection.batch_boolean(secs, m.OpType.Add) \
            if secs else m.CrossSection()
        cuts = []              # (panel_region already took them out)
        polys = [list(map(tuple, lp)) for lp in region.to_polygons()]
        if perforate:
            holes = _perforation(m, region, strips, perforate)
        outlines = polys
    outlines = [[(float(x), float(y)) for x, y in lp] for lp in outlines]
    xs = [q[0] for lp in outlines for q in lp] or [0.0]
    ys = [q[1] for lp in outlines for q in lp] or [0.0]
    return dict(outlines=outlines, bend_table=table, holes=holes, cuts=cuts,
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
        if pattern.get("cuts"):
            sec = sec - m.CrossSection(
                [[list(q) for q in lp] for lp in pattern["cuts"]],
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
    for lp in pattern.get("cuts") or []:
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
      "rule, inset start, inset end, shape 0 plain / 1 round-ended ear)",
      "rows",
      ["Panel", "Edge", "Height", "Angle", "Radius", "Inset A",
       "Inset B", "Ear"], None),
     ("hems", "Hems (panel, edge, length, flip 0/1)", "rows",
      ["Panel", "Edge", "Length", "Flip"], None),
     ("folds", "Folds (x1, y1, x2, y2, angle, radius)", "rows",
      ["X1", "Y1", "X2", "Y2", "Angle", "Radius"], None),
     ("jogs", "Jogs (x1, y1, x2, y2, offset, angle, radius 0 = rule, "
      "dimension 0/1/2, position 0-3, fixed side 1/-1, direction 1/-1)",
      "rows", ["X1", "Y1", "X2", "Y2", "Offset", "Angle", "Radius", "Dim",
               "Position", "Side", "Dir"], None),
     ("holes", "Holes (x, y, diameter, in the flat plate)", "rows",
      ["X", "Y", "Ø"], None),
     ("slots", "Slots (x1, y1, x2, y2, width)", "rows",
      ["X1", "Y1", "X2", "Y2", "Width"], None),
     ("perforate", "Perforation (diameter, pitch, margin, 0 staggered "
      "/ 1 square)", "rows", ["Ø", "Pitch", "Margin", "Square"], None),
     ("pholes", "Panel holes (panel, u, v, diameter): through any panel, "
      "cut before the tabs are merged", "rows",
      ["Panel", "U", "V", "Ø"], None),
     ("gussets", "Gussets (bend number - 1, offset along the bend, d1, d2, "
      "width, draft degrees)", "rows",
      ["Bend", "Offset", "D1", "D2", "Width", "Draft"], None),
     ("tabjogs", "Tab jogs (panel, x1, y1, x2, y2, offset, angle, "
      "radius 0 = rule, fixed x, fixed y)", "rows",
      ["Panel", "X1", "Y1", "X2", "Y2", "Offset", "Angle", "Radius",
       "Fixed X", "Fixed Y"], None),
     ("tabs", "Tabs (panel, centre u, centre v, width, length, angle, "
      "hole diameter)", "rows",
      ["Panel", "U", "V", "Width", "Length", "Angle", "Hole Ø"], None),
     ("corners", "Break corners (panel, u, v, size, 0 round / 1 chamfer)",
      "rows", ["Panel", "U", "V", "Size", "Chamfer"], None),
     ("flat", "Unfolded (show the flat pattern)", "bool", None, None)],
    compute, leaf=True, text=("rule",), check=_check)
