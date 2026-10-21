"""Double-click glides to the fitted view and back, in 3D and 2D.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import view_anim

_APP = QApplication.instance() or QApplication([])


@pytest.fixture
def win():
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    yield w
    w._dirty = False
    w.close()


def test_3d_fit_and_back(win):
    win.model.add_node("cube", dict(width=50, depth=50, height=50))
    _APP.processEvents()
    view = win.view3d
    view.target, view.distance = [500.0, 0.0, 0.0], 3000.0
    view_anim.toggle_3d(view)
    fitted = (list(view.target), view.distance)
    assert view.distance < 3000.0
    view_anim.toggle_3d(view)
    assert view.target == pytest.approx([500.0, 0.0, 0.0])
    assert view.distance == pytest.approx(3000.0)
    view_anim.toggle_3d(view)                  # and fits again
    assert view.distance == pytest.approx(fitted[1])


def test_2d_fit_and_back(win):
    win.model.add_node("rect", dict(x=200, y=100, width=40, height=20))
    _APP.processEvents()
    v2 = win.view2d
    view_anim._set_2d(v2, 0.5, 0.0, 0.0)
    view_anim.toggle_2d(v2)
    c = v2.mapToScene(v2.viewport().rect().center())
    assert (c.x(), c.y()) == pytest.approx((220, 110), abs=5)
    view_anim.toggle_2d(v2)
    assert v2.px_per_mm() == pytest.approx(0.5)


def test_2d_double_click_zooms_in_on_the_spot_and_back(win):
    from PyQt5.QtCore import QPointF
    v2 = win.view2d
    view_anim._set_2d(v2, 2.0, 0.0, 0.0)
    view_anim.toggle_2d(v2, QPointF(30, 10))
    assert v2.px_per_mm() == pytest.approx(6.0)
    c = v2.mapToScene(v2.viewport().rect().center())
    assert (c.x(), c.y()) == pytest.approx((30, 10), abs=1)
    view_anim.toggle_2d(v2, QPointF(99, 99))     # back, wherever clicked
    assert v2.px_per_mm() == pytest.approx(2.0)


def test_standard_views_glide_and_land_exactly(win):
    win.model.add_node("cube", dict(width=30, depth=30, height=30))
    _APP.processEvents()
    view = win.view3d
    view.yaw, view.pitch = 170.0, 40.0
    for name in ("Front", "Top", "Right", "Isometric"):
        view.set_view(name)
        assert (view.yaw, view.pitch) == pytest.approx(view.VIEWS[name])


def test_a_view_click_during_the_sketch_turn_back_takes_over(win):
    """The user's Side view showed the part huge: the sketch's turn-back
    animation kept running under the click and won."""
    from PyQt5.QtGui import QGuiApplication
    from khervecad import normal_to
    import time
    win.model.add_node("cube", dict(width=10, depth=10, height=10))
    _APP.processEvents()
    view = win.view3d
    real = QGuiApplication.platformName
    QGuiApplication.platformName = staticmethod(lambda: "cocoa")
    try:
        view.projection = "Orthographic"
        view._kc_restore_projection = "Perspective"
        normal_to._animate(win, view, dict(yaw=0.0, pitch=89.0,
                                          target=[500.0, 0.0, 0.0],
                                          distance=0.5), lambda: None)
        view.set_view("Right")                 # click during the turn
        t = time.time()
        while time.time() - t < 1.0:
            _APP.processEvents()
            time.sleep(0.01)
    finally:
        QGuiApplication.platformName = real
    assert view.projection == "Perspective"
    assert (view.yaw, view.pitch) == pytest.approx(view.VIEWS["Right"])
    assert view.target[0] == pytest.approx(5.0, abs=1.0)  # on the cube
    assert view.distance > 5.0
