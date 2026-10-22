"""Resize a selected cylinder in the 3D view (2026-10-22, the user: "when
we press on a cylinder we should see it if it's in a difference, and
change its length and its radius on the screen — the bottom radius and
the top radius").

Selecting a cylinder shows three handles on it: **H** on the top face
(drag along the axis: height), **R bottom** and **R top** on the rims
(drag outwards: each radius). While dragging a see-through copy shows
the new size and a readout the new value; the model changes once, on
release (no difference is re-cut under the mouse). Values land on a
tenth (0.1). A cylinder a difference cuts away is drawn see-through red
so it can be found at all.

`CylinderTool` is a `View3D.edit_tool`; `follow_selection` puts it up
and takes it down with the selection.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

HIT_PX = 10
#: handle -> (param, label)
HANDLES = {"height": ("height", "H"),
           "r1": ("radius_bottom", "R bottom"),
           "r2": ("radius_top", "R top")}
COLOURS = {"height": "#1e88e5", "r1": "#e53935", "r2": "#43a047"}


def _num(v, default=0.0):
    from .expr import resolve
    try:
        return float(resolve(v, {}, default))
    except (TypeError, ValueError):
        return default


def _apply_m(m, p):
    return tuple(sum(m[i][k] * p[k] for k in range(3)) + m[i][3]
                 for i in range(3))


def _lin(m, v):
    return tuple(sum(m[i][k] * v[k] for k in range(3)) for i in range(3))


def _unit(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / n for c in v)


def draw_solid(painter, view, project, tris, rgb, opacity, matrix=None):
    """A ghost that reads as a solid: every facet shaded by how squarely
    it faces the camera, painted far to near into its own layer (no
    seams between facets), the layer laid down at *opacity* (the user:
    the see-through copy looked broken and too faint)."""
    from PyQt5.QtCore import QPointF, Qt
    from PyQt5.QtGui import QColor, QImage, QPainter, QPen, QPolygonF
    if not tris:
        return
    _eye, _right, _up, fwd = view._camera()
    faces = []
    step = max(1, len(tris) // 20000)
    for t in tris[::step]:
        w = [_apply_m(matrix, p) if matrix else tuple(p[:3])
             for p in t[:3]]
        ss = [project(p) for p in w]
        if any(s is None or s[2] <= 0 for s in ss):
            continue
        e1 = [w[1][k] - w[0][k] for k in range(3)]
        e2 = [w[2][k] - w[0][k] for k in range(3)]
        n = _unit((e1[1] * e2[2] - e1[2] * e2[1],
                   e1[2] * e2[0] - e1[0] * e2[2],
                   e1[0] * e2[1] - e1[1] * e2[0]))
        lit = abs(sum(n[k] * fwd[k] for k in range(3)))
        depth = sum(s[2] for s in ss) / 3.0
        faces.append((depth, lit, ss))
    if not faces:
        return
    faces.sort(key=lambda f: -f[0])            # far first
    dev = painter.device()
    ratio = dev.devicePixelRatioF() if hasattr(dev, "devicePixelRatioF") \
        else 1.0
    img = QImage(int(dev.width() * ratio), int(dev.height() * ratio),
                 QImage.Format_ARGB32_Premultiplied)
    img.setDevicePixelRatio(ratio)
    img.fill(Qt.transparent)
    layer = QPainter(img)
    layer.setRenderHint(QPainter.Antialiasing, True)
    for _d, lit, ss in faces:
        k = 0.55 + 0.45 * lit
        col = QColor(int(rgb[0] * k), int(rgb[1] * k), int(rgb[2] * k))
        layer.setPen(QPen(col, 0.8))           # closes the hairline seams
        layer.setBrush(col)
        layer.drawPolygon(QPolygonF([QPointF(s[0], s[1]) for s in ss]))
    layer.end()
    painter.save()
    painter.resetTransform()
    painter.setOpacity(opacity)
    painter.drawImage(0, 0, img)
    painter.restore()


class CylinderTool:
    """The cylinder's size handles; declines everything else, so the
    view orbits as usual."""

    auto = True

    def __init__(self, window, node):
        self.window = window
        self.view = window.view3d
        self.node = node
        self.drag = None
        self.hover = None

    # -- geometry ------------------------------------------------------
    def params(self, extra=None):
        p = self.node.params
        out = dict(height=_num(p.get("height"), 1.0),
                   radius_bottom=_num(p.get("radius_bottom")),
                   radius_top=_num(p.get("radius_top")),
                   x=_num(p.get("x")), y=_num(p.get("y")),
                   z=_num(p.get("z")),
                   center=bool(p.get("center")))
        out.update(extra or {})
        return out

    def _frame(self):
        from .mesh import ancestor_matrix
        return ancestor_matrix(
            self.node, stop=self.window.builder.isolated_component())

    def _side(self, a):
        """The cylinder's local direction that reads as 'right' on
        screen: where the radius handles sit."""
        from . import physics
        _eye, right, _up, _fwd = self.view._camera()
        ai = physics._invert(a)
        d = _lin(ai, right)
        d = (d[0], d[1], 0.0)
        if abs(d[0]) + abs(d[1]) < 1e-9:
            d = (1.0, 0.0, 0.0)
        return _unit(d)

    def points(self, extra=None):
        """World points: bottom centre, top centre and each handle,
        with the world direction each handle drags along."""
        q = self.params(extra)
        a = self._frame()
        z0 = q["z"] - (q["height"] / 2 if q["center"] else 0.0)
        z1 = z0 + q["height"]
        s = self._side(a)
        bc = (q["x"], q["y"], z0)
        tc = (q["x"], q["y"], z1)
        out = dict(
            bottom=_apply_m(a, bc), top=_apply_m(a, tc),
            height=(_apply_m(a, tc), _unit(_lin(a, (0, 0, 1)))),
            r1=(_apply_m(a, (bc[0] + s[0] * q["radius_bottom"],
                             bc[1] + s[1] * q["radius_bottom"], z0)),
                _unit(_lin(a, s))),
            r2=(_apply_m(a, (tc[0] + s[0] * q["radius_top"],
                             tc[1] + s[1] * q["radius_top"], z1)),
                _unit(_lin(a, s))))
        return out

    def _project(self):
        v = self.view
        eye, right, up, forward = v._camera()
        return lambda p: v._project(eye, right, up, forward, p)

    def value_for(self, key, along_px, d):
        """The new param value for a drag *along_px* pixels along the
        handle's screen direction."""
        start = d["start"]
        mm = along_px / max(d["px_per_mm"], 1e-9)
        if key == "height" and self.params()["center"]:
            mm *= 2.0                 # a centred cylinder grows both ways
        return max(0.1 if key == "height" else 0.0,
                   round(start + mm, 1) + 0.0)

    # -- the view's hooks --------------------------------------------
    def _hit(self, x, y):
        project = self._project()
        pts = self.points()
        best = None
        for key in HANDLES:
            s = project(pts[key][0])
            if s is None or s[2] <= 0:
                continue
            dist = math.hypot(x - s[0], y - s[1])
            if dist <= HIT_PX and (best is None or dist < best[0]):
                best = (dist, key)
        return best[1] if best else None

    def wants_key(self, event):
        from PyQt5.QtCore import Qt
        return event.key() == Qt.Key_Escape and self.drag is not None

    def key_press(self, event):
        from PyQt5.QtCore import Qt
        if event.key() == Qt.Key_Escape and self.drag is not None:
            self.drag = None
            self.view.update()
            return True
        return False

    def mouse_press(self, event):
        from PyQt5.QtCore import Qt
        if event.button() != Qt.LeftButton or \
                getattr(self.view, "_pick_cb", None) is not None:
            return False
        key = self._hit(event.pos().x(), event.pos().y())
        if key is None:
            return False
        project = self._project()
        point, direction = self.points()[key]
        s0 = project(point)
        s1 = project(tuple(point[k] + direction[k] for k in range(3)))
        sx, sy = s1[0] - s0[0], s1[1] - s0[1]
        px = math.hypot(sx, sy) or 1e-9
        param = HANDLES[key][0]
        self.drag = dict(key=key, param=param,
                         start=self.params()[param],
                         press=(event.pos().x(), event.pos().y()),
                         dir=(sx / px, sy / px), px_per_mm=px,
                         value=None)
        return True

    def mouse_move(self, event):
        d = self.drag
        x, y = event.pos().x(), event.pos().y()
        if d is None:
            hover = self._hit(x, y)
            if hover != self.hover:
                self.hover = hover
                self.view.update()
            return False
        along = (x - d["press"][0]) * d["dir"][0] + \
            (y - d["press"][1]) * d["dir"][1]
        d["value"] = self.value_for(d["key"], along, d)
        self.view.update()
        return True

    def mouse_release(self, event):
        d, self.drag = self.drag, None
        if d is None:
            return False
        if d["value"] is not None and d["value"] != d["start"]:
            self.window.model.set_param(self.node, d["param"], d["value"])
        self.view.update()
        return True

    def wheel(self, event):
        return False

    # -- drawing -----------------------------------------------------
    def _ghost(self, painter, project, extra, colour):
        from .mesh import cylinder_mesh
        q = self.params(extra)
        q["segments"] = 64
        draw_solid(painter, self.view, project, cylinder_mesh(q),
                   colour[:3], 0.72, matrix=self._frame())

    def paint(self, painter, project):
        from PyQt5.QtCore import QPointF
        from PyQt5.QtGui import QColor, QPen
        from .gumball import _cut_away, _tag
        if getattr(self.view, "_pick_cb", None) is not None:
            return
        if self.node.parent is None:
            return
        d = self.drag
        extra = {d["param"]: d["value"]} if d and d["value"] is not None \
            else None
        painter.setRenderHint(painter.Antialiasing, True)
        if extra:
            self._ghost(painter, project, extra, (30, 136, 229, 110))
        elif _cut_away(self.node):
            self._ghost(painter, project, None, (229, 57, 53, 90))
        pts = self.points(extra)
        b, t = project(pts["bottom"]), project(pts["top"])
        if b and t and b[2] > 0 and t[2] > 0:
            painter.setPen(QPen(QColor(COLOURS["height"]), 1.5))
            painter.drawLine(QPointF(b[0], b[1]), QPointF(t[0], t[1]))
        for key, (param, label) in HANDLES.items():
            point = project(pts[key][0])
            if point is None or point[2] <= 0:
                continue
            col = QColor(COLOURS[key])
            hot = (d and d["key"] == key) or self.hover == key
            painter.setPen(QPen(QColor("#ffffff"), 1.5))
            painter.setBrush(col.lighter(120) if hot else col)
            r = 7 if hot else 5.5
            painter.drawEllipse(QPointF(point[0], point[1]), r, r)
            value = extra.get(param) if extra and param in extra \
                else self.params()[param]
            _tag(painter, point[0] + 14, point[1] - 12,
                 "%s %g" % (label, value), col)
        if d and d["value"] is not None:
            label = HANDLES[d["key"]][1]
            point = project(pts[d["key"]][0])
            if point:
                _tag(painter, point[0] + 14, point[1] + 14,
                     "%s  %g  →  %g" % (label, d["start"], d["value"]),
                     QColor(COLOURS[d["key"]]))


def follow_selection(window, nodes):
    """A lone selected cylinder gets its handles; anything else takes
    handles that came that way down."""
    view = window.view3d
    tool = view.edit_tool
    node = nodes[0] if len(nodes) == 1 else None
    want = node is not None and node.type == "cylinder"
    if isinstance(tool, CylinderTool):
        if tool.drag is not None:
            return
        if want and tool.node is node:
            return
        view.edit_tool = None
        tool = None
        view.update()
    if want and tool is None and getattr(view, "_pick_cb", None) is None:
        view.edit_tool = CylinderTool(window, node)
        view.setMouseTracking(True)
        view.update()
