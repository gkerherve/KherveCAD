"""Edit Mode in the 3D view — Blender's way of working a mesh by hand.

Tab over the 3D view (or the toolbar's Edit vertices button, or the
tree's right-click) opens the selected part: a polyhedron as it is,
anything else converted into one first (meshedit.convert). Its vertices
and edges are drawn over the model and:

* click a vertex to select it (Shift adds / removes), click a face to
  take its corners, Shift+drag or B for a box, A all, Alt+A none,
  L everything joined to the selection;
* drag a vertex — or press G — to move the selection in the view's
  plane; X / Y / Z during the move keep it to that axis, Ctrl snaps,
  a click or Enter confirms, Esc or a right click puts it back;
* S scales and R rotates the selection about its centre the same way;
* E extrudes the selected faces and moves them out along their normal;
* Ctrl+click an edge to put a new vertex on it, Ctrl+click a face to
  put one inside it — more vertices where the shape needs them;
* W or a right click opens the vertex menu: Subdivide, Extrude, Merge
  (M), Dissolve (X / Delete), Smooth;
* O turns proportional editing on (the wheel sizes it while moving),
  the panel picks a mirror axis (X-mirror) and Alt+Z sees through.

Every change is written to the polyhedron's ``points`` / ``faces``
params, so it is undoable, saved, shown in the Code tab as OpenSCAD's
own polyhedron(), and the solid stays closed (meshedit.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtCore import QObject, QPointF, QRectF, Qt, QTimer
from PyQt5.QtGui import QColor, QCursor, QPen, QPolygonF
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
                             QGridLayout, QHBoxLayout, QLabel, QMenu,
                             QPushButton, QVBoxLayout)

from . import language, meshedit

#: how near (px) a click must land to take a vertex / an edge
VERTEX_PICK_PX = 9.0
EDGE_PICK_PX = 7.0
#: a press that moves less than this is a click, not a drag
CLICK_PX = 4
#: commit a running move at most this often (ms): each commit rebuilds
#: the preview, the handles follow the mouse at once regardless
COMMIT_MS = 50

SELECT = QColor("#ff9f1a")
VERTEX = QColor(20, 20, 24)
EDGE = QColor(10, 10, 14, 200)
BACK_EDGE = QColor(10, 10, 14, 70)
FACE_FILL = QColor(255, 159, 26, 60)
AXIS_COLORS = {"x": QColor("#d64545"), "y": QColor("#3f9e4d"),
               "z": QColor("#3a6fd8"), "normal": QColor("#e0a020")}

#: keys Edit Mode takes from the menus while it is open (a QAction on
#: M — Measure — would otherwise win over Merge)
_KEYS = {Qt.Key_G, Qt.Key_S, Qt.Key_R, Qt.Key_E, Qt.Key_A, Qt.Key_B,
         Qt.Key_L, Qt.Key_M, Qt.Key_O, Qt.Key_W, Qt.Key_X, Qt.Key_Y,
         Qt.Key_Z, Qt.Key_Delete, Qt.Key_Backspace, Qt.Key_Escape,
         Qt.Key_Return, Qt.Key_Enter}


def _vsub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _vadd(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _vscale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def _vdot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _unit(a):
    n = math.sqrt(_vdot(a, a))
    return _vscale(a, 1.0 / n) if n > 1e-12 else (0.0, 0.0, 1.0)


def _rotate_about(p, pivot, axis, angle):
    """*p* turned *angle* radians about the line through *pivot* along
    the unit *axis* (Rodrigues)."""
    v = _vsub(p, pivot)
    c, s = math.cos(angle), math.sin(angle)
    k = axis
    cross = (k[1] * v[2] - k[2] * v[1], k[2] * v[0] - k[0] * v[2],
             k[0] * v[1] - k[1] * v[0])
    d = _vdot(k, v) * (1.0 - c)
    return _vadd(pivot, (v[0] * c + cross[0] * s + k[0] * d,
                         v[1] * c + cross[1] * s + k[1] * d,
                         v[2] * c + cross[2] * s + k[2] * d))


def _seg_dist(px, py, ax, ay, bx, by):
    """(distance, t) from screen point p to segment a-b."""
    dx, dy = bx - ax, by - ay
    length = dx * dx + dy * dy
    t = 0.0 if length < 1e-9 else max(0.0, min(1.0, (
        (px - ax) * dx + (py - ay) * dy) / length))
    qx, qy = ax + t * dx, ay + t * dy
    return math.hypot(px - qx, py - qy), t


class EditSession(QObject):
    """One open Edit Mode on one polyhedron node. The 3D view hands it
    its mouse, keys and paint (View3D.edit_tool); whatever it declines
    — orbit, pan, zoom — the view does as always."""

    def __init__(self, window, node):
        super().__init__(window)
        self.win = window
        self.view = window.view3d
        self.model = window.model
        self.node = node
        self._path = self._path_of(node)
        self.selection = set()
        self.xray = False
        self.proportional = False
        self.radius = 10.0
        self.falloff = "smooth"
        self.mirror = "none"
        self._xform = None             # a running G / S / R / E
        self._press = None             # what a left/right press began
        self._box = None               # (start, now, mode) screen rect
        self._box_armed = False        # B pressed: the next drag boxes
        self._hover = None             # last mouse position in the view
        self._committing = False
        self._pending = None
        self._commit_timer = QTimer(self)
        self._commit_timer.setSingleShot(True)
        self._commit_timer.setInterval(COMMIT_MS)
        self._commit_timer.timeout.connect(self._commit_now)
        self.points, self.faces, self.world = [], [], []
        self._load()
        self.model.node_changed.connect(self._model_changed)
        self.model.structure_changed.connect(self._model_changed)
        self.view.edit_tool = self
        self.view.setMouseTracking(True)
        self.view.setFocus(Qt.OtherFocusReason)
        self.panel = EditPanel(self)
        self.panel.adjustSize()
        # beside the 3D view's top-left corner, clear of the model
        corner = self.view.mapToGlobal(self.view.rect().topLeft())
        self.panel.move(max(0, corner.x() - self.panel.width() - 12),
                        corner.y())
        self.panel.show()
        self.view.setFocus(Qt.OtherFocusReason)
        self.view.update()

    # ---------------------------------------------------- the node
    def _path_of(self, node):
        path = []
        while node is not None and node.parent is not None:
            path.append(node.index())
            node = node.parent
        return path[::-1]

    def _resolve(self):
        """The edited node — found again by its place in the tree when
        an undo has rebuilt the document under us."""
        node = self.node
        root = self.model.root
        probe = node
        while probe is not None and probe.parent is not None:
            probe = probe.parent
        if probe is root:
            return node
        found = self.model.find(node.id)
        if found is not None and found.type == "polyhedron":
            return found
        probe = root
        for i in self._path:
            if i >= len(probe.children):
                return None
            probe = probe.children[i]
        return probe if probe.type == "polyhedron" else None

    def _load(self):
        """Read the node's points / faces and place them in the view."""
        from . import bake, mesh
        node = self.node
        env = bake._codegen_env(node)
        self.points = [[mesh.rv(v, env)
                        for v in (list(row) + [0.0, 0.0, 0.0])[:3]]
                       for row in node.params.get("points") or []]
        faces = []
        for face in node.params.get("faces") or []:
            try:
                idx = [int(v) for v in face]
            except (TypeError, ValueError):
                continue
            if len(idx) >= 3 and all(0 <= i < len(self.points)
                                     for i in idx):
                faces.append(idx)
        self.faces = faces
        root = self.win._render_scope()[0]
        stop = root if root is not self.model.root else None
        self.matrix = meshedit.frame(node, stop)
        self.inverse = meshedit.linear_inverse(self.matrix)
        self.selection = {i for i in self.selection
                          if i < len(self.points)}
        self._place()

    def _place(self):
        m = self.matrix
        self.world = [meshedit.apply(m, p) for p in self.points]

    def _to_local_point(self, w):
        t = (self.matrix[0][3], self.matrix[1][3], self.matrix[2][3])
        return meshedit.local_delta(self.inverse, _vsub(w, t))

    def _model_changed(self, *_args):
        if self._committing or self._xform is not None:
            return
        node = self._resolve()
        if node is None:
            self.exit(language.tr(
                "Edit Mode closed: the mesh is no longer in the "
                "document."))
            return
        self.node = node
        self._path = self._path_of(node)
        self._load()
        self.panel.refresh()
        self.view.update()

    def _write(self, points, faces=None, now=False):
        """Put new geometry on the node (one change signal). A move in
        progress is throttled; everything else lands at once."""
        self.points = [list(p) for p in points]
        if faces is not None:
            self.faces = [list(f) for f in faces]
        self._place()
        self._pending = (faces is not None)
        if now:
            self._commit_now()
        elif not self._commit_timer.isActive():
            self._commit_timer.start()
        self.view.update()

    def _commit_now(self):
        self._commit_timer.stop()
        if self._pending is None:
            return
        self._pending = None
        node = self.node
        self._committing = True
        try:
            # both lists, ONE change signal: never a frame whose faces
            # name points that are not there yet
            node.params["points"] = [list(p) for p in self.points]
            self.model.set_param(node, "faces",
                                 [list(f) for f in self.faces])
        finally:
            self._committing = False
        self.panel.refresh()

    def _apply(self, result, label):
        """Land a topology operation ``(points, faces, selection)`` —
        refused (with the reason) if it would open the solid."""
        if result is None:
            return False
        points, faces, selection = result[:3]
        why = meshedit.check(points, faces)
        if why:
            self.say(language.tr("{op} refused: {why}").format(
                op=language.tr(label), why=why))
            return False
        self.selection = set(selection)
        self._write(points, faces, now=True)
        return True

    def say(self, text, ms=5000):
        self.win.statusBar().showMessage(text, ms)

    # ------------------------------------------------- geometry help
    def _camera(self):
        eye, right, up, forward = self.view._camera()

        def project(v):
            return self.view._project(eye, right, up, forward, v)
        return project, eye, right, up, forward

    def _front_faces(self, eye, forward):
        ortho = self.view.projection == "Orthographic"
        out = []
        for i, face in enumerate(self.faces):
            n = meshedit.face_normal(self.world, face)
            if ortho:
                front = _vdot(n, forward) < 0.0
            else:
                c = meshedit.face_centre(self.world, face)
                front = _vdot(n, _vsub(eye, c)) > 0.0
            out.append(front)
        return out

    def _visible_vertices(self, front):
        if self.xray:
            return set(range(len(self.points)))
        vis = set()
        for face, f in zip(self.faces, front):
            if f:
                vis.update(face)
        return vis

    def _screen(self):
        """(projected points, front flags, visible vertex set)."""
        project, eye, _r, _u, forward = self._camera()
        proj = [project(w) for w in self.world]
        front = self._front_faces(eye, forward)
        return proj, front, self._visible_vertices(front)

    def vertex_at(self, x, y):
        proj, _front, vis = self._screen()
        best, best_d = None, VERTEX_PICK_PX
        for i in vis:
            p = proj[i]
            if p is None:
                continue
            d = math.hypot(p[0] - x, p[1] - y)
            if d < best_d or (d == best_d and best is not None
                              and p[2] < proj[best][2]):
                best, best_d = i, d
        return best

    def edge_at(self, x, y):
        """``(a, b, t)`` of the visible edge nearest screen (x, y)."""
        proj, front, _vis = self._screen()
        best, best_d = None, EDGE_PICK_PX
        seen = set()
        for face, f in zip(self.faces, front):
            if not f and not self.xray:
                continue
            n = len(face)
            for k in range(n):
                a, b = face[k], face[(k + 1) % n]
                key = (min(a, b), max(a, b))
                if key in seen:
                    continue
                seen.add(key)
                pa, pb = proj[a], proj[b]
                if pa is None or pb is None:
                    continue
                d, t = _seg_dist(x, y, pa[0], pa[1], pb[0], pb[1])
                if d < best_d:
                    best, best_d = (a, b, t), d
        return best

    def face_at(self, x, y):
        """``(face index, world point)`` under screen (x, y)."""
        from . import anchors
        project = self._camera()[0]
        tris, owner = [], []
        for i, face in enumerate(self.faces):
            ring = face[::-1]                     # our CCW
            for k in range(1, len(ring) - 1):
                tris.append((self.world[ring[0]], self.world[ring[k]],
                             self.world[ring[k + 1]]))
                owner.append(i)
        index, point = anchors.pick(tris, project, x, y)
        if index is None:
            return None, None
        return owner[index], point

    def _pivot(self):
        sel = [i for i in self.selection if i < len(self.world)]
        if not sel:
            return None
        n = float(len(sel))
        return (sum(self.world[i][0] for i in sel) / n,
                sum(self.world[i][1] for i in sel) / n,
                sum(self.world[i][2] for i in sel) / n)

    def _cursor(self):
        if self._hover is not None:          # mouse tracking keeps it
            return self._hover
        return self.view.mapFromGlobal(QCursor.pos())

    # ------------------------------------------------- transforms
    def begin(self, kind, pos=None, axis=None, before=None):
        """Start G (move), S (scale) or R (rotate) on the selection,
        following the mouse from *pos*."""
        pivot = self._pivot()
        if pivot is None:
            self.say(language.tr("Select vertices first (click one, or "
                                 "A for all)."))
            return False
        pos = pos if pos is not None else self._cursor()
        project = self._camera()[0]
        sp = project(pivot)
        self._xform = dict(
            kind=kind, start=QPointF(pos), now=QPointF(pos),
            pivot=pivot, pivot_screen=sp, axis=axis,
            orig=[list(p) for p in self.points],
            orig_world=list(self.world),
            before=before or ([list(p) for p in self.points],
                              [list(f) for f in self.faces],
                              set(self.selection)),
            text="")
        self.view.setFocus(Qt.OtherFocusReason)
        self.view.update()
        return True

    def _world_per_px(self, at):
        view = self.view
        f = view._focal()
        if view.projection == "Orthographic":
            return max(view.distance, 1e-6) / f
        sp = self._camera()[0](at)
        depth = sp[2] if sp is not None else view.distance
        return max(depth, 1e-6) / f

    def _axis_vector(self, axis):
        if axis is None:
            return None
        if isinstance(axis, tuple):
            return _unit(axis)
        return {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0),
                "z": (0.0, 0.0, 1.0)}[axis]

    def _update_xform(self, pos, snap=False):
        x = self._xform
        x["now"] = QPointF(pos)
        dx = pos.x() - x["start"].x()
        dy = pos.y() - x["start"].y()
        pivot = x["pivot"]
        axis = self._axis_vector(x["axis"])
        _proj, _eye, right, up, forward = self._camera()
        kind = x["kind"]
        snap_step = float(getattr(getattr(self.win, "scene", None),
                                  "grid_size", 1.0) or 1.0)
        if kind == "grab":
            scale = self._world_per_px(pivot)
            if axis is None:
                delta = _vadd(_vscale(right, dx * scale),
                              _vscale(up, -dy * scale))
                if snap:
                    delta = tuple(round(v / snap_step) * snap_step
                                  for v in delta)
            else:
                project = self._camera()[0]
                p0 = project(pivot)
                p1 = project(_vadd(pivot, _vscale(axis, scale * 100.0)))
                if p0 is None or p1 is None:
                    return
                sx, sy = p1[0] - p0[0], p1[1] - p0[1]
                length = math.hypot(sx, sy)
                if length < 1e-6:
                    return
                amount = (dx * sx + dy * sy) / length \
                    * (scale * 100.0) / length
                if snap:
                    amount = round(amount / snap_step) * snap_step
                delta = _vscale(axis, amount)
            local = meshedit.local_delta(self.inverse, delta)
            pts = meshedit.move(x["orig"], self.selection, local,
                                self.radius if self.proportional else 0.0,
                                self.mirror, self.falloff)
            x["text"] = language.tr("Move") + "  " + "  ".join(
                f"{n} {v:+.3g}" for n, v in zip("xyz", delta))
        else:
            sp = x["pivot_screen"]
            if sp is None:
                return
            ox, oy = x["start"].x() - sp[0], x["start"].y() - sp[1]
            nx, ny = pos.x() - sp[0], pos.y() - sp[1]
            if kind == "scale":
                r0 = math.hypot(ox, oy) or 1.0
                factor = math.hypot(nx, ny) / r0
                if snap:
                    factor = round(factor * 10.0) / 10.0

                def fn_world(w):
                    v = _vsub(w, pivot)
                    if axis is None:
                        return _vadd(pivot, _vscale(v, factor))
                    along = _vdot(v, axis) * (factor - 1.0)
                    return _vadd(w, _vscale(axis, along))
                x["text"] = language.tr("Scale") + f"  {factor:.3g}"
            else:
                a0 = math.atan2(-oy, ox)
                a1 = math.atan2(-ny, nx)
                angle = a1 - a0
                if snap:
                    step = math.radians(5.0)
                    angle = round(angle / step) * step
                turn = axis if axis is not None else _vscale(forward, -1.0)
                if axis is not None and _vdot(axis, forward) > 0:
                    angle = -angle

                def fn_world(w):
                    return _rotate_about(w, pivot, turn, angle)
                x["text"] = language.tr("Rotate") \
                    + f"  {math.degrees(angle):+.3g}°"
            orig, orig_world = x["orig"], x["orig_world"]
            index = {tuple(p): i for i, p in enumerate(orig)}

            def fn_local(p):
                i = index.get(tuple(p))
                w = orig_world[i] if i is not None \
                    else meshedit.apply(self.matrix, p)
                return self._to_local_point(fn_world(w))
            pts = meshedit.transform(
                orig, self.selection, fn_local,
                self.radius if self.proportional else 0.0,
                self.mirror, self.falloff)
        if x["axis"] is not None:
            name = x["axis"].upper() if isinstance(x["axis"], str) \
                else language.tr("normal")
            x["text"] += "  " + language.tr("along {axis}").format(
                axis=name)
        self._write(pts)

    def confirm(self):
        if self._xform is None:
            return
        self._xform = None
        self._commit_now()
        self.view.update()

    def cancel(self):
        x, self._xform = self._xform, None
        if x is None:
            return
        points, faces, selection = x["before"]
        self.selection = set(selection)
        self._write(points, faces, now=True)

    def toggle_axis(self, axis):
        x = self._xform
        if x is None:
            return
        x["axis"] = None if x["axis"] == axis else axis
        self._update_xform(x["now"])

    # ------------------------------------------------- operations
    def select_all(self, toggle=True):
        everything = set(range(len(self.points)))
        if toggle and self.selection >= everything:
            self.selection = set()
        else:
            self.selection = everything
        self._changed_selection()

    def select_none(self):
        self.selection = set()
        self._changed_selection()

    def select_linked(self):
        self.selection = set(meshedit.select_linked(self.faces,
                                                    self.selection))
        self._changed_selection()

    def _changed_selection(self):
        self.panel.refresh()
        self.view.update()

    def subdivide(self):
        if not meshedit.selected_faces(self.faces, self.selection):
            self.say(language.tr("Subdivide works on faces: select every "
                                 "corner of the faces to cut."))
            return
        self._apply(meshedit.subdivide(self.points, self.faces,
                                       self.selection), "Subdivide")

    def extrude(self, follow=True):
        before = ([list(p) for p in self.points],
                  [list(f) for f in self.faces], set(self.selection))
        result = meshedit.extrude(self.points, self.faces, self.selection)
        if result is None:
            self.say(language.tr("Extrude needs some faces selected (all "
                                 "their corners), not every face."))
            return
        points, faces, selection, normal = result
        if not self._apply((points, faces, selection), "Extrude"):
            return
        if follow:
            m = self.matrix
            world_n = tuple(sum(m[r][c] * normal[c] for c in range(3))
                            for r in range(3))
            self.begin("grab", axis=_unit(world_n), before=before)

    def merge(self):
        if len(self.selection) < 2:
            self.say(language.tr("Merge needs two or more vertices "
                                 "selected."))
            return
        self._apply(meshedit.merge(self.points, self.faces,
                                   sorted(self.selection)), "Merge")

    def dissolve(self):
        if not self.selection:
            return
        before = len(self.points)
        if self._apply(meshedit.dissolve(self.points, self.faces,
                                         sorted(self.selection)),
                       "Dissolve") and len(self.points) == before:
            self.say(language.tr("Nothing dissolved: a vertex needs "
                                 "three faces round it."))

    def smooth(self):
        if not self.selection:
            return
        pts = meshedit.smooth(self.points, self.faces,
                              sorted(self.selection))
        self._write(pts, now=True)

    def insert_at(self, x, y):
        """Ctrl+click: a vertex on the edge under the cursor, else
        inside the face under it. Returns the new vertex or None."""
        hit = self.edge_at(x, y)
        if hit is not None:
            a, b, t = hit
            # the screen fraction, mapped back through the perspective
            project = self._camera()[0]
            pa, pb = project(self.world[a]), project(self.world[b])
            if pa and pb and pa[2] > 0 and pb[2] > 0 and \
                    self.view.projection != "Orthographic":
                t = t * pa[2] / (t * pa[2] + (1.0 - t) * pb[2])
            points, faces, new = meshedit.split_edge(
                self.points, self.faces, a, b, t)
        else:
            face, point = self.face_at(x, y)
            if face is None:
                return None
            points, faces, new = meshedit.poke(
                self.points, self.faces, face, self._to_local_point(point))
        if new is None or not self._apply(
                (points, faces, [new]), "Add vertex"):
            return None
        return new

    def toggle_proportional(self):
        self.proportional = not self.proportional
        self.panel.refresh()
        self.view.update()

    def toggle_xray(self):
        self.xray = not self.xray
        self.panel.refresh()
        self.view.update()

    def exit(self, message=None):
        """Leave Edit Mode; the edits stay on the node."""
        if self._xform is not None:
            self.confirm()
        self._commit_now()
        try:
            self.model.node_changed.disconnect(self._model_changed)
            self.model.structure_changed.disconnect(self._model_changed)
        except TypeError:
            pass
        if self.view.edit_tool is self:
            self.view.edit_tool = None
            self.view.setMouseTracking(False)
            self.view.unsetCursor()
            self.view.update()
        if getattr(self.win, "_edit_session", None) is self:
            self.win._edit_session = None
        act = getattr(self.win, "_edit_mesh_act", None)
        if act is not None:
            act.blockSignals(True)
            act.setChecked(False)
            act.blockSignals(False)
        panel, self.panel = self.panel, _NoPanel()
        panel.session = None
        panel.close()
        self.say(message or language.tr("Edit Mode closed."))

    # ------------------------------------------------- the view's hooks
    def wants_key(self, event):
        if event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):
            return False                 # Ctrl+Z & co. stay the app's
        return event.key() in _KEYS

    def key_press(self, event):
        key, mods = event.key(), event.modifiers()
        alt = bool(mods & Qt.AltModifier)
        x = self._xform
        if x is not None:
            if key == Qt.Key_Escape:
                self.cancel()
            elif key in (Qt.Key_Return, Qt.Key_Enter):
                self.confirm()
            elif key in (Qt.Key_X, Qt.Key_Y, Qt.Key_Z):
                self.toggle_axis({Qt.Key_X: "x", Qt.Key_Y: "y",
                                  Qt.Key_Z: "z"}[key])
            elif key == Qt.Key_O:
                self.toggle_proportional()
                self._update_xform(x["now"])
            return True
        if key == Qt.Key_Escape:
            if self._box is not None or self._box_armed:
                self._box, self._box_armed = None, False
                self.view.update()
            else:
                self.exit()
        elif key == Qt.Key_G:
            self.begin("grab")
        elif key == Qt.Key_S:
            self.begin("scale")
        elif key == Qt.Key_R:
            self.begin("rotate")
        elif key == Qt.Key_E:
            self.extrude()
        elif key == Qt.Key_A:
            self.select_none() if alt else self.select_all()
        elif key == Qt.Key_B:
            self._box_armed = True
            self.say(language.tr("Box select: drag a rectangle "
                                 "(Shift+drag works too)."), 3000)
        elif key == Qt.Key_L:
            self.select_linked()
        elif key == Qt.Key_M:
            self.merge()
        elif key == Qt.Key_O:
            self.toggle_proportional()
        elif key == Qt.Key_Z and alt:
            self.toggle_xray()
        elif key in (Qt.Key_X, Qt.Key_Delete, Qt.Key_Backspace):
            self.dissolve()
        elif key == Qt.Key_W:
            self.context_menu(QCursor.pos())
        else:
            return False
        return True

    def mouse_press(self, event):
        pos = event.pos()
        button = event.button()
        mods = event.modifiers()
        if self._xform is not None:
            if button == Qt.LeftButton:
                self.confirm()
            else:
                self.cancel()
            return True
        if button == Qt.RightButton:
            self._press = dict(kind="right", pos=QPointF(pos))
            return False                 # still pans if dragged
        if button != Qt.LeftButton:
            return False
        if mods & Qt.ControlModifier:
            new = self.insert_at(pos.x(), pos.y())
            if new is not None:
                self._press = dict(kind="vertex", pos=QPointF(pos))
                self.panel.refresh()
                return True
            return False
        v = self.vertex_at(pos.x(), pos.y())
        if v is not None and not self._box_armed:
            if mods & Qt.ShiftModifier:
                self.selection ^= {v}
                self._press = dict(kind="toggled", pos=QPointF(pos))
            else:
                if v not in self.selection:
                    self.selection = {v}
                self._press = dict(kind="vertex", pos=QPointF(pos))
            self._changed_selection()
            return True
        if self._box_armed or mods & Qt.ShiftModifier:
            mode = "add" if (mods & Qt.ShiftModifier
                             or self._box_armed) else "set"
            if mods & Qt.AltModifier:
                mode = "remove"
            self._box = [QPointF(pos), QPointF(pos), mode]
            self._box_armed = False
            return True
        self._press = dict(kind="empty", pos=QPointF(pos),
                           shift=bool(mods & Qt.ShiftModifier))
        return False                     # orbit, as ever

    def mouse_move(self, event):
        pos = event.pos()
        self._hover = pos
        if self._xform is not None:
            self._update_xform(pos, bool(event.modifiers()
                                         & Qt.ControlModifier))
            return True
        if self._box is not None:
            self._box[1] = QPointF(pos)
            self.view.update()
            return True
        press = self._press
        if press is not None and press["kind"] == "vertex":
            if (QPointF(pos) - press["pos"]).manhattanLength() > CLICK_PX:
                self._press = None
                self.begin("grab", pos=press["pos"])
                self._xform["drag"] = True
                self._update_xform(pos)
            return True
        return False

    def mouse_release(self, event):
        pos = event.pos()
        if self._xform is not None:
            if self._xform.get("drag"):
                self.confirm()
            return True
        if self._box is not None:
            self._finish_box()
            return True
        press, self._press = self._press, None
        if press is None:
            return False
        if press["kind"] in ("vertex", "toggled"):
            return True
        moved = (QPointF(pos) - press["pos"]).manhattanLength()
        if moved > CLICK_PX:
            return False                 # it was an orbit / a pan
        if press["kind"] == "right":
            QTimer.singleShot(0, lambda g=event.globalPos():
                              self.context_menu(g))
            return False
        face, _point = self.face_at(pos.x(), pos.y())
        corners = set(self.faces[face]) if face is not None else set()
        if press.get("shift"):
            if corners and corners <= self.selection:
                self.selection -= corners
            else:
                self.selection |= corners
        else:
            self.selection = corners
        self._changed_selection()
        return False

    def wheel(self, event):
        if self._xform is not None and self.proportional:
            step = 1.15 if event.angleDelta().y() < 0 else 1 / 1.15
            self.radius = max(0.01, self.radius * step)
            self.panel.refresh()
            self._update_xform(self._xform["now"])
            return True
        return False

    def _finish_box(self):
        a, b, mode = self._box
        self._box = None
        rect = QRectF(a, b).normalized()
        proj, _front, vis = self._screen()
        inside = {i for i in vis if proj[i] is not None
                  and rect.contains(QPointF(proj[i][0], proj[i][1]))}
        if mode == "remove":
            self.selection -= inside
        elif mode == "add":
            self.selection |= inside
        else:
            self.selection = inside
        self._changed_selection()

    def context_menu(self, global_pos):
        """Blender's vertex context menu (right click, or W)."""
        menu = QMenu(self.view)
        tr = language.tr
        for text, slot in (
                (tr("Subdivide"), self.subdivide),
                (tr("Extrude faces\tE"), self.extrude),
                (tr("Merge at centre\tM"), self.merge),
                (tr("Dissolve vertices\tX"), self.dissolve),
                (tr("Smooth vertices"), self.smooth),
                (None, None),
                (tr("Move\tG"), lambda: self.begin("grab")),
                (tr("Scale\tS"), lambda: self.begin("scale")),
                (tr("Rotate\tR"), lambda: self.begin("rotate")),
                (None, None),
                (tr("Select all\tA"), lambda: self.select_all(False)),
                (tr("Select none\tAlt+A"), self.select_none),
                (tr("Select linked\tL"), self.select_linked),
                (None, None),
                (tr("Proportional editing\tO"), self.toggle_proportional),
                (tr("See through (X-ray)\tAlt+Z"), self.toggle_xray),
                (None, None),
                (tr("Leave Edit Mode\tTab"), self.exit)):
            if text is None:
                menu.addSeparator()
                continue
            act = menu.addAction(text)
            act.triggered.connect(lambda _=False, s=slot: s())
            if slot == self.toggle_proportional:
                act.setCheckable(True)
                act.setChecked(self.proportional)
            elif slot == self.toggle_xray:
                act.setCheckable(True)
                act.setChecked(self.xray)
        menu.exec_(global_pos)
        self.view.setFocus(Qt.OtherFocusReason)

    # ------------------------------------------------------- painting
    def paint(self, painter, project):
        from PyQt5.QtGui import QPainter
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        proj = [project(w) for w in self.world]
        _p, eye, _r, _u, forward = self._camera()
        front = self._front_faces(eye, forward)
        vis = self._visible_vertices(front)
        sel = self.selection
        painter.setPen(Qt.NoPen)
        painter.setBrush(FACE_FILL)
        for face, f in zip(self.faces, front):
            if (f or self.xray) and all(v in sel for v in face):
                pts = [proj[v] for v in face]
                if all(p is not None for p in pts):
                    painter.drawPolygon(QPolygonF(
                        [QPointF(p[0], p[1]) for p in pts]))
        drawn = {}
        for face, f in zip(self.faces, front):
            n = len(face)
            for k in range(n):
                a, b = face[k], face[(k + 1) % n]
                key = (min(a, b), max(a, b))
                drawn[key] = drawn.get(key, False) or f
        thin, hot = QPen(EDGE, 1.0), QPen(SELECT, 1.8)
        back = QPen(BACK_EDGE, 1.0)
        for (a, b), f in drawn.items():
            if not f and not self.xray:
                continue
            pa, pb = proj[a], proj[b]
            if pa is None or pb is None:
                continue
            painter.setPen(hot if a in sel and b in sel
                           else (thin if f else back))
            painter.drawLine(QPointF(pa[0], pa[1]), QPointF(pb[0], pb[1]))
        light = QPen(QColor(255, 255, 255, 200), 1.0)
        for i in vis:
            p = proj[i]
            if p is None:
                continue
            painter.setPen(light)
            painter.setBrush(SELECT if i in sel else VERTEX)
            r = 3.8 if i in sel else 3.0
            painter.drawRect(QRectF(p[0] - r, p[1] - r, 2 * r, 2 * r))
        x = self._xform
        if x is not None:
            self._paint_xform(painter, project, x)
        if self._box is not None:
            pen = QPen(QColor("#f2f6fa"), 1.0, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(QColor(255, 255, 255, 25))
            painter.drawRect(QRectF(self._box[0], self._box[1]).normalized())
        self._paint_banner(painter)
        painter.restore()

    def _paint_xform(self, painter, project, x):
        sp = project(x["pivot"])
        if sp is None:
            return
        axis = self._axis_vector(x["axis"])
        if axis is not None:
            a = b = None
            # long enough to cross the view, short enough to stay in
            # front of the camera in perspective
            for span in (2000.0, 600.0, 200.0, 60.0):
                far = self._world_per_px(x["pivot"]) * span
                a = project(_vsub(x["pivot"], _vscale(axis, far)))
                b = project(_vadd(x["pivot"], _vscale(axis, far)))
                if a and b:
                    break
            name = x["axis"] if isinstance(x["axis"], str) else "normal"
            if a and b:
                painter.setPen(QPen(AXIS_COLORS[name], 1.4))
                painter.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))
        if self.proportional:
            r = self.radius / self._world_per_px(x["pivot"])
            painter.setPen(QPen(QColor(255, 255, 255, 160), 1.0,
                                Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(sp[0], sp[1]), r, r)
        if x["kind"] != "grab":
            painter.setPen(QPen(QColor(255, 255, 255, 150), 1.0,
                                Qt.DashLine))
            painter.drawLine(QPointF(sp[0], sp[1]), x["now"])

    def _paint_banner(self, painter):
        x = self._xform
        if x is not None:
            text = x["text"] or language.tr("Move the mouse")
            text += "   " + language.tr(
                "click / Enter: done · Esc / right click: cancel · "
                "X Y Z: axis · Ctrl: snap")
            if self.proportional:
                text += "   " + language.tr(
                    "proportional {radius:.3g} (wheel)").format(
                        radius=self.radius)
        else:
            text = language.tr(
                "Edit Mode · {name} · {sel}/{count} vertices selected · "
                "W or right click: menu · Tab: done").format(
                    name=self.node.name, sel=len(self.selection),
                    count=len(self.points))
        font = painter.font()
        font.setBold(True)
        font.setPointSizeF(9.0)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        w = min(metrics.horizontalAdvance(text) + 24,
                self.view.width() - 16)
        h = metrics.height() + 10
        # along the bottom: the top holds the lighting and navigation bars
        rect = QRectF((self.view.width() - w) / 2.0,
                      self.view.height() - h - 44.0, w, h)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(20, 26, 32, 215))
        painter.drawRoundedRect(rect, 6.0, 6.0)
        painter.setPen(QColor("#f2f6fa"))
        painter.drawText(rect, Qt.AlignCenter,
                         metrics.elidedText(text, Qt.ElideRight,
                                            int(w - 16)))


class _NoPanel:
    """Stands in for the panel once it is closed."""

    def refresh(self):
        pass

    def close(self):
        pass


class EditPanel(QDialog):
    """The Edit Mode tool window: the operations as buttons, the
    proportional / mirror / X-ray options, what the keys do. Closing it
    leaves Edit Mode."""

    def __init__(self, session):
        super().__init__(session.win)
        self.session = session
        tr = language.tr
        self.setWindowTitle(tr("Edit Mode — {name}").format(
            name=session.node.name))
        self.setWindowFlag(Qt.Tool, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.count = QLabel()
        grid = QGridLayout()
        buttons = [
            (tr("Select all (A)"), lambda: session.select_all(False)),
            (tr("Select linked (L)"), session.select_linked),
            (tr("Subdivide"), session.subdivide),
            (tr("Extrude (E)"), session.extrude),
            (tr("Merge (M)"), session.merge),
            (tr("Dissolve (X)"), session.dissolve),
            (tr("Smooth"), session.smooth),
            (tr("Move (G)"), lambda: session.begin("grab")),
        ]
        for k, (text, slot) in enumerate(buttons):
            b = QPushButton(text)
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(lambda _=False, s=slot: self._run(s))
            grid.addWidget(b, k // 2, k % 2)
        self.prop = QCheckBox(tr("Proportional editing (O)"))
        self.prop.setFocusPolicy(Qt.NoFocus)
        self.prop.toggled.connect(self._set_prop)
        self.radius = QDoubleSpinBox()
        self.radius.setRange(0.01, 100000.0)
        self.radius.setDecimals(2)
        self.radius.setSuffix(" mm")
        self.radius.valueChanged.connect(self._set_radius)
        self.falloff = QComboBox()
        for name in meshedit.FALLOFFS:
            self.falloff.addItem(tr(name.capitalize()), name)
        self.falloff.currentIndexChanged.connect(
            lambda _i: setattr(session, "falloff",
                               self.falloff.currentData()))
        self.mirror = QComboBox()
        for name in meshedit.MIRRORS:
            self.mirror.addItem(tr("none") if name == "none"
                                else name.upper(), name)
        self.mirror.currentIndexChanged.connect(
            lambda _i: setattr(session, "mirror",
                               self.mirror.currentData()))
        self.xray = QCheckBox(tr("See through (Alt+Z)"))
        self.xray.setFocusPolicy(Qt.NoFocus)
        self.xray.toggled.connect(self._set_xray)
        opts = QGridLayout()
        opts.addWidget(self.prop, 0, 0, 1, 2)
        opts.addWidget(QLabel(tr("Radius")), 1, 0)
        opts.addWidget(self.radius, 1, 1)
        opts.addWidget(QLabel(tr("Falloff")), 2, 0)
        opts.addWidget(self.falloff, 2, 1)
        opts.addWidget(QLabel(tr("Mirror edits across")), 3, 0)
        opts.addWidget(self.mirror, 3, 1)
        opts.addWidget(self.xray, 4, 0, 1, 2)
        keys = QLabel(tr(
            "Click a vertex to select it, Shift+click to add, click a "
            "face for its corners, Shift+drag for a box.\n"
            "Drag a vertex to move it; G / S / R move, scale, rotate, "
            "then X / Y / Z for an axis, Ctrl to snap.\n"
            "Ctrl+click an edge or a face to add a vertex there.\n"
            "Right click or W: the vertex menu. Tab or Esc: done."))
        keys.setWordWrap(True)
        done = QPushButton(tr("Done (Tab)"))
        done.setFocusPolicy(Qt.NoFocus)
        done.clicked.connect(self.close)
        row = QHBoxLayout()
        row.addWidget(self.count)
        row.addStretch(1)
        row.addWidget(done)
        lay = QVBoxLayout(self)
        lay.addLayout(grid)
        lay.addLayout(opts)
        lay.addWidget(keys)
        lay.addLayout(row)
        self.setMinimumWidth(340)
        self.setMaximumWidth(420)
        self.refresh()

    def _run(self, slot):
        if self.session is None:
            return
        slot()
        self.session.view.setFocus(Qt.OtherFocusReason)

    def _set_prop(self, on):
        if self.session is not None and self.session.proportional != on:
            self.session.toggle_proportional()

    def _set_radius(self, value):
        if self.session is not None:
            self.session.radius = float(value)

    def _set_xray(self, on):
        if self.session is not None and self.session.xray != on:
            self.session.toggle_xray()

    def refresh(self):
        s = self.session
        if s is None:
            return
        for widget, value in ((self.prop, s.proportional),
                              (self.xray, s.xray)):
            widget.blockSignals(True)
            widget.setChecked(value)
            widget.blockSignals(False)
        self.radius.blockSignals(True)
        self.radius.setValue(s.radius)
        self.radius.blockSignals(False)
        self.count.setText(language.tr(
            "{count} vertices · {faces} faces · {sel} selected").format(
                count=len(s.points), faces=len(s.faces),
                sel=len(s.selection)))

    def keyPressEvent(self, event):
        if self.session is not None and self.session.key_press(event):
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        s, self.session = self.session, None
        if s is not None:
            s.exit()
        super().closeEvent(event)


# ------------------------------------------------------------- entry

def _target(window):
    nodes = window.builder.active_tree().selected_nodes()
    if len(nodes) == 1:
        return nodes[0]
    iso = window.builder.isolated_component()
    return iso if not nodes and iso is not None else None


def start(window, node=None):
    """Open Edit Mode on *node* (default: the one selected part),
    converting it into an editable polyhedron first if it is not one.
    Returns the session, or None (the status bar says why)."""
    old = getattr(window, "_edit_session", None)
    if old is not None:
        old.exit()
    node = node if node is not None else _target(window)
    act = getattr(window, "_edit_mesh_act", None)

    def refuse(text):
        window.statusBar().showMessage(text, 7000)
        if act is not None:
            act.blockSignals(True)
            act.setChecked(False)
            act.blockSignals(False)
        return None
    if node is None:
        return refuse(language.tr(
            "Edit Mode: select one part first (in the tree or the 2D "
            "view), then press Tab over the 3D view."))
    existing = meshedit.find_editable(node)
    target, why = meshedit.convert(window.model, node,
                                   fn=window.model.effective_fn())
    if target is None:
        return refuse(language.tr("Edit Mode: {name} — {why}").format(
            name=node.name, why=language.tr(why)))
    session = EditSession(window, target)
    window._edit_session = session
    if act is not None:
        act.blockSignals(True)
        act.setChecked(True)
        act.blockSignals(False)
    if existing is None:
        session.say(language.tr(
            "{name} converted to an editable mesh ({count} vertices) — "
            "Ctrl+Z gives the original back.").format(
                name=node.name, count=len(session.points)), 8000)
    return session


def toggle(window, on=None):
    """Tab: open Edit Mode on the selection, or close the open one."""
    session = getattr(window, "_edit_session", None)
    if on is None:
        on = session is None
    if not on:
        if session is not None:
            session.exit()
        return None
    return start(window)
