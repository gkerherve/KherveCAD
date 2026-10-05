"""3D curves (curve3d.py) and drawing them with snaps (curve_draw.py).

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
from PyQt5.QtCore import QEvent, QPoint, Qt
from PyQt5.QtGui import QKeyEvent, QMouseEvent
from PyQt5.QtWidgets import QApplication

from khervecad import cadexchange as cx, curve3d, curve_draw, mesh, \
    scadparse
from khervecad.curve_draw import Snapper, parse_coords
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


# ------------------------------------------------------------ the node

def test_a_curve_passes_through_its_points():
    pts = [(0, 0, 0), (10, 5, 3), (20, 0, 8)]
    dense = curve3d.polyline(pts, "smooth", False, 6)
    for p in pts:
        assert any(math.dist(p, q) < 1e-9 for q in dense)
    closed = curve3d.polyline(pts, "smooth", True, 6)
    assert closed[0] == closed[-1]
    assert curve3d.polyline(pts, "straight") == pts


def test_curve_round_trips_through_openscad_code(app):
    model = DocumentModel()
    node = model.add_node("curve")
    node.params.update(closed=True, thickness=3.0, style="straight")
    code = model.to_scad()
    assert "module kcad_curve" in code and "kcad_curve(points" in code
    root, warnings = scadparse.parse_scad(code)
    got = [n for n in root.walk() if n.type == "curve"]
    assert len(got) == 1 and not warnings
    p = got[0].params
    assert p["points"] == node.params["points"]
    assert p["closed"] is True and p["style"] == "straight"
    assert p["thickness"] == 3.0 and p["smooth"] == 8


def test_curve_previews_as_a_wire(app):
    model = DocumentModel()
    model.add_node("curve")
    tris = mesh.tessellate(model.root)
    xs = [v[0] for t in tris for v in t]
    assert min(xs) == pytest.approx(-1.0, abs=0.05)     # ball at the start
    assert max(xs) == pytest.approx(61.0, abs=0.05)     # and at the end


def test_validation_names_the_problem(app):
    model = DocumentModel()
    node = model.add_node("curve", dict(points=[[0, 0, 0]]))
    errors = validate(model.root)
    assert "at least two points" in errors[node.id]


@pytest.mark.skipif(not cx.occ_available(), reason="no OpenCascade")
@pytest.mark.parametrize("style,closed", [("smooth", False),
                                         ("smooth", True),
                                         ("straight", False)])
def test_curve_exports_exact(tmp_path, style, closed):
    model = DocumentModel()
    model.add_node("curve", dict(style=style, closed=closed))
    out = tmp_path / "c.step"
    report = cx.export_model(model.root, out)
    assert report.exact == 1 and report.faceted == 0
    text = out.read_text(errors="replace")
    if style == "smooth":
        assert "B_SPLINE_SURFACE" in text
    else:
        assert "CYLINDRICAL_SURFACE" in text


def test_sweep_from_curve_keeps_the_points(app):
    model = DocumentModel()
    node = model.add_node("curve", dict(thickness=4.0))
    sweep = curve3d.sweep_from_curve(model, node)
    assert sweep.type == "sweep" and sweep.params["path"] == \
        node.params["points"]
    assert sweep.children[0].type == "circle"
    assert node not in list(model.root.walk())
    assert mesh.tessellate(model.root)


# ------------------------------------------------------------- snaps

def _cube_tris():
    from khervecad.mesh import cube_mesh
    return cube_mesh(dict(width=10, depth=10, height=10, center=False,
                          x=0, y=0, z=0))


def _down(x, y):
    """A ray straight down onto (x, y)."""
    return (x, y, 100.0), (0.0, 0.0, -1.0)


def test_a_box_has_twelve_edges_and_eight_corners():
    s = Snapper(_cube_tris())
    assert len(s.edges) == 12 and len(s.corners) == 8


def test_a_cylinders_facets_are_not_edges():
    from khervecad.mesh import cylinder_mesh
    s = Snapper(cylinder_mesh(dict(segments=48, height=10, radius_bottom=5,
                                   radius_top=5, x=0, y=0, z=0,
                                   center=False)))
    # only the two rims: 48 + 48 edges, no seams down the side
    assert len(s.edges) == 96


@pytest.mark.parametrize("aim,kind,expect", [
    ((9.8, 9.7), "corner", (10, 10, 10)),
    ((5.2, 9.8), "mid", (5, 10, 10)),
    ((2.0, 9.8), "edge", (2.0, 10, 10)),
    ((3.0, 4.0), "surface", (3.0, 4.0, 10)),
    ((30.2, 40.4), "grid", (30.0, 40.5, 0.0)),
])
def test_snaps_say_what_they_caught(aim, kind, expect):
    s = Snapper(_cube_tris())
    o, d = _down(*aim)
    p, got = s.snap(o, d, lambda _p: 0.5, grid=0.5)
    assert got == kind
    assert p == pytest.approx(expect, abs=1e-6)


def test_clicking_the_first_point_closes_the_loop():
    s = Snapper([])
    pts = [(0, 0, 0), (10, 0, 0), (10, 10, 0)]
    o, d = _down(0.2, 0.1)
    p, kind = s.snap(o, d, lambda _p: 0.5, points=pts)
    assert kind == "start" and p == pts[0]


def test_shift_lifts_straight_up():
    s = Snapper([])
    # looking along +y at the vertical line through (5, 0, 0)
    p, kind = s.snap((5, -50, 12), (0, 1, 0), lambda _p: 0.5,
                     vertical_from=(5, 0, 0))
    assert kind == "vertical" and p == pytest.approx((5, 0, 12))


def test_typed_points():
    assert parse_coords("10, 20, 5") == (10, 20, 5)
    assert parse_coords("10 20", elevation=3) == (10, 20, 3)
    assert parse_coords("@0, 0, 15", last=(1, 2, 3)) == (1, 2, 18)
    assert parse_coords("-1.5;2e1;0") == (-1.5, 20, 0)
    with pytest.raises(ValueError, match="two or three numbers"):
        parse_coords("ten, 20")
    with pytest.raises(ValueError, match="no last point"):
        parse_coords("@1, 1, 1")


# ---------------------------------------------------------- the tool

def _click(view, x, y, button=Qt.LeftButton, mods=Qt.NoModifier):
    pos = QPoint(int(x), int(y))
    for kind, handler in ((QEvent.MouseButtonPress, view.mousePressEvent),
                          (QEvent.MouseButtonRelease,
                           view.mouseReleaseEvent)):
        handler(QMouseEvent(kind, pos, button, button, mods))


def _key(view, key, text=""):
    view.keyPressEvent(QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier, text))


def test_drawing_a_curve_with_the_mouse_and_keyboard(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(1100, 800)
    win.show()
    app.processEvents()
    view = win.view3d
    tool = curve_draw.start(win)
    assert view.edit_tool is tool
    # a click in empty space lands on the ground grid
    _click(view, view.width() / 2, view.height() * 0.8)
    assert len(tool.points) == 1 and tool.points[0][2] == 0.0
    # typed: absolute, then relative
    # typing a digit anywhere starts a coordinate in the box
    _key(view, Qt.Key_1, "1")
    assert tool._box.text() == "1"
    tool._box.setText("10, 0, 0")
    tool._typed()
    assert tool.points[-1] == (10.0, 0.0, 0.0)
    tool._box.setText("@0, 0, 15")
    tool._typed()
    assert tool.points[-1] == (10.0, 0.0, 15.0)
    # Backspace takes one back, Enter finishes
    tool.add_point((20.0, 5.0, 5.0))
    _key(view, Qt.Key_Backspace)
    assert len(tool.points) == 3
    _key(view, Qt.Key_Return)
    assert view.edit_tool is None
    curves = [n for n in win.model.root.walk() if n.type == "curve"]
    assert len(curves) == 1
    assert curves[0].params["points"][-1] == [10.0, 0.0, 15.0]
    # it arrived as one Object in Main, like any new shape
    assert curves[0].parent.type == "component"
    win._dirty = False
    win.deleteLater()


def test_esc_cancels_and_leaves_nothing(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    tool = curve_draw.start(win)
    tool.add_point((0, 0, 0))
    tool.add_point((5, 0, 0))
    _key(win.view3d, Qt.Key_Escape)
    assert win.view3d.edit_tool is None
    assert not [n for n in win.model.root.walk() if n.type == "curve"]
    win._dirty = False
    win.deleteLater()
