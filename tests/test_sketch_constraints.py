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
from PyQt5.QtCore import QPoint, QPointF, Qt
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
        assert data[:2] == ["con_dimension", "con_delete"]
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


def test_constraints_survive_the_openscad_program(app):
    """Export / import / Apply code went through the program, which
    dropped them (the user: lost when calling the file back)."""
    from khervecad import scadparse
    m = DocumentModel()
    o = m.add_node("component", {})
    d = m.add_node("difference", {}, parent=o)
    e = m.add_node("linear_extrude", {}, parent=d)
    m.add_node("polygon", dict(points=[[0, 0], [40, 3], [20, 30]]),
               parent=e)
    sc.add(m, e, "horizontal", ["0.e0"])
    a, b = _lines(m)
    sc.add(m, m.root, "parallel", [_ref(m, a, "l"), _ref(m, b, "l")])
    root, warnings = scadparse.parse_scad(m.to_scad())
    assert not warnings
    ext = next(n for n in root.walk() if n.type == "linear_extrude")
    assert sc.rows(ext) == sc.rows(e)
    assert [c.type for c in ext.children] == ["polygon"]   # no marker
    assert sc.rows(root) == sc.rows(m.root)


def test_sketch_dimension_tool(view, monkeypatch):
    monkeypatch.setattr(sc, "scale_first_enabled", lambda: False)
    m = view.scene().model
    a, b = _lines(m)
    c = m.add_node("circle", dict(x=20, y=-15, radius=4))
    answers = iter(["33", "10", "45"])
    view.scene().ask_value = lambda kind, measured: next(answers)
    view.set_tool(ui.DIMENSION)
    # a line, then empty paper: its length
    _click(view, 20, 1.5)
    _click(view, 60, -30)
    assert abs(_len(a) - 33) < 1e-3
    # a circle: its diameter at once
    _click(view, 24, -15)
    assert c.params["radius"] == pytest.approx(5)
    kinds = [r["kind"] for r in sc.rows(m.root)]
    assert kinds == ["length", "diameter"]
    # and the selection's sizes are drawn while the tool is on
    view.scene().clearSelection()
    view.viewport().repaint()


def test_polygon_sides_are_dimensioned_when_selected(view):
    m = view.scene().model
    p = m.add_node("polygon", dict(points=[[0, 0], [30, 0], [30, 10],
                                           [0, 10]]))
    from khervecad.view2d import PolygonShapeItem
    view.set_tool("select")
    QApplication.processEvents()
    for it in view.scene().items():
        if isinstance(it, PolygonShapeItem) and it.node is p:
            it.setSelected(True)
    drawn = []
    orig = type(view)._draw_dim
    type(view)._draw_dim = lambda self, painter, a, b, **k: drawn.append(
        k.get("text"))
    try:
        view.viewport().repaint()
    finally:
        type(view)._draw_dim = orig
    assert len([t for t in drawn if t]) == 4      # one per side


def test_no_finish_button_and_a_tab_leaves_the_sketch(app):
    from khervecad import sketch_mode, toolbar_style
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    try:
        toolbar_style.apply(win, "Fusion")
        sketch_mode.enter(win)
        assert sketch_mode.sketching(win)
        b = getattr(win, "_finish_sketch", None)
        assert b is None or not b.isVisible()
        win.ribbon.show_tab("features")
        assert not sketch_mode.sketching(win)
    finally:
        toolbar_style.apply(win, "KherveCAD")
        win._dirty = False
        win.close()


def test_constraints_never_become_a_difference_body(app):
    """They were a kcad_constraints(...) CALL first in the block: inside
    a difference() that call was the (empty) body, and the user's whole
    part rendered empty in OpenSCAD. Now an assignment, no geometry."""
    from khervecad import scadparse
    m = DocumentModel()
    d = m.add_node("difference", {})
    m.add_node("polygon", dict(points=[[0, 0], [40, 3], [20, 30]]),
               parent=d)
    m.add_node("circle", dict(x=20, y=10, radius=3), parent=d)
    sc.add(m, d, "horizontal", ["0.e0"])
    code = m.to_scad()
    line = next(l for l in code.splitlines() if "kcad_constraints" in l)
    assert line.strip().startswith("kcad_constraints = ")
    root, warnings = scadparse.parse_scad(code)
    assert not warnings
    diff = next(n for n in root.walk() if n.type == "difference")
    assert [c.type for c in diff.children] == ["polygon", "circle"]
    assert sc.rows(diff) == sc.rows(d)


def test_every_shape_shows_its_sizes(view):
    """Show Dimensions labels every shape, not only the selection."""
    m = view.scene().model
    m.add_node("rect", dict(width=30, height=20))
    m.add_node("circle", dict(x=50, y=10, radius=8))
    QApplication.processEvents()
    drawn = []
    orig = type(view)._draw_dim
    orig_s = type(view)._dim_screen
    type(view)._draw_dim = lambda self, p, a, b, **k: drawn.append(
        k.get("text"))
    type(view)._dim_screen = lambda self, p, a, b, **k: drawn.append(
        k.get("text"))
    try:
        view.scene().show_dims = True
        view.viewport().repaint()
        texts = [t for t in drawn if t]
        assert any("30" in t for t in texts)
        assert any("20" in t for t in texts)
        assert any("16" in t for t in texts)          # the circle's Ø
        drawn.clear()
        view.scene().show_dims = False
        view.viewport().repaint()
        assert not [t for t in drawn if t]
    finally:
        type(view)._draw_dim = orig
        type(view)._dim_screen = orig_s


def test_first_dimension_scales_the_whole_sketch(app, monkeypatch):
    """SolidWorks' scale-on-first-dimension: dimension one side and the
    whole sketch follows in proportion; the next dimension drives only
    its own shape."""
    monkeypatch.setattr(sc, "scale_first_enabled", lambda: True)
    m = DocumentModel()
    a = m.add_node("line", dict(x1=0, y1=0, x2=10, y2=0))
    c = m.add_node("circle", dict(x=20, y=0, radius=2))
    report, scaled = sc.add_dimension(m, m.root, "length",
                                      [_ref(m, a, "l")], 30)
    assert scaled
    assert _len(a) == pytest.approx(30)
    assert c.params["x"] == pytest.approx(60)            # in proportion
    assert c.params["radius"] == pytest.approx(6)
    _r, scaled = sc.add_dimension(m, m.root, "radius",
                                  [_ref(m, c, "o")], 4)
    assert not scaled and _len(a) == pytest.approx(30)
    assert c.params["radius"] == pytest.approx(4)


def test_add_dimension_is_the_sketch_dimension(view):
    view.set_tool("dimension")
    assert view.scene().tool == ui.DIMENSION


def test_dimension_twice_edits_and_drags_out_of_the_way(view, monkeypatch):
    """The same line dimensioned again changes its dimension (two on top
    of each other hid both), and the select tool drags a dimension."""
    from khervecad import dim_edit
    monkeypatch.setattr(sc, "scale_first_enabled", lambda: False)
    m = view.scene().model
    a, _b = _lines(m)
    answers = iter(["33", "25"])
    view.scene().ask_value = lambda kind, measured: next(answers)
    view.set_tool(ui.DIMENSION)
    _click(view, 20, 1.5)
    _click(view, 60, -30)
    _click(view, 20, 1.5)
    _click(view, 60, -30)
    rows = sc.rows(m.root)
    assert [r["kind"] for r in rows] == ["length"]
    assert abs(_len(a) - 25) < 1e-3
    view.set_tool("select")
    view.viewport().repaint()
    QApplication.processEvents()
    rect, _ctx = next(h for h in view._dim_hits
                      if h[1][1] == "constraint")
    start = rect.center().toPoint()
    assert dim_edit.press(view, start)
    end = start + QPoint(0, 60)
    dim_edit.move(view, end)
    assert dim_edit.release(view, end)
    assert abs(sc.rows(m.root)[0]["offset"]) > 0
    assert getattr(view, "_dim_editor", None) is None   # dragged, not typed


def test_diameter_value_drags_out_of_the_way(view, monkeypatch):
    from khervecad import dim_edit
    monkeypatch.setattr(sc, "scale_first_enabled", lambda: False)
    m = view.scene().model
    m.add_node("circle", dict(x=20, y=-15, radius=4))
    view.scene().ask_value = lambda kind, measured: "10"
    view.set_tool(ui.DIMENSION)
    _click(view, 24, -15)
    view.set_tool("select")
    view.viewport().repaint()
    QApplication.processEvents()
    rect, _ctx = next(h for h in view._dim_hits
                      if h[1][1] == "constraint")
    start = rect.center().toPoint()
    assert dim_edit.press(view, start)
    end = start + QPoint(50, -30)
    dim_edit.move(view, end)
    dim_edit.release(view, end)
    moved = sc.rows(m.root)[0]["label_offset"]
    assert moved[0] > 0 and moved[1] < 0
    view.viewport().repaint()
    QApplication.processEvents()
    rect2, _ = next(h for h in view._dim_hits if h[1][1] == "constraint")
    assert abs(rect2.center().x() - end.x()) < 3
    # drawn as a radius-style leader from the circle's centre (its own
    # painter), not a loose mark
    assert not view._dim_leaders


def test_each_object_shows_only_its_own_dimensions(view):
    """Dimensions belong to their Object: both parts' show on the view,
    and the Object tab shows only the active one's."""
    m = view.scene().model
    parts = []
    for i in range(2):
        obj = m.add_node("union", {}, name="Part %d" % i)
        line = m.add_node("line", dict(x1=0, y1=i * 50, x2=30,
                                       y2=i * 50), parent=obj)
        sc.add(m, obj, "length", [sc.ref_of(obj, line, "l")], 30 + i)
        parts.append(obj)
    view.scene().rebuild()
    QApplication.processEvents()
    assert ui.shown_containers(view.scene()) == parts
    view.scene().isolation_resolver = lambda: parts[0]
    assert ui.shown_containers(view.scene()) == [parts[0]]


def test_an_objects_hidden_definition_keeps_its_dimensions(view):
    """An Object's definition is hidden by design; edited in the Object
    tab, its sketch dimensions still show (they had vanished)."""
    m = view.scene().model
    obj = m.add_node("component", {}, name="Object 1")
    obj.visible = False
    line = m.add_node("line", dict(x1=0, y1=0, x2=30, y2=0), parent=obj)
    sc.add(m, obj, "length", [sc.ref_of(obj, line, "l")], 30)
    view.scene().isolation_resolver = lambda: obj
    view.scene().rebuild()
    QApplication.processEvents()
    assert ui.shown_containers(view.scene()) == [obj]


def test_dimensions_follow_their_shapes_into_an_extrude():
    """Extruded Boss on a dimensioned sketch keeps the dimensions: they
    move onto the extrude with the shapes."""
    m = DocumentModel()
    obj = m.add_node("union", {}, name="Plate")
    other = m.add_node("line", dict(x1=0, y1=50, x2=10, y2=50), parent=obj)
    rect = m.add_node("rect", dict(x=0, y=0, width=50, height=20),
                      parent=obj)
    sc.add(m, obj, "length", [sc.ref_of(obj, rect, "e0")], 50)
    sc.add(m, obj, "horizontal", [sc.ref_of(obj, other, "l")])
    ext = m.wrap_nodes([rect], "linear_extrude")
    assert [r["kind"] for r in sc.rows(ext)] == ["length"]
    assert sc.rows(ext)[0]["refs"] == ["0.e0"]
    assert [r["kind"] for r in sc.rows(obj)] == ["horizontal"]
    assert sc.rows(obj)[0]["refs"] == ["0.l"]
    sc.set_value(m, ext, 0, 70)
    assert rect.params["width"] == pytest.approx(70, abs=1e-3)


def test_smart_dimension_gives_a_slots_end_radius(view, monkeypatch):
    """The user's SolidWorks slot: Smart Dimension on a slot's round end
    is its radius from that end's centre (R8 makes it 16 wide), and its
    straight length is centre to centre."""
    monkeypatch.setattr(sc, "scale_first_enabled", lambda: False)
    m = view.scene().model
    slot = m.add_node("line", dict(x1=0, y1=0, x2=24, y2=0, width=10))
    answers = iter(["8", "30"])
    view.scene().ask_value = lambda kind, measured: next(answers)
    view.set_tool(ui.DIMENSION)
    QApplication.processEvents()
    _click(view, 29, 0)                   # on the right round end
    rows = sc.rows(m.root)
    assert [r["kind"] for r in rows] == ["radius"]
    assert rows[0]["refs"] == ["0.a2"]
    assert slot.params["width"] == pytest.approx(16, abs=1e-3)
    _click(view, 12, 0)                   # the centre line…
    _click(view, 60, -40)                 # …then empty paper: its length
    assert math.hypot(slot.params["x2"] - slot.params["x1"],
                      slot.params["y2"] - slot.params["y1"]) == \
        pytest.approx(30, abs=1e-3)
    assert slot.params["width"] == pytest.approx(16, abs=1e-3)


def test_a_slot_radius_drags_and_retypes_under_smart_dimension(view,
                                                             monkeypatch):
    """SolidWorks: with Smart Dimension still on, an R value is dragged
    out of the sketch (its leader follows) or clicked to retype."""
    from khervecad import dim_edit
    monkeypatch.setattr(sc, "scale_first_enabled", lambda: False)
    m = view.scene().model
    slot = m.add_node("line", dict(x1=0, y1=0, x2=24, y2=0, width=10))
    view.scene().ask_value = lambda kind, measured: "8"
    view.set_tool(ui.DIMENSION)
    QApplication.processEvents()
    _click(view, 29, 0)
    view.viewport().repaint()
    QApplication.processEvents()
    rect, _ctx = next(h for h in view._dim_hits if h[1][1] == "constraint")
    start = rect.center().toPoint()
    assert dim_edit.press(view, start)          # tool still Smart Dim
    end = start + QPoint(40, 30)
    dim_edit.move(view, end)
    dim_edit.release(view, end)
    assert sc.rows(m.root)[0].get("label_offset")
    view.viewport().repaint()
    QApplication.processEvents()
    rect2, _ = next(h for h in view._dim_hits if h[1][1] == "constraint")
    assert abs(rect2.center().x() - end.x()) < 3
    # a click without moving opens the value box
    p2 = rect2.center().toPoint()
    assert dim_edit.press(view, p2) and dim_edit.release(view, p2)
    box = view._dim_editor
    box.setText("6")
    box.editingFinished.emit()
    assert slot.params["width"] == pytest.approx(12, abs=1e-3)


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    yield win
    win._dirty = False
    win.close()


def test_smart_dimension_to_the_face_edge(window, monkeypatch):
    """The user's sketch on a face: a new rectangle dimensioned to the
    face's bottom edge — which is not a sketch shape. The edge becomes a
    fixed construction reference and the distance between the two
    parallel edges drives the rectangle."""
    from khervecad import face_sketch
    from PyQt5.QtCore import QPointF
    monkeypatch.setattr(sc, "scale_first_enabled", lambda: False)
    m = window.model
    block = m.add_node("cube", dict(width=80, depth=40, height=10))
    for _ in range(3):
        QApplication.processEvents()
    group = face_sketch.make(window, block, (40.0, 20.0, 10.0),
                             (0.0, 0.0, 1.0))
    # the sketch's 0, 0 is the part origin seen on the face (40, 20 off
    # the click), so the click-relative numbers shift by it
    rect = m.add_node("rect", dict(x=10, y=15, width=20, height=15),
                      parent=group)
    scene = window.view2d.scene()
    scene.rebuild()
    QApplication.processEvents()
    scene.ask_value = lambda kind, measured: "8"
    window.view2d.set_tool(ui.DIMENSION)

    class Ev:
        def __init__(self, x, y):
            self._p = QPointF(x, y)

        def scenePos(self):
            return self._p

        def button(self):
            return Qt.LeftButton

        def accept(self):
            pass
    ui.dimension_press(scene, Ev(20.0, 15.0))        # rect bottom edge
    ui.dimension_press(scene, Ev(40.0, 0.0))         # the face's edge
    kinds = [r["kind"] for r in sc.rows(group)]
    assert "point_line" in kinds
    ref = [n for n in group.children if n.name == "Reference edge"]
    assert ref and ref[0].params.get("modifier") == "%"
    assert not ref[0].visible            # hidden once dimensioned
    assert rect.params["y"] == pytest.approx(8, abs=1e-3)     # 8 above
    # it still drives: a new value moves the rectangle again
    i = [r["kind"] for r in sc.rows(group)].index("point_line")
    sc.set_value(m, group, i, 5)
    assert rect.params["y"] == pytest.approx(5, abs=1e-3)
    face_sketch.close(window)


def test_smart_dimensions_hide_and_show_from_both_bars(window):
    """View ▸ Show Smart Dimensions, and its buttons on the 2D and 3D
    bars, are one switch; off, neither view paints a dimension."""
    act = window._smart_dims_act
    assert act.isChecked() and window.scene.show_sketch_dims
    b2 = window.view2d.nav_bar.buttons["dims"]
    b3 = window.view3d.nav_bar.buttons["smart_dims"]
    b3.click()
    assert not act.isChecked()
    assert window.scene.show_sketch_dims is False
    from PyQt5.QtGui import QImage, QPainter
    from khervecad import sketch_dims3d
    img = QImage(10, 10, QImage.Format_ARGB32)
    p = QPainter(img)
    sketch_dims3d.paint(window, p, lambda pt: None)
    p.end()
    assert window._dims3d_hits == []
    b2.click()                       # the 2D button: hidden one shows
    assert act.isChecked() and window.scene.show_sketch_dims


def test_the_2d_dimensions_button_hides_and_shows_both_kinds(window):
    """The user hid with one ruler and showed with the other: the 2D bar
    has one button for automatic sizes and Smart Dimensions together."""
    btn = window.view2d.nav_bar.buttons["dims"]
    assert "smart_dims" not in window.view2d.nav_bar.buttons
    btn.click()
    assert not window.scene.show_dims
    assert not window.scene.show_sketch_dims
    window._smart_dims_act.setChecked(True)     # from the View menu
    assert btn.isChecked()
    btn.click()                      # one of them on: all come back
    assert window.scene.show_dims and window.scene.show_sketch_dims


def test_the_2d_plane_buttons_are_named_like_solidworks(window):
    texts = [window._plane_buttons[p].text()
             for p in ("Front (XZ)", "Top (XY)", "Side (YZ)")]
    assert texts == ["Front", "Top", "Right"]


def test_a_dimension_made_while_hidden_shows_when_shown_again(view,
                                                               monkeypatch):
    """The user: hide dimensions, add a Smart Dimension, show them again
    — it must be drawn."""
    monkeypatch.setattr(sc, "scale_first_enabled", lambda: False)
    m = view.scene().model
    a, _b = _lines(m)
    view.scene().ask_value = lambda kind, measured: "33"
    view.scene().show_sketch_dims = False
    view.set_tool(ui.DIMENSION)
    _click(view, 20, 1.5)
    _click(view, 60, -30)
    assert [r["kind"] for r in sc.rows(m.root)] == ["length"]
    view.scene().show_sketch_dims = True
    from PyQt5.QtGui import QImage, QPainter
    img = QImage(600, 500, QImage.Format_ARGB32)
    p = QPainter(img)
    view._dim_hits = []
    drawn = ui._paint_dimensions(view, p)
    p.end()
    assert drawn, "the dimension is not drawn once shown again"


def test_tangent_moves_the_line_not_the_circle():
    """Drawing a line tangent to a circle: the circle stays put."""
    from khervecad.model import DocumentModel
    from khervecad import sketch_constraints as C
    m = DocumentModel()
    g = m.add_node("union", {})
    c = m.add_node("circle", dict(x=0, y=0, radius=30), parent=g)
    m.add_node("line", dict(x1=-25, y1=5, x2=-10, y2=80), parent=g)
    C.add(m, g, "tangent", ["1.l", "0.o"])
    assert abs(c.params["x"]) < 1e-3 and abs(c.params["y"]) < 1e-3
    assert abs(c.params["radius"] - 30) < 1e-3


def _move(view, x, y):
    QTest.mouseMove(view.viewport(), view.mapFromScene(QPointF(x, y)))
    from PyQt5.QtGui import QMouseEvent
    from PyQt5.QtCore import QEvent
    pos = view.mapFromScene(QPointF(x, y))
    QApplication.sendEvent(view.viewport(), QMouseEvent(
        QEvent.MouseMove, QPointF(pos), Qt.NoButton, Qt.NoButton,
        Qt.NoModifier))


def _on_circle(c, deg):
    r = c.params["radius"]
    return (c.params["x"] + r * math.cos(math.radians(deg)),
            c.params["y"] + r * math.sin(math.radians(deg)))


def test_join_two_circles_with_tangent_lines_by_clicking(view):
    """The user's lever: two circles, two lines, each line's ends put ON
    the circles with Coincident and made Tangent to both, all by clicks
    — the circles never move, and the outline is one region."""
    from khervecad import sketch_regions as R
    m = view.scene().model
    big = m.add_node("circle", dict(x=0, y=0, radius=20))
    small = m.add_node("circle", dict(x=0, y=60, radius=12))
    left = m.add_node("line", dict(x1=-24, y1=4, x2=-16, y2=57, width=2))
    right = m.add_node("line", dict(x1=23, y1=3, x2=15, y2=58, width=2))
    view.centerOn(0, 30)
    view.resetTransform()
    view.scale(4, 4)
    for line, side in ((left, 180), (right, 0)):
        view.set_tool(ui.tool_of("coincident"))
        p1 = sc._point(line, "p1", {})
        _move(view, *p1)
        assert view.scene()._con_hover[1] == "p1"     # the end lights up
        view.viewport().repaint()
        _click(view, *p1)
        spot = _on_circle(big, side + (25 if side else -25))
        _move(view, *spot)
        assert view.scene()._con_hover[0] is big      # then the circle
        _click(view, *spot)
        assert sc.rows(m.root)[-1]["kind"] == "point_on"
        p2 = sc._point(line, "p2", {})
        _click(view, *p2)
        _click(view, *_on_circle(small, side + (40 if side else -40)))
        for c, end in ((big, "p1"), (small, "p2")):
            view.set_tool(ui.tool_of("tangent"))
            a, b = sc._line(line, "l", {})
            _click(view, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            _click(view, *_on_circle(c, side + (90 if c is big else 60)
                                     * (1 if side == 0 else -1)))
            assert sc.rows(m.root)[-1]["kind"] == "tangent"
    for c, x, y, r in ((big, 0, 0, 20), (small, 0, 60, 12)):
        assert (abs(c.params["x"] - x) < 1e-3 and abs(c.params["y"] - y)
                < 1e-3 and abs(c.params["radius"] - r) < 1e-3)
        for line in (left, right):
            dist = sc._pl_dist((x, y), sc._line(line, "l", {}))
            assert abs(abs(dist) - r) < 1e-3       # tangent
    for line, c, end in ((left, big, "p1"), (left, small, "p2"),
                         (right, big, "p1"), (right, small, "p2")):
        p = sc._point(line, end, {})
        assert abs(math.hypot(p[0] - c.params["x"], p[1] - c.params["y"])
                   - c.params["radius"]) < 1e-3   # its end on the circle
    f = R.faces(R.shapes_of(m.root))
    assert R.face_at(f, (0, 30)) is not None


def test_coincident_picks_a_curve_first_too(view):
    m = view.scene().model
    c = m.add_node("circle", dict(x=0, y=0, radius=10))
    line = m.add_node("line", dict(x1=30, y1=0, x2=40, y2=10))
    view.centerOn(15, 0)
    view.set_tool(ui.tool_of("coincident"))
    _click(view, 0, -10)                  # the circle first
    _click(view, 30, 0)                   # then the line's end
    row = sc.rows(m.root)[-1]
    assert row["kind"] == "point_on" and row["refs"] == ["1.p1", "0.o"]
    assert abs(c.params["x"]) < 1e-3
