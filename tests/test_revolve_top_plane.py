# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""Revolved Boss on a shape drawn straight on the Top plane (2026-11-12,
the user: the rectangle was stood up and spun about Z)."""

import pytest
from PyQt5.QtWidgets import QApplication


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app):
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    w.show()
    QApplication.processEvents()
    return w


def _span(win, obj, node):
    from khervecad import mesh
    tris = mesh.transform_mesh(mesh.ancestor_matrix(node, {}, stop=obj),
                               mesh.tessellate(node, {}))
    return [(min(v[i] for t in tris for v in t),
             max(v[i] for t in tris for v in t)) for i in range(3)]


def test_a_top_plane_rectangle_revolves_about_its_y_axis(win):
    from khervecad import revolve_feature, toolbar_style
    win._interface_style = "SolidWorks"
    m = win.model
    obj = m.add_node("component", {}, name="Exercise9")
    r = m.add_node("rect", dict(x=0, y=0, width=40, height=10),
                   parent=obj, name="Base")
    tool = revolve_feature.revolve(win, [r])
    assert tool is not None and tool.type == "rotate_extrude"
    (x0, x1), (y0, y1), (z0, z1) = _span(win, obj, tool)
    assert abs(x0 + 40) < 0.5 and abs(x1 - 40) < 0.5
    assert abs(y0) < 1e-6 and abs(y1 - 10) < 1e-6      # stays in its plane
    assert abs(z0 + 40) < 0.5 and abs(z1 - 40) < 0.5


def test_the_classic_style_keeps_openscads_revolve(win):
    from khervecad import revolve_feature, toolbar_style
    win._interface_style = toolbar_style.CLASSIC
    m = win.model
    obj = m.add_node("component", {}, name="Classic")
    r = m.add_node("rect", dict(x=0, y=0, width=40, height=10),
                   parent=obj, name="Base")
    assert revolve_feature.revolve(win, [r]) is None
