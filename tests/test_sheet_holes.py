"""Holes in sheet metal (2026-11-15, Exercise 135: the Ø55 opening of the
base flange and the Ø6.5 holes of the flange). A hole is cut through its
panel — in the folded part AND in the flat pattern — and the ribbon's
Simple Hole takes it from a click on the sheet.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QAction

from khervecad import csg, mesh, sheet_body as sb
from khervecad import sheet_metal_ops as ops
from test_lever_by_mouse import win, _button_for, _move, _wait  # noqa: F401

pytestmark = pytest.mark.skipif(not csg.available(), reason="needs Manifold")


def _volume(tris):
    return abs(sum(sb._dot(a, sb._cross(b, c)) for a, b, c in tris)) / 6


def _plate(**extra):
    p = dict(sb._DEFAULTS, outline=[[0, 0], [100, 0], [100, 60], [0, 60]],
             thickness=2.0, radius=2.0, k_factor=0.44)
    p.update(extra)
    return p


def test_a_hole_is_cut_from_the_folded_part_and_the_flat_pattern():
    plain = sb.build(_plate(flanges=[[0, 0, 20, 90]]))
    holed = sb.build(_plate(flanges=[[0, 0, 20, 90]],
                            pholes=[[0, 50, 30, 20]]))
    assert not holed.errors, holed.errors
    v0, v1 = (_volume(sb.folded_tris(b)) for b in (plain, holed))
    assert v0 - v1 == pytest.approx(math.pi * 100 * 2.0, rel=0.02)
    f0, f1 = sb.flat_pattern(plain), sb.flat_pattern(holed)
    assert len(f1["outlines"]) == len(f0["outlines"]) + 1     # the hole
    # the blank is still the same size
    assert f1["width"] == pytest.approx(f0["width"])


def test_a_hole_in_a_flange_uses_the_flanges_own_frame():
    body = sb.build(_plate(flanges=[[0, 0, 30, 90]],
                           pholes=[[1, -50, 10, 6.5]]))
    assert not body.errors, body.errors
    assert len(body.panels[1].holes) == 1
    # lies on the flange wall: one hole's worth of volume gone
    plain = sb.build(_plate(flanges=[[0, 0, 30, 90]]))
    assert _volume(sb.folded_tris(plain)) - _volume(
        sb.folded_tris(body)) == pytest.approx(math.pi * 3.25 ** 2 * 2.0,
                                               rel=0.03)


def test_a_hole_off_its_panel_is_an_error_not_a_silent_nothing():
    body = sb.build(_plate(pholes=[[0, 500, 500, 5]]))
    assert any("off panel" in e for e in body.errors)
    assert sb.build(_plate(pholes=[[3, 5, 5, 5]])).errors


def test_edge_position_dimensions_a_hole_from_an_edge(win):
    body = ops.insert_base(win.model, [[0, 0], [80, 0], [80, 60], [0, 60]],
                           thickness=1.5, radius=1.5)
    ops.add_flange(win.model, body, 0, 0, 30)
    # 10 from the free edge (edge 2), 10 from the side
    u, v = ops.edge_position(win.model, body, 1, 2, 10, 10)
    ops.add_panel_hole(win.model, body, 1, u, v, 6.5)
    assert not ops.describe(win.model, body)["errors"]
    pan = sb.build(body.params).panels[1]
    (hx, hy), = [(sum(p[0] for p in h) / len(h), sum(p[1] for p in h) /
                  len(h)) for h in pan.holes]
    xs = [p[0] for p in pan.poly]
    ys = [p[1] for p in pan.poly]
    assert hy == pytest.approx(max(ys) - 10, abs=0.01)
    assert min(abs(hx - min(xs)), abs(hx - max(xs))) == pytest.approx(
        10, abs=0.01)


def test_the_simple_hole_button_cuts_where_the_sheet_is_clicked(win):
    from khervecad import sheet_metal_ui as ui
    win.model.clear()
    acts = {a.data(): a for a in win.findChildren(QAction)}
    body = ops.insert_base(win.model, [[0, 0], [100, 0], [100, 60],
                                       [0, 60]], thickness=2.0)
    win.builder.active_tree().select_nodes([body])
    QTest.qWait(100)
    ui.ANSWERS["sm_phole_form"] = {"diameter": 8.0}
    try:
        act = next(a for a in win.findChildren(QAction)
                   if a.data() == "sm_phole")
        try:
            QTest.mouseClick(_button_for(win, act), Qt.LeftButton)
        except StopIteration:
            act.trigger()
        v3 = win.view3d
        assert _wait(lambda: v3._pick_cb is not None), \
            "Simple Hole asks for no click"
        QTest.mouseClick(v3.nav_bar.buttons["fit"], Qt.LeftButton)
        QTest.qWait(600)
        q = v3._project(*v3._camera(), (30.0, 20.0, 2.0))
        p = QPoint(int(round(q[0])), int(round(q[1])))
        _move(v3, p)
        QTest.mouseClick(v3, Qt.LeftButton, Qt.NoModifier, p)
        QTest.qWait(100)
    finally:
        ui.ANSWERS.clear()
    rows = body.params.get("pholes")
    assert rows and len(rows) == 1, rows
    panel, u, v, d = rows[0]
    assert (panel, d) == (0, 8.0)
    assert u == pytest.approx(30, abs=1.5) and v == pytest.approx(
        20, abs=1.5), rows
    assert not ops.describe(win.model, body)["errors"]
    win._dirty = False


# ================================================================ corners
def test_a_broken_corner_is_a_tangent_round_and_shows_in_the_blank():
    plain = sb.build(_plate(flanges=[[0, 0, 30, 90]]))
    # the flange's two free corners (its far edge is edge 2)
    far = plain.panels[1].edge(2)
    (ax, ay), (bx, by), _ln = far
    rounded = sb.build(_plate(flanges=[[0, 0, 30, 90]], corners=[
        [1, ax, ay, 10, 0], [1, bx, by, 10, 0]]))
    assert not rounded.errors, rounded.errors
    f0, f1 = sb.flat_pattern(plain), sb.flat_pattern(rounded)

    def area(pat):
        return sum(sb._area2(lp) for lp in pat["outlines"])
    assert area(f0) - area(f1) == pytest.approx(
        2 * (1 - math.pi / 4) * 10 ** 2, rel=0.02)
    # the far edge keeps its tag on what is left of it
    assert rounded.panels[1].edge(2)[2] == pytest.approx(
        far[2] - 20, abs=0.05)


def test_a_corner_too_big_for_its_sides_is_refused(win):
    body = ops.insert_base(win.model, [[0, 0], [30, 0], [30, 30], [0, 30]],
                           thickness=1.5, radius=1.5)
    with pytest.raises(ValueError):
        ops.add_corner(win.model, body, 0, 0, 0, 40)
    assert not body.params.get("corners")


def test_the_break_corner_button_rounds_the_clicked_corner(win):
    from khervecad import sheet_metal_ui as ui
    win.model.clear()
    body = ops.insert_base(win.model, [[0, 0], [100, 0], [100, 60],
                                       [0, 60]], thickness=2.0)
    win.builder.active_tree().select_nodes([body])
    QTest.qWait(100)
    ui.ANSWERS["sm_corner_form"] = {"size": 10.0}
    try:
        act = next(a for a in win.findChildren(QAction)
                   if a.data() == "sm_corner")
        try:
            QTest.mouseClick(_button_for(win, act), Qt.LeftButton)
        except StopIteration:
            act.trigger()
        v3 = win.view3d
        assert _wait(lambda: v3._pick_cb is not None), \
            "Break Corner asks for no click"
        QTest.mouseClick(v3.nav_bar.buttons["fit"], Qt.LeftButton)
        QTest.qWait(600)
        q = v3._project(*v3._camera(), (96.0, 56.0, 2.0))   # near (100, 60)
        p = QPoint(int(round(q[0])), int(round(q[1])))
        _move(v3, p)
        QTest.mouseClick(v3, Qt.LeftButton, Qt.NoModifier, p)
        QTest.qWait(100)
    finally:
        ui.ANSWERS.clear()
    rows = body.params.get("corners")
    assert rows and rows[0][0] == 0 and rows[0][3] == 10.0, rows
    built = sb.build(body.params)
    assert not built.errors and len(built.panels[0].poly) > 5
    win._dirty = False


# ================================================================== ears
def _arch(win, step=10):
    """Exercise 135's plate: 80 wide, a R40 arch over 60 below the
    centre, t 1.5, R 1.5, K 0.5, a 30 mm flange on its bottom edge."""
    pts = [[-40, -60], [40, -60], [40, 0]] + [
        [round(40 * math.cos(math.radians(a)), 4),
         round(40 * math.sin(math.radians(a)), 4)]
        for a in range(step, 180, step)] + [[-40, 0]]
    body = ops.insert_base(win.model, pts, thickness=1.5, radius=1.5)
    win.model.set_param(body, "k_factor", 0.5)
    ops.add_flange(win.model, body, 0, 0, 30)
    return body


def test_the_arch_plate_unfolds_to_the_videos_blank(win):
    body = _arch(win)
    d = ops.describe(win.model, body)
    assert not d["errors"]
    assert d["flat_size"] == [80.0, pytest.approx(127.53, abs=0.01)]


def test_an_ear_is_a_round_ended_flange_with_its_hole(win):
    body = _arch(win)
    # the plate's right side: edge 1, 57 mm long after the set-back
    pan0 = sb.build(body.params).panels[0]
    assert pan0.edge(1)[2] == pytest.approx(57.0, abs=0.01)
    idx = ops.add_ear(win.model, body, 0, 1, center=22.5, width=15,
                      height=22.5, hole=6.5)
    d = ops.describe(win.model, body)
    assert not d["errors"], d["errors"]
    built = sb.build(body.params)
    ear = built.panels[idx]
    leg = 22.5 - 3.0
    expected = 15 * (leg - 7.5) + math.pi * 7.5 ** 2 / 2
    assert abs(sb._area2(ear.poly)) == pytest.approx(expected, rel=0.01)
    assert len(ear.holes) == 1
    (hx, hy) = (sum(p[0] for p in ear.holes[0]) / len(ear.holes[0]),
                sum(p[1] for p in ear.holes[0]) / len(ear.holes[0]))
    assert hy == pytest.approx(leg - 7.5, abs=0.01)
    # the ear stands 90 degrees off the plate: solid, with its hole cut
    plain = sb.build(dict(body.params, pholes=[]))
    assert _volume(sb.folded_tris(plain)) - _volume(
        sb.folded_tris(built)) == pytest.approx(
            math.pi * 3.25 ** 2 * 1.5, rel=0.03)
    # one bend more in the table, the ear on the blank
    assert d["bends"] == 2
    assert d["flat_size"][0] > 80.0


def test_an_ear_that_runs_off_its_edge_is_refused(win):
    body = _arch(win)
    with pytest.raises(ValueError):
        ops.add_ear(win.model, body, 0, 1, center=3, width=15, height=22)
    assert len(body.params["flanges"]) == 1


def test_the_edge_flange_button_makes_an_ear(win):
    from khervecad import sheet_metal_ui as ui
    win.model.clear()
    body = _arch(win)
    win.builder.active_tree().select_nodes([body])
    QTest.qWait(100)
    ui.ANSWERS.update({
        "sm_flange": {"height": 22.5, "angle": 90.0, "ear": True,
                      "ear_center": 22.5, "ear_width": 15.0,
                      "ear_hole": 6.5},
        "sm_flange_edge": (0, 1)})
    try:
        act = next(a for a in win.findChildren(QAction)
                   if a.data() == "sm_flange")
        act.trigger()
    finally:
        ui.ANSWERS.clear()
    rows = body.params["flanges"]
    assert len(rows) == 2 and rows[1][7] == 1, rows
    assert body.params["pholes"] and body.params["pholes"][0][0] == 2
    assert not ops.describe(win.model, body)["errors"]
    win._dirty = False


# ================================================================== tabs
def _arch_with_opening(win):
    body = _arch(win)
    ops.add_panel_hole(win.model, body, 0, 0.0, 0.0, 55.0)       # the opening
    return body


def test_a_tab_stands_in_the_opening_with_its_hole(win):
    body = _arch_with_opening(win)
    before = _volume(sb.folded_tris(sb.build(body.params)))
    # a tab from the plate at the top into the opening: its round end at
    # R15 (the Ø30 hole circle), 10 wide, Ø5.5 hole
    ops.add_tab(win.model, body, 0, 0.0, 15.0, 10, 20, 90, hole=5.5)
    d = ops.describe(win.model, body)
    assert not d["errors"], d["errors"]
    built = sb.build(body.params)
    pan = built.panels[0]
    region = sb.panel_region(pan)
    # in the opening: the tab is there, its hole is not, the rest of the
    # opening is still open
    from khervecad import csg
    assert csg._m.CrossSection  # noqa
    polys = region.to_polygons()
    assert any(sb._inside([lp], 0.0, 22.0) for lp in polys)       # tab body
    inside_hole = sb._inside(polys, 0.0, 15.0)
    assert not inside_hole                                        # hole
    assert not sb._inside(polys, 0.0, -10.0)                      # opening
    # the volume grew by about the tab's part inside the opening
    after = _volume(sb.folded_tris(built))
    tab_in_opening = (10 * (27.5 - 15) + math.pi * 25 / 2) \
        - math.pi * 2.75 ** 2
    assert after - before == pytest.approx(tab_in_opening * 1.5, rel=0.08)
    # and it shows in the blank: one more bump in its outline
    f = sb.flat_pattern(built)
    assert f["width"] == pytest.approx(80.0)


def test_a_tab_that_misses_the_sheet_is_an_error(win):
    body = _arch(win)
    with pytest.raises(ValueError):
        ops.add_tab(win.model, body, 0, 500.0, 500.0, 10, 5, 0)
    assert not body.params.get("tabs")


def test_the_tab_button_adds_a_tab(win):
    from khervecad import sheet_metal_ui as ui
    win.model.clear()
    body = _arch_with_opening(win)
    win.builder.active_tree().select_nodes([body])
    QTest.qWait(100)
    ui.ANSWERS["sm_tab_form"] = {"u": 0.0, "v": 15.0, "width": 10.0,
                                 "length": 20.0, "angle": 90.0,
                                 "hole": 5.5}
    try:
        next(a for a in win.findChildren(QAction)
             if a.data() == "sm_tab").trigger()
    finally:
        ui.ANSWERS.clear()
    assert len(body.params["tabs"]) == 1
    assert not ops.describe(win.model, body)["errors"]
    win._dirty = False


# =================================================================== jogs
def _arch_with_tab(win):
    body = _arch_with_opening(win)
    ops.add_tab(win.model, body, 0, 0.0, 15.0, 10, 20, 90, hole=5.5)
    return body


def _flat_area(body):
    return sum(sb._area2(lp) for lp in sb.flat_pattern(body)["outlines"])


def test_a_jog_steps_the_tab_out_of_the_plate_by_its_offset(win):
    body = _arch_with_tab(win)
    flat0 = _flat_area(sb.build(body.params))
    ops.add_tab_jog(win.model, body, 0, (-8, 22), (8, 22), offset=10,
                angle=90, radius=1.5)
    d = ops.describe(win.model, body)
    assert not d["errors"], d["errors"]
    built = sb.build(body.params)
    # the plate, the flange, then the jog's leg and the moved end
    assert len(built.panels) == 4 and len(built.bends) == 3
    last = built.panels[3]
    assert last.frame.o[2] - built.panels[0].frame.o[2] == pytest.approx(
        10.0, abs=1e-6)                                  # stepped 10 up
    assert tuple(round(c, 6) for c in last.frame.n) == (0.0, 0.0, 1.0)
    # the moved end kept its hole and its place seen square on: its round
    # end is still centred on (0, 15) in x, y
    assert len(last.holes) == 1
    hx = sum(q[0] for q in last.holes[0]) / len(last.holes[0])
    hy = sum(q[1] for q in last.holes[0]) / len(last.holes[0])
    wx, wy, wz = last.frame.at((hx, hy))
    assert (wx, wy) == (pytest.approx(0.0, abs=1e-6),
                        pytest.approx(15.0, abs=1e-6))
    # the blank grows by the bends: 2 allowances + the leg, less the
    # band the jog takes out of the plane (10 wide)
    a = math.pi / 2 * (1.5 + 0.5 * 1.5)
    leg, reach = sb.jog_geometry(10, 90, 1.5, 1.5)
    assert leg == pytest.approx(5.5)
    assert _flat_area(built) - flat0 == pytest.approx(
        10 * (2 * a + leg - reach), rel=0.03)
    # a closed solid still, the step in it
    assert _volume(sb.folded_tris(built)) > 0


def test_a_jog_must_cross_something_that_can_move(win):
    body = _arch(win)
    with pytest.raises(ValueError):
        ops.add_tab_jog(win.model, body, 0, (-8, 20), (8, 20), 10, 90, 1.5)
    assert not body.params.get("tabjogs")


def test_a_clicked_jog_line_is_stretched_across_its_tab(win):
    body = _arch_with_tab(win)
    p1, p2 = ops.jog_span(win.model, body, 0, (-2, 22), (2, 22))
    assert p1[0] == pytest.approx(-5.5, abs=0.05)
    assert p2[0] == pytest.approx(5.5, abs=0.05)     # 5 + 0.5 margin
    assert p1[1] == pytest.approx(22.0, abs=1e-6)


def test_the_jog_button_takes_two_clicks_on_the_tab(win):
    from khervecad import sheet_metal_ui as ui
    win.model.clear()
    body = _arch_with_tab(win)
    win.builder.active_tree().select_nodes([body])
    QTest.qWait(100)
    ui.ANSWERS["sm_tabjog_form"] = {"offset": 10.0, "angle": 90.0,
                                 "radius": 1.5}
    try:
        act = next(a for a in win.findChildren(QAction)
                   if a.data() == "sm_tabjog")
        try:
            QTest.mouseClick(_button_for(win, act), Qt.LeftButton)
        except StopIteration:
            act.trigger()
        v3 = win.view3d
        assert _wait(lambda: v3._pick_cb is not None), "Jog asks no click"
        QTest.mouseClick(v3.nav_bar.buttons["fit"], Qt.LeftButton)
        QTest.qWait(600)
        for x in (-3.0, 3.0):
            assert _wait(lambda: v3._pick_cb is not None)
            q = v3._project(*v3._camera(), (x, 22.0, 1.5))
            p = QPoint(int(round(q[0])), int(round(q[1])))
            _move(v3, p)
            QTest.mouseClick(v3, Qt.LeftButton, Qt.NoModifier, p)
            QTest.qWait(150)
    finally:
        ui.ANSWERS.clear()
    rows = body.params.get("tabjogs")
    assert rows and len(rows) == 1, rows
    row = rows[0]
    assert row[6] == 90.0 and row[5] == 10.0
    assert row[2] == pytest.approx(22, abs=1.0) \
        and row[4] == pytest.approx(22, abs=1.0)
    assert abs(row[1]) > 5.0 and abs(row[3]) > 5.0         # stretched
    assert not ops.describe(win.model, body)["errors"]
    win._dirty = False


# ================================================================ gussets
def test_a_gusset_is_a_rib_in_the_inside_of_the_bend(win):
    body = _arch(win)
    plain = sb.build(body.params)
    v0 = _volume(sb.folded_tris(plain))
    f0 = sb.flat_pattern(plain)
    ops.add_gusset(win.model, body, 1, offset=10, d1=10, d2=10, width=7.5,
                   draft=20)
    d = ops.describe(win.model, body)
    assert not d["errors"], d["errors"]
    built = sb.build(body.params)
    delta = _volume(sb.folded_tris(built)) - v0
    assert 100 < delta < 450, delta         # a 10 x 10 wedge, ~6 wide
    # the blank does not change (the rib is stamped, not unfolded)
    f1 = sb.flat_pattern(built)
    assert (f1["width"], f1["height"]) == (f0["width"], f0["height"])
    # the rib stands in the corner: inside the 80 x 30 outline of the
    # flange, 10 mm from its end
    pts = sb.gusset_points(built.bends[0], built.t, 10, 10, 10, 7.5, 20)
    xs = [p[0] for p in pts]
    assert min(xs) > -40 and max(xs) < 40
    assert (min(xs) + max(xs)) / 2 == pytest.approx(-30.0, abs=0.01)
    # ... and on the inside of the corner: over the plate (z above its
    # 1.5 top) and in front of the flange's inner face (y -58.5)
    assert all(p[1] > -58.6 and p[2] > 1.4 for p in pts)
    assert max(p[2] for p in pts) == pytest.approx(11.5, abs=0.01)
    assert max(p[1] for p in pts) == pytest.approx(-48.5, abs=0.01)


def test_a_gusset_off_its_bend_or_on_no_bend_is_refused(win):
    body = _arch(win)
    with pytest.raises(ValueError):
        ops.add_gusset(win.model, body, 5, 10)
    with pytest.raises(ValueError):
        ops.add_gusset(win.model, body, 1, 500)
    assert not body.params.get("gussets")


def test_the_gusset_button_takes_a_click_near_the_bend(win):
    from khervecad import sheet_metal_ui as ui
    win.model.clear()
    body = _arch(win)
    win.builder.active_tree().select_nodes([body])
    QTest.qWait(100)
    ui.ANSWERS["sm_gusset_form"] = {"offset": 10.0, "d1": 10.0,
                                    "d2": 10.0, "width": 7.5,
                                    "draft": 20.0}
    try:
        act = next(a for a in win.findChildren(QAction)
                   if a.data() == "sm_gusset")
        try:
            QTest.mouseClick(_button_for(win, act), Qt.LeftButton)
        except StopIteration:
            act.trigger()
        v3 = win.view3d
        assert _wait(lambda: v3._pick_cb is not None), \
            "Gusset asks for no click"
        QTest.mouseClick(v3.nav_bar.buttons["fit"], Qt.LeftButton)
        QTest.qWait(600)
        q = v3._project(*v3._camera(), (0.0, -50.0, 1.5))
        p = QPoint(int(round(q[0])), int(round(q[1])))
        _move(v3, p)
        QTest.mouseClick(v3, Qt.LeftButton, Qt.NoModifier, p)
        QTest.qWait(150)
    finally:
        ui.ANSWERS.clear()
    rows = body.params.get("gussets")
    assert rows and rows[0][0] == 0 and rows[0][2:5] == [10.0, 10.0, 7.5]
    assert not ops.describe(win.model, body)["errors"]
    win._dirty = False


# ============================================================== patterns
def _trigger(win, key):
    act = next(a for a in win.findChildren(QAction) if a.data() == key)
    act.trigger()


def test_mirror_copies_an_ear_and_its_hole_to_the_other_side(win):
    from khervecad import sheet_metal_patterns as pat
    body = _arch(win, step=5)           # (the 5 degree facets of an arc)
    ops.add_ear(win.model, body, 0, 1, center=22.5, width=15, height=22.5,
                hole=6.5)
    ops.add_panel_hole(win.model, body, 1, -30.0, 12.0, 6.5)     # a flange hole
    feats = pat.features(win.model, body)
    assert [f["label"] for f in feats] == ["Hole 1", "Hole 2", "Ear 1"], \
        feats
    items = [(f["kind"], f["index"]) for f in feats]
    pat.mirror(win.model, body, items, "x", 0.0)
    d = ops.describe(win.model, body)
    assert not d["errors"], d["errors"]
    built = sb.build(body.params)
    # two ears now, the second on the plate's left side, a mirror image
    ears = [i for i, r in enumerate(body.params["flanges"])
            if len(r) > 7 and r[7] == 1]
    assert len(ears) == 2
    p1, p2 = built.panels[1 + ears[0]], built.panels[1 + ears[1]]
    assert abs(sb._area2(p1.poly)) == pytest.approx(abs(sb._area2(p2.poly)),
                                                    rel=1e-3)
    # ... the same stretch of the side, left against right (a plate
    # with an arched top has facets that look like its edge: the ear
    # must stand on the straight one)
    ys1 = [p1.frame.at(q)[1] for q in p1.poly]
    ys2 = [p2.frame.at(q)[1] for q in p2.poly]
    assert (min(ys2), max(ys2)) == (pytest.approx(min(ys1), abs=0.02),
                                    pytest.approx(max(ys1), abs=0.02))
    h1 = p1.frame.at(tuple(sum(c) / len(p1.holes[0]) for c in
                           zip(*p1.holes[0])))
    h2 = p2.frame.at(tuple(sum(c) / len(p2.holes[0]) for c in
                           zip(*p2.holes[0])))
    assert (h2[0], h2[1], h2[2]) == (pytest.approx(-h1[0], abs=0.02),
                                     pytest.approx(h1[1], abs=0.02),
                                     pytest.approx(h1[2], abs=0.02))
    # the flange hole came with it (the flange's u runs back along its
    # edge from x = -40: u -30 is x -10, u -50 is x +10)
    holes = [r for r in body.params["pholes"] if r[0] == 1]
    assert sorted(h[1] for h in holes) == pytest.approx(
        [-50.0, -30.0], abs=0.05), holes


def test_circular_pattern_turns_a_tab_and_its_jog_four_times(win):
    from khervecad import sheet_metal_patterns as pat
    body = _arch_with_tab(win)
    ops.add_tab_jog(win.model, body, 0, (-8, 22), (8, 22), 10, 90, 1.5)
    n = pat.circular(win.model, body, "tabs", 0, 4)
    n += pat.circular(win.model, body, "tabjogs", 0, 4)
    assert n == 6
    d = ops.describe(win.model, body)
    assert not d["errors"], d["errors"]
    tabs = body.params["tabs"]
    assert len(tabs) == 4 and sorted(round(t[5]) % 360 for t in tabs) == \
        [0, 90, 180, 270]
    # each tab's round end stays on the Ø30 circle
    for t in tabs:
        assert math.hypot(t[1], t[2]) == pytest.approx(15.0, abs=1e-3)
    built = sb.build(body.params)
    # plate, flange + 4 jogs of (leg + moved end)
    assert len(built.panels) == 2 + 8
    zs = sorted(round(p.frame.o[2], 3) for p in built.panels[2:]
                if abs(p.frame.n[2] - 1) < 1e-6)
    assert zs == [10.0] * 4


def test_linear_pattern_steps_a_gusset_along_its_bend(win):
    from khervecad import sheet_metal_patterns as pat
    body = _arch(win)
    ops.add_gusset(win.model, body, 1, offset=10)
    assert pat.linear(win.model, body, "gussets", 0, 3, 30.0) == 2
    assert [r[1] for r in body.params["gussets"]] == [10.0, 40.0, 70.0]
    assert not ops.describe(win.model, body)["errors"]
    with pytest.raises(ValueError):
        pat.linear(win.model, body, "gussets", 0, 9, 30.0)
    with pytest.raises(ValueError):
        pat.linear(win.model, body, "gussets", 0, 1, 30.0)


def test_the_pattern_buttons_take_the_features_ticked_in_the_list(win):
    from khervecad import sheet_metal_ui as ui
    win.model.clear()
    body = _arch(win)
    ops.add_gusset(win.model, body, 1, offset=10)
    win.builder.active_tree().select_nodes([body])
    QTest.qWait(100)
    ui.ANSWERS["sm_lpattern_form"] = {"features": [("gussets", 0)],
                                      "count": 3, "dx": 30.0, "dy": 0.0}
    try:
        _trigger(win, "sm_lpattern")
    finally:
        ui.ANSWERS.clear()
    assert len(body.params["gussets"]) == 3
    ui.ANSWERS["sm_mirror_form"] = {"features": [("gussets", 0)],
                                    "at": 0.0}
    try:
        _trigger(win, "sm_mirror")
    finally:
        ui.ANSWERS.clear()
    assert not ops.describe(win.model, body)["errors"]
    win._dirty = False


def test_an_ear_notches_the_plate_instead_of_dragging_its_outline(win):
    """The plate's side runs on into the tangent facets of the arch: an
    ear on part of that side must cost the plate only a notch as wide as
    the ear (the whole side moved inward met the next facet's line at
    y = 68, far above the arch)."""
    body = _arch(win, step=5)
    before = sb.build(body.params).panels[0]
    area0 = abs(sb._area2(before.poly))
    ops.add_ear(win.model, body, 0, 1, center=22.5, width=15, height=22.5)
    built = sb.build(body.params)
    assert not built.errors, built.errors
    pan = built.panels[0]
    assert max(q[1] for q in pan.poly) == pytest.approx(40.0, abs=0.01)
    region = sb.panel_region(pan)
    # the notch: 15 wide, the bend's set-back (r + t = 3) deep
    assert region.area() == pytest.approx(area0 - 15 * 3.0, abs=0.01)
    assert pan.edge(1)[2] == pytest.approx(57.0, abs=0.01)   # not trimmed


def test_the_arch_plate_button_makes_the_exercises_back_plate(win):
    from khervecad import sheet_metal_ui as ui
    win.model.clear()
    ui.ANSWERS["sm_arch_form"] = {"width": 80.0, "below": 60.0,
                                  "thickness": 1.5, "radius": 1.5,
                                  "k_factor": 0.5}
    try:
        _trigger(win, "sm_arch")
    finally:
        ui.ANSWERS.clear()
    body = next(n for n in win.model.root.walk() if n.type == sb.KIND)
    ops.add_flange(win.model, body, 0, 0, 30)
    d = ops.describe(win.model, body)
    assert not d["errors"], d["errors"]
    assert d["flat_size"] == [80.0, pytest.approx(127.53, abs=0.01)]
    win._dirty = False
