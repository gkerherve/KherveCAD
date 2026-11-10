# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""Feature dimensions on the 3D view, as SolidWorks shows a Boss-Extrude's
depth or a Revolve's angle beside the sketch's Smart Dimensions
(2026-11-10, the user: "a dimension that comes from a linear extrude ...
from a rotation extrude").

A selected Linear extrude shows its Distance (and Distance 2 when it goes
both ways) as a dimension along its axis at the profile's side; a
selected Rotate extrude shows its angle as an arc round its axis. A click
on the number types a new value (dim_link's editor: Enter keeps it, a
click on another dimension meanwhile links to it). While any dimension is
being typed, every feature in view shows its dimensions so they can be
clicked to link. A value driven by an expression reads "Σ 10", as
SolidWorks marks an equation.

`dimensions(window)` -> [(node, key, label, world points)] is what is
drawn; `paint` draws it and fills `window._feature_dim_hits` [(rect,
node, key)]; `press` / `release` open the editor."""

import math

FEATURES = ("linear_extrude", "rotate_extrude")
INK = "#6a1b9a"                 # set apart from the sketch's blue
#: the dimension line stands this far out from the profile, of its size
GAP = 0.18


def _env(window):
    from .anchors import doc_env
    return doc_env(window.model)


def _num(node, key, env, default):
    from . import expr
    try:
        return float(expr.resolve(node.params.get(key, default), env,
                                  default))
    except (TypeError, ValueError):
        return default


def _features_of(node):
    """The extrudes / revolves a selected node stands for: itself, or the
    ones a sketch Group or a wrapper holds directly."""
    if node.type in FEATURES:
        return [node]
    out = []
    stack = list(node.children)
    while stack:
        n = stack.pop()
        if n.type in FEATURES:
            out.append(n)
            continue
        if n.category != "2d" and n.children:
            stack.extend(n.children)
    return out


def shown_features(window):
    """The features whose dimensions are drawn now."""
    model = window.model
    scope = window._render_scope()[0]
    editing = getattr(window.view3d, "_dim3d_editor", None) is not None
    if editing:
        # typing a value: every feature in view can be clicked to link
        return [n for n in scope.walk() if n.type in FEATURES
                and n.visible]
    out = []
    for nid in getattr(window, "_selected_ids", ()) or ():
        node = model.find(nid)
        if node is None:
            continue
        for f in _features_of(node):
            if f not in out:
                out.append(f)
    return out[:12]


def _frame(window, node, own):
    """Matrix from *node*'s frame (with its own transform when *own*) to
    the world the view draws."""
    from . import mesh
    scope = window._render_scope()[0]
    iso = scope if scope is not window.model.root else None
    env = _env(window)
    with window._isolated_frame(iso):
        m = mesh.ancestor_matrix(node, env, stop=iso)
        if own:
            m = mesh.mat_mul(m, mesh.node_matrix(node, env))
    return m


def _box(node, env):
    from . import mesh
    pts = [p for loop in mesh.collect_outlines(node, env) for p in loop]
    if not pts:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def text(node, key, value):
    from . import units
    raw = node.params.get(key)
    try:
        dec = units.DIM_DECIMALS
    except AttributeError:
        dec = 2
    shown = ("%.*f" % (dec, value)).rstrip("0").rstrip(".")
    if key == "angle":
        shown += "°"
    if isinstance(raw, str):
        try:
            float(raw)
        except ValueError:
            shown = "Σ " + shown         # driven by an expression
    return shown


def dimensions(window):
    """[(node, key, label, kind, points)]: *kind* "linear" with points
    (a0, a1, d0, d1) — the two ends on the part and on the dimension line
    — or "angle" with the arc's points."""
    from . import mesh
    env = _env(window)
    out = []
    for node in shown_features(window):
        box = _box(node, env)
        if box is None:
            continue
        x0, y0, x1, y1 = box
        size = max(x1 - x0, y1 - y0, 1e-3)
        if node.type == "linear_extrude":
            m = _frame(window, node, own=True)
            h = _num(node, "height", env, 10.0)
            h2 = _num(node, "height2", env, 0.0)
            centre = bool(node.params.get("center"))
            gap = GAP * size
            px = x1 + gap

            def run(za, zb):
                return [mesh.mat_apply(m, p) for p in (
                    (x1, y0, za), (x1, y0, zb), (px, y0, za), (px, y0, zb))]
            if centre:
                out.append((node, "height", text(node, "height", h),
                            "linear", run(-h / 2.0, h / 2.0)))
            else:
                out.append((node, "height", text(node, "height", h),
                            "linear", run(0.0, h)))
                if h2 > 1e-9:
                    out.append((node, "height2", text(node, "height2", h2),
                                "linear", run(-h2, 0.0)))
        else:
            # the revolve turns its profile (x the radius, y along the
            # axis) about its parent's Z
            m = _frame(window, node, own=False)
            a = _num(node, "angle", env, 360.0)
            r = max(abs(x0), abs(x1)) * (1.0 + GAP)
            z = (y0 + y1) / 2.0
            steps = max(8, int(abs(a) / 6))
            arc = [mesh.mat_apply(m, (r * math.cos(math.radians(a * i / steps)),
                                      r * math.sin(math.radians(a * i / steps)),
                                      z)) for i in range(steps + 1)]
            out.append((node, "angle", text(node, "angle", a), "angle", arc))
    return out


def paint(window, painter, project):
    from PyQt5.QtCore import QPointF, QRectF, Qt
    from PyQt5.QtGui import QBrush, QColor, QFont, QPen, QPolygonF
    window._feature_dim_hits = []
    if not getattr(window.scene, "show_sketch_dims", True):
        return
    try:
        dims = dimensions(window)
    except Exception:                         # never break the paint
        import traceback
        traceback.print_exc()
        return
    if not dims:
        return
    ink = QColor(INK)
    pen = QPen(ink, 1.4)
    pen.setCosmetic(True)
    thin = QPen(ink, 1.0, Qt.DashLine)
    thin.setCosmetic(True)
    font = QFont(painter.font())
    font.setBold(True)
    font.setPointSize(max(8, font.pointSize()))
    painter.save()
    painter.setRenderHint(painter.Antialiasing, True)
    painter.setFont(font)
    fm = painter.fontMetrics()

    def scr(p):
        q = project(p)
        return None if q is None else QPointF(q[0], q[1])

    def arrow(tip, frm):
        dx, dy = tip.x() - frm.x(), tip.y() - frm.y()
        L = math.hypot(dx, dy) or 1.0
        ux, uy = dx / L, dy / L
        base = QPointF(tip.x() - ux * 8, tip.y() - uy * 8)
        painter.setBrush(QBrush(ink))
        painter.drawPolygon(QPolygonF([
            tip, QPointF(base.x() - uy * 3.5, base.y() + ux * 3.5),
            QPointF(base.x() + uy * 3.5, base.y() - ux * 3.5)]))
        painter.setBrush(Qt.NoBrush)

    for node, key, label, kind, pts in dims:
        q = [scr(p) for p in pts]
        if kind == "linear" and any(p is None for p in q):
            continue
        if kind != "linear":
            q = [p for p in q if p is not None]   # the part in view
            if len(q) < 2:
                continue
        if kind == "linear":
            a0, a1, d0, d1 = q
            painter.setPen(thin)
            painter.drawLine(a0, d0)
            painter.drawLine(a1, d1)
            painter.setPen(pen)
            painter.drawLine(d0, d1)
            arrow(d0, d1)
            arrow(d1, d0)
            at = QPointF((d0.x() + d1.x()) / 2, (d0.y() + d1.y()) / 2)
        else:
            painter.setPen(pen)
            for p, r in zip(q, q[1:]):
                painter.drawLine(p, r)
            if len(q) > 1:
                arrow(q[-1], q[-2])
            at = q[len(q) // 2]
        tw = fm.horizontalAdvance(label)
        rect = QRectF(at.x() - tw / 2 - 5, at.y() - fm.height() / 2 - 2,
                      tw + 10, fm.height() + 4)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 235)))
        painter.drawRoundedRect(rect, 4, 4)
        painter.setPen(QPen(ink, 1.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, 4, 4)
        painter.drawText(rect, int(Qt.AlignCenter), label)
        window._feature_dim_hits.append((QRectF(rect), node, key))
    painter.restore()


def hit(window, pos):
    for rect, node, key in getattr(window, "_feature_dim_hits", []):
        if rect.adjusted(-3, -3, 3, 3).contains(pos.x(), pos.y()):
            return rect, node, key
    return None


def press(window, pos):
    got = hit(window, pos)
    if got is None:
        return False
    window._feature_dim_press = got
    return True


def release(window, pos):
    got = getattr(window, "_feature_dim_press", None)
    if got is None:
        return False
    window._feature_dim_press = None
    edit(window, *got)
    return True


def edit(window, rect, node, key):
    """Type a new depth / angle on the model."""
    from . import dim_link
    from .sketch_constrain_ui import _value
    raw = node.params.get(key, "")

    def commit(typed):
        value = _value(typed)
        window.model.set_param(node, key, value)
    return dim_link.open_editor(window, rect, str(raw), commit,
                                ("feature", node, key))
