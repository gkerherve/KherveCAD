"""Two more exercise parts built with the mouse (2026-10-29, the user:
"normal sketch first, then boss types, extruding, smart dimension,
constraints ... smart dimension with extremity, centers, around
rectangles, origins ... and then constraints with fixed").

  * the S-SECTION BRACKET: a slotted base (180 between centres, R50
    ends, 25 thick, two Ø37 holes) and an upright 100 wide whose boss
    Ø100 / Ø45 stands 130 above the base's centre line, joined by an S
    of R25 inside and R50 outside;
  * the BLOCK: 200 x 100 x 25 with a raised part 40 high, an R50
    trough, two grooves underneath and a Ø25 boss, Ø12 hole, 15 high.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest

from khervecad import sketch_constraints as sc
from test_clevis_by_mouse import (_circle, _click_areas, _frame, _ids,
                                  _lines, _rect, _shot, _sketch, _sketch_of,
                                  _snap, _volume, _window_ok)
from test_drawings_by_mouse import (_crossings, _cut_selected,
                                    _fillet_corners, _select_at, _views)
from test_lever_by_mouse import _at, _extruded_boss, _move, win  # noqa
from test_smart_dimension_by_mouse import _dimension


def _constrain(win, kind, *points):
    """A constraint tool (Fix, Equal, Concentric...): click each point."""
    v2 = win.view2d
    v2.set_tool("con_" + kind)
    for pt in points:
        p = _at(win, *pt)
        _move(v2.viewport(), p)
        QTest.mouseClick(v2.viewport(), Qt.LeftButton, Qt.NoModifier, p)
        QTest.qWait(30)
    v2.set_tool("select")


def _fillet_lines(win, a, b, value):
    """Sketch Fillet where two lines meet: click one, then the other."""
    v2 = win.view2d
    v2.scene().ask_value = lambda tool, measured: str(value)
    v2.set_tool("sk_fillet")
    for pt in (a, b):
        p = _at(win, *pt)
        _move(v2.viewport(), p)
        QTest.mouseClick(v2.viewport(), Qt.LeftButton, Qt.NoModifier, p)
        QTest.qWait(30)
    v2.set_tool("select")


def _kinds(cont):
    return [r["kind"] for r in sc.rows(cont)]


def _select_all(win, points):
    _select_at(win, points[0])
    for pt in points[1:]:
        _select_at(win, pt, Qt.ControlModifier)


def test_the_s_bracket_by_mouse(win):
    # ---- 1. Front plane: the base — a rectangle between two R50 circles
    before = _ids(win)
    _sketch(win, "Front (XZ)")
    _snap(win)
    _frame(win, -160, -80, 320, 160)
    _rect(win, (-90, -50), (90, 50))
    _circle(win, (-90, 0), 50)
    _circle(win, (90, 0), 50)
    base = _sketch_of(win, before)
    # Fix: the left circle's centre stays where it is
    _constrain(win, "fix", (-90, 0))
    # Equal: the two end circles
    _constrain(win, "equal", (-140, 0), (140, 0))
    # Smart Dimension, CENTRE to CENTRE: 180
    asked = _dimension(win, (-140, 0), (140, 0), value=180)
    assert asked and asked[0] == ("distance", pytest.approx(180))
    # Smart Dimension on a circle: Ø100
    _dimension(win, (133.3, 25), (150, 70), value="2 * 50")
    # Smart Dimension around the rectangle: its top edge, 180 long
    _dimension(win, (0, 50), (0, 70), value=180)
    assert {"fix", "equal", "distance", "diameter"} <= set(_kinds(base))
    left = next(c for c in base.children if c.type == "circle")
    assert (left.params["x"], left.params["y"]) == (-90, 0)   # fixed
    _shot(win, "s1a-base-sketch")
    _select_all(win, [(0, -50), (-140, 0), (140, 0)])
    _extruded_boss(win)
    _window_ok(win, distance=25)
    _shot(win, "s1b-base")
    size = _volume(win)["size"]
    assert size[0] == pytest.approx(280, abs=0.6)
    assert size[1] == pytest.approx(25, abs=0.05)
    lo = _volume(win)["min"][1]
    toward = 1 if lo > -1 else -1          # which way the base went
    # ---- 2. Front plane: the two Ø37 holes, concentric with the ends
    before = _ids(win)
    _sketch(win, "Front (XZ)")
    _snap(win)
    win.view2d.scene().grid_size = 0.5
    _frame(win, -160, -80, 320, 160)
    _circle(win, (-90, 0), 18.5)
    _circle(win, (90, 0), 15)
    holes = _sketch_of(win, before)
    _dimension(win, (-71.5, 0), (-60, 30), value=37)
    _constrain(win, "equal", (-71.5, 0), (105, 0))
    right = [c for c in holes.children if c.type == "circle"][1]
    assert right.params["radius"] == pytest.approx(18.5)
    _shot(win, "s2a-holes-sketch")
    _select_all(win, [(-108.5, 0), (108.5, 0)])
    _cut_selected(win)
    _window_ok(win, extent="through_all")
    _shot(win, "s2b-holes")
    assert _crossings(win, (-90, -200, 0), (0, 1, 0)) == []
    assert _crossings(win, (90, -200, 0), (0, 1, 0)) == []
    # ---- 3. Side plane: the S — web and bridge as one outline of lines,
    # its outer corner R50 and inner corner R25 by Sketch Fillet; Fix on
    # the bottom corner, then extruded both ways 100
    before = _ids(win)
    _sketch(win, "Side (YZ)")
    _snap(win)
    _frame(win, -150, -60, 300, 260)
    w = -toward                              # the web's side of the base
    # the outline runs 12.5 into the base, so the inner corner's short
    # side (37.5) has room for its R25
    pts = [(75 * w, 180), (25 * w, 180), (25 * w, 50), (-12.5 * w, 50),
           (-12.5 * w, 0), (75 * w, 0), (75 * w, 180)]
    # the side sketch's x may run against world Y: find out by the base
    _lines(win.view2d, pts)
    web = _sketch_of(win, before)
    _constrain(win, "fix", (-12.5 * w, 0))
    _fillet_lines(win, (75 * w, 90), (50 * w, 0), 50)        # outer R50
    _fillet_lines(win, (25 * w, 100), (5 * w, 50), 25)       # inner R25
    arcs = [n for n in web.children if n.type not in ("line",)]
    assert len(arcs) == 2, [n.type for n in web.children]
    _shot(win, "s3a-s-sketch")
    _extruded_boss(win)
    _click_areas(win, web, [(50 * w, 120), (-6 * w, 25)])
    _window_ok(win, direction="symmetric", distance=100)
    _shot(win, "s3b-s")
    # ---- 4. Front plane: the boss round — the corners outside Ø100 cut
    before = _ids(win)
    _sketch(win, "Front (XZ)")
    _snap(win)
    _frame(win, -100, 60, 200, 140)
    _rect(win, (-50, 130), (50, 180))
    _circle(win, (0, 130), 50)
    top = _sketch_of(win, before)
    _constrain(win, "concentric", (50, 130), (0, 180))
    _shot(win, "s4a-boss-sketch")
    _cut_corners = [(-45, 175), (45, 175)]
    from test_clevis_by_mouse import _leave_sketch_and_cut
    _leave_sketch_and_cut(win)
    _click_areas(win, top, _cut_corners)
    _window_ok(win, extent="through_all")
    _shot(win, "s4b-boss")
    # ---- 5. the Ø45 hole, centre dimensioned to the ORIGIN: 130
    before = _ids(win)
    _sketch(win, "Front (XZ)")
    _snap(win)
    _frame(win, -100, 60, 200, 140)
    _circle(win, (0, 125), 22.5)
    hole = _sketch_of(win, before)
    _dimension(win, (22.5, 125), (0, 0), value=130)        # to the origin
    c = next(n for n in hole.children if n.type == "circle")
    assert c.params["y"] == pytest.approx(130, abs=0.01)
    _dimension(win, (22.5, 130), (40, 160), value=45)
    _shot(win, "s5a-hole-sketch")
    _select_at(win, (0, 152.5))
    _cut_selected(win)
    _window_ok(win, extent="through_all")
    _shot(win, "s5b-hole")
    _views(win, "s6-s-bracket")
    assert _crossings(win, (0, -200, 130), (0, 1, 0)) == []
    assert _crossings(win, (0, -200, 165), (0, 1, 0)) != []
    # no sheet left where the cut's side met the S's side (x = -50)
    for y in (30, 50, 70):
        assert _crossings(win, (-200, y, 172), (1, 0, 0)) == \
            pytest.approx([-27.07, 27.07], abs=0.05)
    assert _crossings(win, (45, -200, 175), (0, 1, 0)) == []   # rounded


def test_the_block_by_mouse(win):
    # ---- 1. Top plane: 200 x 100 from the ORIGIN, Fix on that corner,
    # Smart Dimension on two edges
    before = _ids(win)
    _sketch(win, "Top (XY)")
    _snap(win)
    _frame(win, -20, -20, 240, 140)
    _rect(win, (0, 0), (195, 100))
    base = _sketch_of(win, before)
    _constrain(win, "fix", (0, 0))
    _dimension(win, (0, 50), (-10, 50), value=100)          # first: as is
    _dimension(win, (100, 100), (100, 115), value=200)      # 195 -> 200
    rect = next(n for n in base.children if n.type == "rect")
    assert (rect.params["x"], rect.params["y"]) == (0, 0)
    assert rect.params["width"] == pytest.approx(200, abs=0.01)
    _shot(win, "k1a-base-sketch")
    _extruded_boss(win)
    _window_ok(win, distance=25)
    _shot(win, "k1b-base")
    assert _volume(win)["size"] == pytest.approx([200, 100, 25], abs=0.05)
    # ---- 2. Top plane: the raised half, 40 high
    before = _ids(win)
    _sketch(win, "Top (XY)")
    _snap(win)
    _frame(win, -20, -20, 240, 140)
    _rect(win, (100, 0), (200, 100))
    _shot(win, "k2a-raised-sketch")
    _extruded_boss(win)
    _window_ok(win, distance=40)
    _shot(win, "k2b-raised")
    # ---- 3. Front plane: the R50 trough, its centre 50 above the top
    before = _ids(win)
    _sketch(win, "Front (XZ)")
    _snap(win)
    _frame(win, 80, 0, 140, 140)
    _circle(win, (150, 75), 50)
    trough = _sketch_of(win, before)
    _dimension(win, (200, 75), (210, 110), value=100)       # Ø100 = R50
    _shot(win, "k3a-trough-sketch")
    _select_at(win, (150, 125))
    _cut_selected(win)
    _window_ok(win, extent="through_all")
    _shot(win, "k3b-trough")
    assert _crossings(win, (150, 50, -10), (0, 0, 1)) == \
        pytest.approx([0, 25], abs=0.05)
    assert _crossings(win, (195, 50, -10), (0, 0, 1)) == \
        pytest.approx([0, 40], abs=0.05)
    # ---- 4. Front plane: two grooves under it, 10 deep
    before = _ids(win)
    _sketch(win, "Front (XZ)")
    _snap(win)
    _frame(win, 0, -20, 220, 60)
    _rect(win, (50, 0), (87.5, 10))
    _rect(win, (125, 0), (150, 10))
    _shot(win, "k4a-grooves-sketch")
    _select_all(win, [(70, 10), (137.5, 10)])
    _cut_selected(win)
    _window_ok(win, extent="through_all")
    _shot(win, "k4b-grooves")
    assert _crossings(win, (70, 50, -10), (0, 0, 1)) == \
        pytest.approx([10, 25], abs=0.05)
    # ---- 5. Top plane: the Ø25 boss 15 above the top, Smart Dimension
    # from its CENTRE to the base's left EDGE (40) and the ORIGIN
    before = _ids(win)
    _sketch(win, "Top (XY)")
    _snap(win)
    _frame(win, -20, -20, 240, 140)
    _circle(win, (37.5, 50), 12.5)
    boss = _sketch_of(win, before)
    asked = _dimension(win, (50, 50), (0, 25), value=40)    # to the edge
    c = next(n for n in boss.children if n.type == "circle")
    assert c.params["x"] == pytest.approx(40, abs=0.01), (asked, win.statusBar().currentMessage())
    _shot(win, "k5a-boss-sketch")
    _extruded_boss(win)
    _window_ok(win, distance=40)
    _shot(win, "k5b-boss")
    # ---- 6. the Ø12 hole through it
    before = _ids(win)
    _sketch(win, "Top (XY)")
    _snap(win)
    win.view2d.scene().grid_size = 0.5
    _frame(win, 0, 20, 80, 60)
    _circle(win, (40, 50), 6)
    _shot(win, "k6a-hole-sketch")
    _select_at(win, (46, 50))
    _cut_selected(win)
    _window_ok(win, extent="through_all")
    _shot(win, "k6b-hole")
    _views(win, "k7-block")
    assert _crossings(win, (40, 50, -10), (0, 0, 1)) == []
    assert _crossings(win, (40, 60, -10), (0, 0, 1)) == \
        pytest.approx([0, 40], abs=0.05)
