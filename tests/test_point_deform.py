"""SolidWorks' Deform ▸ Point (2026-11-15, the "Deform feature" video):
the falloff maths, then the whole window BY MOUSE — the ribbon's Deform
button, Type Point, the Origin row of the tree as the point, the body
clicked in the tree, distance 15 and radius 40, OK — and the MCP tool.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import numpy as np
import pytest
from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QToolButton

from khervecad import analysis, mesh, point_deform, toolbar_style
from khervecad.mcp_tools import McpToolExecutor

_APP = QApplication.instance() or QApplication([])

# the fan cover's plate with its recess and a few square holes
PLATE = ("difference(){ cylinder(h=3,d=90,$fn=96); "
         "translate([0,0,2]) cylinder(h=2,d=80,$fn=96);"
         "for (x=[-10:10:10], y=[-10:10:10]) "
         "translate([x-1,y-1,0]) cube([2,2,3]);}")


def test_the_falloff_is_one_at_the_point_and_zero_at_the_radius():
    for shape in point_deform.SHAPES:
        f = point_deform.falloff(np.array([0.0, 0.5, 1.0, 2.0]), shape)
        assert f[0] == pytest.approx(1.0)
        assert f[2] == pytest.approx(0.0) and f[3] == pytest.approx(0.0)
        assert 0.0 < f[1] < 1.0
    mid = [float(point_deform.falloff(0.5, s)) for s in point_deform.SHAPES]
    assert mid[0] < mid[1] < mid[2]          # stiffness: peak ... hill


def test_push_moves_only_what_is_inside_the_radius():
    v = np.array([[0, 0, 0], [10, 0, 0], [50, 0, 0.0]])
    out = point_deform.push(v, (0, 0, 0), (0, 0, 1), 15, 40, "medium")
    assert out[0][2] == pytest.approx(15)
    assert 0 < out[1][2] < 15
    assert out[2].tolist() == [50, 0, 0]
    assert out[1][0] == 10                       # only along the axis


@pytest.fixture
def win():
    QSettings("Kherve", "KherveCAD").setValue("tree/history", True)
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    w.resize(1500, 950)
    toolbar_style.apply(w, "SolidWorks", remember=False)
    w.show()
    McpToolExecutor(w).execute("apply_code", {"code": PLATE})
    QTest.qWaitForWindowExposed(w)
    w.ribbon.show_tab("features")
    QTest.qWait(50)
    yield w
    QSettings("Kherve", "KherveCAD").setValue("tree/history", False)
    toolbar_style.apply(w, "KherveCAD", remember=False)
    w._dirty = False
    w.close()


def _button(win, key):
    return next(b for b in win.findChildren(QToolButton)
                if b.isVisible() and b.defaultAction() is not None
                and b.defaultAction().data() == key)


def _click_row(win, match):
    """A real mouse click on the tree row *match*(item) accepts."""
    tree = win.builder.active_tree()
    from PyQt5.QtWidgets import QTreeWidgetItemIterator
    it = QTreeWidgetItemIterator(tree)
    while it.value() is not None:
        item = it.value()
        if match(tree, item):
            tree.scrollToItem(item)
            QTest.mouseClick(tree.viewport(), Qt.LeftButton,
                             Qt.NoModifier,
                             tree.visualItemRect(item).center())
            QTest.qWait(30)
            return item
        it += 1
    raise AssertionError("no such row")


def _top(win):
    return max(p[2] for t in mesh.tessellate(win.model.root)
               for p in t[:3])


def test_point_deform_by_mouse_makes_the_dome(win):
    from khervecad import tree_history
    body = [c for c in win.model.root.children if c.visible][0]
    base_volume = analysis.mass_properties(
        mesh.tessellate(win.model.root))["volume"]
    assert _top(win) == pytest.approx(3.0)
    QTest.mouseClick(_button(win, "curve_deform"), Qt.LeftButton)
    QTest.qWait(50)
    panel = win._deform_panel
    assert panel is not None and panel.isVisible()
    panel.fields["type"].setCurrentIndex(0)           # Point
    QTest.qWait(30)
    assert win._deform_state["type"] == "point"
    assert panel.boxes["point"].isVisible()
    assert not panel.boxes["initial"].isVisible()
    # the Origin row of the tree is the deform point
    _click_row(win, lambda t, i: i.data(0, tree_history.ROLE_FIXED)
               == "origin")
    assert win._deform_state["point"] == (0.0, 0.0, 0.0)
    assert "Origin" in panel.boxes["point"].body.text()
    assert not panel.ok.isEnabled()                    # no body yet
    _click_row(win, lambda t, i: t.node_of(i) is body)
    assert win._deform_state["bodies"] == [body]
    panel.fields["distance"].setValue(15.0)
    panel.fields["radius"].setValue(40.0)
    assert panel.ok.isEnabled()
    panel.ok.click()
    QTest.qWait(50)
    node = next(n for n in win.model.root.walk()
                if n.type == "point_deform")
    assert node.params["distance"] == 15 and node.params["radius"] == 40
    assert node.params["dz"] == pytest.approx(1.0)
    # the dome: the 2 mm recess floor + 15 at the crown, beyond r=40
    # the plate is where it was
    top = _top(win)
    assert 16.5 < top <= 18.05, top
    tris = mesh.tessellate(win.model.root)
    rim = [p for t in tris for p in t[:3]
           if (p[0] ** 2 + p[1] ** 2) ** 0.5 > 41 and p[2] > 0.1]
    assert rim and max(p[2] for p in rim) <= 3.0 + 1e-6
    vol = analysis.mass_properties(tris)["volume"]
    assert vol == pytest.approx(base_volume, rel=0.06)
    from khervecad import model as M
    assert not M.validate(win.model.root)


def _deform_by_mouse(win, body, distance, radius, reverse=False):
    """One Deform window run: ribbon button, Type Point, Origin row,
    the body's row, the numbers, OK."""
    from khervecad import tree_history
    QTest.mouseClick(_button(win, "curve_deform"), Qt.LeftButton)
    QTest.qWait(50)
    panel = win._deform_panel
    panel.fields["type"].setCurrentIndex(0)
    QTest.qWait(30)
    _click_row(win, lambda t, i: i.data(0, tree_history.ROLE_FIXED)
               == "origin")
    _click_row(win, lambda t, i: t.node_of(i) is body)
    panel.fields["distance"].setValue(distance)
    panel.fields["radius"].setValue(radius)
    if reverse:
        panel.fields["reverse"].setChecked(True)
    assert panel.ok.isEnabled()
    panel.ok.click()
    QTest.qWait(50)
    return next(n for n in win.model.root.walk()
                if n.type == "point_deform" and body in
                [c for c in n.children])


def test_the_videos_two_deforms_make_a_dome_with_a_distinct_dimple(win):
    """The video: Deform1 15 mm up, radius 40, medium; Deform2 10 mm
    down, radius 30, medium. The crown is a plateau dome (about 17 mm
    over the plate, steep at the rim); the second push leaves a RING
    ridge round a central dimple, 3 mm deep, the dome 12-14 mm high."""
    body = [c for c in win.model.root.children if c.visible][0]
    d1 = _deform_by_mouse(win, body, 15.0, 40.0)
    assert 16.5 < _top(win) <= 18.05
    # a plateau dome: still 90 % of the lift 10 mm out, steep at 30
    tris = mesh.tessellate(win.model.root)
    pts = [p for t in tris for p in t[:3] if p[2] > 1.0]

    def z_at(r, tol=2.0):
        zs = [p[2] for p in pts if abs((p[0] ** 2 + p[1] ** 2) ** 0.5 - r)
              < tol]
        return max(zs)
    assert z_at(10) > 2 + 0.9 * 15 - 0.8 and z_at(32) < 2 + 0.35 * 15
    _deform_by_mouse(win, d1, 10.0, 30.0, reverse=True)
    tris = mesh.tessellate(win.model.root)
    pts = [p for t in tris for p in t[:3] if p[2] > 1.0]
    ridge = max(p[2] for p in pts)
    centre = max(p[2] for p in pts
                 if (p[0] ** 2 + p[1] ** 2) ** 0.5 < 6)
    assert 12.0 < ridge < 14.0, ridge
    assert ridge - centre >= 2.0, (ridge, centre)
    at = max((p for p in pts if p[2] > ridge - 0.01),
             key=lambda p: p[2])
    assert 10 < (at[0] ** 2 + at[1] ** 2) ** 0.5 < 26


def test_the_mcp_tool_validates(win):
    ex = McpToolExecutor(win)
    body = [c for c in win.model.root.children if c.visible][0]
    out = ex.execute("deform_point", dict(body_ids=[body.id],
                                          shape="bogus"))
    assert "error" in out
