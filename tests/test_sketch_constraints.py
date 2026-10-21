"""Sketch constraints: the solver, saving, the 2D view's click tools,
the ribbon panel and the MCP tool.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math

import pytest
from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from khervecad import document, sketch_constrain_ui as ui
from khervecad import sketch_constraints as sc
from khervecad.model import DocumentModel


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _ref(model, node, name):
    return sc.ref_of(model.root, node, name)


def _lines(model):
    a = model.add_node("line", dict(x1=0, y1=0, x2=40, y2=3))
    b = model.add_node("line", dict(x1=41, y1=1, x2=45, y2=30))
    return a, b


def _len(n):
    p = n.params
    return math.hypot(p["x2"] - p["x1"], p["y2"] - p["y1"])


def test_constraints_hold_and_count_freedom(app):
    m = DocumentModel()
    a, b = _lines(m)
    r = m.root
    sc.add(m, r, "horizontal", [_ref(m, a, "l")])
    sc.add(m, r, "coincident", [_ref(m, a, "p2"), _ref(m, b, "p1")])
    sc.add(m, r, "perpendicular", [_ref(m, a, "l"), _ref(m, b, "l")])
    sc.add(m, r, "length", [_ref(m, b, "l")], 50)
    assert abs(a.params["y1"] - a.params["y2"]) < 1e-4
    assert abs(a.params["x2"] - b.params["x1"]) < 1e-4
    assert abs(b.params["x1"] - b.params["x2"]) < 1e-4
    assert abs(_len(b) - 50) < 1e-4
    # 8 unknowns, 5 equations
    assert sc.solve(r, write=False)["dof"] == 3
    sc.add(m, r, "fix", [_ref(m, a, "p1")])
    sc.add(m, r, "length", [_ref(m, a, "l")], 30)
    assert sc.solve(r, write=False)["dof"] == 0
    assert "Fully" in sc.status_text(sc.solve(r, write=False))


def test_a_conflict_is_refused_and_leaves_the_sketch(app):
    m = DocumentModel()
    a, _b = _lines(m)
    sc.add(m, m.root, "horizontal", [_ref(m, a, "l")])
    before = dict(a.params)
    with pytest.raises(sc.Conflict):
        sc.add(m, m.root, "vertical", [_ref(m, a, "l")])
    assert a.params == before
    assert len(sc.rows(m.root)) == 1


def test_an_edit_drags_the_constrained_rest(app):
    m = DocumentModel()
    a, b = _lines(m)
    sc.add(m, m.root, "coincident", [_ref(m, a, "p2"), _ref(m, b, "p1")])
    sc.add(m, m.root, "parallel", [_ref(m, a, "l"), _ref(m, b, "l")])
    a.params["x2"], a.params["y2"] = 20.0, 20.0
    sc.refresh(m, {a.id})
    assert abs(a.params["x2"] - 20) < 2.0      # the edit mostly stays
    assert abs(b.params["x1"] - a.params["x2"]) < 1e-4
    u = (a.params["x2"] - a.params["x1"], a.params["y2"] - a.params["y1"])
    v = (b.params["x2"] - b.params["x1"], b.params["y2"] - b.params["y1"])
    assert abs(u[0] * v[1] - u[1] * v[0]) < 1e-3 * _len(a) * _len(b)


def test_dimensions_circles_rects_and_expressions(app):
    m = DocumentModel()
    m.add_node("assign", dict(variable="w", value=24))
    c = m.add_node("circle", dict(x=0, y=0, radius=5))
    d = m.add_node("circle", dict(x=3, y=1, radius=9))
    rect = m.add_node("rect", dict(x=30, y=0, width=10, height=10))
    r = m.root
    sc.add(m, r, "diameter", [_ref(m, c, "o")], "w / 2")
    sc.add(m, r, "concentric", [_ref(m, c, "o"), _ref(m, d, "o")])
    sc.add(m, r, "equal", [_ref(m, rect, "e0"), _ref(m, rect, "e1")])
    sc.add(m, r, "length", [_ref(m, rect, "e0")], 16)
    assert abs(c.params["radius"] - 6) < 1e-4
    assert abs(c.params["x"] - d.params["x"]) < 1e-4
    assert abs(rect.params["width"] - 16) < 1e-4
    assert abs(rect.params["height"] - 16) < 1e-4


def test_angle_tangent_and_point_on(app):
    m = DocumentModel()
    a, b = _lines(m)
    c = m.add_node("circle", dict(x=10, y=20, radius=5))
    r = m.root
    sc.add(m, r, "angle", [_ref(m, a, "l"), _ref(m, b, "l")], 60)
    assert abs(sc.measure(r, "angle", [_ref(m, a, "l"), _ref(m, b, "l")])
               - 60) < 1e-3
    sc.add(m, r, "tangent", [_ref(m, a, "l"), _ref(m, c, "o")])
    dist = sc._pl_dist(sc._point(c, "c", {}), sc._line(a, "l", {}))
    assert abs(abs(dist) - c.params["radius"]) < 1e-4
    sc.add(m, r, "point_on", [_ref(m, b, "p2"), _ref(m, c, "o")])
    p = sc._point(b, "p2", {})
    assert abs(math.hypot(p[0] - c.params["x"], p[1] - c.params["y"])
               - c.params["radius"]) < 1e-4


def test_auto_constrain(app):
    m = DocumentModel()
    a = m.add_node("line", dict(x1=0, y1=0, x2=40, y2=1))
    m.add_node("line", dict(x1=40.2, y1=1, x2=40.5, y2=30))
    assert sc.auto_constrain(m, m.root) == 3
    assert a.params["y1"] == pytest.approx(a.params["y2"], abs=1e-4)


def test_constraints_survive_save_and_load(app, tmp_path):
    m = DocumentModel()
    a, b = _lines(m)
    sc.add(m, m.root, "parallel", [_ref(m, a, "l"), _ref(m, b, "l")])
    path = str(tmp_path / "c.kcad")
    document.save_kcad(m, path)
    m2 = DocumentModel()
    document.load_kcad(m2, path)
    assert sc.rows(m2.root) == sc.rows(m.root)


def test_a_deleted_shape_drops_its_constraints(app):
    m = DocumentModel()
    a, b = _lines(m)
    sc.add(m, m.root, "parallel", [_ref(m, a, "l"), _ref(m, b, "l")])
    m.remove_node(b)
    sc.refresh(m)
    assert sc.rows(m.root) == []


# ------------------------------------------------- the 2D view's tools
@pytest.fixture
def view(app):
    from khervecad.view2d import SketchScene, SketchView
    scene = SketchScene(DocumentModel())
    scene.snap_enabled = False
    v = SketchView(scene)
    v.resize(600, 500)
    v.show()
    v.centerOn(20, 15)
    yield v
    v.close()


def _click(view, x, y):
    QTest.mouseClick(view.viewport(), Qt.LeftButton, Qt.NoModifier,
                     view.mapFromScene(QPointF(x, y)))


def test_click_tools_add_constraints(view):
    m = view.scene().model
    a, b = _lines(m)
    view.set_tool(ui.tool_of("horizontal"))
    _click(view, 20, 1.5)                 # on line a, away from its ends
    assert [r["kind"] for r in sc.rows(m.root)] == ["horizontal"]
    view.set_tool(ui.tool_of("coincident"))
    _click(view, a.params["x2"], a.params["y2"])
    _click(view, b.params["x1"], b.params["y1"])
    assert sc.rows(m.root)[-1]["kind"] == "coincident"
    assert abs(a.params["x2"] - b.params["x1"]) < 1e-4
    view.scene().ask_value = lambda kind, measured: "33"
    view.set_tool(ui.tool_of("length"))
    _click(view, (a.params["x1"] + a.params["x2"]) / 2, a.params["y1"])
    assert abs(_len(a) - 33) < 1e-4
    view.viewport().repaint()             # the glyphs paint


def test_ribbon_has_a_constraints_panel(app):
    from khervecad import ribbon
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        keys = dict((k, p) for k, _f, _s, p in ribbon.TABS)["sketch"]
        assert "sketch_constrain" in keys
        _t, acts = ribbon.panel_actions(win, "sketch_constrain")
        data = [a.data() for a in acts]
        assert data[0] == "con_delete"            # the first icon
        assert data[-2:] == ["con_auto", "con_list"]
        # Equal is among the icons the Fusion panel shows (it was 9th
        # of 8 shown, hidden in the drop-down)
        assert data.index("con_equal") < ribbon.PANEL_SHOWN[
            "sketch_constrain"]
        for kind, _g in ui.TOOLS:
            assert ui.tool_of(kind) in data
        _t, create = ribbon.panel_actions(win, "sketch")
        assert not any(str(a.data()).startswith("con_") for a in create)
        next(a for a in acts if a.data() == "con_parallel").trigger()
        assert win.view2d.scene().tool == "con_parallel"
    finally:
        win._dirty = False
        win.close()


def test_mcp_sketch_constraint(app):
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    win = MainWindow()
    try:
        ex = McpToolExecutor(win)
        m = win.model
        a, b = _lines(m)
        ia, ib = m.root.children.index(a), m.root.children.index(b)
        out = ex.execute("sketch_constraint", dict(
            action="add", kind="perpendicular",
            refs=["%d.l" % ia, "%d.l" % ib]))
        assert "error" not in out, out
        assert out["constraints"][0]["kind"] == "perpendicular"
        assert {s["index"] for s in out["shapes"]} >= {ia, ib}
        bad = ex.execute("sketch_constraint", dict(
            action="add", kind="parallel",
            refs=["%d.l" % ia, "%d.l" % ib]))
        assert "error" in bad
        out = ex.execute("sketch_constraint", dict(action="list"))
        assert len(out["constraints"]) == 1 and out["dof"] == 7
    finally:
        win._dirty = False
        win.close()


def test_marks_on_one_spot_sit_side_by_side(view):
    m = view.scene().model
    a, b = _lines(m)
    sc.add(m, m.root, "horizontal", [_ref(m, a, "l")])
    sc.add(m, m.root, "equal", [_ref(m, a, "l"), _ref(m, b, "l")])
    marks, _font = ui.glyphs(view)
    on_a = sorted((r for r, t, _c, i in marks if t in ("H", "=")
                   and abs(r.center().y() - marks[0][0].center().y()) < 1),
                  key=lambda r: r.left())
    assert len(on_a) == 2
    assert on_a[1].left() >= on_a[0].right()         # no overlap
    view.viewport().repaint()


def test_delete_tool_removes_the_clicked_constraint(view):
    m = view.scene().model
    a, b = _lines(m)
    sc.add(m, m.root, "horizontal", [_ref(m, a, "l")])
    sc.add(m, m.root, "parallel", [_ref(m, a, "l"), _ref(m, b, "l")])
    marks, _f = ui.glyphs(view)
    rect = next(r for r, t, _c, _i in marks if t == "H")
    view.set_tool(ui.DELETE)
    QTest.mouseClick(view.viewport(), Qt.LeftButton, Qt.NoModifier,
                     rect.center().toPoint())
    assert [r["kind"] for r in sc.rows(m.root)] == ["parallel"]


def test_a_typed_value_holds_and_the_rest_follows(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        m = win.model
        p = m.add_node("polygon", dict(points=[[0, 0], [40, 0], [20, 30]]))
        sc.add(m, m.root, "horizontal", [_ref(m, p, "e1")])
        pts = [list(q) for q in p.params["points"]]
        pts[2] = [25, 35]
        m.set_param(p, "points", pts)            # as Properties does
        assert p.params["points"][2] == pytest.approx([25, 35], abs=1e-2)
        assert p.params["points"][1][1] == pytest.approx(35, abs=1e-2)
    finally:
        win._dirty = False
        win.close()
