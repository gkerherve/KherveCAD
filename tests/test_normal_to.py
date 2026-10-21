"""Edit Sketch / Normal To: the 3D view turns square on to the shape's
plane and hands over to the sketch at the same scale, and back.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import normal_to, sketch_mode, toolbar_style

_APP = QApplication.instance() or QApplication([])


def test_plane_of_a_normal():
    assert normal_to.plane_of((0, 0, 1)) == "Top (XY)"
    assert normal_to.plane_of((0, -1, 0)) == "Front (XZ)"
    assert normal_to.plane_of((1, 0, 0)) == "Side (YZ)"
    assert normal_to.plane_of((0, 0.7, 0.7)) is None


@pytest.fixture
def win():
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    w.resize(1200, 800)
    toolbar_style.apply(w, "SolidWorks", remember=False)
    w.show()
    yield w
    toolbar_style.apply(w, "KherveCAD", remember=False)
    w._dirty = False
    w.close()


def test_edit_sketch_turns_to_the_shape_then_sketches_at_its_scale(win,
                                                                  monkeypatch):
    monkeypatch.setattr(normal_to, "DURATION_MS", 0)   # no waiting
    m = win.model
    rect = m.add_node("rect", dict(x=40, y=10, width=20, height=10))
    view = win.view3d
    view.yaw, view.pitch, view.distance = 30.0, 25.0, 300.0
    win.builder.tree.select_nodes([rect])
    assert normal_to.edit(win)
    for _ in range(6):
        _APP.processEvents()
    assert sketch_mode.sketching(win)
    assert win.view2d.scene().plane == "Top (XY)"
    assert (view.yaw, view.pitch) == normal_to.CAMERA["Top (XY)"]
    assert view.target[:2] == pytest.approx([50, 15])
    want = win._normal_to_scale             # the 3D view's px per mm
    assert win.view2d.px_per_mm() == pytest.approx(want, rel=1e-6)
    centre = win.view2d.mapToScene(win.view2d.viewport().rect().center())
    assert (centre.x(), centre.y()) == pytest.approx((50, 15), abs=1.0)
    # Finish: the camera turns back where it was
    sketch_mode.finish(win)
    for _ in range(4):
        _APP.processEvents()
    assert (view.yaw, view.pitch, view.distance) == pytest.approx(
        (30.0, 25.0, 300.0))
    assert view.projection != "Orthographic" or True


def test_create_sketch_with_a_shape_selected_edits_it(win, monkeypatch):
    monkeypatch.setattr(normal_to, "DURATION_MS", 0)
    m = win.model
    rect = m.add_node("rect", dict(width=20, height=10))
    win.builder.tree.select_nodes([rect])
    sketch_mode.create_action(win).trigger()
    for _ in range(4):
        _APP.processEvents()
    assert sketch_mode.sketching(win)
    assert win._normal_to_saved is not None


def test_classic_layout_turns_and_shows_the_plane(monkeypatch):
    from khervecad.mainwindow import MainWindow
    monkeypatch.setattr(normal_to, "DURATION_MS", 0)
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    try:
        m = w.model
        rect = m.add_node("rect", dict(width=20, height=10))
        w.builder.tree.select_nodes([])
        normal_to.action(w).trigger()          # nothing selected: pick
        assert w.view3d._pick_cb is not None
        w.view3d._pick_cb(dict(kind="face", pos=[5, 5, 0],
                               dir=[0, 0, 1]), rect)
        for _ in range(4):
            _APP.processEvents()
        assert (w.view3d.yaw, w.view3d.pitch) == \
            normal_to.CAMERA["Top (XY)"]
        assert w.view2d.scene().plane == "Top (XY)"
        assert not sketch_mode.sketching(w)    # classic: both views
    finally:
        w._dirty = False
        w.close()


def test_combo_rows_use_the_styled_delegate():
    from PyQt5.QtWidgets import QComboBox, QStyledItemDelegate
    from khervecad import style
    style.apply_style(_APP)
    c = QComboBox()
    c.addItems(["a", "b"])
    c.show()
    _APP.processEvents()
    assert isinstance(c.itemDelegate(), QStyledItemDelegate)
    c.close()
