"""Platform & shadow stage for the 3D preview.

An optional "product shot" setting for the 3D view (View > 3D Platform
& Shadow): instead of the ground grid, the model stands on a round
slab — a turntable whose top is exactly the mesh's lowest Z — and
casts a soft shadow onto it from a light far away at the top-left of
the viewer.

The light is tied to the camera, not the world: it sits up, to the
viewer's left and a little behind the model, so however the user
orbits, the shadow falls towards the bottom-right of the model on
screen — the way a photographer keeps the key light over one
shoulder. It is directional (parallel rays), since the light is far.

Everything here is drawn *before* the model, and nothing ever has to
be depth-sorted against it: the model's bounding box fits inside the
disc and stands on its top face, so from any camera above that face
the slab lies wholly behind the model. From below, the stage is not
drawn at all and the view keeps its grid.

Cost. The preview is pure Python, so the shadow is cast from a
*vertex-clustered* copy of the mesh (`cluster`: at most
`SHADOW_TARGET` triangles, built once per mesh). Clustering, unlike
the view's strided draft, keeps the surface closed, so the shadow has
no holes. Each triangle is projected along the light onto the plane
in plain ground coordinates — only 2 multiply-adds per vertex — and
only the light-facing ones are kept (they all wind the same way, so a
single winding-fill path is their union). That path depends on the
camera's *yaw* alone and is cached per yaw; the ground-to-screen step
is one projective `QTransform` Qt applies in C++, near-plane clipping
included. The path is filled into a mask at a fraction of the view's
resolution, box-blurred there, and scaled up smoothly: overlapping
triangles cannot darken each other, and the edge comes out soft.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (QColor, QImage, QLinearGradient, QPainter,
                         QPainterPath, QPen, QPolygonF, QTransform)

#: the shadow is cast from a clustered copy of the mesh this size at most
SHADOW_TARGET = 5000

#: where the light sits, in the camera's frame: this far to the viewer's
#: left and this far behind the model for every 1 unit up. The shadow's
#: length is their hypotenuse times the height (~0.62: a key light about
#: 58 degrees up).
LIGHT_LEFT = 0.52
LIGHT_BACK = 0.34

#: the platform's radius as a fraction of the model's XY diagonal, and
#: its thickness as a fraction of that radius
RADIUS_FACTOR = 0.7
THICKNESS_FACTOR = 0.075

#: how dark the shadow is where it is fully in shadow (0..1)
SHADOW_OPACITY = 0.36

#: segments around the platform's rim
RIM_SEGMENTS = 144

#: the shadow mask's short side in pixels: the view is down-sampled to
#: about this much, so the blur (and the soft edge) scales with the view
MASK_SHORT_SIDE = 170


def light_dir(right, forward):
    """Unit vector *towards* the light: world up, the viewer's left
    (-right) and slightly behind the model (+forward, flattened), so the
    shadow falls to the bottom-right of the model on screen."""
    fx, fy = forward[0], forward[1]
    flat = math.hypot(fx, fy)
    if flat < 1e-9:                     # looking straight down: yaw is
        fx, fy = -right[1], right[0]    # still in `right`, take it there
        flat = math.hypot(fx, fy) or 1.0
    fx, fy = fx / flat, fy / flat
    lx = -right[0] * LIGHT_LEFT + fx * LIGHT_BACK
    ly = -right[1] * LIGHT_LEFT + fy * LIGHT_BACK
    lz = 1.0
    norm = math.sqrt(lx * lx + ly * ly + lz * lz)
    return lx / norm, ly / norm, lz / norm


def bounds(mesh):
    """((xmin, ymin, zmin), (xmax, ymax, zmax)) of a triangle list, or
    None when it is empty."""
    if not mesh:
        return None
    xs = [v[0] for tri in mesh for v in tri]
    ys = [v[1] for tri in mesh for v in tri]
    zs = [v[2] for tri in mesh for v in tri]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def cluster(mesh, box, target=SHADOW_TARGET):
    """*mesh* decimated by vertex clustering to at most ~*target*
    triangles (the mesh itself when already small enough).

    Every vertex snaps to the centre of its cell in a uniform grid;
    triangles whose corners collapse together vanish and duplicates
    merge. Unlike a strided subset this keeps the surface closed — a
    shadow cast from it has no holes — and the error is half a cell,
    which the shadow's blur hides."""
    if len(mesh) <= target:
        return list(mesh)
    (x0, y0, z0), (x1, y1, z1) = box
    size = max(x1 - x0, y1 - y0, z1 - z0, 1e-6)
    cells = 96
    out = []
    for _attempt in range(3):
        step = size / cells
        inv = 1.0 / step
        half = 0.5 * step
        seen = set()
        out = []
        for a, b, c in mesh:
            ka = (int((a[0] - x0) * inv), int((a[1] - y0) * inv),
                  int((a[2] - z0) * inv))
            kb = (int((b[0] - x0) * inv), int((b[1] - y0) * inv),
                  int((b[2] - z0) * inv))
            if ka == kb:
                continue
            kc = (int((c[0] - x0) * inv), int((c[1] - y0) * inv),
                  int((c[2] - z0) * inv))
            if kc == ka or kc == kb:
                continue
            # one key per triangle whatever corner it starts from, with
            # the winding kept (it is what tells light-facing faces)
            key = min((ka, kb, kc), (kb, kc, ka), (kc, ka, kb))
            if key in seen:
                continue
            seen.add(key)
            out.append(tuple((x0 + k[0] * step + half,
                              y0 + k[1] * step + half,
                              z0 + k[2] * step + half) for k in key))
        if len(out) <= target * 1.15:
            break
        # the count goes with the surface area, i.e. with cells squared
        cells = max(int(cells * math.sqrt(target / len(out)) * 0.95), 8)
    return out


def _ground_homography(view, eye, right, up, forward, z0):
    """QTransform mapping ground points (x, y) on the plane z = *z0* to
    widget pixels — the view's own projection, perspective or
    orthographic, as one 3x3 matrix Qt can apply (and near-clip)."""
    ex, ey, ez = eye
    rx, ry, rz = right
    ux, uy, uz = up
    fx, fy, fz = forward
    hw = view.width() * 0.5
    hh = view.height() * 0.5
    dz = z0 - ez
    cx0 = -ex * rx - ey * ry + dz * rz
    cy0 = -ex * ux - ey * uy + dz * uz
    cz0 = -ex * fx - ey * fy + dz * fz
    if view.projection == "Orthographic":
        s = view._focal() / max(view.distance, 1e-6)
        return QTransform(s * rx, -s * ux, 0.0,
                          s * ry, -s * uy, 0.0,
                          hw + s * cx0, hh - s * cy0, 1.0)
    f = view._focal()
    return QTransform(hw * fx + f * rx, hh * fx - f * ux, fx,
                      hw * fy + f * ry, hh * fy - f * uy, fy,
                      hw * cz0 + f * cx0, hh * cz0 - f * cy0, cz0)


def palette(view, tokens):
    """(top, side, rim, shadow opacity) for the platform, chosen to sit
    well on the current background: a light grey slab on light
    backgrounds, a slate one on dark ones."""
    from .view3d import BACKGROUNDS
    pair = BACKGROUNDS.get(view.background)
    ground = QColor(pair[1]) if pair else QColor(tokens["editor"])
    if ground.lightnessF() < 0.5:
        return (QColor("#5b636d"), QColor("#3b4148"), QColor("#7d8690"),
                SHADOW_OPACITY + 0.12)
    return (QColor("#eceef1"), QColor("#b6bdc5"), QColor("#ffffff"),
            SHADOW_OPACITY)


class Stage:
    """The platform and its shadow for one View3D, with the per-mesh
    and per-yaw caches that keep it cheap to repaint.

    Caches are keyed by the identity of the mesh list: View3D replaces
    the list on every set_mesh and never edits one in place."""

    def __init__(self):
        self._mesh = None
        self._box = None
        self._tris = []             # the clustered shadow caster
        self._path_key = None
        self._path = None

    # -------------------------------------------------------- caches
    def _prepare(self, mesh):
        if mesh is not self._mesh:
            self._mesh = mesh
            self._box = bounds(mesh)
            self._tris = cluster(mesh, self._box) if self._box else []
            self._path_key = self._path = None
        return self._box

    def geometry(self, mesh):
        """(cx, cy, z0, radius, thickness) of the platform under *mesh*,
        or None for an empty mesh."""
        box = self._prepare(mesh)
        if box is None:
            return None
        (x0, y0, z0), (x1, y1, z1) = box
        dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
        diag = math.hypot(dx, dy)
        # a tall, slim model still gets a disc its shadow lands on: the
        # shadow of the top reaches ~0.6 x the height from the footprint
        radius = max(RADIUS_FACTOR * diag, 0.5 * (diag + dz), 1.0)
        return ((x0 + x1) * 0.5, (y0 + y1) * 0.5, z0, radius,
                radius * THICKNESS_FACTOR)

    def rim_points(self, mesh, segments=24):
        """Points round the platform's top and bottom rims, for View3D.fit
        to frame the whole stage rather than just the model."""
        geo = self.geometry(mesh)
        if geo is None:
            return []
        cx, cy, z0, radius, thick = geo
        pts = []
        for i in range(segments):
            t = 2.0 * math.pi * i / segments
            x, y = cx + radius * math.cos(t), cy + radius * math.sin(t)
            pts.append((x, y, z0))
            pts.append((x, y, z0 - thick))
        return pts

    def shadow_path(self, light, z0):
        """The shadow on the plane z = *z0* in ground coordinates: the
        union (winding fill) of the light-facing triangles projected
        along *light*. Cached until the light moves."""
        key = (round(light[0], 4), round(light[1], 4), z0)
        if key == self._path_key:
            return self._path
        lx, ly, lz = light
        kx, ky = lx / lz, ly / lz
        path = QPainterPath()
        path.setFillRule(Qt.WindingFill)
        move, line, close = path.moveTo, path.lineTo, path.closeSubpath
        for a, b, c in self._tris:
            h = a[2] - z0
            ax, ay = a[0] - kx * h, a[1] - ky * h
            h = b[2] - z0
            bx, by = b[0] - kx * h, b[1] - ky * h
            h = c[2] - z0
            cx, cy = c[0] - kx * h, c[1] - ky * h
            # the projected winding is the sign of normal . light: keep
            # the faces lit from the light (they all turn the same way,
            # so winding fill unions them without cancelling)
            if (bx - ax) * (cy - ay) - (by - ay) * (cx - ax) <= 0.0:
                continue
            move(ax, ay)
            line(bx, by)
            line(cx, cy)
            close()
        self._path_key, self._path = key, path
        return path

    # ------------------------------------------------------- drawing
    def draw(self, view, painter, tokens, eye, right, up, forward):
        """Paint the platform and the shadow. Returns False — nothing
        drawn — when there is no model or the camera is below the
        platform's top, so the caller can draw its grid instead."""
        geo = self.geometry(view.mesh)
        if geo is None:
            return False
        cx, cy, z0, radius, thick = geo
        ortho = view.projection == "Orthographic"
        if (forward[2] > -1e-3) if ortho else (eye[2] <= z0 + 1e-6):
            return False
        top_c, side_c, rim_c, opacity = palette(view, tokens)
        light = light_dir(right, forward)

        # rim points, top and bottom (None = behind the near plane)
        top, bottom = [], []
        for i in range(RIM_SEGMENTS):
            t = 2.0 * math.pi * i / RIM_SEGMENTS
            x, y = cx + radius * math.cos(t), cy + radius * math.sin(t)
            top.append(view._project(eye, right, up, forward, (x, y, z0)))
            bottom.append(view._project(eye, right, up, forward,
                                        (x, y, z0 - thick)))
        clipped = any(p is None for p in top) \
            or any(p is None for p in bottom)

        painter.save()
        antialias = painter.testRenderHint(QPainter.Antialiasing)
        if not clipped:
            self._draw_side(painter, top, bottom, side_c, light, eye,
                            forward, ortho, cx, cy, radius, z0)
        homography = _ground_homography(view, eye, right, up, forward, z0)
        disc = QPainterPath()
        disc.addEllipse(QPointF(cx, cy), radius, radius)
        disc = homography.map(disc)               # near-clipped by Qt
        grad = self._top_gradient(disc.boundingRect(), top_c)
        painter.setPen(Qt.NoPen)
        painter.setBrush(grad)
        painter.drawPath(disc)

        self._draw_shadow(view, painter, homography, disc,
                          self.shadow_path(light, z0), opacity, antialias)

        if not clipped:                           # a bright lip on the rim
            pen = QPen(rim_c)
            pen.setWidthF(1.1)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPolygon(QPolygonF([QPointF(p[0], p[1])
                                           for p in top]))
        painter.restore()
        return True

    @staticmethod
    def _top_gradient(rect, top_c):
        """The top face, a touch brighter towards the light (top-left
        on screen) and a touch darker away from it."""
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, top_c.lighter(104))
        grad.setColorAt(1.0, top_c.darker(109))
        return grad

    @staticmethod
    def _draw_side(painter, top, bottom, side_c, light, eye, forward,
                   ortho, cx, cy, radius, z0):
        """The slab's edge: every rim segment facing the camera, shaded
        by how squarely it faces the light. A convex slab's front faces
        never overlap, so no sorting is needed."""
        n = len(top)
        lx, ly = light[0], light[1]
        flat = math.hypot(lx, ly) or 1.0
        lx, ly = lx / flat, ly / flat
        hue, sat, val, _a = side_c.getHsvF()
        hue = max(hue, 0.0)
        for i in range(n):
            j = (i + 1) % n
            t = 2.0 * math.pi * (i + 0.5) / n
            nx, ny = math.cos(t), math.sin(t)
            if ortho:
                facing = nx * forward[0] + ny * forward[1] < 0.0
            else:
                px, py = cx + radius * nx, cy + radius * ny
                facing = (px - eye[0]) * nx + (py - eye[1]) * ny < 0.0
            if not facing:
                continue
            lit = 0.5 + 0.5 * (nx * lx + ny * ly)     # 0 away .. 1 facing
            color = QColor.fromHsvF(hue, sat,
                                    min(val * (0.82 + 0.36 * lit), 1.0))
            quad = QPolygonF([QPointF(top[i][0], top[i][1]),
                              QPointF(top[j][0], top[j][1]),
                              QPointF(bottom[j][0], bottom[j][1]),
                              QPointF(bottom[i][0], bottom[i][1])])
            pen = QPen(color)
            pen.setWidthF(1.0)           # no seams between the segments
            painter.setPen(pen)
            painter.setBrush(color)
            painter.drawPolygon(quad)

    @staticmethod
    def _draw_shadow(view, painter, homography, disc, path, opacity,
                     antialias):
        """Fill the shadow path into a small mask, box-blur it there and
        lay it over the platform's top, scaled up smoothly."""
        if path.isEmpty():
            return
        w, h = view.width(), view.height()
        k = max(min(w, h) / MASK_SHORT_SIDE, 1.0)
        mw, mh = max(int(w / k) + 2, 2), max(int(h / k) + 2, 2)
        sharp = QImage(mw, mh, QImage.Format_ARGB32_Premultiplied)
        sharp.fill(Qt.transparent)
        mp = QPainter(sharp)
        mp.setRenderHint(QPainter.Antialiasing, antialias)
        mp.setPen(Qt.NoPen)
        mp.setBrush(QColor(0, 0, 0))
        mp.setTransform(homography * QTransform.fromScale(1.0 / k, 1.0 / k))
        mp.drawPath(path)
        mp.end()
        # 3x3 box blur: nine offset copies summed at 1/9 each (Plus mode
        # adds, so this is a true average, not a stack of overlays)
        soft = QImage(mw, mh, QImage.Format_ARGB32_Premultiplied)
        soft.fill(Qt.transparent)
        bp = QPainter(soft)
        bp.setCompositionMode(QPainter.CompositionMode_Plus)
        bp.setOpacity(1.0 / 9.0)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                bp.drawImage(dx, dy, sharp)
        bp.end()
        painter.save()
        painter.setClipPath(disc, Qt.IntersectClip)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setOpacity(opacity)
        painter.drawImage(QRectF(0, 0, mw * k, mh * k), soft,
                          QRectF(0, 0, mw, mh))
        painter.restore()
