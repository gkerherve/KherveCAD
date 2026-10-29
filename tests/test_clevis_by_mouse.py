"""The clevis of the user's exercise drawing, built with the mouse the
way the user works (2026-10-29): Sketch Mode on a plane, shapes drawn in
the 2D view, Features ▸ Extruded Boss / Extruded Cut, the areas clicked
in 3D, Done, the Extrude window's Direction, End condition and Distance
set, OK.

  1. Front plane: the fork (a 40 mm wide body to a Ø40 lug top, the
     Ø20 pin hole) — Boss, Symmetric 50.
  2. Side plane: two lines either side of a 15 mm web under the block —
     the two areas clicked, Cut, Through all.
  3. Front plane: the Ø60 / Ø32 ring — Boss, Symmetric 50.
  4. Side plane: the 25 mm slot between the two lugs — Cut, Through all.

With KHERVECAD_SHOTS=<folder> a picture of the window is saved after
each step.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os

import pytest
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QPushButton

from khervecad import (analysis, cut_feature, extrude_panel, mesh,
                       sketch_section)
from test_lever_by_mouse import (_APP, _at, _drag, _extruded_boss, _move,
                                 _open_top_sketch, _wait, win)  # noqa

SHOTS = os.environ.get("KHERVECAD_SHOTS")


def _shot(win, name):
    if not SHOTS:
        return
    QTest.qWait(150)
    win.view3d.fit()
    QTest.qWait(150)
    win.grab().save(os.path.join(SHOTS, name + ".png"))


def _tab(win, name):
    from PyQt5.QtWidgets import QTabBar
    bar = next(b for b in win.findChildren(QTabBar) if b.isVisible() and
               any(b.tabText(i).replace("&", "") == name
                   for i in range(b.count())))
    i = next(i for i in range(bar.count())
             if bar.tabText(i).replace("&", "") == name)
    QTest.mouseClick(bar, Qt.LeftButton, Qt.NoModifier,
                     bar.tabRect(i).center())
    QTest.qWait(100)


def _sketch(win, plane):
    """The Sketch tab, Sketch, then the plane clicked in 3D."""
    _tab(win, "Sketch")
    _open_top_sketch(win, plane)


def _lines(v2, *chains):
    for chain in chains:
        v2.set_tool("line")
        for pt in chain:
            p = v2.mapFromScene(float(pt[0]), float(pt[1]))
            _move(v2.viewport(), p)
            QTest.mouseClick(v2.viewport(), Qt.LeftButton, Qt.NoModifier, p)
        QTest.keyClick(v2.viewport(), Qt.Key_Escape)
        QTest.qWait(20)


def _circle(win, c, r):
    v2 = win.view2d
    v2.set_tool("circle")
    _drag(v2.viewport(), _at(win, *c), _at(win, c[0] + r, c[1]))


def _rect(win, a, b):
    v2 = win.view2d
    v2.set_tool("rect")
    _drag(v2.viewport(), _at(win, *a), _at(win, *b))


def _click_areas(win, container, points):
    """Click each sketch point (the container's own frame) in 3D, then
    Done."""
    v3 = win.view3d
    assert v3._pick_cb is not None, "no areas offered"
    QTest.mouseClick(v3.nav_bar.buttons["fit"], Qt.LeftButton)
    QTest.qWait(100)
    o, r, u, n = sketch_section._frame(container)
    cam = v3._camera()
    for sx, sy in points:
        world = tuple(o[i] + r[i] * sx + u[i] * sy + n[i] * 0.01
                      for i in range(3))
        q = v3._project(*cam, world)
        p = QPoint(int(round(q[0])), int(round(q[1])))
        _move(v3, p)
        QTest.mouseClick(v3, Qt.LeftButton, Qt.NoModifier, p)
        QTest.qWait(30)
    done = next(b for b in v3.findChildren(QPushButton)
                if b.isVisible() and "Done" in b.text())
    QTest.mouseClick(done, Qt.LeftButton)
    QTest.qWait(150)


def _choose(combo, value):
    QTest.mouseClick(combo, Qt.LeftButton)        # opens the list
    QTest.qWait(30)
    combo.hidePopup()
    combo.setCurrentIndex(combo.findData(value))
    QTest.qWait(50)


def _type(spin, value):
    QTest.mouseDClick(spin.lineEdit(), Qt.LeftButton)
    spin.lineEdit().selectAll()
    QTest.keyClicks(spin.lineEdit(), str(value))
    QTest.keyClick(spin.lineEdit(), Qt.Key_Return)
    QTest.qWait(50)


def _window_ok(win, direction=None, distance=None, extent=None):
    panel = extrude_panel._panel(win)
    assert panel is not None, "no Extrude window"
    if direction:
        _choose(panel.fields["direction"], direction)
    if extent is not None:
        _choose(panel.fields["extent"], extent)
    if distance is not None:
        _type(panel.fields["height"], distance)
    title = panel.title.text()
    QTest.mouseClick(panel.ok, Qt.LeftButton)
    QTest.qWait(150)
    return title


def _sketch_of(win, before):
    """The sketch the shapes just drawn went into."""
    new = [n for n in win.model.root.walk() if n.id not in before
           and n.type in ("line", "circle", "rect")]
    assert new, "nothing drawn"
    return new[-1].parent


def _ids(win):
    return {n.id for n in win.model.root.walk()}


def _volume(win):
    return analysis.mass_properties(mesh.tessellate(win.model.root))


def _leave_sketch_and_cut(win):
    from test_lever_by_mouse import _extruded_boss as _boss  # noqa
    # the Features tab leaves the sketch, then Extruded Cut with nothing
    # selected offers the areas the lines make with the part
    from PyQt5.QtWidgets import QTabBar
    from khervecad import sketch_mode
    bar = next(b for b in win.findChildren(QTabBar) if b.isVisible() and
               any(b.tabText(i).replace("&", "") == "Features"
                   for i in range(b.count())))
    i = next(i for i in range(bar.count())
             if bar.tabText(i).replace("&", "") == "Features")
    QTest.mouseClick(bar, Qt.LeftButton, Qt.NoModifier,
                     bar.tabRect(i).center())
    assert _wait(lambda: not sketch_mode.sketching(win))
    QTest.qWait(300)
    win.builder.active_tree().clearSelection()
    act = next(a for a in cut_feature.actions(win)
               if a.data() == "extruded_cut")
    from test_lever_by_mouse import _button_for
    try:
        QTest.mouseClick(_button_for(win, act), Qt.LeftButton)
    except StopIteration:
        act.trigger()
    QTest.qWait(80)


def _snap(win):
    """Snap to a 2.5 mm grid, as the user sets it: the drawing's sizes
    (7.5, 12.5) land exactly."""
    sc = win.view2d.scene()
    sc.snap_enabled = True
    sc.grid_size = 2.5


def _frame(win, x, y, w, h):
    from PyQt5.QtCore import QRectF
    win.view2d.frame_rect(QRectF(x, y, w, h))
    QTest.qWait(30)


def test_the_clevis_by_mouse(win):
    """The drawing's sizes, the cylinder's axis at z = 0: cylinder top 30,
    block bottom 50 (80 below the lug top), hole centre 90 (40 above the
    block bottom), lug top 110, slot bottom 75 (25 above the block
    bottom); fork 40 across (the Ø40 lug) by 50 along the axis, slot 25,
    web 15."""
    v2 = win.view2d
    # ---- 1. Front plane: the fork's outline, lug top and pin hole
    before = _ids(win)
    _sketch(win, "Front (XZ)")
    _snap(win)
    _frame(win, -45, -10, 90, 130)
    _rect(win, (-20, 17.5), (20, 90))   # down near the bore (16)
    _circle(win, (0, 90), 20)
    _circle(win, (0, 90), 10)
    fork = _sketch_of(win, before)
    _extruded_boss(win)
    _click_areas(win, fork, [(0, 40), (0, 105), (-15, 85)])
    _window_ok(win, direction="symmetric", distance=50)
    _shot(win, "1-fork-boss")
    v = _volume(win)
    assert v["size"] == pytest.approx([40, 50, 92.5], abs=0.05)
    # ---- 2. Side plane: the bottom cut, both sides of the 15 web,
    # from the block's underside (z 50) down
    before = _ids(win)
    _sketch(win, "Side (YZ)")
    _snap(win)
    # zoomed in on each pocket: further out the line lined up with the
    # middle of the part's side (z 48.75) — the dotted guide shows it
    _frame(win, 2, 5, 43, 50)
    _lines(v2, [(7.5, 10), (7.5, 50), (40, 50), (40, 10), (7.5, 10)])
    _frame(win, -45, 5, 43, 50)
    _lines(v2, [(-7.5, 10), (-7.5, 50), (-40, 50), (-40, 10), (-7.5, 10)])
    _frame(win, -45, 0, 90, 120)
    web = _sketch_of(win, before)
    _shot(win, "2a-bottom-cut-sketch")
    _leave_sketch_and_cut(win)
    _click_areas(win, web, [(16, 30), (-16, 30)])
    title = _window_ok(win, extent="through_all")
    assert title == "Extruded Cut"
    _shot(win, "2b-bottom-cut")
    v_cut = _volume(win)["volume"]
    assert v["volume"] - v_cut == pytest.approx(2 * 17.5 * 32.5 * 40,
                                                rel=0.01)
    # ---- 3. Front plane: the Ø60 / Ø32 cylinder, 50 long
    before = _ids(win)
    _sketch(win, "Front (XZ)")
    _snap(win)
    _frame(win, -45, -40, 90, 160)
    _circle(win, (0, 0), 30)
    _circle(win, (0, 0), 16)
    ring = _sketch_of(win, before)
    _extruded_boss(win)
    # the fork's outline splits the ring: its top piece too
    _click_areas(win, ring, [(0, -23), (0, 23)])
    _window_ok(win, direction="symmetric", distance=50)
    _shot(win, "3-cylinder-boss")
    v = _volume(win)
    assert v["size"] == pytest.approx([60, 50, 140], abs=0.05)
    # ---- 4. Side plane: the 25 slot between the lugs, down to z 75
    before = _ids(win)
    _sketch(win, "Side (YZ)")
    _snap(win)
    _frame(win, -45, 30, 90, 100)
    _lines(v2, [(-12.5, 120), (-12.5, 75), (12.5, 75), (12.5, 120),
                (-12.5, 120)])
    slot = _sketch_of(win, before)
    _leave_sketch_and_cut(win)
    _click_areas(win, slot, [(0, 77.5), (0, 90), (0, 105), (0, 115)])
    _window_ok(win, extent="through_all")
    _shot(win, "4-slot-cut")
    if SHOTS:                        # from the drawing's corner
        for yaw in (-60, 30):
            win.view3d.snapshot(1000, 900, yaw=yaw, pitch=25,
                                clean=True)[0].save(os.path.join(
                                    SHOTS, "5-finished-%d.png" % yaw))
    # the finished part, measured with rays along Y
    tris = mesh.tessellate(win.model.root)

    def crossings(x, z):
        hits = analysis.surface_hits((x, -100, z), (0, 1, 0),
                                     [("part", tris)])
        return sorted(round(h["point"][1], 2) for h in hits)
    lugs = [-25, -12.5, 12.5, 25]
    assert crossings(0, 105) == pytest.approx(lugs, abs=0.05)
    assert crossings(15, 90) == pytest.approx(lugs, abs=0.05)
    assert crossings(0, 90) == []                     # the pin hole
    assert crossings(0, 60) == pytest.approx([-25, 25], abs=0.05)
    assert crossings(0, 40) == pytest.approx([-7.5, 7.5], abs=0.05)
    assert crossings(18, 40) == pytest.approx([-7.5, 7.5], abs=0.05)
    assert crossings(0, 0) == []                      # the bore
    assert crossings(0, 23) == pytest.approx([-25, 25], abs=0.05)
