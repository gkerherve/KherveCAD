"""Tests for Linked copies (the retired Masters tab now makes Objects),
and the Examples / Library menus.

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
# The Masters tab was retired (2026-09-19): a master is now a hidden
# Object, and its Linked copies call that Object's module.

def test_make_master_makes_a_hidden_object_and_leaves_a_copy(model):
    cube = model.add_node("cube")
    n = len(mesh.tessellate(cube))
    ref = model.make_master(cube)
    assert model.masters_group() is None         # no store any more
    comp = next(c for c in model.root.children if c.type == "component")
    assert not comp.visible                      # a definition
    assert cube in list(comp.walk())
    assert ref.type == "reference" and ref.parent is model.root
    assert ref.params["ref"] == comp.name
    # the scene still shows the cube once, through the copy
    assert len(mesh.tessellate(model.root)) == n


def test_make_master_inside_a_loop_keeps_the_copy_there(model):
    loop = model.add_node("for_loop")
    part = model.add_node("union", parent=loop)
    model.add_node("cube", parent=part)
    ref = model.make_master(part)
    assert ref.parent is loop
    assert part.type == "component" and part.parent is model.root


def test_a_placed_group_is_wrapped_so_its_move_survives(model):
    part = model.add_node("union")
    model.add_node("cube", parent=part)
    part.params["x"] = 50.0
    model.make_master(part)
    tris = mesh.tessellate(model.root)
    assert min(v[0] for t in tris for v in t) == pytest.approx(50.0)


def _old_document():
    """A tree as the Masters tab saved it: a store with two masters and
    a Linked copy of each."""
    from khervecad.model import CadNode
    root = CadNode("root")
    store = CadNode("masters", "Masters")
    widget = CadNode("union", "Widget")
    widget.add(CadNode("cube", "Cube 1"))
    store.add(widget)
    store.add(CadNode("sphere", "Ball"))
    root.add(store)
    for name, x in (("Widget", 0.0), ("Ball", 40.0)):
        root.add(CadNode("reference", f"Copy of {name}",
                         dict(ref=name, x=x)))
    return root


def test_an_old_masters_document_opens_as_objects(model):
    import json
    root = _old_document()
    before = mesh.tessellate(root, fn=24)
    data = {"format": "kcad", "version": 1,
            "tree": document.node_to_dict(root)}
    fd, path = tempfile.mkstemp(suffix=".kcad")
    os.close(fd)
    try:
        with open(path, "w") as fh:
            json.dump(data, fh)
        document.load_kcad(model, path)
    finally:
        os.remove(path)
    assert model.masters_group() is None
    comps = [c for c in model.root.children if c.type == "component"]
    assert sorted(c.name for c in comps) == ["Ball", "Widget"]
    assert all(not c.visible for c in comps)
    ball = next(c for c in comps if c.name == "Ball")
    assert [n.name for n in ball.children] == ["Ball body"]
    assert len(mesh.tessellate(model.root, fn=24)) == len(before)
    assert validate(model.root) == {}


# ------------------------------------------------------------ the tabs

def test_there_is_no_masters_tab(app):
    from khervecad.mainwindow import MainWindow
    w = MainWindow()
    tabs = [w.builder.tabText(i) for i in range(w.builder.count())]
    assert tabs == ["Main", "Object", "Variables", "Code"]


# ------------------------------------------------------------ examples

def test_all_examples_build_cleanly(model):
    for label, _cat, build in examples.EXAMPLES:
        m = DocumentModel()
        examples.load_example(m, build)
        assert validate(m.root) == {}, f"{label} has validation errors"
        # raw-OpenSCAD examples render only through the engine, so the
        # built-in tessellator legitimately produces nothing for them
        raw = any(n.type == "scad_raw" for n in m.root.walk())
        tris = mesh.tessellate(m.root, fn=m.effective_fn())
        assert raw or len(tris) > 0, f"{label} produced no geometry"


def test_bolt_circle_places_an_object(model):
    examples.load_example(model, examples.bolt_circle)
    assert model.masters_group() is None
    assert any(c.type == "component" and c.name == "Bolt"
               for c in model.root.children)
    assert any(n.type == "reference" for n in model.root.walk())


# ------------------------------------------------------------ library menu

def test_default_part_builds_with_a_size():
    from khervecad.library import default_part
    node = default_part("cf_tee")
    assert node is not None
    assert node.name                             # got a size-prefixed name
