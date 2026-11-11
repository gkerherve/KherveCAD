"""Linear and Circular Sketch Pattern by the mouse (2026-11-11, the user:
"linear pattern and circular pattern like SolidWorks … select what I want
to pattern … I do not see what is the centre of rotation").

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

from khervecad import sketch_pattern as SP
from khervecad.model import DocumentModel
from khervecad.view2d import SketchScene, SketchView


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def view(app):
    scene = SketchScene(DocumentModel())
    scene.snap_enabled = False
    v = SketchView(scene)
    v.resize(800, 600)
    v.show()
    v.resetTransform()
    v.scale(8, -8)
    v.centerOn(0, 0)
    yield v
    v.close()


def _click(view, x, y, button=Qt.LeftButton):
    QTest.mouseClick(view.viewport(), button, Qt.NoModifier,
                     view.mapFromScene(QPointF(x, y)))
    QApplication.processEvents()


def test_circular_round_a_clicked_centre(view):
    m = view.scene().model
    hub = m.add_node("line", dict(x1=5, y1=5, x2=5, y2=-25, width=0.2,
                                  modifier="%"), name="Axis")
    hole = m.add_node("circle", dict(x=25, y=5, radius=3), name="Hole")
    QApplication.processEvents()
    view.set_tool(SP.CIRCULAR)
    _click(view, 28, 5)                        # the hole's rim
    st = SP._state(view.scene())
    assert st["shapes"] == [hole] and st["centre"] == (0.0, 0.0)
    panel = view._pattern_panels[SP.CIRCULAR]
    assert panel.isVisible() and "Origin" in panel.box_centre.body.text()
    SP.set_active(view.scene(), SP.CENTRE)     # the Centre box
    _click(view, 5, 5)                         # the axis's start point
    assert st["centre"] == (5.0, 5.0)
    assert "Axis" in panel.box_centre.body.text()
    panel.fields["count"].setValue(4)
    view.viewport().repaint()                  # the preview paints
    QTest.mouseClick(panel.ok, Qt.LeftButton)
    assert not panel.isVisible()
    loop = next(n for n in m.root.walk() if n.type == "for_loop")
    assert hole.parent.type == "rotate" and hole.parent.parent is loop
    assert loop.params["end"] == 3.0
    code = m.to_scad()
    assert "for (i = [0 : 1 : 3])" in code and "pivot = [5, 5, 0]" in code
    assert "i * 360 / 4" in code
    assert _centres(m) == sorted([(25.0, 5.0), (5.0, 25.0), (-15.0, 5.0),
                                  (5.0, -15.0)])
    # select it, press the button again: the window opens on it
    view.scene().model  # (same model)
    SP.begin(view.scene(), SP.CIRCULAR, edit=loop)
    assert view._pattern_panels[SP.CIRCULAR].fields["count"].value() == 4
    view._pattern_panels[SP.CIRCULAR].fields["count"].setValue(2)
    QTest.mouseClick(view._pattern_panels[SP.CIRCULAR].ok, Qt.LeftButton)
    assert [n.type for n in m.root.walk()].count("for_loop") == 1
    assert _centres(m) == sorted([(25.0, 5.0), (-15.0, 5.0)])
    m.undo_stack.undo() if m.undo_stack.canUndo() else None


def _centres(m):
    from khervecad import mesh
    outs = mesh.collect_outlines(m.root, {})
    return sorted((round(sum(p[0] for p in o) / len(o), 2) + 0.0,
                   round(sum(p[1] for p in o) / len(o), 2) + 0.0)
                  for o in outs if len(o) > 8)


def test_typed_centre_and_a_part_turn(app):
    st = SP.new_state(SP.CIRCULAR)
    st.update(count=3, angle=90.0, centre=(10.0, 0.0))
    assert [round(t, 6) for _x, _y, t in SP.placements(st)] == [45.0, 90.0]
    st["equal"] = False                        # the step between copies
    assert [t for _x, _y, t in SP.placements(st)] == [90.0, 180.0]


def test_linear_with_two_directions_and_a_rectangle(view):
    m = view.scene().model
    rect = m.add_node("rect", dict(x=0, y=0, width=4, height=2), name="R")
    QApplication.processEvents()
    view.set_tool(SP.LINEAR)
    _click(view, 2, 0)                         # its bottom side
    panel = view._pattern_panels[SP.LINEAR]
    assert not panel.fields["spacing2"].isVisible()
    panel.fields["spacing1"].setValue(10)
    panel.fields["count1"].setValue(3)
    panel.fields["dir2"].setChecked(True)
    assert panel.fields["spacing2"].isVisible()
    panel.fields["spacing2"].setValue(5)
    QTest.keyClick(view.viewport(), Qt.Key_Return)
    loops = [n for n in m.root.walk() if n.type == "for_loop"]
    assert [l.params["variable"] for l in loops] == ["i", "j"]
    from khervecad import mesh
    corners = sorted((round(min(p[0] for p in o), 3) + 0.0,
                      round(min(p[1] for p in o), 3) + 0.0)
                     for o in mesh.collect_outlines(m.root, {}))
    assert corners == sorted((10.0 * i, 5.0 * j) for i in range(3)
                             for j in range(2))
    st = SP.state_of(loops[0])                 # opened again: Direction 2
    st["dir2"] = False                         # off: the j loop goes
    SP.make(m, st)
    assert [n.type for n in m.root.walk()].count("for_loop") == 1
    assert len(mesh.collect_outlines(m.root, {})) == 3


def test_a_turned_rectangle_becomes_a_polygon():
    from khervecad.model import CadNode
    r = CadNode("rect", "R", dict(x=10, y=0, width=4, height=2))
    t, p = SP.copied_params(r, (0, 0), 0, 0, 90)
    assert t == "polygon"
    assert [[round(a, 3), round(b, 3)] for a, b in p["points"]] == \
        [[0, 10], [0, 14], [-2, 14], [-2, 10]]


def test_esc_cancels(view):
    m = view.scene().model
    m.add_node("circle", dict(x=10, y=0, radius=2))
    QApplication.processEvents()
    view.set_tool(SP.CIRCULAR)
    _click(view, 12, 0)
    QTest.keyClick(view.viewport(), Qt.Key_Escape)
    assert SP._state(view.scene()) is None
    assert len([n for n in m.root.children if n.type == "circle"]) == 1


def test_a_circular_pattern_of_holes_is_cut(app, monkeypatch):
    """A hole on a face sketch, patterned 6 times round the middle, then
    the Extruded Cut: six holes through the block."""
    from khervecad import analysis, cut_feature, face_sketch, mesh, \
        sketch_choice
    from khervecad.mainwindow import MainWindow
    from khervecad.mcp_tools import McpToolExecutor
    win = MainWindow()
    try:
        McpToolExecutor(win).execute("apply_code", {
            "code": "translate([-30, -30, 0]) cube([60, 60, 10]); "
                    "// Block\n"})
        QApplication.processEvents()
        m = win.model
        part = next(c for c in m.root.children if c.visible
                    and c.type not in ("assign", "variables"))
        full = analysis.mass_properties(mesh.tessellate(m.root))["volume"]
        group = face_sketch.make(win, part, (0, 0, 10), (0, 0, 1),
                                 open_2d=False)
        group.params[cut_feature.KEY] = "extruded_cut"
        hole = m.add_node("circle", dict(x=20, y=0, radius=2),
                          parent=group)
        st = SP.new_state(SP.CIRCULAR, [hole])
        loop, _skip = SP.make(m, st)
        assert loop.parent is group
        diff = cut_feature.apply(m, group, part, "extruded_cut")
        assert diff is not None
        ext = next(n for n in m.root.walk() if n.type == "linear_extrude")
        ext.params.update(height=20.0)       # right through
        QApplication.processEvents()
        left = analysis.mass_properties(mesh.tessellate(m.root))["volume"]
        one = math.pi * 4 * 10
        assert abs((full - left) - 6 * one) < 0.06 * 6 * one
    finally:
        win._dirty = False
        win.close()


def test_properties_show_instances_and_total_angle(app):
    """No "i * 60" to edit: Instances and Total angle, on the loop and on
    the turn inside it."""
    from khervecad import mesh
    from khervecad.properties import PropertiesPanel
    m = DocumentModel()
    hole = m.add_node("circle", dict(x=20, y=0, radius=2))
    st = SP.new_state(SP.CIRCULAR, [hole])
    loop, _s = SP.make(m, st)
    panel = PropertiesPanel(m)
    for node in (loop, hole.parent):
        panel.set_node(node)
        rows = panel._pattern
        assert rows["count"].value() == 6 and rows["angle"].value() == 360
        assert "variable" not in panel._editors   # no From / To
    rows["count"].setValue(8)
    assert hole.parent.params["z"] == "i * 360 / 8"
    assert loop.params["end"] == 7.0
    assert len(mesh.collect_outlines(m.root, {})) == 8
    rows["angle"].setValue(90)                 # spans 90°: 8 over 90
    assert hole.parent.params["z"] == "i * 90 / 7"
    rows["equal"].setChecked(False)            # 90° between copies
    assert hole.parent.params["z"] == "i * 90"


def test_history_shows_one_pattern_row_with_its_shape(app):
    """No "Body-Rotate" beside the Repeat: the turn is the pattern's
    inside (2026-11-11, the user)."""
    from PyQt5.QtCore import Qt
    from khervecad import feature_list, tree_history
    from khervecad.mainwindow import MainWindow
    win = MainWindow()
    tree_history.set_enabled(True)
    try:
        m = win.model
        hole = m.add_node("circle", dict(x=20, y=0, radius=2))
        loop, _s = SP.make(m, SP.new_state(SP.CIRCULAR, [hole]))
        assert feature_list.is_plumbing(hole.parent)
        tree = win.builder.tree
        tree.rebuild()
        rows = [tree.topLevelItem(i)
                for i in range(tree.topLevelItemCount())]
        rows = [r for r in rows if not r.data(0, tree_history.ROLE_FIXED)]
        assert [r.data(0, Qt.UserRole) for r in rows] == [loop.id]
        assert [rows[0].child(i).data(0, Qt.UserRole)
                for i in range(rows[0].childCount())] == [hole.id]
    finally:
        tree_history.set_enabled(False)
        win._dirty = False
        win.close()
