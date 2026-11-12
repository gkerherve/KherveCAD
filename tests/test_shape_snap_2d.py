# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""A whole sketch shape dragged in the 2D view snaps by its own corners,
centre and side middles onto the origin and other shapes' points
(2026-11-12, the user)."""

import pytest
from PyQt5.QtCore import QPointF
from PyQt5.QtWidgets import QApplication


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app):
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    QApplication.processEvents()
    return w


def _item(scene, node):
    return next(i for i in scene.items() if getattr(i, "node", None) is node)


def test_a_rectangle_centre_and_side_middle_snap_to_the_origin(win):
    m = win.model
    rect = m.add_node("rect", dict(x=10.3, y=7.1, width=20, height=10))
    QApplication.processEvents()
    scene = win.view2d.scene()
    item = _item(scene, rect)
    # centre (20.3, 12.1) dragged to near the origin: lands exactly on it
    got = scene.snap_shape(item, item.pos() + QPointF(-20.0, -12.0))
    centre = item.mapToScene(item.rect().center()) + (got - item.pos())
    assert abs(centre.x()) < 1e-6 and abs(centre.y()) < 1e-6
    # the middle of its left side (10.3, 12.1) to the origin
    got = scene.snap_shape(item, item.pos() + QPointF(-10.0, -12.0))
    mid = item.mapToScene(QPointF(item.rect().left(),
                                  item.rect().center().y())) + \
        (got - item.pos())
    assert abs(mid.x()) < 1e-6 and abs(mid.y()) < 1e-6
    # far from anything: no feature snap (the grid takes it)
    assert scene.snap_shape(item, item.pos() + QPointF(40.0, 40.0)) is None


def test_a_circle_centre_snaps_onto_a_line_end(win):
    m = win.model
    m.add_node("line", dict(x1=30, y1=30, x2=60, y2=30))
    circ = m.add_node("circle", dict(x=0, y=40, radius=5))
    QApplication.processEvents()
    scene = win.view2d.scene()
    item = _item(scene, circ)
    got = scene.snap_shape(item, item.pos() + QPointF(29.8, -10.2))
    c = item.mapToScene(item.rect().center()) + (got - item.pos())
    assert abs(c.x() - 30) < 1e-6 and abs(c.y() - 30) < 1e-6


def test_dragging_a_rectangle_by_mouse_snaps_its_centre_and_is_light(win):
    # the user: moving a rectangle was slow, and its centre could not be
    # seen to snap. Dragged by mouse onto the origin, with far fewer model
    # updates than mouse moves
    import time
    from PyQt5.QtCore import QEvent, QPoint, Qt
    from PyQt5.QtGui import QMouseEvent
    from PyQt5.QtTest import QTest
    m = win.model
    rect = m.add_node("rect", dict(x=20.3, y=15.1, width=20, height=10))
    QApplication.processEvents()
    view = win.view2d
    scene = view.scene()
    item = _item(scene, rect)
    emits = []
    m.node_changed.connect(lambda n: emits.append(n))
    start = view.mapFromScene(item.mapToScene(item.rect().center()))
    end = view.mapFromScene(QPointF(0.4, -0.3))
    vp = view.viewport()
    QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, start)
    steps = 30
    for i in range(1, steps + 1):
        p = QPoint(start.x() + (end.x() - start.x()) * i // steps,
                   start.y() + (end.y() - start.y()) * i // steps)
        QApplication.sendEvent(vp, QMouseEvent(
            QEvent.MouseMove, QPointF(p), Qt.NoButton, Qt.LeftButton,
            Qt.NoModifier))
    assert scene._shape_drag is item           # its points are drawn
    QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, end)
    QApplication.processEvents()
    p = rect.params
    assert abs(p["x"] + p["width"] / 2) < 1e-6
    assert abs(p["y"] + p["height"] / 2) < 1e-6
    assert len([n for n in emits if n is rect]) < steps / 3
