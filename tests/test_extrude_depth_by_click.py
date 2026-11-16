# KherveCAD - easy CAD GUI on the OpenSCAD engine.
# Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later; see LICENSE.
"""Smart Dimension and a double-click on a FINISHED extrusion open its
depth box (2026-11-16, the user: "I want to be able to create smart
dimension on extrusion ... why it does not work?" — the depth box only
opened while a sketch or the Extrude window was open)."""

import pytest
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import constrain3d, feature_dims
from khervecad import sketch_constrain_ui as ui
from khervecad.mcp_tools import McpToolExecutor

from test_stacked_features import app, win  # noqa


def _block(win):
    McpToolExecutor(win).execute("apply_code", {
        "code": "linear_extrude(height = 15) square([40, 20]);\n"})
    QApplication.processEvents()
    ext = next(n for n in win.model.root.walk()
               if n.type == "linear_extrude")
    win.resize(1300, 850)
    win.show()
    v = win.view3d
    v.set_view("Isometric", animate=False)
    v.fit()
    QTest.qWait(300)
    return ext


def _screen(win, world):
    t = constrain3d.Constrain3D(win, ui.PREFIX + "dimension")
    x, y = t._project()(world)[:2]
    return int(round(x)), int(round(y))


def _type(win, value):
    box = win.view3d._dim3d_editor
    assert box is not None, "no depth box opened"
    box.setText(value)
    QTest.keyClick(box, Qt.Key_Return)
    QTest.qWait(30)


def _height_edge(win):
    """A pixel on one of the block's upright edges, as the view picks."""
    for cx, cy in ((0, 0), (40, 0), (40, 20), (0, 20)):
        x0, y0 = _screen(win, (cx, cy, 7))
        for dx in (0, -2, 2, -4, 4):
            desc, _ = win.view3d._pick_at(x0 + dx, y0)
            if desc and desc.get("kind") == "edge":
                return x0 + dx, y0
    raise AssertionError("no upright edge in view")


@pytest.mark.parametrize("where", ["face", "edge"])
def test_smart_dimension_on_a_finished_extrusion(win, where):
    ext = _block(win)
    x, y = _screen(win, (20, 10, 15)) if where == "face" \
        else _height_edge(win)
    assert constrain3d.start(win, ui.PREFIX + "dimension")
    win.view3d.edit_tool.click(x, y)
    _type(win, "25")
    assert float(ext.params["height"]) == pytest.approx(25)


def test_double_click_the_end_face_edits_the_depth(win):
    ext = _block(win)
    x, y = _screen(win, (20, 10, 15))
    QTest.mouseDClick(win.view3d, Qt.LeftButton, Qt.NoModifier,
                      QPoint(x, y))
    QTest.qWait(30)
    _type(win, "8")
    assert float(ext.params["height"]) == pytest.approx(8)


def test_a_side_face_is_not_the_depth(win):
    ext = _block(win)
    x, y = _screen(win, (20, 0, 7))
    desc, _ = win.view3d._pick_at(x, y)
    assert feature_dims.depth_at(win, desc) is None



def test_with_the_extrude_window_open_the_end_face_is_the_depth(win):
    from test_dimension_while_extruding import _extruding, _screen as scr
    from khervecad import drag_feature
    part, ext = _extruding(win)
    h0 = float(ext.params["height"])
    assert drag_feature.pause_for(win, ui.PREFIX + "dimension")
    t = win.view3d.edit_tool
    # the middle of the boss's end face, away from its sketch's lines
    t.click(*scr(t, (45, 30, 20 + h0)))
    _type(win, "17")
    assert float(ext.params["height"]) == pytest.approx(17)
