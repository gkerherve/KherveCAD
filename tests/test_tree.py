"""Tests for the Objects tree: checkbox-free visibility and guides.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from khervecad.model import DocumentModel
from khervecad.treepanel import ObjectTree


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def model(app):
    return DocumentModel()


def test_items_have_no_checkbox(model):
    model.add_node("cube")
    tree = ObjectTree(model)
    item = tree.topLevelItem(0)
    assert not (item.flags() & Qt.ItemIsUserCheckable)


def test_space_toggles_visibility(model):
    cube = model.add_node("cube")
    tree = ObjectTree(model)
    assert cube.visible
    tree._toggle_visibility([cube])
    assert not cube.visible
    tree._toggle_visibility([cube])
    assert cube.visible


def test_mixed_selection_flips_together(model):
    a = model.add_node("cube")
    b = model.add_node("sphere")
    model.set_visible(b, False)               # a visible, b hidden
    tree = ObjectTree(model)
    tree._toggle_visibility([a, b])            # flip to opposite of a
    assert not a.visible and not b.visible


def test_hidden_node_is_dimmed_and_italic(model):
    cube = model.add_node("cube")
    model.set_visible(cube, False)
    tree = ObjectTree(model)
    item = tree.topLevelItem(0)
    assert item.font(0).italic()
    # a foreground brush is set (the dim colour), not the default
    assert item.foreground(0).style() != Qt.NoBrush


# ----------------------------------------- decorators are their own rows

def test_decorator_chain_shows_each_node_as_a_row(model):
    cube = model.add_node("cube")
    tr = model.wrap_nodes([cube], "translate")
    model.wrap_nodes([tr], "color")            # color > translate > cube
    tree = ObjectTree(model)
    assert tree.topLevelItemCount() == 1       # the outer color
    color_item = tree.topLevelItem(0)
    assert tree.node_of(color_item).type == "color"
    trans_item = color_item.child(0)
    assert tree.node_of(trans_item).type == "translate"
    cube_item = trans_item.child(0)
    assert tree.node_of(cube_item).type == "cube"


def test_hiding_a_group_dims_the_whole_subtree(model):
    from khervecad.treepanel import ROLE_TAG
    a = model.add_node("cube")
    grp = model.wrap_nodes([a], "union")
    model.set_visible(grp, False)
    tree = ObjectTree(model)
    row = tree.topLevelItem(0)
    child = row.child(0)
    assert row.data(0, ROLE_TAG) is True       # explicitly hidden -> tag
    assert child.data(0, ROLE_TAG) is False    # child not tagged...
    assert child.font(0).italic()              # ...but dimmed by its parent
    assert row.text(0) == grp.name             # text stays clean (rename ok)


def _placement_children(item):
    from khervecad.treepanel import ROLE_PLACEMENT
    return [item.child(i) for i in range(item.childCount())
            if item.child(i).data(0, ROLE_PLACEMENT)]


def test_placed_part_shows_position_and_rotation_rows(model):
    """A snapped/moved part lists its translate and rotate in the
    tree, matching the translate(...) rotate(...) the code emits."""
    comp = model.new_component("Lid")
    model.add_node("cube", parent=comp)
    comp.params.update(x=5.0, y=5.0, z=20.0, rz=90.0)
    tree = ObjectTree(model)
    item = tree.topLevelItem(0)
    rows = _placement_children(item)
    assert [r.text(0) for r in rows] == ["Position (5, 5, 20)",
                                        "Rotation (0, 0, 90)"]
    # clicking a placement row selects the part itself
    assert tree.node_of(rows[0]) is comp


def test_unplaced_part_has_no_placement_rows(model):
    comp = model.new_component("Base")
    model.add_node("cube", parent=comp)
    tree = ObjectTree(model)
    assert _placement_children(tree.topLevelItem(0)) == []


def test_placement_rows_follow_a_mate_resolve(model):
    """When a mate moves the part, the tree rows update live."""
    from khervecad import mates
    base = model.new_component("Base")
    model.add_node("cube", dict(width=20.0, depth=20.0, height=20.0),
                   parent=base)
    lid = model.new_component("Lid")
    model.add_node("cube", dict(width=10.0, depth=10.0, height=10.0),
                   parent=lid)
    tree = ObjectTree(model)
    mates.attach(model, lid, "Base", "Bottom", "Top")
    item = tree.topLevelItem(1)
    rows = _placement_children(item)
    assert rows and rows[0].text(0) == "Position (5, 5, 20)"
    assert "Base" in rows[0].toolTip(0)      # explains where it came from
    # placement rows are metadata: not editable, not draggable
    assert not (rows[0].flags() & Qt.ItemIsEditable)
    assert not (rows[0].flags() & Qt.ItemIsDragEnabled)


def test_instance_shows_placement_rows(model):
    comp = model.new_component("Bolt", visible=False)
    model.add_node("cube", parent=comp)
    ref = model.add_instance(comp)
    ref.params.update(x=30.0)
    model.node_changed.emit(ref)
    tree = ObjectTree(model)
    item = tree.topLevelItem(0)              # the instance row
    assert tree.node_of(item) is ref
    rows = _placement_children(item)
    assert [r.text(0) for r in rows] == ["Position (30, 0, 0)"]


def test_part_shows_a_colour_row_with_a_swatch(model):
    """A part carries its colour the same way it carries its
    placement, so the tree lists it beside Position/Rotation — with
    the colour itself as the icon."""
    comp = model.new_component("Shell")
    model.add_node("cube", parent=comp)
    comp.params.update(z=12.0, color="#20e0c0")
    tree = ObjectTree(model)
    item = tree.topLevelItem(0)
    rows = _placement_children(item)
    assert [r.text(0) for r in rows] == ["Position (0, 0, 12)",
                                         "Color (#20e0c0)"]
    color_row = rows[-1]
    assert not color_row.icon(0).isNull()          # a swatch, not blank
    assert "colour" in color_row.toolTip(0).lower()
    assert tree.node_of(color_row) is comp         # selects the part
    assert not (color_row.flags() & Qt.ItemIsEditable)


def test_colour_row_shows_opacity_when_translucent(model):
    comp = model.new_component("Glass")
    model.add_node("cube", parent=comp)
    comp.params.update(color="#88ccff", alpha=0.4)
    tree = ObjectTree(model)
    rows = _placement_children(tree.topLevelItem(0))
    assert [r.text(0) for r in rows] == ["Color (#88ccff, 0.4 opacity)"]


def test_no_colour_row_when_the_part_has_no_colour(model):
    comp = model.new_component("Plain")
    model.add_node("cube", parent=comp)
    comp.params.update(x=3.0)
    tree = ObjectTree(model)
    rows = _placement_children(tree.topLevelItem(0))
    assert [r.text(0) for r in rows] == ["Position (3, 0, 0)"]


def test_colour_row_updates_when_the_colour_changes(model):
    comp = model.new_component("Shell")
    model.add_node("cube", parent=comp)
    comp.params["color"] = "#ff0000"
    tree = ObjectTree(model)
    model.set_param(comp, "color", "#0000ff")
    rows = _placement_children(tree.topLevelItem(0))
    assert [r.text(0) for r in rows] == ["Color (#0000ff)"]
