"""Sketch relations and Smart Dimensions IN the 3D view (2026-11-01,
the user: "I want to be able to use the constraints in 3D mode too —
clicking a constraint switched straight to 2D").

A constraint tool chosen while the 3D model shows (not sketching) runs
here as a `View3D.edit_tool`: every sketch's points, lines, rectangle
sides, circles and slot ends are projected onto the screen; the one
under the mouse lights up (what a click would take), clicks collect the
picks the relation needs — from one sketch, like the 2D tool — and the
relation or dimension is added with the 2D tool's own rules
(sketch_constrain_ui: `_wants`, `finish`'s adjustments, `_smart`). What
a solid hides is not offered. A drag still turns the view; Esc / a
right click drops the picks, a second Esc ends the tool.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from . import sketch_constraints as sc

#: how near (px) the mouse must be to take an entity
PICK_PX = 9.0
#: a point beats a curve this close to it
POINT_PX = 7.0
#: how far a press may move and still be a click (px)
CLICK_PX = 4


def _mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)]
            for i in range(4)]


def _apply(m, p):
    return tuple(m[i][0] * p[0] + m[i][1] * p[1] + m[i][3]
                 for i in range(3))


def sketches(window):
    """[(container, 4x4 to the world)] of the sketches in view."""
    from . import mesh
    root = window._render_scope()[0]
    iso = root if root is not window.model.root else None
    out = []
    with window._isolated_frame(iso):
        for c in root.walk():
            if not any(k.type in sc.SHAPES and k.visible
                       for k in c.children):
                continue
            try:
                m = _mul(mesh.ancestor_matrix(c, {}, stop=iso),
                         mesh.node_matrix(c, {}))
            except Exception:
                continue
            out.append((c, m))
    return out


def _seg_px(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    n2 = dx * dx + dy * dy
    t = 0.0 if n2 < 1e-12 else max(0.0, min(1.0, (
        (p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / n2))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy), t


class Constrain3D:
    """The edit tool (see the module's docstring)."""

    def __init__(self, window, tool):
        from . import sketch_constrain_ui as ui
        self.window = window
        self.view = window.view3d
        self.tool = tool
        self.kind = tool[len(ui.PREFIX):]
        self.picks = []                 # (node, entity, kind)
        self.hover = None
        self._down = None
        self._seen = None

    # ------------------------------------------------------- geometry
    def _project(self):
        v = self.view
        cam = v._camera()
        return lambda p: v._project(*cam, p)

    def _occluder(self):
        if self._seen is None:
            from . import sketch_dims3d
            try:
                self._seen = sketch_dims3d._occluder(self.window)
            except Exception:
                self._seen = lambda p: True
        return self._seen

    def _shapes(self, cont):
        return [k for k in cont.children if k.type in sc.SHAPES
                and k.visible]

    def entities(self):
        """[(node, entity, kind, world geometry)] of every sketch."""
        from . import sketch_constrain_ui as ui
        out = []
        for cont, m in sketches(self.window):
            for node in self._shapes(cont):
                for name, kind in ui._entities(node):
                    try:
                        if kind == "point":
                            g = _apply(m, sc._point(node, name, {}))
                        elif kind == "line":
                            a, b = sc._line(node, name, {})
                            g = (_apply(m, a), _apply(m, b))
                        else:
                            c, r = sc._circle(node, name, {})
                            a0, sweep = ui._end_arc(node, name)
                            g = [_apply(m, (c[0] + r * math.cos(
                                a0 + sweep * i / 48), c[1] + r * math.sin(
                                    a0 + sweep * i / 48))) for i in range(49)]
                    except (KeyError, ValueError, IndexError, TypeError):
                        continue
                    out.append((node, name, kind, g))
        return out

    def _allowed(self):
        """Which kinds the next click may take."""
        from . import sketch_constrain_ui as ui
        if self.kind == "dimension":
            return ("point", "line", "circle")
        want = ui._wants(self.kind, self.picks)
        if want is None:
            return ("point", "line", "circle")
        if want == "curve":
            return ("line", "circle")
        return (want,)

    def _working_on(self):
        """The container of the sketch being drawn or extruded, if any."""
        w = self.window
        sk = getattr(w, "_sketch3d_tool", None)
        if sk is not None:
            return sk.holder or sk.group
        drag = getattr(w, "_drag_paused", None)
        return drag.target() if drag is not None else None

    def _face_info(self, parent):
        """The face's outline for *parent*'s sketch: (group, info)."""
        from . import face_outline, face_sketch
        group = face_sketch.group_of(parent) if parent is not None else None
        if group is None or group.parent is None:
            return None, {}
        scene = self.window.view2d.scene()
        if getattr(self, "_face_for", None) is not group:
            self._face_for = group
            part = face_sketch.part_of(group)
            if part is not None:
                face_outline.show(self.window, group, part)
        return group, getattr(scene, "face_outline", None) or {}

    def model_near(self, x, y, parent):
        """The face's corner, centre or edge under the screen point:
        ("point", (x, y)) or ("line", (a, b)) in the sketch, or None."""
        from . import face_sketch
        group, info = self._face_info(parent)
        if group is None:
            return None
        project = self._project()

        def scr(p):
            return project(face_sketch.to_world(group, p[0], p[1]))
        best = None
        for px, py, kind in list(info.get("points") or []) + \
                [(0.0, 0.0, "origin")]:
            if kind == "middle":
                continue               # mid-edge: the EDGE is meant
            q = scr((px, py))
            if q is not None:
                d = math.hypot(q[0] - x, q[1] - y)
                if d <= PICK_PX and (best is None or d < best[0]):
                    best = (d, "point", (px, py))
        if best is not None:
            return best[1:]
        for a, b in info.get("segments") or ():
            qa, qb = scr(a), scr(b)
            if qa is None or qb is None:
                continue
            d, _t = _seg_px((x, y), qa, qb)
            if d <= PICK_PX and (best is None or d < best[0]):
                best = (d, "line", (a, b))
        return best[1:] if best else None

    def model_pick(self, x, y, parent):
        """A click on the face: a fixed construction copy in the sketch,
        as the 2D view makes, returned as a pick."""
        from PyQt5.QtCore import QPointF
        from . import face_outline
        near = self.model_near(x, y, parent)
        if near is None:
            return None
        kind, where = near
        pos = where if kind == "point" else where[0]
        return face_outline.reference(
            self.window.view2d.scene(), QPointF(pos[0], pos[1]), kind,
            parent=parent)

    def pick_at(self, x, y):
        """The entity under the screen point (x, y), or None."""
        project = self._project()
        solid = self._occluder()
        working = self._working_on()
        current = None

        def seen(p):
            # the sketch being extruded lies under its own boss: offered
            return current is working or solid(p)
        allowed = self._allowed()
        best = None
        for node, name, kind, g in self.entities():
            current = node.parent
            if kind not in allowed:
                continue
            if kind == "point":
                if name == "m" and self.kind != "dimension":
                    continue
                q = project(g)
                if q is None or not seen(g):
                    continue
                d = math.hypot(q[0] - x, q[1] - y)
                rank = 0 if d <= POINT_PX else 2
            elif kind == "line":
                qa, qb = project(g[0]), project(g[1])
                if qa is None or qb is None:
                    continue
                d, t = _seg_px((x, y), qa, qb)
                mid = tuple(g[0][i] + (g[1][i] - g[0][i]) * t
                            for i in range(3))
                if not seen(mid):
                    continue
                rank = 1
            else:
                pts = [project(p) for p in g]
                d, at = 1e9, None
                for i, (qa, qb) in enumerate(zip(pts, pts[1:])):
                    if qa is None or qb is None:
                        continue
                    dd, _t = _seg_px((x, y), qa, qb)
                    if dd < d:
                        d, at = dd, g[i]
                if at is None or not seen(at):
                    continue
                rank = 1
            if d > PICK_PX:
                continue
            key = (rank, d)
            if best is None or key < best[0]:
                best = (key, (node, name, kind))
        return best[1] if best else None

    # --------------------------------------------------------- events
    def mouse_press(self, event):
        from PyQt5.QtCore import Qt
        if event.button() == Qt.RightButton:
            self.drop()
            return True
        self._down = event.pos()
        return False                # the view may still orbit on a drag

    def mouse_move(self, event):
        x, y = event.pos().x(), event.pos().y()
        hit = self.pick_at(x, y)
        near = None
        if hit is None and self.kind == "dimension":
            parent = self.picks[0][0].parent if self.picks \
                else self._working_on()
            near = (self.model_near(x, y, parent), parent)
        if hit != self.hover or near != getattr(self, "model_hover", None):
            self.hover = hit
            self.model_hover = near
            self.view.update()
        return False

    def mouse_release(self, event):
        from PyQt5.QtCore import Qt
        down, self._down = self._down, None
        if down is None or event.button() != Qt.LeftButton or \
                (event.pos() - down).manhattanLength() > CLICK_PX:
            return False
        self._seen = None
        self.click(event.pos().x(), event.pos().y())
        return True

    def wheel(self, event):
        return False

    def key_press(self, event):
        from PyQt5.QtCore import Qt
        if event.key() == Qt.Key_Escape and self.picks:
            self.drop()
            return True
        return False

    def drop(self):
        self.picks = []
        self.view.update()
        self._say(self._prompt())

    def exit(self):
        tool = getattr(self.window, "_sketch3d_tool", None)
        from PyQt5.QtCore import QTimer
        if tool is not None:      # back to the 3D sketch it came from
            QTimer.singleShot(0, tool.resume)
        elif getattr(self.window, "_drag_paused", None) is not None:
            from . import drag_feature      # or to the Extrude window
            QTimer.singleShot(0, lambda: drag_feature.resume_paused(
                self.window))
        self.picks = []
        self.hover = None

    # ---------------------------------------------------------- logic
    def _say(self, text):
        self.window.statusBar().showMessage(text, 8000)

    def _prompt(self):
        from . import sketch_constrain_ui as ui
        if self.kind == "dimension":
            return ("Smart Dimension (3D): click a line, a circle or a "
                    "point." if not self.picks else
                    "Smart Dimension (3D): click a second one — or "
                    "anywhere empty for this one's size.")
        return ui.prompt(self.kind, len(self.picks)) + " (3D)"

    def click(self, x, y):
        hit = self.pick_at(x, y)
        if self.kind == "dimension":
            return self._dimension_click(hit, x, y)
        if hit is None:
            self._say(self._prompt())
            return None
        if self.picks and hit[0].parent is not self.picks[0][0].parent:
            self._say("Constraints join shapes of one sketch: pick a "
                      "shape beside the first.")
            return None
        if self.picks and hit[:2] == self.picks[0][:2]:
            self._say("That is the first pick — click something else.")
            return None
        self.picks.append(hit)
        wants = sc.KINDS[self.kind][1]
        done = len(self.picks) == len(wants) or (
            self.kind in sc.TWO_POINT and hit[2] == "line"
            and len(self.picks) == 1)
        if not done:
            self.view.update()
            self._say(self._prompt())
            return None
        return self._finish()

    def _finish(self):
        from . import sketch_constrain_ui as ui
        picks, self.picks = list(self.picks), []
        kind = self.kind
        if kind == "coincident" and any(k != "point" for _n, _e, k in picks):
            kind = "point_on"
        if kind == "point_on" and picks[0][2] != "point":
            picks.reverse()
        if kind == "tangent" and picks[1][2] == "line":
            picks.reverse()
        container = picks[0][0].parent
        refs = [sc.ref_of(container, n, name) for n, name, _k in picks]
        value = None
        if sc.KINDS[kind][2]:
            text = ui._ask_value(self.window.view2d.scene(), kind,
                                 sc.measure(container, kind, refs))
            if text is None:
                return None
            value = ui._value(text)
        try:
            report = sc.add(self.window.model, container, kind, refs, value)
        except ValueError as exc:
            self._say(str(exc))
            return None
        self.view.update()
        self._say("%s added — %s" % (sc.KINDS[kind][0],
                                     sc.status_text(report)))
        return report

    def _dimension_click(self, hit, x=None, y=None):
        from . import sketch_constrain_ui as ui
        if hit is None and x is not None:
            # the model's corner, centre or edge (SolidWorks)
            parent = self.picks[0][0].parent if self.picks \
                else self._working_on()
            try:
                hit = self.model_pick(x, y, parent)
            except (ValueError, KeyError):
                hit = None
        if not self.picks:
            if hit is None:
                self._say(self._prompt())
                return None
            self.picks.append(hit)
            self.view.update()
            self._say(self._prompt())
            return None
        first = self.picks[0]
        if hit is None and first[1] == "m":
            first = (first[0], "l", "line")
        if hit is None:
            hit = first if first[2] in ("line", "circle") else None
        if hit is None:
            self._say("Smart Dimension (3D): click the second point or "
                      "line.")
            return None
        if hit[0].parent is not first[0].parent:
            self._say("Dimensions join shapes of one sketch.")
            return None
        self.picks = []
        made = ui._smart(first, hit)
        self.view.update()
        if made is None:
            self._say("Those two cannot be dimensioned together.")
            return None
        kind, chosen = made
        container = chosen[0][0].parent
        refs = [sc.ref_of(container, n, name) for n, name, _k in chosen]
        text = ui._ask_value(self.window.view2d.scene(), kind,
                             sc.measure(container, kind, refs))
        if text is None:
            return None
        model = self.window.model
        same = [i for i, r in enumerate(sc.rows(container))
                if r["kind"] == kind and sorted(r["refs"]) == sorted(refs)]
        try:
            if same:
                report = sc.set_value(model, container, same[0],
                                      ui._value(text))
            else:
                report, _scaled = sc.add_dimension(model, container, kind,
                                                   refs, ui._value(text))
        except ValueError as exc:
            self._say(str(exc))
            return None
        self._say("%s %s — %s" % (sc.KINDS[kind][0], text,
                                  sc.status_text(report)))
        return report

    # ---------------------------------------------------------- paint
    def paint(self, painter, project):
        from PyQt5.QtCore import QPointF
        from PyQt5.QtGui import QColor, QPen
        geo = {(id(n), e): g for n, e, _k, g in self.entities()}
        near = getattr(self, "model_hover", None)
        if near and near[0]:
            from . import face_sketch
            group = face_sketch.group_of(near[1])
            kind, where = near[0]
            pts = [project(face_sketch.to_world(group, p[0], p[1])) for p in
                   ([where] if kind == "point" else where)]
            if all(pts):
                painter.setPen(QPen(QColor(240, 140, 30), 3))
                if kind == "point":
                    painter.drawEllipse(QPointF(pts[0][0], pts[0][1]), 5, 5)
                else:
                    painter.drawLine(QPointF(pts[0][0], pts[0][1]),
                                     QPointF(pts[1][0], pts[1][1]))

        def draw(item, colour, width):
            g = geo.get((id(item[0]), item[1]))
            if g is None:
                return
            pen = QPen(colour, width)
            pen.setCosmetic(True)
            painter.setPen(pen)
            if item[2] == "point":
                q = project(g)
                if q is not None:
                    painter.setBrush(colour)
                    painter.drawEllipse(QPointF(q[0], q[1]), 5.0, 5.0)
                return
            pts = list(g) if item[2] == "circle" else [g[0], g[1]]
            qs = [project(p) for p in pts]
            for a, b in zip(qs, qs[1:]):
                if a is not None and b is not None:
                    painter.drawLine(QPointF(a[0], a[1]),
                                     QPointF(b[0], b[1]))
        painter.save()
        painter.setRenderHint(painter.Antialiasing, True)
        for p in self.picks:
            draw(p, QColor(230, 120, 20), 4.0)
        if self.hover is not None:
            draw(self.hover, QColor(0, 190, 255, 235), 6.0)
        painter.restore()


def start(window, tool):
    """Run constraint *tool* in the 3D view. True when it started."""
    from . import sketch_constrain_ui as ui
    if tool == ui.DELETE:
        return False                      # deleting marks: the 2D view
    view = window.view3d
    end(window)
    old = getattr(view, "edit_tool", None)
    if old is not None:
        for name in ("exit", "close", "_end", "stop", "cancel"):
            fn = getattr(old, name, None)
            if callable(fn):
                try:
                    fn()
                except Exception:         # pragma: no cover
                    pass
                break
    t = Constrain3D(window, tool)
    view.edit_tool = t
    view.setMouseTracking(True)
    view.update()
    t._say(t._prompt())
    return True


def end(window):
    """The 3D constraint tool, if running, stops (another tool chosen)."""
    view = window.view3d
    if isinstance(getattr(view, "edit_tool", None), Constrain3D):
        view.edit_tool.exit()
        view.edit_tool = None
        view.update()
