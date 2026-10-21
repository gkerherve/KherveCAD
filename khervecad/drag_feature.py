"""Extrude and revolve by DRAGGING in the 3D view (2026-10-21, the user:
"in SolidWorks / Fusion there is an arrow that comes up and we push it up
with the mouse ... and the rotational extrusion too").

After Linear extrude or Rotate extrude (or with one selected and Extrude
▸ Drag selected), the 3D view shows a handle on it:

* a **Linear extrude** gets an arrow on its top face, along its own +Z:
  drag it to pull the solid out — the height follows live;
* a **Rotate extrude** gets a curved arrow at the end of its sweep: drag
  it round to set the angle (up to 360°).

A readout beside the handle gives the height / angle; Ctrl snaps to the
sketch grid / 15°; Esc while dragging puts it back; a press anywhere else
turns the view as always, Esc (idle) or the Select button ends the tool.
It edits the node's own `height` / `angle`, so the program, undo and
every other view stay as they are. The geometry helpers are Qt-free.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from .gumball import HIT_PX, _seg_dist, snap

KINDS = ("linear_extrude", "rotate_extrude")
SIZE_PX = 70
COLOUR = "#1e88e5"
MIN_HEIGHT = 0.01
#: a new extrude's first height, before it is dragged (SolidWorks' 10)
FIRST_HEIGHT = 10.0
#: the mark on the mirror([0, 0, 1]) that makes an extrude go DOWN
REVERSE = "reverse"


def reversed_of(ext):
    """The mirror turning *ext* downwards, if it has one."""
    p = ext.parent
    if p is not None and p.type == "mirror" and len(p.children) == 1 \
            and p.params.get(REVERSE):
        return p
    return None


def set_direction(model, ext, down):
    """Extrude up (+Z) or down: down is a mirror([0, 0, 1]) round it —
    linear_extrude has no negative height."""
    mir = reversed_of(ext)
    if down and mir is None:
        mir = model.wrap_nodes([ext], "mirror")
        mir.params.update(x=0.0, y=0.0, z=1.0)
        mir.params[REVERSE] = True
        model.rename(mir, "Reverse direction")
        model.node_changed.emit(mir)
    elif not down and mir is not None:
        model.ungroup(mir)


def signed_height(ext):
    h = _num(ext.params.get("height", FIRST_HEIGHT), FIRST_HEIGHT)
    return -h if reversed_of(ext) is not None else h


def _num(v, default):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _apply(m, p):
    return tuple(sum(m[r][c] * p[c] for c in range(3)) + m[r][3]
                 for r in range(3))


def _apply_dir(m, d):
    return tuple(sum(m[r][c] * d[c] for c in range(3)) for r in range(3))


def frame(node, scope=None):
    """(matrix to the scope's frame, local tris of the node's content)."""
    from . import mesh
    m = mesh.ancestor_matrix(node, stop=scope)
    try:
        tris = mesh.tessellate(node)
    except Exception:
        tris = []
    return m, tris


def linear_handle(node, m, tris):
    """(base, axis, scale) in scope coordinates: base = the top face's
    centre, axis = the extrusion direction (unit), scale = scope mm per
    local mm along it."""
    pts = [p for t in tris for p in t]
    if not pts:
        return None
    cx = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2
    cy = (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
    top = max(p[2] for p in pts)
    base = _apply(m, (cx, cy, top))
    d = _apply_dir(m, (0.0, 0.0, 1.0))
    s = math.sqrt(sum(c * c for c in d)) or 1.0
    return base, tuple(c / s for c in d), s


def revolve_handle(node, m, tris):
    """(point, tangent, radius) at the END of the sweep, in scope
    coordinates; tangent = d point / d angle (per radian)."""
    pts = [p for t in tris for p in t]
    if not pts:
        return None
    r = max(math.hypot(p[0], p[1]) for p in pts)
    z = (min(p[2] for p in pts) + max(p[2] for p in pts)) / 2
    a = math.radians(_num(node.params.get("angle", 360.0), 360.0))
    p = _apply(m, (r * math.cos(a), r * math.sin(a), z))
    t = _apply_dir(m, (-r * math.sin(a), r * math.cos(a), 0.0))
    return p, t, r


# =================================================================== Qt

def start(window, node=None, quiet=False, created=False):
    """Switch the drag handles on (for *node*, else the selection; a
    selected 2D shape is extruded first). *created*: Cancel removes the
    extrude again."""
    from . import language
    view = window.view3d
    if view.edit_tool is not None and not isinstance(view.edit_tool,
                                                     DragFeature):
        if not quiet:
            window.statusBar().showMessage(language.tr(
                "Finish what the 3D view is doing first (Esc)."), 5000)
        return None
    if node is None:
        from .model import SHAPE_2D
        sel = window.builder.active_tree().selected_nodes()
        if len(sel) == 1 and sel[0].category == SHAPE_2D and \
                _extrude_above(sel[0]) is None:
            node = _new_extrude(window, sel[0])
            created = True
    tool = DragFeature(window, node, created)
    if tool.target() is None:
        if quiet:
            return None
        pick(window)                       # like Fillet: click it in 3D
        return None
    tool.show_buttons()
    view.edit_tool = tool
    view.setMouseTracking(True)
    view.update()
    window.statusBar().showMessage(language.tr(
        "Drag the blue arrow up or down (Ctrl snaps) — OK keeps it, "
        "Cancel or Esc takes it back."), 8000)
    return tool


def _extrude_above(node):
    probe = node.parent
    while probe is not None:
        if probe.type in KINDS:
            return probe
        probe = probe.parent
    return None


def _new_extrude(window, shape):
    model = window.model
    ext = model.wrap_nodes([shape], "linear_extrude")
    model.set_param(ext, "height", FIRST_HEIGHT)
    window.builder.active_tree().select_nodes([ext])
    return ext


def flat_shapes(window):
    """[(2D shape, its triangles in the scope's frame)] — what a click in
    the 3D view can pick to extrude."""
    from . import mesh
    from .model import SHAPE_2D
    scope = window._render_scope()[0] or window.model.root
    stop = None if scope is window.model.root else scope
    out = []
    for n in scope.walk():
        if n is scope or n.category != SHAPE_2D or not n.visible:
            continue
        if n.parent is not None and n.parent.category == SHAPE_2D:
            continue                       # a piece of a 2D boolean
        try:
            tris = mesh.tessellate(n)
        except Exception:
            continue
        if not tris:
            continue
        m = mesh.ancestor_matrix(n, stop=stop)
        out.append((n, [tuple(_apply(m, p) for p in t) for t in tris]))
    return out


def pick(window):
    """Nothing to drag selected: click a 2D shape (rectangle, polygon,
    circle…) in the 3D view — it is extruded and its Z arrow shows (the
    user: "select the shape you want to extrude in the 3D view ... a Z
    appears to put it up or down ... and an OK button"). A shape already
    extruded brings its extrude's arrow back."""
    from . import language
    shapes = flat_shapes(window)
    if not shapes:
        window.statusBar().showMessage(language.tr(
            "No 2D shape in view — draw a rectangle, polygon or circle "
            "first."), 6000)
        return

    def picked(desc, node):
        if desc is None or node is None:
            return
        window.view3d.cancel_pick()
        ext = _extrude_above(node)
        if ext is not None:
            window.builder.active_tree().select_nodes([ext])
            start(window, ext)
        else:
            start(window, _new_extrude(window, node), created=True)

    window.view3d.start_pick(
        picked, groups=shapes,
        banner=language.tr("Click the 2D shape to extrude · Esc cancels"),
        labeler=lambda desc, node: getattr(node, "name", ""))


def action(window):
    act = getattr(window, "_drag_feature_act", None)
    if act is not None:
        return act
    from PyQt5.QtWidgets import QAction
    from . import icons, language, toolbars, tooltips
    tooltips.TIPS.setdefault("drag_extrude", (
        "Drag extrude / revolve",
        "Extrude a 2D shape by dragging, as in SolidWorks and Fusion: "
        "click the shape in the 3D view, then drag its blue Z arrow up or "
        "down. A Rotate extrude gets a curved arrow for its angle.",
        ["Click this, then click a rectangle, polygon or circle in the 3D "
         "view (or select one first).",
         "Drag the arrow up or down — Ctrl snaps to the grid.",
         "OK keeps it; Cancel or Esc takes it back."],
        "Linear extrude and Rotate extrude show the arrow by themselves."))
    act = QAction(icons.icon("mdi.arrow-expand-up"),
                  language.tr("Drag extrude"), window)
    act.setData("drag_extrude")
    toolbars.remember_glyph(act, "mdi.arrow-expand-up", "extrude")
    tooltips.apply(act, "drag_extrude")
    act.triggered.connect(lambda _=False: start(window))
    window._drag_feature_act = act
    return act


class DragFeature:
    """View3D.edit_tool: the extrude arrow / revolve arc."""

    def __init__(self, window, node=None, created=False):
        self.window = window
        self.view = window.view3d
        self.fixed = node
        self.drag = None
        self.hover = False
        self.created = created
        self.buttons = []
        ext = self.target()
        self.original = None if ext is None else (
            ext, signed_height(ext) if ext.type == "linear_extrude"
            else _num(ext.params.get("angle", 360.0), 360.0))

    def show_buttons(self):
        """OK / Cancel over the 3D view, like Fillet's Done."""
        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QPushButton
        from . import language
        styles = {"ok": "#2e7d32", "cancel": "#6d6d6d"}
        for key, text, slot in (("ok", "✓  " + language.tr("OK"), self.ok),
                                ("cancel", "✕  " + language.tr("Cancel"),
                                 self.cancel)):
            b = QPushButton(text, self.view)
            b.setCursor(Qt.ArrowCursor)
            b.setStyleSheet(
                "QPushButton { background: %s; color: white; border-radius:"
                " 4px; padding: 4px 14px; font-weight: bold; }" % styles[key])
            b.clicked.connect(slot)
            b.adjustSize()
            self.buttons.append(b)
        total = sum(b.width() for b in self.buttons) + 10
        x = (self.view.width() - total) // 2
        for b in self.buttons:
            b.move(x, 40)
            b.show()
            b.raise_()
            x += b.width() + 10

    def ok(self):
        from . import language
        ext = self.target()
        self.exit()
        if ext is not None:
            self.window.statusBar().showMessage(language.tr(
                "{name} kept.").format(name=ext.name), 4000)

    def cancel(self):
        """Take it back: a new extrude goes, an old one gets its height
        and direction back."""
        model = self.window.model
        if self.original is not None:
            ext, value = self.original
            if ext.type == "linear_extrude":
                set_direction(model, ext, False)
                if self.created:
                    shape = ext.children[0] if ext.children else None
                    model.ungroup(ext)
                    if shape is not None:
                        self.window.builder.active_tree().select_nodes(
                            [shape])
                else:
                    set_direction(model, ext, value < 0)
                    model.set_param(ext, "height", abs(value))
            else:
                model.set_param(ext, "angle", value)
        self.drag = None
        self.exit()

    def target(self):
        node = self.fixed
        if node is None or node.parent is None:
            nodes = self.window.builder.active_tree().selected_nodes()
            node = nodes[0] if len(nodes) == 1 else None
            self.fixed = None
        probe = node
        while probe is not None and probe.type not in KINDS:
            probe = probe.parent
        return probe

    def _scope(self):
        scope = self.window._render_scope()[0]
        return None if scope is None or scope is self.window.model.root \
            else scope

    def _project(self):
        v = self.view
        eye, right, up, forward = v._camera()
        return lambda p: v._project(eye, right, up, forward, p)

    def _screen(self):
        node = self.target()
        if node is None:
            return None
        project = self._project()
        if node.type == "linear_extrude":
            # the frame BEFORE a reverse mirror, so up stays up
            from . import mesh
            holder = reversed_of(node) or node
            m = mesh.ancestor_matrix(holder, stop=self._scope())
            try:
                tris = mesh.tessellate(node)
            except Exception:
                tris = []
            got = linear_handle(node, m, tris)
            if got is None:
                return None
            _base, axis, scale = got
            pts = [p for t in tris for p in t]
            cx = (min(p[0] for p in pts) + max(p[0] for p in pts)) / 2
            cy = (min(p[1] for p in pts) + max(p[1] for p in pts)) / 2
            sh = signed_height(node)
            if node.params.get("center"):
                sh /= 2.0
            sign = -1.0 if sh < 0 else 1.0
            base = _apply(m, (cx, cy, sh))
            bs = project(base)
            if bs is None:
                return None              # behind the camera
            length = SIZE_PX * max(bs[2], 1e-6) / self.view._focal()
            up = project(tuple(base[k] + axis[k] * length
                               for k in range(3)))
            tip = project(tuple(base[k] + sign * axis[k] * length
                                for k in range(3)))
            if tip is None or up is None:
                return None
            return dict(node=node, kind="linear", a=bs, b=tip, up=up,
                        length=length, scale=scale)
        m, tris = frame(node, self._scope())
        got = revolve_handle(node, m, tris)
        if got is None:
            return None
        p, t, _r = got
        ps = project(p)
        if ps is None:
            return None
        # the screen tangent per radian, measured over a small step
        step = 0.05
        qs = project(tuple(p[k] + t[k] * step for k in range(3)))
        if qs is None:
            return None
        per = ((qs[0] - ps[0]) / step, (qs[1] - ps[1]) / step)
        norm = math.hypot(*per) or 1.0
        tip = (ps[0] + per[0] / norm * 40, ps[1] + per[1] / norm * 40,
               ps[2])
        return dict(node=node, kind="revolve", a=ps, b=tip, per=per)

    def _hit(self, x, y, scr):
        return _seg_dist((x, y), scr["a"][:2], scr["b"][:2]) <= HIT_PX + 3

    # -- the view's hooks ------------------------------------------------
    def wants_key(self, event):
        from PyQt5.QtCore import Qt
        return event.key() == Qt.Key_Escape

    def key_press(self, event):
        from PyQt5.QtCore import Qt
        if event.key() != Qt.Key_Escape:
            return False
        if self.drag is not None:
            self._restore_drag(self.drag)
            self.drag = None
        else:
            self.cancel()
        self.view.update()
        return True

    def exit(self):
        for b in self.buttons:
            b.hide()
            b.deleteLater()
        self.buttons = []
        if self.view.edit_tool is self:
            self.view.edit_tool = None
            self.view.setMouseTracking(False)
            self.view.update()

    def mouse_press(self, event):
        from PyQt5.QtCore import Qt
        if event.button() != Qt.LeftButton:
            return False
        scr = self._screen()
        if scr is None or not self._hit(event.pos().x(), event.pos().y(),
                                        scr):
            return False
        node = scr["node"]
        param = "height" if scr["kind"] == "linear" else "angle"
        start = signed_height(node) if param == "height" else \
            _num(node.params.get("angle", 360.0), 360.0)
        self.drag = dict(scr, param=param, start=start,
                         press=(event.pos().x(), event.pos().y()),
                         value=start)
        return True

    def mouse_move(self, event):
        from PyQt5.QtCore import Qt
        x, y = event.pos().x(), event.pos().y()
        d = self.drag
        if d is None:
            scr = self._screen()
            hover = bool(scr and self._hit(x, y, scr))
            if hover != self.hover:
                self.hover = hover
                self.view.update()
            return False
        ctrl = bool(event.modifiers() & Qt.ControlModifier)
        dx, dy = x - d["press"][0], y - d["press"][1]
        if d["kind"] == "linear":
            # along +Z of the sketch, whichever way the arrow points now
            sx, sy = d["up"][0] - d["a"][0], d["up"][1] - d["a"][1]
            px = math.hypot(sx, sy) or 1.0
            world = (dx * sx + dy * sy) / px / px * d["length"]
            delta = world / d["scale"]
            if d["node"].params.get("center"):
                delta *= 2.0                # both ends move
            value = d["start"] + delta
            if ctrl:
                value = snap(value, self._grid())
            if abs(value) < MIN_HEIGHT:
                value = MIN_HEIGHT if d["start"] >= 0 else -MIN_HEIGHT
        else:
            per = d["per"]
            n2 = per[0] * per[0] + per[1] * per[1] or 1.0
            value = d["start"] + math.degrees((dx * per[0] + dy * per[1])
                                              / n2)
            if ctrl:
                value = snap(value, 15.0)
            value = max(1.0, min(360.0, value))
        d["value"] = round(value, 4)
        if d["param"] == "height":
            self._set_height(d["node"], d["value"])
        else:
            self._set(d["node"], d["param"], d["value"])
        return True

    def _set_height(self, ext, signed):
        set_direction(self.window.model, ext, signed < 0)
        self._set(ext, "height", round(abs(signed), 4))

    def _restore_drag(self, d):
        if d["param"] == "height":
            self._set_height(d["node"], d["start"])
        else:
            self._set(d["node"], d["param"], d["start"])

    def mouse_release(self, event):
        d, self.drag = self.drag, None
        if d is None:
            return False
        from . import language
        self.window.statusBar().showMessage(
            language.tr("Height {v:g} mm").format(v=d["value"])
            if d["param"] == "height" else
            language.tr("Angle {v:g}°").format(v=d["value"]), 5000)
        self.view.update()
        return True

    def wheel(self, event):
        return False

    def _grid(self):
        scene = getattr(self.window, "scene", None)
        try:
            return float(getattr(scene, "grid_size", 1.0)) or 1.0
        except (TypeError, ValueError):
            return 1.0

    def _set(self, node, param, value):
        self.window.model.set_param(node, param, value)

    # -- drawing -----------------------------------------------------
    def paint(self, painter, project):
        try:
            self._paint(painter)
        except Exception:      # never out of a paint: Qt would abort
            pass

    def _paint(self, painter):
        from PyQt5.QtCore import QPointF, Qt
        from PyQt5.QtGui import QColor, QFont, QPen, QPolygonF
        scr = self._screen()
        if scr is None or scr["a"][2] <= 0:
            return
        hot = self.hover or self.drag is not None
        col = QColor(COLOUR)
        painter.setRenderHint(painter.Antialiasing, True)
        a, b = scr["a"], scr["b"]
        painter.setPen(QPen(col.lighter(125) if hot else col,
                            4.5 if hot else 3))
        if scr["kind"] == "revolve":
            # a short arc ahead of the sweep's end
            per = scr["per"]
            n = math.hypot(*per) or 1.0
            ux, uy = per[0] / n, per[1] / n
            pts = [QPointF(a[0] + ux * 40 * f - uy * 6 * f * f,
                           a[1] + uy * 40 * f + ux * 6 * f * f)
                   for f in [i / 8 for i in range(9)]]
            painter.drawPolyline(QPolygonF(pts))
            tip, back = pts[-1], pts[-2]
        else:
            painter.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))
            tip, back = QPointF(b[0], b[1]), QPointF(a[0], a[1])
        dx, dy = tip.x() - back.x(), tip.y() - back.y()
        ln = math.hypot(dx, dy) or 1.0
        ux, uy = dx / ln, dy / ln
        painter.setBrush(col)
        painter.drawPolygon(QPolygonF([
            QPointF(tip.x() + ux * 13, tip.y() + uy * 13),
            QPointF(tip.x() - uy * 7, tip.y() + ux * 7),
            QPointF(tip.x() + uy * 7, tip.y() - ux * 7)]))
        painter.setPen(QPen(QColor("#ffffff"), 1.5))
        painter.drawEllipse(QPointF(a[0], a[1]), 5, 5)
        painter.setBrush(Qt.NoBrush)
        node = scr["node"]
        if scr["kind"] == "linear":
            text = "%g mm" % round(signed_height(node), 3)
        else:
            text = "%g°" % round(_num(node.params.get("angle", 360), 360),
                                 2)
        font = QFont(painter.font())
        font.setBold(True)
        painter.setFont(font)
        fm = painter.fontMetrics()
        w = fm.horizontalAdvance(text) + 12
        x0, y0 = int(b[0]) + 16, int(b[1]) - 12
        painter.fillRect(x0, y0, w, fm.height() + 6,
                         QColor(255, 255, 255, 230))
        painter.setPen(col.darker(140))
        painter.drawText(x0 + 6, y0 + 3 + fm.ascent(), text)
