"""Tests for the 3D preview's platform & shadow stage (stage.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtCore import QSettings, QSize
from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtWidgets import QApplication

from khervecad import stage
from khervecad.view3d import _SETTINGS, View3D


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def clean_stage_setting():
    """The stage persists in QSettings (the user's own app reads it), so
    start from no value and put back whatever was there."""
    settings = QSettings(*_SETTINGS)
    saved = settings.value("render_stage")
    settings.remove("render_stage")
    yield
    if saved is None:
        settings.remove("render_stage")
    else:
        settings.setValue("render_stage", saved)


def _box(x, y, z, s):
    """An axis-aligned cube, outward (counter-clockwise) winding."""
    pts = [(x, y, z), (x + s, y, z), (x + s, y + s, z), (x, y + s, z),
           (x, y, z + s), (x + s, y, z + s), (x + s, y + s, z + s),
           (x, y + s, z + s)]
    faces = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
             (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
             (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    return [tuple(pts[i] for i in f) for f in faces]


def _view(mesh, stage_on):
    """A small view with fixed look settings — set as attributes, not
    through the persisting setters, so the user's QSettings stay put."""
    view = View3D()
    view.lighting_bar.hide()
    view.resize(260, 260)
    view.background = "Studio"
    view.projection = "Perspective"
    view.style = "Shaded"
    view.stage = stage_on
    view.set_mesh(mesh, "test", bsp=None)
    view.wait_for_bsp()
    view.yaw, view.pitch = 35.0, 25.0
    view.fit()
    return view


def _twin(view, stage_on):
    """The same scene and camera with the stage switched — a stage-on
    fit() also frames the platform, so fitting again would move it."""
    other = _view(list(view.mesh), stage_on)
    other.yaw, other.pitch = view.yaw, view.pitch
    other.distance, other.target = view.distance, list(view.target)
    return other


def _image(view):
    img = QImage(QSize(view.width(), view.height()), QImage.Format_ARGB32)
    img.fill(0)
    painter = QPainter(img)
    view.render(painter)
    painter.end()
    return img


def _lum(img, x, y):
    c = img.pixelColor(int(round(x)), int(round(y)))
    return c.red() + c.green() + c.blue()


def test_stage_is_off_by_default_and_persists(app, clean_stage_setting):
    view = View3D()
    assert view.stage is False
    seen = []
    view.stage_toggled.connect(seen.append)
    view.set_stage(True)
    assert view.stage is True and seen == [True]
    assert View3D().stage is True          # a new view reads it back
    view.set_stage(False)
    assert View3D().stage is False


def test_shadow_falls_below_right_of_a_floating_cube(app):
    """A cube floating 30 mm over the platform casts its shadow down and
    to the right on screen, where the platform is then darker than with
    the stage off — and darker than the mirror spot up and to the left."""
    # a tiny block at z = 0 sets the platform's height
    mesh = _box(-30, -30, 0, 2) + _box(-10, -10, 30, 20)
    on = _view(mesh, True)
    eye, right, up, forward = on._camera()
    lx, ly, lz = stage.light_dir(right, forward)
    # where the middle of the cube (z = 40) lands along the light
    sx, sy = -lx / lz * 40.0, -ly / lz * 40.0
    centre = on._project(eye, right, up, forward, (0.0, 0.0, 0.0))
    shadow = on._project(eye, right, up, forward, (sx, sy, 0.0))
    mirror = on._project(eye, right, up, forward, (-sx, -sy, 0.0))
    assert shadow[0] > centre[0] and shadow[1] > centre[1]  # bottom-right
    lit = _image(on)
    off = _image(_twin(on, False))
    assert _lum(lit, *shadow[:2]) < _lum(off, *shadow[:2]) - 60
    assert _lum(lit, *shadow[:2]) < _lum(lit, *mirror[:2]) - 60


def test_the_shadow_follows_the_camera(app):
    """The light hangs off the camera, so after orbiting half-way round
    the shadow still falls to the bottom-right on screen."""
    view = _view(_box(-10, -10, 0, 20), True)
    for yaw in (35.0, 125.0, 215.0, 305.0):
        view.yaw = yaw
        eye, right, up, forward = view._camera()
        lx, ly, lz = stage.light_dir(right, forward)
        a = view._project(eye, right, up, forward, (0.0, 0.0, 0.0))
        b = view._project(eye, right, up, forward,
                          (-lx / lz * 10, -ly / lz * 10, 0.0))
        assert b[0] > a[0] and b[1] > a[1], yaw


def test_platform_sits_under_the_model(app):
    mesh = _box(5, -20, 3, 10) + _box(-15, 0, 7, 4)
    cx, cy, z0, radius, thick = stage.Stage().geometry(mesh)
    assert z0 == 3                                  # the lowest point
    assert (cx, cy) == (0.0, -8.0)                  # bbox centre in XY
    corner = math.hypot(15 - cx, 4 - cy)            # farthest bbox corner
    assert radius > corner and thick > 0            # the footprint fits


def test_camera_below_the_plane_draws_no_platform(app):
    on = _view(_box(-10, -10, 0, 20), True)
    on.pitch = -30.0
    off = _twin(on, False)
    assert _image(on) == _image(off)                # the grid, as before


def test_an_empty_mesh_does_not_crash(app):
    on = _view([], True)
    assert _image(on) == _image(_twin(on, False))   # the grid, no platform


def test_snapshot_carries_the_stage(app):
    view = _view(_box(-10, -10, 0, 20), True)
    with_stage, _ = view.snapshot(160, 160)
    view.stage = False
    without, _ = view.snapshot(160, 160)
    assert with_stage != without


def test_cluster_decimates_without_losing_the_outline(app):
    """A dense sphere clusters to the target size and keeps its extent
    (the shadow is cast from the clustered copy)."""
    tris = []
    n = 80                                          # 12 640 triangles
    for i in range(n):
        for j in range(2 * n):
            def p(a, b):
                th, ph = math.pi * a / n, math.pi * b / n
                return (10 * math.sin(th) * math.cos(ph),
                        10 * math.sin(th) * math.sin(ph),
                        10 * math.cos(th))
            a, b, c, d = p(i, j), p(i + 1, j), p(i + 1, j + 1), p(i, j + 1)
            tris.append((a, b, c))
            tris.append((a, c, d))
    box = stage.bounds(tris)
    small = stage.cluster(tris, box, target=2000)
    assert 200 < len(small) <= 2000 * 1.15
    (x0, _y0, _z0), (x1, _y1, _z1) = stage.bounds(small)
    assert x0 == pytest.approx(-10, abs=1.0) and x1 == pytest.approx(10,
                                                                     abs=1.0)
