"""Sketch Fillet / Chamfer where ARCS meet (2026-11-11, the user, with
SolidWorks' flange: after trimming the two circles into one outline,
"select an arc and create a sketch fillet of 8 mm … we have a sketch
chamfer which is maybe almost the same. Can we do that too?").

`corner(model, a, b, size, round_)` works on any two sketch curves that
share an end — line and line, line and arc, arc and arc (an arc is a
`line` with a bulge, `sketch_arc`):

- **fillet**: the circle of radius *size* tangent to both, found where
  the two curves' offsets by *size* meet (a line's parallels, an arc's
  concentric circles r ± size), the one whose tangent points lie on the
  curves nearest the corner; both curves are cut back to the tangent
  points and the fillet is a new arc between them;
- **chamfer**: a point *size* along each curve from the corner (along
  the arc for an arc), both cut back to it and joined by a line.

New pieces are tied by Coincident relations at their ends.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from . import sketch_trim as tr

TOL = 1e-4


def _ends(cv):
    return tr.point_at(cv, 0.0), tr.point_at(cv, 1.0)


def shared_end(a_node, b_node):
    """(t on a, t on b, the point) where the two curves meet end to
    end (within TOL), else None."""
    ca, cb = tr.curve_of(a_node), tr.curve_of(b_node)
    if ca is None or cb is None or tr._closed(ca) or tr._closed(cb):
        return None
    best = None
    for ta, pa in zip((0.0, 1.0), _ends(ca)):
        for tb, pb in zip((0.0, 1.0), _ends(cb)):
            d = math.hypot(pa[0] - pb[0], pa[1] - pb[1])
            if d < TOL * 10 and (best is None or d < best[0]):
                best = (d, ta, tb, ((pa[0] + pb[0]) / 2,
                                    (pa[1] + pb[1]) / 2))
    return None if best is None else best[1:]


def partner(node, end):
    """The sibling curve whose end meets *node*'s end *end* ("p1" /
    "p2"), and that end's point — for a click on a corner point."""
    cv = tr.curve_of(node)
    if cv is None or node.parent is None:
        return None
    p = tr.point_at(cv, 0.0 if end == "p1" else 1.0)
    for o in node.parent.children:
        if o is node:
            continue
        co = tr.curve_of(o)
        if co is None or tr._closed(co):
            continue
        for q in _ends(co):
            if math.hypot(p[0] - q[0], p[1] - q[1]) < TOL * 10:
                return o
    return None


def _offsets(cv, r):
    """The curve's offsets by r as carriers: lines or circles."""
    if cv[0] == "seg":
        a, b = cv[1], cv[2]
        d = (b[0] - a[0], b[1] - a[1])
        L = math.hypot(*d) or 1.0
        n = (-d[1] / L * r, d[0] / L * r)
        out = []
        for s in (1, -1):
            out.append(("seg", (a[0] + s * n[0], a[1] + s * n[1]),
                        (b[0] + s * n[0], b[1] + s * n[1])))
        return out
    _k, cx, cy, rad, _a0, _sw = cv
    out = [("arc", cx, cy, rad + r, 0.0, tr.TWO_PI)]
    if rad - r > 1e-9:
        out.append(("arc", cx, cy, rad - r, 0.0, tr.TWO_PI))
    return out


def _foot(cv, q):
    """The point of cv's carrier nearest q (the tangent point)."""
    if cv[0] == "seg":
        a, b = cv[1], cv[2]
        d = (b[0] - a[0], b[1] - a[1])
        L2 = d[0] ** 2 + d[1] ** 2 or 1e-12
        t = ((q[0] - a[0]) * d[0] + (q[1] - a[1]) * d[1]) / L2
        return (a[0] + d[0] * t, a[1] + d[1] * t)
    _k, cx, cy, rad, _a0, _sw = cv
    dx, dy = q[0] - cx, q[1] - cy
    L = math.hypot(dx, dy) or 1.0
    return (cx + dx / L * rad, cy + dy / L * rad)


def _cut_back(params, cv, t_corner, t_new):
    """The curve kept from its far end to *t_new* (the corner end goes)."""
    if t_corner < 0.5:
        s, e, span = t_new, 1.0, 1.0 - t_new
        a, b = tr.point_at(cv, t_new), tr.point_at(cv, 1.0)
    else:
        s, e, span = 0.0, t_new, t_new
        a, b = tr.point_at(cv, 0.0), tr.point_at(cv, t_new)
    sweep = cv[5] * span if cv[0] == "arc" else 0.0
    tr._apply(params, a, b, sweep, cv)
    return t_new if t_corner < 0.5 else t_new   # (the new end's t)


def corner(model, a, b, size, round_=True):
    """Fillet (round_) or chamfer the corner where curves *a* and *b*
    meet. Returns the new node. Raises ValueError when they do not meet
    or the size does not fit."""
    from . import sketch_arc
    from . import sketch_constraints as sc
    if a is b or a.parent is not b.parent:
        raise ValueError("pick two curves of one sketch that meet")
    meet = shared_end(a, b)
    if meet is None:
        raise ValueError("those two do not meet end to end — trim them "
                         "to a corner first")
    ta, tb, P = meet
    ca, cb = tr.curve_of(a), tr.curve_of(b)
    size = float(size)
    if size <= 0:
        raise ValueError("the size must be more than 0")
    tr.remember(a)
    tr.remember(b)
    # the corner is going: a relation tying the two ends there would pull
    # them back together
    parent = a.parent
    ea = sc.ref_of(parent, a, "p1" if ta < 0.5 else "p2")
    eb = sc.ref_of(parent, b, "p1" if tb < 0.5 else "p2")
    rows = sc.rows(parent)
    keep = [r for r in rows if not (r.get("kind") == "coincident" and
                                    set(r.get("refs", ())) == {ea, eb})]
    if len(keep) != len(rows):
        parent.params[sc.KEY] = keep
    if round_:
        best = None
        for oa in _offsets(ca, size):
            for ob in _offsets(cb, size):
                for q in tr.meet_points(oa, ob):
                    fa, fb = _foot(ca, q), _foot(cb, q)
                    ua, ub = tr._on(ca, fa, 1e-6), tr._on(cb, fb, 1e-6)
                    if ua is None or ub is None:
                        continue
                    d = math.hypot(fa[0] - P[0], fa[1] - P[1]) + \
                        math.hypot(fb[0] - P[0], fb[1] - P[1])
                    if d < 1e-9:
                        continue
                    if best is None or d < best[0]:
                        best = (d, q, fa, fb, ua, ub)
        if best is None:
            raise ValueError("a %g fillet does not fit there" % size)
        _d, q, fa, fb, ua, ub = best
        # the arc from fa to fb round q, on the corner's side
        dx, dy = P[0] - q[0], P[1] - q[1]
        L = math.hypot(dx, dy) or 1.0
        m = (q[0] + dx / L * size, q[1] + dy / L * size)
        bulge = sketch_arc.bulge_through(fa, fb, m)
        params = dict(x1=round(fa[0], 6), y1=round(fa[1], 6),
                      x2=round(fb[0], 6), y2=round(fb[1], 6), width=0.2,
                      bulge=round(bulge, 12))
        name = "Sketch fillet R%g" % size
    else:
        def along(cv, t_end):
            # the point `size` along the curve from its corner end
            if cv[0] == "seg":
                a0, b0 = cv[1], cv[2]
                L = math.hypot(b0[0] - a0[0], b0[1] - a0[1]) or 1.0
                dt = size / L
            else:
                dt = size / (abs(cv[5]) * cv[3] or 1.0)
            if dt >= 1.0:
                raise ValueError("a %g chamfer is longer than a side" % size)
            u = dt if t_end < 0.5 else 1.0 - dt
            return tr.point_at(cv, u), u
        fa, ua = along(ca, ta)
        fb, ub = along(cb, tb)
        params = dict(x1=round(fa[0], 6), y1=round(fa[1], 6),
                      x2=round(fb[0], 6), y2=round(fb[1], 6), width=0.2)
        name = "Sketch chamfer %g" % size
    _cut_back(a.params, ca, ta, ua)
    _cut_back(b.params, cb, tb, ub)
    model.node_changed.emit(a)
    model.node_changed.emit(b)
    params[MARK] = {"kind": "fillet" if round_ else "chamfer",
                    "size": size}
    new = model.add_node("line", params, parent=a.parent)
    model.rename(new, name)
    parent = a.parent

    def end_of(node, pt):
        cv = tr.curve_of(node)
        p0, p1 = _ends(cv)
        return "p1" if math.hypot(p0[0] - pt[0], p0[1] - pt[1]) <= \
            math.hypot(p1[0] - pt[0], p1[1] - pt[1]) else "p2"
    for node, pt, mine in ((a, fa, "p1"), (b, fb, "p2")):
        try:
            sc.add(model, parent, "coincident",
                   [sc.ref_of(parent, node, end_of(node, pt)),
                    sc.ref_of(parent, new, mine)])
        except (ValueError, KeyError):
            pass
    if round_:
        # SolidWorks' fillet holds: tangent to both, and its radius a
        # dimension you can change later (the user: "not able to see
        # where the radius ... change later on")
        for node in (a, b):
            ent = "o" if tr.curve_of(node)[0] == "arc" else "l"
            try:
                sc.add(model, parent, "tangent",
                       [sc.ref_of(parent, node, ent),
                        sc.ref_of(parent, new, "o")])
            except (ValueError, KeyError):
                pass
        try:
            sc.add(model, parent, "radius", [sc.ref_of(parent, new, "o")],
                   value=size)
        except (ValueError, KeyError):
            pass
    else:
        try:
            sc.add(model, parent, "length", [sc.ref_of(parent, new, "l")],
                   value=round(math.dist(fa, fb), 6))
        except (ValueError, KeyError):
            pass
    return new


def between(model, a, b, size, round_=True):
    """The two curves clicked: an arc's corner by `corner`; two straight
    lines by `corner` when they meet end to end, else by the older
    `sketch_modify.line_corner`, which also finds where lines that only
    nearly meet (or cross) would meet."""
    from . import sketch_arc, sketch_modify
    arcs = sketch_arc.is_arc(a) or sketch_arc.is_arc(b)
    if arcs or shared_end(a, b) is not None:
        try:
            return corner(model, a, b, size, round_)
        except ValueError:
            if arcs:
                raise
    return sketch_modify.line_corner(model, a, b, size, round_)


#: on a fillet / chamfer line: what it is and its size (the tree's tag)
MARK = "sketch_corner"


def label(node):
    """"(fillet R8)" / "(chamfer 5)" for the tree, from the CURRENT
    radius / length (a dimension may have changed it)."""
    rec = node.params.get(MARK)
    if not isinstance(rec, dict):
        return ""
    cv = tr.curve_of(node)
    if rec.get("kind") == "fillet" and cv is not None and cv[0] == "arc":
        return "(fillet R%g)" % round(cv[3], 3)
    if cv is not None and cv[0] == "seg":
        return "(chamfer %g)" % round(math.dist(cv[1], cv[2]), 3)
    return "(%s)" % rec.get("kind", "")


# ------------------------------------------- what the click would take
# (2026-11-11, the user: "not able to see what I'm selecting … one being
# highlighted and then the other one")
HOVER_INK = "#ff8c00"     # under the cursor
PICKED_INK = "#1e88e5"    # the first one picked


def _polyline(node):
    from . import sketch_arc
    if node is None or node.parent is None or node.type != "line":
        return []
    try:
        return sketch_arc.node_points(node)
    except Exception:
        return []


def hovered(node, entity):
    """The curves a click on (node, entity) would act on: a corner point
    -> both curves meeting there; a curve -> that curve."""
    if node is None or node.type != "line":
        return []
    if entity in ("p1", "p2"):
        other = partner(node, entity)
        if other is not None:
            return [node, other]
    return [node]


def hover_2d(scene, pos):
    from . import sketch_constrain_ui as scu
    hit = scu.pick(scene, pos, "point")
    nodes = []
    if hit is not None and hit[0].type == "line" and hit[1] in ("p1", "p2"):
        nodes = hovered(hit[0], hit[1])
    if not nodes:
        hit = scu.pick(scene, pos, "curve")
        if hit is not None:
            nodes = hovered(hit[0], hit[1])
    old = getattr(scene, "_corner_hover", None)
    scene._corner_hover = nodes
    if nodes or old:
        scene.update()


def _scene_points(scene, node):
    from PyQt5.QtCore import QPointF
    from . import sketch_constrain_ui as scu
    from .view2d_edit import Frame
    item = next((it for it in scu._shape_items(scene) if it.node is node),
                None)
    frame = item.parentItem() if item is not None else None
    to_s = frame.mapToScene if isinstance(frame, Frame) else \
        (lambda p: QPointF(p))
    return [to_s(QPointF(x, y)) for x, y in _polyline(node)]


def paint_2d(view, painter):
    from PyQt5.QtGui import QColor, QPen, QPolygonF
    from . import sketch_modify
    scene = view.scene()
    if getattr(scene, "tool", None) not in (sketch_modify.FILLET,
                                            sketch_modify.CHAMFER):
        return
    k = abs(view.transform().m11()) or 1.0
    painter.save()
    first = getattr(scene, "_sk_first", None)
    for nodes, ink in (([first] if first is not None else [], PICKED_INK),
                       (getattr(scene, "_corner_hover", None) or [],
                        HOVER_INK)):
        painter.setPen(QPen(QColor(ink), 3.0 / k))
        for n in nodes:
            pts = _scene_points(scene, n)
            if len(pts) >= 2:
                painter.drawPolyline(QPolygonF(pts))
    painter.restore()


def paint_3d(painter, project, group, picked, hover):
    from . import sketch_trim
    from PyQt5.QtGui import QColor, QPen
    for nodes, ink in ((picked, PICKED_INK), (hover, HOVER_INK)):
        for n in nodes or []:
            pts = _polyline(n)
            if len(pts) >= 2:
                old = sketch_trim.HOVER_INK
                sketch_trim.HOVER_INK = ink
                try:
                    sketch_trim.paint_3d(painter, project, group, pts)
                finally:
                    sketch_trim.HOVER_INK = old
