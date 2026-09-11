"""The floating zoom / pan / focus bars and Vibe Model.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import viewnav


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _box(x0, y0, z0, s):
    """Two triangles per face of an axis-aligned cube."""
    x1, y1, z1 = x0 + s, y0 + s, z0 + s
    quads = [((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)),
             ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)),
             ((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)),
             ((x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)),
             ((x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)),
             ((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1))]
    return [t for a, b, c, d in quads for t in ((a, b, c), (a, c, d))]


def test_3d_bar_zooms_pans_turns_and_focuses(app):
    from khervecad.view3d import View3D
    view = View3D()
    view.resize(640, 420)
    far = _box(200, 0, 0, 10)
    view.set_mesh(_box(0, 0, 0, 10) + far, "test")
    view.fit()
    bar = viewnav.attach_3d(view)
    dist = view.distance
    bar.buttons["zoom_in"].click()
    assert view.distance < dist and view.user_moved
    target = list(view.target)
    bar.buttons["right"].click()
    assert view.target != target
    yaw = view.yaw
    bar.buttons["orbit_left"].click()
    assert view.yaw != yaw
    view.set_highlight_mesh(far)                # the far part selected
    bar.buttons["focus"].click()
    assert abs(view.target[0] - 205) < 1.0
    close_up = view.distance
    view.set_highlight_mesh([])
    bar.buttons["focus"].click()                # nothing: the whole model
    assert view.distance > 5 * close_up         # both boxes in frame
    assert 0 < view.target[0] < 200


def test_3d_bar_toggles_the_platform_stage(app):
    from PyQt5.QtCore import QSettings
    from khervecad.view3d import View3D
    settings = QSettings("Kherve", "KherveCAD")
    saved = settings.value("render_stage")
    try:
        view = View3D()
        view.set_stage(False)
        bar = viewnav.attach_3d(view)
        button = bar.buttons["stage"]
        assert not button.isChecked()
        button.click()
        assert view.stage and button.isChecked()
        view.set_stage(False)                   # the menu, say
        assert not button.isChecked()
    finally:
        if saved is None:
            settings.remove("render_stage")
        else:
            settings.setValue("render_stage", saved)


def test_3d_bar_sits_top_right_and_hides_for_a_pick(app):
    from khervecad.view3d import View3D
    view = View3D()
    view.resize(640, 420)
    bar = viewnav.attach_3d(view)
    view.show()                 # Qt holds resize events until shown
    view.resize(800, 500)
    app.processEvents()
    geo = bar.geometry()
    assert geo.right() <= 800 and geo.right() > 800 - 30 and geo.top() < 30
    view.start_pick(lambda _d: None, banner="pick")
    assert bar.isHidden()
    view.cancel_pick()
    assert not bar.isHidden()
    view.close()


def test_2d_bar_zooms_and_focuses_an_offset_part(app):
    from khervecad.model import DocumentModel
    from khervecad.view2d import SketchScene, SketchView
    model = DocumentModel()
    scene = SketchScene(model)
    view = SketchView(scene)
    view.resize(600, 400)
    view.show()
    bar = viewnav.attach_2d(view)
    ppm = view.px_per_mm()
    bar.buttons["zoom_in"].click()
    assert view.px_per_mm() > ppm
    node = model.add_node("rect")
    for key, value in (("x", 500.0), ("y", 300.0), ("width", 40.0),
                       ("height", 20.0)):
        model.set_param(node, key, value)
    app.processEvents()
    bar.buttons["focus"].click()               # nothing selected: all
    centre = view.mapToScene(view.viewport().rect().center())
    assert abs(centre.x() - 520) < 5 and abs(centre.y() - 310) < 5
    h = view.horizontalScrollBar()
    before = h.value()
    bar.buttons["zoom_in"].click()
    bar.buttons["right"].click()
    assert h.value() != before
    view.close()


def test_vibe_model_folds_the_panels_away_and_back(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        assert not win._left_column.isHidden()
        win._vibe_act.trigger()
        assert win._vibe_act.isChecked()
        assert win._left_column.isHidden() and win.view2d.isHidden()
        assert win._tools_bar.isHidden() and not win.view3d.isHidden()
        win._vibe_act.trigger()
        assert not win._left_column.isHidden()
        assert not win.view2d.isHidden() and not win._tools_bar.isHidden()
        win.set_vibe_model(True)                # programmatic: tick follows
        assert win._vibe_act.isChecked()
        win.set_vibe_model(False)
    finally:
        win._dirty = False
        win.close()
