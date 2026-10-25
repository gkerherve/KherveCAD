"""Sketch dimensions on the 3D view (2026-10-25, the user: "show the
dimensions in the 3D view too"). Each sketch's driving dimensions are
drawn where its Object is: in the Object tab on the Object edited, in
Main on every placed instance of it (an Object's definition is hidden
and only its instances show) and on a visible part where it stands.

Linear dimensions (length, distance, h/v distance, point to line) as a
dimension line with extension lines, arrows and the value, offset
square to what they measure (the 2D view's dragged `offset`, else a
default); diameters, radii and angles as their value beside what they
size. Painted by `View3D` through its `overlay_painters` hook, never in
clean pictures (exports, Printables stills).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from . import sketch_constraints as sc

LINEAR = ("distance", "hdistance", "vdistance", "length", "point_line")
OFFSET_MM = 8.0          # default distance of the dimension line, model


def _mul(a, b):
    from .mesh import mat_mul
    return mat_mul(a, b)


def _apply(m, p):
    x, y, z = p
    return (m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3],
            m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3],
            m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3])


def _top(node, root):
    while node.parent is not None and node.parent is not root:
        node = node.parent
    return node


def _under(node, scope):
    while node is not None:
        if node is scope:
            return True
        node = node.parent
    return False


def placements(window):
    """[(container, 4x4 matrix to the world)] for every sketch with
    dimensions that the 3D view shows now."""
    from . import mesh
    model = window.model
    root = model.root
    scope = window._render_scope()[0]
    iso = scope if scope is not root else None
    out = []
    conts = [c for c in sc.containers(model)
             if any("value" in r for r in sc.rows(c))]
    if iso is not None:
        with window._isolated_frame(iso):
            for c in conts:
                if _under(c, iso):
                    m = _mul(mesh.ancestor_matrix(c, {}, stop=iso),
                             mesh.node_matrix(c, {}))
                    out.append((c, m))
        return out
    for c in conts:
        top = _top(c, root)
        if top.visible and top is not root:
            m = _mul(mesh.ancestor_matrix(c, {}),
                     mesh.node_matrix(c, {}))
            out.append((c, m))
            continue
        if top is root:
            out.append((c, mesh.node_matrix(c, {})))
            continue
        if top.type != "component":
            continue
        # a hidden definition: drawn on each instance of it
        inside = mesh.node_matrix(c, {}) if c is top else _mul(
            mesh.ancestor_matrix(c, {}, stop=top), mesh.node_matrix(c, {}))
        for ref in root.walk():
            if ref.type == "reference" and ref.visible and \
                    ref.params.get("ref") == top.name:
                place = _mul(mesh.ancestor_matrix(ref, {}),
                             mesh.node_matrix(ref, {}))
                out.append((c, _mul(place, inside)))
    return out


def _local(cont, row):
    """(kind, points) of a dimension in the sketch's own 2D frame."""
    kind = row["kind"]
    ents = [sc.entity(cont, r) for r in row["refs"]]
    if kind == "length":
        node, name = ents[0]
        return "linear", list(sc._line(node, name, {}))
    if kind == "point_line":
        (pn, pname), (ln, lname) = ents
        p = sc._point(pn, pname, {})
        a, b = sc._line(ln, lname, {})
        dx, dy = b[0] - a[0], b[1] - a[1]
        d2 = dx * dx + dy * dy or 1.0
        t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / d2
        return "linear", [p, (a[0] + dx * t, a[1] + dy * t)]
    if kind in LINEAR:
        (an, aname), (bn, bname) = ents
        pa = sc._point(an, aname, {})
        pb = sc._point(bn, bname, {})
        if kind == "hdistance":
            pb = (pb[0], pa[1])
        elif kind == "vdistance":
            pb = (pa[0], pb[1])
        return "linear", [pa, pb]
    if kind in ("diameter", "radius"):
        node, name = ents[0]
        c, r = sc._circle(node, name, {})
        return "label", [(c[0] + r * 0.72, c[1] + r * 0.72)]
    spots = []
    for node, name in ents:
        k = sc.kind_of(node, name)
        if k == "line":
            a, b = sc._line(node, name, {})
            spots.append(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
        elif k == "point":
            spots.append(sc._point(node, name, {}))
    if not spots:
        return None, []
    return "label", [(sum(p[0] for p in spots) / len(spots),
                      sum(p[1] for p in spots) / len(spots))]


def _centre(cont, row):
    """The centre of the shape a dimension's first pick belongs to."""
    try:
        node, _name = sc.entity(cont, row["refs"][0])
        if node.type in ("rect", "circle"):
            return sc._point(node, "c", {})
        if node.type == "polygon":
            pts = [sc._point(node, "v%d" % i, {})
                   for i in range(len(node.params["points"]))]
            return (sum(p[0] for p in pts) / len(pts),
                    sum(p[1] for p in pts) / len(pts))
    except (KeyError, ValueError, IndexError, TypeError):
        pass
    return None


def _text(row):
    unit = "°" if row["kind"] == "angle" else ""
    prefix = {"radius": "R", "diameter": "Ø"}.get(row["kind"], "")
    return "%s%s%s" % (prefix, row["value"], unit)


def paint(window, painter, project):
    """Draw every shown sketch's dimensions; *project* maps a world
    point to (x, y, depth) in view pixels or None."""
    from PyQt5.QtCore import QPointF, QRectF, Qt
    from PyQt5.QtGui import QBrush, QColor, QFont, QPen, QPolygonF
    window._dims3d_hits = []                # (chip rect, sketch, row)
    try:
        placed = placements(window)
    except Exception:                       # never break the paint
        return
    if not placed:
        return
    ink = QColor("#1565c0")
    pen = QPen(ink, 1.4)
    pen.setCosmetic(True)
    thin = QPen(ink, 1.0)
    thin.setCosmetic(True)
    font = QFont(painter.font())
    font.setBold(True)
    font.setPointSize(max(8, font.pointSize()))
    painter.save()
    painter.setRenderHint(painter.Antialiasing, True)
    painter.setFont(font)
    fm = painter.fontMetrics()

    def scr(m, p):
        q = project(_apply(m, (p[0], p[1], 0.0)))
        return None if q is None else QPointF(q[0], q[1])

    def chip(at, text, cont=None, index=None):
        tw = fm.horizontalAdvance(text)
        rect = QRectF(at.x() - tw / 2 - 5, at.y() - fm.height() / 2 - 2,
                      tw + 10, fm.height() + 4)
        if cont is not None:
            window._dims3d_hits.append((QRectF(rect), cont, index))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 230)))
        painter.drawRoundedRect(rect, 4, 4)
        painter.setPen(QPen(ink, 1.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawText(rect, int(Qt.AlignCenter), text)

    for cont, m in placed:
        for index, row in enumerate(sc.rows(cont)):
            if "value" not in row:
                continue
            try:
                what, pts = _local(cont, row)
            except (KeyError, ValueError, IndexError, TypeError):
                continue
            if what == "label":
                at = scr(m, pts[0])
                if at is not None:
                    chip(QPointF(at.x() + 6, at.y() - 6), _text(row),
                         cont, index)
                continue
            if what != "linear":
                continue
            (ax, ay), (bx, by) = pts
            L = math.hypot(bx - ax, by - ay)
            if L < 1e-9:
                continue
            nx, ny = -(by - ay) / L, (bx - ax) / L
            off = row.get("offset")
            if not isinstance(off, (int, float)):
                # by default OUTSIDE the shape it measures
                off = OFFSET_MM
                c = _centre(cont, row)
                if c is not None and (c[0] - ax) * nx + (c[1] - ay) * ny > 0:
                    off = -off
            pa, pb = scr(m, (ax, ay)), scr(m, (bx, by))
            oa = scr(m, (ax + nx * off, ay + ny * off))
            ob = scr(m, (bx + nx * off, by + ny * off))
            if None in (pa, pb, oa, ob):
                continue
            painter.setPen(thin)
            painter.drawLine(pa, oa)
            painter.drawLine(pb, ob)
            painter.setPen(pen)
            painter.drawLine(oa, ob)
            sx, sy = ob.x() - oa.x(), ob.y() - oa.y()
            sl = math.hypot(sx, sy) or 1.0
            ux, uy = sx / sl, sy / sl
            painter.setBrush(QBrush(ink))
            for tip, sgn in ((oa, 1.0), (ob, -1.0)):
                base = QPointF(tip.x() + sgn * ux * 8, tip.y() + sgn * uy * 8)
                painter.drawPolygon(QPolygonF([
                    tip, QPointF(base.x() - uy * 3.5, base.y() + ux * 3.5),
                    QPointF(base.x() + uy * 3.5, base.y() - ux * 3.5)]))
            painter.setBrush(Qt.NoBrush)
            chip(QPointF((oa.x() + ob.x()) / 2, (oa.y() + ob.y()) / 2),
                 str(row["value"]), cont, index)
    painter.restore()


def press(window, pos):
    """A click on a dimension's value in the 3D view: type a new one
    (the user: change the Smart Dimensions there too). True when
    taken."""
    for rect, cont, index in getattr(window, "_dims3d_hits", []):
        if rect.adjusted(-3, -3, 3, 3).contains(pos.x(), pos.y()):
            edit(window, rect, cont, index)
            return True
    return False


def edit(window, rect, cont, index):
    from PyQt5.QtWidgets import QLineEdit
    view = window.view3d
    old = getattr(view, "_dim3d_editor", None)
    if old is not None:
        old.deleteLater()
    row = sc.rows(cont)[index]
    box = QLineEdit(str(row.get("value", "")), view)
    box.setFixedWidth(max(70, int(rect.width()) + 20))
    box.move(int(rect.x()) - 8, int(rect.y()) - 3)
    box.selectAll()
    box.show()
    box.setFocus()
    view._dim3d_editor = box

    def done():
        if getattr(view, "_dim3d_editor", None) is not box:
            return
        view._dim3d_editor = None
        text = box.text().strip().replace(",", ".")
        box.deleteLater()
        try:
            value = float(text)
        except ValueError:
            value = text                    # an expression of variables
        try:
            sc.set_value(window.model, cont, index, value)
        except (ValueError, KeyError, IndexError) as exc:
            window.statusBar().showMessage(str(exc), 5000)
        view.update()
    box.editingFinished.connect(done)
    return box
