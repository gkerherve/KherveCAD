"""Tests for the 2D measure tool, feature snapping and dimensions.

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
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtCore import QPointF
from PyQt5.QtWidgets import QApplication

from khervecad import view2d


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    return MainWindow()


def test_feature_points_cover_corners_and_centres(window):
    m = window.model
    m.add_node("rect", dict(width=30.0, height=20.0, x=0.0, y=0.0))
    m.add_node("circle", dict(radius=8.0, x=50.0, y=10.0))
    app = QApplication.instance()
    app.processEvents()
    pts = {(round(p.x(), 3), round(p.y(), 3))
           for p in window.scene.feature_points()}
    assert (0.0, 0.0) in pts             # rect near corner
    assert (30.0, 20.0) in pts           # rect far corner
    assert (15.0, 10.0) in pts           # rect centre
    assert (50.0, 10.0) in pts           # circle centre


def test_snap_feature_grabs_nearby_corner_else_grid(window):
    m = window.model
    m.add_node("rect", dict(width=30.0, height=20.0, x=0.0, y=0.0))
    QApplication.instance().processEvents()
    sc = window.scene
    p, on = sc.snap_feature(QPointF(30.4, 19.6))
    assert on and (round(p.x(), 2), round(p.y(), 2)) == (30.0, 20.0)
    # far from any feature -> grid snap (0.5 grid), not a feature
    p, on = sc.snap_feature(QPointF(100.2, 100.2))
    assert not on
    assert (round(p.x(), 2), round(p.y(), 2)) == (100.0, 100.0)


def test_measure_tool_reports_distance_and_clears(window):
    sc = window.scene
    window.view2d.set_tool(view2d.MEASURE)
    assert sc.tool == view2d.MEASURE

    seen = []
    sc.measure_changed.connect(seen.append)
    sc._emit_measure(QPointF(0.0, 0.0), QPointF(30.0, 20.0))
    assert seen and "36.06 mm" in seen[-1]        # hypot(30, 20)

    # a full two-point measurement stays visible until cleared
    sc._measure_a = QPointF(0.0, 0.0)
    sc._measure_b = QPointF(30.0, 20.0)
    sc.clear_measure()
    assert sc._measure_a is None and sc._measure_b is None


def test_switching_tool_clears_measurement(window):
    sc = window.scene
    window.view2d.set_tool(view2d.MEASURE)
    sc._measure_a = QPointF(1.0, 2.0)
    sc._measure_b = QPointF(3.0, 4.0)
    window.view2d.set_tool(view2d.SELECT)
    assert sc._measure_a is None and sc._measure_b is None


def test_fmt_mm_trims_trailing_zeros():
    assert view2d._fmt_mm(30.0) == "30 mm"
    assert view2d._fmt_mm(30.5) == "30.5 mm"
    assert view2d._fmt_mm(36.056) == "36.06 mm"
    assert view2d._fmt_mm(0.0) == "0 mm"


def test_placed_dimension_saves_and_reloads(window, tmp_path):
    from khervecad import document
    from khervecad.mainwindow import MainWindow
    m = window.model
    m.add_dimension((0.0, 0.0), (30.0, 0.0), "Top (XY)")
    m.add_dimension((0.0, 0.0), (0.0, 20.0), "Front (XZ)")
    assert len(m.dimensions) == 2
    path = tmp_path / "dims.kcad"
    document.save_kcad(m, str(path))
    m2 = MainWindow().model
    document.load_kcad(m2, str(path))
    assert m2.dimensions == m.dimensions


def test_placed_dimension_is_undoable(window):
    m = window.model
    m.add_dimension((0.0, 0.0), (10.0, 0.0), "Top (XY)")
    QApplication.instance().processEvents()          # let capture fire
    assert len(m.dimensions) == 1
    m.undo_stack.undo()
    QApplication.instance().processEvents()
    assert m.dimensions == []
    m.undo_stack.redo()
    QApplication.instance().processEvents()
    assert len(m.dimensions) == 1


def test_dimension_tool_hit_test_and_remove(window):
    from PyQt5.QtCore import QPoint
    m = window.model
    m.add_dimension((0.0, 0.0), (30.0, 0.0), "Top (XY)")
    v = window.view2d
    vp = v.mapFromScene(QPointF(15.0, 0.0))          # midpoint of the line
    assert v._dimension_at(vp) == 0
    assert v._dimension_at(QPoint(vp.x() + 300, vp.y() + 300)) is None
    m.remove_dimension(0)
    assert m.dimensions == []


def test_dimensions_only_show_in_their_plane(window):
    m = window.model
    m.add_dimension((0.0, 0.0), (30.0, 0.0), "Front (XZ)")
    v = window.view2d
    window.scene.plane = "Top (XY)"                  # different plane
    vp = v.mapFromScene(QPointF(15.0, 0.0))
    assert v._dimension_at(vp) is None               # not hit-testable here


def test_auto_dims_render_for_every_shape(window):
    from PyQt5.QtGui import QPainter, QPixmap
    m = window.model
    rect = m.add_node("rect", dict(width=30.0, height=20.0))
    circ = m.add_node("circle", dict(radius=8.0, x=50.0, y=10.0))
    line = m.add_node("line", dict(x1=0.0, y1=40.0, x2=25.0, y2=55.0))
    app = QApplication.instance()
    app.processEvents()
    sc = window.scene
    assert sc.show_dims                    # on by default
    for node in (rect, circ, line):
        it = sc._items.get(node.id)
        if it:
            it.setSelected(True)
    app.processEvents()
    # rendering the overlay with every shape type selected must not raise
    pm = QPixmap(500, 400)
    pm.fill()
    painter = QPainter(pm)
    window.view2d.render(painter)
    painter.end()
