"""Trim Entities with SolidWorks' options (2026-11-11, the user).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import sketch_trim as tr
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
    v.resize(800, 600)
    v.show()
    v.resetTransform()
    v.scale(8, -8)
    v.centerOn(10, 5)
    yield v
    tr.set_mode(tr.CLOSEST)
    v.close()


def _line(m, a, b, name):
    return m.add_node("line", dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1],
                                   width=0.2), name=name)


def _ends(n):
    p = n.params
    return (round(p["x1"], 3), round(p["y1"], 3), round(p["x2"], 3),
            round(p["y2"], 3))


def _click(view, x, y):
    QTest.mouseClick(view.viewport(), Qt.LeftButton, Qt.NoModifier,
                     view.mapFromScene(QPointF(x, y)))
    QApplication.processEvents()


def test_corner_runs_two_lines_to_meet(app):
    m = DocumentModel()
    a = _line(m, (0, 0), (8, 0), "A")            # short of the corner
    b = _line(m, (12, -5), (12, 10), "B")         # past it
    tr.corner(m, a, (2, 0), b, (12, 8))
    assert _ends(a) == (0, 0, 12, 0)
    assert _ends(b) == (12, 0, 12, 10)            # the clicked side kept


def test_away_inside_and_outside(app):
    m = DocumentModel()
    l1 = _line(m, (0, 0), (30, 0), "L")
    b1 = _line(m, (10, -5), (10, 5), "B1")
    c = m.add_node("circle", dict(x=25, y=0, radius=2))   # crosses at 23, 27
    assert tr.away(m, l1, [b1, c], inside=True) == "split"
    pieces = sorted(_ends(n) for n in m.root.children
                    if n.type == "line" and n.name != "B1")
    assert pieces == [(0, 0, 10, 0), (27, 0, 30, 0)]
    l2 = _line(m, (0, 3), (30, 3), "L2")
    b2 = _line(m, (20, -5), (20, 5), "B2")
    tr.away(m, l2, [b1, b2], inside=False)
    assert _ends(l2) == (10, 3, 20, 3)


def test_options_by_mouse_in_the_window(view):
    from khervecad import sketch_modify
    m = view.scene().model
    a = _line(m, (0, 0), (20, 0), "A")
    b1 = _line(m, (5, -5), (5, 5), "B1")
    b2 = _line(m, (15, -5), (15, 5), "B2")
    QApplication.processEvents()
    view.set_tool(sketch_modify.TRIM)
    panel = tr.open_panel(view)
    panel.fields["mode"].setCurrentIndex(
        [k for k, _l in tr.MODES].index(tr.INSIDE))
    assert tr.mode() == tr.INSIDE
    assert "boundary" in panel.message.text()
    _click(view, 5, 3)                            # boundary 1
    _click(view, 15, 3)                           # boundary 2
    _click(view, 10, 0)                           # the line: middle goes
    pieces = sorted(_ends(n) for n in m.root.children
                    if n.type == "line" and n not in (b1, b2))
    assert pieces == [(0, 0, 5, 0), (15, 0, 20, 0)]


def test_power_trim_drags_across(view):
    from khervecad import sketch_modify
    m = view.scene().model
    _line(m, (0, 0), (20, 0), "A")
    _line(m, (0, 4), (20, 4), "C")
    b = _line(m, (10, -5), (10, 10), "B")
    QApplication.processEvents()
    tr.set_mode(tr.POWER)
    view.set_tool(sketch_modify.TRIM)
    vp = view.viewport()
    start = view.mapFromScene(QPointF(15, -2))
    end = view.mapFromScene(QPointF(15, 6))
    QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, start)
    from PyQt5.QtGui import QMouseEvent
    from PyQt5.QtCore import QEvent
    for k in range(1, 9):
        p = start + (end - start) * k / 8
        QApplication.sendEvent(vp, QMouseEvent(
            QEvent.MouseMove, p, Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
    QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, end)
    QApplication.processEvents()
    ends = sorted(_ends(n) for n in m.root.children
                  if n.type == "line" and n is not b)
    assert ends == [(0, 0, 10, 0), (0, 4, 10, 4)]  # both lost x > 10
