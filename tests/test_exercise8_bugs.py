"""Bugs found while filming Exercise 8 (clevis), 2026-11-15 — each one
driven with real mouse events.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QAbstractButton

from khervecad import analysis, choice_preview, mesh, sketch_mode
from test_lever_by_mouse import (_button_for, _extruded_boss, _wait,  # noqa
                                 win)
from test_clevis_by_mouse import (_circle, _click_areas, _frame,  # noqa
                                  _sketch_of, _tab, _window_ok, _ids)


@pytest.fixture(autouse=True)
def _plane_rows():
    """The tests' default hides the Origin / plane rows; these use them."""
    from PyQt5.QtCore import QSettings
    QSettings("Kherve", "KherveCAD").setValue("tree/planes", True)
    yield


def _new_object(win):
    win.builder.worktree.new_object()          # the tab's New Object
    QTest.qWait(150)


def _row_sketch(win, row):
    """Sketch tab, a Front / Top / Right Plane tree row selected, Sketch."""
    _tab(win, "Sketch")
    tree = win.builder.active_tree()
    item = next(tree.topLevelItem(i) for i in range(tree.topLevelItemCount())
                if tree.topLevelItem(i).text(0) == row)
    QTest.mouseClick(tree.viewport(), Qt.LeftButton, Qt.NoModifier,
                     tree.visualItemRect(item).center())
    QTest.qWait(80)
    QTest.mouseClick(_button_for(win, sketch_mode.create_action(win)),
                     Qt.LeftButton)
    assert _wait(lambda: sketch_mode.sketching(win))
    QTest.qWait(500)


def _top_of(win, node):
    while node.parent is not None and node.parent is not win.model.root:
        node = node.parent
    return node


def _volume(win):
    return analysis.mass_properties(mesh.tessellate(win.model.root))


# ------------------------------------------------ 2. Front Plane row in Main
def test_front_plane_row_in_main_makes_a_part_that_extrudes(win):
    """A sketch from the Front Plane row with no Object open left a
    "Front sketch" rotate at the Main level: Extruded Boss then found
    no regions. It becomes a part like a Top-plane sketch does."""
    before = _ids(win)
    _row_sketch(win, "Front Plane")
    _frame(win, -45, -8, 90, 100)
    _circle(win, (0, 40), 24)
    _circle(win, (0, 40), 11)
    sk = _sketch_of(win, before)
    assert sk.type == "rotate"
    assert _top_of(win, sk).type == "component", \
        "the sketch stayed loose at the Main level"
    assert win.builder.isolated_component() is not None
    _extruded_boss(win)
    sketches, items = choice_preview.region_items(win)
    assert items, "Extruded Boss finds no regions"
    _click_areas(win, sk, [(18, 40)])
    _window_ok(win, direction="symmetric", distance=40)
    v = _volume(win)
    assert v["size"][1] == pytest.approx(40, abs=0.1)
    assert v["volume"] > 0


# ------------------------------------------------ the clevis, up to its arms
def _clevis_boss(win):
    """An Object holding Boss-Extrude1 of Exercise 8 (the fork, 40 thick,
    Front plane), plus the Right-plane sketch of the arms and the O10 hole
    drawn but not cut. Returns the Right sketch."""
    import math
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(win)
    _new_object(win)

    def call(tool, **a):
        r = ex.execute(tool, a)
        QTest.qWait(30)
        assert not (isinstance(r, dict) and "error" in r), r
        return r

    def sketch(normal):
        return call("reference_geometry", action="sketch", origin=[0, 0, 0],
                    normal=normal)["sketch_id"]

    def add(sk, typ, **p):
        return call("add_node", type=typ, parent_id=sk, params=p)["created"]
    th = math.radians(7.0)
    xb = (24 - 40 * math.sin(th)) / math.cos(th)
    tx, ty = 24 * math.cos(th), 40 - 24 * math.sin(th)
    s1 = sketch([0, -1, 0])
    cl = add(s1, "line", x1=0, y1=0, x2=0, y2=40, width=0.2, modifier="%")
    add(s1, "circle", x=0, y=40, radius=24)
    add(s1, "circle", x=0, y=40, radius=11)
    a = add(s1, "line", x1=11, y1=40, x2=11, y2=0, width=0.2)
    b = add(s1, "line", x1=11, y1=0, x2=xb, y2=0, width=0.2)
    c = add(s1, "line", x1=xb, y1=0, x2=tx, y2=ty, width=0.2)
    call("sketch_modify", action="mirror", node_ids=[a, b, c], mirror_line=cl)
    call("sketch_feature", node_id=s1, depth=40, mid_plane=True,
         regions=[[0, 58], [-15, 5], [15, 5]])
    s2 = sketch([1, 0, 0])
    t2 = math.radians(2.0)
    p = (10 * math.cos(t2), 10 + 10 * math.sin(t2))
    xt = p[0] + (90 - p[1]) * math.tan(t2)
    add(s2, "line", x1=p[0], y1=p[1], x2=-p[0], y2=p[1], width=0.2,
        bulge=-math.tan((math.pi + 2 * t2) / 4))
    add(s2, "line", x1=-p[0], y1=p[1], x2=-xt, y2=90, width=0.2)
    add(s2, "line", x1=-xt, y1=90, x2=xt, y2=90, width=0.2)
    add(s2, "line", x1=xt, y1=90, x2=p[0], y2=p[1], width=0.2)
    add(s2, "circle", x=0, y=10, radius=5)
    QTest.qWait(200)
    return next(n for n in win.model.root.walk() if n.id == s2)


def _cut_on(win, view):
    """Features tab, Extruded Cut with nothing selected, the 3D view
    turned to *view* and fitted."""
    from khervecad import cut_feature
    _tab(win, "Features")
    QTest.qWait(300)
    win.builder.active_tree().clearSelection()
    act = next(a for a in cut_feature.actions(win)
               if a.data() == "extruded_cut")
    QTest.mouseClick(_button_for(win, act), Qt.LeftButton)
    QTest.qWait(200)
    assert win.view3d._pick_cb is not None
    win.view3d.set_view(view, animate=False)
    QTest.qWait(200)
    QTest.mouseClick(win.view3d.nav_bar.buttons["fit"], Qt.LeftButton)
    QTest.qWait(200)


def _click_world(win, world):
    from PyQt5.QtCore import QPoint
    from test_lever_by_mouse import _move
    v3 = win.view3d
    q = v3._project(*v3._camera(), world)
    p = QPoint(int(round(q[0])), int(round(q[1])))
    _move(v3, p)
    QTest.mouseClick(v3, Qt.LeftButton, Qt.NoModifier, p)
    QTest.qWait(150)


# ------------------------------------------------ 5. the small circle's area
def test_a_region_click_on_the_hole_takes_the_hole_not_an_edge_on_slab(win):
    """In the Right view the Front sketch's regions stand edge-on across
    the view: a click on the symmetrical hole's centre (y = 0) hit one of
    those slivers and the cut took the wrong area."""
    from khervecad import region_panel
    _clevis_boss(win)
    before = _volume(win)["volume"]
    _cut_on(win, "Right")
    # the hole's centre lies in the Front sketch's plane (y = 0), which
    # the Right view sees edge-on: the exact pixel must still be the hole
    v3 = win.view3d
    q = v3._project(*v3._camera(), (0.0, 0.0, 10.05))
    _desc, key = v3._pick_at(q[0], q[1])
    assert key is not None and key[0] == 1, \
        "picked the Front sketch's region %r" % (key,)
    _click_world(win, (0.0, 0.0, 10.05))
    ok = region_panel.ok_button(win)
    assert ok is not None, "no region panel"
    QTest.mouseClick(ok, Qt.LeftButton)
    QTest.qWait(200)
    _window_ok(win, direction="symmetric", extent="through_all")
    drop = before - _volume(win)["volume"]
    # the hole only: two bores of O10, about 13 mm long each
    assert 1000 < drop < 3000, drop


def test_two_sketches_tying_in_depth_the_first_listed_takes_the_click(win):
    """Every sketch's regions are offered inside an Object: where two
    slabs meet under the click the free sketch (listed first) wins, not
    the older extruded one (the clevis' slot cut took the fork's)."""
    view = win.view3d
    view.projection = "Orthographic"
    view.fit()
    old = [((0, 0, 0.0), (40, 0, 0.0), (40, 30, 0.0)),
           ((0, 0, 0.0), (40, 30, 0.0), (0, 30, 0.0))]
    new = [((10, 10, 0.004), (30, 10, 0.004), (30, 20, 0.004)),
           ((10, 10, 0.004), (30, 20, 0.004), (10, 20, 0.004))]
    eye, r, u, f = view._camera()
    x, y, _d = view._project(eye, r, u, f, (22.0, 14.0, 0.0))
    view._pick_groups = [((1, 0), new), ((0, 0), old)]
    assert view._pick_at(x, y)[1] == (1, 0)
    view._pick_groups = [((0, 0), old), ((1, 0), new)]
    assert view._pick_at(x, y)[1] == (0, 0)


# --------------------------------- 3, 4, 6. the planes clicked in 3D, in an Object
def test_right_plane_clicked_in_3d_inside_an_object(win):
    """The plane is named "Side (YZ)" (Right Plane): clicking it in 3D with
    the fork in the Object opens the sketch there."""
    from test_lever_by_mouse import _open_top_sketch
    _clevis_boss(win)
    _tab(win, "Sketch")
    win.builder.active_tree().clearSelection()
    _open_top_sketch(win, "Side (YZ)")
    assert win.view2d.scene().plane == "Side (YZ)"


@pytest.mark.parametrize("view", ["Top", "Isometric", "Front"])
def test_top_plane_in_an_object_sketch_and_boss_by_mouse(win, view):
    """Top Plane clicked in 3D inside the Object holding the fork: two
    circles, Extruded Boss, the ring region clicked — the region window
    opens and the boss is made."""
    from khervecad import extrude_panel
    from test_lever_by_mouse import _open_top_sketch
    _clevis_boss(win)
    _tab(win, "Sketch")
    win.builder.active_tree().clearSelection()
    before = _ids(win)
    _open_top_sketch(win, "Top (XY)")
    assert win.view2d.scene().plane == "Top (XY)"
    _frame(win, -30, -20, 60, 40)
    _circle(win, (0, 0), 13)
    _circle(win, (0, 0), 9)
    sk = _sketch_of(win, before)
    v0 = _volume(win)
    _extruded_boss(win)
    win.view3d.set_view(view, animate=False)
    QTest.qWait(200)
    _click_areas(win, sk, [(11, 0)])
    assert extrude_panel._panel(win) is not None, "no Extrude window"
    _window_ok(win, direction="up", distance=27)
    v1 = _volume(win)
    assert v1["volume"] != pytest.approx(v0["volume"], abs=1.0)


def _sketch_on(win, row):
    """A new sketch on a plane row, the Sketch tab's way."""
    _row_sketch(win, row)


# -------------------- 7. the tapered leg and Mirror Entities, by mouse only
def test_the_clevis_leg_at_7_degrees_and_its_mirror_by_mouse(win):
    """Sketch 1 of Exercise 8 with no assistant call: the leg is drawn
    roughly, made Tangent to the R24 circle and given its 7 degree angle
    to the vertical line by Smart Dimension (so no end point has to sit on
    the grid), then Mirror Entities about the centerline."""
    import math
    from khervecad import sketch_constraints as sc
    from khervecad import sketch_mirror, sketch_modify
    from test_clevis_by_mouse import _lines, _snap
    from test_smart_dimension_by_mouse import _dimension
    from test_lever_by_mouse import _at, _move
    v2 = win.view2d
    before = _ids(win)
    _sketch_on(win, "Front Plane")
    _snap(win)
    win.view2d.scene().grid_size = 0.5
    _frame(win, -45, -8, 90, 100)
    # the centerline up the axis, made construction
    _lines(v2, [(0, 0), (0, 40)])
    cl = next(n for n in win.model.root.walk()
              if n.id not in before and n.type == "line")
    win.model.set_param(cl, "modifier", "%")
    _circle(win, (0, 40), 24)
    _circle(win, (0, 40), 11)
    # the right leg: down from the small circle, along the base, up to
    # about the big circle (anywhere near: the solver finishes it)
    _lines(v2, [(11, 40), (11, 0), (19, 0), (24, 37)])
    mine = [n for n in win.model.root.walk() if n.id not in before
            and n.type == "line" and n is not cl]
    vertical, base, slant = mine
    big = next(n for n in win.model.root.walk() if n.id not in before
               and n.type == "circle" and n.params["radius"] == 24)
    # Tangent: the slanted line, then the circle (a point away from it)
    v2.set_tool("con_tangent")
    for pt in ((21.5, 18.5), (-24, 40)):
        p = _at(win, *pt)
        _move(v2.viewport(), p)
        QTest.mouseClick(v2.viewport(), Qt.LeftButton, Qt.NoModifier, p)
        QTest.qWait(30)
    v2.set_tool("select")
    assert any(r["kind"] == "tangent" for r in sc.rows(slant.parent)), \
        win.statusBar().currentMessage()
    # the angle between the vertical line and the slanted one: 7
    # (clicked away from the middles: a middle is a point of its own)
    ax, ay = slant.params["x1"], slant.params["y1"]
    bx, by = slant.params["x2"], slant.params["y2"]
    asked = _dimension(win, (11, 10),
                       (ax + (bx - ax) * 0.25, ay + (by - ay) * 0.25),
                       value=7)
    assert asked and asked[0][0] == "angle", asked
    assert [r["kind"] for r in sc.rows(slant.parent)].count("tangent") == 1
    assert not any(r.get("driven") for r in sc.rows(slant.parent))
    x1, y1, x2, y2 = (slant.params[k] for k in ("x1", "y1", "x2", "y2"))
    ang = abs(math.degrees(math.atan2(x2 - x1, y2 - y1)))
    assert min(ang, 180 - ang) == pytest.approx(7, abs=0.05), ang
    # tangent to R24 about (0, 40)
    dx, dy = x2 - x1, y2 - y1
    dist = abs(dx * (40 - y1) - dy * (0 - x1)) / math.hypot(dx, dy)
    assert dist == pytest.approx(24, abs=0.02)
    # Mirror Entities: the three lines about the centerline
    act = next(a for a in sketch_modify.panel_actions(win)
               if a.data() == sketch_mirror.TOOL)
    win.builder.active_tree().clearSelection()   # a selection pre-fills it
    v2.scene().clearSelection()
    act.trigger()
    QTest.qWait(50)
    ax, ay = slant.params["x1"], slant.params["y1"]
    bx, by = slant.params["x2"], slant.params["y2"]
    def along(n, t):
        q = n.params
        return (q["x1"] + (q["x2"] - q["x1"]) * t,
                q["y1"] + (q["y2"] - q["y1"]) * t)
    for pt in (along(vertical, 0.75), along(base, 0.3), along(slant, 0.25)):
        p = _at(win, *pt)
        _move(v2.viewport(), p)
        QTest.mouseClick(v2.viewport(), Qt.LeftButton, Qt.NoModifier, p)
        QTest.qWait(30)
    p = _at(win, 5, -5)
    QTest.mouseClick(v2.viewport(), Qt.RightButton, Qt.NoModifier, p)
    p = _at(win, 0, 10)
    QTest.mouseClick(v2.viewport(), Qt.LeftButton, Qt.NoModifier, p)
    QTest.qWait(50)
    panel = v2._mirror_panel
    assert panel.isVisible() and panel.ok.isEnabled()
    QTest.mouseClick(panel.ok, Qt.LeftButton)
    QTest.qWait(100)
    lines = [n for n in win.model.root.walk() if n.id not in before
             and n.type == "line" and n.params.get("modifier") != "%"]
    assert len(lines) == 6
    mirrored = [n for n in lines if n not in mine]
    xs = sorted(round(min(n.params["x1"], n.params["x2"]), 2)
                for n in mirrored)
    assert xs[0] == pytest.approx(-x2, abs=0.05)


# ---------------- 8. Through All - Both with "Flip side to cut", by mouse
def _block_with_circle(win, radius=10):
    """An Object holding a 40 mm cube (x, y 0..40, z 0..40) and a Top-plane
    circle drawn by mouse at its middle, Extruded Cut started."""
    from khervecad.mcp_tools import McpToolExecutor
    _new_object(win)
    McpToolExecutor(win).execute("add_node", dict(
        type="cube", params=dict(width=40, depth=40, height=40,
                                 center=False),
        parent_id=win.builder.isolated_component().id))
    QTest.qWait(200)
    before = _ids(win)
    _row_sketch(win, "Top Plane")
    _frame(win, -10, -10, 60, 60)
    _circle(win, (20, 20), radius)
    sk = _sketch_of(win, before)
    _cut_on(win, "Top")
    return sk


def _flip_cut(win, flip):
    from khervecad import region_panel, extrude_panel
    sk = _block_with_circle(win)
    _click_world(win, (20.0, 20.0, 0.05))
    ok = region_panel.ok_button(win)
    assert ok is not None, "no region panel"
    QTest.mouseClick(ok, Qt.LeftButton)
    QTest.qWait(200)
    panel = extrude_panel._panel(win)
    assert "flip" in panel.fields and panel.fields["flip"].isVisible()
    assert not panel.fields["flip"].isChecked()
    if flip:
        QTest.mouseClick(panel.fields["flip"], Qt.LeftButton)
        QTest.qWait(150)
    _window_ok(win, direction="symmetric", extent="through_all")
    return sk


def test_flip_side_to_cut_keeps_the_inside_of_the_profile(win):
    import math
    _flip_cut(win, flip=True)
    v = _volume(win)["volume"]
    assert v == pytest.approx(math.pi * 100 * 40, rel=0.03)    # the disc


def test_without_flip_the_profile_is_removed_as_before(win):
    import math
    _flip_cut(win, flip=False)
    v = _volume(win)["volume"]
    assert v == pytest.approx(64000 - math.pi * 100 * 40, rel=0.03)


def test_flip_survives_scad_export_and_import(win):
    from khervecad import scadparse
    _flip_cut(win, flip=True)
    code = win.model.to_scad()
    assert "flip = true" in code
    back, _warn = scadparse.parse_scad(code)
    reg = next(n for n in back.walk() if n.type == "regions")
    assert reg.params.get("flip") is True


def test_mcp_sketch_feature_flip(win):
    import math
    from khervecad.mcp_tools import McpToolExecutor
    ex = McpToolExecutor(win)
    _new_object(win)
    scope = win.builder.isolated_component()
    cube = ex.execute("add_node", dict(type="cube", params=dict(
        width=40, depth=40, height=40, center=False), parent_id=scope.id))
    sk = ex.execute("reference_geometry", dict(
        action="sketch", origin=[0, 0, 0], normal=[0, 0, 1]))["sketch_id"]
    ex.execute("add_node", dict(type="circle", parent_id=sk, params=dict(
        x=20, y=20, radius=10)))
    out = ex.execute("sketch_feature", dict(
        node_id=sk, kind="extruded_cut", through_all=True, flip=True,
        part_id=cube["created"], regions=[[20, 20]]))
    assert "error" not in out, out
    v = _volume(win)["volume"]
    assert v == pytest.approx(math.pi * 100 * 40, rel=0.03)
