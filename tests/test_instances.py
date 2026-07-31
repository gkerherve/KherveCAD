"""Tests for the part/assembly model: Object definitions live in the
Object tab, the Main assembly holds *instances* (references that
compile to placed module calls), each mated independently.

Run with: python -m pytest tests/  (offscreen Qt).

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
os.environ.setdefault("KHERVECAD_DISABLE_ENGINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import document, mates, mesh, scadparse
from khervecad.model import CadNode, DocumentModel
from khervecad.treepanel import ObjectTree


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def model(app):
    return DocumentModel()


def _definition(model, name="Bracket", size=10.0):
    comp = model.new_component(name, visible=False)
    model.add_node("cube", dict(width=size, depth=size, height=size),
                   parent=comp)
    return comp


def test_instance_emits_module_call(model):
    comp = _definition(model)
    inst = model.add_instance(comp)
    inst.params.update(x=40.0, rz=90.0)
    code = model.to_scad()
    assert code.count("module Bracket()") == 1
    assert "*Bracket();" in code                 # hidden definition
    assert "translate([40, 0, 0]) rotate([0, 0, 90]) Bracket();" in code


def test_many_instances_one_definition(model):
    comp = _definition(model)
    a = model.add_instance(comp)
    b = model.add_instance(comp)
    assert a.name == "Bracket 1"
    assert b.name == "Bracket 2"
    assert model.instances_of(comp) == [a, b]
    code = model.to_scad()
    assert code.count("module Bracket()") == 1
    assert code.count("Bracket();") >= 3         # def call + 2 instances


def test_instance_renders_definition_locally(model):
    """A hidden definition renders nothing itself; its instance renders
    the local geometry under the instance's own placement."""
    comp = _definition(model, size=10.0)
    inst = model.add_instance(comp)
    inst.params["x"] = 50.0
    comp.params["x"] = 999.0     # definition placement must NOT leak
    tris = mesh.tessellate(model.root)
    xs = [v[0] for t in tris for v in t]
    assert min(xs) == pytest.approx(50.0)
    assert max(xs) == pytest.approx(60.0)


def test_scad_roundtrip_instances(model, tmp_path):
    comp = _definition(model)
    inst = model.add_instance(comp)
    inst.params.update(x=25.0, z=5.0)
    code1 = model.to_scad()
    path = tmp_path / "asm.scad"
    document.export_scad(model, str(path))

    other = DocumentModel()
    warnings = scadparse.import_scad(other, str(path))
    assert not warnings
    comps = other.components()
    assert len(comps) == 1                       # ONE definition
    refs = [c for c in other.root.children if c.type == "reference"]
    assert len(refs) == 1                        # ONE instance
    assert refs[0].params["ref"] == "Bracket"
    assert refs[0].params["x"] == 25.0
    body1 = [l for l in code1.splitlines() if not l.startswith("//")]
    body2 = [l for l in other.to_scad().splitlines()
             if not l.startswith("//")]
    assert body1 == body2


def test_mates_between_two_instances(model):
    """Two instances of ONE Object mate to each other — the point of
    the part/assembly split."""
    comp = _definition(model, size=10.0)
    base = model.add_instance(comp)
    lid = model.add_instance(comp)
    mates.attach(model, lid, base.name, "Bottom", "Top")
    assert (lid.params["x"], lid.params["y"],
            lid.params["z"]) == (0.0, 0.0, 10.0)
    # moving the parent instance carries the child along
    base.params["x"] = 30.0
    mates.refresh(model)
    assert lid.params["x"] == 30.0
    assert lid.params["z"] == 10.0


def test_parts_lists_objects_and_instances(model):
    comp = _definition(model)
    visible_comp = model.new_component("Legacy")     # visible, placed
    model.add_node("sphere", parent=visible_comp)
    inst = model.add_instance(comp)
    names = [p.name for p in mates.parts(model)]
    assert "Legacy" in names
    assert "Bracket 1" in names
    assert names.count("Bracket") == 1               # definition itself

    # a dangling instance is not a part
    inst.params["ref"] = "Nonsense"
    assert "Bracket 1" not in [p.name for p in mates.parts(model)]


def test_main_tree_hides_definitions(model, app):
    comp = _definition(model)                        # hidden definition
    inst = model.add_instance(comp)
    visible_comp = model.new_component("Legacy")
    tree = ObjectTree(model)
    tops = tree._top_nodes()
    assert comp not in tops                          # definition hidden
    assert inst in tops                              # instance shown
    assert visible_comp in tops                      # legacy Object shown


def test_picked_anchor_shared_by_instances(model):
    """A custom anchor stored on the definition resolves from every
    instance."""
    from khervecad import anchors
    comp = _definition(model, size=10.0)
    a = model.add_instance(comp)
    b = model.add_instance(comp)
    b.params["x"] = 100.0
    anchors.add_user_anchor(model, comp, [5.0, 5.0, 10.0],
                            [0.0, 0.0, 1.0], name="Boss")
    for inst, expected_x in ((a, 5.0), (b, 105.0)):
        anchor = mates.find_anchor(mates.definition_of(model, inst),
                                   "Boss")
        pos, direction = anchors.anchor_world(inst, anchor)
        assert pos[0] == pytest.approx(expected_x)
        assert direction[2] == pytest.approx(1.0)


def _assembly_object(model, name="Elbow"):
    """An Object built from instances of another Object — the shape a
    part takes once you snap library parts together inside it."""
    part = _definition(model, "CF40_Blank", size=6.0)
    asm = model.new_component(name)
    model.add_node("cylinder", dict(radius=3.0, height=40.0), parent=asm)
    for i in (1, 2):
        ref = CadNode("reference", f"{part.name} {i}",
                      dict(ref=part.name, z=10.0 * i))
        asm.add(ref)
    model.structure_changed.emit()
    return asm, part


def test_isolated_object_defines_the_modules_it_calls(model):
    """The Object tab renders one Object standalone. Its instances emit
    a bare `CF40_Blank();` call — OpenSCAD renders NOTHING for a module
    it cannot find (a warning, not an error), so without the definition
    those parts silently vanished from the exact render while the
    built-in preview still showed them."""
    asm, _part = _assembly_object(model)
    code = model.subtree_scad(asm)
    assert code.count("CF40_Blank();") == 2       # the two instances
    assert code.count("module CF40_Blank()") == 1
    # ...and only its module: the definition must not also place itself
    # in the isolated scene
    body = code[code.index("module CF40_Blank()"):]
    end = body.index("module Elbow()")
    assert "CF40_Blank();" not in body[:end]
    assert "cube" in body[:end]                   # the module has a body


def test_isolated_object_without_instances_is_unchanged(model):
    comp = _definition(model, "Plain")
    code = model.subtree_scad(comp)
    assert code.count("module Plain()") == 1
    assert code.count("Plain();") == 1


def test_kcad_roundtrip_instance_mate(model, tmp_path):
    comp = _definition(model)
    base = model.add_instance(comp)
    lid = model.add_instance(comp)
    mates.attach(model, lid, base.name, "Bottom", "Top")
    path = tmp_path / "asm.kcad"
    document.save_kcad(model, str(path))

    other = DocumentModel()
    document.load_kcad(other, str(path))
    loaded = [c for c in other.root.children if c.type == "reference"]
    assert len(loaded) == 2
    mate = mates.mate_of(loaded[1])
    assert mate["parent"] == "Bracket 1"
    assert mate["anchor"] == "Bottom"
    # and it still solves after the reload
    loaded[0].params["y"] = 44.0
    mates.refresh(other)
    assert loaded[1].params["y"] == 44.0
