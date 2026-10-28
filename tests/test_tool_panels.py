"""The tool windows (tool_panel.py): Extrude's, by mouse and keyboard in
the real window; Mirror Entities' look.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import pytest
from PyQt5.QtCore import QPoint, QRect, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

import test_lever_by_mouse as L
from khervecad import drag_feature, extrude_panel

win = L.win                                     # the same window fixture


def _rect_extrude(w):
    L._open_top_sketch(w)
    w.view2d.set_tool("rect")
    L._drag(w.view2d.viewport(), L._at(w, 0, 0), L._at(w, 30, 20))
    L._extruded_boss(w)
    QTest.qWait(50)
    panel = extrude_panel._panel(w)
    assert panel is not None and panel.isVisible()
    return panel, panel.ext


def _type(spin, text):
    spin.setFocus()
    spin.selectAll()
    QTest.keyClicks(spin, text)
    QTest.keyClick(spin, Qt.Key_Return)
    QTest.qWait(30)


def _choose(combo, label):
    combo.setCurrentIndex(combo.findText(label))
    QTest.qWait(30)


def test_the_extrude_window_opens_beside_the_3d_view_in_the_theme(win):
    from khervecad.style import tokens
    panel, ext = _rect_extrude(win)
    assert panel.title.text() == "Extrude"
    vp = win.view3d
    view_rect = QRect(vp.mapTo(win, QPoint(0, 0)), vp.size())
    assert not panel.geometry().intersects(view_rect)
    assert tokens()["card"] in panel.styleSheet()     # the app's colours
    assert "rgba(32, 38, 46" not in panel.styleSheet()
    assert "region" in panel.boxes["profiles"].body.text() or \
        "Rectangle" in panel.boxes["profiles"].body.text()


def test_typing_the_distance_and_choosing_the_direction(win):
    panel, ext = _rect_extrude(win)
    _type(panel.fields["height"], "12")
    assert ext.params["height"] == pytest.approx(12)
    _choose(panel.fields["direction"], "Symmetric")
    assert ext.params["center"] is True
    _choose(panel.fields["direction"], "Two sides")
    assert not ext.params["center"]
    assert panel.fields["height2"].isVisible()
    _type(panel.fields["height2"], "5")
    assert ext.params["height2"] == pytest.approx(5)
    _choose(panel.fields["direction"], "One side")
    assert ext.params["height2"] == 0 and not panel.fields["height2"].isVisible()
    QTest.mouseClick(panel.fields["reverse"], Qt.LeftButton)
    assert drag_feature.reversed_of(ext) is not None
    assert extrude_panel._panel(win) is panel          # still open
    QTest.mouseClick(panel.fields["reverse"], Qt.LeftButton)
    assert drag_feature.reversed_of(ext) is None
    _choose(panel.fields["extent"], "Through all")
    assert ext.params["extent"] == "through_all"
    assert not panel.fields["height"].isEnabled()


def test_dragging_the_arrow_updates_the_distance_field(win):
    panel, ext = _rect_extrude(win)
    L._drag_arrow(win, 8.0)
    assert ext.params["height"] == pytest.approx(8)
    assert panel.fields["height"].value() == pytest.approx(8)


def test_cancel_takes_a_new_extrude_back(win):
    panel, ext = _rect_extrude(win)
    _type(panel.fields["height"], "7")
    QTest.mouseClick(panel.cancel, Qt.LeftButton)
    QTest.qWait(50)
    assert not any(n.type == "linear_extrude"
                   for n in win.model.root.walk())
    assert extrude_panel._panel(win) is None


def test_ok_keeps_it_and_closes(win):
    panel, ext = _rect_extrude(win)
    _type(panel.fields["height"], "7")
    QTest.mouseClick(panel.ok, Qt.LeftButton)
    QTest.qWait(50)
    assert extrude_panel._panel(win) is None
    assert any(n is ext for n in win.model.root.walk())
    assert ext.params["height"] == pytest.approx(7)


def test_reverse_keeps_the_window_open(win):
    panel, ext = _rect_extrude(win)
    QTest.mouseClick(panel.fields["reverse"], Qt.LeftButton)
    QTest.qWait(50)
    assert extrude_panel._panel(win) is panel and panel.isVisible()
    assert drag_feature.reversed_of(ext) is not None
    assert win.view3d.edit_tool is panel.tool()


def test_the_extrude_properties_speak_like_its_window(win):
    """Properties of a Boss / Cut extrude: Profiles, Direction, End
    condition, Distance (2), Reverse — then Twist, Scale, Slices."""
    from PyQt5.QtWidgets import QCheckBox, QComboBox
    panel, ext = _rect_extrude(win)
    QTest.mouseClick(panel.ok, Qt.LeftButton)
    QTest.qWait(50)
    win.builder.active_tree().select_nodes([ext])
    QTest.qWait(50)
    props = win.properties
    assert props.node is ext
    st = props._extrude
    assert "Rectangle" in st["profiles"].text() or \
        "region" in st["profiles"].text()
    for key in ("height", "height2", "twist", "scale", "segments"):
        assert key in props._editors
    assert "center" not in props._editors and "extent" not in \
        props._editors                         # spoken as Direction / End
    st["direction"].setCurrentIndex(st["direction"].findData("symmetric"))
    assert ext.params["center"] is True
    st["direction"].setCurrentIndex(st["direction"].findData("two"))
    assert not ext.params["center"] and ext.params["height2"] > 0
    assert st["row:height2"][1].isVisibleTo(props)
    st["direction"].setCurrentIndex(st["direction"].findData("one"))
    assert not st["row:height2"][1].isVisibleTo(props)
    st["reverse"].click()                    # its box, as a click does
    QTest.qWait(30)
    assert extrude_panel.is_reversed(ext)
    assert win.properties.node is ext          # still showing it
    st = props._extrude                        # (rebuilt for it)
    assert st["reverse"].isChecked()
    st["extent"].setCurrentIndex(st["extent"].findData("through_all"))
    assert ext.params["extent"] == "through_all"
    assert not st["row:height"][1].isEnabled()
    # the arrow / window changing the height shows here too
    win.model.set_param(ext, "height", 6)
    QApplication.processEvents()
    assert props._editors["height"].currentText().startswith("6")


def test_twist_and_scale_in_the_extrude_window(win):
    panel, ext = _rect_extrude(win)
    _type(panel.fields["twist"], "90")
    assert ext.params["twist"] == pytest.approx(90)
    _type(panel.fields["scale"], "0.5")
    assert ext.params["scale"] == pytest.approx(0.5)
    win.model.set_param(ext, "twist", 30)       # changed elsewhere
    QApplication.processEvents()
    assert panel.fields["twist"].value() == pytest.approx(30)


def test_the_assembly_shows_no_sketch_dimensions(win):
    """The Main tab is the assembly: an Object's sketch dimensions show
    in its Object tab and while sketching, not among the parts."""
    from khervecad import sketch_constraints as sc, sketch_dims3d
    from khervecad import sketch_constrain_ui as ui
    m = win.model
    obj = m.add_node("component", {}, name="Washer")
    obj.visible = True
    sk = m.add_node("linear_extrude", dict(height=3), parent=obj)
    m.add_node("circle", dict(x=0, y=0, radius=10), parent=sk)
    sc.add_dimension(m, sk, "diameter", ["0.o"], 20)
    QTest.qWait(50)
    win.builder.open_component(obj)            # the Object tab
    QTest.qWait(80)
    assert not sketch_dims3d.assembly_mode(win)
    assert sketch_dims3d.placements(win)
    win.builder.setCurrentIndex(0)                # the Main tab
    QTest.qWait(80)
    assert sketch_dims3d.assembly_mode(win)
    assert sketch_dims3d.placements(win) == []
    assert sk not in ui.shown_containers(win.scene)


def test_a_region_and_its_shapes_are_highlighted(win):
    """In the 2D view a Regions node shows the area it keeps; selected,
    that area is outlined; a shape of it selected shows its own blue
    outline (the shapes are outlines once a Regions uses them)."""
    from PyQt5.QtCore import QPointF
    from PyQt5.QtGui import QColor
    from khervecad import region_area, sketch_regions as R
    m = win.model
    g = m.add_node("union", {}, name="Sketch")
    for r in (10, 4):
        m.add_node("circle", dict(x=0, y=0, radius=r), parent=g)
    m.add_node("rect", dict(x=-20, y=-15, width=40, height=30), parent=g)
    shapes = R.shapes_of(g)
    got = R.faces(shapes)
    reg = R.make(m, g, got, R.solid_faces(shapes, got), hide=shapes)
    QTest.qWait(80)
    scene = win.view2d.scene()
    areas = scene._region_areas
    assert len(areas) == 1 and areas[0].node is reg
    assert areas[0].pen().style() == Qt.NoPen      # not selected yet
    tree = win.builder.active_tree()
    tree.select_nodes([reg])
    QTest.qWait(100)
    area = scene._region_areas[0]
    assert area.pen().style() != Qt.NoPen          # the region, outlined
    big = reg.children[0]
    tree.select_nodes([big])
    QTest.qWait(100)
    item = scene._items[big.id]
    # selected and selectable: drawn in the selection blue (ShapeItem.paint,
    # pixel-checked in test_sketch_regions_mouse)
    assert item.isSelected() and item.flags() & item.ItemIsSelectable
