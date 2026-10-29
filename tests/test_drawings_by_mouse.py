"""Two textbook exercises built with the mouse (2026-10-29, the user: "can
you make those two parts using the mouse and show me step by step ...
also work with smart dimension"): the PIVOT GUIDE and the BEARING
BRACKET. Every step is Sketch on a plane, shapes drawn in the 2D view,
Smart Dimension clicked, Features ▸ Extruded Boss / Cut, the areas
clicked in 3D, the Extrude window, OK. With KHERVECAD_SHOTS=<folder> a
picture is saved after each step.

Simplified where the drawing needs more than an extrude can give: the
pivot guide's lug stands upright (the drawing leans it 15°) and its
curved R100 arm is left out; the bracket's ribs are straight and its
Ø17 tapped boss, side boss and R3 fillets are left out.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest

from khervecad import analysis, mesh, sketch_constraints as sc
from test_clevis_by_mouse import (SHOTS, _circle, _click_areas, _frame,
                                  _ids, _leave_sketch_and_cut, _lines,
                                  _rect, _shot, _sketch, _sketch_of, _snap,
                                  _volume, _window_ok)
from test_lever_by_mouse import _at, _extruded_boss, _move, win  # noqa
from test_smart_dimension_by_mouse import _dimension


def _crossings(win, origin, direction):
    tris = mesh.tessellate(win.model.root)
    axis = [i for i in range(3) if direction[i]][0]
    hits = analysis.surface_hits(origin, direction, [("part", tris)])
    return sorted(round(h["point"][axis], 2) for h in hits)


def _views(win, name):
    if SHOTS:
        for yaw in (-55, 35):
            win.view3d.snapshot(1000, 900, yaw=yaw, pitch=25,
                                clean=True)[0].save(os.path.join(
                                    SHOTS, "%s-%d.png" % (name, yaw)))


def _select_at(win, pt, mods=Qt.NoModifier):
    v2 = win.view2d
    v2.set_tool("select")
    p = _at(win, *pt)
    _move(v2.viewport(), p)
    QTest.mouseClick(v2.viewport(), Qt.LeftButton, mods, p)
    QTest.qWait(50)


def _cut_selected(win):
    """Features tab, then Extruded Cut with the sketch shapes selected."""
    from test_lever_by_mouse import _button_for
    from khervecad import cut_feature, sketch_mode
    from test_lever_by_mouse import _wait
    from PyQt5.QtWidgets import QTabBar
    bar = next(b for b in win.findChildren(QTabBar) if b.isVisible() and
               any(b.tabText(i).replace("&", "") == "Features"
                   for i in range(b.count())))
    i = next(i for i in range(bar.count())
             if bar.tabText(i).replace("&", "") == "Features")
    QTest.mouseClick(bar, Qt.LeftButton, Qt.NoModifier,
                     bar.tabRect(i).center())
    assert _wait(lambda: not sketch_mode.sketching(win))
    QTest.qWait(300)
    act = next(a for a in cut_feature.actions(win)
               if a.data() == "extruded_cut")
    QTest.mouseClick(_button_for(win, act), Qt.LeftButton)
    QTest.qWait(80)
    assert win.view3d._pick_cb is None


def _edit_in_3d(win, cont, kind, value):
    """Click a sketch dimension's value in the 3D view, type *value*."""
    v3 = win.view3d
    QTest.mouseClick(v3.nav_bar.buttons["fit"], Qt.LeftButton)
    v3.repaint()
    QTest.qWait(100)
    i = next(i for i, r in enumerate(sc.rows(cont)) if r["kind"] == kind)
    rect = next(h[0] for h in win._dims3d_hits
                if h[1] is cont and h[2] == i)
    p = rect.center().toPoint()
    QTest.mousePress(v3, Qt.LeftButton, Qt.NoModifier, p)
    QTest.mouseRelease(v3, Qt.LeftButton, Qt.NoModifier, p)
    QTest.qWait(50)
    box = v3._dim3d_editor
    box.selectAll()
    QTest.keyClicks(box, str(value))
    QTest.keyClick(box, Qt.Key_Return)
    QTest.qWait(300)


def test_the_pivot_guide_by_mouse(win):
    """Pivot hole at the origin; the plate 40 thick (Y) from x -22.5 to
    the R25 end round (85, 0), 48 up to the lug's seat; the 27 slot from
    x 45 to 85; the Ø16 hole 35 above the seat in a lug R20, 16 thick."""
    v2 = win.view2d
    # ---- 1. Front plane: the plate's outline and its R25 end
    before = _ids(win)
    _sketch(win, "Front (XZ)")
    _snap(win)
    _frame(win, -40, -40, 160, 110)
    _lines(v2, [(-22.5, -25), (85, -25), (85, 25), (22.5, 25),
                (22.5, 47.5), (-22.5, 47.5), (-22.5, -25)])
    _circle(win, (85, 0), 25)
    plate = _sketch_of(win, before)
    # Smart Dimension: the seat line's MIDDLE to the origin, 47.5 -> 48
    asked = _dimension(win, (0, 47.5), (0, 0), value=48)
    assert asked and asked[0] == ("distance", pytest.approx(47.5))
    _shot(win, "p1a-plate-sketch")
    _extruded_boss(win)
    _click_areas(win, plate, [(0, 0), (75, 0), (100, 0)])
    _window_ok(win, direction="symmetric", distance=40)
    _shot(win, "p1b-plate-boss")
    assert _volume(win)["size"] == pytest.approx([132.5, 40, 73], abs=0.05)
    # ---- 2. Front plane: the pivot hole, drawn Ø10, Smart Dimension
    # to 12.5, then cut through
    before = _ids(win)
    _sketch(win, "Front (XZ)")
    _snap(win)
    _frame(win, -30, -30, 60, 60)
    _circle(win, (0, 0), 5)
    hole = _sketch_of(win, before)
    asked = _dimension(win, (5, 0), (20, 20), value=12.5)
    assert asked and asked[0][0] == "diameter", asked
    _shot(win, "p2a-pivot-hole-smart-dimension")
    _leave_sketch_and_cut(win)
    _click_areas(win, hole, [(0, 0)])
    _window_ok(win, extent="through_all")
    _shot(win, "p2b-pivot-hole-cut")
    assert _crossings(win, (0, -100, 0), (0, 1, 0)) == []
    # ---- 3. Front plane: the slot — a rectangle between two circles
    before = _ids(win)
    _sketch(win, "Front (XZ)")
    _snap(win)
    _frame(win, 20, -30, 90, 60)
    _rect(win, (45, -12.5), (85, 12.5))
    _circle(win, (45, 0), 12.5)
    _circle(win, (85, 0), 12.5)
    slot = _sketch_of(win, before)
    # Smart Dimension: the slot's centre line, origin to its left end
    asked = _dimension(win, (45, 0), (0, 0), value=45)
    _shot(win, "p3a-slot-sketch")
    # the three shapes selected (click, Ctrl+click) and Extruded Cut:
    # everything they close is cut, no wall left where they cross
    _select_at(win, (65, 12.5))
    _select_at(win, (32.5, 0), Qt.ControlModifier)
    _select_at(win, (97.5, 0), Qt.ControlModifier)
    _cut_selected(win)
    _window_ok(win, extent="through_all")
    _shot(win, "p3b-slot-cut")
    for x in (40, 47, 65, 83, 90):          # no wall anywhere in it
        assert _crossings(win, (x, -100, 0), (0, 1, 0)) == [], x
    assert _crossings(win, (65, -100, 20), (0, 1, 0)) == \
        pytest.approx([-20, 20], abs=0.05)
    # ---- 4. Front plane: the lug on the seat, R20 top, 16 thick
    before = _ids(win)
    _sketch(win, "Front (XZ)")
    _snap(win)
    _frame(win, -40, 30, 80, 90)
    _rect(win, (-20, 48), (20, 83))
    _circle(win, (0, 83), 20)
    lug = _sketch_of(win, before)
    _shot(win, "p4a-lug-sketch")
    _extruded_boss(win)
    _click_areas(win, lug, [(0, 60), (0, 75), (0, 98)])
    _window_ok(win, direction="symmetric", distance=16)
    _shot(win, "p4b-lug-boss")
    # ---- 5. the Ø16 hole through the lug
    before = _ids(win)
    _sketch(win, "Front (XZ)")
    _snap(win)
    _frame(win, -30, 55, 60, 60)
    _circle(win, (0, 83), 7.5)
    pin = _sketch_of(win, before)
    _dimension(win, (7.5, 83), (25, 105), value=16)
    _shot(win, "p5a-lug-hole-smart-dimension")
    _leave_sketch_and_cut(win)
    _click_areas(win, pin, [(0, 83)])
    _window_ok(win, extent="through_all")
    _shot(win, "p5b-lug-hole-cut")
    _views(win, "p6-pivot-guide")
    assert _volume(win)["size"] == pytest.approx([132.5, 40, 128], abs=0.6)
    assert _crossings(win, (0, -100, 83), (0, 1, 0)) == []
    assert _crossings(win, (0, -100, 95), (0, 1, 0)) == \
        pytest.approx([-8, 8], abs=0.05)
    # ---- 6. later: the pivot hole's Ø clicked in 3D, 12.5 -> 20
    cont = next(n for n in win.model.root.walk()
                if any(r["kind"] == "diameter" and
                       r.get("value") == 12.5 for r in sc.rows(n)))
    _edit_in_3d(win, cont, "diameter", 20)
    _shot(win, "p7-pivot-hole-changed-to-20")
    assert _crossings(win, (0, -100, 8), (0, 1, 0)) == []
    assert _crossings(win, (0, -100, 11), (0, 1, 0)) == \
        pytest.approx([-20, 20], abs=0.05)


def test_the_bearing_bracket_by_mouse(win):
    """Base 84 x 70 x 11 with four Ø8 holes 58 x 46 apart; a web 8 thick
    tapering from 42 to 28 and an identical rib across it; the Ø46
    bearing boss, 34 long, its centre 133 up, reamed Ø28.55."""
    v2 = win.view2d
    # ---- 1. Top plane: the base
    before = _ids(win)
    _sketch(win, "Top (XY)")
    _snap(win)
    _frame(win, -60, -50, 120, 100)
    _rect(win, (-42.5, -35), (42.5, 35))
    base = _sketch_of(win, before)
    # Smart Dimension: the width 85 -> 84
    rect = next(c for c in base.children if c.type == "rect")
    # Smart Dimension: the depth first (the first dimension scales the
    # whole sketch, so it is given its true 70), then the width 85 -> 84
    _dimension(win, (42.5, 0), (55, 0), value=70)
    _dimension(win, (0, 35), (0, 50), value=84)
    _shot(win, "b1a-base-sketch")
    _extruded_boss(win)            # one rectangle: no areas to pick
    _window_ok(win, distance=11)
    _shot(win, "b1b-base-boss")
    assert _volume(win)["size"] == pytest.approx([84, 70, 11], abs=0.05)
    # ---- 2. Top plane: the four Ø8 holes, cut through
    before = _ids(win)
    _sketch(win, "Top (XY)")
    _snap(win)
    _frame(win, -60, -50, 120, 100)
    win.view2d.scene().grid_size = 0.5     # the holes' 29 and 23 land
    for x in (-29, 29):
        for y in (-23, 23):
            _circle(win, (x, y), 5)
    holes = _sketch_of(win, before)
    first = next(c for c in holes.children if c.type == "circle")
    # Smart Dimension: each Ø10 typed 8 — only that circle changes
    for x in (-29, 29):
        for y in (-23, 23):
            # a click on empty space after the circle: its Ø
            _dimension(win, (x + 5, y), (x + 8, y - 8), value=8)
    assert all(c.params["radius"] == pytest.approx(4)
               for c in holes.children if c.type == "circle")
    _shot(win, "b2a-holes-sketch")
    _leave_sketch_and_cut(win)
    _click_areas(win, holes, [(x, y) for x in (-29, 29)
                              for y in (-23, 23)])
    _window_ok(win, extent="through_all")
    _shot(win, "b2b-holes-cut")
    assert _crossings(win, (-29, -23, -50), (0, 0, 1)) == []
    # ---- 3. Front plane: the web, 42 at the base to 28 at the boss
    before = _ids(win)
    _sketch(win, "Front (XZ)")
    _snap(win)
    _frame(win, -60, -10, 120, 170)
    _lines(v2, [(-21, 11), (21, 11), (14, 130), (-14, 130), (-21, 11)])
    web = _sketch_of(win, before)
    _shot(win, "b3a-web-sketch")
    _extruded_boss(win)
    _click_areas(win, web, [(0, 60)])
    _window_ok(win, direction="symmetric", distance=8)
    _shot(win, "b3b-web-boss")
    # ---- 4. Side plane: the rib across it, the same shape
    before = _ids(win)
    _sketch(win, "Side (YZ)")
    _snap(win)
    _frame(win, -60, -10, 120, 170)
    _lines(v2, [(-30, 11), (30, 11), (10, 130), (-10, 130), (-30, 11)])
    rib = _sketch_of(win, before)
    _shot(win, "b4a-rib-sketch")
    _extruded_boss(win)
    _click_areas(win, rib, [(-15, 40), (15, 40), (0, 120)])
    _window_ok(win, direction="symmetric", distance=8)
    _shot(win, "b4b-rib-boss")
    # ---- 5. Front plane: the Ø46 bearing boss, 34 long, centre 133 up
    before = _ids(win)
    _sketch(win, "Front (XZ)")
    _snap(win)
    _frame(win, -50, 90, 100, 80)
    win.view2d.scene().grid_size = 0.5
    _circle(win, (0, 133), 22.5)
    boss = _sketch_of(win, before)
    # Smart Dimension: Ø45 -> 46, then the origin to its centre 132.5 -> 133
    _dimension(win, (22.5, 133), (40, 160), value=46)
    _shot(win, "b5a-boss-sketch")
    # the web's and rib's outlines split the circle into pieces: the
    # circle SELECTED (a click on its rim) extrudes all it closes at once
    _select_at(win, (0, 156))
    _extruded_boss(win)
    assert win.view3d._pick_cb is None
    _window_ok(win, direction="symmetric", distance=34)
    _shot(win, "b5b-boss")
    # ---- 6. the reamed bore Ø28.55
    before = _ids(win)
    _sketch(win, "Front (XZ)")
    _snap(win)
    _frame(win, -50, 90, 100, 80)
    win.view2d.scene().grid_size = 0.5
    _circle(win, (0, 133), 14.5)
    bore = _sketch_of(win, before)
    _dimension(win, (14.5, 133), (35, 160), value=28.55)
    _shot(win, "b6a-bore-sketch")
    _select_at(win, (0, 147.5))         # the bore circle, selected
    _cut_selected(win)
    _window_ok(win, extent="through_all")
    _shot(win, "b6b-bore-cut")
    _views(win, "b7-bracket")
    size = _volume(win)["size"]
    assert size == pytest.approx([84, 70, 156], abs=0.6)
    for z in (122, 128, 133, 140):          # nothing left in the bore
        assert _crossings(win, (0, -100, z), (0, 1, 0)) == [], z
    assert _crossings(win, (0, -100, 150), (0, 1, 0)) == \
        pytest.approx([-17, 17], abs=0.05)
    # ---- 7. later: the boss Ø clicked in 3D, 46 -> 50 — it grows
    cont = next(n for n in win.model.root.walk()
                if any(r["kind"] == "diameter" and r.get("value") == 46
                       for r in sc.rows(n)))
    _edit_in_3d(win, cont, "diameter", 50)
    _shot(win, "b8-boss-changed-to-50")
    assert _volume(win)["size"][2] == pytest.approx(158, abs=0.6)
