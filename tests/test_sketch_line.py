"""The SolidWorks-style line: chained, snapping, readout, relations.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QEvent, QPointF, Qt
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import sketch_constraints as sc, sketch_line
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


def _lines(view):
    return [n for n in view.scene().model.root.walk() if n.type == "line"]


def test_lines_chain_and_snap_horizontal_vertical(view):
    view.set_tool("line")
    _click(view, 0.2, 0.1)              # snaps to the origin
    _click(view, 30, 0.6)               # nearly level: snaps horizontal
    _click(view, 30.4, 20)              # nearly upright: snaps vertical
    QTest.keyClick(view.viewport(), Qt.Key_Escape)
    a, b = _lines(view)
    assert (a.params["x1"], a.params["y1"]) == (0, 0)
    assert a.params["y2"] == pytest.approx(0)
    assert b.params["x1"] == a.params["x2"] and \
        b.params["y1"] == a.params["y2"]          # the chain
    assert b.params["x2"] == pytest.approx(30)
    kinds = sorted(r["kind"] for r in sc.rows(view.scene().model.root))
    assert kinds == ["coincident", "horizontal", "vertical"]


def test_snap_to_a_point_and_line_up_with_one(view):
    scene = view.scene()
    m = scene.model
    m.add_node("line", dict(x1=10, y1=10, x2=40, y2=25))
    QApplication.processEvents()
    pt, info = sketch_line.snap(scene, QPointF(40.2, 24.9))
    assert (pt.x(), pt.y()) == (40, 25) and info["point"] is not None
    # far from any point but level with (40, 25): y lines up
    pt, info = sketch_line.snap(scene, QPointF(70, 25.1))
    assert pt.y() == pytest.approx(25) and info["guides"]
    assert sketch_line.readout_text(QPointF(0, 0), QPointF(3, 4)) \
        .startswith("L 5.00")


def test_polygon_snaps_and_gets_relations(view):
    view.set_tool("polygon")
    for x, y in [(0, 0), (30, 0.5), (30.4, 20), (0.3, 20)]:
        _click(view, x, y)
    QTest.keyClick(view.viewport(), Qt.Key_Return)
    QApplication.processEvents()
    poly = next(n for n in view.scene().model.root.walk()
                if n.type == "polygon")
    pts = poly.params["points"]
    assert pts[1][1] == pytest.approx(0) and pts[2][0] == pytest.approx(30)
    kinds = sorted(r["kind"] for r in sc.rows(view.scene().model.root))
    assert kinds.count("horizontal") >= 2 and kinds.count("vertical") >= 1


def test_a_horizontal_line_still_follows_the_grid(monkeypatch):
    from types import SimpleNamespace
    from PyQt5.QtCore import QPointF
    from khervecad import sketch_line as sl
    scene = SimpleNamespace(snap_enabled=True, grid_size=0.1)
    monkeypatch.setattr(sl, "sketch_points", lambda s, skip=None: [
        (QPointF(0, 0), None, "origin")])
    monkeypatch.setattr(sl, "_px", lambda s, p: 1e-6)
    pt, info = sl.snap(scene, QPointF(3.4567, 0.01), QPointF(0, 0))
    assert info["angle"] == "h"
    assert abs(pt.x() - 3.5) < 1e-9 and pt.y() == 0


def test_snaps_square_to_the_last_side_and_under_a_drawn_point(monkeypatch):
    from types import SimpleNamespace
    from PyQt5.QtCore import QPointF
    from khervecad import sketch_line as sl
    monkeypatch.setattr(sl, "sketch_points", lambda s, skip=None: [])
    monkeypatch.setattr(sl, "_px", lambda s, p: 0.5)
    pts = [QPointF(0, 0), QPointF(10, 5)]   # a side at ~27°
    scene = SimpleNamespace(snap_enabled=False, grid_size=1.0,
                            _poly_points=pts)
    # square to that side, slightly off
    pt, info = sl.snap(scene, QPointF(7.2, 10.0), pts[-1])
    assert info["angle"] == "perp"
    assert abs((pt.x() - 10) * 10 + (pt.y() - 5) * 5) < 1e-6
    # lined up under the first point
    pts.append(QPointF(20, 20))
    pt, info = sl.snap(scene, QPointF(0.3, 5.0), pts[-1])
    assert abs(pt.x()) < 1e-9


def test_polygon_relations_come_from_its_real_sides():
    from khervecad import sketch_constraints as sc
    from khervecad import sketch_line as sl
    from khervecad.model import DocumentModel
    m = DocumentModel()
    # level, 45°, upright, then square to... back home
    poly = m.add_node("polygon", dict(points=[[0, 0], [10, 0], [20, 10],
                                              [20, 20], [0, 20]]))
    sl.polygon_relations(m, poly, ["h", "h", "v", "h", "v"])  # stale flags
    kinds = {(r["kind"], r["refs"][-1].split(".")[1])
             for r in sc.rows(m.root)}
    assert ("diagonal", "e1") in kinds
    assert ("horizontal", "e1") not in kinds
    assert ("horizontal", "e0") in kinds and ("vertical", "e2") in kinds
    sc.refresh(m, set())
    p = poly.params["points"]
    assert abs(abs(p[2][0] - p[1][0]) - abs(p[2][1] - p[1][1])) < 1e-6
