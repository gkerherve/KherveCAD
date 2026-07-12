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
