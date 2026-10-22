"""The move triad: shown by selecting a part, free drag on the part,
typed position.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QEvent, QPointF, Qt
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import QApplication

from khervecad import drag_feature, gumball

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


def _ev(kind, x, y, mods=Qt.NoModifier):
    return QMouseEvent(kind, QPointF(x, y), Qt.LeftButton, Qt.LeftButton,
                       mods)


def _part(win):
    m = win.model
    g = m.add_node("union", {})
    m.add_node("cube", dict(width=20, depth=20, height=20), parent=g)
    _APP.processEvents()
    return g


def test_selecting_a_part_shows_no_triad_until_the_gumball_is_on(win):
    """The user changed their mind: the triad only with the Gumball."""
    g = _part(win)
    win.builder.tree.select_nodes([g])
    assert win.view3d.edit_tool is None
    assert gumball.toggle(win, True)
    assert isinstance(win.view3d.edit_tool, gumball.Gumball)
    gumball.toggle(win, False)
    assert win.view3d.edit_tool is None


def test_snap_and_gumball_sit_beside_translate(win):
    from khervecad import ribbon, toolbar_style
    toolbar_style.apply(win, "SolidWorks", remember=False)
    try:
        _t, acts = ribbon.panel_actions(win, "transform")
        data = [a.data() for a in acts]
        assert "translate" in data and win._gumball_act in acts
        assert win._bar_parts["snap"] in acts
        _t, assemble = ribbon.panel_actions(win, "assemble")
        assert win._gumball_act not in assemble
    finally:
        toolbar_style.apply(win, "KherveCAD", remember=False)


def test_type_where_the_part_goes(win):
    g = _part(win)
    win.builder.tree.select_nodes([g])
    gumball.toggle(win, True)
    tool = win.view3d.edit_tool
    _APP.processEvents()
    c = tool.centre()
    tool.move_to([c[0] + 30, c[1], c[2] - 5])
    _APP.processEvents()
    assert float(g.params.get("x", 0)) == pytest.approx(30)
    assert float(g.params.get("z", 0)) == pytest.approx(-5)


def test_drag_the_part_itself(win):
    g = _part(win)
    view = win.view3d
    view.set_view("Front", animate=False)
    win.builder.tree.select_nodes([g])
    gumball.toggle(win, True)
    tool = view.edit_tool
    _APP.processEvents()
    # press on the part (its projected centre), away from the handles
    project = tool._project()
    tris = view.highlight_mesh
    assert tris
    from khervecad import anchors
    pt = None
    for t in tris:
        cx = sum(p[0] for p in t) / 3
        cz = sum(p[2] for p in t) / 3
        s = project((cx, sum(p[1] for p in t) / 3, cz))
        if s and anchors.pick(tris, project, s[0], s[1])[0] is not None \
                and tool._screen() and \
                gumball.handle_at(s[0], s[1], tool._screen()[2][:2],
                                  [t2[:2] for t2 in tool._screen()[3]],
                                  [[p[:2] for p in r]
                                   for r in tool._screen()[4]]) is None:
            pt = s
            break
    assert pt is not None
    assert tool.mouse_press(_ev(QEvent.MouseButtonPress, pt[0], pt[1]))
    assert tool.drag["handle"][0] == "free"
    tool.mouse_move(_ev(QEvent.MouseMove, pt[0] + 60, pt[1]))
    tool.mouse_release(None)
    # seen from the front, moving right is +X
    assert float(g.params.get("x", 0)) > 1.0
    assert abs(float(g.params.get("y", 0))) < 1e-6
