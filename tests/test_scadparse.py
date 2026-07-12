"""Tests for the OpenSCAD importer.

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

from khervecad import document, scadparse
from khervecad.model import DocumentModel


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def model(app):
    return DocumentModel()


def _parse(text):
    root, warnings = scadparse.parse_scad(text)
    return root, warnings


def test_import_primitives(app):
    root, warnings = _parse("""
        // a comment
        translate([5, -3]) circle(r=8, $fn=32);
        translate([1.5, 2]) square([10, 4]);
        cube([20, 10, 5], center=true);
        sphere(d=24);
        cylinder(h=25, r1=10, r2=4, $fn=64, center=false);
    """)
    assert not warnings
    types = [n.type for n in root.children]
    assert types == ["circle", "rect", "cube", "sphere", "cylinder"]
    circle = root.children[0]
    assert circle.params["x"] == 5.0
    assert circle.params["y"] == -3.0
    assert circle.params["radius"] == 8.0
    assert circle.params["segments"] == 32
    assert root.children[3].params["radius"] == 12.0
    cyl = root.children[4]
    assert cyl.params["radius_bottom"] == 10.0
    assert cyl.params["radius_top"] == 4.0


def test_import_booleans_and_extrude(app):
    root, warnings = _parse("""
        difference() {
            linear_extrude(height=6, twist=45) {
                translate([0, 0]) circle(r=30, $fn=64);
            }
            cylinder(h=20, r=5);
        }
    """)
    assert not warnings
    diff = root.children[0]
    assert diff.type == "difference"
    assert diff.children[0].type == "linear_extrude"
    assert diff.children[0].params["twist"] == 45.0
    assert diff.children[0].children[0].type == "circle"


def test_import_disable_modifier(app):
    root, _ = _parse("*cube(5);")
    assert root.children[0].visible is False


def test_import_line_pattern_folds_back(app):
    root, _ = _parse(
        "hull() { translate([0, 0]) circle(d=2, $fn=32); "
        "translate([10, 5]) circle(d=2, $fn=32); }")
    line = root.children[0]
    assert line.type == "line"
    assert line.params["x2"] == 10.0
    assert line.params["y2"] == 5.0
    assert line.params["width"] == 2.0


def test_import_for_loop(app):
    root, _ = _parse("""
        for (a = [0 : 90 : 270]) rotate([0, 0, a])
            translate([20, 0, 0]) cylinder(h=5, r=2);
    """)
    loop = root.children[0]
    assert loop.type == "for_loop"
    assert loop.params["variable"] == "a"
    assert loop.params["end"] == 270.0
    rot = loop.children[0]
    assert rot.type == "rotate"
    assert rot.params["z"] == "a"
    assert rot.children[0].type == "cylinder"
    assert rot.children[0].params["x"] == 20.0


def test_import_for_value_list(app):
    root, _ = _parse("for (x = [1, 2, 4]) sphere(r=x);")
    loop = root.children[0]
    assert loop.loop_values() == [1, 2, 4]
    assert loop.children[0].params["radius"] == "x"


def test_import_if_else(app):
    root, _ = _parse("""
        size = 12;
        if (size > 10) { cube(size); } else { sphere(r=size); }
    """)
    assign, cond = root.children
    assert assign.type == "assign"
    assert assign.params["variable"] == "size"
    assert cond.type == "if_else"
    assert cond.params["condition"] == "size > 10"
    assert cond.children[0].type == "cube"
    else_branch = cond.children[1]
    assert else_branch.name == "Else"
    assert else_branch.children[0].type == "sphere"


def test_import_offset_and_import(app):
    root, _ = _parse("""
        offset(r=3) square(10);
        offset(delta=2, chamfer=true) circle(5);
        translate([1, 2, 3]) import("rotor.stl", convexity=10);
    """)
    assert root.children[0].type == "offset"
    assert root.children[0].params["radius"] == 3.0
    assert root.children[1].params["chamfer"] is True
    stl = root.children[2]
    assert stl.type == "stl_import"
    assert stl.params["path"] == "rotor.stl"
    assert stl.params["z"] == 3.0


def test_import_scalar_rotate_and_scale(app):
    root, _ = _parse("rotate(45) scale(2) square(10);")
    rot = root.children[0]
    assert rot.params["z"] == 45.0
    assert rot.children[0].params["x"] == 2.0


def test_unknown_call_is_skipped_with_warning(app):
    root, warnings = _parse("""
        frobnicate(1, 2) { cube(3); }
        sphere(r=1);
    """)
    assert [n.type for n in root.children] == ["sphere"]
    assert any("frobnicate" in w for w in warnings)


def test_module_definition_skipped(app):
    root, warnings = _parse("""
        module thing(a) { cube(a); }
        cube(5);
    """)
    assert [n.type for n in root.children] == ["cube"]
    assert any("module" in w for w in warnings)


def test_full_roundtrip_export_import_export(model, tmp_path):
    """Everything KherveCAD generates must re-import losslessly."""
    c = model.add_node("circle", dict(x=3.0, y=4.0, radius=6.0,
                                      segments=32))
    ext = model.wrap_nodes([c], "linear_extrude")
    ext.params.update(height=8.0, twist=30.0)
    hole = model.add_node("cylinder")
    model.wrap_nodes([ext, hole], "difference")
    model.add_node("line", dict(x1=0.0, y1=0.0, x2=15.0, y2=5.0,
                                width=3.0))
    loop = model.add_node("for_loop", dict(variable="k", start=0.0,
                                           end=2.0, step=1.0))
    model.add_node("sphere", dict(x="k * 10"), parent=loop)
    model.add_node("assign", dict(variable="bore", value="38.1"))
    hidden = model.add_node("cube")
    model.set_visible(hidden, False)

    code1 = model.to_scad()
    path = tmp_path / "out.scad"
    document.export_scad(model, str(path))

    other = DocumentModel()
    warnings = scadparse.import_scad(other, str(path))
    assert not warnings
    code2 = other.to_scad()
    assert _body(code1) == _body(code2)


def _body(code):
    return "\n".join(line for line in code.splitlines()
                     if not line.startswith("//")).strip()


def test_vector_variable_and_accessors(app):
    """A vector variable used via .x/.y/.z and [i] evaluates."""
    from khervecad import expr
    env = {"plate": [100, 50, 5]}
    assert expr.evaluate("plate.x", env) == 100
    assert expr.evaluate("plate.y", env) == 50
    assert expr.evaluate("plate.z", env) == 5
    assert expr.evaluate("plate[1]", env) == 50
    assert expr.evaluate("plate.x - 2 * 4", env) == 92
    assert expr.evaluate("[1, 2, 3]") == [1, 2, 3]


def test_import_scad_with_dot_accessor(app):
    """A basic file using `plate.z` imports and renders."""
    from khervecad import mesh
    root, warnings = _parse(
        "plate = [100, 50, 5];\n"
        "cube(plate);\n"
        "translate([0, 0, plate.z]) cylinder(h = 10, d = 6);\n")
    m = DocumentModel()
    m.root = root
    assert len(mesh.tessellate(m.root, fn=m.effective_fn())) > 0
