"""Smart Dimension while the Extrude window is open (2026-11-10, the
user: two parallel edges of the part could not be dimensioned, stray
"Reference edge" sketches piled up in the History, and after a right
click "the extrude is gone ... I'm left not able to move").

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import constrain3d, drag_feature, sketch_constraints as sc
from khervecad.mcp_tools import McpToolExecutor

from test_stacked_features import app, win, _sketch_on  # noqa


def _screen(tool, world):
    q = tool._project()(world)
    return q[0], q[1]


def _extruding(win):
    """A plain block (no sketch) and a boss being extruded on it: the
    Extrude window open, its arrow showing."""
    McpToolExecutor(win).execute(
        "apply_code", {"code": "cube([100, 60, 20]); // Base\n"})
    QApplication.processEvents()
    part = next(c for c in win.model.root.children
                if c.visible and c.type != "assign")
    win.resize(1300, 850)
    win.show()
    tool = _sketch_on(win, part, (50, 30, 20))
    tool.set_mode("rect")
    tool.place((30, 20))
    tool.place((60, 40))
    QApplication.processEvents()
    v = win.view3d
    v.set_view("Isometric", animate=False)
    v.fit()
    QTest.qWait(400)
    assert isinstance(v.edit_tool, drag_feature.DragFeature)
    ext = v.edit_tool.target()
    return part, ext


def _smart_dimension(win):
    from khervecad import sketch_constrain_ui as ui
    assert drag_feature.pause_for(win, ui.PREFIX + "dimension")
    return win.view3d.edit_tool


def test_two_edges_of_the_part_only_measure_and_say_why(win):
    part, ext = _extruding(win)
    win.view2d.scene().ask_value = lambda k, m: "25"
    t = _smart_dimension(win)
    said = []
    t._say = said.append
    # the block's top front edge and its top back edge: parallel
    t.click(*_screen(t, (80, 0, 20)))
    got = t.click(*_screen(t, (80, 60, 20)))
    assert got is not None, said
    cont = t._working_on()
    row = [r for r in sc.rows(cont) if "value" in r][-1]
    assert row.get("driven") and row["value"] == pytest.approx(60.0)
    assert "edges of the PART" in said[-1]
    # the references are IN the sketch, not stray beside it
    refs = [n for n in win.model.root.walk()
            if n.name.startswith("Reference edge")]
    assert len(refs) == 2 and all(n.parent is cont for n in refs)


def test_a_dimension_given_up_leaves_no_reference_behind(win):
    part, ext = _extruding(win)
    win.view2d.scene().ask_value = lambda k, m: None       # Cancel
    t = _smart_dimension(win)
    t.click(*_screen(t, (80, 0, 20)))
    t.click(*_screen(t, (80, 60, 20)))
    assert not [n for n in win.model.root.walk()
                if n.name.startswith("Reference")]
    # ... nor a first pick dropped with a right click
    t.click(*_screen(t, (80, 0, 20)))
    assert [n for n in win.model.root.walk()
            if n.name.startswith("Reference")]
    t.drop()
    assert not [n for n in win.model.root.walk()
                if n.name.startswith("Reference")]


def test_a_right_click_ends_smart_dimension_and_the_arrow_is_back(win):
    part, ext = _extruding(win)
    t = _smart_dimension(win)
    v = win.view3d
    assert isinstance(v.edit_tool, constrain3d.Constrain3D)
    QTest.mouseClick(v, Qt.RightButton, Qt.NoModifier, QPoint(60, 60))
    QTest.qWait(200)
    assert isinstance(v.edit_tool, drag_feature.DragFeature)
    assert ext.parent is not None                # the extrude is still there


def test_the_view_turns_about_the_new_feature(win):
    from khervecad import cut_feature
    part, ext = _extruding(win)
    centre = cut_feature._feature_centre(win)
    assert centre[:2] == pytest.approx([45.0, 30.0], abs=0.01)
    assert centre[2] > 20.0


def test_the_arrow_has_a_right_click_ok(win):
    from PyQt5.QtCore import QTimer
    from PyQt5.QtWidgets import QMenu
    from khervecad import view3d_menu
    part, ext = _extruding(win)
    seen = []

    def choose():
        m = QApplication.activePopupWidget()
        if m is None:
            return
        seen.extend(a.text() for a in m.actions())
        m.actions()[0].trigger()
        m.close()
    QTimer.singleShot(100, choose)
    view3d_menu.context_menu(win, QPoint(80, 80))
    QTest.qWait(200)
    assert seen and seen[0].startswith("OK")
    assert win.view3d.edit_tool is None and ext.parent is not None


def test_two_corners_show_the_dimension_at_the_cursor_until_placed(win):
    """The user: "between two points it creates a lock ... I expected a
    smart dimension coming and I don't see any" — it was waiting for the
    placing click and nothing on the view said so."""
    from PyQt5.QtGui import QImage, QPainter
    from khervecad import sketch_dims3d
    part, ext = _extruding(win)
    win.view2d.scene().ask_value = lambda k, m: "70"
    t = _smart_dimension(win)
    v = win.view3d
    said = []
    v.flash = lambda text, ms=0: said.append(text)
    t.click(*_screen(t, (0, 0, 20)))             # two corners of the block
    assert t.click(*_screen(t, (100, 60, 20))) is None
    assert t._placing is not None and "click where the number goes" in said[-1]
    # the dimension is drawn at the cursor meanwhile
    t._cursor = _screen(t, (50, 80, 20))
    img = QImage(v.width(), v.height(), QImage.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    t._paint_placing(p, t._project())
    p.end()
    assert any(img.pixelColor(x, y).alpha() for x in range(0, img.width(), 3)
               for y in range(0, img.height(), 3))
    # placed above the pair: horizontal — driven, both being the part's
    got = t.click(*_screen(t, (50, 80, 20)))
    assert got is not None
    cont = t._working_on()
    row = [r for r in sc.rows(cont) if "value" in r][-1]
    assert row["kind"] == "hdistance" and row["value"] == pytest.approx(100.0)
    # ... and it is DRAWN, with no lock on the corners it measures from
    QTest.qWait(100)
    v.repaint()
    assert any(h[1] is cont for h in win._dims3d_hits)
    marks = [h for h in getattr(win, "_relation_hits", [])
             if sc.rows(h[1])[h[2]].get("kind") == "fix"]
    assert not marks
