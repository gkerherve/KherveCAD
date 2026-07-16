"""Tests for Objects (components): module codegen, round-trips,
promotion helpers and preview tessellation.

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
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from PyQt5.QtWidgets import QApplication

from khervecad import document, mesh, scadparse
from khervecad.model import CadNode, DocumentModel, module_name


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def model(app):
    return DocumentModel()


def _body(code):
    return "\n".join(line for line in code.splitlines()
                     if not line.startswith("//")).strip()


def test_component_emits_module_and_call(model):
    comp = model.new_component("Bracket")
    model.add_node("cube", parent=comp)
    code = model.to_scad()
    assert "module Bracket() {" in code
    assert "Bracket();" in code
    # the definition comes before the call
    assert code.index("module Bracket()") < code.rindex("Bracket();")


def test_component_placement_prefix(model):
    comp = model.new_component("Arm")
    comp.params.update(x=10.0, rz=45.0)
    model.add_node("cube", parent=comp)
    code = model.to_scad()
    assert "translate([10, 0, 0]) rotate([0, 0, 45]) Arm();" in code


def test_hidden_component_gets_disable_modifier(model):
    comp = model.new_component("Ghost")
    model.add_node("sphere", parent=comp)
    model.set_visible(comp, False)
    code = model.to_scad()
    assert "*Ghost();" in code
    assert "module Ghost() {" in code            # definition stays clean


def test_module_name_sanitisation():
    assert module_name("Object 2") == "Object_2"
    assert module_name("My Part (v2)") == "My_Part__v2_"
    assert module_name("cube") == "cube_"        # no builtin shadowing
    assert module_name("2nd") == "_2nd"
    assert module_name("") == "part"


def test_duplicate_names_get_unique_modules(model):
    a = model.new_component("Wheel")
    b = model.new_component("Wheel")
    model.add_node("cube", parent=a)
    model.add_node("cube", parent=b)
    code = model.to_scad()
    assert "module Wheel() {" in code
    assert "module Wheel_2() {" in code
    assert "Wheel();" in code
    assert "Wheel_2();" in code


def test_scad_roundtrip_components(model, tmp_path):
    """Export -> import -> export must be lossless for an assembly of
    Objects, placement and visibility included."""
    a = model.new_component("Base")
    model.add_node("cube", dict(width=30.0), parent=a)
    b = model.new_component("Lid")
    b.params.update(x=0.0, y=0.0, z=22.0, rz=90.0, color="#aa0000")
    model.add_node("cube", dict(height=2.0), parent=b)
    hidden = model.new_component("Jig")
    model.add_node("cylinder", parent=hidden)
    model.set_visible(hidden, False)

    code1 = model.to_scad()
    path = tmp_path / "assembly.scad"
    document.export_scad(model, str(path))

    other = DocumentModel()
    warnings = scadparse.import_scad(other, str(path))
    assert not warnings
    comps = other.components()
    assert [c.name for c in comps] == ["Base", "Lid", "Jig"]
    assert comps[1].params["z"] == 22.0
    assert comps[1].params["rz"] == 90.0
    assert comps[1].params["color"] == "#aa0000"
    assert comps[2].visible is False
    assert _body(code1) == _body(other.to_scad())


def test_kcad_roundtrip_component(model, tmp_path):
    comp = model.new_component("Frame")
    comp.params.update(x=5.0, ry=30.0)
    model.add_node("cube", parent=comp)
    path = tmp_path / "doc.kcad"
    document.save_kcad(model, str(path))

    other = DocumentModel()
    document.load_kcad(other, str(path))
    loaded = other.components()
    assert len(loaded) == 1
    assert loaded[0].type == "component"
    assert loaded[0].name == "Frame"
    assert loaded[0].params["x"] == 5.0
    assert loaded[0].params["ry"] == 30.0
    assert loaded[0].children[0].type == "cube"


def test_make_component_converts_group_in_place(model):
    c1 = model.add_node("cube")
    c2 = model.add_node("sphere")
    group = model.group_nodes([c1, c2])
    group.params["x"] = 7.0
    comp = model.make_component(group)
    assert comp is group
    assert comp.type == "component"
    assert comp.params["x"] == 7.0               # placement preserved
    assert model.components() == [comp]


def test_make_component_wraps_plain_shape(model):
    cube = model.add_node("cube")
    comp = model.make_component(cube)
    assert comp.type == "component"
    assert comp.children == [cube]
    assert model.components() == [comp]


def test_component_mesh_matches_group(model):
    """The preview places a component exactly like a group."""
    comp = model.new_component("Moved")
    comp.params.update(x=100.0)
    model.add_node("cube", dict(width=10.0, depth=10.0, height=10.0),
                   parent=comp)
    tris = mesh.tessellate(model.root)
    xs = [v[0] for tri in tris for v in tri]
    assert min(xs) == pytest.approx(100.0)
    assert max(xs) == pytest.approx(110.0)
