"""Tests for 3D render styles and selection glow.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad.view3d import RENDER_STYLES, View3D


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def test_every_style_paints_without_error(app):
    view = View3D()
    view.resize(200, 200)
    view.set_mesh([((0, 0, 0), (10, 0, 0), (0, 10, 0)),
                   ((0, 0, 0), (0, 10, 0), (0, 0, 10))], "test")
    view.set_highlight_mesh([((0, 0, 0), (10, 0, 0), (0, 10, 0))])
    for style in RENDER_STYLES:
        view.set_style(style)
        assert view.style == style
        view.grab()                    # exercises the paint path


def test_style_persists(app):
    view = View3D()
    view.set_style("Brushed metal")
    other = View3D()
    assert other.style == "Brushed metal"
    view.set_style("Shaded")           # restore default for other tests


def test_unknown_style_ignored(app):
    view = View3D()
    view.set_style("Shaded")
    view.set_style("Nonsense")
    assert view.style == "Shaded"


def _cube(s=20.0):
    pts = [(0, 0, 0), (s, 0, 0), (s, s, 0), (0, s, 0),
           (0, 0, s), (s, 0, s), (s, s, s), (0, s, s)]
    faces = [(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6),
             (0, 4, 5), (0, 5, 1), (1, 5, 6), (1, 6, 2),
             (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0)]
    return [tuple(pts[i] for i in f) for f in faces]


def _central_avg(view):
    from PyQt5.QtCore import QSize
    from PyQt5.QtGui import QImage, QPainter
    w, h = view.width(), view.height()
    img = QImage(QSize(w, h), QImage.Format_ARGB32)
    img.fill(0)
    painter = QPainter(img)
    view.render(painter)
    painter.end()
    r = g = b = n = 0
    for x in range(w // 3, 2 * w // 3, 4):
        for y in range(h // 3, 2 * h // 3, 4):
            c = img.pixelColor(x, y)
            r += c.red(); g += c.green(); b += c.blue(); n += 1
    return (r / n, g / n, b / n)


def test_styles_render_distinctly(app):
    """Each render style must produce a visibly different image — a
    regression guard against styles collapsing into look-alikes."""
    view = View3D()
    view.resize(300, 300)
    view.set_mesh(_cube(), "test")
    view.fit()
    avgs = {}
    for style in RENDER_STYLES:
        view.set_style(style)
        avgs[style] = _central_avg(view)

    def dist(a, b):
        return sum(abs(x - y) for x, y in zip(a, b))

    # every pair of styles differs by a clear margin
    styles = list(RENDER_STYLES)
    for i in range(len(styles)):
        for j in range(i + 1, len(styles)):
            d = dist(avgs[styles[i]], avgs[styles[j]])
            assert d > 20, (styles[i], styles[j], d)
    # Matte used to be nearly identical to Shaded — keep them apart
    assert dist(avgs["Matte"], avgs["Shaded"]) > 60


def test_fit_centers_the_model(app):
    """fit() frames the mesh centred in the pane and filling most of
    the height, so it never sits low with dead space above."""
    view = View3D()
    view.resize(400, 300)
    mesh = _cube(30.0)
    # offset the cube well away from the origin/target start
    mesh = [tuple((x + 70, y - 40, z + 25) for x, y, z in tri)
            for tri in mesh]
    view.set_mesh(mesh, "test")
    view.fit()
    eye, right, up, forward = view._camera()
    xs, ys = [], []
    for tri in mesh:
        for v in tri:
            p = view._project(eye, right, up, forward, v)
            if p:
                xs.append(p[0]); ys.append(p[1])
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    assert abs(cx - view.width() / 2) < 12
    assert abs(cy - view.height() / 2) < 12       # centred, not low
    fill_h = (max(ys) - min(ys)) / view.height()
    assert fill_h > 0.7                            # fills the pane
