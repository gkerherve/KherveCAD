"""Sculpting by dragging over the 3D view — Blender's sculpt mode.

A small non-modal panel (brush, radius, strength, mirror) hands the 3D
view a brush tool (``View3D.edit_tool``, the hook Edit Mode uses): a
press on the surface starts a stroke and the brush follows the mouse —

* dab brushes (inflate, draw, clay strips, layer, smooth, flatten,
  pinch, mask) lay a dab every ``SPACING`` × radius along the path;
* crease / ridge lay a line segment between consecutive dabs, so a
  drag draws one wrinkle;
* grab, elastic grab and snake hook drag: the pull is where the mouse
  went, on the plane through the start facing the camera — a snake hook
  pulls a horn straight out into the air;
* pose takes two steps: click the joint, then press on the limb and
  drag to swing it round the joint in the screen's plane.

Shift while stroking smooths (as in Blender), ``[`` / ``]`` shrink and
grow the brush. A press off the surface still orbits, the wheel zooms.
The whole stroke lands on release as ONE set_param (one Ctrl+Z), in the
part's LOCAL frame, so the sculpt survives placing the Object.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QColor, QPen
from PyQt5.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFormLayout,
                             QHBoxLayout, QLabel, QPushButton, QVBoxLayout)

from . import language, mesh, sculpt

#: dabs this share of the radius apart along a drag
SPACING = 0.3
#: brushes whose drag is a pull rather than a row of dabs
DRAGS = frozenset({"grab", "elastic_grab", "snake_hook"})


def meshes(window, node):
    """``(world_tris, local_tris)`` of the sculpt node's CURRENT surface
    — as the view shows it and as the node computes it, same order —
    or ``(None, None)``."""
    from . import bake
    root = window._render_scope()[0]
    iso = root if root is not window.model.root else None
    fn = window.model.effective_fn()
    with window._isolated_frame(iso):
        world = mesh.selected_world_tris(root, {node.id}, fn=fn)
    env = bake._codegen_env(node)
    mesh._set_fn(fn)
    try:
        _points, _faces, local = bake.baked(node, env)
    except Exception:
        local = []
    finally:
        mesh._set_fn(None)
    if not world or len(world) != len(local):
        return None, None
    return world, local


def stroke_row(kind, point, radius, strength, direction=None,
               world=None, local=None, tip=None):
    """One stroke row for a sculpt, or None. *point*/*direction* (and a
    pose's *tip*) are world coordinates when *world*/*local* are given,
    else local."""
    if world is not None:
        if tip is not None:
            tip, _d = sculpt.to_local(world, local, tip)
            if tip is None:
                return None
        point, direction = sculpt.to_local(world, local, point, direction)
        if point is None:
            return None
    k = sculpt.kind_index(kind)
    if k < 0:
        return None
    d = list(direction) if direction is not None else [0.0, 0.0, 0.0]
    row = [k] + [round(float(v), 3) for v in point] + [
        round(float(radius), 3), round(float(strength), 3)] + [
        round(float(v), 4) for v in d]
    if tip is not None:
        row += [round(float(v), 3) for v in tip]
    return row


def add_stroke(model, node, kind, point, radius, strength, direction=None,
               world=None, local=None) -> bool:
    """Append one stroke to *node* (a sculpt). *point*/*direction* are
    world coordinates when *world*/*local* are given, else local."""
    row = stroke_row(kind, point, radius, strength, direction, world, local)
    if row is None:
        return False
    rows = [list(r) for r in (node.params.get("strokes") or [])]
    model.set_param(node, "strokes", rows + [row])
    return True


def add_line(model, node, kind, start, end, radius, strength,
             world=None, local=None) -> bool:
    """Append a crease / ridge from *start* to *end* (world points when
    *world*/*local* are given, else the node's own frame)."""
    if world is not None:
        start, _d = sculpt.to_local(world, local, start)
        end, _d = sculpt.to_local(world, local, end)
        if start is None or end is None:
            return False
    direction = [end[k] - start[k] for k in range(3)]
    return add_stroke(model, node, kind, start, radius, strength, direction)


# ----------------------------------------------------------- ray casting

def screen_ray(view, x, y):
    """``(origin, direction)`` of the view's ray through screen (x, y) —
    the inverse of View3D._project."""
    eye, right, up, forward = view._camera()
    w2, h2 = view.width() / 2.0, view.height() / 2.0
    if view.projection == "Orthographic":
        s = view._focal() / max(view.distance, 1e-6)
        a, b = (x - w2) / s, (h2 - y) / s
        origin = [eye[k] + right[k] * a + up[k] * b for k in range(3)]
        return origin, list(forward)
    f = view._focal()
    a, b = (x - w2) / f, (h2 - y) / f
    d = [forward[k] + right[k] * a + up[k] * b for k in range(3)]
    n = math.sqrt(sum(c * c for c in d)) or 1.0
    return list(eye), [c / n for c in d]


def ray_hit(tris_array, origin, direction):
    """``(point, normal)`` of the nearest hit of the ray on the (N, 3, 3)
    triangle array, or ``(None, None)`` — Möller-Trumbore in numpy."""
    import numpy as np
    if tris_array is None or not len(tris_array):
        return None, None
    o = np.asarray(origin, dtype=float)
    d = np.asarray(direction, dtype=float)
    a, b, c = tris_array[:, 0], tris_array[:, 1], tris_array[:, 2]
    e1, e2 = b - a, c - a
    p = np.cross(d, e2)
    det = np.einsum("ij,ij->i", e1, p)
    ok = np.abs(det) > 1e-12
    inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
    s = o - a
    u = np.einsum("ij,ij->i", s, p) * inv
    q = np.cross(s, e1)
    v = (q @ d) * inv
    t = np.einsum("ij,ij->i", e2, q) * inv
    hit = ok & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (t > 1e-6)
    if not hit.any():
        return None, None
    t = np.where(hit, t, np.inf)
    i = int(t.argmin())
    point = (o + d * t[i]).tolist()
    n = np.cross(e1[i], e2[i])
    n = (n / (np.linalg.norm(n) or 1.0)).tolist()
    return point, n


def _plane_point(view, x, y, through):
    """Where the ray through (x, y) meets the plane through *through*
    facing the camera — how a drag reaches into the air."""
    origin, d = screen_ray(view, x, y)
    _eye, _right, _up, forward = view._camera()
    denom = sum(d[k] * forward[k] for k in range(3))
    if abs(denom) < 1e-9:
        return None
    t = sum((through[k] - origin[k]) * forward[k] for k in range(3)) / denom
    return [origin[k] + d[k] * t for k in range(3)]


def _dist(a, b):
    return math.sqrt(sum((a[k] - b[k]) ** 2 for k in range(3)))


# -------------------------------------------------------------- the tool

class SculptTool:
    """The brush on the 3D view (View3D.edit_tool): mouse, keys and the
    brush cursor; whatever it declines — orbit, pan, zoom — the view
    does as always."""

    def __init__(self, panel):
        self.panel = panel
        self.view = panel.window_.view3d
        self._array = None
        self._stroke = None          # the running drag
        self._hover = None           # (point, normal) under the mouse
        self._joint = None           # a pose's first click

    # -- the surface ----------------------------------------------------
    def reload(self, world):
        import numpy as np
        self._array = np.asarray(world, dtype=float) if world else None

    def hit(self, x, y):
        origin, d = screen_ray(self.view, x, y)
        return ray_hit(self._array, origin, d)

    # -- the view's hooks -----------------------------------------------
    def wants_key(self, event):
        if event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):
            return False
        return event.key() in (Qt.Key_BracketLeft, Qt.Key_BracketRight,
                               Qt.Key_Escape)

    def key_press(self, event):
        key = event.key()
        if key == Qt.Key_BracketLeft:
            self.panel.radius.setValue(self.panel.radius.value() / 1.2)
        elif key == Qt.Key_BracketRight:
            self.panel.radius.setValue(self.panel.radius.value() * 1.2)
        elif key == Qt.Key_Escape:
            if self._stroke is None and self._joint is None:
                return False
            self._stroke = self._joint = None
        else:
            return False
        self.view.update()
        return True

    def mouse_press(self, event):
        if event.button() != Qt.LeftButton:
            return False
        pos = event.pos()
        point, normal = self.hit(pos.x(), pos.y())
        if point is None:
            return False                    # off the surface: orbit
        kind = self.panel.kind.currentData()
        if event.modifiers() & Qt.ShiftModifier:
            kind = "smooth"
        if kind == "pose" and self._joint is None:
            self._joint = (point, normal)   # first click: the joint
            self.panel.status(language.tr(
                "Pose: now press on the limb that moves and drag to "
                "swing it; Esc cancels."))
            self.view.update()
            return True
        self._stroke = dict(kind=kind, start=point, normal=normal,
                            screen=QPointF(pos), dabs=[(point, normal)],
                            end=point)
        self.view.update()
        return True

    def mouse_move(self, event):
        pos = event.pos()
        s = self._stroke
        if s is None:
            self._hover = self.hit(pos.x(), pos.y())
            self.view.update()
            return False
        if s["kind"] in DRAGS or s["kind"] == "pose":
            p = _plane_point(self.view, pos.x(), pos.y(), s["start"])
            if p is not None:
                s["end"] = p
        else:
            point, normal = self.hit(pos.x(), pos.y())
            if point is not None and _dist(point, s["dabs"][-1][0]) >= \
                    SPACING * self.panel.radius.value():
                s["dabs"].append((point, normal))
            self._hover = (point, normal) if point is not None else None
        self.view.update()
        return True

    def mouse_release(self, event):
        s, self._stroke = self._stroke, None
        if s is None:
            return False
        if s["kind"] == "pose":
            joint, self._joint = self._joint, None
            self.panel.commit(self.pose_rows(s, joint))
        else:
            self.panel.commit(self.rows(s))
        self.view.update()
        return True

    def wheel(self, event):
        return False

    # -- what a stroke becomes ------------------------------------------
    def rows(self, s):
        """The stroke as world-frame row specs (kind, point, radius,
        strength, direction)."""
        kind = s["kind"]
        radius = self.panel.radius.value()
        strength = self.panel.strength.value()
        if kind == "smooth":
            strength = abs(strength) or 1.0
        if kind in DRAGS:
            pull = [s["end"][k] - s["start"][k] for k in range(3)]
            length = math.sqrt(sum(c * c for c in pull))
            if length < 1e-6:
                return []
            if kind == "snake_hook":
                return [(kind, s["start"], radius, 1.0, pull, None)]
            return [(kind, s["start"], radius, length,
                     [c / length for c in pull], None)]
        dabs = s["dabs"]
        if kind in sculpt.LINES:
            if len(dabs) < 2:
                return []
            return [(kind, a[0], radius, strength,
                     [b[0][k] - a[0][k] for k in range(3)], None)
                    for a, b in zip(dabs, dabs[1:])]
        return [(kind, p, radius, strength, n, None) for p, n in dabs]

    def pose_rows(self, s, joint):
        if joint is None:
            return []
        _eye, _right, _up, forward = self.view._camera()
        # the joint sits inside the limb, not on its skin
        radius = self.panel.radius.value()
        pivot = [joint[0][k] - joint[1][k] * radius * 0.5 for k in range(3)]
        a = [s["start"][k] - pivot[k] for k in range(3)]
        b = [s["end"][k] - pivot[k] for k in range(3)]
        # the swing in the screen's plane, about the viewing axis
        cross = [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
                 a[0] * b[1] - a[1] * b[0]]
        sin = sum(cross[k] * forward[k] for k in range(3))
        cos = sum(a[k] * b[k] for k in range(3))
        angle = math.degrees(math.atan2(sin, cos))
        if abs(angle) < 0.2:
            return []
        return [("pose", pivot, radius, angle, list(forward), s["start"])]

    # -- the brush cursor -----------------------------------------------
    def paint(self, painter, project):
        radius = self.panel.radius.value()
        pen = QPen(QColor(255, 140, 0) if self._stroke is None
                   else QColor(255, 60, 30))
        pen.setWidthF(1.5)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        def circle(point, normal):
            if point is None:
                return
            c = project(point)
            if c is None:
                return
            # the radius as pixels: project a point a radius aside
            side = [0.0, 0.0, 1.0] if abs(normal[2]) < 0.9 else [1.0, 0, 0]
            t = [normal[1] * side[2] - normal[2] * side[1],
                 normal[2] * side[0] - normal[0] * side[2],
                 normal[0] * side[1] - normal[1] * side[0]]
            n = math.sqrt(sum(v * v for v in t)) or 1.0
            edge = project([point[k] + t[k] / n * radius for k in range(3)])
            r = math.hypot(edge[0] - c[0], edge[1] - c[1]) if edge else 8.0
            painter.drawEllipse(QPointF(c[0], c[1]), r, r)

        if self._hover is not None and self._hover[0] is not None:
            circle(*self._hover)
        if self._joint is not None:
            circle(*self._joint)
        s = self._stroke
        if s is None:
            return
        pts = [project(p) for p, _n in s["dabs"]] \
            if s["kind"] not in DRAGS and s["kind"] != "pose" \
            else [project(s["start"]), project(s["end"])]
        pts = [p for p in pts if p is not None]
        for a, b in zip(pts, pts[1:]):
            painter.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))

    def paint_overlay(self, painter):
        pass

    def close(self):
        if self.view.edit_tool is self:
            self.view.edit_tool = None
        self.view.update()


# ------------------------------------------------------------- the panel

class SculptPanel(QDialog):
    """Brush settings + the brush on the view. Closing the panel ends
    the sculpt (the strokes stay on the node)."""

    def __init__(self, window, node):
        super().__init__(window)
        self.setWindowTitle(
            language.tr("Sculpt — {name}").format(name=node.name))
        self.setWindowFlag(Qt.Tool, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.window_, self.node = window, node
        self._world = self._local = None
        form = QFormLayout()
        self.kind = QComboBox()
        for name in sculpt.KINDS:
            self.kind.addItem(language.tr(
                name.replace("_", " ").capitalize()), name)
        self.kind.setCurrentIndex(1)                 # inflate
        self.kind.currentIndexChanged.connect(lambda _i: self._hint())
        self.radius = QDoubleSpinBox()
        self.radius.setRange(0.05, 10000.0)
        self.radius.setValue(5.0)
        self.radius.setSuffix(" mm")
        self.radius.valueChanged.connect(
            lambda _v: self.window_.view3d.update())
        self.strength = QDoubleSpinBox()
        self.strength.setRange(-1000.0, 1000.0)
        self.strength.setDecimals(2)
        self.strength.setValue(1.0)
        self.mirror = QComboBox()
        for name in sculpt.MIRRORS:
            self.mirror.addItem(
                language.tr("none") if name == "none" else name, name)
        self.mirror.setCurrentIndex(self.mirror.findData(
            str(node.params.get("mirror", "none"))))
        self.mirror.currentIndexChanged.connect(
            lambda _i: self._set_mirror(self.mirror.currentData()))
        form.addRow(language.tr("Brush"), self.kind)
        form.addRow(language.tr("Radius"), self.radius)
        form.addRow(language.tr("Strength"), self.strength)
        form.addRow(language.tr("Mirror"), self.mirror)
        self.count = QLabel()
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        undo = QPushButton(language.tr("Undo last stroke"))
        undo.clicked.connect(self.undo_last)
        done = QPushButton(language.tr("Done"))
        done.clicked.connect(self.close)
        row = QHBoxLayout()
        row.addWidget(undo)
        row.addStretch(1)
        row.addWidget(done)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self.hint)
        lay.addWidget(QLabel(language.tr(
            "Drag over the surface to sculpt. Shift smooths, [ and ] "
            "change the size; a press off the model still orbits.")))
        lay.addWidget(self.count)
        lay.addLayout(row)
        self.tool = SculptTool(self)
        self._hint()
        self._refresh_count()
        self.arm()

    HINTS = {
        "grab": "Drag the surface where the mouse goes.",
        "inflate": "Puff out along the normals; negative pulls in.",
        "smooth": "Relax bumps (strength = passes).",
        "flatten": "Press onto the patch's plane (0-1).",
        "pinch": "Draw towards the brush centre (0-1).",
        "crease": "Drag to carve a groove strength mm deep.",
        "ridge": "Drag to raise a ridge: veins, tendons, scars.",
        "snake_hook": "Drag out of the surface to pull a horn, tentacle "
                      "or spike; strength scales the pull.",
        "draw": "Build up along the patch's own normal (mm).",
        "clay_strips": "Lay square slabs of clay strength mm thick.",
        "layer": "Raise an even plate strength mm high.",
        "elastic_grab": "Drag with a soft falloff the whole body follows.",
        "pose": "Click the joint, then drag the limb round it.",
        "mask": "Freeze where you paint (negative frees it again).",
    }

    def _hint(self):
        name = self.kind.currentData()
        self.hint.setText(language.tr(self.HINTS.get(name, "")))
        self.tool._joint = None

    def status(self, text, ms=5000):
        self.window_.statusBar().showMessage(text, ms)
        flash = getattr(self.window_.view3d, "flash", None)
        if flash is not None:
            flash(text)

    # -- the brush ------------------------------------------------------
    def arm(self):
        """Install the brush on the view over the CURRENT surface."""
        self._world, self._local = meshes(self.window_, self.node)
        view = self.window_.view3d
        if self._world is None:
            self.status(language.tr(
                "{name}: nothing to sculpt yet — put a solid inside "
                "it first.").format(name=self.node.name), 6000)
            return
        self.tool.reload(self._world)
        view.edit_tool = self.tool
        view.setMouseTracking(True)
        view.setFocus(Qt.OtherFocusReason)

    def commit(self, specs):
        """Land the stroke's rows (world frame) as one undo step."""
        rows = []
        for kind, point, radius, strength, direction, tip in specs:
            row = stroke_row(kind, point, radius, strength, direction,
                             world=self._world, local=self._local, tip=tip)
            if row is not None:
                rows.append(row)
        if not rows:
            if specs:
                self.status(language.tr(
                    "That stroke missed the sculpted surface."), 3000)
            return 0
        old = [list(r) for r in (self.node.params.get("strokes") or [])]
        self.window_.model.set_param(self.node, "strokes", old + rows)
        self._refresh_count()
        self.arm()                             # the surface has moved
        return len(rows)

    def _set_mirror(self, name):
        self.window_.model.set_param(self.node, "mirror", name)
        self.arm()

    def undo_last(self):
        rows = [list(r) for r in (self.node.params.get("strokes") or [])]
        if rows:
            self.window_.model.set_param(self.node, "strokes", rows[:-1])
        self._refresh_count()
        self.arm()

    def _refresh_count(self):
        self.count.setText(language.tr("{count} stroke(s)").format(
            count=len(self.node.params.get('strokes') or [])))

    def closeEvent(self, event):
        self.tool.close()
        super().closeEvent(event)


def start(window, node):
    """Open the sculpt panel for *node* (a sculpt) and put the brush on
    the 3D view."""
    old = getattr(window, "_sculpt_panel", None)
    if old is not None:
        try:
            old.close()
        except RuntimeError:                   # already deleted
            pass
    panel = SculptPanel(window, node)
    panel.show()
    window._sculpt_panel = panel
    return panel
