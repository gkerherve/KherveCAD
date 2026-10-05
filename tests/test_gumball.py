"""The Gumball (gumball.py): drag an arrow to slide, a ring to turn.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtCore import QEvent, QPoint, Qt
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import QApplication

from khervecad import gumball


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def test_handle_hit_prefers_arrows():
    centre = (100, 100)
    tips = [(200, 100), (100, 0), (60, 140)]
    rings = [[(100 + 70, 100), (100, 100 + 70)], [], []]
    assert gumball.handle_at(150, 102, centre, tips, rings) == ("move", 0)
    assert gumball.handle_at(100, 50, centre, tips, rings) == ("move", 1)
    assert gumball.handle_at(136, 134, centre, tips, rings) == ("turn", 0)
    assert gumball.handle_at(300, 300, centre, tips, rings) is None


def _mouse(view, kind, x, y, mods=Qt.NoModifier):
    ev = QMouseEvent(kind, QPoint(int(x), int(y)), Qt.LeftButton,
                     Qt.LeftButton, mods)
    {QEvent.MouseButtonPress: view.mousePressEvent,
     QEvent.MouseMove: view.mouseMoveEvent,
     QEvent.MouseButtonRelease: view.mouseReleaseEvent}[kind](ev)


@pytest.fixture
def scene(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    win.resize(1100, 800)
    win.show()
    cube = win.model.add_node("cube", dict(width=20, depth=20, height=20,
                                           center=True))
    comp = win.model.enclose_as_part(cube)
    win.builder.tree.select_nodes([comp])
    for _ in range(5):
        app.processEvents()
    win.view3d.fit()
    app.processEvents()
    assert gumball.toggle(win, True)
    yield win, comp
    win._dirty = False
    win.deleteLater()


def _drag(app, win, handle, dx, dy, mods=Qt.NoModifier):
    view = win.view3d
    tool = view.edit_tool
    _c, _l, cs, tips, rings = tool._screen()
    kind, axis = handle
    if kind == "move":
        x = cs[0] + (tips[axis][0] - cs[0]) * 0.6
        y = cs[1] + (tips[axis][1] - cs[1]) * 0.6
    else:
        p = rings[axis][len(rings[axis]) // 8]
        x, y = p[0], p[1]
    _mouse(view, QEvent.MouseButtonPress, x, y)
    assert tool.drag and tool.drag["handle"] == handle
    _mouse(view, QEvent.MouseMove, x + dx, y + dy, mods)
    _mouse(view, QEvent.MouseButtonRelease, x + dx, y + dy)
    app.processEvents()


def test_dragging_the_x_arrow_slides_along_x(app, scene):
    win, comp = scene
    tool = win.view3d.edit_tool
    _c, _l, cs, tips, _r = tool._screen()
    dx, dy = tips[0][0] - cs[0], tips[0][1] - cs[1]
    _drag(app, win, ("move", 0), dx * 0.5, dy * 0.5, Qt.ControlModifier)
    assert comp.params["x"] > 0
    assert comp.params["y"] == pytest.approx(0, abs=1e-6)
    assert comp.params["z"] == pytest.approx(0, abs=1e-6)
    # Ctrl snapped it to the grid
    step = win.scene.grid_size
    assert comp.params["x"] / step == pytest.approx(
        round(comp.params["x"] / step))


def test_dragging_a_ring_turns_about_its_centre(app, scene):
    win, comp = scene
    _drag(app, win, ("turn", 2), 40, 40)
    assert abs(comp.params["rz"]) > 1
    assert comp.params["rx"] == pytest.approx(0, abs=1e-6)
    # turned about its own centre, which stayed where it was
    assert comp.params["x"] == pytest.approx(0, abs=1e-3)
    assert comp.params["y"] == pytest.approx(0, abs=1e-3)


def test_a_drag_elsewhere_still_orbits(app, scene):
    win, comp = scene
    view = win.view3d
    yaw = view.yaw
    _mouse(view, QEvent.MouseButtonPress, 20, 20)
    _mouse(view, QEvent.MouseMove, 80, 20)
    _mouse(view, QEvent.MouseButtonRelease, 80, 20)
    assert view.yaw != yaw and comp.params.get("x", 0) == 0


def test_escape_puts_it_back(app, scene):
    win, comp = scene
    view = win.view3d
    tool = view.edit_tool
    _c, _l, cs, tips, _r = tool._screen()
    x, y = (cs[0] + tips[2][0]) / 2, (cs[1] + tips[2][1]) / 2
    _mouse(view, QEvent.MouseButtonPress, x, y)
    _mouse(view, QEvent.MouseMove, x, y - 60)
    assert comp.params["z"] != 0
    from PyQt5.QtGui import QKeyEvent
    view.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape,
                                 Qt.NoModifier))
    assert comp.params["z"] == 0
