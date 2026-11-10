"""A boss on a boss on a boss, a cut, a boss, a revolve: every sketch
with Smart Dimensions, the History as a feature list, and everything
following when a dimension changes (2026-11-10, the user).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import (analysis, cut_feature, feature_list, mesh,
                       sketch_constraints as sc, suppress)
from khervecad.mainwindow import MainWindow
from khervecad.mcp_tools import McpToolExecutor
from khervecad.model import DocumentModel


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app, monkeypatch):
    monkeypatch.setattr(cut_feature, "IN_3D", True)
    w = MainWindow()
    yield w
    w._dirty = False
    w.close()


def _volume(win):
    return analysis.mass_properties(mesh.tessellate(win.model.root))["volume"]


def _base(win, size="[100, 60, 20]"):
    McpToolExecutor(win).execute("apply_code", {
        "code": "translate([-50, -30, 0]) cube(%s); // Base\n" % size})
    QApplication.processEvents()
    return next(c for c in win.model.root.children
                if c.visible and c.type != "assign")


def _sketch_on(win, part, pos, kind="extruded_boss", normal=(0, 0, 1)):
    cut_feature.start(win, kind)
    win.view3d._pick_cb(dict(kind="face", pos=pos, dir=normal), part)
    return win.view3d.edit_tool


def _keep(win):
    """OK on the extrude's arrow."""
    tool = win.view3d.edit_tool
    if tool is not None and hasattr(tool, "ok"):
        tool.ok()
    QApplication.processEvents()


def _rect_feature(win, part, pos, a, b, kind="extruded_boss", height=None):
    tool = _sketch_on(win, part, pos, kind)
    tool.set_mode("rect")
    tool.place(a)
    tool.place(b)
    QApplication.processEvents()
    ext = next(n for n in tool.group.walk() if n.type == "linear_extrude")
    if height is not None:
        win.model.set_param(ext, "height", height)
    _keep(win)
    return ext


# ------------------------------------------------------- lines on a face
def _line_loop(tool, pts):
    tool.set_mode("line")
    for p in pts + [pts[0]]:
        tool.place(p)
    tool._end_chain()


def test_a_boss_of_lines_on_a_face_is_exactly_its_size(win):
    """Its area was grown 0.15 mm all round (the push into the part
    meant for a rib standing BESIDE it): 60 came out 60.3."""
    part = _base(win)
    full = _volume(win)
    tool = _sketch_on(win, part, (30, 20, 20))
    _line_loop(tool, [(-30, -18), (30, -18), (30, 18), (-30, 18)])
    tool.go_on()
    QApplication.processEvents()
    ext = next(n for n in win.model.root.walk()
               if n.type == "linear_extrude")
    win.model.set_param(ext, "height", 15.0)
    _keep(win)
    assert _volume(win) - full == pytest.approx(60 * 36 * 15, abs=0.5)


def test_a_centerline_and_its_relations_go_into_the_feature(win):
    """A construction diagonal with its middle on the origin centres the
    loop. Making the feature left both behind, and the relations to
    them were dropped."""
    from khervecad import sketch3d_tools as more, sketch_tools2
    part = _base(win)
    tool = _sketch_on(win, part, (30, 20, 20))
    _line_loop(tool, [(-27, -16), (29, -16), (29, 19), (-27, 19)])
    more.use(tool, sketch_tools2.CONST_LINE)
    tool.place((-27, -16))
    tool.place((29, 19))
    g = tool.group
    diag = g.children[-1]
    assert diag.params.get("modifier") == "%"
    # tied to the corners it was drawn from, both ends
    ties = [r for r in sc.rows(g) if r["kind"] == "coincident"
            and any(ref.startswith("4.") for ref in r["refs"])]
    assert {r["refs"][1] for r in ties} == {"4.p1", "4.p2"}
    point = win.model.add_node("circle", dict(x=0.0, y=0.0, radius=0.25,
                                              modifier="%"), parent=g)
    sc.add(win.model, g, "fix", [sc.ref_of(g, point, "c")])
    report = sc.add(win.model, g, "midpoint",
                    [sc.ref_of(g, point, "c"), sc.ref_of(g, diag, "l")])
    lines = [c for c in g.children if c.type == "line"][:4]
    xs = sorted({round(c.params[k], 3) for c in lines for k in ("x1", "x2")})
    assert xs == [-28.0, 28.0]                       # centred on the origin
    assert "degree" in sc.status_text(report)        # sizes still free
    tool.go_on()
    QApplication.processEvents()
    reg = next(n for n in win.model.root.walk() if n.type == "regions")
    assert diag.parent is reg and point.parent is reg
    assert diag.params.get("modifier") == "%"        # still construction
    assert any(r["kind"] == "midpoint" for r in sc.rows(reg))
    from khervecad import regions2d
    assert diag not in regions2d.shapes(reg)         # and no edge of the area
    _keep(win)


def test_a_construction_point_closes_no_area(win):
    """With a reference point in the sketch, a loop of lines was
    extruded as four hair-thin strips."""
    part = _base(win)
    full = _volume(win)
    tool = _sketch_on(win, part, (30, 20, 20))
    _line_loop(tool, [(-20, -10), (20, -10), (20, 10), (-20, 10)])
    win.model.add_node("circle", dict(x=0.0, y=0.0, radius=0.25,
                                      modifier="%"), parent=tool.group)
    tool.go_on()
    QApplication.processEvents()
    _keep(win)
    assert _volume(win) - full == pytest.approx(40 * 20 * 10, abs=0.5)


def test_a_sketch_point_is_two_freedoms_not_three():
    m = DocumentModel()
    g = m.add_node("union", {})
    p = m.add_node("circle", dict(x=1.0, y=2.0, radius=0.25, modifier="%"),
                   parent=g)
    assert [k for k, _v in sc._vars(p)] == ["x", "y"]
    c = m.add_node("circle", dict(x=1.0, y=2.0, radius=5.0), parent=g)
    assert [k for k, _v in sc._vars(c)] == ["x", "y", "radius"]


# ----------------------------------------------------- a regular polygon
class _Scene:
    def __init__(self, model):
        self.model = model
        self.made = []


def test_a_regular_polygon_stays_regular_under_one_dimension():
    """One side dimensioned moved that side alone (nine freedoms left)."""
    from khervecad import sketch_tools2
    m = DocumentModel()
    g = m.add_node("union", {})
    pts = sketch_tools2.regular_points((0.0, 0.0), (13.0, 0.0), 6)
    poly = m.add_node("polygon", dict(points=[[round(x, 6), round(y, 6)]
                                              for x, y in pts]), parent=g)
    circle = sketch_tools2.regular_relations(_Scene(m), poly, (0.0, 0.0))
    assert circle.params.get("modifier") == "%"
    sc.add(m, g, "fix", [sc.ref_of(g, circle, "c")])
    sc.add(m, g, "horizontal", [sc.ref_of(g, poly, "e1")])
    report = sc.add(m, g, "length", [sc.ref_of(g, poly, "e0")], 15.0)
    assert sc.status_text(report).startswith("Fully")
    q = poly.params["points"]
    sides = [math.dist(q[i], q[(i + 1) % 6]) for i in range(6)]
    assert sides == pytest.approx([15.0] * 6, abs=1e-4)
    assert [math.hypot(*p) for p in q] == pytest.approx([15.0] * 6, abs=1e-4)
    assert circle.params["radius"] == pytest.approx(15.0, abs=1e-4)


# --------------------------------------------------------------- revolve
def test_revolved_boss_turns_the_area_about_the_sketch_axis(win):
    """A triangle of lines on the Front plane came out as three thin
    rings lying on their side."""
    from khervecad import face_sketch, revolve_feature
    m = win.model
    g = m.add_node("union", dict(x=0.0, y=0.0, z=0.0, rx=90.0, ry=0.0,
                                 rz=0.0))
    g.params[face_sketch.KEY] = True
    for a, b in (((0, 10), (4, 10)), ((4, 10), (0, 16)), ((0, 16), (0, 10))):
        m.add_node("line", dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1],
                                width=0.2), parent=g)
    tool = revolve_feature.revolve(win, list(g.children))
    assert tool is not None and tool.type == "rotate_extrude"
    assert tool.children[0].type == "regions"
    tris = mesh.tessellate(m.root)
    assert analysis.mass_properties(tris)["volume"] == pytest.approx(
        math.pi * 16 * 6 / 3, rel=0.01)
    zs = [v[2] for t in tris for v in t[:3]]
    ys = [v[1] for t in tris for v in t[:3]]
    assert (min(zs), max(zs)) == pytest.approx((10, 16), abs=0.01)
    assert (min(ys), max(ys)) == pytest.approx((-4, 4), abs=0.05)


def test_a_revolves_profile_stands_in_its_sketch_plane():
    """Where its dimensions and references are drawn and solved."""
    m = DocumentModel()
    rot = m.add_node("rotate", dict(x=-90.0, y=0.0, z=0.0))
    rev = m.add_node("rotate_extrude", {}, parent=rot)
    shape = m.add_node("circle", dict(x=5.0, y=7.0, radius=1.0), parent=rev)
    at = mesh.mat_apply(mesh.ancestor_matrix(shape), (5.0, 7.0, 0.0))
    assert at == pytest.approx([5.0, 7.0, 0.0], abs=1e-9)


# --------------------------------------------------- the History list
def _stack(win):
    """Base, a boss on it, a boss on that, then a pocket in the BASE."""
    part = _base(win)
    b2 = _rect_feature(win, part, (30, 20, 20), (-30, -18), (30, 18),
                       height=15.0)
    b3 = _rect_feature(win, part, (0, 0, 35), (-10, -10), (10, 10),
                       height=12.0)
    cut = _rect_feature(win, part, (42, 0, 20), (36, -8), (46, 8),
                        kind="extruded_cut", height=6.0)
    return part, b2, b3, cut


def test_history_lists_features_in_the_order_made(win):
    """The pocket, made last, stood second: its Difference wraps the
    base. And every feature was three rows."""
    part, b2, b3, cut = _stack(win)
    listed = feature_list.features(win.model)
    assert [n for n in listed if n.type == "linear_extrude"] == [b2, b3, cut]
    assert listed[-1] is cut                         # made last, listed last
    assert not any(n.type == "difference" or
                   feature_list.is_sketch_group(n) for n in listed)
    # the tree walks to the cut BEFORE the bosses
    walk = [n for n in win.model.root.walk() if n in (b2, b3, cut)]
    assert walk[0] is cut


def test_the_history_view_shows_one_row_a_feature(win):
    from PyQt5.QtCore import Qt
    from khervecad import tree_history
    part, b2, b3, cut = _stack(win)
    tree_history.set_enabled(True)
    try:
        tree = win.builder.tree
        tree.rebuild()
        rows = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
        rows = [r for r in rows if not r.data(0, tree_history.ROLE_FIXED)]
        ids = [r.data(0, Qt.UserRole) for r in rows]
        assert ids[-3:] == [b2.id, b3.id, cut.id]
        last = rows[-1]
        assert last.childCount() == 1                # its sketch, under it
        assert last.child(0).text(0).startswith("Sketch")
        assert last.child(0).child(0).text(0).startswith("Rect")
    finally:
        tree_history.set_enabled(False)
        win.builder.tree.rebuild()


def test_rolling_back_in_history_takes_what_was_made_after(win):
    """Roll back to the first boss: the second boss AND the pocket go —
    though the pocket stands before both in the tree."""
    part, b2, b3, cut = _stack(win)
    full = _volume(win)
    n = feature_list.roll_back_to(win.model, b2)
    assert n == 2 and feature_list.rolled(b3) and feature_list.rolled(cut)
    QApplication.processEvents()
    assert _volume(win) == pytest.approx(100 * 60 * 20 + 60 * 36 * 15, abs=1)
    suppress.roll_forward(win.model)
    QApplication.processEvents()
    assert _volume(win) == pytest.approx(full, abs=1e-6)


def test_a_switched_off_extrude_draws_nothing():
    m = DocumentModel()
    e = m.add_node("linear_extrude", {"height": 5})
    m.add_node("rect", {}, parent=e)
    e.params[suppress.KEY] = True
    assert suppress.keep_of(e) == "none"
    assert mesh.tessellate(m.root) == []


def test_the_order_survives_save_and_open(win, tmp_path):
    part, b2, b3, cut = _stack(win)
    ex = McpToolExecutor(win)
    path = str(tmp_path / "stack.kcad")
    ex.execute("save_document", {"path": path})
    win._dirty = False
    ex.execute("open_document", {"path": path})
    QApplication.processEvents()
    heights = [n.params["height"] for n in feature_list.features(win.model)
               if n.type == "linear_extrude"]
    assert heights == [15.0, 12.0, 6.0]
    win._dirty = False


# ------------------------------------------- everything follows a change
def _box(win, node):
    r = McpToolExecutor(win).execute(
        "get_node_bounds", {"node_ids": [node.id]})["nodes"][0]
    return r["min"], r["max"]


def test_a_stack_stays_together_when_a_lower_boss_grows(win):
    """The boss under a stack made 10 mm taller put its own top 2 mm
    from where the next sketch stood — nearer than the face that had
    moved up — and that sketch went DOWN onto it."""
    part = _base(win)
    b2 = _rect_feature(win, part, (30, 20, 20), (-30, -18), (30, 18),
                       height=15.0)
    b3 = _rect_feature(win, part, (0, 0, 35), (-10, -10), (10, 10),
                       height=12.0)
    from khervecad import face_sketch
    # (the part clicked is the boss itself, then the boss with its cut)
    on = face_sketch.group_of(b3)
    cut = _rect_feature(win, on, (0, 0, 47), (-4, -4), (4, 4),
                        kind="extruded_cut", height=8.0)
    pin = _rect_feature(win, on.parent, (0, 0, 39), (-1, -1), (1, 1),
                        height=14.0)
    assert _box(win, pin)[0][2] == pytest.approx(39.0, abs=0.02)
    full = _volume(win)
    win.model.set_param(b2, "height", 25.0)
    QApplication.processEvents()
    assert _box(win, b3)[0][2] == pytest.approx(45.0, abs=0.02)
    assert _box(win, cut)[1][2] == pytest.approx(57.0, abs=0.02)
    assert _box(win, pin)[0][2] == pytest.approx(49.0, abs=0.02)
    assert _volume(win) - full == pytest.approx(60 * 36 * 10, abs=1)
    # and the base under all of it
    win.model.set_param(next(n for n in part.walk() if n.type == "cube")
                        if part.type != "cube" else part, "height", 30.0)
    QApplication.processEvents()
    assert _box(win, b2)[0][2] == pytest.approx(30.0, abs=0.02)
    assert _box(win, pin)[0][2] == pytest.approx(59.0, abs=0.02)


def test_the_selected_features_dimensions_show_through_the_part(win):
    """A boss stands on its own sketch, and a base grown past where its
    width was written hid the number: neither could be clicked."""
    from khervecad import sketch_dims3d
    part = _base(win)
    b2 = _rect_feature(win, part, (30, 20, 20), (-30, -18), (30, 18))
    cont = b2
    rect = next(c for c in b2.children if c.type == "rect")
    sc.add(win.model, cont, "length", [sc.ref_of(cont, rect, "e0")], 60.0)
    win.builder.active_tree().select_nodes([b2])
    assert id(cont) in sketch_dims3d._selected_sketches(win, [cont])
    win.builder.active_tree().clearSelection()
    assert not sketch_dims3d._selected_sketches(win, [cont])
    b2.params[suppress.ROLLED] = True                # rolled back: none
    assert cont not in [c for c, _m in sketch_dims3d.placements(win)]


# ------------------------------------------------- clicks that found nothing
def test_a_click_on_a_sketch_point_starts_a_shape_there(win):
    """The press was always taken as a grab of the point: a centerline
    from a corner never began."""
    from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
    from PyQt5.QtGui import QMouseEvent
    from PyQt5.QtTest import QTest
    from khervecad import face_sketch as fs, sketch3d_tools as more
    from khervecad import sketch_tools2
    win.show()
    win.view3d.resize(800, 600)
    part = _base(win)
    tool = _sketch_on(win, part, (30, 20, 20))
    QTest.qWait(700)                                 # the turn to the face
    _line_loop(tool, [(-20, -10), (20, -10), (20, 10), (-20, 10)])
    more.use(tool, sketch_tools2.CONST_LINE)
    v, g = win.view3d, tool.group

    def click(x, y):
        q = v._project(*v._camera(), fs.to_world(g, x, y))
        p = QPoint(int(round(q[0])), int(round(q[1])))
        for kind, held in ((QEvent.MouseButtonPress, Qt.LeftButton),
                           (QEvent.MouseButtonRelease, Qt.NoButton)):
            QApplication.sendEvent(v, QMouseEvent(
                kind, QPointF(p), Qt.LeftButton, held, Qt.NoModifier))
    before = len(g.children)
    click(-20, -10)
    click(20, 10)
    QApplication.processEvents()
    assert len(g.children) == before + 1
    assert g.children[-1].params.get("modifier") == "%"
    tool.finish()


def test_a_relation_takes_the_origin(win):
    """Midpoint on the origin: nothing was under the click."""
    from PyQt5.QtTest import QTest
    from khervecad import constrain3d, face_sketch as fs
    win.show()
    win.view3d.resize(800, 600)
    part = _base(win)
    tool = _sketch_on(win, part, (30, 20, 20))
    QTest.qWait(700)
    _line_loop(tool, [(-20, -10), (20, -10), (20, 10), (-20, 10)])
    tool.tool_icon("con_midpoint")                   # the ribbon's button
    con = win.view3d.edit_tool
    assert isinstance(con, constrain3d.Constrain3D)
    v = win.view3d
    q = v._project(*v._camera(), fs.to_world(tool.group, 0.0, 0.0))
    con.click(int(round(q[0])), int(round(q[1])))
    assert len(con.picks) == 1 and con.picks[0][2] == "point"
    assert con.picks[0][0].name.startswith("Reference point")
    constrain3d.end(win)
    tool.finish()


def test_an_assistant_reads_the_history_and_rolls_it_back(win):
    part, b2, b3, cut = _stack(win)
    ex = McpToolExecutor(win)
    got = ex.execute("suppress", {"action": "history"})["history"]
    steps = [r for r in got if r["type"] == "linear_extrude"]
    assert [r["id"] for r in steps] == [b2.id, b3.id, cut.id]
    assert [r["cut"] for r in steps] == [False, False, True]
    assert steps[0]["sketch"][0]["type"] == "rect"
    got = ex.execute("suppress", {"action": "rollback_history",
                                  "node_id": b2.id})["history"]
    assert [r.get("off") for r in got if r["type"] == "linear_extrude"] == \
        [None, "rolled back", "rolled back"]
    ex.execute("suppress", {"action": "roll_forward"})
    assert not suppress.any_rollback(win.model.root)
