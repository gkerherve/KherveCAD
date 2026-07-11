"""3D preview — software-rendered shaded viewer.

Bottom-right frame of the main window. Renders a triangle mesh with a
painter's-algorithm rasteriser (no OpenGL dependency): orbit with the
left mouse button, pan with the right/middle button, zoom with the
wheel. The mesh comes from the OpenSCAD engine when available, or
from the built-in tessellator otherwise; a badge in the corner says
which one produced it.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import QWidget


class View3D(QWidget):
    """Orbiting shaded view of a triangle mesh."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mesh = []                  # [(v0, v1, v2)] world space
        self.colors = None              # optional per-face colours
        self.source = "no model"
        self.yaw = 35.0                 # degrees around Z
        self.pitch = 22.0               # degrees above the XY plane
        self.distance = 160.0
        self.target = [0.0, 0.0, 10.0]
        self._last = None
        self._mode = None
        self.setMinimumHeight(160)
        self.setMouseTracking(False)

    # ------------------------------------------------------------- API
    def set_mesh(self, mesh, source: str, colors=None):
        """*colors* is an optional per-face list of (colorstring,
        alpha) — colours from color() nodes shown by the preview."""
        self.mesh = mesh or []
        self.colors = colors if colors and len(colors) == len(self.mesh) \
            else None
        self.source = source
        self.update()

    def fit(self):
        """Frame the whole mesh."""
        if not self.mesh:
            return
        xs = [v[0] for tri in self.mesh for v in tri]
        ys = [v[1] for tri in self.mesh for v in tri]
        zs = [v[2] for tri in self.mesh for v in tri]
        self.target = [(min(xs) + max(xs)) / 2,
                       (min(ys) + max(ys)) / 2,
                       (min(zs) + max(zs)) / 2]
        size = max(max(xs) - min(xs), max(ys) - min(ys),
                   max(zs) - min(zs), 1.0)
        self.distance = size * 2.2
        self.update()

    # -------------------------------------------------------- projection
    def _camera(self):
        yaw = math.radians(self.yaw)
        pitch = math.radians(self.pitch)
        # camera basis: forward points at the target.
        fx = -math.cos(pitch) * math.cos(yaw)
        fy = -math.cos(pitch) * math.sin(yaw)
        fz = -math.sin(pitch)
        rx, ry, rz = -math.sin(yaw), math.cos(yaw), 0.0
        ux = fy * rz - fz * ry
        uy = fz * rx - fx * rz
        uz = fx * ry - fy * rx
        ex = self.target[0] - fx * self.distance
        ey = self.target[1] - fy * self.distance
        ez = self.target[2] - fz * self.distance
        return (ex, ey, ez), (rx, ry, rz), (ux, uy, uz), (fx, fy, fz)

    def _project(self, eye, right, up, forward, v):
        dx, dy, dz = v[0] - eye[0], v[1] - eye[1], v[2] - eye[2]
        cx = dx * right[0] + dy * right[1] + dz * right[2]
        cy = dx * up[0] + dy * up[1] + dz * up[2]
        cz = dx * forward[0] + dy * forward[1] + dz * forward[2]
        if cz < 0.1:
            return None
        f = 1.2 * min(self.width(), self.height())
        return (self.width() / 2 + f * cx / cz,
                self.height() / 2 - f * cy / cz, cz)

    # ---------------------------------------------------------- painting
    def paintEvent(self, event):
        from .style import tokens
        t = tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(t["editor"]))

        eye, right, up, forward = self._camera()
        self._draw_ground(painter, t, eye, right, up, forward)

        base = QColor(t["select"])
        light = (0.35, -0.5, 0.75)
        norm = math.sqrt(sum(c * c for c in light))
        light = tuple(c / norm for c in light)

        faces = []
        for index, tri in enumerate(self.mesh):
            pts = [self._project(eye, right, up, forward, v)
                   for v in tri]
            if any(p is None for p in pts):
                continue
            depth = (pts[0][2] + pts[1][2] + pts[2][2]) / 3
            ux, uy, uz = (tri[1][0] - tri[0][0], tri[1][1] - tri[0][1],
                          tri[1][2] - tri[0][2])
            vx, vy, vz = (tri[2][0] - tri[0][0], tri[2][1] - tri[0][1],
                          tri[2][2] - tri[0][2])
            nx, ny, nz = (uy * vz - uz * vy, uz * vx - ux * vz,
                          ux * vy - uy * vx)
            length = math.sqrt(nx * nx + ny * ny + nz * nz)
            if length < 1e-12:
                continue
            shade = abs(nx * light[0] + ny * light[1]
                        + nz * light[2]) / length
            face_color = self.colors[index] if self.colors else None
            faces.append((depth, pts, shade, face_color))

        faces.sort(key=lambda f: -f[0])
        pen = QPen(QColor(0, 0, 0, 30))
        pen.setWidthF(0.5)
        for _depth, pts, shade, face_color in faces:
            value = 0.35 + 0.65 * shade
            if face_color is not None:
                own = QColor(face_color[0])
                if not own.isValid():
                    own = base
                color = QColor.fromHsvF(
                    max(own.hueF(), 0.0), own.saturationF(),
                    min(own.valueF() * (0.45 + 0.55 * shade), 1.0))
                color.setAlphaF(max(min(face_color[1], 1.0), 0.15))
            else:
                color = QColor.fromHsvF(
                    base.hueF() if base.hueF() >= 0 else 0.58,
                    base.saturationF() * 0.75,
                    min(value, 1.0))
            painter.setPen(pen)
            painter.setBrush(color)
            painter.drawPolygon(QPolygonF(
                [QPointF(p[0], p[1]) for p in pts]))

        self._draw_axes(painter, t, eye, right, up, forward)
        painter.setPen(QColor(t["text"]))
        painter.drawText(8, self.height() - 8,
                         f"{self.source} — {len(self.mesh)} triangles")
        painter.end()

    def _draw_ground(self, painter, t, eye, right, up, forward):
        pen = QPen(QColor(t["border"]))
        pen.setWidthF(0.7)
        painter.setPen(pen)
        span, step = 100, 10
        for i in range(-span, span + 1, step):
            for a, b in (((i, -span, 0), (i, span, 0)),
                         ((-span, i, 0), (span, i, 0))):
                pa = self._project(eye, right, up, forward, a)
                pb = self._project(eye, right, up, forward, b)
                if pa and pb:
                    painter.drawLine(QPointF(pa[0], pa[1]),
                                     QPointF(pb[0], pb[1]))

    def _draw_axes(self, painter, t, eye, right, up, forward):
        origin = self._project(eye, right, up, forward, (0, 0, 0))
        if origin is None:
            return
        scale = self.distance / 8.0
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        for axis, label, color in (((scale, 0, 0), "X", "#d64545"),
                                   ((0, scale, 0), "Y", "#3f9e4d"),
                                   ((0, 0, scale), "Z", "#3a6fd8")):
            tip = self._project(eye, right, up, forward, axis)
            if tip:
                pen = QPen(QColor(color))
                pen.setWidthF(1.6)
                painter.setPen(pen)
                painter.drawLine(QPointF(origin[0], origin[1]),
                                 QPointF(tip[0], tip[1]))
                painter.drawText(QPointF(tip[0] + 3, tip[1] - 3),
                                 label)

    # ------------------------------------------------------------- mouse
    def mousePressEvent(self, event):
        self._last = event.pos()
        self._mode = "orbit" if event.button() == Qt.LeftButton else "pan"

    def mouseReleaseEvent(self, event):
        self._last = None
        self._mode = None

    def mouseMoveEvent(self, event):
        if self._last is None:
            return
        delta = event.pos() - self._last
        self._last = event.pos()
        if self._mode == "orbit":
            self.yaw -= delta.x() * 0.5
            self.pitch = max(-89.0, min(89.0,
                                        self.pitch + delta.y() * 0.5))
        else:
            _eye, right, up, _fwd = self._camera()
            scale = self.distance / 600.0
            for i in range(3):
                self.target[i] -= right[i] * delta.x() * scale
                self.target[i] += up[i] * delta.y() * scale
        self.update()

    def wheelEvent(self, event):
        factor = 0.87 if event.angleDelta().y() > 0 else 1.15
        self.distance = max(2.0, min(5000.0, self.distance * factor))
        self.update()

    def mouseDoubleClickEvent(self, event):
        self.fit()
