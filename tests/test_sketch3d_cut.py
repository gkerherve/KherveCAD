"""Extruded Cut drawn on the face in the 3D view (2026-11-01, the user).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import analysis, cut_feature, mesh, sketch3d
from khervecad.mainwindow import MainWindow
from khervecad.mcp_tools import McpToolExecutor


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app):
    w = MainWindow()
    yield w
    w._dirty = False
    w.close()


def test_straighten_snaps_level_and_upright():
    assert sketch3d.straighten((0, 0), (10, 0.5)) == (10, 0)
    assert sketch3d.straighten((0, 0), (0.5, 10)) == (0, 10)
    assert sketch3d.straighten((0, 0), (10, 10)) == (10, 10)


def test_a_slot_drawn_in_3d_is_cut_on_done(win, monkeypatch):
    monkeypatch.setattr(cut_feature, "IN_3D", True)
    McpToolExecutor(win).execute("apply_code",
                                 {"code": "cube([40, 30, 20]); // Block\n"})
    QApplication.processEvents()
    m = win.model
    part = next(c for c in m.root.children if c.visible and c.type != "assign")
    full = analysis.mass_properties(mesh.tessellate(m.root))["volume"]
    cut_feature.start(win, "extruded_cut")
    win.view3d._pick_cb(dict(kind="face", pos=(20, 15, 20),
                             dir=(0, 0, 1)), part)
    tool = win.view3d.edit_tool
    assert isinstance(tool, sketch3d.Sketch3DTool)
    assert not getattr(win, "_face_sketch", None)     # no 2D view
    tool.set_mode("slot")
    tool.place((10, 10))
    tool.place((30, 10.5))                            # snaps level
    slot = tool.place((20, 13))
    assert slot.params["slot"] and slot.params["y2"] == slot.params["y1"]
    assert win.view3d.edit_tool is not tool           # the feature is made
    assert any(n.type == "difference" for n in m.root.walk())
    QApplication.processEvents()
    left = analysis.mass_properties(mesh.tessellate(m.root))["volume"]
    assert left < full - 100


def _on_face(win, monkeypatch):
    monkeypatch.setattr(cut_feature, "IN_3D", True)
    McpToolExecutor(win).execute("apply_code",
                                 {"code": "cube([40, 30, 20]); // Block\n"})
    QApplication.processEvents()
    part = next(c for c in win.model.root.children
                if c.visible and c.type != "assign")
    cut_feature.start(win, "extruded_cut")
    win.view3d._pick_cb(dict(kind="face", pos=(20, 15, 20),
                             dir=(0, 0, 1)), part)
    return win.view3d.edit_tool


def test_the_sketch_icons_drive_it_and_no_bar_shows(win, monkeypatch):
    from PyQt5.QtWidgets import QPushButton
    from khervecad import sketch_tools
    tool = _on_face(win, monkeypatch)
    assert not win.view3d.findChildren(QPushButton, "sketch3d_bar")
    win._set_tool(sketch_tools.SLOT)
    assert tool.mode == "slot" and win.view3d.edit_tool is tool
    win._set_tool("circle")
    assert tool.mode == "circle"
    tool.finish()


def test_snaps_to_a_middle_and_lights_the_edge(win, monkeypatch):
    tool = _on_face(win, monkeypatch)
    win.view3d.resize(800, 600)
    win.view3d.fit()
    mids = [p for p in tool.info["points"] if p[2] == "middle"]
    assert mids
    x, y, _k = mids[0]
    got = tool.snap_local(x + 0.05, y + 0.05)
    assert got == (x, y) and tool.snapped[2] == "middle" and tool.lit
    tool.finish()


def test_what_was_drawn_can_be_seen(win, monkeypatch):
    tool = _on_face(win, monkeypatch)
    tool.set_mode("line")
    tool.place((5, 5))
    tool.place((15, 12))
    assert len(tool._own()[0]) == 1          # one line, not a band's sides
    tool.finish()


def test_a_3d_line_is_a_sketch_line_that_closes_with_the_edges(win,
                                                               monkeypatch):
    """Thin and joined, like the 2D Line, and left open it asks which area
    it closes with the model's edges (the user)."""
    from khervecad import sketch_constraints as sc, sketch_regions
    tool = _on_face(win, monkeypatch)
    asked = []
    monkeypatch.setattr(sketch_regions, "start_3d",
                        lambda w, g, cut=False, **k: asked.append(cut) or True)
    tool.set_mode("line")
    for p in ((5, 5), (15, 5), (15, 12)):
        tool.place(p)
    lines = [n for n in tool.group.children if n.type == "line"]
    assert [n.params["width"] for n in lines] == [0.2, 0.2]
    assert [r["kind"] for r in sc.rows(tool.group)].count("coincident") == 1
    tool.finish()
    assert asked == [True]


def test_lines_ending_on_the_edge_close_an_area_with_it(win, monkeypatch):
    """Three lines from the block's edge and back cut out exactly that."""
    from PyQt5.QtTest import QTest
    from khervecad import extrude_panel, face_sketch as fs
    tool = _on_face(win, monkeypatch)
    g = tool.group
    tool.set_mode("line")
    for p in ((25, 0), (25, 12), (15, 12), (15, 0)):
        tool.place(fs.to_local(g, (p[0], p[1], 20)))
    tool.finish()
    QTest.qWait(50)                      # one click: the window, for a cut
    panel = extrude_panel._panel(win)
    assert panel is not None and not panel.isHidden()
    ext = panel.ext
    assert extrude_panel.is_cut(ext) and ext.params["reverse"]
    assert ext.params["height"] == 10 and not ext.params.get("extent")
    # its direction can be turned round there
    panel.fields["reverse"].click()
    QApplication.processEvents()
    assert not ext.params.get("reverse")
    panel.fields["reverse"].click()
    QApplication.processEvents()
    hits = McpToolExecutor(win).execute("probe_surface", {
        "from": [20, 6, 50], "direction": [0, 0, -1]})["hits"]
    assert not any(abs(h["point"][2] - 20) < 1e-3 for h in hits)


def test_the_extrude_window_opens_on_the_first_shape(win, monkeypatch):
    """The window the user already knows, not another one."""
    from khervecad import drag_feature, extrude_panel
    from khervecad import sketch_constrain_ui as ui
    tool = _on_face(win, monkeypatch)
    tool.place((5, 5))
    tool.place((15, 12))
    drag = win.view3d.edit_tool
    assert isinstance(drag, drag_feature.DragFeature)
    panel = extrude_panel._panel(win)
    assert panel is not None and not panel.isHidden()
    ext = drag.target()
    assert not ext.params.get("extent")          # one side, blind
    assert ext.params["height"] == 10 and ext.params["reverse"]
    # Smart Dimension with the window open, and back
    win._set_tool(ui.DIMENSION)
    assert win.view3d.edit_tool is not drag
    assert extrude_panel._panel(win) is panel
    # another shape joins the same extrude
    win._set_tool("circle")
    sk = win.view3d.edit_tool
    assert isinstance(sk, sketch3d.Sketch3DTool) and sk.holder is ext
    sk.place((20, 5))
    sk.place((22, 5))
    assert len(ext.children) == 2
    sk.finish()
    assert win.view3d.edit_tool is drag
    drag.cancel()                                    # all of it goes
    assert not any(n.type == "difference" for n in win.model.root.walk())
    assert win.view3d.edit_tool is None


def test_a_circle_at_a_sloped_faces_centre_follows_it(win, monkeypatch):
    """The user's circle on the rib's slope: 40 -> 45 left it behind."""
    from khervecad import face_outline, face_sketch, model_refs
    tool = None
    McpToolExecutor(win).execute("apply_code", {"code":
        "rotate([90, 0, 0]) linear_extrude(height=10) "
        "polygon(points=[[0, 0], [40, 0], [0, 30]]); // Rib\n"})
    QApplication.processEvents()
    m = win.model
    part = next(c for c in m.root.children if c.visible and c.type != "assign")
    poly = next(n for n in m.root.walk() if n.type == "polygon")
    n = (30 / 50, 0.0, 40 / 50)                      # the slope's normal
    g = face_sketch.make(win, part, (20, -5, 15), n, open_2d=False)
    assert g.params.get(face_sketch.FACE_REF)
    tool = sketch3d.Sketch3DTool(win, "circle")
    tool.use_group(g)
    cx, cy, kind = next(p for p in tool.info["points"]
                        if p[2] == "face centre")
    tool.place((cx, cy))
    circle = tool.place((cx + 3, cy)) or g.children[0]
    tool._end()
    m.set_param(poly, "points", [[0, 0], [60, 0], [0, 30]])
    QApplication.processEvents()
    model_refs.refresh(win)
    p = circle.params
    w = face_sketch.to_world(g, float(p["x"]), float(p["y"]))
    assert w[0] == pytest.approx(30, abs=0.01)
    assert w[1] == pytest.approx(-5, abs=0.01)
    assert w[2] == pytest.approx(15, abs=0.01)


def test_choosing_a_face_turns_the_camera_to_it(win, monkeypatch):
    from khervecad import face_sketch
    from khervecad import view_anim
    goals = []
    glide = view_anim.glide_3d
    monkeypatch.setattr(view_anim, "glide_3d", lambda view, goal, **kw: (
        goals.append(goal), glide(view, goal, **kw)))
    tool = _on_face(win, monkeypatch)
    want = face_sketch.camera_for((0, 0, 1))
    assert len(goals) == 1                      # it glides, not jumps
    assert (goals[0]["yaw"], goals[0]["pitch"]) == pytest.approx(want)
    tool.finish()


def test_the_chosen_face_is_green_until_the_window_closes(win, monkeypatch):
    monkeypatch.setattr(cut_feature, "IN_3D", True)
    McpToolExecutor(win).execute("apply_code", {"code": "cube(20);\n"})
    QApplication.processEvents()
    part = next(c for c in win.model.root.children
                if c.visible and c.type != "assign")
    cut_feature.start(win, "extruded_cut")
    face = [((0, 0, 20), (20, 0, 20), (20, 20, 20))]
    win.view3d._pick_cb(dict(kind="face", pos=(10, 10, 20), dir=(0, 0, 1),
                             tris=face), part)
    tool = win.view3d.edit_tool
    assert win._chosen_face == face
    tool.place((5, 5))
    tool.place((15, 12))
    drag = win.view3d.edit_tool
    assert win._chosen_face == face              # still, with the window
    drag.ok()
    assert not win._chosen_face


@pytest.mark.parametrize("how", ["param", "mirror"])
def test_a_reversed_extrude_is_pulled_along_its_arrow(win, how):
    from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt
    from PyQt5.QtGui import QMouseEvent
    from khervecad import drag_feature
    m = win.model
    ext = m.add_node("linear_extrude", dict(height=10))
    m.add_node("rect", dict(width=20, height=20), parent=ext)
    if how == "param":
        ext.params["reverse"] = True
    else:
        drag_feature.set_direction(m, ext, True)
    QApplication.processEvents()
    win.view3d.resize(800, 600)
    win.view3d.fit()
    tool = drag_feature.DragFeature(win, ext)
    scr = tool._screen()

    def event(kind, x, y):
        return QMouseEvent(kind, QPointF(x, y), Qt.LeftButton, Qt.LeftButton,
                           Qt.NoModifier)
    ax, ay = scr["a"][:2]
    bx, by = scr["b"][:2]
    assert tool.mouse_press(event(QEvent.MouseButtonPress, ax, ay))
    tool.mouse_move(event(QEvent.MouseMove, ax + (bx - ax),
                          ay + (by - ay)))           # along the arrow
    deeper = tool.drag["value"]
    assert deeper > 10
    tool.mouse_move(event(QEvent.MouseMove, ax - (bx - ax) * 0.2,
                          ay - (by - ay) * 0.2))     # back against it
    assert tool.drag["value"] < 10
    tool.drag = None


@pytest.mark.parametrize("kind", ["extruded_cut", "extruded_boss"])
def test_smart_dimension_with_the_window_open(win, monkeypatch, kind):
    """A size, and a distance to the model's edge, while extruding."""
    from khervecad import drag_feature, extrude_panel, face_sketch
    from khervecad import sketch_constrain_ui as ui
    monkeypatch.setattr(cut_feature, "IN_3D", True)
    McpToolExecutor(win).execute("apply_code",
                                 {"code": "cube([40, 30, 20]); // Block\n"})
    QApplication.processEvents()
    part = next(c for c in win.model.root.children
                if c.visible and c.type != "assign")
    win.view3d.resize(800, 600)
    win.view3d.fit()
    cut_feature.start(win, kind)
    win.view3d._pick_cb(dict(kind="face", pos=(20, 15, 20),
                             dir=(0, 0, 1)), part)
    sk = win.view3d.edit_tool
    sk.set_mode("circle")
    sk.place((20, 15))
    circle = sk.place((23, 15))
    drag = win.view3d.edit_tool
    assert isinstance(drag, drag_feature.DragFeature)
    assert extrude_panel._panel(win) is not None
    win.view2d.scene().ask_value = lambda k, m: "8"
    win._set_tool(ui.DIMENSION)
    tool = win.view3d.edit_tool
    g = face_sketch.group_of(circle)

    def screen(lx, ly):
        q = tool._project()(face_sketch.to_world(g, lx, ly))
        return q[0], q[1]
    x, y = screen(circle.params["x"] + 3, circle.params["y"])
    tool.click(x, y)
    tool.click(3, 3)                             # empty: its size
    assert circle.params["radius"] == pytest.approx(4)
    # the circle's centre to the block's corner
    assert tool.model_near(*screen(0, 0), circle.parent) is not None
    tool.click(*screen(circle.params["x"], circle.params["y"]))
    tool.click(*screen(0, 0))
    assert any(n.name == "Reference point" for n in circle.parent.children)
    drag.cancel()


def _block_with_cut(win, height=20):
    """A block and a reversed cut going down from its top."""
    m = win.model
    obj = m.add_node("component", {})
    obj.visible = True
    block = m.add_node("cube", dict(width=40, depth=30, height=height),
                         parent=obj)
    shelf = m.add_node("translate", dict(x=0, y=0, z=-20), parent=obj)
    m.add_node("cube", dict(width=40, depth=30, height=5), parent=shelf)
    g = m.add_node("translate", dict(x=0, y=0, z=height), parent=obj)
    ext = m.add_node("linear_extrude", dict(height=10), parent=g)
    ext.params["reverse"] = True
    m.add_node("circle", dict(x=20, y=15, radius=3), parent=ext)
    return block, g, ext


def test_up_to_next_goes_the_way_a_reversed_cut_goes(win):
    from khervecad import extent
    block, g, ext = _block_with_cut(win)
    extent.set_extent(win.model, ext, "up_to_next")
    assert ext.params["height"] == pytest.approx(20)   # the block's bottom
    extent.set_extent(win.model, ext, "through_all_one")
    assert ext.params["height"] > 20


def test_a_picked_surface_and_vertex_follow_a_changed_size(win):
    from khervecad import extent
    block, g, ext = _block_with_cut(win)
    extent.set_extent(win.model, ext, "up_to_face",
                      face=[5, 5, -15, 0, 0, 1])       # the shelf's top
    assert ext.params["height"] == pytest.approx(35)
    shelf = g.parent.children[1]
    win.model.set_param(shelf, "z", -30)               # moved down 10
    extent.refresh(win.model)
    assert ext.params["height"] == pytest.approx(45)
    extent.set_extent(win.model, ext, "up_to_vertex", point=[0, 0, -25])
    win.model.set_param(shelf, "z", -40)
    extent.refresh(win.model)
    assert ext.params["up_to_point"][2] == pytest.approx(-35)
    assert ext.params["height"] == pytest.approx(55)


def test_up_to_next_cuts_from_a_sketch_a_hair_off_its_face(win):
    """Circle 13: the face had moved 0.02 mm from the sketch's plane and
    the cut stopped at it, cutting nothing."""
    from khervecad import extent
    m = win.model
    obj = m.add_node("component", {})
    obj.visible = True
    block = m.add_node("cube", dict(width=40, depth=30, height=20), parent=obj)
    g = m.add_node("translate", dict(z=20.02), parent=obj)
    ext = m.add_node("linear_extrude", dict(height=10), parent=g)
    ext.params["reverse"] = True
    m.add_node("circle", dict(x=20, y=15, radius=3), parent=ext)
    assert m.wrap_nodes([block, g], "difference") is not None
    extent.set_extent(m, ext, "up_to_next")
    assert ext.params["height"] == pytest.approx(20.02)


def test_an_older_face_sketch_takes_up_its_face(win):
    from khervecad import face_sketch as fs, model_refs
    m = win.model
    obj = m.add_node("component", {})
    obj.visible = True
    m.add_node("cube", dict(width=40, depth=30, height=20), parent=obj)
    near = m.add_node("union", dict(z=20.02), parent=obj)
    near.params[fs.KEY] = True
    far = m.add_node("union", dict(z=30.0), parent=obj)
    far.params[fs.KEY] = True
    win.builder.open_component(obj)
    QApplication.processEvents()
    model_refs.adopt(win)
    assert near.params.get(fs.FACE_REF)
    assert not far.params.get(fs.FACE_REF)
    model_refs.refresh(win)
    assert near.params["z"] == pytest.approx(20.0)     # back on the face


def test_smart_dimension_between_two_sketches(win):
    """The user's top of a rectangle to the extruded rectangle: another
    sketch's point is copied in and the dimension is made."""
    from khervecad import constrain3d, sketch_constraints as sc
    m = win.model
    a = m.add_node("union", {})
    ra = m.add_node("rect", dict(x=0, y=0, width=10, height=10), parent=a)
    b = m.add_node("union", {})
    rb = m.add_node("rect", dict(x=30, y=0, width=10, height=10), parent=b)
    QApplication.processEvents()
    win.view3d.resize(800, 600)
    win.view3d.fit()
    win.view2d.scene().ask_value = lambda k, v: "50"
    assert constrain3d.start(win, "con_dimension")
    tool = win.view3d.edit_tool

    def at(p):
        q = tool._project()(p)
        return q[0], q[1]
    tool.click(*at((10, 0, 0)))                      # a corner of a
    tool.click(*at((30, 0, 0)))                      # a corner of b
    assert any(r["kind"] == "distance" for r in sc.rows(b))
    assert any(n.name == "Reference point" for n in b.children)
    # the newer sketch moves; the older one is what it is measured from
    assert ra.params["x"] + ra.params["width"] == pytest.approx(10)
    assert rb.params["x"] == pytest.approx(60, abs=.01)


def test_the_tool_window_is_a_real_window(win):
    from PyQt5.QtCore import Qt
    from khervecad import tool_panel
    p = tool_panel.ToolPanel(win.view3d, "Test")
    assert p.isWindow() and p.windowFlags() & Qt.Tool
    p.deleteLater()


def test_a_square_dimensioned_to_a_moved_top_moves_with_it(win):
    """64 -> 60 must move the square 4 mm, and resizing the face under
    it must not throw it (the user)."""
    from khervecad import (constrain3d, face_sketch, model_refs,
                           sketch_constraints as sc)
    m = win.model
    obj = m.add_node("component", {})
    obj.visible = True
    plate = m.add_node("cube", dict(width=64, depth=16, height=64), parent=obj)
    win.builder.open_component(obj)
    QApplication.processEvents()
    win.view3d.resize(800, 600)
    win.view3d.fit()
    g = face_sketch.make(win, plate, (32, 0, 32), (0, -1, 0), open_2d=False)
    ext = m.add_node("linear_extrude", dict(height=5), parent=g)
    was = g.params["y"]
    # local coords of the top corner, and a square 10 below it
    lx, ly = face_sketch.to_local(g, (64, 0, 64))
    sq = m.add_node("rect", dict(x=lx - 10, y=ly - 20, width=10, height=10),
                    parent=ext)
    QApplication.processEvents()
    win.view2d.scene().ask_value = lambda k, v: "10"
    assert constrain3d.start(win, "con_dimension")
    tool = win.view3d.edit_tool
    ref = tool._add_reference(ext, "point", [(lx, ly)],
                              dict(ref_world=[[64.0, 0.0, 64.0]]))
    sc.add(m, ext, "distance", [sc.ref_of(ext, sq, "v2"),
                                sc.ref_of(ext, ref[0], "c")], 14.1421)
    before = face_sketch.to_world(g, sq.params["x"], sq.params["y"])
    constrain3d.end(win)
    plate.params["height"] = 60
    m.node_changed.emit(plate)
    QApplication.processEvents()
    model_refs.refresh(win)
    after = face_sketch.to_world(g, sq.params["x"], sq.params["y"])
    assert g.params["y"] == pytest.approx(was)
    assert ref[0].params["ref_world"][0][2] == pytest.approx(60)
    # it keeps its distance to the corner that came 4 lower
    refs = [sc.ref_of(ext, sq, "v2"), sc.ref_of(ext, ref[0], "c")]
    assert sc.measure(ext, "distance", refs) == pytest.approx(14.1421,
                                                              abs=0.01)
    assert after != before


def _line_sketch(win):
    m = win.model
    g = m.add_node("union", {})
    line = m.add_node("line", dict(x1=0, y1=0, x2=30, y2=3), parent=g)
    QApplication.processEvents()
    win.view3d.resize(800, 600)
    win.view3d.fit()
    return g, line


def _draw(win):
    from PyQt5.QtGui import QImage, QPainter
    img = QImage(win.view3d.size(), QImage.Format_ARGB32)
    p = QPainter(img)
    win.view3d.render(p)
    p.end()


def test_add_then_delete_a_relation_in_3d(win):
    from khervecad import constrain3d, sketch_constraints as sc
    g, line = _line_sketch(win)
    constrain3d.start(win, "con_horizontal")
    tool = win.view3d.edit_tool
    q = tool._project()((15, 1.5, 0))
    tool.click(q[0], q[1])
    assert any(r["kind"] == "horizontal" for r in sc.rows(g))
    constrain3d.start(win, "con_delete")
    tool = win.view3d.edit_tool
    assert isinstance(tool, constrain3d.Constrain3D)
    _draw(win)
    rect = win._relation_hits[0][0]
    tool.click(rect.center().x(), rect.center().y())
    assert not sc.rows(g)


def test_right_click_deletes_a_relation_in_3d(win, monkeypatch):
    from PyQt5.QtCore import QPoint
    from PyQt5.QtWidgets import QMenu
    from khervecad import sketch_constraints as sc, view3d_menu
    g, line = _line_sketch(win)
    sc.add(win.model, g, "horizontal", [sc.ref_of(g, line, "l")])
    win.builder.active_tree().select_nodes([line])
    _draw(win)
    rect = win._relation_hits[0][0]
    menus = []
    monkeypatch.setattr(QMenu, "exec_", lambda self, *a: menus.append(self))
    view3d_menu.context_menu(win, QPoint(int(rect.center().x()),
                                         int(rect.center().y())))
    acts = {a.text(): a for a in menus[0].actions()}
    acts["Delete constraint"].trigger()
    assert not sc.rows(g)


# ---- as SolidWorks does it (2026-11-09, the user: "go through every
# step and see what is not the same")
def test_a_3d_arc_needs_the_line_drawn_out_first(win, monkeypatch):
    """As in the 2D view: merely leaving the point is a line; drawn out,
    back on the point and out again is the tangent arc — a half circle to
    a point square to the line."""
    from khervecad import sketch_line as sl
    tool = _on_face(win, monkeypatch)
    win.view3d.resize(800, 600)
    tool.set_mode("line")
    tool.place((5, 5))
    tool.place((15, 5))
    v = win.view3d
    q = v._project(*v._camera(), tool._world((15, 5)))
    x, y = q[0], q[1]
    tool._arc_switch(x + sl.ARC_GO_PX + 4, y)       # just leaving
    tool._arc_switch(x, y)
    tool._arc_switch(x + sl.ARC_GO_PX + 4, y)
    assert not tool.arc
    tool._arc_switch(x + sl.ARC_AWAY_PX + 4, y)     # drawn out first
    tool._arc_switch(x, y)
    tool._arc_switch(x + sl.ARC_GO_PX + 4, y)
    assert tool.arc
    arc = tool.place((15, 15))
    assert arc.name == "Arc" and abs(arc.params["bulge"]) == pytest.approx(1)
    assert not tool.arc                             # one arc, then lines
    tool.points = []
    tool._end()


def test_a_level_line_is_as_long_as_the_cursor_reaches(win, monkeypatch):
    """Not as far as the cursor is from its start: 20, never 20.0062."""
    tool = _on_face(win, monkeypatch)
    tool.set_mode("line")
    tool.place((5, 5))
    line = tool.place((25, 5.5))
    assert (line.params["x2"], line.params["y2"]) == (25, 5)
    tool.points = []
    tool._end()


def test_the_view_shows_the_depth_once_the_cut_is_made(win, monkeypatch):
    """Drawn square on, the arrow would be seen end-on: the view goes
    back to where the face was chosen from."""
    from PyQt5.QtTest import QTest
    v = win.view3d
    v.yaw, v.pitch = 40.0, 25.0
    tool = _on_face(win, monkeypatch)
    QTest.qWait(700)                                 # the turn to the face
    assert v.pitch == pytest.approx(90)
    tool.place((5, 5))
    tool.place((15, 12))
    QTest.qWait(700)
    assert (v.yaw % 360, v.pitch) == pytest.approx((40.0, 25.0))
    assert not hasattr(win, "_cut_view_before")
    v.edit_tool.cancel()


def test_a_view_already_square_on_is_tilted_for_the_depth(win, monkeypatch):
    from PyQt5.QtTest import QTest
    v = win.view3d
    v.yaw, v.pitch = -90.0, 90.0                     # looking down already
    tool = _on_face(win, monkeypatch)
    QTest.qWait(700)
    tool.place((5, 5))
    tool.place((15, 12))
    QTest.qWait(700)
    assert v.pitch == pytest.approx(35.0)
    v.edit_tool.cancel()


def test_a_view_turned_by_hand_is_left_alone(win, monkeypatch):
    from PyQt5.QtTest import QTest
    v = win.view3d
    v.yaw, v.pitch = 40.0, 25.0
    tool = _on_face(win, monkeypatch)
    QTest.qWait(700)
    v.yaw, v.pitch = 10.0, 60.0                      # the user's orbit
    tool.place((5, 5))
    tool.place((15, 12))
    QTest.qWait(700)
    assert (v.yaw, v.pitch) == (10.0, 60.0)
    v.edit_tool.cancel()


def test_enter_keeps_the_cut(win, monkeypatch):
    from PyQt5.QtCore import Qt
    from PyQt5.QtTest import QTest
    from khervecad import drag_feature
    tool = _on_face(win, monkeypatch)
    tool.place((5, 5))
    tool.place((15, 12))
    assert isinstance(win.view3d.edit_tool, drag_feature.DragFeature)
    win.show()
    win.view3d.setFocus()
    QTest.keyClick(win.view3d, Qt.Key_Return)
    assert win.view3d.edit_tool is None
    assert any(n.type == "difference" for n in win.model.root.walk())


def test_choosing_the_face_shows_no_done_button(win, monkeypatch):
    """One click and that pick is over: nothing to be done with."""
    monkeypatch.setattr(cut_feature, "IN_3D", True)
    McpToolExecutor(win).execute("apply_code", {"code": "cube(20);\n"})
    QApplication.processEvents()
    cut_feature.start(win, "extruded_cut")
    done = getattr(win.view3d, "_pick_done", None)
    assert win.view3d._pick_cb is not None
    assert done is None or done.isHidden()
    win.view3d.cancel_pick()


# ---- found making an L piece by hand, every size a Smart Dimension
# (2026-11-10, the user: "use smart dimensions in many places and show
# me nothing goes wrong")
def test_a_loop_of_lines_stays_closed_under_a_dimension(win, monkeypatch):
    """The last line back on the first point was not tied to it: 80 on
    the L's foot pushed its free start to -4 and the outline came open."""
    from khervecad import sketch_constraints as sc
    tool = _on_face(win, monkeypatch)
    tool.set_mode("line")
    for p in ((5, 5), (25, 5), (25, 15), (5, 15), (5, 5)):
        tool.place(p)
    g = tool.group
    lines = [n for n in g.children if n.type == "line"]
    assert len(lines) == 4
    assert [r["kind"] for r in sc.rows(g)].count("coincident") == 4
    sc.add_dimension(win.model, g, "length", [sc.ref_of(g, lines[0], "l")],
                     30)
    first, last = lines[0].params, lines[-1].params
    assert (first["x1"], first["y1"]) == pytest.approx(
        (last["x2"], last["y2"]), abs=1e-6)
    assert abs(first["x2"] - first["x1"]) == pytest.approx(30)
    tool.points = []
    tool._end()


def test_the_parts_own_outline_is_never_moved_by_the_solver(win):
    """A dimension of 48 to the part's edge moved the edge 0.4 mm."""
    from khervecad import sketch_constraints as sc, sketch_section
    m = win.model
    g = m.add_node("union", {})
    edges = m.add_node("polygon", dict(points=[[0, 0], [80, 0], [80, 50],
                                               [0, 50]]), parent=g,
                       name=sketch_section.NAME)
    line = m.add_node("line", dict(x1=30, y1=10, x2=30, y2=30, width=0.2),
                      parent=g)
    assert sc._vars(edges) == []
    sc.add(m, g, "point_line", [sc.ref_of(g, line, "p1"),
                                sc.ref_of(g, edges, "e1")], 48)
    assert edges.params["points"] == [[0, 0], [80, 0], [80, 50], [0, 50]]
    assert line.params["x1"] == pytest.approx(32)


def test_a_cut_sketch_does_not_climb_off_its_face(win, monkeypatch):
    """Its own cut starts a hair above the plane and was taken for the
    face: 20.0, 20.02, 20.13 … at every change, each cut shallower."""
    from khervecad import model_refs
    tool = _on_face(win, monkeypatch)
    g = tool.group
    tool.place((5, 5))
    tool.place((15, 12))                       # a rectangle: the cut is made
    drag = win.view3d.edit_tool
    for _ in range(6):
        win.model.node_changed.emit(g)
        QApplication.processEvents()
        model_refs.refresh(win)
    assert g.params["z"] == pytest.approx(20.0, abs=1e-6)
    drag.ok()
    left = analysis.mass_properties(mesh.tessellate(win.model.root))["volume"]
    assert left == pytest.approx(40 * 30 * 20 - 10 * 7 * 10, abs=1)


def test_a_dimension_click_on_the_part_takes_its_true_edge(win, monkeypatch):
    """Not the kept outline, which is grown a hair past the part."""
    from khervecad import constrain3d, sketch_section
    m = win.model
    g = m.add_node("union", {})
    m.add_node("polygon", dict(points=[[0, 0], [8, 0], [8, 5]]), parent=g,
               name=sketch_section.NAME)
    line = m.add_node("line", dict(x1=1, y1=1, x2=3, y2=1), parent=g)
    tool = constrain3d.Constrain3D(win, "con_dimension") \
        if hasattr(constrain3d, "Constrain3D") else None
    assert tool is not None
    assert tool._shapes(g) == [line]


def test_the_cursor_readout_hides_under_a_message(win):
    win.show()
    win.statusBar().showMessage("Drag the blue arrow")
    assert win._cursor_label.isHidden()
    win.statusBar().clearMessage()
    assert not win._cursor_label.isHidden()
