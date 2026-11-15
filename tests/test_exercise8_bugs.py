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
