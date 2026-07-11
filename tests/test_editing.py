"""Tests for clipboard, reordering, validation and code line spans.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def model(app):
    return DocumentModel()


@pytest.fixture
def window(app):
    from khervecad.mainwindow import MainWindow
    return MainWindow()


# ------------------------------------------------------------ line spans

def test_spans_cover_nodes(model):
    circle = model.add_node("circle")
    ext = model.wrap_nodes([circle], "linear_extrude")
    cube = model.add_node("cube")
    code, spans = model.to_scad_map()
    lines = code.splitlines()
    s, e = spans[ext.id]
    assert lines[s].startswith("linear_extrude")
    assert lines[e - 1] == "}"
    cs, ce = spans[circle.id]
    assert "circle" in lines[cs]
    assert s < cs < e
    ks, _ = spans[cube.id]
    assert "cube" in lines[ks]


def test_node_at_line_finds_deepest(model):
    circle = model.add_node("circle")
    ext = model.wrap_nodes([circle], "linear_extrude")
    _code, spans = model.to_scad_map()
    inner_line = spans[circle.id][0]
    assert model.node_at_line(inner_line) is circle
    assert model.node_at_line(spans[ext.id][0]) is ext


def test_if_else_spans_and_code(model):
    cond = model.add_node("if_else", dict(condition="a > 1"))
    model.add_node("cube", parent=cond)
    model.add_node("sphere", parent=cond.children[0])
    code, spans = model.to_scad_map()
    s, e = spans[cond.id]
    lines = code.splitlines()
    assert lines[s].startswith("if (a > 1) {")
    assert lines[e - 1] == "}"


# ------------------------------------------------------------ validation

def test_validate_ok_document(model):
    c = model.add_node("circle")
    model.wrap_nodes([c], "linear_extrude")
    model.add_node("cube")
    assert validate(model.root) == {}


def test_validate_bad_expression(model):
    node = model.add_node("circle", dict(radius="nonsense + 2"))
    errors = validate(model.root)
    assert node.id in errors
    assert "nonsense" in errors[node.id]


def test_validate_expression_ok_inside_loop(model):
    loop = model.add_node("for_loop", dict(variable="i"))
    node = model.add_node("circle", dict(radius="i + 1"), parent=loop)
    errors = validate(model.root)
    assert node.id not in errors


def test_validate_assign_makes_variable_known(model):
    model.add_node("assign", dict(variable="bore", value="38"))
    node = model.add_node("circle", dict(radius="bore / 2"))
    assert node.id not in validate(model.root)


def test_validate_empty_extrusion(model):
    ext = model.add_node("linear_extrude")
    errors = validate(model.root)
    assert "2D" in errors[ext.id]


def test_validate_3d_inside_extrusion(model):
    cube = model.add_node("cube")
    ext = model.wrap_nodes([cube], "linear_extrude")
    errors = validate(model.root)
    assert ext.id in errors
    assert "3D" in errors[ext.id]


def test_validate_rotate_extrude_axis_crossing(model):
    circle = model.add_node("circle", dict(x=0.0, radius=10.0))
    rev = model.wrap_nodes([circle], "rotate_extrude")
    errors = validate(model.root)
    assert rev.id in errors and "axis" in errors[rev.id]
    circle.params["x"] = 20.0
    assert rev.id not in validate(model.root)


def test_validate_nonterminating_while(model):
    loop = model.add_node("while_loop", dict(
        variable="x", start=0.0, condition="x < 10", update="x"))
    model.add_node("cube", parent=loop)
    errors = validate(model.root)
    assert "terminate" in errors[loop.id]


def test_validate_missing_stl(model):
    node = model.add_node("stl_import", dict(path="/nope/missing.stl"))
    assert "not found" in validate(model.root)[node.id]


def test_validate_bad_variable_name(model):
    node = model.add_node("assign", dict(variable="2bad", value="1"))
    assert "variable" in validate(model.root)[node.id]


# ------------------------------------------------------------- clipboard

def test_copy_paste_roundtrip(window):
    model = window.model
    circle = model.add_node("circle", dict(radius=7.0))
    ext = model.wrap_nodes([circle], "linear_extrude")
    tree = window.builder.tree
    tree.select_nodes([ext])
    tree.copy_selection()

    payload = json.loads(QApplication.clipboard().text())
    assert payload["format"] == "kcad-clipboard"

    tree.select_nodes([])
    tree.paste_clipboard()
    assert len(model.root.children) == 2
    pasted = model.root.children[1]
    assert pasted.type == "linear_extrude"
    assert pasted.children[0].params["radius"] == 7.0
    assert pasted.name != ext.name            # renamed "(copy)"


def test_cut_removes_and_paste_restores(window):
    model = window.model
    cube = model.add_node("cube")
    tree = window.builder.tree
    tree.select_nodes([cube])
    tree.cut_selection()
    assert model.root.children == []
    tree.paste_clipboard()
    assert model.root.children[0].type == "cube"


def test_paste_into_selected_container(window):
    model = window.model
    group = model.add_node("union")
    sphere = model.add_node("sphere")
    tree = window.builder.tree
    tree.select_nodes([sphere])
    tree.copy_selection()
    tree.select_nodes([group])
    tree.paste_clipboard()
    assert group.children[0].type == "sphere"


def test_copy_excludes_nested_selection(window):
    model = window.model
    group = model.add_node("union")
    inner = model.add_node("cube", parent=group)
    tree = window.builder.tree
    tree.select_nodes([group, inner])
    tree.copy_selection()
    payload = json.loads(QApplication.clipboard().text())
    assert len(payload["nodes"]) == 1         # only the group


def test_shift_selection_reorders(window):
    model = window.model
    a = model.add_node("cube")
    b = model.add_node("sphere")
    tree = window.builder.tree
    tree.select_nodes([b])
    tree.shift_selection(-1)
    assert [n.type for n in model.root.children] == ["sphere", "cube"]
    tree.shift_selection(-1)                  # already first: no-op
    assert [n.type for n in model.root.children] == ["sphere", "cube"]


def test_error_nodes_marked_in_tree(window):
    model = window.model
    bad = model.add_node("circle", dict(radius="oops"))
    tree = window.builder.tree
    item = tree._item_of(bad)
    assert "oops" in item.toolTip(0) or "⚠" in item.toolTip(0)


def test_engine_error_maps_to_node(window):
    model = window.model
    cube = model.add_node("cube")
    _code, spans = model.to_scad_map()
    line = spans[cube.id][0] + 1              # OpenSCAD lines are 1-based
    window._engine_failed(f"ERROR: something bad in file x, line {line}")
    assert cube.id in window.builder._engine_errors
    window._engine_mesh([])                   # success clears them
    assert window.builder._engine_errors == {}


def test_tab_q_steps_through_objects(window):
    m = window.model
    a = m.add_node("cube")
    b = m.add_node("sphere")
    c = m.add_node("cylinder")
    tree = window.builder.tree
    tree.step_selection(1)                     # from none -> first
    assert tree.selected_nodes()[0] is a
    tree.step_selection(1)
    assert tree.selected_nodes()[0] is b
    tree.step_selection(1)
    assert tree.selected_nodes()[0] is c
    tree.step_selection(1)                     # wraps to the start
    assert tree.selected_nodes()[0] is a
    tree.step_selection(-1)                    # wraps to the end
    assert tree.selected_nodes()[0] is c


def test_step_descends_into_children(window):
    m = window.model
    group = m.add_node("union")
    inner = m.add_node("cube", parent=group)
    tree = window.builder.tree
    tree.select_nodes([group])
    tree.step_selection(1)                     # next is the child
    assert tree.selected_nodes()[0] is inner


# ------------------------------------------------------ polygon points

def test_points_editor_insert_splits_edge(app):
    from khervecad.properties import PointsEditor
    out = []
    editor = PointsEditor([[0, 0], [10, 0], [10, 10], [0, 10]],
                          out.append)
    editor.table.setCurrentCell(0, 0)          # select vertex 0
    editor._add_row()
    # new vertex is the midpoint of edge 0->1, inserted between them
    assert out[-1] == [[0.0, 0.0], [5.0, 0.0], [10.0, 0.0],
                       [10.0, 10.0], [0.0, 10.0]]


def test_points_editor_insert_no_selection_splits_closing_edge(app):
    from khervecad.properties import PointsEditor
    out = []
    editor = PointsEditor([[0, 0], [10, 0], [0, 10]], out.append)
    editor.table.clearSelection()
    editor.table.setCurrentCell(-1, -1)
    editor._add_row()
    # midpoint of the closing edge (last -> first) appended at the end
    assert out[-1][-1] == [0.0, 5.0]


def test_points_editor_remove_keeps_minimum(app):
    from khervecad.properties import PointsEditor
    out = []
    editor = PointsEditor([[0, 0], [10, 0], [10, 10], [0, 10]],
                          out.append)
    editor.table.setCurrentCell(0, 0)
    editor._remove_row()
    assert len(out[-1]) == 3
    for _ in range(5):                          # never drops below 3
        editor.table.setCurrentCell(0, 0)
        editor._remove_row()
    assert editor.table.rowCount() == 3


# ------------------------------------------------------ variables sheet

def test_variables_sheet_lists_and_edits(window):
    m = window.model
    m.add_node("assign", dict(variable="width", value="100"))
    m.add_node("assign", dict(variable="height", value="width/2"))
    m.add_node("cube")
    m.structure_changed.emit()
    sheet = window.builder.variables
    assert sheet.table.rowCount() == 2
    assert sheet.table.item(0, 0).text() == "width"
    assert sheet.table.item(1, 1).text() == "width/2"

    sheet.table.item(0, 1).setText("250")          # edit a value
    assert m.root.children[0].params["value"] == "250"
    sheet.table.item(1, 0).setText("h")            # rename a variable
    assert m.root.children[1].params["variable"] == "h"
    assert m.root.children[1].name == "h ="


def test_variables_sheet_add_keeps_vars_before_geometry(window):
    m = window.model
    m.add_node("assign", dict(variable="a", value="1"))
    m.add_node("cube")
    m.structure_changed.emit()
    window.builder.variables._add()
    kinds = [n.type for n in m.root.children]
    assert kinds == ["assign", "assign", "cube"]    # new var before cube


def test_variables_sheet_remove(window):
    m = window.model
    m.add_node("assign", dict(variable="a", value="1"))
    m.add_node("assign", dict(variable="b", value="2"))
    m.structure_changed.emit()
    sheet = window.builder.variables
    sheet.table.setCurrentCell(0, 0)
    sheet._remove()
    assert [n.params["variable"] for n in m.root.children] == ["b"]


def test_assign_nodes_coloured_in_tree(window):
    from khervecad.treepanel import VAR_COLOR, VAR_COLOR_DARK
    m = window.model
    node = m.add_node("assign", dict(variable="a", value="1"))
    m.structure_changed.emit()
    item = window.builder.tree._item_of(node)
    assert item is not None
    assert item.foreground(0).color().name() in (VAR_COLOR, VAR_COLOR_DARK)


# ----------------------------------------- variable-or-value editors

def test_numeric_field_offers_variables_or_fixed_value(window):
    from khervecad.properties import VarOrValueEdit
    m = window.model
    m.add_node("assign", dict(variable="deck_thickness", value="50"))
    m.add_node("assign", dict(variable="leg_h", value="150"))
    cube = m.add_node("cube", dict(width=100.0, height=100.0))
    m.structure_changed.emit()

    window.properties.set_node(cube)
    editor = window.properties._editors["width"]
    assert isinstance(editor, VarOrValueEdit) and editor.isEditable()

    # the dropdown lists the document's variables
    editor.showPopup()
    assert [editor.itemText(i) for i in range(editor.count())] == \
        ["deck_thickness", "leg_h"]

    # picking a variable stores its name (an expression)
    editor.setEditText("deck_thickness")
    editor._commit()
    assert cube.params["width"] == "deck_thickness"
    # typing a number stores a fixed float
    editor.setEditText("42.5")
    editor._commit()
    assert cube.params["width"] == 42.5


def test_numeric_field_round_trips_a_variable(window):
    from khervecad.properties import VarOrValueEdit
    m = window.model
    m.add_node("assign", dict(variable="leg_h", value="150"))
    cube = m.add_node("cube", dict(height="leg_h"))
    m.structure_changed.emit()
    window.properties.set_node(cube)
    editor = window.properties._editors["height"]
    assert isinstance(editor, VarOrValueEdit)
    assert editor.currentText() == "leg_h"


def test_points_editor_move_interpolates_between_neighbours(app):
    from khervecad.properties import PointsEditor
    out = []
    editor = PointsEditor([[0, 0], [10, 0], [10, 10], [0, 10]],
                          out.append)
    editor.table.setCurrentCell(0, 0)              # point (0,0)
    editor._move_row(1)                            # move it one place down
    # reordered, and the moved point sits midway between its neighbours
    # ([10,0] and [10,10]) -> [10,5]
    assert out[-1] == [[10.0, 0.0], [10.0, 5.0], [10.0, 10.0], [0.0, 10.0]]


def test_points_editor_move_clamped_at_ends(app):
    from khervecad.properties import PointsEditor
    out = []
    editor = PointsEditor([[0, 0], [10, 0], [10, 10]], out.append)
    editor.table.setCurrentCell(0, 0)
    editor._move_row(-1)                            # already first: no-op
    assert out == []


# ---------------------------------------------- defaults & editable code

def test_common_segments_on_by_default():
    m = DocumentModel()
    assert m.global_fn_on is True
    assert m.global_fn == 45
    assert m.effective_fn() == 45


def test_code_tab_editable_and_apply(window):
    m = window.model
    m.add_node("cube")
    m.structure_changed.emit()
    assert not window.builder.code.isReadOnly()
    window.builder.code.setPlainText(
        "sphere(r=6, $fn=12);\ncylinder(h=4, r1=2, r2=2, $fn=8);")
    window.builder._apply_code()
    assert [n.type for n in m.root.children] == ["sphere", "cylinder"]
    assert m.root.children[0].params["radius"] == 6.0


def test_selected_object_shows_size_and_cursor(window):
    from PyQt5.QtCore import QPointF
    m = window.model
    m.add_node("cube", dict(width=8.0, depth=6.0, height=4.0))
    m.structure_changed.emit()
    window.builder.tree.select_nodes([m.root.children[0]])
    text = window._dims_label.text()
    assert "X 8" in text and "Y 6" in text and "Z 4" in text
    window.builder.tree.select_nodes([])
    assert window._dims_label.text() == ""

    # cursor read-out uses the current plane's axes
    window._set_plane("Top (XY)")
    window._cursor_moved(QPointF(12.3, 45.6))
    assert "12.3" in window._cursor_label.text()
    assert "45.6" in window._cursor_label.text()
