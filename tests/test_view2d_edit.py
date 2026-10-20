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
    # its contents are shown but locked: a Rotate can only rotate
    item = scene._items[rect.id]
    assert not item.isSelected() and not (
        item.flags() & item.ItemIsMovable)
    dial = next(g for g in scene._gizmos
                if isinstance(g, view2d_edit.RotateDial))
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


def test_a_rotate_turns_about_its_pivot_and_round_trips(setup):
    from khervecad import mesh, scadparse
    model, scene, view = setup
    rect, rot = _rotated_rect(model, 90.0)
    rot.params.update(px=10.0, py=0.0, pz=0.0)
    model.structure_changed.emit()
    scene.rebuild()
    # (0, 0) turned 90° about (10, 0) lands at (10, -10)
    corner = scene._items[rect.id].mapToScene(QPointF(0, 0))
    assert (round(corner.x(), 6), round(corner.y(), 6)) == (10, -10)
    m = mesh.node_matrix(rot)
    assert mesh.transform_point(m, (0, 0, 0)) == pytest.approx((10, -10, 0))
    code = model.to_scad()
    assert "kcad_rotate(a = [0, 0, 90], pivot = [10, 0, 0])" in code
    assert "module kcad_rotate" in code
    root, _warnings = scadparse.parse_scad(code)
    back = [n for n in root.walk() if n.type == "rotate"][0]
    assert (back.params["z"], back.params["px"]) == (90, 10)
    # a rotate with no pivot stays OpenSCAD's own, byte for byte
    rot.params.update(px=0.0)
    assert "kcad_rotate" not in model.to_scad()


def _shift_drag(view, start, end, steps=4):
    from PyQt5.QtCore import QEvent
    from PyQt5.QtGui import QMouseEvent
    vp = view.viewport()
    QTest.mousePress(vp, Qt.LeftButton, Qt.ShiftModifier, start)
    for i in range(1, steps + 1):
        p = QPoint(start.x() + (end.x() - start.x()) * i // steps,
                   start.y() + (end.y() - start.y()) * i // steps)
        QApplication.sendEvent(vp, QMouseEvent(
            QEvent.MouseMove, QPointF(p), Qt.NoButton, Qt.LeftButton,
            Qt.ShiftModifier))
    QTest.mouseRelease(vp, Qt.LeftButton, Qt.ShiftModifier, end)


def test_dragging_the_dial_centre_adds_a_move_above_the_rotate(setup):
    """The user's picture: moving the rotation point is a translate
    created ABOVE the rotate, moving part and pivot together."""
    model, scene, view = setup
    scene.snap_enabled = False
    rect, rot = _rotated_rect(model, 30.0)
    scene.set_highlight([rot])
    dial = next(g for g in scene._gizmos
                if isinstance(g, view2d_edit.RotateDial))
    centre = view.mapFromScene(dial.pos())             # (0, 0)
    _drag(view, centre, view.mapFromScene(QPointF(12, 8)))
    QApplication.processEvents()
    move = rot.parent
    assert move.type == "translate" and move.children == [rot]
    assert (round(move.params["x"]), round(move.params["y"])) == (12, 8)
    assert rot.params["z"] == 30.0 and not rot.params.get("px")
    # a second drag uses the same Move
    scene.set_highlight([rot])
    centre = view.mapFromScene(next(
        g for g in scene._gizmos
        if isinstance(g, view2d_edit.RotateDial)).pos())
    _drag(view, centre, view.mapFromScene(QPointF(20, 8)))
    QApplication.processEvents()
    assert rot.parent is move and round(move.params["x"]) == 20


def test_shift_dragging_the_dial_centre_moves_the_pivot(setup):
    model, scene, view = setup
    scene.snap_enabled = False
    rect, rot = _rotated_rect(model, 0.0)
    tr = model.wrap_nodes([rot], "translate")
    tr.params["x"] = 5.0
    model.structure_changed.emit()
    scene.set_highlight([rot])
    dial = next(g for g in scene._gizmos
                if isinstance(g, view2d_edit.RotateDial))
    centre = view.mapFromScene(dial.pos())             # the pivot: (5, 0)
    target = view.mapFromScene(QPointF(15, 10))
    _shift_drag(view, centre, target)
    # the pivot is in the rotate's own frame: the translate's 5 is off it
    assert rot.params["px"] == pytest.approx(10, abs=0.3)
    assert rot.params["py"] == pytest.approx(10, abs=0.3)


def test_no_rebuild_under_a_drag(setup):
    """A rebuild while a shape is held deleted the shapes Qt was still
    moving (a segfault in QGraphicsItem::setPos): it waits for the
    release now."""
    model, scene, view = setup
    rect = model.add_node("rect", dict(x=0.0, y=0.0, width=20.0,
                                       height=10.0))
    model.structure_changed.emit()
    scene.rebuild()
    item = scene._items[rect.id]
    item.setSelected(True)
    start = view.mapFromScene(QPointF(10, 5))
    QTest.mousePress(view.viewport(), Qt.LeftButton, Qt.NoModifier, start)
    assert scene.mouseGrabberItem() is item
    scene.rebuild()                                   # e.g. a re-select
    assert scene._items[rect.id] is item and scene._rebuild_pending
    QTest.mouseRelease(view.viewport(), Qt.LeftButton, Qt.NoModifier,
                       start)
    QApplication.processEvents()
    assert not scene._rebuild_pending
    assert scene._items[rect.id] is not item           # rebuilt after


def test_a_selected_move_drags_as_a_whole_and_its_shapes_are_locked(setup):
    """The user: "translate, we can only translate"."""
    model, scene, view = setup
    scene.snap_enabled = False
    rect, rot = _rotated_rect(model, 30.0)
    move = model.wrap_nodes([rot], "translate")
    model.structure_changed.emit()
    scene.set_highlight([move])
    area = next(g for g in scene._gizmos
                if isinstance(g, view2d_edit.ContainerArea))
    assert area.movable and area.node is move
    assert not scene._gizmos or not any(
        isinstance(g, view2d_edit.RotateDial) for g in scene._gizmos)
    inside = scene._items[rect.id].mapToScene(QPointF(10, 5))
    _drag(view, view.mapFromScene(inside),
          view.mapFromScene(inside + QPointF(8, -6)))
    assert (round(move.params["x"]), round(move.params["y"])) == (8, -6)
    assert (rect.params["x"], rect.params["y"]) == (0.0, 0.0)
    assert rot.params["z"] == 30.0


def test_a_selected_rotate_cannot_be_dragged(setup):
    model, scene, view = setup
    scene.snap_enabled = False
    rect, rot = _rotated_rect(model, 30.0)
    scene.set_highlight([rot])
    inside = scene._items[rect.id].mapToScene(QPointF(10, 5))
    _drag(view, view.mapFromScene(inside),
          view.mapFromScene(inside + QPointF(8, -6)))
    assert (rect.params["x"], rect.params["y"]) == (0.0, 0.0)
    assert rot.parent.type != "translate" and rot.params["z"] == 30.0


def test_only_parts_with_a_position_are_dragged_when_selected(setup):
    model, scene, view = setup
    cube = model.add_node("cube", dict(width=10.0, depth=10.0,
                                       height=10.0))
    rot = model.wrap_nodes([cube], "rotate")
    model.structure_changed.emit()
    scene.set_highlight([rot])
    item = scene._part_items[rot.id]
    assert not item.flags() & item.ItemIsMovable    # a rotate only turns
    scene.set_highlight([cube])
    cube_item = scene._part_items.get(cube.id) or scene._part_items[rot.id]
    move = model.wrap_nodes([rot], "translate")
    model.structure_changed.emit()
    scene.set_highlight([move])
    assert scene._part_items[move.id].flags() & item.ItemIsMovable


def test_a_polygon_of_expression_points_draws_with_its_handles(app):
    """Points written as expressions crashed the sketch's handles."""
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        model = win.model
        node = model.add_node("polygon")
        model.set_param(node, "points",
                        [[0, 0], ["2 * 10", 0], ["2 * 10", "5 + 5"]])
        app.processEvents()
        win.scene.select_nodes([node])
        app.processEvents()
        item = win.scene._items[node.id]
        spec = dict(item.handle_spec())
        assert spec["v1"].x() == 20 and spec["v2"].y() == 10
    finally:
        win._dirty = False
        win.close()
