"""Editing the tree's selection in the 2D view: shapes drawn through
their rotate, a rotation dial, a linear extrude's height handle.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest
from PyQt5.QtCore import QPoint, QPointF, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import view2d_edit
from khervecad.model import DocumentModel
from khervecad.view2d import SketchScene, SketchView


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def setup(app):
    model = DocumentModel()
    scene = SketchScene(model)
    view = SketchView(scene)
    view.resize(700, 600)
    view.show()
    view.centerOn(10, 10)
    yield model, scene, view
    view.close()


def _drag(view, start, end, steps=4):
    """Press, move with the button HELD, release (QTest.mouseMove sends
    no button, so a grabbed handle never hears it offscreen)."""
    from PyQt5.QtCore import QEvent
    from PyQt5.QtGui import QMouseEvent
    vp = view.viewport()
    QTest.mousePress(vp, Qt.LeftButton, Qt.NoModifier, start)
    for i in range(1, steps + 1):
        p = QPoint(start.x() + (end.x() - start.x()) * i // steps,
                   start.y() + (end.y() - start.y()) * i // steps)
        QApplication.sendEvent(vp, QMouseEvent(
            QEvent.MouseMove, QPointF(p), Qt.NoButton, Qt.LeftButton,
            Qt.NoModifier))
    QTest.mouseRelease(vp, Qt.LeftButton, Qt.NoModifier, end)


def _rotated_rect(model, angle=30.0):
    rect = model.add_node("rect", dict(x=0.0, y=0.0, width=20.0,
                                       height=10.0))
    rot = model.wrap_nodes([rect], "rotate")
    rot.params["z"] = angle
    model.structure_changed.emit()
    return rect, rot


def test_a_rotated_rectangle_shows_rotated(setup):
    model, scene, view = setup
    rect, rot = _rotated_rect(model)
    scene.rebuild()
    item = scene._items[rect.id]
    corner = item.mapToScene(QPointF(20, 0))       # (20, 0) turned 30°
    assert corner.x() == pytest.approx(20 * math.cos(math.radians(30)),
                                       abs=1e-6)
    assert corner.y() == pytest.approx(20 * math.sin(math.radians(30)),
                                       abs=1e-6)


def test_dragging_a_corner_of_a_rotated_rectangle_edits_it(setup):
    model, scene, view = setup
    rect, rot = _rotated_rect(model, 90.0)
    scene.snap_enabled = False
    scene.rebuild()
    item = scene._items[rect.id]
    item.setSelected(True)
    # the far corner (20, 10) of the rect lies at (-10, 20) once turned
    handle = next(h for h in item.handles
                  if (h.scenePos() - QPointF(-10, 20)).manhattanLength()
                  < 1e-6)
    start = view.mapFromScene(handle.scenePos())
    end = view.mapFromScene(QPointF(-10, 30))      # 10 further along x
    _drag(view, start, end)
    assert rect.params["width"] == pytest.approx(30, abs=0.5)
    assert rect.params["height"] == pytest.approx(10, abs=0.5)
    assert rect.params["x"] == pytest.approx(0, abs=0.5)


def test_rectangle_corners_resize_the_right_edges(setup):
    """Qt's "top" corners are the smaller y — the bottom edge in this
    Y-up view; they were read the other way round."""
    model, scene, view = setup
    scene.snap_enabled = False
    rect = model.add_node("rect", dict(x=0.0, y=0.0, width=20.0,
                                       height=10.0))
    model.structure_changed.emit()
    scene.rebuild()
    item = scene._items[rect.id]
    item.setSelected(True)
    upper_right = next(h for h in item.handles
                       if (h.scenePos() - QPointF(20, 10))
                       .manhattanLength() < 1e-6)
    _drag(view, view.mapFromScene(upper_right.scenePos()),
          view.mapFromScene(QPointF(30, 20)))
    p = rect.params
    assert (round(p["x"]), round(p["y"]), round(p["width"]),
            round(p["height"])) == (0, 0, 30, 20)


def test_selecting_a_rotate_shows_a_dial_that_turns_it(setup):
    model, scene, view = setup
    rect, rot = _rotated_rect(model, 0.0)
    scene.set_highlight([rot])
    assert scene._items[rect.id].isSelected()      # its contents light up
    dial = scene._gizmos[0]
    assert isinstance(dial, view2d_edit.RotateDial)
    pivot = view.mapFromScene(QPointF(0, 0))
    # the dial is drawn at a fixed screen size: its knob (at 0°) sits
    # DIAL_PX pixels right of the pivot on screen
    knob = QPoint(pivot.x() + int(view2d_edit.DIAL_PX), pivot.y())
    up = QPoint(pivot.x(), pivot.y() - int(view2d_edit.DIAL_PX))  # 90°
    _drag(view, knob, up, steps=8)
    assert rot.params["z"] == pytest.approx(90, abs=0.01)
    QApplication.processEvents()
    corner = scene._items[rect.id].mapToScene(QPointF(20, 0))
    assert corner.x() == pytest.approx(0, abs=1e-6)
    assert corner.y() == pytest.approx(20, abs=1e-6)


def test_a_linear_extrude_gets_a_height_handle(setup):
    model, scene, view = setup
    rect = model.add_node("rect", dict(x=0.0, y=0.0, width=20.0,
                                       height=10.0))
    ext = model.wrap_nodes([rect], "linear_extrude")
    ext.params["height"] = 10.0
    model.structure_changed.emit()
    scene.set_highlight([ext])
    assert scene.plane in ("Front (XZ)", "Side (YZ)")    # height shows
    part = scene._part_items[ext.id]
    part.setSelected(True)
    handle = next(h for h in part.handles if h.role == "height")
    start = view.mapFromScene(handle.scenePos())
    end = view.mapFromScene(handle.scenePos() + QPointF(0, 15))
    _drag(view, start, end)
    assert ext.params["height"] == pytest.approx(25, abs=1.0)
