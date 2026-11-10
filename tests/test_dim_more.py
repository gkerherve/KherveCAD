"""The rest of SolidWorks' Smart Dimension (2026-11-10, the user): the
horizontal / vertical distance by where the number is placed, an arc's
length, a diameter across a centerline, driven dimensions, the near /
far side of a circle.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import constrain3d, dim_more, sketch_constraints as sc
from khervecad.model import DocumentModel

from test_stacked_features import app, win  # noqa


# ------------------------------------------------------------ the solver
def _sketch(*shapes):
    m = DocumentModel()
    g = m.add_node("union", {}, name="Sketch")
    nodes = [m.add_node(t, dict(p), parent=g) for t, p in shapes]
    for n, (_t, p) in zip(nodes, shapes):
        if p.get("modifier"):
            n.params["modifier"] = p["modifier"]
    return m, g, nodes


def test_an_arcs_length_is_driven():
    m, g, (arc,) = _sketch(("line", dict(x1=0, y1=0, x2=10, y2=0,
                                         width=0.2, bulge=1.0)))
    # a half circle over a 10 chord: pi * 5
    assert sc.measure(g, "arc_length", ["0.l"]) == pytest.approx(
        math.pi * 5, abs=1e-6)
    sc.add(m, g, "fix", ["0.p1"])
    sc.add(m, g, "fix", ["0.p2"])
    sc.add(m, g, "arc_length", ["0.l"], 12.0)
    p = arc.params
    assert (p["x1"], p["x2"]) == (0, 10)             # the ends stayed
    assert sc.arc_length(((0, 0), (10, 0)), p["bulge"]) == pytest.approx(
        12.0, abs=1e-4)
    assert 0 < p["bulge"] < 1.0                      # flatter


def test_a_diameter_across_a_centerline():
    m, g, (axis, edge) = _sketch(
        ("line", dict(x1=0, y1=0, x2=0, y2=30, width=0.2, modifier="%")),
        ("line", dict(x1=7, y1=5, x2=7, y2=25, width=0.2)))
    sc.add(m, g, "fix", ["0.p1"])
    sc.add(m, g, "fix", ["0.p2"])
    assert sc.measure(g, "point_line", ["1.p1", "0.l"],
                      {"double": True}) == pytest.approx(14.0)
    sc.add(m, g, "vertical", ["1.l"])
    sc.add(m, g, "point_line", ["1.p1", "0.l"], 20.0,
           extra={"double": True})
    assert edge.params["x1"] == pytest.approx(10.0, abs=1e-4)
    row = sc.rows(g)[-1]
    assert dim_more.text(row) == "Ø20"


def test_the_near_and_far_side_of_a_circle():
    m, g, (a, b) = _sketch(
        ("circle", dict(x=0, y=0, radius=4)),
        ("circle", dict(x=30, y=0, radius=6)))
    sc.add(m, g, "fix", ["0.c"])
    sc.add(m, g, "radius", ["0.o"], 4.0)
    sc.add(m, g, "radius", ["1.o"], 6.0)
    sc.add(m, g, "horizontal", ["0.c", "1.c"])
    rim = {"0": "min", "1": "min"}                   # the gap between
    assert sc.measure(g, "distance", ["0.c", "1.c"],
                      {"rim": rim}) == pytest.approx(20.0)
    sc.add(m, g, "distance", ["0.c", "1.c"], 15.0, extra={"rim": rim})
    assert b.params["x"] == pytest.approx(25.0, abs=1e-4)
    sc.set_value(m, g, len(sc.rows(g)) - 1, 10.0)
    assert b.params["x"] == pytest.approx(20.0, abs=1e-4)
    # outside to outside
    assert sc.measure(g, "distance", ["0.c", "1.c"], {
        "rim": {"0": "max", "1": "max"}}) == pytest.approx(30.0)


def test_a_driven_dimension_only_measures():
    m, g, (r,) = _sketch(("rect", dict(x=0, y=0, width=40, height=20)))
    sc.add(m, g, "fix", ["0.v0"])
    sc.add(m, g, "length", ["0.e0"], 40.0)
    sc.add(m, g, "length", ["0.e1"], 20.0)
    # the diagonal is already decided: driving it must be refused ...
    with pytest.raises(sc.Conflict):
        sc.add(m, g, "distance", ["0.v0", "0.v2"], 50.0)
    # ... and Smart Dimension adds it driven instead
    report, scaled, driven = dim_more.add(m, g, "distance",
                                          ["0.v0", "0.v2"], 50.0)
    assert driven and not scaled
    row = sc.rows(g)[-1]
    assert row["driven"] and row["value"] == pytest.approx(
        math.hypot(40, 20), abs=1e-3)
    assert dim_more.text(row).startswith("(") and r.params["width"] == 40
    with pytest.raises(ValueError):
        sc.set_value(m, g, len(sc.rows(g)) - 1, 60.0)
    # it follows the sketch
    sc.set_value(m, g, 1, 30.0)
    sc.refresh(m)
    assert sc.rows(g)[-1]["value"] == pytest.approx(math.hypot(30, 20),
                                                    abs=1e-3)
    # driving again: it takes the size it measures, which holds
    sc.set_driven(m, g, len(sc.rows(g)) - 1, False)
    assert not sc.rows(g)[-1].get("driven")
    assert sc.rows(g)[-1]["value"] == pytest.approx(math.hypot(30, 20),
                                                    abs=1e-3)


def test_a_sketch_of_driven_dimensions_alone_still_solves():
    m, g, (line,) = _sketch(("line", dict(x1=0, y1=0, x2=3, y2=4,
                                          width=0.2)))
    sc.add(m, g, "length", ["0.l"], None, extra={"driven": True})
    assert sc.rows(g)[0]["value"] == pytest.approx(5.0)
    assert sc.solve(g)["ok"]
    sc.refresh(m)


# ------------------------------------------------- where it is placed
def _two_points():
    m, g, (a, b) = _sketch(
        ("circle", dict(x=0, y=0, radius=0.25, modifier="%")),
        ("circle", dict(x=30, y=10, radius=0.25, modifier="%")))
    return m, g, ("distance", [(a, "c", "point"), (b, "c", "point")])


def test_where_the_number_goes_picks_the_kind():
    m, g, made = _two_points()
    assert dim_more.needs_place(made)
    assert dim_more.refine(made, (15, 25))[0] == "hdistance"   # above
    assert dim_more.refine(made, (15, -9))[0] == "hdistance"   # below
    assert dim_more.refine(made, (40, 5))[0] == "vdistance"    # right
    assert dim_more.refine(made, (-8, 5))[0] == "vdistance"    # left
    assert dim_more.refine(made, (15, 5))[0] == "distance"     # between
    assert dim_more.refine(made, (40, 30))[0] == "distance"    # a corner


def test_level_points_need_no_placing():
    m, g, (a, b) = _sketch(
        ("circle", dict(x=0, y=0, radius=0.25, modifier="%")),
        ("circle", dict(x=30, y=0, radius=0.25, modifier="%")))
    assert not dim_more.needs_place(
        ("distance", [(a, "c", "point"), (b, "c", "point")]))


def test_the_arc_itself_gives_its_length():
    m, g, (arc,) = _sketch(("line", dict(x1=0, y1=0, x2=10, y2=0,
                                         width=0.2, bulge=1.0)))
    made = ("distance", [(arc, "p1", "point"), (arc, "p2", "point")])
    assert dim_more.needs_place(made)                # level, but an arc
    from khervecad import sketch_arc
    on = sketch_arc.points(0, 0, 10, 0, 1.0)
    mid = on[len(on) // 2]
    kind, chosen, _x = dim_more.refine(made, mid)
    assert kind == "arc_length" and chosen == [(arc, "l", "line")]
    assert dim_more.refine(made, (5, 40))[0] == "distance"


def test_across_the_centerline_doubles():
    m, g, (axis, edge) = _sketch(
        ("line", dict(x1=0, y1=0, x2=0, y2=30, width=0.2, modifier="%")),
        ("line", dict(x1=7, y1=5, x2=7, y2=25, width=0.2)))
    made = ("point_line", [(edge, "p1", "point"), (axis, "l", "line")])
    assert dim_more.needs_place(made)
    assert dim_more.refine(made, (-12, 10))[2] == {"double": True}
    assert dim_more.refine(made, (12, 10))[2] == {}
    # a reference copied from the model is no centerline
    axis.name = "Reference edge"
    assert not dim_more.needs_place(made)


# ------------------------------------------------------ in the 3D view
def _screen(tool, world):
    q = tool._project()(world)
    return q[0], q[1]


def _points3d(win):
    m = win.model
    g = m.add_node("union", {}, name="Sketch")
    a = m.add_node("line", dict(x1=0, y1=0, x2=30, y2=10, width=0.2),
                   parent=g)
    QTest.qWait(50)
    v = win.view3d
    v.resize(900, 700)
    v.set_view("Top", animate=False)
    v.fit()
    QApplication.processEvents()
    return g, a


@pytest.mark.parametrize("place, kind, moved", [
    ((15, 25, 0), "hdistance", ("x2", 40.0)),
    ((45, 5, 0), "vdistance", ("y2", 40.0)),
])
def test_the_third_click_places_a_3d_dimension(win, place, kind, moved):
    g, a = _points3d(win)
    win.view2d.scene().ask_value = lambda k, measured: "40"
    constrain3d.start(win, "con_dimension")
    t = win.view3d.edit_tool
    assert t.click(*_screen(t, (0, 0, 0))) is None
    assert t.click(*_screen(t, (30, 10, 0))) is None     # waits
    assert not sc.rows(g) or all("value" not in r for r in sc.rows(g))
    assert t.click(*_screen(t, place)) is not None
    row = [r for r in sc.rows(g) if "value" in r][-1]
    assert row["kind"] == kind
    constrain3d.end(win)


def test_a_dimension_a_full_sketch_cannot_take_comes_driven(win):
    m = win.model
    g = m.add_node("union", {}, name="Sketch")
    r = m.add_node("rect", dict(x=0, y=0, width=40, height=20), parent=g)
    sc.add(m, g, "fix", ["0.v0"])
    sc.add(m, g, "length", ["0.e0"], 40.0)
    sc.add(m, g, "length", ["0.e1"], 20.0)
    QTest.qWait(50)
    v = win.view3d
    v.resize(900, 700)
    v.set_view("Top", animate=False)
    v.fit()
    win.view2d.scene().ask_value = lambda k, measured: "99"
    constrain3d.start(win, "con_dimension")
    t = win.view3d.edit_tool
    t.click(*_screen(t, (0, 0, 0)))
    t.click(*_screen(t, (40, 20, 0)))
    t.click(*_screen(t, (20, 10, 0)))            # between: the diagonal
    row = sc.rows(g)[-1]
    assert row["kind"] == "distance" and row.get("driven")
    assert r.params["width"] == 40
    # the right-click menu's tick
    from khervecad import view3d_menu
    view3d_menu.set_driven(win, g, len(sc.rows(g)) - 1, False)
    assert not sc.rows(g)[-1].get("driven")
    view3d_menu.set_driven(win, g, len(sc.rows(g)) - 1, True)
    assert sc.rows(g)[-1].get("driven")
    constrain3d.end(win)


def test_an_assistant_adds_the_same_dimensions(win):
    from khervecad.mcp_tools import McpToolExecutor
    m = win.model
    g = m.add_node("union", {}, name="Sketch")
    m.add_node("line", dict(x1=0, y1=0, x2=0, y2=30, width=0.2), parent=g)
    g.children[0].params["modifier"] = "%"
    m.add_node("line", dict(x1=7, y1=5, x2=7, y2=25, width=0.2), parent=g)
    ex = McpToolExecutor(win)
    for end in ("p1", "p2"):
        ex.execute("sketch_constraint", dict(
            action="add", node_id=g.id, kind="fix", refs=["0." + end]))
    got = ex.execute("sketch_constraint", dict(
        action="add", node_id=g.id, kind="point_line",
        refs=["1.p1", "0.l"], value=20, double=True, scale_sketch=False))
    assert "error" not in got
    assert g.children[1].params["x1"] == pytest.approx(10.0, abs=1e-3)
    got = ex.execute("sketch_constraint", dict(
        action="add", node_id=g.id, kind="length", refs=["1.l"],
        driven=True))
    assert sc.rows(g)[-1]["driven"]
    ex.execute("sketch_constraint", dict(
        action="set_driven", node_id=g.id, index=len(sc.rows(g)) - 1,
        driven=False))
    assert not sc.rows(g)[-1].get("driven")
