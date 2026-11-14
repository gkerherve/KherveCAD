"""SolidWorks' extrude "From: Offset" by mouse (Exercise 55, the control
bracket: both bore cuts start 8 and 13 mm off the Front plane). The
Extrude window's From row: Sketch Plane / Offset + a distance; the
extrude starts that far along its own direction, Reverse included, and
History shows no extra row.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtTest import QTest

import test_lever_by_mouse as L
from khervecad import extrude_from, extrude_panel, feature_list
from khervecad.mcp_tools import McpToolExecutor

win = L.win


def _rect_extrude(w):
    L._open_top_sketch(w)
    w.view2d.set_tool("rect")
    L._drag(w.view2d.viewport(), L._at(w, 0, 0), L._at(w, 30, 20))
    L._extruded_boss(w)
    QTest.qWait(50)
    panel = extrude_panel._panel(w)
    assert panel is not None and panel.isVisible()
    return panel, panel.ext


def _type(spin, text):
    spin.setFocus()
    spin.selectAll()
    QTest.keyClicks(spin, text)
    QTest.keyClick(spin, Qt.Key_Return)
    QTest.qWait(30)


def _choose(combo, label):
    """Click the combo, then the entry by keyboard (offscreen popups take
    no mouse)."""
    QTest.mouseClick(combo, Qt.LeftButton)
    combo.hidePopup()
    combo.setCurrentIndex(combo.findText(label))
    QTest.qWait(30)


def _tick(box):
    """Click the check box's own square."""
    QTest.mouseClick(box, Qt.LeftButton, Qt.NoModifier,
                     QPoint(8, box.height() // 2))
    QTest.qWait(30)


def _z(w, ext):
    top = ext
    while top.parent is not None and top.parent is not w.model.root and \
            top.parent.type != "component":
        top = top.parent
    r = McpToolExecutor(w).execute("get_node_bounds", {"node_ids": [ext.id]})
    r = r["nodes"][0]
    return r["min"][2], r["max"][2]


def test_from_offset_moves_the_start_along_the_extrude(win):
    panel, ext = _rect_extrude(win)
    _type(panel.fields["height"], "10")
    assert "from" in panel.fields
    assert not panel.fields["from_offset"].isVisible()
    _choose(panel.fields["from"], "Offset")
    assert panel.fields["from_offset"].isVisible()
    _type(panel.fields["from_offset"], "8")
    assert extrude_from.offset_of(ext) == pytest.approx(8)
    lo, hi = _z(win, ext)
    assert lo == pytest.approx(8, abs=0.05) and hi == pytest.approx(18, abs=0.05)
    # Reverse: the start goes the other way too
    _tick(panel.fields["reverse"])
    QTest.qWait(30)
    lo, hi = _z(win, ext)
    assert lo == pytest.approx(-18, abs=0.05) and hi == pytest.approx(-8, abs=0.05)
    assert extrude_panel._panel(win) is panel
    # the offset is a setting of the extrude, no feature of its own
    holder = extrude_from.holder_of(ext)
    assert holder is not None and feature_list.is_plumbing(holder)
    # back to the sketch plane
    _tick(panel.fields["reverse"])
    _choose(panel.fields["from"], "Sketch Plane")
    assert extrude_from.holder_of(ext) is None
    lo, hi = _z(win, ext)
    assert lo == pytest.approx(0, abs=0.05) and hi == pytest.approx(10, abs=0.05)
    QTest.mouseClick(panel.ok, Qt.LeftButton)


def test_from_offset_with_up_to_surface_measures_from_the_offset(win):
    """Cut-Extrude1's case: Up To Surface from an offset start — the depth
    is what is left between the offset and the surface."""
    panel, ext = _rect_extrude(win)
    _choose(panel.fields["from"], "Offset")
    _type(panel.fields["from_offset"], "8")
    from khervecad import extent
    h = extent.set_extent(win.model, ext, "up_to_face",
                          face=[0, 0, 20, 0, 0, 1])
    assert h == pytest.approx(12, abs=0.05)
    lo, hi = _z(win, ext)
    assert lo == pytest.approx(8, abs=0.05) and hi == pytest.approx(20, abs=0.05)
