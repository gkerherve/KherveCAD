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


def test_selecting_a_move_shows_the_triad_and_moves_it(win):
    m = win.model
    mv = m.add_node("translate", dict(x=0, y=0, z=0))
    m.add_node("cube", dict(width=10, depth=10, height=10), parent=mv)
    _APP.processEvents()
    win.builder.active_tree().select_nodes([mv])
    _APP.processEvents()
    tool = win.view3d.edit_tool
    assert isinstance(tool, gumball.Gumball) and tool.auto
    assert tool.target() is mv
    assert tool.mode() == "move"                # arrows only
    tool.move_to((20.0, 5.0, 5.0))
    assert float(mv.params["x"]) == pytest.approx(20.0, abs=0.01)
    assert "rx" not in mv.params
    assert mv.parent is m.root                  # not wrapped in a Group
    win.builder.active_tree().select_nodes([])
    _APP.processEvents()
    assert win.view3d.edit_tool is None


def test_selecting_a_rotate_shows_the_triad_and_turns_it(win):
    m = win.model
    rot = m.add_node("rotate", dict(x=0, y=0, z=0))
    poly = m.add_node("polygon", dict(points=[[0, 0], [10, 0], [0, 10]]))
    m.add_node("cube", dict(width=10, depth=10, height=10), parent=rot)
    _APP.processEvents()
    tree = win.builder.active_tree()
    tree.select_nodes([rot])
    _APP.processEvents()
    tool = win.view3d.edit_tool
    assert isinstance(tool, gumball.Gumball) and tool.target() is rot
    assert tool.mode() == "turn"                # rings only
    d = dict(handle=("turn", 2), node=rot, start=gumball._start(rot),
             centre=tool.centre(), value=30.0)
    tool._apply(d)
    assert float(rot.params["z"]) == pytest.approx(30.0, abs=0.01)
    assert "rx" not in rot.params
    tree.select_nodes([poly])                  # a polygon: gone
    _APP.processEvents()
    assert win.view3d.edit_tool is None


def test_the_typed_box_is_the_position_not_the_centre(win):
    m = win.model
    g = m.add_node("union", dict(x=7.5, y=10, z=2.5, ry=-90))
    m.add_node("cylinder", dict(r1=3, r2=3, height=10), parent=g)
    _APP.processEvents()
    tool = gumball.Gumball(win)
    win.builder.active_tree().select_nodes([g])
    _APP.processEvents()
    assert tool.position() == pytest.approx((7.5, 10, 2.5))
    tool.set_position((1, 2, 3))
    assert [float(g.params[k]) for k in "xyz"] == [1, 2, 3]


def test_a_ring_changes_only_its_angle_and_lands_on_release(win):
    m = win.model
    g = m.add_node("union", dict(x=7.5, y=10, z=2.5, ry=-90))
    m.add_node("cylinder", dict(r1=3, r2=3, height=10), parent=g)
    _APP.processEvents()
    win.view3d.edit_tool = None
    tool = gumball.Gumball(win)
    win.builder.active_tree().select_nodes([g])
    _APP.processEvents()
    assert tool.centre() == pytest.approx((7.5, 10, 2.5), abs=1e-6)
    d = dict(handle=("turn", 1), node=g, start=gumball._start(g),
             centre=tool.centre(), value=6.0)
    tool.drag = d
    d["values"] = tool._values(d)
    assert float(g.params["ry"]) == -90          # nothing applied yet
    tool._ghost_matrix(d)
    tool.drag = None
    tool._apply(d)
    assert [float(g.params[k]) for k in ("x", "y", "z", "rx", "ry", "rz")] \
        == pytest.approx([7.5, 10, 2.5, 0, -84, 0])


def test_angles_lock_and_tenths():
    assert gumball.lock_angle(-87.6) == -90
    assert gumball.lock_angle(44.0) == 45
    assert gumball.lock_angle(31.9) == 30
    assert gumball.lock_angle(36.234) == 36.2


def test_the_tree_rows_follow_the_drag(win):
    from khervecad.treepanel import ROLE_PLACEMENT
    m = win.model
    g = m.new_component("Pin")
    g.visible = True
    g.params.update(x=7.5, y=10, z=2.5, ry=-90)
    m.add_node("cylinder", dict(r1=3, r2=3, height=10), parent=g)
    _APP.processEvents()
    tree = win.builder.active_tree()
    tree.select_nodes([g])
    _APP.processEvents()
    tool = gumball.Gumball(win)
    d = dict(handle=("turn", 1), node=g, start=gumball._start(g),
             centre=tool.centre(), value=6.0)
    d["values"] = tool._values(d)
    tool._live_tree(d)
    item = tree._item_of(g)
    rows = [item.child(i).text(0) for i in range(item.childCount())
            if item.child(i).data(0, ROLE_PLACEMENT)]
    assert any(r.startswith("Rotation (0, -84, 0)") for r in rows), rows
    assert float(g.params["ry"]) == -90          # model untouched
