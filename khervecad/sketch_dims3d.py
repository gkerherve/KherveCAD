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


def assembly_mode(window):
    """The Main tab and no sketch open: parts, not their sketches."""
    builder = getattr(window, "builder", None)
    if builder is None or builder.isolated_component() is not None:
        return False
    from . import sketch_mode
    if sketch_mode.sketching(window) or \
            getattr(window, "_face_sketch", None) is not None:
        return False
    return True


def _in_object(c, root):
    probe = c
    while probe is not None and probe is not root:
        if probe.type == "component":
            return True
        probe = probe.parent
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
    if iso is None and assembly_mode(window):
        # the assembly (Main tab, not sketching): an Object's sketch
        # dimensions stay in its Object tab (the user: none at all here)
        conts = [c for c in conts if not _in_object(c, root)]
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
        # a leader from the centre out through the edge (SolidWorks' R8):
        # [centre, the point on the edge, where the value sits]; a slot's
        # end leans away from the slot
        node, name = ents[0]
        c, r = sc._circle(node, name, {})
        ux, uy = 0.707, 0.707
        if node.type == "line" and name in ("a1", "a2"):
            a = sc._point(node, "p1", {})
            b = sc._point(node, "p2", {})
            dx, dy = (b[0] - a[0], b[1] - a[1]) if name == "a2" else \
                (a[0] - b[0], a[1] - b[1])
            L = math.hypot(dx, dy) or 1.0
            ux, uy = dx / L * 0.707 + dy / L * 0.707, \
                dy / L * 0.707 - dx / L * 0.707
        edge = (c[0] + r * ux, c[1] + r * uy)
        out = (c[0] + (r + max(r, 6.0)) * ux, c[1] + (r + max(r, 6.0)) * uy)
        return "leader", [c, edge, out]
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
        if node.type == "line" and float(node.params.get("width", 0) or 0):
            # a slot's centre line: the dimension goes OUTSIDE the slot,
            # half its width plus a gap (SolidWorks' 24 above it)
            a = sc._point(node, "p1", {})
            b = sc._point(node, "p2", {})
            return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
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
    value = row["value"]
    if isinstance(value, (int, float)):
        from . import units
        value = units.number(value)
    return "%s%s%s" % (prefix, value, unit)


def _closed_solids(mesh):
    """The triangles of *mesh* that belong to CLOSED pieces (every edge
    shared by two of the piece's faces), as an (n, 3, 3) array: flat
    sketch faces in the view are not solids and hide nothing."""
    import numpy as np
    tris = np.asarray(mesh, dtype=np.float64).reshape(-1, 3, 3)
    if not len(tris):
        return tris
    keys = np.round(tris.reshape(-1, 3) / 1e-4).astype(np.int64)
    _u, vid = np.unique(keys, axis=0, return_inverse=True)
    vid = vid.reshape(-1, 3)
    edges = {}
    for t, (a, b, c) in enumerate(vid.tolist()):
        for e in ((a, b), (b, c), (c, a)):
            edges.setdefault((min(e), max(e)), []).append(t)
    parent = list(range(len(vid)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for faces in edges.values():
        for f in faces[1:]:
            parent[root(f)] = root(faces[0])
    open_ = {root(faces[0]) for faces in edges.values() if len(faces) != 2}
    keep = [t for t in range(len(vid)) if root(t) not in open_]
    return tris[keep]


def _occluder(window):
    """seen(world point) -> False when a solid of the 3D view stands
    between it and the eye (2026-10-31, the user: a dimension showed
    through the part, "it should not go through the solid"). A ray
    toward the eye against the view's closed pieces, kept per mesh
    serial; everything is seen without numpy or a solid."""
    view = getattr(window, "view3d", None)
    if view is None or not view.mesh:
        return lambda p: True
    try:
        import numpy as np
    except ImportError:
        return lambda p: True
    serial = getattr(view, "_mesh_serial", None)
    cache = getattr(view, "_dims_solid", None)
    if cache is None or cache[0] != serial:
        try:
            tris = _closed_solids(view.mesh)
        except Exception:
            tris = None
        cache = view._dims_solid = (serial, tris)
    tris = cache[1]
    if tris is None or not len(tris):
        return lambda p: True
    v0 = tris[:, 0]
    e1, e2 = tris[:, 1] - v0, tris[:, 2] - v0
    eye, _r, _u, forward = view._camera()
    ortho = view.projection == "Orthographic"
    size = float(np.ptp(tris.reshape(-1, 3), axis=0).max()) or 1.0
    eps = size * 1e-4                       # off the face it may lie on

    def seen(p):
        p = np.asarray(p, dtype=np.float64)
        if ortho:
            d = -np.asarray(forward, dtype=np.float64)
            limit = np.inf
        else:
            d = np.asarray(eye, dtype=np.float64) - p
            limit = float(np.linalg.norm(d))
            d = d / (limit or 1.0)
        o = p + d * eps
        h = np.cross(d, e2)
        a = np.einsum("ij,ij->i", e1, h)
        ok = np.abs(a) > 1e-12
        f = np.where(ok, 1.0 / np.where(ok, a, 1.0), 0.0)
        s = o - v0
        u = f * np.einsum("ij,ij->i", s, h)
        q = np.cross(s, e1)
        v = f * (q @ d)
        t = f * np.einsum("ij,ij->i", e2, q)
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > eps) & \
            (t < limit)
        return not bool(hit.any())

    return seen


def paint(window, painter, project):
    """Draw every shown sketch's dimensions; *project* maps a world
    point to (x, y, depth) in view pixels or None."""
    from PyQt5.QtCore import QPointF, QRectF, Qt
    from PyQt5.QtGui import QBrush, QColor, QFont, QPen, QPolygonF
    window._dims3d_hits = []                # (chip rect, sketch, row)
    if not getattr(window.scene, "show_sketch_dims", True):
        return
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

    def jac(m, p):
        """Screen pixels per sketch mm along x and y at *p*: how a mouse
        drag maps back onto the sketch plane."""
        o, ex, ey = scr(m, p), scr(m, (p[0] + 1, p[1])), \
            scr(m, (p[0], p[1] + 1))
        if None in (o, ex, ey):
            return None
        return ((ex.x() - o.x(), ex.y() - o.y()),
                (ey.x() - o.x(), ey.y() - o.y()))

    def chip(at, text, cont=None, index=None, drag=None):
        tw = fm.horizontalAdvance(text)
        rect = QRectF(at.x() - tw / 2 - 5, at.y() - fm.height() / 2 - 2,
                      tw + 10, fm.height() + 4)
        if cont is not None:
            window._dims3d_hits.append((QRectF(rect), cont, index, drag))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 230)))
        painter.drawRoundedRect(rect, 4, 4)
        painter.setPen(QPen(ink, 1.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawText(rect, int(Qt.AlignCenter), text)

    try:
        seen = _occluder(window)
    except Exception:
        seen = None

    def vis(m, p):
        """Is the sketch point *p* in front of every solid?"""
        return seen is None or seen(_apply(m, (p[0], p[1], 0.0)))

    def seg(m, a, b):
        """A line from *a* to *b* (sketch mm), drawn only where no
        solid stands in front of it (the user: a dimension must never
        show through the part, whatever plane its sketch is on)."""
        n = SEG_SAMPLES if seen is not None else 1
        ps = [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n)
              for i in range(n + 1)]
        ok = [vis(m, p) for p in ps]
        run = None
        for i in range(len(ps)):
            if ok[i] and run is None:
                run = i
            if run is not None and (not ok[i] or i == len(ps) - 1):
                j = i if ok[i] else i - 1
                if j > run:
                    qa, qb = scr(m, ps[run]), scr(m, ps[j])
                    if qa is not None and qb is not None:
                        painter.drawLine(qa, qb)
                run = None

    for cont, m in placed:
        for index, row in enumerate(sc.rows(cont)):
            if "value" not in row:
                continue
            try:
                what, pts = _local(cont, row)
            except (KeyError, ValueError, IndexError, TypeError):
                continue
            if what == "leader":
                at = row.get("leader_at")
                if isinstance(at, (list, tuple)) and len(at) == 2:
                    # dragged: the value sits there, the leader swings to
                    # it through the edge
                    c, e = pts[0], pts[1]
                    r = math.hypot(e[0] - c[0], e[1] - c[1])
                    dx, dy = at[0] - c[0], at[1] - c[1]
                    dl = math.hypot(dx, dy) or 1.0
                    pts = [c, (c[0] + r * dx / dl, c[1] + r * dy / dl),
                           (float(at[0]), float(at[1]))]
                pc, pe, po = (scr(m, p) for p in pts)
                if None not in (pc, pe, po):
                    painter.setPen(pen)
                    seg(m, pts[0], pts[2])
                    painter.setBrush(QBrush(ink))
                    ex, ey = pe.x() - pc.x(), pe.y() - pc.y()
                    el = math.hypot(ex, ey) or 1.0
                    ux, uy = ex / el, ey / el
                    base = QPointF(pe.x() - ux * 8, pe.y() - uy * 8)
                    if vis(m, pts[1]):
                        painter.drawPolygon(QPolygonF([
                            pe, QPointF(base.x() - uy * 3.5,
                                        base.y() + ux * 3.5),
                            QPointF(base.x() + uy * 3.5,
                                    base.y() - ux * 3.5)]))
                    painter.setBrush(Qt.NoBrush)
                    if vis(m, pts[0]):
                        painter.drawEllipse(pc, 2.0, 2.0)
                    if not vis(m, pts[2]):
                        continue
                    chip(po, _text(row), cont, index,
                         dict(kind="leader", jac=jac(m, pts[2]),
                              at=list(pts[2])))
                continue
            if what == "label":
                at = scr(m, pts[0])
                if at is not None and vis(m, pts[0]):
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
                try:
                    node0, _n0 = sc.entity(cont, row["refs"][0])
                    w = float(node0.params.get("width", 0) or 0) \
                        if node0.type == "line" else 0.0
                except (KeyError, ValueError, IndexError, TypeError):
                    w = 0.0
                if w:
                    off = w / 2.0 + OFFSET_MM
                c = _centre(cont, row)
                if c is not None and (c[0] - ax) * nx + (c[1] - ay) * ny > 0:
                    off = -off
            pa, pb = scr(m, (ax, ay)), scr(m, (bx, by))
            oa = scr(m, (ax + nx * off, ay + ny * off))
            ob = scr(m, (bx + nx * off, by + ny * off))
            if None in (pa, pb, oa, ob):
                continue
            la = (ax + nx * off, ay + ny * off)
            lb = (bx + nx * off, by + ny * off)
            painter.setPen(thin)
            seg(m, (ax, ay), la)
            seg(m, (bx, by), lb)
            painter.setPen(pen)
            seg(m, la, lb)
            sx, sy = ob.x() - oa.x(), ob.y() - oa.y()
            sl = math.hypot(sx, sy) or 1.0
            ux, uy = sx / sl, sy / sl
            painter.setBrush(QBrush(ink))
            for tip, sgn, lp in ((oa, 1.0, la), (ob, -1.0, lb)):
                if not vis(m, lp):
                    continue
                base = QPointF(tip.x() + sgn * ux * 8, tip.y() + sgn * uy * 8)
                painter.drawPolygon(QPolygonF([
                    tip, QPointF(base.x() - uy * 3.5, base.y() + ux * 3.5),
                    QPointF(base.x() + uy * 3.5, base.y() - ux * 3.5)]))
            painter.setBrush(Qt.NoBrush)
            if not vis(m, ((la[0] + lb[0]) / 2, (la[1] + lb[1]) / 2)):
                continue
            chip(QPointF((oa.x() + ob.x()) / 2, (oa.y() + ob.y()) / 2),
                 str(row["value"]), cont, index,
                 dict(kind="linear", jac=jac(m, (ax, ay)), n=(nx, ny),
                      offset=off))
    painter.restore()


DRAG_PX = 4

#: rays along each dimension line: it is drawn in pieces where seen
SEG_SAMPLES = 16


def press(window, pos):
    """A press on a dimension's value in the 3D view: a drag moves it out
    of the way (SolidWorks), a click without moving types a new value.
    True when taken."""
    for hit in getattr(window, "_dims3d_hits", []):
        rect, cont, index = hit[:3]
        drag = hit[3] if len(hit) > 3 else None
        if rect.adjusted(-3, -3, 3, 3).contains(pos.x(), pos.y()):
            window._dim3d_drag = dict(rect=rect, cont=cont, index=index,
                                      info=drag, start=pos, moved=False)
            return True
    return False


def _to_local(jac, dx, dy):
    """A screen move (px) as a move in the sketch (mm)."""
    (ax, ay), (bx, by) = jac
    det = ax * by - bx * ay
    if abs(det) < 1e-9:
        return None
    return ((dx * by - bx * dy) / det, (ax * dy - dx * ay) / det)


def move(window, pos):
    d = getattr(window, "_dim3d_drag", None)
    if d is None:
        return False
    dx, dy = pos.x() - d["start"].x(), pos.y() - d["start"].y()
    if not d["moved"] and math.hypot(dx, dy) < DRAG_PX:
        return True
    info = d["info"]
    if not info or not info.get("jac"):
        return True
    local = _to_local(info["jac"], dx, dy)
    if local is None:
        return True
    d["moved"] = True
    row = sc.rows(d["cont"])[d["index"]]
    if info["kind"] == "linear":
        n = info["n"]
        row["offset"] = round(info["offset"] + local[0] * n[0]
                              + local[1] * n[1], 3)
    else:
        row["leader_at"] = [round(info["at"][0] + local[0], 3),
                            round(info["at"][1] + local[1], 3)]
    window.view3d.update()
    return True


def release(window, pos):
    d = getattr(window, "_dim3d_drag", None)
    if d is None:
        return False
    window._dim3d_drag = None
    if d["moved"]:
        cont = d["cont"]
        cont.params[sc.KEY] = sc.rows(cont)
        window.model.node_changed.emit(cont)     # one undo step
    else:
        edit(window, d["rect"], d["cont"], d["index"])
    return True


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
        from .sketch_constrain_ui import _value
        value = _value(text)        # "52 - 10" -> 42; variables kept
        try:
            sc.set_value(window.model, cont, index, value)
        except (ValueError, KeyError, IndexError) as exc:
            window.statusBar().showMessage(str(exc), 5000)
        view.update()
    box.editingFinished.connect(done)
    return box
