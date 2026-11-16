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
    t = win.view3d.edit_tool
    t.click(x, y)
    # the dimension comes with the cursor first, then a click places it
    assert t._depth_pending is ext and getattr(win.view3d, "_dim3d_editor", None) is None
    win.view3d.repaint()
    t.click(x + 40, y)
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
    t.click(60, 60)
    _type(win, "17")
    assert float(ext.params["height"]) == pytest.approx(17)


def test_a_refused_dimension_names_the_relation_it_fights(win):
    from khervecad import sketch_constraints as sc
    m = win.model
    ext = m.add_node("linear_extrude", dict(height=5))
    line = m.add_node("line", dict(x1=0, y1=0, x2=20, y2=0, width=0.2),
                      parent=ext)
    sc.add(m, ext, "fix", [sc.ref_of(ext, line, "p1")])
    sc.add(m, ext, "fix", [sc.ref_of(ext, line, "p2")])
    with pytest.raises(sc.Conflict) as err:
        sc.add(m, ext, "length", [sc.ref_of(ext, line, "l")], 30)
    text = str(err.value)
    assert "It fights" in text and "FIXED" in text, text


def test_smart_dimension_on_a_cut_pocket_floor(win):
    McpToolExecutor(win).execute("apply_code", {"code": (
        "difference() {\n  cube([40, 40, 20]);\n"
        "  translate([20, 20, 12]) linear_extrude(height = 10)"
        " circle(r = 8);\n}\n")})
    QApplication.processEvents()
    cut = next(n for n in win.model.root.walk()
               if n.type == "linear_extrude")
    win.resize(1300, 850)
    win.show()
    v = win.view3d
    v.set_view("Top", animate=False)
    v.fit()
    QTest.qWait(300)
    x, y = _screen(win, (22, 22, 12))
    desc, _ = v._pick_at(x, y)
    assert feature_dims.depth_at(win, desc) is cut
    assert constrain3d.start(win, ui.PREFIX + "dimension")
    t = v.edit_tool
    t.click(x, y)
    assert t._depth_pending is cut
    t.click(x + 30, y)
    _type(win, "6")
    assert float(cut.params["height"]) == pytest.approx(6)


def test_2d_smart_dimension_on_a_boss_depth_edge(win):
    """Front view: the boss's section has upright edges along its depth;
    Smart Dimension on one sets the depth (it was a fixed reference
    line whose length could not hold)."""
    from PyQt5.QtCore import QPointF
    from khervecad import depth_dim2d, section_outline
    ext = _block(win)                      # 40 x 20, 15 high
    scene = win.view2d.scene()
    scene.set_plane("Front (XZ)")
    tris = win.view3d.model_mesh or win.view3d.mesh
    segs = section_outline.segments(tris, "Front (XZ)", 0.0)
    assert segs
    scene.face_outline = {"segments": segs, "points": [], "section": True}
    scene.ask_value = lambda kind, measured: (
        "22" if abs(measured - 15) < 1e-6 else None)
    assert depth_dim2d.press(scene, QPointF(40, 7))
    assert float(ext.params["height"]) == pytest.approx(22)
    # the bottom edge is no depth: left to the normal dimension
    assert not depth_dim2d.press(scene, QPointF(20, 0))
