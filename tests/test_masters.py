"""Tests for the Masters store, the Masters tab, and the Examples /
Library menus.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import document, examples, mesh
from khervecad.model import DocumentModel, validate


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def model(app):
    return DocumentModel()


# ------------------------------------------------------------ make master

def test_make_master_moves_node_and_leaves_linked_copy(model):
    cube = model.add_node("cube")
    ref = model.make_master(cube)
    group = model.masters_group()
    assert group is not None
    assert cube in group.children               # the definition moved in
    assert cube not in model.root.children      # ...and out of the scene
    assert ref.type == "reference"
    assert ref.parent is model.root             # a Linked copy took its place
    assert ref.params["ref"] == cube.name


def test_master_is_unique_named(model):
    a = model.add_node("cube")
    b = model.add_node("cube")
    b.name = a.name                             # force a clash
    model.make_master(b)
    names = [n.name for n in model.root.walk()]
    assert names.count(b.name) == 1


def test_masters_render_only_through_copies(model):
    cube = model.add_node("cube")
    model.make_master(cube)
    group = model.masters_group()
    # the store itself contributes no geometry...
    assert mesh.tessellate(group, fn=model.effective_fn()) == []
    # ...but the scene still shows the cube via the Linked copy
    assert len(mesh.tessellate(model.root, fn=model.effective_fn())) > 0


def test_masters_not_emitted_as_scene_geometry(model):
    """A master with no Linked copy adds nothing to the scene."""
    lone = model.new_master()
    lone.add(model._clone(model.add_node("sphere")))
    # remove the sphere that add_node put in the scene, keep only the master
    for child in list(model.root.children):
        if child.type == "sphere":
            model.remove_node(child)
    assert mesh.tessellate(model.root, fn=model.effective_fn()) == []


def test_instance_master_adds_copy_to_scene(model):
    cube = model.add_node("cube")
    master = model.make_master(cube).params["ref"]
    master_node = next(n for n in model.masters_group().children)
    before = len(model.root.children)
    ref = model.instance_master(master_node)
    assert ref.parent is model.root
    assert len(model.root.children) == before + 1


def test_masters_round_trip(model):
    cube = model.add_node("cube")
    model.make_master(cube)
    fd, path = tempfile.mkstemp(suffix=".kcad")
    os.close(fd)
    try:
        document.save_kcad(model, path)
        m2 = DocumentModel()
        document.load_kcad(m2, path)
    finally:
        os.remove(path)
    group = m2.masters_group()
    assert group is not None
    assert [n.name for n in group.children] == ["Cube 1"]


# ------------------------------------------------------------ the tabs

def test_objects_tab_hides_masters_masters_tab_shows_them(app):
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    cube = w.model.add_node("cube")
    w.model.make_master(cube)
    obj_names = [w.builder.tree.topLevelItem(i).text(0)
                 for i in range(w.builder.tree.topLevelItemCount())]
    mas_names = [w.builder.masters_tree.topLevelItem(i).text(0)
                 for i in range(w.builder.masters_tree.topLevelItemCount())]
    assert "Masters" not in obj_names            # store hidden from Objects
    assert "Copy of Cube 1" in obj_names         # the Linked copy shows
    assert "Cube 1" in mas_names                 # the master shows in Masters


# ------------------------------------------------------------ examples

def test_all_examples_build_cleanly(model):
    for label, _cat, build in examples.EXAMPLES:
        m = DocumentModel()
        examples.load_example(m, build)
        assert validate(m.root) == {}, f"{label} has validation errors"
        tris = mesh.tessellate(m.root, fn=m.effective_fn())
        assert len(tris) > 0, f"{label} produced no geometry"


def test_bolt_circle_uses_masters(model):
    examples.load_example(model, examples.bolt_circle)
    assert model.masters_group() is not None
    assert any(n.type == "reference" for n in model.root.walk())


# --------------------------------------------- highlight an off-scene master

def test_selected_world_tris_reaches_a_master(model):
    """A master isn't in the rendered scene, but selecting it must still
    yield highlight geometry (2D silhouette + 3D glow) — so
    selected_world_tris falls back to the master's own subtree."""
    cube = model.add_node("cube")
    model.make_master(cube)
    # walking the whole scene from root would skip the store...
    tris = mesh.selected_world_tris(model.root, {cube.id},
                                    fn=model.effective_fn())
    assert len(tris) > 0


def test_master_difference_shows_in_2d(app):
    """Regression: a non-primitive master (a flange = difference) used to
    return no 2D silhouette because the isolate path walked from root."""
    from khervecad.library import default_part
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    flange = default_part("cf_flange")
    w.model.masters_group(create=True).add(flange)
    w.model.structure_changed.emit()
    w.builder.masters_tree.select_nodes([flange])
    assert w.scene._isolating()
    assert len(w.scene._part_items) == 1        # the silhouette is drawn


# ------------------------------------------------------------ library menu

def test_default_part_builds_with_a_size():
    from khervecad.library import default_part
    node = default_part("cf_tee")
    assert node is not None
    assert node.name                             # got a size-prefixed name
