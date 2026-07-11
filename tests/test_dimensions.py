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
