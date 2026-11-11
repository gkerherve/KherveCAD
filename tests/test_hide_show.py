"""Hide/Show Items — SolidWorks' glasses on the 3D and 2D bars
(2026-11-11, the user).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import hide_show


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_both_bars_have_the_glasses_with_the_same_toggles(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        b3 = win.view3d.nav_bar.buttons["show"]
        b2 = win.view2d.nav_bar.buttons["show"]
        for b in (b3, b2):
            menu = b.menu()
            menu.aboutToShow.emit()
            keys = set(menu._items)
            assert {"smart_dims", "relations", "construction", "planes",
                    "axes", "grid"} <= keys
        # a toggle IS the window's action: ticking it in one bar ticks
        # the other and the View menu
        act = win._relations_act
        was = act.isChecked()
        b3.menu()._items["relations"].click()
        assert act.isChecked() != was
        b2.menu().aboutToShow.emit()
        assert b2.menu()._items["relations"].isChecked() == act.isChecked()
        act.setChecked(was)
    finally:
        win._dirty = False
        win.close()


def test_construction_geometry_hides_from_the_sketch(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    act = hide_show.construction_action(win)
    try:
        m = win.model
        line = m.add_node("line", dict(x1=0, y1=0, x2=20, y2=0, width=0.2,
                                       modifier="%"), name="Centerline")
        circle = m.add_node("circle", dict(x=5, y=5, radius=3))
        scene = win.view2d.scene()
        scene.rebuild()
        QApplication.processEvents()
        shown = {getattr(i, "node", None) for i in scene.items()}
        assert line in shown and circle in shown
        act.setChecked(False)
        QApplication.processEvents()
        shown = {getattr(i, "node", None) for i in scene.items()}
        assert line not in shown and circle in shown
    finally:
        act.setChecked(True)
        win._dirty = False
        win.close()


def test_the_2d_bar_shows_exit_sketch_not_planes_while_sketching(app):
    """SolidWorks / Fusion: the 3D view chose the plane, so the 2D bar
    has Exit Sketch where Front / Top / Right were (the user); the
    classic layout keeps its planes."""
    from khervecad import sketch_mode, toolbar_style
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        win.show()
        toolbar_style.apply(win, "SolidWorks", remember=False)
        sketch_mode.enter(win)
        QApplication.processEvents()
        planes = list(win._plane_buttons.values())
        assert planes and not any(b.isVisible() for b in planes)
        exit_btn = win._exit_sketch_btn
        assert exit_btn.isVisible()
        assert "exit" in exit_btn.text().lower()
        exit_btn.click()
        QApplication.processEvents()
        assert not sketch_mode.sketching(win)
        toolbar_style.apply(win, "KherveCAD", remember=False)
        QApplication.processEvents()
        assert all(b.isVisible() for b in planes)
        assert not exit_btn.isVisible()
    finally:
        win._dirty = False
        win.close()
