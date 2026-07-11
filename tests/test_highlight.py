"""Tests for selection highlight across the 2D and 3D views.

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
from PyQt5.QtWidgets import QApplication

from khervecad import library, mesh
from khervecad.model import CadNode, DocumentModel


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


# -------------------------------------------------- selected_world_tris

def test_selected_tris_of_leaf_in_transformed_part(model):
    # a cube offset by a translate: selecting the cube must return it
    # at its transformed (world) position, not at the origin.
    cube = model.add_node("cube", dict(width=4.0, depth=4.0,
                                       height=4.0))
    move = model.wrap_nodes([cube], "translate")
    move.params.update(x=100.0, y=0.0, z=0.0)
    tris = mesh.selected_world_tris(model.root, {cube.id})
    assert tris
    xs = [v[0] for t in tris for v in t]
    assert min(xs) == pytest.approx(100.0)
    assert max(xs) == pytest.approx(104.0)


def test_selected_tris_empty_when_nothing_selected(model):
    model.add_node("cube")
    assert mesh.selected_world_tris(model.root, set()) == []


def test_selecting_parent_includes_children(model):
    group = model.add_node("union")
    model.add_node("cube", dict(width=2.0, depth=2.0, height=2.0),
                   parent=group)
    model.add_node("sphere", dict(radius=1.0, segments=8),
                   parent=group)
    whole = mesh.tessellate(model.root)
    selected = mesh.selected_world_tris(model.root, {group.id})
    assert len(selected) == len(whole)          # everything under it


def test_selecting_one_child_marks_only_it(model):
    group = model.add_node("union")
    cube = model.add_node("cube", parent=group)
    model.add_node("sphere", dict(segments=8), parent=group)
    selected = mesh.selected_world_tris(model.root, {cube.id})
    assert len(selected) == 12                   # just the cube faces


def test_highlight_survives_boolean_first_operand(model):
    # a tube inside the kept body of a difference is still highlightable
    body = model.add_node("union")
    tube = library._cyl("Tube", 5.0, 20.0)
    body.add(tube)
    model.add_node("cylinder", dict(radius_bottom=2.0, radius_top=2.0),
                   parent=body)
    model.wrap_nodes([body], "difference")
    # subtract something
    model.root.children[0].add(
        CadNode("sphere", "cut", dict(radius=1.0, segments=6)))
    tris = mesh.selected_world_tris(model.root, {tube.id})
    assert tris                                   # tube is in operand 1


# ---------------------------------------------------------- view wiring

def test_window_highlights_selected_part_in_both_views(window):
    m = window.model
    part = library.build_part("cf_tee",
                              dict(library.CF_SIZES["CF63 (DN63)"],
                                   port_length=60.0))
    m.root.add(part)
    m.structure_changed.emit()
    tube = next(n for n in part.walk() if n.name == "Tube"
                and n.type == "cylinder")
    window.builder.tree.select_nodes([tube])
    # 3D: the selected object's faces are queued to glow
    assert window.view3d.highlight_mesh
    # 2D: an accent outline overlay exists for the selection
    assert window.scene._highlight_ids == {tube.id}
    assert window.scene._highlight_items


def test_highlight_clears_on_empty_selection(window):
    m = window.model
    cube = m.add_node("cube")
    window.builder.tree.select_nodes([cube])
    assert window.view3d.highlight_mesh
    window.builder.tree.select_nodes([])
    assert window.view3d.highlight_mesh == []
    assert window.scene._highlight_items == []


def test_highlight_follows_plane_change(window):
    m = window.model
    part = library.build_part("cf_nipple",
                              dict(library.CF_SIZES["CF40 (DN40)"],
                                   port_length=40.0))
    m.root.add(part)
    m.structure_changed.emit()
    window.builder.tree.select_nodes([part])
    window._set_plane("Front (XZ)")
    assert window.scene.plane == "Front (XZ)"
    assert window.scene._highlight_items       # rebuilt for new plane
