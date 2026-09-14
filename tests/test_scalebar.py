"""The 3D view's scale bar (scalebar.py).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QImage, QPainter
from PyQt5.QtWidgets import QApplication

from khervecad import mesh, scalebar
from khervecad.model import CadNode
from khervecad.view3d import View3D


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("ppu", [1e-6, 0.37, 1.0, 3.3, 59.9, 60.0, 171.0,
                                 5000.0, 2.5e7])
def test_a_round_length_always_fits(ppu):
    length = scalebar.nice_length(ppu)
    assert scalebar.MIN_PX <= length * ppu <= scalebar.MAX_PX
    mantissa = length / 10 ** math.floor(math.log10(length) + 1e-9)
    assert round(mantissa, 9) in (1, 2, 5)


def test_no_length_without_a_scale():
    assert scalebar.nice_length(0) is None
    assert scalebar.nice_length(float("inf")) is None


def test_label_speaks_the_document_unit():
    assert scalebar.label(20, "nm") == "20 nm"
    assert scalebar.label(0.5, "um") == "0.5 µm"
    assert scalebar.label(0.002, "mm") == "0.002 mm"


@pytest.mark.parametrize("projection", ["Perspective", "Orthographic"])
def test_bar_is_true_at_the_orbit_centre(app, projection):
    """A length L across the screen at the orbit centre spans exactly
    L x px_per_unit pixels: the bar measures what the camera turns
    about (and, in orthographic, everything)."""
    view = View3D()
    view.resize(800, 600)
    view.projection = projection
    view.target, view.distance = [3.0, -2.0, 1.0], 40.0
    view.yaw, view.pitch = 30.0, 20.0
    eye, right, up, forward = view._camera()
    a = view._project(eye, right, up, forward, view.target)
    far = [view.target[i] + 5.0 * right[i] for i in range(3)]
    b = view._project(eye, right, up, forward, far)
    assert abs((b[0] - a[0]) - 5.0 * scalebar.px_per_unit(view)) < 1e-6


def test_drawn_bottom_left(app):
    img = QImage(400, 300, QImage.Format_ARGB32)
    img.fill(Qt.white)
    painter = QPainter(img)
    length = scalebar.draw(painter, 400, 300, 2.0, "nm", QColor("black"))
    painter.end()
    assert length == 50                     # 100 px at 2 px per nm
    y = 300 - scalebar.MARGIN_BOTTOM
    for x in (scalebar.MARGIN_X + 5, scalebar.MARGIN_X + 95):
        assert img.pixelColor(x, y).lightnessF() < 0.5
    assert img.pixelColor(scalebar.MARGIN_X + 130, y).lightnessF() > 0.9


def test_view_paints_the_bar_only_when_asked(app):
    view = View3D()
    view.resize(400, 300)
    view.set_mesh(mesh.tessellate(CadNode("sphere", "S", dict(radius=5.0))),
                  "test")
    view.fit()
    view.unit = "nm"

    def bar_row(on):
        view.scale_bar = on
        img, _camera = view.snapshot(400, 300)
        y = img.height() - scalebar.MARGIN_BOTTOM * img.height() // 300
        return [img.pixelColor(x, y).rgb()
                for x in range(img.width() // 20, img.width() // 6)]
    assert bar_row(True) != bar_row(False)
