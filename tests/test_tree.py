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


# --------------------------------------------- merged decorator rows

def test_decorator_chain_merges_into_one_row(model):
    from khervecad.treepanel import ROLE_BADGES
    cube = model.add_node("cube")
    tr = model.wrap_nodes([cube], "translate")
    model.wrap_nodes([tr], "color")            # color > translate > cube
    tree = ObjectTree(model)
    assert tree.topLevelItemCount() == 1       # one merged row
    item = tree.topLevelItem(0)
    assert item.childCount() == 0              # the chain is collapsed
    # selection/properties targets the geometry; structure the chain root
    assert tree.node_of(item).type == "cube"
    assert tree._root_of(item).type == "color"
    badges = item.data(0, ROLE_BADGES)
    assert badges[0][0] == "color"             # colour swatch
    assert badges[1] == ("icon", "mdi.cursor-move")   # translate glyph


def test_group_is_not_merged(model):
    a = model.add_node("cube")
    b = model.add_node("sphere")
    model.wrap_nodes([a, b], "union")          # a real group, 2 children
    tree = ObjectTree(model)
    assert tree.topLevelItemCount() == 1
    assert tree.topLevelItem(0).childCount() == 2


def test_delete_merged_row_removes_whole_chain(model):
    cube = model.add_node("cube")
    tr = model.wrap_nodes([cube], "translate")
    model.wrap_nodes([tr], "color")
    tree = ObjectTree(model)
    tree.topLevelItem(0).setSelected(True)
    for node in tree._top_level_selection():
        model.remove_node(node)
    assert model.root.children == []           # nothing orphaned


def test_decorator_wrapping_group_folds_but_keeps_children(model):
    from khervecad.treepanel import ROLE_BADGES
    a = model.add_node("cube")
    b = model.add_node("sphere")
    grp = model.wrap_nodes([a, b], "union")
    r1 = model.wrap_nodes([grp], "rotate")
    model.wrap_nodes([r1], "rotate")           # rotate>rotate>union
    tree = ObjectTree(model)
    assert tree.topLevelItemCount() == 1
    row = tree.topLevelItem(0)
    assert tree.node_of(row).type == "union"   # the group is the row
    assert row.childCount() == 2               # its children still nest
    badges = row.data(0, ROLE_BADGES)
    assert badges == [("icon", "mdi.rotate-right"),
                      ("icon", "mdi.rotate-right")]


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
