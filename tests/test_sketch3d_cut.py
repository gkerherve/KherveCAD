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
    assert len(tool._own()[0]) >= 2          # the line stays drawn
    tool.finish()


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
