"""The further sketch CREATE tools, driven with real clicks.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest
from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import mesh, scadparse, sketch_constraints as sc
from khervecad import sketch_tools2 as s2
from khervecad.model import DocumentModel
from khervecad.view2d import SketchScene, SketchView


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def view(app):
    scene = SketchScene(DocumentModel())
    scene.snap_enabled = False
    v = SketchView(scene)
    v.resize(700, 600)
    v.show()
    v.centerOn(20, 20)
    yield v
    v.close()


def _click(view, x, y):
    QTest.mouseClick(view.viewport(), Qt.LeftButton, Qt.NoModifier,
                     view.mapFromScene(QPointF(x, y)))


def _draw(view, tool, pts):
    view.set_tool(tool)
    for x, y in pts:
        _click(view, x, y)


def _shapes(view):
    return [n for n in view.scene().model.root.walk()
            if n is not view.scene().model.root]


def test_construction_line_is_left_out_of_the_solid(view):
    _draw(view, s2.CONST_LINE, [(0, 0), (30, 10)])
    (line,) = _shapes(view)
    assert line.type == "line" and line.params["modifier"] == "%"
    assert "%" in view.scene().model.to_scad()
    m = view.scene().model
    e = m.add_node("linear_extrude", dict(height=3))
    line.parent.remove(line)
    e.add(line)
    assert mesh.tessellate(e) == []               # not in the extrusion


def test_point_rect3_circles_and_polygon(view):
    m = view.scene().model
    _draw(view, s2.POINT, [(5, 5)])
    _draw(view, s2.RECT_3PT, [(0, 0), (20, 0), (20, 8)])
    _draw(view, s2.CIRCLE_2PT, [(30, 0), (40, 0)])
    _draw(view, s2.CIRCLE_3PT, [(50, 0), (60, 10), (70, 0)])
    view.scene().ask_value = lambda tool, default: "5"
    _draw(view, s2.POLY_REG, [(10, 30), (16, 30)])
    kinds = [n.type for n in _shapes(view)]
    assert kinds == ["circle", "polygon", "circle", "circle", "polygon"]
    pt, rect, c2, c3, pent = _shapes(view)
    assert pt.params["modifier"] == "%"
    assert len(rect.params["points"]) == 4
    assert c2.params["radius"] == pytest.approx(5)
    assert c3.params["radius"] == pytest.approx(10)
    assert len(pent.params["points"]) == 5


def test_polyline_joins_its_lines(view):
    m = view.scene().model
    view.set_tool(s2.POLYLINE)
    for x, y in [(0, 0), (20, 0), (20, 15)]:
        _click(view, x, y)
    QTest.keyClick(view.viewport(), Qt.Key_Return)
    QApplication.processEvents()
    (group,) = _shapes(view)[:1]
    assert group.name == "Polyline"
    lines = [c for c in group.children if c.type == "line"]
    assert len(lines) == 2
    assert [r["kind"] for r in sc.rows(group)] == ["coincident"]


def test_spline_conic_tangent_arc_and_circle(view):
    m = view.scene().model
    view.set_tool(s2.BSPLINE)
    for x, y in [(0, 0), (20, 20), (40, 0), (20, -10)]:
        _click(view, x, y)
    QTest.keyClick(view.viewport(), Qt.Key_Return)
    _draw(view, s2.CONIC, [(0, 40), (40, 40), (20, 60)])
    tri = [m.add_node("line", dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1]))
           for a, b in (((60, 0), (100, 0)), ((100, 0), (80, 35)),
                        ((80, 35), (60, 0)))]
    QApplication.processEvents()
    _draw(view, s2.CIRCLE_TAN, [(80, 0), (90, 17.5), (70, 17.5)])
    circle = _shapes(view)[-1]
    assert circle.type == "circle"
    # the incircle of that triangle touches the base: centre y = radius
    assert circle.params["y"] == pytest.approx(circle.params["radius"],
                                               abs=1e-3)
    _draw(view, s2.ARC_TAN, [(99, 0), (110, 10)])
    arc = _shapes(view)[-1]
    assert arc.type == "polygon"
    root, warnings = scadparse.parse_scad(m.to_scad())
    assert not warnings


def test_construction_toggle(app):
    m = DocumentModel()
    r = m.add_node("rect", {})
    assert s2.toggle_construction(m, [r]) == 1
    assert r.params["modifier"] == "%"
    s2.toggle_construction(m, [r])
    assert not r.params.get("modifier")
